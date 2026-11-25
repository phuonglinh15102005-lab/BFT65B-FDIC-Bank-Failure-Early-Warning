#!/usr/bin/env python3
r"""BFT65B Part 3 supplementary benchmark: old vs optimized pandas vs Polars.

This script reads the *unchanged* Part 2 Parquet snapshot and verified Step 01
Polars evidence. It creates a NEW, compact evidence directory and ZIP; it never
modifies input Parquets or the original Step 01--04 benchmark outputs.

Run in the folder containing the five original Part 3 scripts and Parquets:

    python .\05_fair_baseline_sensitivity.py --reference .\part3_step01_polars_evidence.zip

Use --warmup 3 --repeats 15 (defaults) for the actual Windows experiment.
This is a sensitivity comparison of *implementations*, not a causal estimate
of engine speed or a cold-disk benchmark. Memory estimates are sampled RSS.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import random
import runpy
import statistics
import subprocess
import sys
import threading
import time
import traceback
import uuid
import zipfile


EXPECTED = {
    "clean": ("panel_clean.parquet", "0d1837815820e93eb71508dabd6f48143e2b596b09453606ccf0070c3717e107"),
    "pit": ("panel_pit_base.parquet", "3fce669406ff1898ac85d9c41c6385b7f8c6b27e29ecd041bb0a3c59f6337421"),
}
TASKS = ("crisis_profile", "calendar_lag", "decision_profile")
ENGINES = ("polars", "pandas_original", "pandas_optimized")
INT_FIELDS = {"REPORTS", "DECISIONS", "INVALID_LOAN_DENOM", "MATCHED_PRIOR_QUARTER",
              "VALID_ASSET_GROWTH", "MISSING_P3ASSET", "INVALID_ASSET_DENOM"}
RTOL, ATOL = 1e-10, 1e-9
COLS = {
    "crisis_profile": ("REPDTE", "REPORTS", "MEAN_ASSET", "MEAN_DEP", "MEAN_ROA",
                       "MEAN_EQ_ASSET", "MEAN_NCLNLS_LOANS", "INVALID_LOAN_DENOM"),
    "calendar_lag": ("REPDTE", "REPORTS", "MATCHED_PRIOR_QUARTER", "VALID_ASSET_GROWTH",
                     "MEAN_ASSET_GROWTH", "MEAN_ASSET"),
    "decision_profile": ("DECISION_DATE", "DECISIONS", "MEAN_ASSET", "MEAN_EQ_ASSET",
                         "MEAN_ROA", "MISSING_P3ASSET", "INVALID_ASSET_DENOM"),
}


def must(condition, message):
    if not condition:
        raise AssertionError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def check_sources(root):
    result = {}
    for key, (name, expected) in EXPECTED.items():
        path = root / name
        must(path.is_file(), f"Missing input: {path}")
        actual = sha(path)
        must(actual == expected, f"The archived snapshot changed: {name}; stop instead of mixing runs")
        result[key] = {"filename": name, "sha256": actual, "bytes": path.stat().st_size}
    return result


def read_reference(path):
    must(path.is_file() and zipfile.is_zipfile(path), f"Missing valid reference ZIP: {path}")
    with zipfile.ZipFile(path) as z:
        must(z.testzip() is None, "Reference ZIP CRC failed")
        audit = json.loads(z.read("polars_audit.json"))
        must(audit.get("status") == "PASS", "Polars audit is not PASS")
        for key, (_, digest) in EXPECTED.items():
            must(audit["sources"][key]["sha256"] == digest, "Reference input mismatch: " + key)
        out = {}
        for task in TASKS:
            must(audit["workloads"][task]["status"] == "PASS", "Reference workload failed: " + task)
            raw = z.read(task + ".csv")
            must(hashlib.sha256(raw).hexdigest() == audit["workloads"][task]["csv_sha256"],
                 "Reference aggregate CSV checksum mismatch: " + task)
            rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
            must(len(rows) > 0 and tuple(rows[0]) == COLS[task], "Reference columns changed: " + task)
            out[task] = rows
    return out


def pandas_optimized(pd, task, root):
    """Avoid avoidable conversions/copies; validate panel uniqueness OUTSIDE timed work."""
    if task == "crisis_profile":
        fields = ["CERT", "REPDTE", "ASSET", "DEP", "EQ", "ROA", "LNLSGR", "NCLNLS"]
        # An AND list; date32 Parquet values are Python datetime.date in pandas.
        df = pd.read_parquet(root / EXPECTED["clean"][0], columns=fields,
                             filters=[("REPDTE", ">=", date(2008, 3, 31)),
                                      ("REPDTE", "<=", date(2014, 12, 31))])
        df["REPDTE"] = pd.to_datetime(df["REPDTE"], errors="raise")
        df["EQ_ASSET"] = df["EQ"].div(df["ASSET"].where(df["ASSET"] > 0))
        df["NCLNLS_LOANS"] = df["NCLNLS"].div(df["LNLSGR"].where(df["LNLSGR"] > 0))
        df["INVALID_LOAN_DENOM"] = (df["LNLSGR"].isna() | (df["LNLSGR"] <= 0)).astype("int64")
        result = df.groupby("REPDTE", as_index=False, sort=True).agg(
            REPORTS=("CERT", "size"), MEAN_ASSET=("ASSET", "mean"),
            MEAN_DEP=("DEP", "mean"), MEAN_ROA=("ROA", "mean"),
            MEAN_EQ_ASSET=("EQ_ASSET", "mean"),
            MEAN_NCLNLS_LOANS=("NCLNLS_LOANS", "mean"),
            INVALID_LOAN_DENOM=("INVALID_LOAN_DENOM", "sum"))
        return result[list(COLS[task])].sort_values("REPDTE").reset_index(drop=True)

    if task == "calendar_lag":
        df = pd.read_parquet(root / EXPECTED["clean"][0], columns=["CERT", "REPDTE", "ASSET"])
        df["REPDTE"] = pd.to_datetime(df["REPDTE"], errors="raise")
        df["QID"] = df["REPDTE"].dt.year * 4 + (df["REPDTE"].dt.month - 1) // 3
        previous = df[["CERT", "QID", "ASSET"]].rename(columns={"ASSET": "PREV_ASSET"}).copy()
        previous["QID"] += 1
        previous["PREV_PRESENT"] = 1
        # Unlike the old baseline, this does not recheck keys inside EACH timed merge.
        # Exact one-to-one uniqueness is a separately verified input contract.
        joined = df.merge(previous, on=["CERT", "QID"], how="left", sort=False)
        joined["ASSET_GROWTH"] = (joined["ASSET"].div(
            joined["PREV_ASSET"].where(joined["PREV_ASSET"] > 0)) - 1)
        joined["MATCHED_PRIOR_QUARTER"] = joined["PREV_PRESENT"].notna().astype("int64")
        joined["VALID_ASSET_GROWTH"] = joined["ASSET_GROWTH"].notna().astype("int64")
        result = joined.groupby("REPDTE", as_index=False, sort=True).agg(
            REPORTS=("CERT", "size"),
            MATCHED_PRIOR_QUARTER=("MATCHED_PRIOR_QUARTER", "sum"),
            VALID_ASSET_GROWTH=("VALID_ASSET_GROWTH", "sum"),
            MEAN_ASSET_GROWTH=("ASSET_GROWTH", "mean"), MEAN_ASSET=("ASSET", "mean"))
        return result[list(COLS[task])].sort_values("REPDTE").reset_index(drop=True)

    fields = ["CERT", "DECISION_DATE", "SOURCE_REPDTE", "ASSET", "EQ", "ROA", "P3ASSET"]
    df = pd.read_parquet(root / EXPECTED["pit"][0], columns=fields)
    # Original Part 2 contract: ALL decision dates are <= 2025-06-30, checked
    # once before timing. No full-column timestamp conversion is needed here.
    df["EQ_ASSET"] = df["EQ"].div(df["ASSET"].where(df["ASSET"] > 0))
    df["MISSING_P3ASSET"] = df["P3ASSET"].isna().astype("int64")
    df["INVALID_ASSET_DENOM"] = (df["ASSET"].isna() | (df["ASSET"] <= 0)).astype("int64")
    result = df.groupby("DECISION_DATE", as_index=False, sort=True).agg(
        DECISIONS=("CERT", "size"), MEAN_ASSET=("ASSET", "mean"),
        MEAN_EQ_ASSET=("EQ_ASSET", "mean"), MEAN_ROA=("ROA", "mean"),
        MISSING_P3ASSET=("MISSING_P3ASSET", "sum"),
        INVALID_ASSET_DENOM=("INVALID_ASSET_DENOM", "sum"))
    return result[list(COLS[task])].sort_values("DECISION_DATE").reset_index(drop=True)


def as_records(engine, frame):
    return frame.to_dicts() if engine == "polars" else frame.to_dict(orient="records")


def compare(task, engine, frame, reference):
    must(tuple(frame.columns) == COLS[task], f"{engine}/{task}: output column mismatch")
    rows = as_records(engine, frame)
    expected = reference[task]
    must(len(rows) == len(expected), f"{engine}/{task}: output row mismatch")
    maximum = 0.0
    for idx, (row, gold) in enumerate(zip(rows, expected)):
        for field in COLS[task]:
            actual, target = row[field], gold[field]
            if field in {"REPDTE", "DECISION_DATE"}:
                must(str(actual)[:10] == target, f"{engine}/{task}/{idx}: date mismatch")
            elif field in INT_FIELDS:
                must(int(actual) == int(target), f"{engine}/{task}/{idx}/{field}: integer mismatch")
            elif actual is None or target == "" or (isinstance(actual, float) and math.isnan(actual)):
                must(target == "" and (actual is None or math.isnan(float(actual))),
                     f"{engine}/{task}/{idx}/{field}: null mismatch")
            else:
                a, b = float(actual), float(target)
                must(math.isfinite(a) and math.isfinite(b), f"{engine}/{task}/{idx}/{field}: nonfinite")
                maximum = max(maximum, abs(a - b))
                must(math.isclose(a, b, rel_tol=RTOL, abs_tol=ATOL),
                     f"{engine}/{task}/{idx}/{field}: numeric mismatch {a} vs {b}")
    return maximum


def run_task(engine, task, root, src, lib):
    clean, pit = root / EXPECTED["clean"][0], root / EXPECTED["pit"][0]
    if engine == "polars":
        return {"crisis_profile": src["query_crisis"],
                "calendar_lag": src["query_calendar"],
                "decision_profile": src["query_decision"]}[task](
                    lib, pit if task == "decision_profile" else clean).collect()
    if engine == "pandas_original":
        return {"crisis_profile": src["run_crisis"],
                "calendar_lag": src["run_calendar"],
                "decision_profile": src["run_decision"]}[task](
                    lib, pit if task == "decision_profile" else clean)
    return pandas_optimized(lib, task, root)


class RSS:
    def __init__(self, psutil):
        self.process = psutil.Process()
        self.start = self.process.memory_info().rss
        self.peak = self.start
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.loop, daemon=True)

    def loop(self):
        while not self.stop.wait(0.01):
            self.peak = max(self.peak, self.process.memory_info().rss)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join(timeout=2)
        self.peak = max(self.peak, self.process.memory_info().rss)


def worker(args):
    try:
        import psutil
        if args.engine == "polars":
            import polars as lib
            must(lib.thread_pool_size() == args.threads, "Polars thread count mismatch")
            src = runpy.run_path(str(args.script_dir / "01_polars_core.py"), run_name="polars_module")
        else:
            import pandas as lib
            import pyarrow as pa
            pa.set_cpu_count(args.threads)
            src = runpy.run_path(str(args.script_dir / "02_pandas_parity.py"), run_name="pandas_module")
        reference = read_reference(args.reference)
        times = []
        max_difference = 0.0
        if args.mode == "time":
            for trial in range(args.warmup + args.repeats):
                tic = time.perf_counter()
                frame = run_task(args.engine, args.task, args.data_dir, src, lib)
                duration = time.perf_counter() - tic
                max_difference = max(max_difference, compare(args.task, args.engine, frame, reference))
                times.append({"trial": trial, "warmup": trial < args.warmup, "seconds": duration})
            result = {"status": "PASS", "engine": args.engine, "task": args.task,
                      "mode": args.mode, "times": times, "max_absolute_difference": max_difference}
        else:
            with RSS(psutil) as meter:
                for trial in range(args.warmup + 1):
                    frame = run_task(args.engine, args.task, args.data_dir, src, lib)
            max_difference = compare(args.task, args.engine, frame, reference)
            result = {"status": "PASS", "engine": args.engine, "task": args.task,
                      "mode": args.mode, "baseline_rss_mib": round(meter.start / 2**20, 3),
                      "peak_rss_mib": round(meter.peak / 2**20, 3),
                      "max_absolute_difference": max_difference}
        print("BFT65B_FAIR_BENCHMARK=" + json.dumps(result))
        return 0
    except Exception:
        traceback.print_exc()
        return 2


def run_child(args, engine, task, mode):
    cmd = [sys.executable, str(Path(__file__).resolve()), "--worker",
           "--script-dir", str(args.script_dir), "--data-dir", str(args.data_dir),
           "--reference", str(args.reference), "--threads", str(args.threads),
           "--warmup", str(args.warmup), "--repeats", str(args.repeats),
           "--engine", engine, "--task", task, "--mode", mode]
    env = os.environ.copy()
    for key in ("POLARS_MAX_THREADS", "ARROW_NUM_THREADS", "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[key] = str(args.threads)
    env["PYTHONHASHSEED"] = "0"
    done = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=1200)
    must(done.returncode == 0, f"{engine}/{task}/{mode} failed: {done.stdout[-2000:]} {done.stderr[-2000:]}")
    records = [line.split("=", 1)[1] for line in done.stdout.splitlines()
               if line.startswith("BFT65B_FAIR_BENCHMARK=")]
    must(len(records) == 1, f"{engine}/{task}/{mode}: missing worker result")
    result = json.loads(records[0])
    must(result["status"] == "PASS", "Unexpected worker outcome")
    return result


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def parent(args):
    import pandas as pd
    import polars as pl
    import pyarrow as pa
    import psutil

    inputs = check_sources(args.data_dir)
    _ = read_reference(args.reference)
    for name in ("01_polars_core.py", "02_pandas_parity.py"):
        must((args.script_dir / name).is_file(), "Missing source script: " + name)
    # These contracts are checked once, outside all benchmark timing workers.
    clean = pl.scan_parquet(str(args.data_dir / EXPECTED["clean"][0]))
    pit = pl.scan_parquet(str(args.data_dir / EXPECTED["pit"][0]))
    unique = clean.select(["CERT", "REPDTE"]).unique().select(pl.len()).collect().item()
    must(unique == 1_669_802, "Duplicate bank-quarter keys in the frozen clean panel")
    max_date = pit.select(pl.col("DECISION_DATE").max()).collect().item()
    must(max_date == date(2025, 6, 30), "PIT decision cutoff differs from frozen contract")
    print("Snapshot, unique bank-quarter keys and decision cutoff: PASS", flush=True)

    scheduled = [(task, engine) for task in TASKS for engine in ENGINES]
    random.Random(20261111).shuffle(scheduled)
    times, memory, summary = [], [], []
    for task, engine in scheduled:
        result = run_child(args, engine, task, "time")
        for item in result["times"]:
            times.append({"task": task, "engine": engine, **item})
        measured = [r["seconds"] for r in result["times"] if not r["warmup"]]
        print(f"  {task:<18} {engine:<17} median={statistics.median(measured):.4f}s "
              f"max_diff={result['max_absolute_difference']:.2g}", flush=True)
        summary.append({"task": task, "engine": engine,
                        "median_seconds": round(statistics.median(measured), 7),
                        "mean_seconds": round(statistics.mean(measured), 7),
                        "cv": round(statistics.stdev(measured) / statistics.mean(measured), 5)
                        if len(measured) > 1 else None,
                        "min_seconds": round(min(measured), 7),
                        "max_seconds": round(max(measured), 7),
                        "max_absolute_parity_difference": result["max_absolute_difference"]})

    if not args.skip_memory:
        for task, engine in scheduled:
            result = run_child(args, engine, task, "memory")
            memory.append({"task": task, "engine": engine,
                           "baseline_rss_mib": result["baseline_rss_mib"],
                           "peak_rss_mib": result["peak_rss_mib"],
                           "incremental_rss_mib": round(result["peak_rss_mib"] - result["baseline_rss_mib"], 3)})
            print(f"  MEMORY {task}/{engine}: peak={result['peak_rss_mib']:.1f} MiB", flush=True)

    root = args.output_parent / ("part3_step05_fair_benchmark_" +
                                 datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_") +
                                 uuid.uuid4().hex[:6])
    root.mkdir(parents=True, exist_ok=False)
    write_csv(root / "trial_times.csv", times)
    write_csv(root / "timing_summary.csv", summary)
    if memory:
        write_csv(root / "memory_summary.csv", memory)
    info = {"status": "PASS", "purpose": "Sensitivity analysis: original pandas vs optimized pandas vs Polars",
            "execution": "Windows results must be compared with Windows results from this SAME run",
            "python": platform.python_version(), "platform": platform.platform(),
            "versions": {"polars": pl.__version__, "pandas": pd.__version__,
                         "pyarrow": pa.__version__, "psutil": psutil.__version__},
            "threads": args.threads, "warmups": args.warmup, "repeats": args.repeats,
            "timing": "In a separate fresh process for each engine-task, including full input read/transform/materialize; excluding import/verification and output writing",
            "limitation": "Warm OS caches; sequential run schedule; sampled RSS; optimized pandas uses one-time external join-key validation",
            "input_files": inputs, "reference_zip_sha256": sha(args.reference),
            "source_script_sha256": {name: sha(args.script_dir / name)
                                     for name in ("01_polars_core.py", "02_pandas_parity.py")},
            "timing_summary": summary, "memory_summary": memory}
    (root / "step05_audit.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    zpath = root / "part3_step05_fair_benchmark_evidence.zip"
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(root.iterdir()):
            if file.is_file() and file != zpath:
                archive.write(file, arcname=file.name)
    with zipfile.ZipFile(zpath) as archive:
        must(archive.testzip() is None, "Output ZIP CRC failed")
    must(check_sources(args.data_dir) == inputs, "The input files changed during benchmarking")
    print("PART3 STEP 05: PASS")
    print("EVIDENCE ZIP:", zpath)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path.cwd())
    parser.add_argument("--script-dir", type=Path, default=Path.cwd())
    parser.add_argument("--output-parent", type=Path, default=Path.cwd())
    parser.add_argument("--reference", type=Path, default=Path("part3_step01_polars_evidence.zip"))
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--repeats", type=int, default=15)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--skip-memory", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--engine", choices=ENGINES, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--task", choices=TASKS, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--mode", choices=("time", "memory"), default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()
    for key in ("data_dir", "script_dir", "output_parent", "reference"):
        setattr(args, key, getattr(args, key).resolve())
    must(args.repeats >= 1 and args.warmup >= 0 and 1 <= args.threads <= 12, "Invalid settings")
    if args.worker:
        return worker(args)
    return parent(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"PART3 STEP 05: FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(2)
