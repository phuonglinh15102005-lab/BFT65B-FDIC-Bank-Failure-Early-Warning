#!/usr/bin/env python3
r"""BFT65B Part 3 / Step 04: local PySpark reproduction and verified parity.

Run with the frozen, verified clean and PIT Parquet inputs and Step 01 reference.
For a new source snapshot, rebuild reference evidence before requesting parity.

Checks Java, source hashes and the frozen-snapshot Step 01 Polars evidence; executes the
same three bank-quarter transformations with local Spark; validates all 363
aggregate rows and exports Spark physical plans. Source files are read only.

This is a correctness/plan inspection, NOT a controlled Spark benchmark.
Archive-container ZIP SHA is NOT an identity gate; internal
reference CSV SHA and frozen input Parquet hashes remain mandatory.
"""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import csv
from datetime import date, datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
import traceback
import uuid
import zipfile


EXPECTED = {
    "clean": ("panel_clean.parquet", "0d1837815820e93eb71508dabd6f48143e2b596b09453606ccf0070c3717e107"),
    "pit": ("panel_pit_base.parquet", "3fce669406ff1898ac85d9c41c6385b7f8c6b27e29ecd041bb0a3c59f6337421"),
}
EXPECTED_REFERENCE_SHA256 = "bd6282e261486bfa69c7f71cd2d95bce2b7622f8a491340cb7e92b7415ea8f97"
TASKS = ("crisis_profile", "calendar_lag", "decision_profile")
COLUMNS = {
    "crisis_profile": ("REPDTE", "REPORTS", "MEAN_ASSET", "MEAN_DEP", "MEAN_ROA",
                       "MEAN_EQ_ASSET", "MEAN_NCLNLS_LOANS", "INVALID_LOAN_DENOM"),
    "calendar_lag": ("REPDTE", "REPORTS", "MATCHED_PRIOR_QUARTER", "VALID_ASSET_GROWTH",
                     "MEAN_ASSET_GROWTH", "MEAN_ASSET"),
    "decision_profile": ("DECISION_DATE", "DECISIONS", "MEAN_ASSET", "MEAN_EQ_ASSET",
                         "MEAN_ROA", "MISSING_P3ASSET", "INVALID_ASSET_DENOM"),
}
INTEGER_COLUMNS = {"REPORTS", "DECISIONS", "INVALID_LOAN_DENOM", "MATCHED_PRIOR_QUARTER",
                   "VALID_ASSET_GROWTH", "MISSING_P3ASSET", "INVALID_ASSET_DENOM"}
OUTCOME_COUNTS = {
    "crisis_profile": (28, "REPORTS", 210467),
    "calendar_lag": (170, "REPORTS", 1669802),
    "decision_profile": (165, "DECISIONS", 1629398),
}
RTOL, ATOL = 1e-10, 1e-6


