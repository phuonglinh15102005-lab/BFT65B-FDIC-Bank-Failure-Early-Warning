# Part 1 — supplemental archival evidence (not a revised report)

Use alongside the original 24 Nov report extract and core code. The following is an evidence supplement, not an instruction to award a particular score. Data were NOT re-downloaded and storage queries were NOT re-timed in this review. The original report does not yet incorporate the proposed wording. No personal paths or raw data are included.

## 1. Provenance and checks actually executed

Historical source: `BFT65B_FINAL_Parts1-5_Curated.zip`, prefix `BFT65B_FINAL/01_PART1_ACQUISITION_STORAGE/`. Source archive SHA-256: 81276c603b3139e5d952e03a2c2806208cd3972d313876995ac6eb4553cf649c.

Extracted the Part 1 evidence into a temporary directory. Ran its archived `verify_part1_evidence.py` after restoring the historical expected `scripts/01b_benchmark_storage.py` location with the identical file from `code/`. This is a saved-evidence verification, not an independent run over raw Parquet. The current release verifier already references `code/`.

```json
{
  "status": "SAVED_EVIDENCE_VERIFIED",
  "prepared_quarter_checksum_pairs": 170,
  "prepared_quarter_checksum_matches": 170,
  "run_fingerprints_matching_reference": 80,
  "warmups": 20,
  "timed_runs": 60,
  "recomputed_aggregate_groups": 20,
  "reported_storage_sizes_arithmetically_consistent": true,
  "benchmark_script_matches_recorded_sha256": true,
  "rows": 1682616,
  "quarters": 170,
  "zstd_reduction_vs_csv_pct": 66.60523222599693,
  "zstd_reduction_vs_snappy_pct": 27.358038334902535,
  "zstd_full_scan_speedup_vs_csv": 2.2061482184400165,
  "csv_null_marker_sensitivity_not_a_new_measurement": {
    "null_cells": 1330072,
    "marker_bytes_per_null": 24,
    "marker_bytes": 31921728,
    "marker_mib": 30.44293212890625,
    "counterfactual_csv_bytes": 446404973,
    "counterfactual_csv_mib": 425.7249574661255,
    "counterfactual_zstd_reduction_pct": 64.21722412129131,
    "assumption": "Remove only 24 marker bytes for each null, holding delimiters, quoting and all other bytes fixed. Not an observed alternative CSV file or timing."
  },
  "limitations": [
    "Checksums compared here identify prepared inputs, not original FDIC HTTP payloads.",
    "This verification recomputes saved-log consistency; it does not reread all Financials files or rerun queries.",
    "Input checksum equality is demonstrated across panel-review and benchmark logs, not against a new live API download.",
    "Raw-file completeness relies on the acquisition audit and its recorded API totals.",
    "Three timed observations do not establish statistical superiority."
  ]
}
```

Original archived benchmark code SHA-256: `fab4ab46d7fd4e7e65d576644880453456cd366eafba5d92e18b26d1cedca842` (matches the recorded producer hash). Original acquisition code in the curated archive is byte-identical to the supplied course starter, SHA-256 `cb5171ffcb4a5195e65c796b393e7f7c50b8e4a492ef907a9085d5a5b631eb51`; this archived code has pagination/retry, per-quarter manifest row counts and duplicate-key checks. Current release is hardened. Original raw acquisition manifest and HTTP payloads were NOT recovered in this inspection.

## 2. Acquisition chronology (D5, D6)

`source_evidence/acquisition_audit_summary.json` recorded `2026-11-08T03:22:09.392804+00:00` (audit completion time, NOT individual download time). This audit read all 170 quarters, 1,682,616 rows, 24,064 distinct valid CERT, zero duplicate valid financial keys, zero errors, 18 review items. Both small tables already existed by that timestamp; Failures/Assistance = 4,117 (3,524 FAILURE + 593 ASSISTANCE); Institutions = 27,835. Counts agree with the user download-log totals recorded in the original audit. Exact endpoint HTTP completion timestamps not recoverable from these files. The supplementary History/status/dictionary retrieval on 9 Nov is separate from the three-table snapshot.

