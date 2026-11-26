"""Validate the 15 development predictors against the archived pandas specification."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform


COMMIT = "050889604e449efa26c7bb44943c58cef8477e54"
PANEL_DIGESTS = {
    "panel_clean.parquet": "0d1837815820e93eb71508dabd6f48143e2b596b09453606ccf0070c3717e107",
    "panel_pit_base.parquet": "3fce669406ff1898ac85d9c41c6385b7f8c6b27e29ecd041bb0a3c59f6337421",
}
BUILDER = "04_PART4_FEATURE_PIPELINE/code/part4_step01_reference_UNCHANGED.py"
GATE = "04_PART4_FEATURE_PIPELINE/code/part4_v2_relabel_asof_gate.py"
ORACLE = "evidence/final_review/part4/supplement/original_oracle.py"
SOURCES = {
    BUILDER: "a651be686ca57dc65f9e59e444cab99088ce010247fed56d8986a0b7939cc763",
    GATE: "7807ecebefca1a2d592d450c7c42930578e6d9b5086f39494cf83078c0ff13b3",
    ORACLE: "3dad2f82a3daf5795426c2705c29cf35a49e23c429cf9ac2a54668ac1e213227",
}
KEYS = ["CERT", "DECISION_DATE"]
META = KEYS + ["SOURCE_REPDTE"]
ROWS = 1_232_375


def require(condition, message):
    if not condition:
        raise ValueError(message)


def file_sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def verify_inputs(repo, panels):
    for directory, pins in [(repo, SOURCES), (panels, PANEL_DIGESTS)]:
        for name, expected in pins.items():
            require(file_sha(directory / name) == expected, f"Input hash mismatch for {name}")


def load_source(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def feature_plan(builder, panels):
    import polars as pl
    source = builder.prepare_source_columns(panels / "panel_pit_base.parquet", panels / "panel_clean.parquet")
    return (source.filter(pl.col("DECISION_DATE") <= builder.DEV_END)
            .with_columns(builder.feature_expressions()).select(META + builder.FEATURES))


def output_digest(frame):
    """Use sorted keys plus each column's data type, missing mask and numeric values."""
    import numpy as np
    ordered = frame.sort(KEYS)
    dig = hashlib.sha256()
    for s in ordered.iter_columns():
        dig.update(f"{s.name}|{s.dtype}|{len(s)}\n".encode())
        missing = s.is_null().to_numpy()
        dig.update(np.packbits(missing, bitorder="little").tobytes())
        values = (s.fill_null(0) if missing.any() else s).to_numpy()
        little = values.astype(values.dtype.newbyteorder("<"), copy=False)
        dig.update(little.tobytes())
    return dig.hexdigest()


def audit(repo, panels):
    from datetime import datetime, timezone
    import numpy as np
    import pandas as pd
    import polars as pl
    import pyarrow as pa
    import sklearn
    verify_inputs(repo, panels)
    builder = load_source(repo / BUILDER)
    oracle = load_source(repo / ORACLE)
    gate = load_source(repo / GATE)
    actual = feature_plan(builder, panels).collect().sort(KEYS)
    require(actual.height == ROWS and len(builder.FEATURES) == 15, "Unexpected development dimensions")
    require(actual.select(KEYS).n_unique() == ROWS, "Development keys are not unique")
    aligned = pl.col("SOURCE_REPDTE").dt.offset_by("3mo").dt.month_end() == pl.col("DECISION_DATE")
    require(actual.select(aligned.fill_null(False).all()).item(), "Source quarter mismatch")
    require(actual["DECISION_DATE"].max() == builder.DEV_END, "Unexpected last decision date")
    # Read raw inputs independently for pandas. No outcome, event or score table is an argument.
    raw = pd.read_parquet(panels / "panel_pit_base.parquet", columns=oracle.RAW,
                          filters=[("DECISION_DATE", "<=", builder.DEV_END)]).sort_values(KEYS).reset_index(drop=True)
    clean = pd.read_parquet(panels / "panel_clean.parquet", columns=["CERT", "REPDTE", "ASSET"],
                            filters=[("REPDTE", "<=", builder.DEV_END)])
    for key in META:
        observed = actual[key].to_numpy()
        target = raw[key].to_numpy() if key == "CERT" else pd.to_datetime(raw[key]).to_numpy(dtype="datetime64[D]")
        require(np.array_equal(observed, target), f"Independent input alignment failed for {key}")
    reference = oracle.independent_features(raw, clean)
    require(list(reference.columns) == builder.FEATURES, "Oracle feature order changed")
    validations = {}
    for feature in builder.FEATURES:
        target = reference[feature].to_numpy(dtype=float)
        observed = actual[feature].cast(pl.Float64).to_numpy()
        missing_mismatches = int(np.count_nonzero(actual[feature].is_null().to_numpy() != np.isnan(target)))
        value_mismatches = int(np.count_nonzero(~np.isclose(observed, target, rtol=1e-8,
                                                            atol=1e-9, equal_nan=True)))
        valid = np.isfinite(observed) & np.isfinite(target)
        maximum = float(np.abs(observed[valid] - target[valid]).max()) if valid.any() else None
        validations[feature] = {"null_mask_mismatches": missing_mismatches,
                                "value_mismatches": value_mismatches, "max_abs_finite_difference": maximum}
        require(missing_mismatches == value_mismatches == 0, f"Feature mismatch for {feature}")
    parity = gate.full_pit_source_value_parity(panels / "panel_clean.parquet", panels / "panel_pit_base.parquet", builder)
    require(parity["source_value_rows_checked"] == ROWS and parity["source_fields_checked"] == 11,
            "Wrong source-parity dimensions")
    verify_inputs(repo, panels)
    return {
        "status": "PASS", "scope": "Development financial values only. No labels, fitting or locked scores.",
        "source_commit": COMMIT, "source_sha256": SOURCES, "panel_sha256": PANEL_DIGESTS,
        "utc": datetime.now(timezone.utc).isoformat(), "environment": {
            "python": platform.python_version(), "platform": platform.platform(), "polars": pl.__version__,
            "pandas": pd.__version__, "numpy": np.__version__, "pyarrow": pa.__version__,
            "scikit_learn_import_only": sklearn.__version__,
        },
        "rows": ROWS, "features": len(validations), "cells_compared": ROWS * len(validations),
        "source_cells_compared": ROWS * parity["source_fields_checked"], "source_parity": parity,
        "comparison": {"atol": 1e-9, "rtol": 1e-8, "exact_null_mask": True}, "per_feature": validations,
        "first_decision": str(actual["DECISION_DATE"].min()), "last_decision": str(builder.DEV_END),
        "validated_output_sha256": output_digest(actual),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--panels", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    require(not args.out.exists(), "Choose a new output path")
    result = audit(args.repo, args.panels)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(result["status"], result["cells_compared"], result["source_cells_compared"])
