#!/usr/bin/env python3
"""BFT65B Part 3 - Step 03: controlled Polars/pandas laptop benchmark.

Place this script beside the APPROVED 01_polars_core.py, 02_pandas_parity.py,
panel_clean.parquet and panel_pit_base.parquet, then run:

    python 03_benchmark_local.py

This script automatically finds the single Step 01 and Step 02 evidence ZIPs
in their timestamped subfolders. Use --polars-zip and --pandas-zip if several
versions exist. It NEVER changes the source Parquets or earlier evidence.

Method: fresh child process per engine x task; separately measure execution
latency and sampled peak resident RAM. All measured results are compared with
the approved Polars CSVs. Java/Spark is intentionally outside this step.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
from io import StringIO
import importlib.metadata
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


TASKS = ("crisis_profile", "calendar_lag", "decision_profile")
ENGINES = ("polars", "pandas")
EXPECTED_INPUTS = {
    "clean": ("panel_clean.parquet", "0d1837815820e93eb71508dabd6f48143e2b596b09453606ccf0070c3717e107"),
    "pit": ("panel_pit_base.parquet", "3fce669406ff1898ac85d9c41c6385b7f8c6b27e29ecd041bb0a3c59f6337421"),
}
INTEGER_COLUMNS = {
    "REPORTS", "DECISIONS", "INVALID_LOAN_DENOM", "MATCHED_PRIOR_QUARTER",
    "VALID_ASSET_GROWTH", "MISSING_P3ASSET", "INVALID_ASSET_DENOM",
}
RTOL = 1e-10
ATOL = 1e-8
MiB = 2**20


def must(condition: bool, detail: str) -> None:
    if not condition:
        raise ValueError(detail)


def sha256_file(path: Path) -> str:
    dig = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(4 * 1024 * 1024), b""):
            dig.update(block)
    return dig.hexdigest()


def choose_evidence(folder: Path, prefix: str, name: str, given: Path | None) -> Path:
    if given is not None:
        file = given.resolve()
        must(file.is_file(), f"Cannot find specified {prefix} ZIP: {file}")
        return file
    found = sorted(folder.glob(f"{prefix}_*/{name}"))
    if len(found) == 1:
        return found[0].resolve()
    if not found:
        raise ValueError(f"No {prefix} ZIP found. Use --polars-zip / --pandas-zip as applicable.")
    raise ValueError(f"Found {len(found)} ZIPs for {prefix}; specify the exact one to avoid mixing runs.")


def verify_evidence(polars_zip: Path, pandas_zip: Path) -> dict:
    must(zipfile.is_zipfile(polars_zip), "Polars reference is not a valid ZIP")
    must(zipfile.is_zipfile(pandas_zip), "pandas parity evidence is not a valid ZIP")
    with zipfile.ZipFile(polars_zip) as a, zipfile.ZipFile(pandas_zip) as b:
        must(a.testzip() is None and b.testzip() is None, "An evidence ZIP has a CRC error")
        p = json.loads(a.read("polars_audit.json"))
        q = json.loads(b.read("pandas_parity_audit.json"))
        must(p["status"] == "PASS" and q["status"] == "PASS", "A prior checkpoint is not PASS")
        must(q["polars_zip_sha256"] == sha256_file(polars_zip),
             "Step 02 did not validate against this exact Polars ZIP")
        for key, (_name, digest) in EXPECTED_INPUTS.items():
            must(p["sources"][key]["sha256"] == digest, f"Step 01 {key} input mismatch")
            must(q["source_sha256"][key] == digest, f"Step 02 {key} input mismatch")
        for task in TASKS:
            must(p["workloads"][task]["status"] == "PASS", f"Polars {task} not PASS")
            must(q["task_results"][task]["status"] == "PASS", f"pandas {task} parity not PASS")
            raw = a.read(f"{task}.csv")
            must(hashlib.sha256(raw).hexdigest() == p["workloads"][task]["csv_sha256"],
                 f"Polars {task} CSV checksum failed")
            other = b.read(f"pandas_{task}.csv")
            must(hashlib.sha256(other).hexdigest() == q["task_results"][task]["pandas_csv_sha256"],
                 f"pandas {task} CSV checksum failed")
            must(not q["task_results"][task]["discrepancies"],
                 f"pandas {task} has a stored parity discrepancy")
    return {"polars_zip": {"name": polars_zip.name, "sha256": sha256_file(polars_zip)},
            "pandas_zip": {"name": pandas_zip.name, "sha256": sha256_file(pandas_zip)}}


def verify_inputs(data_dir: Path) -> dict:
    info = {}
    for label, (filename, expected) in EXPECTED_INPUTS.items():
        path = (data_dir / filename).resolve()
        must(path.is_file(), f"Missing source: {path}")
        digest = sha256_file(path)
        must(digest == expected, f"Part 2 {label} Parquet does not match approved SHA-256")
        info[label] = {"name": filename, "bytes": path.stat().st_size, "sha256": digest}
    return info


def load_reference(zip_path: Path, task: str) -> list[dict]:
    with zipfile.ZipFile(zip_path) as package:
        rows = list(csv.DictReader(StringIO(package.read(f"{task}.csv").decode("utf-8"))))
    must(bool(rows), f"Empty Polars reference for {task}")
    return rows


def compare_aggregates(actual_csv: str, reference: list[dict], task: str) -> float:
    """Independent CSV comparison: dates/integer counts exact, floats tolerant."""
    actual = list(csv.DictReader(StringIO(actual_csv)))
    must(len(actual) == len(reference), f"{task}: output row count mismatch")
    max_abs = 0.0
    for idx, (row, known) in enumerate(zip(actual, reference)):
        must(tuple(row) == tuple(known), f"{task}, row {idx}: output columns differ")
        for column in row:
            x, y = row[column], known[column]
            if column in ("REPDTE", "DECISION_DATE") or column in INTEGER_COLUMNS:
                must(x == y, f"{task}, row {idx}, {column}: {x!r} != {y!r}")
            elif x == "" or y == "":
                must(x == y, f"{task}, row {idx}, {column}: null-pattern mismatch")
            else:
                a, b = float(x), float(y)
                must(math.isfinite(a) and math.isfinite(b),
                     f"{task}, row {idx}, {column}: nonfinite numeric value")
                max_abs = max(max_abs, abs(a - b))
                must(math.isclose(a, b, rel_tol=RTOL, abs_tol=ATOL),
                     f"{task}, row {idx}, {column}: numeric parity mismatch: {a} vs {b}")
    return max_abs


def result_csv(engine: str, result) -> str:
    if engine == "polars":
        return result.write_csv()
    return result.to_csv(index=False, float_format="%.17g", date_format="%Y-%m-%d")


def measured_query(engine: str, task: str, clean: Path, pit: Path,
                   polars_module: dict | None, pandas_module: dict | None, lib):
    if engine == "polars":
        name = {"crisis_profile": "query_crisis", "calendar_lag": "query_calendar",
                "decision_profile": "query_decision"}[task]
        func = polars_module[name]
        return func(lib, clean if task != "decision_profile" else pit).collect()
    name = {"crisis_profile": "run_crisis", "calendar_lag": "run_calendar",
            "decision_profile": "run_decision"}[task]
    return pandas_module[name](lib, clean if task != "decision_profile" else pit)


class PeakRSS:
    """10-ms sampled RSS of one freshly spawned Python worker (not peak heap)."""

    def __init__(self, psutil):
        self.process = psutil.Process(os.getpid())
        self.stop_signal = threading.Event()
        self.baseline = self.read()
        self.peak = self.baseline
        self.thread = threading.Thread(target=self.run, daemon=True)

    def read(self):
        try:
            return self.process.memory_info().rss
        except Exception:
            return 0

    def run(self):
        while not self.stop_signal.wait(0.01):
            self.peak = max(self.peak, self.read())

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop_signal.set()
        self.thread.join(timeout=2)
        self.peak = max(self.peak, self.read())


def child(args) -> int:
    """Exactly one engine x task in a fresh process; emit a single JSON record."""
    try:
        import psutil

        if args.engine == "polars":
            import polars as lib
            source = runpy.run_path(str(args.script_dir / "01_polars_core.py"),
                                    run_name="bft65b_polars_dependency")
            polars_module, pandas_module = source, None
            used_threads = lib.thread_pool_size()
            must(used_threads == args.threads,
                 f"Polars thread count {used_threads} != requested {args.threads}")
        else:
            import pandas as lib
            import pyarrow as pa
            pa.set_cpu_count(args.threads)
            source = runpy.run_path(str(args.script_dir / "02_pandas_parity.py"),
                                    run_name="bft65b_pandas_dependency")
            polars_module, pandas_module = None, source
            used_threads = pa.cpu_count()

        reference = load_reference(args.polars_zip, args.task)
        clean = args.data_dir / EXPECTED_INPUTS["clean"][0]
        pit = args.data_dir / EXPECTED_INPUTS["pit"][0]
        values = []
        max_abs_difference = 0.0
        if args.mode == "time":
            for iteration in range(args.warmup + args.repeats):
                start = time.perf_counter()
                frame = measured_query(args.engine, args.task, clean, pit,
                                       polars_module, pandas_module, lib)
                duration = time.perf_counter() - start
                max_abs_difference = max(
                    max_abs_difference,
                    compare_aggregates(result_csv(args.engine, frame), reference, args.task),
                )
                values.append({"iteration": iteration, "warmup": iteration < args.warmup,
                               "seconds": round(duration, 9), "rows": len(frame)})
            record = {"status": "PASS", "mode": "time", "engine": args.engine,
                      "task": args.task, "iterations": values,
                      "max_abs_difference": max_abs_difference,
                      "actual_threads": used_threads}
        else:
            with PeakRSS(psutil) as monitor:
                for _ in range(args.warmup + 1):
                    frame = measured_query(args.engine, args.task, clean, pit,
                                           polars_module, pandas_module, lib)
            max_abs_difference = compare_aggregates(
                result_csv(args.engine, frame), reference, args.task)
            record = {"status": "PASS", "mode": "memory", "engine": args.engine,
                      "task": args.task, "actual_threads": used_threads,
                      "baseline_rss_mib": round(monitor.baseline / MiB, 3),
                      "peak_observed_rss_mib": round(monitor.peak / MiB, 3),
                      "increment_over_baseline_mib": round(
                          max(0, monitor.peak - monitor.baseline) / MiB, 3),
                      "max_abs_difference": max_abs_difference,
                      "sample_interval_milliseconds": 10,
                      "memory_runs_after_import": args.warmup + 1}
        print("BFT65B_WORKER_JSON=" + json.dumps(record, separators=(",", ":")))
        return 0
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return 2


def run_child(args, engine: str, task: str, mode: str, env: dict) -> dict:
    command = [sys.executable, str(Path(__file__).resolve()),
               "--worker", "--engine", engine, "--task", task, "--mode", mode,
               "--script-dir", str(args.script_dir),
               "--data-dir", str(args.data_dir), "--polars-zip", str(args.polars_zip),
               "--threads", str(args.threads), "--warmup", str(args.warmup),
               "--repeats", str(args.repeats)]
    started = time.perf_counter()
    completed = subprocess.run(command, env=env,
                               capture_output=True, text=True, timeout=900, check=False)
    total = time.perf_counter() - started
    if completed.returncode != 0:
        raise RuntimeError(
            f"{engine}/{task}/{mode} subprocess failed ({completed.returncode}): "
            + completed.stderr[-4000:] + completed.stdout[-800:]
        )
    matches = [line[len("BFT65B_WORKER_JSON="):] for line in completed.stdout.splitlines()
               if line.startswith("BFT65B_WORKER_JSON=")]
    must(len(matches) == 1, f"{engine}/{task}/{mode}: missing or ambiguous worker response")
    result = json.loads(matches[0])
    must(result["status"] == "PASS" and result["engine"] == engine
         and result["task"] == task and result["mode"] == mode,
         f"{engine}/{task}/{mode}: unexpected worker response")
    result["total_child_wall_seconds_including_startup_and_validation"] = round(total, 4)
    return result


def quartiles(items: list[float]) -> tuple[float, float]:
    sorted_values = sorted(items)
    # Linear interpolation at percentiles 25 and 75, explicit for reproducibility.
    def quantile(q):
        pos = (len(sorted_values) - 1) * q
        low = math.floor(pos)
        high = math.ceil(pos)
        return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (pos - low)
    return quantile(0.25), quantile(0.75)


def csv_save(path: Path, rows: list[dict]) -> None:
    must(bool(rows), f"No rows to write: {path}")
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def json_save(path: Path, result: dict) -> None:
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")


def create_evidence_zip(folder: Path) -> Path:
    target = folder / "part3_step03_benchmark_evidence.zip"
    with zipfile.ZipFile(target, mode="w", compression=zipfile.ZIP_DEFLATED) as package:
        for path in sorted(folder.iterdir()):
            if path.is_file() and path != target:
                package.write(path, arcname=path.name)
    return target


def parent(args) -> int:
    import psutil

    try:
        must(args.threads >= 1 and args.threads <= (os.cpu_count() or 1),
             "--threads must be between 1 and available logical CPU count")
        must(args.warmup >= 1 and args.repeats >= 3,
             "Require at least one warmup and at least three measured iterations")
        args.script_dir = Path(__file__).resolve().parent
        args.data_dir = args.data_dir.resolve()
        args.polars_zip = choose_evidence(
            args.data_dir, "part3_step01_polars", "part3_step01_polars_evidence.zip", args.polars_zip)
        args.pandas_zip = choose_evidence(
            args.data_dir, "part3_step02_pandas", "part3_step02_pandas_parity_evidence.zip", args.pandas_zip)
        for filename in ("01_polars_core.py", "02_pandas_parity.py"):
            must((args.script_dir / filename).is_file(),
                 f"Missing reviewed dependency script: {args.script_dir / filename}")
        sources = verify_inputs(args.data_dir)
        provenance = verify_evidence(args.polars_zip, args.pandas_zip)
    except Exception as error:
        print(f"PART3 STEP 03: FAIL_PRECHECK - {type(error).__name__}: {error}")
        return 2

    folder = args.output_parent.resolve() / (
        "part3_step03_benchmark_"
        + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_")
        + uuid.uuid4().hex[:6]
    )
    folder.mkdir(parents=True, exist_ok=False)
    environment = {
        "project": "BFT65B FDIC Part 3",
        "stage": "03 controlled local Polars/pandas benchmark",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "platform": platform.platform(), "python": platform.python_version(),
        "logical_cpus": psutil.cpu_count(logical=True),
        "physical_cpus": psutil.cpu_count(logical=False),
        "total_ram_gib": round(psutil.virtual_memory().total / 2**30, 2),
        "configured_compute_threads": args.threads,
        "warmups_per_timing_worker": args.warmup,
        "timed_iterations_per_worker": args.repeats,
        "memory_measurement_runs": args.warmup + 1,
        "measurement_method": (
            "Separate fresh child per engine/task/mode. Timings: whole task including "
            "Parquet read, transformations, final materialization; exclude imports, "
            "CSV conversion, verification, output writing, process startup. "
            "Each query re-reads Parquet; one or more warmups precede timing. "
            "Memory: separate fresh child per engine/task, 10-ms sampled Python RSS "
            "over warmup plus one execution, including retained allocator memory. "
            "Host OS filesystem cache is NOT flushed."
        ),
        "libraries": {}, "dependency_scripts_sha256": {
            name: sha256_file(args.script_dir / name)
            for name in ("01_polars_core.py", "02_pandas_parity.py", "03_benchmark_local.py")
        },
        "input_files": sources, "approved_evidence": provenance,
        "limitations": [
            "Benchmarks run on one laptop and on a warm OS file cache, not cold disk",
            "pandas groupby and Polars lazy query have different execution models",
            "PyArrow Parquet read may use multiple threads; pandas groupby is a baseline",
            "CPU affinity, thermal throttling and background Windows load are not controlled",
            "RSS samples can miss short spikes and include retained memory; not heap allocation",
            "No Spark result or cluster extrapolation is warranted from this step alone",
        ],
    }
    for name in ("polars", "pandas", "numpy", "pyarrow", "psutil"):
        try:
            environment["libraries"][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            environment["libraries"][name] = None

    env = os.environ.copy()
    for key in ("POLARS_MAX_THREADS", "ARROW_NUM_THREADS", "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[key] = str(args.threads)
    env["PYTHONHASHSEED"] = "0"
    raw_rows, memory_rows, worker_results = [], [], []
    audit = {"status": "RUNNING", "tasks": list(TASKS), "engines": list(ENGINES),
             "parity_per_iteration_required": True, "worker_success_count": 0,
             "warnings": [], "summary_rows": 0}

    # Fixed pseudo-random engine order by task reduces a universal first/second advantage.
    randomizer = random.Random(20261111)
    schedule = []
    for task in TASKS:
        engines = list(ENGINES)
        randomizer.shuffle(engines)
        schedule.extend((engine, task) for engine in engines)
    environment["schedule"] = [{"engine": e, "task": t} for e, t in schedule]

    try:
        for engine, task in schedule:
            print(f"TIMING: {engine} / {task} (warmup={args.warmup}; repeats={args.repeats})", flush=True)
            result = run_child(args, engine, task, "time", env)
            worker_results.append(result)
            audit["worker_success_count"] += 1
            for item in result["iterations"]:
                raw_rows.append({"engine": engine, "task": task, "iteration": item["iteration"],
                                 "warmup": item["warmup"], "seconds": item["seconds"],
                                 "output_rows": item["rows"], "configured_threads": args.threads})
            timed = [item["seconds"] for item in result["iterations"] if not item["warmup"]]
            print(f"  PASS; median={statistics.median(timed):.4f}s; max parity diff={result['max_abs_difference']:.3g}",
                  flush=True)

        for engine, task in schedule:
            print(f"MEMORY: {engine} / {task} (separate process)", flush=True)
            result = run_child(args, engine, task, "memory", env)
            worker_results.append(result)
            audit["worker_success_count"] += 1
            memory_rows.append({"engine": engine, "task": task,
                                "baseline_rss_mib": result["baseline_rss_mib"],
                                "peak_observed_rss_mib": result["peak_observed_rss_mib"],
                                "increment_over_baseline_mib": result["increment_over_baseline_mib"],
                                "sampling_interval_ms": result["sample_interval_milliseconds"],
                                "configured_threads": args.threads})
            print(f"  PASS; peak observed RSS={result['peak_observed_rss_mib']:.1f} MiB", flush=True)

        summary_rows = []
        for task in TASKS:
            records = {}
            for engine in ENGINES:
                durations = [r["seconds"] for r in raw_rows
                             if r["engine"] == engine and r["task"] == task and not r["warmup"]]
                must(len(durations) == args.repeats, f"{engine}/{task}: incomplete timed trials")
                q1, q3 = quartiles(durations)
                mem = next(r for r in memory_rows if r["engine"] == engine and r["task"] == task)
                records[engine] = {"median": statistics.median(durations),
                                   "mean": statistics.mean(durations),
                                   "p25": q1, "p75": q3,
                                   "cv": statistics.stdev(durations) / statistics.mean(durations),
                                   "max_rss": mem["peak_observed_rss_mib"],
                                   "delta_rss": mem["increment_over_baseline_mib"]}
            polars = records["polars"]
            pandas = records["pandas"]
            must(polars["median"] > 0 and pandas["median"] > 0, "Invalid timing median")
            summary_rows.append({
                "task": task, "repeats": args.repeats, "threads": args.threads,
                "polars_median_s": round(polars["median"], 6),
                "pandas_median_s": round(pandas["median"], 6),
                "pandas_over_polars_speedup": round(pandas["median"] / polars["median"], 4),
                "polars_p25_s": round(polars["p25"], 6),
                "polars_p75_s": round(polars["p75"], 6),
                "pandas_p25_s": round(pandas["p25"], 6),
                "pandas_p75_s": round(pandas["p75"], 6),
                "polars_time_cv": round(polars["cv"], 5),
                "pandas_time_cv": round(pandas["cv"], 5),
                "polars_peak_observed_rss_mib": polars["max_rss"],
                "pandas_peak_observed_rss_mib": pandas["max_rss"],
                "polars_incremental_rss_mib": polars["delta_rss"],
                "pandas_incremental_rss_mib": pandas["delta_rss"],
            })
            if polars["cv"] > 0.20 or pandas["cv"] > 0.20:
                audit["warnings"].append(f"High trial variation (>20% CV) in {task}; interpret the speedup cautiously")

        # Recheck source immutability before PASS.
        must(verify_inputs(args.data_dir) == sources, "Input Parquet changed during benchmark")
        csv_save(folder / "benchmark_trials.csv", raw_rows)
        csv_save(folder / "benchmark_memory.csv", memory_rows)
        csv_save(folder / "benchmark_summary.csv", summary_rows)
        json_save(folder / "benchmark_environment.json", environment)
        json_save(folder / "worker_details.json", {"workers": worker_results})
        audit["status"] = "PASS"
        audit["summary_rows"] = len(summary_rows)
        audit["worker_success_count_expected"] = len(TASKS) * len(ENGINES) * 2
        audit["reference_parity_max_abs_difference"] = max(
            r["max_abs_difference"] for r in worker_results)
        json_save(folder / "benchmark_audit.json", audit)
        (folder / "README.txt").write_text(
            "BFT65B Part 3 Step 03: controlled LOCAL Polars vs pandas benchmark\n"
            "This ZIP is aggregate-only; source Parquets remain unchanged.\n"
            "Latency: separate fresh workers, 1+ warmups and multiple timed queries.\n"
            "Measure scan + transformation + final aggregation, excluding startup,\n"
            "verification, CSV and Python imports. Warm filesystem caches.\n"
            "RAM: separate fresh workers per task; observed process RSS sampled\n"
            "every 10 ms across warmup plus one task execution. This is not a\n"
            "precise allocator peak, and memory retention affects the measure.\n"
            "All runs must match the previously approved Step 01 Polars output.\n"
            "Use medians, IQR, CV and explicit limitations in the report.\n"
            "Do NOT claim a Spark cluster is needed solely from these numbers.\n"
            "Upload this ZIP plus your Terminal screen for external review.\n",
            encoding="utf-8",
        )
        archive = create_evidence_zip(folder)
        print("PART3 STEP 03: PASS")
        for row in summary_rows:
            print(f"  {row['task']}: polars={row['polars_median_s']:.4f}s, "
                  f"pandas={row['pandas_median_s']:.4f}s, "
                  f"pandas/polars={row['pandas_over_polars_speedup']:.2f}x", flush=True)
        for warning in audit["warnings"]:
            print("  WARNING:", warning)
        print(f"UPLOAD THIS ZIP: {archive}")
        return 0
    except Exception as error:
        audit["status"] = "FAIL"
        audit["error"] = f"{type(error).__name__}: {error}"
        json_save(folder / "benchmark_audit_failed.json", audit)
        json_save(folder / "benchmark_environment.json", environment)
        if raw_rows:
            csv_save(folder / "benchmark_trials_partial.csv", raw_rows)
        if memory_rows:
            csv_save(folder / "benchmark_memory_partial.csv", memory_rows)
        archive = create_evidence_zip(folder)
        print(f"PART3 STEP 03: FAIL - {audit['error']}")
        print(f"UPLOAD DEBUG ZIP: {archive}")
        return 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    script_folder = Path(__file__).resolve().parent
    parser.add_argument("--data-dir", type=Path, default=script_folder)
    parser.add_argument("--output-parent", type=Path, default=script_folder)
    parser.add_argument("--polars-zip", type=Path, default=None)
    parser.add_argument("--pandas-zip", type=Path, default=None)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=7)
    # Internal subprocess controls (the user normally never sets these).
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--engine", choices=ENGINES, help=argparse.SUPPRESS)
    parser.add_argument("--task", choices=TASKS, help=argparse.SUPPRESS)
    parser.add_argument("--mode", choices=("time", "memory"), help=argparse.SUPPRESS)
    parser.add_argument("--script-dir", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        must(bool(args.engine and args.task and args.mode and args.script_dir and args.polars_zip),
             "Internal worker requires engine, task, mode, script-dir and Polars reference")
        return child(args)
    return parent(args)


if __name__ == "__main__":
    sys.exit(main())