## 3. Schema and benchmark environment (D1, D7, D8)

Archived `schema.csv`: Float64 × 30, Date × 1, String × 1, Int64 × 1. CERT (Int64) and REPDTE (Date) form the composite key; STNAME (String) is descriptive metadata, not a third key. The 30 numeric columns use Float64 for a uniform schema across quarters whose raw inferred types include Int64, Float64, Null. `typed_financials` performs strict casts and `fill_nan(None)`. Preserve units and legitimate negatives; no imputation at storage stage. Source monetary amounts in USD thousands, reported ratios in percent. The broad course-starter field set covers capitalization, funding/liquidity, credit quality, reserves and earnings; it supports DQ and downstream feature construction, not all fields enter the model.

Exact measured environment from the original `benchmark_reports/environment.json` (personal executable path omitted):

```json
{
  "python": "3.13.9",
  "polars": "2.1.0",
  "psutil": "7.2.2",
  "os": "Windows-11-10.0.26300-SP0",
  "processor": "Intel64 Family 6 Model 154 Stepping 4, GenuineIntel",
  "physical_cpu_count": 10,
  "logical_cpu_count": 12,
  "ram_gib": 15.568843841552734,
  "threads": 4
}
```

Disk type and PyArrow version are not recorded in this benchmark environment JSON; the storage benchmark itself uses Polars and psutil. ZSTD level 3 and 100,000-row groups were fixed; this experiment compares layouts, not codec-level or row-group hyperparameter sweeps.

## 4. Original latency ranges and chosen layout (D2, D3, D4)

All values in seconds; original sentinel CSV only; 3 measured repeats per cell. The 80 measurement records (20 warmups + 60 timed) were reconciled against the archived summary by the verifier.

| Workload | Variant | Median | Min | Max | CSV median / variant median |
|---|---|---:|---:|---:|---:|
| all_rows_all_columns | csv_uncompressed | 0.97123 | 0.96277 | 1.35027 | 1.000 |
| all_rows_six_columns | csv_uncompressed | 0.54847 | 0.46329 | 0.72909 | 1.000 |
| one_year_six_columns | csv_uncompressed | 0.59713 | 0.52063 | 0.61778 | 1.000 |
| one_quarter_six_columns | csv_uncompressed | 0.47538 | 0.44667 | 0.66858 | 1.000 |
| all_rows_all_columns | parquet_snappy | 0.30359 | 0.28701 | 0.31759 | 3.199 |
| all_rows_six_columns | parquet_snappy | 0.13036 | 0.08017 | 0.15408 | 4.207 |
| one_year_six_columns | parquet_snappy | 0.01507 | 0.01469 | 0.01975 | 39.632 |
| one_quarter_six_columns | parquet_snappy | 0.01720 | 0.01425 | 0.03421 | 27.645 |
| all_rows_all_columns | parquet_zstd | 0.44024 | 0.34998 | 0.44386 | 2.206 |
| all_rows_six_columns | parquet_zstd | 0.11909 | 0.09597 | 0.36213 | 4.605 |
| one_year_six_columns | parquet_zstd | 0.03941 | 0.01404 | 0.04389 | 15.153 |
| one_quarter_six_columns | parquet_zstd | 0.01893 | 0.01563 | 0.03501 | 25.111 |
| all_rows_all_columns | parquet_zstd_by_year | 0.40627 | 0.39442 | 0.44580 | 2.391 |
| all_rows_six_columns | parquet_zstd_by_year | 0.09337 | 0.07428 | 0.10775 | 5.874 |
| one_year_six_columns | parquet_zstd_by_year | 0.02326 | 0.02213 | 0.05082 | 25.671 |
| one_quarter_six_columns | parquet_zstd_by_year | 0.02410 | 0.02133 | 0.07097 | 19.722 |
| all_rows_all_columns | parquet_zstd_by_quarter | 0.48118 | 0.45823 | 0.56152 | 2.018 |
| all_rows_six_columns | parquet_zstd_by_quarter | 0.12641 | 0.12177 | 0.14207 | 4.339 |
| one_year_six_columns | parquet_zstd_by_quarter | 0.04453 | 0.04247 | 0.07190 | 13.409 |
| one_quarter_six_columns | parquet_zstd_by_quarter | 0.04991 | 0.04966 | 0.07064 | 9.525 |

