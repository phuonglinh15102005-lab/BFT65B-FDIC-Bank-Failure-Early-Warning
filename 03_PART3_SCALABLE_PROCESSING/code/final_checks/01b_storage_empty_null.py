#!/usr/bin/env python3
"""BFT65B Part 1: same-data storage sensitivity with EMPTY CSV null fields.

Run: python 01b_benchmark_storage.py
Inputs: the already validated audit v2 prepared financial snapshot.
Outputs: new benchmark copies plus a small storage_review_bundle.zip.
No API calls, changes to raw/prepared, modelling or automatic file deletion.

CSV is reconstructed from the SAME typed snapshot as the Parquet variants.
Nulls are serialized as empty fields, after explicitly asserting that no non-null
source text field is the empty string; typed schema and fingerprints are checked.
It is an uncompressed CSV baseline, not an original FDIC HTTP CSV download.
Five variants; four materializing queries; one warm-up and three timed repeats
per pair by default. Fresh subprocess per query, fixed thread count, shuffled
order, no cache flushing. This is NOT a cold-disk benchmark.

Sources: course final_report_bft65b.pdf; https://api.fdic.gov/banks/docs/;
https://docs.pola.rs/api/python/stable/reference/lazyframe/ .
AI assistance: ChatGPT, 2026-11-08; disclose in report and README.
"""
from __future__ import annotations

import argparse
import calendar
from collections import defaultdict
import csv
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import shutil
import statistics
import subprocess
import sys
import threading
import time
import zipfile

VERSION = "1.1-empty-csv-null"
DEFAULT_AUDIT = Path('data/audit_results')
NULL_TOKEN = ""
PROJECTION = ["CERT", "REPDTE", "ASSET", "DEP", "EQ", "ROA"]
QUERIES = ["all_rows_all_columns", "all_rows_six_columns", "one_year_six_columns", "one_quarter_six_columns"]
ROW_GROUP_SIZE = 100_000


def say(s):
    print(s, flush=True)


def require(condition, text):
    if not condition:
        raise ValueError(text)


def save_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False, default=str), encoding="utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_csv(path, rows):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["status"])
        writer.writeheader()
        writer.writerows(rows)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def fingerprint(df):
    """Order-independent row-multiset checks, with two seeds, schema and null counts.

    Hashes are strong diagnostics, not a mathematical proof of equality.
    Fixed Polars version is used within every experiment.
    """
    return {"rows": df.height, "schema": [(c, str(t)) for c, t in df.schema.items()],
            "null_counts": df.null_count().row(0),
            "row_hash_sum_seed0": str(df.hash_rows(seed=0).sum()),
            "row_hash_sum_seed42": str(df.hash_rows(seed=42).sum())}


def make_query(manifest, variant, query):
    info = manifest["variants"][variant]
    schema = {k: getattr(pl, v) for k, v in manifest["schema"].items()}
    if info["format"] == "csv":
        lf = pl.scan_csv(info["path"], schema=schema,
                         empty_string_is_null=True)
    elif info["partitioning"] == "none":
        lf = pl.scan_parquet(info["path"], hive_partitioning=False)
    else:
        hs = {"year": pl.Int32}
        if info["partitioning"] == "year_quarter":
            hs["quarter"] = pl.Int32
        lf = pl.scan_parquet(str(Path(info["path"]) / "**/*.parquet"), hive_partitioning=True, hive_schema=hs)
    return apply_query(lf, manifest, query, info["partitioning"])


def apply_query(lf, manifest, query, partitioning="none"):
    year, quarter = manifest["filter_year"], manifest["filter_quarter"]
    if query.startswith("one_"):
        if query == "one_year_six_columns":
            lo, hi = date(year, 1, 1), date(year, 12, 31)
        else:
            m = quarter * 3
            lo, hi = date(year, m - 2, 1), date(year, m, calendar.monthrange(year, m)[1])
        lf = lf.filter(pl.col("REPDTE").is_between(lo, hi, closed="both"))
        # Explicit partition filters have the same time scope as the date filter.
        if partitioning != "none":
            lf = lf.filter(pl.col("year") == year)
        if partitioning == "year_quarter" and query == "one_quarter_six_columns":
            lf = lf.filter(pl.col("quarter") == quarter)
    columns = list(manifest["schema"]) if query == "all_rows_all_columns" else PROJECTION
    return lf.select(columns)


