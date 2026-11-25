# BFT65B Part 3 — supplemental archival evidence (24 November 2026)

**Scope:** baseline `BFT65B_REPORT_SUBMISSION_CANDIDATE_20261124`, pp. 6–10, 22, 26. This is an evidence supplement, not a replacement report or a claim that proposed edits are already submitted. The original Windows benchmark outputs were recovered from `BFT65B_FINAL_Parts1-5_Curated.zip`, `part3_step05_fair_benchmark_evidence.zip`, `part3_step01_polars_evidence.zip`, `part3_step04_spark_evidence.zip`, and the 13 November `SHARE_THIS_06/07/09_EVIDENCE.zip` returns. The latter three archive digests match their embedded copies and the 13 November independent review index. The Step05 member bytes match the curated archive. The original aggregate/plan checksums match their producer audits. The companion ZIP supplies selected CSV/JSON/plan evidence plus member provenance (local user path prefixes redacted where necessary).

No engine was rerun on the private FDIC snapshot here; this review recalculates archived observations. No model, threshold, or held-out scores were touched. No 10× test was run. The recorded nine same-engine replay comparisons are checked against their saved summary, not reconstructed from new engine output.

## 1. Evidence previously marked unverified

### Fair blocked trial (Step05, 11 November)

Producer `05_fair_baseline_sensitivity.py`; `trial_times.csv`, `timing_summary.csv`, `memory_summary.csv`, `step05_audit.json` in original fair evidence archive. Recalculated all nine medians from 135 timed observations, excluding 27 warmups. All match. Windows 11, Python 3.13.9, Polars 2.1.0, pandas 3.1.1, PyArrow 26.0.1, psutil 7.2.2; four configured threads. Read/transform/materialize included; imports, comparison and output writing excluded. Separate memory workers sampled process RSS at 10 ms; the recorded peak spans the warmups and one further execution (not necessarily the same observation as the latency median).

| Workload | Polars median s | Original pandas median s | Optimized pandas median s |
|---|---:|---:|---:|
| Crisis | 0.1240214 | 0.5208387 | 0.1081538 |
| Calendar lag | 0.1933102 | 0.9714457 | 0.5441795 |
| Decision | 0.0568776 | 0.6264005 | 0.4882450 |

Calendar lag memory: optimized pandas peak 351.359 MiB, baseline 86.816 MiB, incremental 264.543 MiB; Polars peak 433.387 MiB, baseline 48.586 MiB, incremental 384.801 MiB. Thus the report's 351.4/433.4 attribution is **correct**. The 351.438 MiB in the earlier original-pandas run is a different measurement.

### Layout ablation (Step06)

`layout_audit.json`, `layout_rowgroups.csv`, `layout_trials.csv` from `SHARE_THIS_06_EVIDENCE.zip`. Both layouts contain 1,669,802 reports and 17 groups: sixteen groups of 100,000 rows and the last of 69,802. Both use ZSTD; the date-sorted rewrite matches the recorded content fingerprint, including schema, null counts and two hash sums. Recalculated from the 12 paired rounds after three warmup rounds: original median 0.04264035000051081 s, date-sorted median 0.015134649999708927 s, ratio of medians 2.817399, median paired ratio 2.786335, 12/12 wins. All 17 original groups overlap the 2008–2014 predicate; 14/17 date-sorted groups are eligible to skip (3 overlap). Recorded mean-ASSET difference is zero. This is the reduced count/mean-ASSET query, not the full crisis profile. Footer eligibility is not measured I/O. Same row-group counts and sizes are now verified; re-encoding and cache state can still matter, so avoid a causal claim about ordering alone.

### Polars reference

`optimized_plan_crisis_profile.txt` from `part3_step01_polars_evidence.zip`: `PROJECT 7/33 COLUMNS`, `SELECTION: col("REPDTE").is_between([2008-03-31, 2014-12-31])`, guarded ratios and `AGGREGATE[maintain_order: false]` followed by sort. The plan hash matches `polars_audit.json`. The archived lag and decision plans also match their producer hashes. This supports scan-level projection, predicate pushdown and common-subplan caching, not an observed physical hash-table implementation or measured thread utilization. The Polars reference reported six synthetic edge checks.

### Spark — two distinct comparisons, both valid

