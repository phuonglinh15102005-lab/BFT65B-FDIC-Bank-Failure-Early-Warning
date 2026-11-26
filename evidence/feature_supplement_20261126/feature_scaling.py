"""Scale the full predictor block with disjoint copies of development bank histories."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
from statistics import median
import subprocess
import sys
import tempfile
import threading
import time

import psutil
import feature_audit as audit


def prepare_layouts(panels, root, builder):
    import polars as pl
    tables = [("panel_clean.parquet", "REPDTE"), ("panel_pit_base.parquet", "DECISION_DATE")]
    bases = {}
    maximum = 0
    for name, date_key in tables:
        base = pl.scan_parquet(panels / name).filter(pl.col(date_key) <= builder.DEV_END)
        stats = base.select(pl.col("CERT").min().alias("min"), pl.col("CERT").max().alias("max"),
                            pl.col("CERT").null_count().alias("nulls"), pl.len().alias("rows")).collect().row(0, named=True)
        audit.require(stats["min"] >= 0 and not stats["nulls"], "Invalid bank key")
        maximum = max(maximum, stats["max"])
        bases[name] = (base, stats["rows"])
    # Original CERT is in [0, stride). Each copy occupies a separate integer interval.
    stride = maximum + 1
    layouts = {}
    for scale in (1, 2, 3):
        directory = root / str(scale)
        directory.mkdir()
        layouts[str(scale)] = {}
        for name, _ in tables:
            base, raw_rows = bases[name]
            schema = base.collect_schema()
            copies = [base.with_columns((pl.col("CERT") + i*stride).cast(schema["CERT"])) for i in range(scale)]
            dataset = pl.concat(copies, parallel=False)
            path = directory / name
            dataset.sink_parquet(path, compression="zstd", compression_level=3, row_group_size=131072,
                                 statistics=True, maintain_order=True)
            saved = pl.scan_parquet(path)
            rows = saved.select(pl.len()).collect().item()
            audit.require(rows == scale*raw_rows and saved.collect_schema() == schema, "Replica layout mismatch")
            layouts[str(scale)][name] = {"rows": rows, "columns": len(schema), "bytes": path.stat().st_size,
                                          "sha256": audit.file_sha(path)}
    return stride, layouts


def run_one(repo, directory, scale, stride, reference_digest):
    import polars as pl
    audit.require(pl.thread_pool_size() == 4, "Expected four Polars threads")
    builder = audit.load_source(repo / audit.BUILDER)
    process = psutil.Process()
    samples = [process.memory_info().rss]
    stopped = threading.Event()

    def sample():
        while not stopped.wait(.020):
            samples.append(process.memory_info().rss)

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    try:
        start = time.perf_counter()
        frame = audit.feature_plan(builder, directory).collect()
        elapsed = time.perf_counter() - start
        samples.append(process.memory_info().rss)
    finally:
        stopped.set()
        sampler.join()
    audit.require(frame.height == scale*audit.ROWS, "Replica output row count mismatch")
    for i in range(scale):
        lower = i*stride
        replica = (frame.filter((pl.col("CERT") >= lower) & (pl.col("CERT") < lower + stride))
                   .with_columns(pl.col("CERT") - lower))
        audit.require(replica.height == audit.ROWS and audit.output_digest(replica) == reference_digest,
                      "Normalized replica differs from the validated 15-feature output")
    return {"scale": scale, "elapsed_s": elapsed, "sampled_peak_RSS_MiB": max(samples)/2**20,
            "rss_samples": len(samples), "output_rows": frame.height, "verified_replicas": scale}


def run_study(opts):
    audit.require(not opts.out.exists(), "Choose a new output path")
    for var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[var] = "1"
    os.environ["POLARS_MAX_THREADS"] = "4"
    audit.verify_inputs(opts.repo, opts.panels)
    reference = json.loads(opts.reference.read_text(encoding="utf-8"))
    audit.require(reference["status"] == "PASS" and reference["panel_sha256"] == audit.PANEL_DIGESTS
                  and reference["source_sha256"] == audit.SOURCES, "Use a local feature audit result")
    digest = reference["validated_output_sha256"]
    builder = audit.load_source(opts.repo / audit.BUILDER)
    with tempfile.TemporaryDirectory(prefix="bft65b-feature-scale-", dir=opts.scratch_parent) as temp:
        root = Path(temp)
        stride, layouts = prepare_layouts(opts.panels, root, builder)
        warmups, measured = [], []
        # One warmup per scale and a balanced Latin-square order for the three measured blocks.
        blocks = ((1, 2, 3), (1, 2, 3), (2, 3, 1), (3, 1, 2))
        for block, order in enumerate(blocks):
            for scale in order:
                command = [sys.executable, "-B", __file__, "worker", "--repo", str(opts.repo),
                           "--directory", str(root / str(scale)), "--scale", str(scale),
                           "--stride", str(stride), "--digest", digest]
                completed = subprocess.run(command, stdout=subprocess.PIPE, text=True, check=True)
                record = {"block": block, **json.loads(completed.stdout)}
                (measured if block else warmups).append(record)
                print("block", block, "scale", scale, "seconds", round(record["elapsed_s"], 3), flush=True)
    summaries = {}
    for scale in (1, 2, 3):
        rows = [x for x in measured if x["scale"] == scale]
        times = [x["elapsed_s"] for x in rows]
        peaks = [x["sampled_peak_RSS_MiB"] for x in rows]
        summaries[str(scale)] = {"output_rows": rows[0]["output_rows"], "seconds_median": median(times),
                                  "seconds_range": [min(times), max(times)], "peak_RSS_MiB_median": median(peaks),
                                  "peak_RSS_MiB_max": max(peaks)}
    audit.verify_inputs(opts.repo, opts.panels)
    result = {"status": "PASS", "utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
              "platform": platform.platform(), "polars": builder.pl.__version__, "threads": 4,
              "host_ram_MiB": psutil.virtual_memory().total/2**20, "source_commit": audit.COMMIT,
              "reference_output_sha256": digest, "panel_sha256": audit.PANEL_DIGESTS, "layouts": layouts,
              "design": "Clean and PIT inputs limited to development dates at all scales; each scale rewritten "
                        "using ZSTD level 3, 131072-row groups and original column types/order. CERT offset alone "
                        "distinguishes copies. Exact native feature source. Fresh process per trial. Timers include "
                        "plan construction and materialization, excluding startup, file generation, parity and output writes. "
                        "Warm OS cache; sampled worker RSS around 20 ms. Every normalized replica checked on sorted "
                        "keys and all 15 outputs against the independently validated result.",
              "scope": "One local feature stage. Replication preserves history shapes; no independent banks, new skew, "
                       "production refresh latency, Spark cluster or original Windows laptop measurement.",
              "warmups": warmups, "measured": measured, "summary": summaries}
    with opts.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    study = modes.add_parser("run")
    study.add_argument("--repo", type=Path, required=True)
    study.add_argument("--panels", type=Path, required=True)
    study.add_argument("--reference", type=Path, required=True)
    study.add_argument("--out", type=Path, required=True)
    study.add_argument("--scratch-parent", type=Path)
    worker = modes.add_parser("worker")
    worker.add_argument("--repo", type=Path, required=True)
    worker.add_argument("--directory", type=Path, required=True)
    worker.add_argument("--scale", type=int, required=True)
    worker.add_argument("--stride", type=int, required=True)
    worker.add_argument("--digest", required=True)
    args = parser.parse_args()
    if args.mode == "worker":
        print(json.dumps(run_one(args.repo, args.directory, args.scale, args.stride, args.digest)))
    else:
        run_study(args)
