# Public evidence map — E1 through E12

All files under `evidence/verified_archive_aggregates/` are **archived summary artifacts** from the original project (where unchanged) or a clearly labelled digest certificate. Their source-archive member names and SHA-256 values appear in `SOURCE_CHAIN_SHA256.csv`. Re-exporting existing evidence is **not a new model run**.

| Report ID | Public evidence | Verification boundary |
|---|---|---|
| E1 | `evidence/aggregate/storage_benchmark_original.csv`, source acquisition code | Private historical source Parquet, size and row-group primary ledgers held offline |
| E2 | `evidence/aggregate/missingness_chart_data.csv`, `ratio_diagnostics_by_quarter.csv`, Part2 source | Bank-level exits and main clean panel private |
| E3 | `evidence/aggregate/scale_summary.csv`, `verified_archive_aggregates/scale_trials_archived.csv`, `part3_early_benchmark_summary.csv`, `part3_spark_aggregate_parity_audit.json`; Spark plans | Early blocked benchmark and later reduced-workload stress are different experiments; later interleaved primary trials still offline |
| E4 | `verified_archive_aggregates/part4_step05_canary_by_quarter_29.csv`, `part4_step05_canary_audit.json`, `part4_feature_formula_oracle_summary.json`, `part4_fold_preprocessing_parameters.csv` | Step05 29-quarter canary is **not** Step V2 relabel/as-of gate; no filing-vintage verification |
| E5 | Frozen protocol `00_ASSIGNMENT/part5_protocol_freeze.json`; `verified_archive_aggregates/model_lock_claim_audit_digest_certificate.json` | Hash certificate, no private model file |
| E6 | `verified_archive_aggregates/candidate_grid_21.csv`, `threshold_cost_scenarios_4.csv`, `forward_platt_diagnostics.csv`, `logistic_candidate_summary_12.csv`, `hgb_candidate_summary_8.csv`; existing permutation data | Primary dev-only model selection and policy; no raw OOF scores |
| E7 | `verified_archive_aggregates/test_calibration_bins_11.csv`, digest certificate; `evidence/aggregate/final_test_year_metrics.csv`, `locked_event_recall_by_asset_size.csv` | One saved test-score ledger remains offline; no re-scoring |
| E8 | `verified_archive_aggregates/spark_mllib_first_fold_metrics.csv`, `registered_logistic_parity_summary.json` | Local demonstration only; does not reproduce HGB with Spark |
| E9 | `release_evidence/continuous_windows_20261119/`, `REPRODUCTION_VERIFICATION_REPORT.md` | Frozen source/cache-to-development replay, not fresh acquisition/model-test E2E |
| E10 | `supplementary_diagnostics/E10/` (original hashed aggregate files; redacted log/status) | Post-lock development summaries; unlabeled clean 2020/21 data for RBCRWAJ |
| E11 | `supplementary_diagnostics/E11/verified_aggregate_results/outputs/` | Post-lock development fold and unlabeled matched-CERT reporting transitions |
| E12 | `supplementary_diagnostics/E12/verified_aggregate_results/outputs/` | Post-lock development-only positive-equity robustness and random-fold overlap |

**Do not upload:** raw FDIC snapshots, Parquet, any bank-level/score-row ledgers, fitted models, cached response bodies or additional private archived ZIPs. Timing/benchmark evidence from separate schedules must not be combined as one identical experiment.

**24 November additions:** `verified_archive_aggregates/locked_policy_quarterly_workload_62.csv` and `locked_policy_workload_and_metrics_audit.json` contain read-only aggregates from the frozen score/first-alert/event ledgers; `development_source_cost_audit_original.json`, `scale_audit_original.json`, and `storage_configuration_extract.json` record original measured settings and cost summaries. `20261124_SOURCE_PROVENANCE.json` identifies their archived members.