Independently compared the original Spark and Polars aggregate CSVs by quarter key, integer counts, null pattern and float tolerance (rtol 1e-10, atol 1e-6). All 363 rows match; original CSV digests match producer audit. The 1,089-row later replay is the recorded 9 engine/task comparison summary (`outputs/verification/PRIOR_NUMERICAL_COMPARISON.csv`): 363 rows × three engines. These are **different** comparisons, so differing deltas are not a discrepancy. Table 3 is accurately labelled replay-versus-archive but should include the direct cross-engine comparison.

| Task | Rows | Spark vs Polars max absolute | Spark vs Polars max relative | Spark replay vs own archive max absolute | Median collect() s |
|---|---:|---:|---:|---:|---:|
| Crisis | 28 | 1.3322676295501878e-15 | 1.1869644028310012e-14 | 2.4424906541753444e-15 | 1.5271522000002733 |
| Lag | 170 | 2.220446049250313e-16 | 1.7403474473639324e-15 | 5.551115123125783e-16 | 3.864114800000607 |
| Decision | 165 | 2.4424906541753444e-15 | 3.4659006298706935e-15 | 4.440892098500626e-15 | 1.3161496000002444 |

The Step04 parity audit also records 1,452 invalid loan denominators, 1,645,928 exact predecessor matches, 954,592 missing P3ASSET cases, and three successful synthetic temporal checks. The clean-stage `step2c_summary.json` and `internal_gaps_after.csv` independently corroborate 23,849 clean CERTs, 25 CERTs with internal gaps, 39 missing quarters. The lag count reconciliation gives 23,874 unmatched predecessors = 23,849 first reports + 25 post-gap returns. These independent identities and synthetic cases complement, rather than replace, a full row-level independent oracle for the financial values.

### Spark action configuration (Step09)

**Recovered from original `spark09/spark_action_audit.json`:** Spark 4.3.0, Java 17.0.21, local[4], default parallelism 4, requested driver memory `3g`, reported effective driver memory `3g`, `spark.sql.shuffle.partitions=8`, AQE=true. The 21 timed actions (seven per task) and six warmups match the original audit medians exactly, with final AQE plans observed. This resolves the earlier configuration uncertainty in the current report. It establishes the recorded Spark configuration, not a measurement of actual JVM maximum heap or network transfer. `collect()` stopwatch excludes query construction/plan initialization/startup; do not compare with end-to-end local worker times as a speed ratio.

### Full physical-plan operator chain

The final and initial Spark plans are printed together; count only the final plan, not both. The recovered Step04 final plan contains four Exchanges for lag, two each for crisis and decision. Lag: two hash repartitions on the join keys → two sorts → left SortMergeJoin → partial HashAggregate → quarter-key hash Exchange → final HashAggregate → range Exchange and final sort. Crisis/decision: scan/filter → partial HashAggregate → hash Exchange → final HashAggregate → range Exchange and sort. AQE coalesces shuffle reads. Both join-side `ShuffleQueryStage` annotations report 63.7 MiB (approximately 1.67 million rows); this is a plan-reported stage statistic, not measured network bytes. The current Exhibit 3A lists only the join-side exchanges; add downstream aggregation and ordering.

## 2. New analysis from archived Step07 trials (not yet credited in report)

The 108 measured observations (12 rounds × nine combinations) exclude 27 warmup observations. All paired medians and percentile bootstrap endpoints independently reproduce with the producer's seed 20261112 and 2,500 within-round resamples. The optimized pandas/Polars results are:

| Workload | Wins | Median paired ratio | Observed range | Bootstrap 95% interval | Ratio of medians |
|---|---:|---:|---:|---:|---:|
| Crisis | 12/12 | 2.690860 | 1.100–6.333 | 1.758–3.569 | 2.131 |
| Lag | 12/12 | 4.408536 | 2.351–10.392 | 3.140–7.643 | 4.320 |
| Decision | 12/12 | 5.021778 | 1.165–17.445 | 3.473–7.327 | 5.706 |

| Workload | Polars last-five / first-five median | Optimized pandas last-five / first-five median | Spearman correlation: paired ratio vs round |
|---|---:|---:|---:|
| Crisis | 0.2875 | 0.3237 | 0.189 |
| Lag | 0.4547 | 0.4302 | 0.133 |
| Decision | 0.9261 | 0.3328 | -0.552 |

