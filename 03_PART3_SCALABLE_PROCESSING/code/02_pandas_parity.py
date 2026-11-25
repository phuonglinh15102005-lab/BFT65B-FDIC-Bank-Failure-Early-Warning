#!/usr/bin/env python3
"""BFT65B Part 3 - Step 02: pandas baseline and Polars parity audit.

Copy this file beside panel_clean.parquet and panel_pit_base.parquet, then run:

    python 02_pandas_parity.py

If there is more than one Polars Step 01 folder, specify its evidence ZIP:

    python 02_pandas_parity.py --polars-zip "FULL_PATH_TO_EVIDENCE_ZIP"

This is a one-pass correctness check, NOT yet a timing or RAM benchmark.
Reads original Part 2 files; never overwrites them or the Step 01 evidence.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
from io import BytesIO
import json
import math
import os
from pathlib import Path
import platform
import sys
import time
import uuid
import zipfile


SOURCES = {
    "clean": ("panel_clean.parquet", "0d1837815820e93eb71508dabd6f48143e2b596b09453606ccf0070c3717e107"),
    "pit": ("panel_pit_base.parquet", "3fce669406ff1898ac85d9c41c6385b7f8c6b27e29ecd041bb0a3c59f6337421"),
}
CRISIS_FIRST = date(2008, 3, 31)
CRISIS_LAST = date(2014, 12, 31)
DECISION_LAST = date(2025, 6, 30)
TASKS = {
    "crisis_profile": (
        "REPDTE", "REPORTS", "MEAN_ASSET", "MEAN_DEP", "MEAN_ROA",
        "MEAN_EQ_ASSET", "MEAN_NCLNLS_LOANS", "INVALID_LOAN_DENOM",
    ),
    "calendar_lag": (
        "REPDTE", "REPORTS", "MATCHED_PRIOR_QUARTER", "VALID_ASSET_GROWTH",
        "MEAN_ASSET_GROWTH", "MEAN_ASSET",
    ),
    "decision_profile": (
        "DECISION_DATE", "DECISIONS", "MEAN_ASSET", "MEAN_EQ_ASSET",
        "MEAN_ROA", "MISSING_P3ASSET", "INVALID_ASSET_DENOM",
    ),
}
INTEGER_COLUMNS = {
    "REPORTS", "INVALID_LOAN_DENOM", "MATCHED_PRIOR_QUARTER", "VALID_ASSET_GROWTH",
    "DECISIONS", "MISSING_P3ASSET", "INVALID_ASSET_DENOM",
}
RTOL = 1e-10
ATOL = 1e-8


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_polars_zip(base: Path, specified: Path | None) -> Path:
    if specified:
        archive = specified.resolve()
        require(archive.is_file(), f"Specified Polars evidence ZIP not found: {archive}")
        return archive
    candidates = sorted(base.glob("part3_step01_polars_*/part3_step01_polars_evidence.zip"))
    if len(candidates) == 1:
        return candidates[0].resolve()
    if not candidates:
        raise ValueError(
            "No Polars Step 01 ZIP found beside the input files. "
            "Run Step 01 first, or use --polars-zip with its full ZIP path."
        )
    raise ValueError(
        f"Found {len(candidates)} Polars ZIPs; choose one with --polars-zip "
        "so results are not mixed across runs."
    )


def verify_polars_archive(archive: Path) -> dict:
    require(zipfile.is_zipfile(archive), "Polars evidence is not a valid ZIP")
    with zipfile.ZipFile(archive) as package:
        require(package.testzip() is None, "Polars ZIP integrity/CRC check failed")
        expected_names = {"polars_audit.json"} | {
            f"{name}.csv" for name in TASKS
        } | {f"optimized_plan_{name}.txt" for name in TASKS}
        require(expected_names.issubset(package.namelist()), "Polars ZIP missing mandatory evidence")
        audit = json.loads(package.read("polars_audit.json"))
        require(audit.get("status") == "PASS", "Polars Step 01 is not PASS")
        require(audit.get("synthetic_tests", {}).get("status") == "PASS",
                "Polars synthetic edge-case checks did not PASS")
        for key in SOURCES:
            require(audit["sources"][key]["sha256"] == SOURCES[key][1],
                    f"Polars ZIP refers to a different {key} source")
        files = {}
        for name in TASKS:
            require(audit["workloads"][name]["status"] == "PASS",
                    f"Polars workload {name} is not PASS")
            csv_data = package.read(f"{name}.csv")
            plan_data = package.read(f"optimized_plan_{name}.txt")
            require(sha256_bytes(csv_data) == audit["workloads"][name]["csv_sha256"],
                    f"Polars CSV hash mismatch in {name}")
            require(sha256_bytes(plan_data) == audit["workloads"][name]["optimized_plan_sha256"],
                    f"Polars optimized plan hash mismatch in {name}")
            files[name] = csv_data
    return {"path": str(archive), "sha256": sha256_file(archive), "audit": audit,
            "csv_bytes": files}


def calendar_join(pd, df):
    """Exact previous CALENDAR quarter, matched on bank CERT and quarter id."""
    df = df.copy()
    df["REPDTE"] = pd.to_datetime(df["REPDTE"], errors="raise")
    df["QID"] = df["REPDTE"].dt.year * 4 + ((df["REPDTE"].dt.month - 1) // 3)
    previous = df[["CERT", "QID", "ASSET"]].copy()
    previous["QID"] = previous["QID"] + 1
    previous = previous.rename(columns={"ASSET": "PREV_ASSET"})
    previous["PREV_PRESENT"] = 1
    joined = df.merge(previous, on=["CERT", "QID"], how="left", sort=False,
                      validate="one_to_one")
    joined["ASSET_GROWTH"] = (
        joined["ASSET"].div(joined["PREV_ASSET"].where(joined["PREV_ASSET"] > 0)) - 1
    )
    return joined


def run_crisis(pd, clean: Path):
    fields = ["CERT", "REPDTE", "ASSET", "DEP", "EQ", "ROA", "LNLSGR", "NCLNLS"]
    df = pd.read_parquet(clean, columns=fields)
    df["REPDTE"] = pd.to_datetime(df["REPDTE"], errors="raise")
    mask = df["REPDTE"].between(pd.Timestamp(CRISIS_FIRST), pd.Timestamp(CRISIS_LAST))
    df = df.loc[mask].copy()
    df["EQ_ASSET"] = df["EQ"].div(df["ASSET"].where(df["ASSET"] > 0))
    df["NCLNLS_LOANS"] = df["NCLNLS"].div(df["LNLSGR"].where(df["LNLSGR"] > 0))
    df["INVALID_LOAN_DENOM"] = (df["LNLSGR"].isna() | (df["LNLSGR"] <= 0)).astype("int64")
    result = df.groupby("REPDTE", as_index=False, sort=True).agg(
        REPORTS=("CERT", "size"),
        MEAN_ASSET=("ASSET", "mean"),
        MEAN_DEP=("DEP", "mean"),
        MEAN_ROA=("ROA", "mean"),
        MEAN_EQ_ASSET=("EQ_ASSET", "mean"),
        MEAN_NCLNLS_LOANS=("NCLNLS_LOANS", "mean"),
        INVALID_LOAN_DENOM=("INVALID_LOAN_DENOM", "sum"),
    )
    return result[list(TASKS["crisis_profile"])].sort_values("REPDTE").reset_index(drop=True)


def run_calendar(pd, clean: Path):
    df = pd.read_parquet(clean, columns=["CERT", "REPDTE", "ASSET"])
    df = calendar_join(pd, df)
    df["MATCHED_PRIOR_QUARTER"] = df["PREV_PRESENT"].notna().astype("int64")
    df["VALID_ASSET_GROWTH"] = df["ASSET_GROWTH"].notna().astype("int64")
    result = df.groupby("REPDTE", as_index=False, sort=True).agg(
        REPORTS=("CERT", "size"),
        MATCHED_PRIOR_QUARTER=("MATCHED_PRIOR_QUARTER", "sum"),
        VALID_ASSET_GROWTH=("VALID_ASSET_GROWTH", "sum"),
        MEAN_ASSET_GROWTH=("ASSET_GROWTH", "mean"),
        MEAN_ASSET=("ASSET", "mean"),
    )
    return result[list(TASKS["calendar_lag"])].sort_values("REPDTE").reset_index(drop=True)


def run_decision(pd, pit: Path):
    fields = ["CERT", "DECISION_DATE", "SOURCE_REPDTE", "ASSET", "EQ", "ROA", "P3ASSET"]
    df = pd.read_parquet(pit, columns=fields)
    df["DECISION_DATE"] = pd.to_datetime(df["DECISION_DATE"], errors="raise")
    df = df.loc[df["DECISION_DATE"] <= pd.Timestamp(DECISION_LAST)].copy()
    df["EQ_ASSET"] = df["EQ"].div(df["ASSET"].where(df["ASSET"] > 0))
    df["MISSING_P3ASSET"] = df["P3ASSET"].isna().astype("int64")
    df["INVALID_ASSET_DENOM"] = (df["ASSET"].isna() | (df["ASSET"] <= 0)).astype("int64")
    result = df.groupby("DECISION_DATE", as_index=False, sort=True).agg(
        DECISIONS=("CERT", "size"),
        MEAN_ASSET=("ASSET", "mean"),
        MEAN_EQ_ASSET=("EQ_ASSET", "mean"),
        MEAN_ROA=("ROA", "mean"),
        MISSING_P3ASSET=("MISSING_P3ASSET", "sum"),
        INVALID_ASSET_DENOM=("INVALID_ASSET_DENOM", "sum"),
    )
    return result[list(TASKS["decision_profile"])].sort_values("DECISION_DATE").reset_index(drop=True)


def test_synthetic(pd) -> None:
    sample = pd.DataFrame({
        "CERT": [10, 10, 20, 20, 30, 30],
        "REPDTE": [date(2020, 3, 31), date(2020, 9, 30),
                   date(2020, 3, 31), date(2020, 6, 30),
                   date(2020, 3, 31), date(2020, 6, 30)],
        "ASSET": [100., 150., 0., 200., 100., 120.],
    })
    check = calendar_join(pd, sample)
    gap = check.loc[(check.CERT == 10) & (check.REPDTE == pd.Timestamp(2020, 9, 30))].iloc[0]
    zero = check.loc[(check.CERT == 20) & (check.REPDTE == pd.Timestamp(2020, 6, 30))].iloc[0]
    good = check.loc[(check.CERT == 30) & (check.REPDTE == pd.Timestamp(2020, 6, 30))].iloc[0]
    require(pd.isna(gap.PREV_PRESENT) and pd.isna(gap.ASSET_GROWTH),
            "Synthetic gap wrongly uses previous observed quarter")
    require(zero.PREV_PRESENT == 1 and pd.isna(zero.ASSET_GROWTH),
            "Synthetic zero asset denominator incorrectly yields growth")
    require(good.PREV_PRESENT == 1 and math.isclose(good.ASSET_GROWTH, 0.2),
            "Synthetic true adjacent-quarter asset growth is incorrect")
    test = pd.DataFrame({"ASSET": [100., 0., float("nan")], "EQ": [20.] * 3,
                         "LNLSGR": [50., 0., float("nan")], "NCLNLS": [5., 10., 10.]})
    eq = test.EQ.div(test.ASSET.where(test.ASSET > 0))
    loans = test.NCLNLS.div(test.LNLSGR.where(test.LNLSGR > 0))
    require(math.isclose(eq.iloc[0], 0.2) and math.isclose(loans.iloc[0], 0.1),
            "Synthetic ratios are wrong")
    require(eq.iloc[1:].isna().all() and loans.iloc[1:].isna().all(),
            "Synthetic invalid denominators must yield missing ratios")


def compare_result(pd, np, name: str, actual, reference_bytes: bytes) -> dict:
    """Dates/counts exact; floating aggregates compared by declared tolerance."""
    expected = pd.read_csv(BytesIO(reference_bytes), parse_dates=[TASKS[name][0]])
    expected_columns = list(TASKS[name])
    require(actual.columns.tolist() == expected_columns,
            f"{name}: pandas columns differ from contract")
    require(expected.columns.tolist() == expected_columns,
            f"{name}: Polars reference columns differ from contract")
    discrepancies = []
    if len(actual) != len(expected):
        discrepancies.append({"column": "__row_count__", "pandas": len(actual),
                              "polars": len(expected)})
        return {"status": "FAIL", "polars_rows": len(expected),
                "pandas_rows": len(actual), "columns": {}, "discrepancies": discrepancies}

    date_column = expected_columns[0]
    actual_dates = pd.to_datetime(actual[date_column]).dt.strftime("%Y-%m-%d").tolist()
    reference_dates = expected[date_column].dt.strftime("%Y-%m-%d").tolist()
    if actual_dates != reference_dates:
        discrepancies.append({"column": date_column, "problem": "Date keys/order differ",
                              "first_pandas": actual_dates[:4], "first_polars": reference_dates[:4]})

    columns = {}
    for field in expected_columns[1:]:
        a = actual[field].to_numpy()
        b = expected[field].to_numpy()
        if field in INTEGER_COLUMNS:
            matches = np.asarray(a, dtype="int64") == np.asarray(b, dtype="int64")
            diff = np.abs(np.asarray(a, dtype="int64") - np.asarray(b, dtype="int64"))
            max_diff = int(diff.max()) if len(diff) else 0
            columns[field] = {"type": "exact_integer", "mismatched_quarters": int((~matches).sum()),
                              "max_absolute_difference": max_diff}
        else:
            a = np.asarray(a, dtype="float64")
            b = np.asarray(b, dtype="float64")
            matches = np.isclose(a, b, atol=ATOL, rtol=RTOL, equal_nan=True)
            finite_pair = np.isfinite(a) & np.isfinite(b)
            abs_diff = np.abs(a[finite_pair] - b[finite_pair])
            relative = abs_diff / np.maximum(np.abs(b[finite_pair]), ATOL)
            max_diff = float(abs_diff.max()) if abs_diff.size else 0.0
            max_relative = float(relative.max()) if relative.size else 0.0
            columns[field] = {"type": "floating_tolerance", "rtol": RTOL, "atol": ATOL,
                              "mismatched_quarters": int((~matches).sum()),
                              "max_absolute_difference": max_diff,
                              "max_relative_difference": max_relative,
                              "pandas_nulls": int(np.isnan(a).sum()),
                              "polars_nulls": int(np.isnan(b).sum())}
            if not np.all(np.isfinite(a) | np.isnan(a)):
                discrepancies.append({"column": field, "problem": "pandas result contains Infinity"})
        if not bool(matches.all()):
            bad_indices = np.where(~matches)[0][:5].tolist()
            discrepancies.append({
                "column": field, "problem": "Values differ", "mismatched_quarters": int((~matches).sum()),
                "first_examples": [{"quarter": reference_dates[i],
                                    "pandas": None if pd.isna(a[i]) else float(a[i]),
                                    "polars": None if pd.isna(b[i]) else float(b[i])}
                                   for i in bad_indices],
            })

    return {"status": "PASS" if not discrepancies else "FAIL", "pandas_rows": len(actual),
            "polars_rows": len(expected), "date_keys_equal": actual_dates == reference_dates,
            "columns": columns, "discrepancies": discrepancies}


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    script_dir = Path(__file__).resolve().parent
    parser.add_argument("--data-dir", type=Path, default=script_dir)
    parser.add_argument("--polars-zip", type=Path, default=None)
    parser.add_argument("--output-parent", type=Path, default=script_dir)
    args = parser.parse_args()
    try:
        import pandas as pd
        import numpy as np
    except ImportError as error:
        print(f"PART3 STEP 02: FAIL - Missing library: {error}")
        return 2

    print(f"Python {platform.python_version()} | pandas {pd.__version__} | numpy {np.__version__}")
    try:
        clean = (args.data_dir / SOURCES["clean"][0]).resolve()
        pit = (args.data_dir / SOURCES["pit"][0]).resolve()
        for key, file in (("clean", clean), ("pit", pit)):
            require(file.is_file(), f"Missing {key} source: {file}")
            require(sha256_file(file) == SOURCES[key][1],
                    f"{key}: source file changed since approved Part 2 checkpoint")
        archive = find_polars_zip(args.data_dir.resolve(), args.polars_zip)
        polars = verify_polars_archive(archive)
        test_synthetic(pd)
    except Exception as error:
        print(f"PART3 STEP 02: FAIL - {type(error).__name__}: {error}")
        return 2

    output = args.output_parent.resolve() / (
        "part3_step02_pandas_"
        + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_")
        + uuid.uuid4().hex[:6]
    )
    output.mkdir(parents=True, exist_ok=False)
    results = {
        "project": "BFT65B FDIC Part 3",
        "stage": "02 pandas reference comparison, NOT benchmark",
        "status": "RUNNING",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "polars_source_zip": archive.name,
        "polars_zip_sha256": polars["sha256"],
        "source_sha256": {key: sha for key, (_file, sha) in SOURCES.items()},
        "synthetic_tests": "PASS",
        "floating_tolerance": {"relative": RTOL, "absolute": ATOL},
        "task_results": {},
        "limitations": [
            "One pass per task is only a correctness test, not a valid speed benchmark",
            "Memory not benchmarked; later runs require controlled warmups/repeats",
            "PIT one-quarter delay is assumed, not historically vintage-verified",
        ],
    }
    tasks = {"crisis_profile": lambda: run_crisis(pd, clean),
             "calendar_lag": lambda: run_calendar(pd, clean),
             "decision_profile": lambda: run_decision(pd, pit)}
    try:
        for name, executor in tasks.items():
            print(f"Running pandas {name} and comparing with verified Polars...")
            t0 = time.perf_counter()
            frame = executor()
            elapsed = time.perf_counter() - t0
            parity = compare_result(pd, np, name, frame, polars["csv_bytes"][name])
            parity["single_run_seconds_not_benchmark"] = round(elapsed, 5)
            file = output / f"pandas_{name}.csv"
            frame.to_csv(file, index=False, float_format="%.17g", date_format="%Y-%m-%d")
            parity["pandas_csv_sha256"] = sha256_file(file)
            results["task_results"][name] = parity
            max_abs = max((item.get("max_absolute_difference", 0)
                           for item in parity["columns"].values()), default=0)
            print(f"  {name}: {parity['status']} | rows={len(frame)} | max_abs_difference={max_abs:.6g}")
            if parity["discrepancies"]:
                print("  First mismatch:", parity["discrepancies"][0])

        results["status"] = (
            "PASS" if all(item["status"] == "PASS" for item in results["task_results"].values())
            else "FAIL_PARITY"
        )
        write_json(output / "pandas_parity_audit.json", results)
        (output / "README.txt").write_text(
            "BFT65B Part 3, Step 02 - pandas correctness/parity evidence.\n"
            "The three pandas workloads use exactly the same definitions as\n"
            "Step 01 Polars; dates and integer counts are compared exactly.\n"
            f"Floating comparison: relative tolerance {RTOL}, absolute {ATOL}.\n"
            "One-pass timings are diagnostic only; NOT a fair benchmark.\n"
            "The ZIP contains only aggregated results and an audit, no bank-level data.\n"
            "Please upload this ZIP and the terminal output for independent review.\n",
            encoding="utf-8",
        )
        zip_path = output / "part3_step02_pandas_parity_evidence.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as package:
            for file in sorted(output.iterdir()):
                if file.is_file() and file != zip_path:
                    package.write(file, arcname=file.name)
        print(f"PART3 STEP 02: {results['status']}")
        print(f"OUTPUT FOLDER: {output}")
        print(f"UPLOAD THIS ZIP: {zip_path}")
        return 0 if results["status"] == "PASS" else 2
    except Exception as error:
        results["status"] = "FAIL_EXECUTION"
        results["error"] = f"{type(error).__name__}: {error}"
        write_json(output / "pandas_parity_audit_failed.json", results)
        print(f"PART3 STEP 02: FAIL - {results['error']}")
        print(f"DEBUG OUTPUT: {output / 'pandas_parity_audit_failed.json'}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
