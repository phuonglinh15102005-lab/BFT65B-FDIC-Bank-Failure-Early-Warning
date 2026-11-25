# BFT65B — Evidence path map for the revised academic report

Root A: `BFT65B_FINAL_Parts1-5_Curated.zip` → `BFT65B_FINAL/`.
Root B: `BFT65B_CONTINUOUS_VERIFIED_RELEASE_20261119.zip` → `BFT65B_CONTINUOUS_VERIFIED_RELEASE_20261119/`.

| Report ref | Exact grounded evidence paths in archive A, unless B stated | Reproduced claim |
|---|---|---|
| E1 | `01_PART1_ACQUISITION_STORAGE/evidence_additional/storage_benchmark_original.csv`; `01_PART1_ACQUISITION_STORAGE/evidence_additional/rowgroup_metadata_original.csv` | 20 materialization queries, size/read trade-offs, rowgroup metadata |
| E2 | `02_PART2_DATA_QUALITY_PANEL/evidence/missingness_comparison.csv`; `02_PART2_DATA_QUALITY_PANEL/evidence/ratio_extremes.csv`; `02_PART2_DATA_QUALITY_PANEL/evidence/preflight_evidence/ratio_diagnostics_by_quarter.csv` | Missingness, extreme reported ratios, quarterly reporting discontinuity |
| E3 | `03_PART3_SCALABLE_PROCESSING/evidence_original/part3_step03_benchmark_evidence/benchmark_trials.csv`; `03_PART3_SCALABLE_PROCESSING/evidence_step08/source_evidence/scale_summary.csv`; `03_PART3_SCALABLE_PROCESSING/evidence_step08/source_evidence/scale_trials.csv` | Repeated performance, 1×/3×/5× stress and memory results |
| E4 | `04_PART4_FEATURE_PIPELINE/evidence/fold_audit/v2_temporal_folds.csv`; `04_PART4_FEATURE_PIPELINE/evidence/fold_audit/v2_preprocessing_params.csv`; `04_PART4_FEATURE_PIPELINE/evidence/development_only/asof_future_poison_audit.csv` | Train-only controls, 4Q horizon, PIT canaries |
| E5 | `05_PART5_MODELLING_VALIDATION/evidence/01_baseline/baseline_fold_metrics.csv`; `05_PART5_MODELLING_VALIDATION/evidence/02A_logistic/logistic_candidate_summary.csv`; `05_PART5_MODELLING_VALIDATION/evidence/02B_hgb/hgb_candidate_summary.csv` | Frozen selection among registered families/configurations |
| E6 | `05_PART5_MODELLING_VALIDATION/evidence/03_threshold/development_threshold_scenarios.csv`; `05_PART5_MODELLING_VALIDATION/evidence/03_threshold/chronological_calibration_diagnostics.csv`; `05_PART5_MODELLING_VALIDATION/evidence/extended_source_audits/C_dev_permutation/permutation_importance_summary.csv` | Dev-only threshold, forward Platt diagnostic, posthoc permutation; ablation run is separately archived in 18 Nov closeout |
| E7 | `05_PART5_MODELLING_VALIDATION/evidence/06_test_locked/final_test_scored_rows.csv.gz`; `05_PART5_MODELLING_VALIDATION/evidence/final_crosscheck/calibration_bins.csv`; `05_PART5_MODELLING_VALIDATION/evidence/06_test_locked/final_test_year_metrics.csv`; `05_PART5_MODELLING_VALIDATION/evidence/extended_source_audits/A_source_cost/test_15_missed_events_with_FDIC_size_COST.csv`; `05_PART5_MODELLING_VALIDATION/evidence/oracle_cost_weighted/test_cost_weighted/locked_test_event_COST_join.csv` | Final AP/AUC, 11-bin calibration, annual variation, missed COST severity |
| E8 | `05_PART5_MODELLING_VALIDATION/evidence/04_spark_demo/spark_mllib_fold_metrics.csv`; `05_PART5_MODELLING_VALIDATION/evidence/spark_registered_parity/`; `BFT65B_CONTINUOUS_VERIFIED_RELEASE_20261119/completed_analyses/test_ci/` (B) | Spark logistic parity and posthoc uncertainty |
| E9 | `release_evidence/continuous_windows_20261119/STAGE_STATUS.csv` (B); `release_evidence/continuous_windows_20261119/DATASET_COMPARISON.csv` (B); `release_evidence/continuous_independent_review_20261119/PARENT_CONTINUITY.csv` (B) | Continuous snapshot/cache→development replay and documented limits |

The user’s repository submission must not commit prohibited raw bank data. Paths here identify archived private verification artifacts used for manuscript review; they are **not** assertions that these exact data outputs are public on GitHub.

New academic reference [7]: Cole, R.A. and White, L.J. (2012), *Journal of Financial Services Research*, 42, 5–29, DOI `10.1007/s10693-011-0116-9` (verified via IDEAS/RePEc).