def worker(args):
    manifest = read_json(args.worker_manifest)
    proc = psutil.Process()
    baseline = proc.memory_info().rss
    samples = [baseline]
    stop = threading.Event()

    def sample():
        while not stop.wait(0.01):
            samples.append(proc.memory_info().rss)

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    t0 = time.perf_counter()
    try:
        frame = make_query(manifest, args.variant, args.query).collect(engine="streaming")
        elapsed = time.perf_counter() - t0
        samples.append(proc.memory_info().rss)
    finally:
        stop.set()
        sampler.join()
    # Validation and process startup/imports are outside the timed interval.
    result = {"variant": args.variant, "query": args.query, "seconds": elapsed,
              "baseline_rss_mib": baseline / 2**20, "peak_rss_mib": max(samples) / 2**20,
              "peak_rss_increase_mib": (max(samples) - baseline) / 2**20,
              "memory_samples": len(samples), "fingerprint": fingerprint(frame)}
    save_json(args.worker_output, result)


def experiment(args):
    audit = args.audit_dir.resolve()
    prior = read_json(audit / "summary.json")
    require((audit / "STANDARDIZATION_COMPLETE.json").is_file(), "Missing completed audit marker.")
    require(prior.get("prepared_state") == "STANDARDIZED_FOR_REVIEW" and prior.get("status") == "ACQUISITION_STRUCTURE_PASS",
            "Choose a completed, passing audit directory.")
    input_dir = audit / "prepared/financials"
    files = sorted(input_dir.glob("REPDTE=*.parquet"))
    require(files, f"No prepared financial files in {input_dir}")
    expected_dates = [date(y,m,d) for y in range(date.fromisoformat(prior['start']).year, date.fromisoformat(prior['end']).year+1)
                      for m,d in [(3,31),(6,30),(9,30),(12,31)] if prior['start'] <= date(y,m,d).isoformat() <= prior['end']]
    require({p.name for p in files} == {f"REPDTE={d:%Y%m%d}.parquet" for d in expected_dates}, "Prepared quarter coverage differs from audit.")
    source = pl.scan_parquet([str(p) for p in files], hive_partitioning=False)
    schema = source.collect_schema()
    require(schema.get("CERT") == pl.Int64 and schema.get("REPDTE") == pl.Date, "Use typed prepared Financials.")
    require(set(PROJECTION).issubset(schema), "Missing required benchmark projection columns.")
    require(not {"year", "quarter"}.intersection(schema), "Partition names collide with source columns.")
    require(all(str(t) in {"Int64", "Float64", "String", "Date", "Int32", "Float32"} for t in schema.values()), "Unsupported prepared schema.")
    n = source.select(pl.len()).collect().item()
    require(n == prior['total_financial_rows'], "Financial row count differs from selected audit.")
    text_cols = [c for c,t in schema.items() if t == pl.String]
    if text_cols:
        empty_literal_counts = source.select([((pl.col(c) == '').fill_null(False)).sum().alias(c) for c in text_cols]).collect().row(0)
        require(not any(empty_literal_counts),
            'Source contains non-null empty text values: empty-null CSV cannot preserve their distinction. '
            'Use the original sentinel experiment or an escaped representation instead.')
    root = (args.out or (Path(__file__).resolve().parent / "BFT65B_outputs" / ("storage_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")))).resolve()
    require(not root.exists(), "Output directory exists; choose a new --out path.")
    require(not root.is_relative_to(audit) and not audit.is_relative_to(root), "Output must be separate from audit/prepared inputs.")
    root.parent.mkdir(parents=True, exist_ok=True)
    source_bytes = sum(p.stat().st_size for p in files)
    require(shutil.disk_usage(root.parent).free > max(source_bytes * 10, 512 * 2**20),
            "Not enough free space for benchmark copies. Free disk space or choose --out on another drive.")
    root.mkdir()
    data_dir, reports = root / "benchmark_data", root / "reports"
    data_dir.mkdir();reports.mkdir();(reports / "plans").mkdir();(reports / "runs").mkdir()
    manifest = {"version":VERSION,"source_audit":str(audit),"rows":n,"quarters":len(files),"schema":{c:str(t) for c,t in schema.items()},
                "filter_year":args.year,"filter_quarter":args.quarter,"threads":args.threads,"variants":{}}

    say("[1/4] Creating comparable storage copies. Source data will not change.")
    for name, fmt, comp in [("csv_uncompressed","csv","none"),("parquet_snappy","parquet","snappy"),("parquet_zstd","parquet","zstd")]:
        path = data_dir / (name + (".csv" if fmt == "csv" else ".parquet"))
        t0 = time.perf_counter()
        if fmt == "csv":
            source.sink_csv(path, null_value=NULL_TOKEN, date_format="%Y-%m-%d")
        else:
            source.sink_parquet(path, compression=comp, compression_level=3 if comp=="zstd" else None, row_group_size=ROW_GROUP_SIZE)
        manifest['variants'][name] = {"path":str(path),"format":fmt,"compression":comp,"partitioning":"none",
                                      "build_seconds_including_input_read":time.perf_counter()-t0}
        say(f"  Created {name}")
    grouped = defaultdict(list)
    for p in files:grouped[p.name[7:11]].append(p)
    for name, part in [("parquet_zstd_by_year","year"),("parquet_zstd_by_quarter","year_quarter")]:
        path = data_dir / name;path.mkdir();t0=time.perf_counter()
        for year, inputs in sorted(grouped.items()):
            yd=path / f"year={year}";yd.mkdir()
            if part == "year":
                pl.scan_parquet([str(p) for p in inputs],hive_partitioning=False).sink_parquet(
                    yd/'part-000.parquet',compression='zstd',compression_level=3,row_group_size=ROW_GROUP_SIZE)
            else:
                for p in inputs:
                    quarter=(int(p.name[11:13])-1)//3+1
                    qd=yd/f"quarter={quarter}";qd.mkdir()
                    pl.scan_parquet(p,hive_partitioning=False).sink_parquet(qd/'part-000.parquet',compression='zstd',compression_level=3,row_group_size=ROW_GROUP_SIZE)
        manifest['variants'][name]={"path":str(path),"format":"parquet","compression":"zstd","partitioning":part,
                                    "build_seconds_including_input_read":time.perf_counter()-t0}
        say(f"  Created {name}")
    write_csv(reports/'source_checksums.csv',[{"path":str(p),"bytes":p.stat().st_size,"sha256":sha256(p)} for p in files])
    save_json(reports/'storage_manifest.json',manifest)
    write_csv(reports/'schema.csv',[{"column":c,"dtype":str(t)} for c,t in schema.items()])

    say("[2/4] Verifying the same data and saving query plans...")
    references={}
    for q in QUERIES:
        frame=apply_query(source,manifest,q).collect(engine='streaming')
        require(frame.height>0,f"No rows for {q}. Set --year and --quarter to a period present in this snapshot.")
        references[q]=json.loads(json.dumps(fingerprint(frame)))
        del frame
    save_json(reports/'reference_fingerprints.json',references)
    for v in manifest['variants']:
        for q in QUERIES:
            (reports/'plans'/f'{v}__{q}.txt').write_text(make_query(manifest,v,q).explain(optimized=True),encoding='utf-8')
    sizes=[]
    for v,info in manifest['variants'].items():
        p=Path(info['path']);parts=[p] if p.is_file() else list(p.rglob('*.parquet'))
        sizes.append({"variant":v,"format":info['format'],"compression":info['compression'],"partitioning":info['partitioning'],
                      "file_count":len(parts),"bytes":sum(p.stat().st_size for p in parts),
                      "build_seconds_including_input_read":info['build_seconds_including_input_read']})
    baseline_size=sizes[0]['bytes']
    for s in sizes:
        s.update(mib=s['bytes']/2**20,csv_to_variant_size_ratio=baseline_size/s['bytes'],storage_reduction_pct=100*(1-s['bytes']/baseline_size))
    write_csv(reports/'storage_sizes.csv',sizes)

    say("[3/4] Benchmarking reads. Fresh processes; OS cache is NOT cleared.")
    rng=random.Random(args.seed);measurements=[];jobs=[]
    pairs=[(v,q) for v in manifest['variants'] for q in QUERIES]
    for is_warmup, repetitions in [(True,args.warmups),(False,args.repeats)]:
        for repeat in range(1,repetitions+1):
            batch=list(pairs);rng.shuffle(batch)
            jobs.extend((is_warmup,repeat,v,q) for v,q in batch)
    for order,(warmup,repeat,v,q) in enumerate(jobs,1):
        result_path=reports/'runs'/f'{order:03d}.json'
        cmd=[sys.executable,str(Path(__file__).resolve()),'--worker-manifest',str(reports/'storage_manifest.json'),
             '--variant',v,'--query',q,'--worker-output',str(result_path),'--threads',str(args.threads)]
        result=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8')
        require(result.returncode==0,f"Worker failed ({v}/{q}): {result.stdout}\n{result.stderr}")
        record=read_json(result_path)
        require(record.pop('fingerprint')==references[q],f"Data equivalence failed for {v}/{q}; do not report speedups.")
        record.update(run_order=order,warmup=warmup,repeat=repeat,equivalence_pass=True)
        measurements.append(record)
        write_csv(reports/'measurements.csv',measurements)
        say(f"  {order}/{len(jobs)} {'warm-up' if warmup else 'timed'}: {v} / {q} = {record['seconds']:.3f}s")

    say("[4/4] Summarizing measurements and packaging the small review bundle...")
    summary_rows=[]
    for v,q in pairs:
        runs=[r for r in measurements if not r['warmup'] and r['variant']==v and r['query']==q]
        times=[r['seconds'] for r in runs]
        summary_rows.append({"variant":v,"query":q,"repeats":len(runs),"output_rows":references[q]['rows'],
            "median_seconds":statistics.median(times),"min_seconds":min(times),"max_seconds":max(times),
            "stdev_seconds":statistics.stdev(times) if len(times)>1 else 0.,
            "median_peak_rss_mib":statistics.median(r['peak_rss_mib'] for r in runs),
            "max_peak_rss_mib":max(r['peak_rss_mib'] for r in runs),
            "median_peak_rss_increase_mib":statistics.median(r['peak_rss_increase_mib'] for r in runs)})
    base={r['query']:r['median_seconds'] for r in summary_rows if r['variant']=='csv_uncompressed'}
    for r in summary_rows:r['speedup_vs_csv']=base[r['query']]/r['median_seconds']
    write_csv(reports/'benchmark_summary.csv',summary_rows)
    full_scope=(prior['start']=='1984-03-31' and prior['end']=='2026-06-30' and len(files)==170)
    status='STORAGE_BENCHMARK_COMPLETE' if full_scope and args.repeats>=3 and args.warmups>=1 else 'TEST_RUN_NOT_FULL_PROTOCOL'
    environment={"python":platform.python_version(),"polars":pl.__version__,"psutil":psutil.__version__,
                 "os":platform.platform(),"processor":platform.processor(),"physical_cpu_count":psutil.cpu_count(logical=False),
                 "logical_cpu_count":psutil.cpu_count(),"ram_gib":psutil.virtual_memory().total/2**30,
                 "threads":pl.thread_pool_size(),"python_executable":sys.executable}
    save_json(reports/'environment.json',environment)
    report={"status":status,"run_time_utc":datetime.now(timezone.utc).isoformat(),"source_audit":str(audit),"output_dir":str(root),
            "rows":n,"quarters":len(files),"first_quarter":prior['start'],"last_quarter":prior['end'],
            "full_assignment_scope":full_scope,"variants":len(sizes),"queries":QUERIES,"filter_year":args.year,"filter_quarter":args.quarter,
            "warmups_per_pair":args.warmups,"timed_repeats_per_pair":args.repeats,"seed":args.seed,
            "all_equivalence_checks_passed":True,"row_group_size":ROW_GROUP_SIZE,"zstd_level":3,
            "source_financial_bytes":source_bytes,"script_sha256":sha256(__file__),"environment":environment,
            "scope_note":"Financials storage experiment only; small tables remain separate prepared Parquet inputs.",
            "cache_note":"No OS-cache flush. Warm-up and repeated access; cache residency is not guaranteed. Not cold disk I/O.",
            "timing_note":"Includes query construction and collection; excludes interpreter/imports, writes, validation hashes and plan generation.",
            "memory_note":"Native RSS sampled every 10ms plus endpoints; observed peak can miss short spikes. Baseline and incremental RSS reported.",
            "baseline_note":"Uncompressed CSV reconstructed from the same typed snapshot. Explicit schema supplied; not FDIC original CSV bytes.",
            "partition_note":"Year/quarter folder keys support explicit partition filters equivalent to REPDTE filters. All layouts project identical source columns.",
            "equivalence_note":"Row counts, schema, null counts and two order-independent row-hash sums checked; hashes are diagnostics, not a proof.",
            "limitations":["No pandas comparison or Spark parity in this Part 1 experiment.",
                           "Build times are single observed conversions including source reads, not repeated write benchmarks.",
                           "Sequential partitions can have different row-group boundaries; this is an end-to-end layout comparison, not isolated metadata-only effect.",
                           "Hardware and cache affect measurements. Record disk type manually for the final report.",
                           "Choose final layout from measured workload tradeoffs; no assumption that every Parquet variant beats CSV in every query."]}
    save_json(reports/'storage_summary.json',report)
    instructions='''PART 1 STORAGE EXPERIMENT

1. Use storage_sizes.csv for bytes, file count, compression ratio and reduction.
2. Use benchmark_summary.csv for median/min/max/std time, observed peak RSS and
   speedup_vs_csv (>1 means faster, <1 means slower). Warm-ups are excluded.
3. Use measurements.csv, environment.json and plans/ to document reproducibility.
4. Choose the final format/compression/layout AFTER inspecting tradeoffs. Explain
   schemas (keys, dates, floats, nulls), year/quarter pruning and small-file overhead.
5. Source CSV was reconstructed from the SAME prepared snapshot, NOT directly from HTTP.
   Missing fields are empty and a typed schema is enforced; the source guard rejects
   any genuine non-null empty text fields that could otherwise be confused with nulls.
6. Do not report these as cold-cache results. OS cache was not flushed; hardware
   and other applications can affect timings. Do not compare this directly with
   the 4.525-second step2 run: that was a different workload, not a benchmark.
7. Archive storage_review_bundle.zip. It excludes all benchmark data copies. No source
   data were modified. Do not commit benchmark_data or financial data to GitHub.
8. Part 1 still requires narrative: reproducible download method, resume behavior,
   completeness checks, and a justified storage design. Benchmark alone is not the
   whole Part 1. Small tables stay separate; this benchmark covers large Financials.

Dependencies: Polars, psutil. Use the already working project Python environment.
Rerun command: python 01b_benchmark_storage.py --audit-dir PATH --out NEW_PATH
Use --repeats 7 and --warmups 2 or more for the sensitivity run. Fresh subprocess per run;
imports are excluded from query timing. Fixed threads and randomized order.

Sources: instructor PDF; https://api.fdic.gov/banks/docs/;
https://docs.pola.rs/api/python/stable/reference/lazyframe/ .
AI assistance: ChatGPT, 2026-11-08. Cite in report and README.
'''
    (reports/'READ_ME.txt').write_text(instructions,encoding='utf-8')
    bundle=root/'storage_review_bundle.zip'
    with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(reports.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(root))
    save_json(root/'STORAGE_COMPLETE.json',{"status":status,"all_equivalence_checks_passed":True})
    say(f"DONE - {status}")
    say(f"Rows: {n:,}; quarters: {len(files)}; equivalence: PASS")
    say(f"Benchmark evidence archive: {bundle}")


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--audit-dir',type=Path,default=DEFAULT_AUDIT)
    ap.add_argument('--out',type=Path)
    ap.add_argument('--year',type=int,default=2023)
    ap.add_argument('--quarter',type=int,default=1,choices=[1,2,3,4])
    ap.add_argument('--repeats',type=int,default=7)
    ap.add_argument('--warmups',type=int,default=2)
    ap.add_argument('--threads',type=int,default=min(4,os.cpu_count() or 1))
    ap.add_argument('--seed',type=int,default=20261108)
    ap.add_argument('--worker-manifest',type=Path,help=argparse.SUPPRESS)
    ap.add_argument('--worker-output',type=Path,help=argparse.SUPPRESS)
    ap.add_argument('--variant',help=argparse.SUPPRESS)
    ap.add_argument('--query',help=argparse.SUPPRESS)
    args=ap.parse_args()
    if args.repeats<1 or args.warmups<0 or args.threads<1:ap.error('Invalid repeats/warmups/threads.')
    os.environ['POLARS_MAX_THREADS']=str(args.threads)
    global pl,psutil
    try:
        import polars as pl
        import psutil
        if args.worker_manifest:
            worker(args)
        else:
            say('BFT65B - Part 1 storage benchmark starts.')
            say(f'Input audit: {args.audit_dir}; fixed threads: {args.threads}')
            experiment(args)
    except Exception as exc:
        say(f'STOPPED: {type(exc).__name__}: {exc}')
        say('Benchmark failed. Consult stderr and do not use partial results.')
        return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
