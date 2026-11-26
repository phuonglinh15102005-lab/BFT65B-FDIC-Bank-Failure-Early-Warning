"""Measure materialization of all development predictors for one or two simultaneous jobs."""
import argparse
from datetime import datetime, timezone
import json
from multiprocessing import get_context
from multiprocessing.connection import wait
import os
from pathlib import Path
import platform
from statistics import median
import time
import traceback

import psutil
import feature_audit as audit


def worker(channel, repo, panels):
    try:
        import polars as pl
        builder = audit.load_source(repo / audit.BUILDER)
        audit.require(pl.thread_pool_size() == 4, "Expected four Polars threads per job")
        channel.send(("ready", None))
        audit.require(channel.recv() == "run", "Start barrier failed")
        start = time.perf_counter()
        frame = audit.feature_plan(builder, panels).collect()
        end = time.perf_counter()
        channel.send(("done", {"elapsed_s": end-start, "ended_at": end, "rows": frame.height,
                               "predictors": len(builder.FEATURES)}))
        audit.require(channel.recv() == "verify", "Verification barrier failed")
        channel.send(("digest", audit.output_digest(frame)))
    except Exception:
        channel.send(("error", traceback.format_exc()))
    finally:
        channel.close()


def receive(channel, expected):
    if not channel.poll(180):
        raise TimeoutError("Timed out waiting for benchmark process")
    status, payload = channel.recv()
    if status != expected:
        raise RuntimeError(str(payload))
    return payload


def run_batch(repo, panels, jobs, digest):
    ctx = get_context("spawn")
    children, pipes = [], []
    try:
        for _ in range(jobs):
            parent, child = ctx.Pipe()
            proc = ctx.Process(target=worker, args=(child, repo, panels))
            proc.start()
            child.close()
            children.append(proc)
            pipes.append(parent)
        for pipe in pipes:
            receive(pipe, "ready")
        observed = [psutil.Process(proc.pid) for proc in children]
        start = time.perf_counter()
        for pipe in pipes:
            pipe.send("run")
        outstanding = list(pipes)
        timings = []
        peak_rss, samples = 0, 0
        while outstanding:
            peak_rss = max(peak_rss, sum(proc.memory_info().rss for proc in observed))
            samples += 1
            for pipe in wait(outstanding, timeout=.020):
                timings.append(receive(pipe, "done"))
                outstanding.remove(pipe)
            if time.perf_counter()-start > 180:
                raise TimeoutError("Feature computation exceeded three minutes")
        makespan = max(t["ended_at"] for t in timings)-start
        for pipe in pipes:
            pipe.send("verify")
        for pipe in pipes:
            audit.require(receive(pipe, "digest") == digest, "Output differs from the locally validated reference")
        audit.require(all(t["rows"] == audit.ROWS and t["predictors"] == 15 for t in timings),
                      "Unexpected output shape")
        return {"jobs": jobs, "batch_seconds": makespan, "job_seconds": sorted(t["elapsed_s"] for t in timings),
                "peak_sum_RSS_MiB": peak_rss / 2**20, "rss_samples": samples, "verified_outputs": jobs}
    finally:
        for pipe in pipes:
            pipe.close()
        for proc in children:
            proc.join(2)
            if proc.is_alive():
                proc.terminate()
                proc.join()


def benchmark(repo, panels, reference):
    audit.verify_inputs(repo, panels)
    audit.require(reference["status"] == "PASS" and reference["panel_sha256"] == audit.PANEL_DIGESTS
                  and reference["source_sha256"] == audit.SOURCES, "Use a fresh feature_audit.py result")
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[name] = "1"
    os.environ["POLARS_MAX_THREADS"] = "4"
    target = reference["validated_output_sha256"]
    warmup = [run_batch(repo, panels, k, target) for k in (1, 2)]
    trials = []
    for block in range(1, 7):
        order = (1, 2) if block % 2 else (2, 1)
        for jobs in order:
            trial = {"block": block, **run_batch(repo, panels, jobs, target)}
            trials.append(trial)
            print(block, jobs, round(trial["batch_seconds"], 3), flush=True)
    summary = {}
    for jobs in (1, 2):
        group = [v for v in trials if v["jobs"] == jobs]
        elapsed = [v["batch_seconds"] for v in group]
        rss = [v["peak_sum_RSS_MiB"] for v in group]
        summary[str(jobs)] = {"batch_seconds_median": median(elapsed),
                              "batch_seconds_range": [min(elapsed), max(elapsed)],
                              "sampled_sum_RSS_MiB_median": median(rss),
                              "sampled_sum_RSS_MiB_max": max(rss)}
    audit.verify_inputs(repo, panels)
    affinity = len(psutil.Process().cpu_affinity()) if hasattr(psutil.Process(), "cpu_affinity") else None
    return {"status": "PASS", "scope": "Full label-free development predictor block on a separate host. "
            "Two-job batches run the same input twice, using separate processes and a common start barrier. "
            "The first result remains in memory until the second finishes. No fitting, scoring, cluster or SLA test.",
            "utc": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
            "python": platform.python_version(), "logical_cpus_available": affinity,
            "host_ram_MiB": psutil.virtual_memory().total / 2**20, "polars_threads_per_job": 4,
            "reference_environment": reference["environment"], "validated_output_sha256": target,
            "clock": "Barrier release to latest materialized result. Process startup and result verification excluded.",
            "memory": "Maximum sampled simultaneous sum of worker RSS; shared pages may be counted twice. "
                      "Up to 20 ms between polling attempts. Parent process excluded.",
            "cache": "Input hashes and warmups read files before six measured blocks. OS cache was not flushed.",
            "warmups": warmup, "measured": trials, "summary": summary}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--panels", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    audit.require(not args.out.exists(), "Choose a new output path")
    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    result = benchmark(args.repo, args.panels, reference)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
