# Producer replay patches —18November2026

Only two release-copy source files were changed. Archived originals remain untouched. Exact changes are preserved in WORKFLOW_PRODUCER_PATCHES.diff and SHA/syntax evidence in WORKFLOW_PRODUCER_PATCHES.json. No real-data, model, metric, oracle, canary or scientific producer command was executed for this patch review.

## Part2C: external read-only cache

Added --cache-dir PATH. It requires --offline, an existing directory, and a source-cache/output separation check. The Collector is initialized in the new output directory as before, then its cache pointer is redirected to the prior cache. Original Collector.get validates URL/body SHA and reads cached hits; offline misses fail without network or source-cache write. The unchanged adjacent02b helper retains its original required SHA. Input/registry/clean/PIT transformations are unchanged. New config records read_only_cache_dir. Normal offline behavior without --cache-dir remains available.

Supported command: python -B 02c_finalize_panel.py --step2-dir ORIGINAL_STEP2 --step2b-dir ORIGINAL_STEP2B --out NEW_OUTPUT --offline --cache-dir ORIGINAL_STEP2C/request_cache. Original output status remains CLEAN_PANEL_READY_FOR_REVIEW, followed by external replay comparison.

Use original frozen checkpoint inputs for this isolated replay. Fresh Part2A summary paths/timestamps change the Step2B input-signature contract; do not silently claim a newly chained E2E run using old Step2B metadata.

## Part4V2: production-only development cohort

Added --production-only with explicit --asof-quarters 0. In this mode reject --pandas-oracle-source, --old-dev and --assistance-events-csv. Original feature construction, original outcome/status function call, primary-policy expressions,20-column cohort selection, primary/legacy Parquet writes and accounting remain unchanged. All preexisting public helper functions retain identical AST.

Skip only the already-closed full PIT source-value check, pandas policy/oracle adjudication and canary. Their statuses become CLOSED_PRIOR_NOT_RERUN; policy_mismatch is null. Production status is PRODUCER_REPLAY_COMPLETE_COMPARISON_REQUIRED, not audit PASS. The final full-audit requirement and old instruction to repeat preprocessing checks apply only to default full-audit mode. Every mode now requires a NEW --out-dir; no producer output is overwritten.

Supported command: python -B part4_v2_relabel_asof_gate.py --clean ORIGINAL_CLEAN --pit ORIGINAL_PIT --registry-zip ORIGINAL_BUNDLE --step01-source ORIGINAL_STEP01_SOURCE --out-dir NEW_OUTPUT --asof-quarters 0 --production-only. The caller must compare every generated development key/label/source-date/split/feature/null mask against the archived development input before reporting replay PASS. Byte identity is recorded separately from numerical equivalence.

No final-test feature/cohort/prediction/model file is opened by this mode. It imports Step01 functions without executing Step01.main. Shared source clean/PIT Parquet cover the complete snapshot, while collected feature/output rows are restricted to development. Do not interpret that as a claim that no later raw row group was physically scanned.
