#!/usr/bin/env python3
"""BFT65B Part 3 - Step 01: verified, read-only Polars transformations.

Run from the folder containing panel_clean.parquet and panel_pit_base.parquet:

    python 01_polars_core.py

Or specify the data folder:

    python 01_polars_core.py --data-dir "C:\\path\\to\\step2c"

This step DOES NOT benchmark against pandas or Spark. It establishes a fixed,
reproducible reference for later cross-engine parity tests. Source Parquet files
are NEVER edited, removed or overwritten. Only aggregate data leave the script.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sys
import time
import uuid
import zipfile


EXPECTED = {
    "clean": {
        "file": "panel_clean.parquet",
        "sha256": "0d1837815820e93eb71508dabd6f48143e2b596b09453606ccf0070c3717e107",
        "rows": 1_669_802,
        "columns": ("CERT", "REPDTE", "ASSET", "DEP", "EQ", "ROA", "LNLSGR", "NCLNLS"),
    },
    "pit": {
        "file": "panel_pit_base.parquet",
        "sha256": "3fce669406ff1898ac85d9c41c6385b7f8c6b27e29ecd041bb0a3c59f6337421",
        "rows": 1_629_398,
        "columns": ("CERT", "DECISION_DATE", "SOURCE_REPDTE", "ASSET", "EQ", "ROA", "P3ASSET"),
    },
}

CRISIS_FIRST = date(2008, 3, 31)
CRISIS_LAST = date(2014, 12, 31)
DECISION_LAST = date(2025, 6, 30)

TASK_COLUMNS = {
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def must(condition: bool, explanation: str) -> None:
    if not condition:
        raise AssertionError(explanation)


def quarter_id(pl, date_col: str):
    return pl.col(date_col).dt.year() * 4 + (pl.col(date_col).dt.month() - 1) // 3


def build_calendar_lag(pl, base):
    """Match the immediately preceding CALENDAR quarter, never the prior observed row."""
    base = base.select("CERT", "REPDTE", "ASSET").with_columns(
        quarter_id(pl, "REPDTE").alias("QID")
    )
    previous = base.select(
        "CERT",
        (pl.col("QID") + 1).alias("QID"),
        pl.col("ASSET").alias("PREV_ASSET"),
        pl.lit(1).alias("PREV_PRESENT"),
    )
    return base.join(previous, on=["CERT", "QID"], how="left").with_columns(
        pl.when(pl.col("PREV_ASSET") > 0)
        .then(pl.col("ASSET") / pl.col("PREV_ASSET") - 1.0)
        .otherwise(None)
        .alias("ASSET_GROWTH")
    )


def query_crisis(pl, clean_file: Path):
    return (
        pl.scan_parquet(str(clean_file))
        .filter(pl.col("REPDTE").is_between(CRISIS_FIRST, CRISIS_LAST))
        .select("CERT", "REPDTE", "ASSET", "DEP", "EQ", "ROA", "LNLSGR", "NCLNLS")
        .with_columns(
            pl.when(pl.col("ASSET") > 0)
            .then(pl.col("EQ") / pl.col("ASSET"))
            .otherwise(None).alias("EQ_ASSET"),
            pl.when(pl.col("LNLSGR") > 0)
            .then(pl.col("NCLNLS") / pl.col("LNLSGR"))
            .otherwise(None).alias("NCLNLS_LOANS"),
        )
        .group_by("REPDTE")
        .agg(
            pl.len().alias("REPORTS"),
            pl.col("ASSET").mean().alias("MEAN_ASSET"),
            pl.col("DEP").mean().alias("MEAN_DEP"),
            pl.col("ROA").mean().alias("MEAN_ROA"),
            pl.col("EQ_ASSET").mean().alias("MEAN_EQ_ASSET"),
            pl.col("NCLNLS_LOANS").mean().alias("MEAN_NCLNLS_LOANS"),
            (pl.col("LNLSGR").is_null() | (pl.col("LNLSGR") <= 0))
            .sum().alias("INVALID_LOAN_DENOM"),
        )
        .sort("REPDTE")
    )


def query_calendar(pl, clean_file: Path):
    return (
        build_calendar_lag(pl, pl.scan_parquet(str(clean_file)))
        .group_by("REPDTE")
        .agg(
            pl.len().alias("REPORTS"),
            pl.col("PREV_PRESENT").is_not_null().sum().alias("MATCHED_PRIOR_QUARTER"),
            pl.col("ASSET_GROWTH").is_not_null().sum().alias("VALID_ASSET_GROWTH"),
            pl.col("ASSET_GROWTH").mean().alias("MEAN_ASSET_GROWTH"),
            pl.col("ASSET").mean().alias("MEAN_ASSET"),
        )
        .sort("REPDTE")
    )


def query_decision(pl, pit_file: Path):
    return (
        pl.scan_parquet(str(pit_file))
        .filter(pl.col("DECISION_DATE") <= DECISION_LAST)
        .select("CERT", "DECISION_DATE", "SOURCE_REPDTE", "ASSET", "EQ", "ROA", "P3ASSET")
        .with_columns(
            pl.when(pl.col("ASSET") > 0)
            .then(pl.col("EQ") / pl.col("ASSET"))
            .otherwise(None).alias("EQ_ASSET")
        )
        .group_by("DECISION_DATE")
        .agg(
            pl.len().alias("DECISIONS"),
            pl.col("ASSET").mean().alias("MEAN_ASSET"),
            pl.col("EQ_ASSET").mean().alias("MEAN_EQ_ASSET"),
            pl.col("ROA").mean().alias("MEAN_ROA"),
            pl.col("P3ASSET").is_null().sum().alias("MISSING_P3ASSET"),
            (pl.col("ASSET").is_null() | (pl.col("ASSET") <= 0))
            .sum().alias("INVALID_ASSET_DENOM"),
        )
        .sort("DECISION_DATE")
    )


def synthetic_tests(pl) -> dict:
    """Independent micro-fixtures for temporal and financial edge cases."""
    sample = pl.DataFrame({
        "CERT": [10, 10, 20, 20, 30, 30],
        "REPDTE": [
            date(2020, 3, 31), date(2020, 9, 30),
            date(2020, 3, 31), date(2020, 6, 30),
            date(2020, 3, 31), date(2020, 6, 30),
        ],
        "ASSET": [100., 150., 0., 200., 100., 120.],
    })
    joined = build_calendar_lag(pl, sample.lazy()).collect()
    cases = {(row["CERT"], row["REPDTE"]): row for row in joined.iter_rows(named=True)}
    missing_q2 = cases[(10, date(2020, 9, 30))]
    zero_denom = cases[(20, date(2020, 6, 30))]
    valid_q2 = cases[(30, date(2020, 6, 30))]
    must(missing_q2["PREV_PRESENT"] is None and missing_q2["ASSET_GROWTH"] is None,
         "Synthetic: a skipped quarter must NOT be forward-filled")
    must(zero_denom["PREV_PRESENT"] == 1 and zero_denom["ASSET_GROWTH"] is None,
         "Synthetic: matched previous quarter with zero assets must have null growth")
    must(valid_q2["PREV_PRESENT"] == 1 and math.isclose(valid_q2["ASSET_GROWTH"], 0.2),
         "Synthetic: valid adjacent-quarter asset growth must equal 20%")

    denoms = pl.DataFrame({
        "ASSET": [100., 0., None], "EQ": [20., 20., 20.],
        "LNLSGR": [50., 0., None], "NCLNLS": [5., 10., 10.],
    }).with_columns(
        pl.when(pl.col("ASSET") > 0).then(pl.col("EQ") / pl.col("ASSET"))
        .otherwise(None).alias("EQ_ASSET"),
        pl.when(pl.col("LNLSGR") > 0).then(pl.col("NCLNLS") / pl.col("LNLSGR"))
        .otherwise(None).alias("NCLNLS_LOANS"),
    )
    records = denoms.to_dicts()
    must(math.isclose(records[0]["EQ_ASSET"], 0.2), "Synthetic: EQ/ASSET wrong")
    must(math.isclose(records[0]["NCLNLS_LOANS"], 0.1), "Synthetic: NCLNLS/LNLSGR wrong")
    must(all(records[i][col] is None for i in (1, 2)
             for col in ("EQ_ASSET", "NCLNLS_LOANS")),
         "Synthetic: zero or missing denominator must produce a null ratio")
    return {
        "status": "PASS", "tests": 6,
        "details": [
            "Skipped calendar quarter does not use preceding observed quarter",
            "Previous-quarter zero assets does not create infinite growth",
            "True adjacent-quarter growth equals 0.20",
            "Positive EQ/ASSET equals 0.20",
            "Positive NCLNLS/LNLSGR equals 0.10",
            "Zero and missing denominators yield nulls",
        ],
    }


def check_output(pl, name: str, frame) -> dict:
    """Full-result invariants; do not mistake them for pandas/Spark parity."""
    date_field = TASK_COLUMNS[name][0]
    must(tuple(frame.columns) == TASK_COLUMNS[name], f"{name}: output schema changed")
    dates = frame[date_field].to_list()
    must(dates == sorted(set(dates)), f"{name}: dates unsorted or duplicated")
    for field, dtype in frame.schema.items():
        if dtype in (pl.Float32, pl.Float64):
            for value in frame[field].to_list():
                must(value is None or math.isfinite(value), f"{name}: {field} has NaN/Inf")
    summary = {"quarters": frame.height, "first_quarter": str(dates[0]),
               "last_quarter": str(dates[-1])}

    if name == "crisis_profile":
        summary.update(rows_scanned_in_window=int(frame["REPORTS"].sum()),
                       invalid_loan_denominators=int(frame["INVALID_LOAN_DENOM"].sum()))
        must(frame.height == 28, "crisis_profile: expected 28 crisis quarters")
        must(dates[0] == CRISIS_FIRST and dates[-1] == CRISIS_LAST,
             "crisis_profile: unexpected crisis time boundaries")
        must(summary["rows_scanned_in_window"] == 210_467,
             "crisis_profile: crisis row count does not match verified input")
        must(summary["invalid_loan_denominators"] == 1_452,
             "crisis_profile: invalid loan denominator count changed")
    elif name == "calendar_lag":
        summary.update(
            total_rows=int(frame["REPORTS"].sum()),
            prior_quarter_matches=int(frame["MATCHED_PRIOR_QUARTER"].sum()),
            valid_growth=int(frame["VALID_ASSET_GROWTH"].sum()),
        )
        summary["unmatched_prior_quarter"] = (
            summary["total_rows"] - summary["prior_quarter_matches"]
        )
        must(frame.height == 170, "calendar_lag: expected 170 quarters")
        must(dates[0] == date(1984, 3, 31) and dates[-1] == date(2026, 6, 30),
             "calendar_lag: unexpected quarter boundaries")
        must(summary["total_rows"] == EXPECTED["clean"]["rows"],
             "calendar_lag: left join lost or duplicated records")
        must(summary["prior_quarter_matches"] == 1_645_928,
             "calendar_lag: prior-quarter matches changed")
        must(summary["valid_growth"] <= summary["prior_quarter_matches"],
             "calendar_lag: valid growth cannot exceed matched prior quarters")
    elif name == "decision_profile":
        summary.update(total_rows=int(frame["DECISIONS"].sum()),
                       p3asset_missing=int(frame["MISSING_P3ASSET"].sum()),
                       invalid_asset_denominators=int(frame["INVALID_ASSET_DENOM"].sum()))
        must(frame.height == 165, "decision_profile: expected 165 decision quarters")
        must(dates[0] == date(1984, 6, 30) and dates[-1] == DECISION_LAST,
             "decision_profile: unexpected decision boundaries")
        must(summary["total_rows"] == EXPECTED["pit"]["rows"],
             "decision_profile: decision row count does not match verified input")
        must(summary["p3asset_missing"] == 954_592,
             "decision_profile: missing P3ASSET count changed")
        must(summary["invalid_asset_denominators"] == 0,
             "decision_profile: unexpected invalid asset denominator")
    return summary


def inspect_source(pl, label: str, path: Path) -> dict:
    must(path.is_file(), f"Missing source file: {path}")
    digest = sha256_file(path)
    must(digest == EXPECTED[label]["sha256"],
         f"{path.name}: SHA-256 does not match the approved Part 2 file")
    schema = pl.scan_parquet(str(path)).collect_schema()
    must(all(column in schema for column in EXPECTED[label]["columns"]),
         f"{path.name}: required columns missing")
    return {"name": path.name, "bytes": path.stat().st_size, "sha256": digest,
            "expected_rows": EXPECTED[label]["rows"], "required_columns_present": True}


def save_json(path: Path, content: dict) -> None:
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")


def write_readme(path: Path) -> None:
    path.write_text(
        "BFT65B Part 3 - Step 01 Polars-only reference evidence\n"
        "==================================================\n"
        "Inputs: exact SHA-256 verified Part 2 Parquet files, never modified.\n"
        "crisis_profile: 2008Q1-2014Q4, denominator-guarded financial ratios.\n"
        "calendar_lag: match bank's immediately previous CALENDAR quarter;\n"
        "              missing quarter remains missing, never forward-filled.\n"
        "decision_profile: outcome-free decision-date summaries to 2025Q2\n"
        "                  using Part 2's one-quarter-lagged PIT table.\n"
        "Financial amounts are as stored by FDIC (thousands of USD); ROA\n"
        "is recorded as percent, while EQ/ASSET and NCLNLS/LNLSGR are fractions.\n"
        "Execution plans are OPTIMIZED Polars plans BEFORE materialization.\n"
        "One observed run time per task is diagnostic only: NOT a benchmark.\n"
        "Do not claim engine parity, Spark support, speedup or cluster thresholds\n"
        "until later stages have been executed and independently compared.\n"
        "PIT availability delay is an explicit assumption, NOT a verified\n"
        "original historical FDIC filing-vintage guarantee.\n"
        "No bank-level identifiers, labels or non-aggregate rows are exported.\n"
        "Upload the evidence ZIP and terminal output for review.\n",
        encoding="utf-8",
    )


def run() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    script_dir = Path(__file__).resolve().parent
    parser.add_argument("--data-dir", type=Path, default=script_dir,
                        help="Directory holding both Part 2 Parquet files")
    parser.add_argument("--output-parent", type=Path, default=script_dir,
                        help="Parent for the NEW timestamped result directory")
    args = parser.parse_args()

    try:
        import polars as pl
    except ImportError:
        print("PART3 STEP 01: FAIL - Polars is not installed in this Python environment.")
        return 2

    clean_file = (args.data_dir / EXPECTED["clean"]["file"]).resolve()
    pit_file = (args.data_dir / EXPECTED["pit"]["file"]).resolve()
    print(f"Polars {pl.__version__} | Python {platform.python_version()}")
    print("Checking exact approved Part 2 source checksums...")
    try:
        source_checks = {
            "clean": inspect_source(pl, "clean", clean_file),
            "pit": inspect_source(pl, "pit", pit_file),
        }
        synthetic = synthetic_tests(pl)
    except Exception as error:
        print(f"PART3 STEP 01: FAIL - {type(error).__name__}: {error}")
        return 2

    # The UUID prevents accidental overwrite even for two runs in the same second.
    run_name = ("part3_step01_polars_"
                + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_")
                + uuid.uuid4().hex[:6])
    folder = args.output_parent.resolve() / run_name
    folder.mkdir(parents=True, exist_ok=False)
    metadata = {
        "project": "BFT65B FDIC Part 3",
        "stage": "01 Polars reference, not a cross-engine benchmark",
        "status": "RUNNING",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "logical_cpus": os.cpu_count(),
        "polars": pl.__version__,
        "polars_max_threads": pl.thread_pool_size(),
        "sources": source_checks,
        "synthetic_tests": synthetic,
        "workloads": {},
        "limitations": [
            "Not a valid comparative benchmark: one non-controlled run per task",
            "No pandas or PySpark parity attempted yet",
            "Historical FDIC filing vintages are unverified; one-quarter PIT lag is assumed",
            "Summaries have no failure labels or future outcomes",
        ],
    }

    queries = {
        "crisis_profile": query_crisis(pl, clean_file),
        "calendar_lag": query_calendar(pl, clean_file),
        "decision_profile": query_decision(pl, pit_file),
    }

    try:
        for name, lazy_query in queries.items():
            print(f"Running {name}...")
            start = time.perf_counter()
            optimized_plan = lazy_query.explain(optimized=True)
            result = lazy_query.collect()
            elapsed = time.perf_counter() - start
            metrics = check_output(pl, name, result)
            csv_file = folder / f"{name}.csv"
            plan_file = folder / f"optimized_plan_{name}.txt"
            result.write_csv(str(csv_file))
            plan_file.write_text(optimized_plan, encoding="utf-8")
            metadata["workloads"][name] = {
                "status": "PASS", "metrics": metrics,
                "diagnostic_single_run_seconds_not_benchmark": round(elapsed, 5),
                "csv_sha256": sha256_file(csv_file),
                "optimized_plan_sha256": sha256_file(plan_file),
            }
            print(f"  PASS: {metrics}")

        metadata["status"] = "PASS"
        write_readme(folder / "README.txt")
        save_json(folder / "polars_audit.json", metadata)
        archive = folder / "part3_step01_polars_evidence.zip"
        with zipfile.ZipFile(archive, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
            for file in sorted(folder.iterdir()):
                if file.is_file() and file != archive:
                    z.write(file, arcname=file.name)
        print("PART3 STEP 01: PASS")
        print("Synthetic edge-case checks: PASS (6)")
        print(f"Output folder: {folder}")
        print(f"UPLOAD THIS ZIP: {archive}")
        return 0
    except Exception as error:
        metadata["status"] = "FAIL"
        metadata["error"] = f"{type(error).__name__}: {error}"
        save_json(folder / "polars_audit_failed.json", metadata)
        print(f"PART3 STEP 01: FAIL - {metadata['error']}")
        print(f"Debug file: {folder / 'polars_audit_failed.json'}")
        return 2


if __name__ == "__main__":
    sys.exit(run())
