# E10 archived aggregate results

These files document the post-lock diagnostics from the November 2026 Windows run. Data rows about individual institutions and the earlier model inputs are excluded.

| File | Population and interpretation |
|---|---|
| development_15_feature_group_medians.csv | Three descriptive group statistics are reported for each of the 15 registered predictors, alongside observed and missing counts, in the labelled development cohort. Differences compare bank-quarters with and without a positive four-quarter label. |
| hgb_train_vs_validation_ap_dev_only.csv | Three development-fold refits of the selected HGB configuration. Training AP is in-sample. Validation AP checks the corresponding registered result. |
| rbcrwaj_2020q1_zero_cohort_persistence.csv | Unlabelled financial-panel check on the 2020Q1 zero cohort. The denominator at each later quarter consists of the original cohort members observed with a nonmissing ratio. |
| RUN_MANIFEST.json | Scope, configuration, input digests and declared limitations of the original diagnostic run. |
| RUN_ACCEPTANCE.json | Recorded acceptance checks and SHA-256 digests for the three CSVs and RUN_MANIFEST.json. |

All four historical digests matched in the independent 24 November examination. The diagnostic added neither a model-selection candidate nor a score on the held-out test.