def require(test: bool, reason: str) -> None:
    if not test:
        raise ValueError(reason)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as reader:
        for chunk in iter(lambda: reader.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_reference(data_dir: Path, specified: Path | None) -> Path:
    if specified:
        path = specified.resolve()
        require(path.is_file(), f"Step 01 reference does not exist: {path}")
        return path
    candidates = sorted(data_dir.glob("part3_step01_polars_*/part3_step01_polars_evidence.zip"))
    if len(candidates) != 1:
        direct = data_dir / "part3_step01_polars_evidence.zip"
        if direct.is_file():
            return direct
        require(False, "Find exactly one Step 01 reference ZIP, or pass --polars-zip FULL_PATH. "
                f"Found {len(candidates)} timestamped candidates.")
    return candidates[0]


def check_inputs_and_reference(data_dir: Path, zip_path: Path) -> tuple[dict, dict]:
    inputs = {}
    for key, (name, digest) in EXPECTED.items():
        path = data_dir / name
        require(path.is_file(), f"Source file not found: {path}")
        actual = sha256(path)
        require(actual == digest, f"Frozen-snapshot {key} Parquet SHA-256 mismatch")
        inputs[key] = {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": actual}
    require(zipfile.is_zipfile(zip_path), "Step 01 reference is not a ZIP")
    zip_sha = sha256(zip_path)
    # Archive container bytes are NOT an identity contract: ZIP timestamps and
    # member-order metadata can change on valid reruns. The hashes of every
    # internal reference CSV and the exact Parquet inputs are checked below.
    # Retain the container SHA-256 in the output for provenance only.
    # EXPECTED_REFERENCE_SHA256 remains the archived reference hash, NOT a gate.
    reference = {}
    with zipfile.ZipFile(zip_path) as z:
        require(z.testzip() is None, "Corrupted Step 01 reference ZIP")
        mandatory = {"polars_audit.json"} | {f"{task}.csv" for task in TASKS}
        require(mandatory.issubset(set(z.namelist())),
                f"Step 01 evidence missing required internal members: {mandatory - set(z.namelist())}")
        audit = json.loads(z.read("polars_audit.json"))
        require(audit["status"] == "PASS", "Step 01 reference audit is not PASS")
        for key, (_name, digest) in EXPECTED.items():
            require(audit["sources"][key]["sha256"] == digest,
                    f"Step 01 reference has inconsistent {key} source")
        for task in TASKS:
            require(audit["workloads"][task]["status"] == "PASS", f"Reference {task} is not PASS")
            content = z.read(f"{task}.csv")
            require(hashlib.sha256(content).hexdigest() == audit["workloads"][task]["csv_sha256"],
                    f"Reference CSV checksum invalid: {task}")
            rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
            require(rows and tuple(rows[0]) == COLUMNS[task], f"Unexpected reference schema: {task}")
            reference[task] = rows
    return inputs, {"rows": reference, "zip_sha256": zip_sha, "zip_name": zip_path.name}


def java_info() -> dict:
    status = {"java_home": os.environ.get("JAVA_HOME"), "ready": False}
    try:
        proc = subprocess.run(["java", "-version"], capture_output=True, text=True,
                              timeout=15, check=False)
        message = (proc.stderr or proc.stdout).strip()
        status.update(returncode=proc.returncode, version_output=message[:500])
        if proc.returncode == 0:
            version_match = re.search(r'version "(\d+)', message)
            if not version_match:
                version_match = re.search(r'openjdk\s+(\d+)', message)
            major = int(version_match.group(1)) if version_match else None
            status.update(major=major, ready=(major in (17, 21, 25)))
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        status["error"] = str(exc)
    return status


def build_query(task: str, spark, data_dir: Path):
    from pyspark.sql import functions as F
    if task == "crisis_profile":
        df = (spark.read.parquet(str(data_dir / EXPECTED["clean"][0]))
              .filter(F.col("REPDTE").between(date(2008, 3, 31), date(2014, 12, 31)))
              .select("CERT", "REPDTE", "ASSET", "DEP", "EQ", "ROA", "LNLSGR", "NCLNLS")
              .withColumn("EQ_ASSET", F.when(F.col("ASSET") > 0, F.col("EQ") / F.col("ASSET")))
              .withColumn("NCLNLS_LOANS", F.when(F.col("LNLSGR") > 0,
                                                    F.col("NCLNLS") / F.col("LNLSGR"))))
        agg = df.groupBy("REPDTE").agg(
            F.count("*").alias("REPORTS"),
            F.avg("ASSET").alias("MEAN_ASSET"),
            F.avg("DEP").alias("MEAN_DEP"),
            F.avg("ROA").alias("MEAN_ROA"),
            F.avg("EQ_ASSET").alias("MEAN_EQ_ASSET"),
            F.avg("NCLNLS_LOANS").alias("MEAN_NCLNLS_LOANS"),
            F.sum(F.when(F.col("LNLSGR").isNull() | (F.col("LNLSGR") <= 0), 1)
                  .otherwise(0)).alias("INVALID_LOAN_DENOM"))
    elif task == "calendar_lag":
        base = spark.read.parquet(str(data_dir / EXPECTED["clean"][0]))
        joined = calendar_match(base)
        agg = joined.groupBy("REPDTE").agg(
            F.count("*").alias("REPORTS"),
            F.sum(F.when(F.col("PREV_PRESENT").isNotNull(), 1).otherwise(0))
                .alias("MATCHED_PRIOR_QUARTER"),
            F.sum(F.when(F.col("ASSET_GROWTH").isNotNull(), 1).otherwise(0))
                .alias("VALID_ASSET_GROWTH"),
            F.avg("ASSET_GROWTH").alias("MEAN_ASSET_GROWTH"),
            F.avg("ASSET").alias("MEAN_ASSET"))
    elif task == "decision_profile":
        df = (spark.read.parquet(str(data_dir / EXPECTED["pit"][0]))
              .filter(F.col("DECISION_DATE") <= date(2025, 6, 30))
              .select("CERT", "DECISION_DATE", "SOURCE_REPDTE", "ASSET", "EQ", "ROA", "P3ASSET")
              .withColumn("EQ_ASSET", F.when(F.col("ASSET") > 0, F.col("EQ") / F.col("ASSET"))))
        agg = df.groupBy("DECISION_DATE").agg(
            F.count("*").alias("DECISIONS"),
            F.avg("ASSET").alias("MEAN_ASSET"),
            F.avg("EQ_ASSET").alias("MEAN_EQ_ASSET"),
            F.avg("ROA").alias("MEAN_ROA"),
            F.sum(F.when(F.col("P3ASSET").isNull(), 1).otherwise(0))
                .alias("MISSING_P3ASSET"),
            F.sum(F.when(F.col("ASSET").isNull() | (F.col("ASSET") <= 0), 1)
                  .otherwise(0)).alias("INVALID_ASSET_DENOM"))
    else:
        raise ValueError(f"Unknown task: {task}")
    return agg.select(*COLUMNS[task]).orderBy(COLUMNS[task][0])


def calendar_match(source):
    """Self-join on the PRECEDING CALENDAR quarter, never last observed row."""
    from pyspark.sql import functions as F
    base = (source.select("CERT", "REPDTE", "ASSET")
            .withColumn("QID", F.year("REPDTE") * 4 + F.quarter("REPDTE") - 1))
    previous = base.select("CERT", (F.col("QID") + 1).alias("QID"),
                           F.col("ASSET").alias("PREV_ASSET"),
                           F.lit(1).alias("PREV_PRESENT"))
    return (base.join(previous, on=["CERT", "QID"], how="left")
            .withColumn("ASSET_GROWTH", F.when(F.col("PREV_ASSET") > 0,
                                         F.col("ASSET") / F.col("PREV_ASSET") - F.lit(1.0))))


def synthetic_temporal_test(spark) -> dict:
    """Force edge cases to exist; full-data parity alone may not exercise them."""
    from pyspark.sql.types import StructType, StructField, LongType, DateType, DoubleType
    schema = StructType([StructField("CERT", LongType(), False),
                         StructField("REPDTE", DateType(), False),
                         StructField("ASSET", DoubleType(), True)])
    frame = spark.createDataFrame([
        (10, date(2020, 3, 31), 100.), (10, date(2020, 9, 30), 150.),
        (20, date(2020, 3, 31), 0.), (20, date(2020, 6, 30), 200.),
        (30, date(2020, 3, 31), 100.), (30, date(2020, 6, 30), 120.)], schema)
    records = {(r["CERT"], r["REPDTE"]): r for r in
               calendar_match(frame).select("CERT", "REPDTE", "PREV_PRESENT", "ASSET_GROWTH").collect()}
    missing = records[10, date(2020, 9, 30)]
    zero = records[20, date(2020, 6, 30)]
    valid = records[30, date(2020, 6, 30)]
    require(missing["PREV_PRESENT"] is None and missing["ASSET_GROWTH"] is None,
            "Synthetic Spark test: skipped quarter must not be forward-filled")
    require(zero["PREV_PRESENT"] == 1 and zero["ASSET_GROWTH"] is None,
            "Synthetic Spark test: zero denominator must not create growth")
    require(valid["PREV_PRESENT"] == 1 and math.isclose(valid["ASSET_GROWTH"], 0.2),
            "Synthetic Spark test: 20% adjacent-quarter growth mismatch")
    return {"status": "PASS", "tests": 3,
            "description": "Skipped quarter; zero prior assets; valid immediately preceding quarter"}


def verify_rows(task: str, actual: list[dict], expected: list[dict]) -> dict:
    require(len(actual) == len(expected), f"{task}: expected {len(expected)} rows, got {len(actual)}")
    size, count_field, total = OUTCOME_COUNTS[task]
    require(len(actual) == size, f"{task}: unexpected count of quarters")
    require(sum(int(r[count_field]) for r in actual) == total, f"{task}: incorrect total rows")
    max_abs, max_rel = 0.0, 0.0
    for idx, (got, ref) in enumerate(zip(actual, expected)):
        require(tuple(got) == tuple(ref), f"{task}: column order mismatch at row {idx}")
        for field, g in got.items():
            e = ref[field]
            if field in INTEGER_COLUMNS or field in {"REPDTE", "DECISION_DATE"}:
                require(str(g) == e, f"{task}, row {idx}, {field}: {g} != {e}")
            elif g is None or e == "":
                require(g is None and e == "", f"{task}, row {idx}, {field}: null-pattern mismatch")
            else:
                g, e = float(g), float(e)
                require(math.isfinite(g) and math.isfinite(e), f"{task}, row {idx}: nonfinite value")
                max_abs = max(max_abs, abs(g - e))
                max_rel = max(max_rel, abs(g - e) / max(abs(e), 1e-12))
                require(math.isclose(g, e, rel_tol=RTOL, abs_tol=ATOL),
                        f"{task}, row {idx}, {field}: Spark {g} != Polars {e}")
    counts = {}
    if task == "crisis_profile":
        counts["invalid_loan_denominators"] = sum(int(r["INVALID_LOAN_DENOM"]) for r in actual)
        require(counts["invalid_loan_denominators"] == 1452, "Crisis loan denominator invariant failed")
    elif task == "calendar_lag":
        counts["prior_quarter_matches"] = sum(int(r["MATCHED_PRIOR_QUARTER"]) for r in actual)
        require(counts["prior_quarter_matches"] == 1645928, "Adjacent-quarter join count changed")
    else:
        counts["p3asset_missing"] = sum(int(r["MISSING_P3ASSET"]) for r in actual)
        require(counts["p3asset_missing"] == 954592, "Missing P3ASSET count changed")
        require(sum(int(r["INVALID_ASSET_DENOM"]) for r in actual) == 0,
                "Invalid asset denominator count changed")
    return {"status": "PASS", "rows": len(actual), "source_rows": total,
            "max_absolute_difference": max_abs, "max_relative_difference": max_rel,
            "parity_tolerance": {"rtol": RTOL, "atol": ATOL}, "invariants": counts}


def csv_result(path: Path, task: str, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS[task])
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ("" if v is None else format(v, ".17g") if isinstance(v, float)
                                 else str(v)) for k, v in row.items()})


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent)
    p.add_argument("--polars-zip", type=Path, default=None)
    p.add_argument("--cores", type=int, default=4)
    p.add_argument("--driver-memory", default="3g")
    args = p.parse_args()
    root = args.data_dir.resolve()
    require(1 <= args.cores <= 8, "Use between 1 and 8 local Spark cores")
    print("PART3 STEP 04: Spark parity and execution plans")
    print("Python:", sys.version.split()[0], "| OS:", platform.system())
    java = java_info()
    print("JAVA:", "READY" if java["ready"] else "NOT READY", java.get("version_output", java.get("error", "")))
    if not java["ready"]:
        print("PART3 STEP 04: BLOCKED - Please install JDK 17 or 21, set JAVA_HOME and PATH,")
        print("then restart VS Code and verify: java -version")
        return 2

    try:
        from pyspark.sql import SparkSession
        import pyspark
    except ImportError as exc:
        print("PART3 STEP 04: BLOCKED - PySpark is missing:", exc)
        return 2

    ref_path = find_reference(root, args.polars_zip)
    print("Verifying original Part 2 Parquet hashes and Step 01 Polars reference...")
    inputs, reference = check_inputs_and_reference(root, ref_path)

    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
    spark = None
    folder = root / ("part3_step04_spark_" + datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6])
    folder.mkdir(parents=False, exist_ok=False)
    try:
        start = time.perf_counter()
        spark = (SparkSession.builder.master(f"local[{args.cores}]")
                 .appName("BFT65B_Part3_Local_Spark_Parity")
                 .config("spark.ui.enabled", "false")
                 .config("spark.sql.session.timeZone", "UTC")
                 .config("spark.sql.adaptive.enabled", "true")
                 .config("spark.sql.shuffle.partitions", "8")
                 .config("spark.driver.memory", args.driver_memory)
                 .getOrCreate())
        spark.sparkContext.setLogLevel("ERROR")
        startup = time.perf_counter() - start
        synthetic = synthetic_temporal_test(spark)
        print("Synthetic calendar-edge tests: PASS (3/3)")
        results = {}
        for task in TASKS:
            print(f"Running Spark {task} (full input; collecting aggregate only)...", flush=True)
            started = time.perf_counter()
            query = build_query(task, spark, root)
            plan_buffer = io.StringIO()
            with redirect_stdout(plan_buffer):
                query.explain(mode="formatted")
            (folder / f"plan_{task}.txt").write_text(plan_buffer.getvalue(), encoding="utf-8")
            collected = query.collect()
            elapsed = time.perf_counter() - started
            final_plan_buffer = io.StringIO()
            with redirect_stdout(final_plan_buffer):
                query.explain(mode="formatted")
            (folder / f"plan_final_{task}.txt").write_text(final_plan_buffer.getvalue(), encoding="utf-8")
            rows = [row.asDict(recursive=False) for row in collected]
            status = verify_rows(task, rows, reference["rows"][task])
            status["one_shot_execution_seconds"] = round(elapsed, 3)
            status["csv_sha256"] = None
            output_path = folder / f"spark_{task}.csv"
            csv_result(output_path, task, rows)
            status["csv_sha256"] = sha256(output_path)
            results[task] = status
            print(f"  {task}: PASS | quarters={len(rows)} | max difference="
                  f"{status['max_absolute_difference']:.4g} | elapsed={elapsed:.2f}s", flush=True)

        env = {
            "python": sys.version.split()[0], "platform": platform.platform(),
            "pyspark": pyspark.__version__, "spark": spark.version, "java": java,
            "spark_startup_seconds": round(startup, 3),
            "master": spark.sparkContext.master,
            "cores": args.cores, "driver_memory": args.driver_memory,
            "sql_shuffle_partitions": spark.conf.get("spark.sql.shuffle.partitions"),
            "adaptive_query_execution": spark.conf.get("spark.sql.adaptive.enabled"),
            "sql_timezone": spark.conf.get("spark.sql.session.timeZone"),
            "input_files": inputs,
            "reference_zip": {"name": reference["zip_name"], "sha256": reference["zip_sha256"]},
            "measurement_warning": "One execution per task; durations are diagnostic, not statistically comparable to Step 03 medians",
        }
        (folder / "spark_environment.json").write_text(json.dumps(env, indent=2), encoding="utf-8")
        audit = {"status": "PASS", "cross_engine_parity": "PASS", "tasks": results,
                 "synthetic_temporal_checks": synthetic,
                 "explanation": "Spark execution plans are captured for interpretation; no Spark benchmark claim",
                 "source_data_modified": False}
        (folder / "spark_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
        (folder / "README.txt").write_text(
            "Part 3 Step 04: local PySpark reproduction of the three Polars aggregate workloads.\n"
            "All 363 aggregate rows are compared against the original Step 01 ZIP, with exact dates/"
            "integer counts and finite float tolerance.\n"
            "Read spark_audit.json first, then formatted physical plans and three output CSVs.\n"
            "Do not infer cluster speedup or a controlled Spark benchmark from one-shot timings.\n",
            encoding="utf-8")
        package = folder / "part3_step04_spark_evidence.zip"
        with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as z:
            for file in sorted(folder.iterdir()):
                if file.is_file() and file != package:
                    z.write(file, file.name)
        with zipfile.ZipFile(package) as z:
            require(z.testzip() is None, "Output ZIP CRC failed")
        print("PART3 STEP 04: PASS")
        print("Spark evidence ZIP:", package)
        return 0
    except Exception:
        (folder / "spark_audit_failed.txt").write_text(traceback.format_exc(), encoding="utf-8")
        print("PART3 STEP 04: FAIL. See error and spark_audit_failed.txt", file=sys.stderr)
        raise
    finally:
        if spark is not None:
            spark.stop()


if __name__ == "__main__":
    sys.exit(main())