Measured rounds 3–7 vs 10–14: five of six engine/workload median times fell by approximately 55–71%; Polars decision fell 7.4%. These are descriptive trends, not causal cache evidence or formal trend tests. Sample CVs for these six series range 0.591–1.092. The decision speed-ratio range is wide. The paired bootstrap assumes exchangeable rounds; systematic drift/dependence may change its coverage. It is not justified to claim exactly how much it overstates precision. Report it as conditional/descriptive rather than evidence of a population-level engine advantage.

The blocked worker reuses the same process across three warmups and 15 trials. The interleaved worker imports libraries before its stopwatch but performs only one query per fresh subprocess. OS cache is not cleared. Therefore run-order, process state and elapsed system conditions are confounded. The blocked reversal is real: optimized pandas is faster for crisis but slower for the two other workloads. The paired protocol shows Polars winning all 12 rounds for every workload. So rankings depend on workload **within the blocked protocol** and change with the protocol; no causal claim about order alone.

Optimized pandas' decision path omits the explicit date filter; it is redundant for the hash-pinned PIT input whose maximum decision date is 2025-06-30, verified outside the Step05 clock. Polars retains it; parity still holds. This favors the optimized pandas path on that frozen snapshot and should be disclosed, not described as an output error. Both the input contract and the external uniqueness validation are essential to this optimization; do not generalize it to unrestricted input.

## 3. Scaling and cluster argument

The Step08 reduced pandas implementation concatenates projected Parquet inputs, converts dates to period IDs and performs `validate='1:1'` in the timed lag merge; the reduced Polars join also requests `validate='1:1'`. This is not the optimized Step05 comparator and the reduced workload is not the full lag-growth query. Name the comparator in Figure 5/main text. The 1×/3×/5× medians and observed ranges remain unchanged.

At 5× (8,349,010 rows), Polars lag median 8.5673 s, original-style reduced pandas median 27.8338 s; ratio 3.2489×. Median sampled peak RSS 2,689.71 vs 1,785.09 MiB (+50.7%). Across three Polars 5× trials, maximum sampled peak RSS was 2,728.84 MiB and maximum runtime 10.414 s. This leaves 3,415.16 MiB to the experiment's 6,144 MiB guard, based on the largest **observed sampled** peak, not a guaranteed production headroom. Relative to 1×, Polars lag median runtime increased 7.02× and RSS 4.64× for five times the rows. This demonstrates why capacity decisions must consider latency and memory separately. Neither method dominates both.

The rubric asks for measurement-based scaling reasoning, not a prescribed 10× trial, physical cluster or a numerical crossover. The report already identifies 70% RAM and p95 service targets as proposed criteria, not measured outputs. Three runs cannot estimate p95 reliably; use observed ranges and require a representative full-job trial before migration. The claim that a linear fit predicts 3.2 GiB at 10× is inconsistent with the three reported Polars lag RSS medians. A least-squares fit of RSS (MiB) on replication factor gives 44.165 + 527.425 × factor, hence 5,318.415 MiB (~5.19 GiB) at 10×. **This is unmeasured, not a forecast or safety guarantee; do not include it as evidence of actual capacity.** A 10× run is optional, not necessary to satisfy the rubric, and should be resource-capped if attempted. More reduced-workload runs alone cannot prove a remote-cluster crossover.

## 4. Reassessment requested (no credit for proposed edits)

- Heading/protocol and dispersion: legitimate presentation improvements; blocked workload-dependent ranking itself is correct.
- Fair benchmark RSS: now verified against the correct archive, not a mislabel.
- Cross-engine Table 3: direct comparison now independently reproduced from original aggregate CSVs; current table's explicitly labelled replay values are not wrong, but direct parity should be shown.
- Layout/Step09: original trials and audit now recovered; timing and effective Spark configuration verified. Remaining caveats on cold-cache, single-machine sampling and network cost stand.
- Physical plan: complete chain includes final sorting exchanges; correct the condensed exhibit.
- Polars crisis projection: verified from original Polars plan and checksum, not inferred from Spark.
- Scaling: qualify comparator in main text; use measured headroom, not unvalidated extrapolation. No official 10×/cluster-run requirement.
- Full independently generated row-level financial oracle remains absent; distinguish separate engine implementations, independent aggregate identity checks and synthetic tests from independent source-data truth.

Official technical context: Polars lazy optimizations (https://docs.pola.rs/user-guide/lazy/optimizations/); Spark SQL performance tuning (https://spark.apache.org/docs/latest/sql-performance-tuning.html). Use these for semantics, not for project-specific measurements.
