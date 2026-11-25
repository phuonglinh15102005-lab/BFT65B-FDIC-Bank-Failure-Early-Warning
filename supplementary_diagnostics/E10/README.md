# E10 — original aggregate evidence, recovered 24 November 2026

Recovered from `BFT65B_UPDATED_REPORT_AND_DEV_EVIDENCE_20261122.zip` → `BFT65B_E10_DEVELOPMENT_DIAGNOSTICS_20261122.zip` → `evidence/E10/`. All three CSVs and the run manifest match the original `RUN_ACCEPTANCE.json` SHA-256 entries byte for byte. The public log and status have only the local user-profile prefix redacted; original/public hashes are in `PUBLIC_LOG_REDACTION.json`. The original archive remains private.

The three HGB refits and predictor summaries use development only. The RBCRWAJ persistence check uses the unlabeled clean financial panel across 2020–2021; no held-out outcomes or scores enter that diagnostic. E10 is post-lock and does not reselect any model or threshold. Verify with `python -B tools/verify_e10_workload_aggregate.py` from the repository root.