Year-ZSTD median is lower than single-file ZSTD in three of four workloads, at 153.10 vs 152.34 MiB (43 files vs 1). The recorded ranges overlap for these two variants in each workload; three repeats do not establish statistical superiority or equivalence. Single-file ZSTD is a design choice for compactness and one-file management, not a latency optimum. The quarterly prepared layer serves repair/recovery. Single-file ZSTD one-year speedup is 15.15×; Snappy is 39.6×. All Parquet observed ranges lie below the corresponding CSV observed minimum for the original benchmark; do not generalize beyond the tested environment/encoding.

Original CSV 478,326,701 B; ZSTD 159,736,091 B; 1,330,072 null cells. 24→1 byte sensitivity: remove 30,591,656 B, leaving 447,735,045 B (426.99 MiB), saving 64.32%. 24→0 byte sensitivity: remove 31,921,728 B, leaving 446,404,973 B (425.72 MiB), saving 64.22%. Both are byte arithmetic with all other bytes fixed, NOT observed runtimes or guaranteed equivalent serialization. Empty-string/null round-trip must be checked. Existing `01b_storage_empty_null.py` has not been run on the real snapshot in this review.

## 5. Replay scope (D9)

The 19 Nov `prepare/COMPARISON_SPEC.json` lists exactly 172 Parquet comparisons: 170 quarterly Financials, `institutions.parquet`, `failures_all.parquet`. The corresponding `config/prepared_snapshot_manifest.json` has 174 entries: these 172 Parquets plus `summary.json` and `STANDARDIZATION_COMPLETE.json`. The audit producer also writes `failure_events.parquet` and `assistance_events.parquet`; these two derivative tables are not part of the claimed 172-file comparison. The larger continuous replay compares 179 datasets in total, 178 byte-identical; the non-byte-identical development dataset matched logical values. Thus 172 and 179 are different scopes. Use “offline replay from the retained snapshot, with returned comparison evidence reviewed separately” rather than implying an independent live acquisition.

## 6. Candidate report changes (not yet integrated)

- Cover: “Financials, Institutions and Failures/Assistance were present in the acquisition audit completed on 8 November 2026 at 03:22 UTC. Supplementary History/status/field-dictionary retrieval occurred on 9 November. Exact endpoint completion times were not retained in the supplied records.”
- §1.1: “The adapted course starter retained CERT (Int64) and REPDTE (Date) as the key, STNAME (String) as metadata and 30 Float64 accounting fields covering capital, funding/liquidity, asset quality and earnings. A common numeric type reconciles quarter-to-quarter inferred schemas; NaN becomes null, not zero. Monetary amounts remain in USD thousands and reported ratios in percent.”
- §1.2/F: “The CSV reference was reconstructed from the same typed snapshot with a collision-checked null marker; observed speedups apply to this encoding. Year-partitioned ZSTD had lower medians in three workloads, but ranges overlapped single-file ZSTD and n=3 cannot establish a winner. We chose the 152.34 MiB single file for compactness and simpler whole-panel handling; 43 yearly or 170 quarterly files remain valid alternatives for selective reads or targeted recovery. The chosen ZSTD was 15.2× faster on the one-year scan versus 39.6× for Snappy.”
- F: give recorded environment, fixed settings and the observed-minimum-versus-maximum comparison; replace “leads” with “lowest observed median.”

## 7. Request for independent re-review

Reassess D1–D9 against this archival evidence. Distinguish report omissions from missing evidence in the previous review pack. The official rubric does not prescribe a separate bulk endpoint reconciliation, n=7, or codec/row-group sweep. Do not treat the proposed wording as already incorporated or award credit for an unexecuted empty-null benchmark. Retain justified deductions and cite the remaining issue precisely.
