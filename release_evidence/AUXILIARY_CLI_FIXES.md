# Auxiliary CLI release-copy fixes —18November2026

Archived originals are unchanged. Exact diffs and before/after SHA256 are recorded in AUXILIARY_CLI_FIXES.diff/.json. Actual tests were limited to AST parsing and both new --help commands; no CSV/chart, data, metrics, models or scientific stage was executed. Captured help stdout/stderr, commands, Python environment and hashes are in the JSON evidence.

## Recorded Part1 plotting helper

`01_PART1_ACQUISITION_STORAGE/code/plot_part1_latency.py` no longer reads data or imports matplotlib at module import. Requires explicit `--summary benchmark_summary.csv --out NEW_EXTERNAL_DIRECTORY`. Rejects an existing output directory, repository overlap and source CSV-directory overlap. Matplotlib is lazy; MPLCONFIGDIR is confined to the new output. Original variants, labels, colors, queries, median/min/max arithmetic, bars/whiskers/axis limits/legend and PNG settings are unchanged. Whiskers remain observed min/max, not CIs. No benchmark is run.

## Registered Spark reference preflight helper

`05_PART5_MODELLING_VALIDATION/code/registered_lr_parity/run_registered_spark_recheck.py` keeps its preflight-only behavior: no classifier fits, model loads, subprocess dispatch or final-test inference. `--reference-dir` is now required, eliminating an omitted private evidence default. Missing provided files produce `BLOCKED_INPUTS`/exit3. Optional `--out NEW_EXTERNAL.json` may be outside the repository rather than obsolete repair_results; reject source/reference overlap and overwrite, then write with exclusive creation. No references or metrics were recomputed during these tests.
