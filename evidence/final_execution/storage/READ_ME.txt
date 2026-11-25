PART 1 STORAGE EXPERIMENT

1. Use storage_sizes.csv for bytes, file count, compression ratio and reduction.
2. Use benchmark_summary.csv for median/min/max/std time, observed peak RSS and
   speedup_vs_csv (>1 means faster, <1 means slower). Warm-ups are excluded.
3. Use measurements.csv, environment.json and plans/ to document reproducibility.
4. Compare the four variants without changing the locked modelling inputs. Explain
   schemas (keys, dates, floats, nulls), year/quarter pruning and small-file overhead.
5. Source CSV was reconstructed from the SAME prepared snapshot, NOT directly from HTTP.
   CSV variants use explicit empty or sentinel encodings; gzip decompresses the same empty CSV within timing. A typed schema is enforced; literal empty text is reversibly encoded in empty-null variants and decoded inside
   query timing. A collision check and synthetic/full-data round-trip checks are required.
6. Do not report these as cold-cache results. OS cache was not flushed; hardware
   and other applications can affect timings. Do not compare this directly with
   the 4.525-second step2 run: that was a different workload, not a benchmark.
7. Archive storage_review_bundle.zip. It excludes all benchmark data copies. No source
   data were modified. Do not commit benchmark_data or financial data to GitHub.
8. Part 1 still requires narrative: reproducible download method, resume behavior,
   completeness checks, and a justified storage design. Benchmark alone is not the
   whole Part 1. Small tables stay separate; this benchmark covers large Financials.

Dependencies: Polars, psutil. Use the already working project Python environment.
Rerun command: python tools/storage_sensitivity.py --audit-dir PATH --out NEW_PATH
Use --repeats 7 and --warmups 2 or more for the sensitivity run. Fresh subprocess per run;
imports are excluded from query timing. Fixed threads and randomized order.

Sources: instructor PDF; https://api.fdic.gov/banks/docs/;
https://docs.pola.rs/api/python/stable/reference/lazyframe/ .
AI assistance: ChatGPT, 2026-11-08. Cite in report and README.
