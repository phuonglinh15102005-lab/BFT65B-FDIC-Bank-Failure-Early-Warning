# Current release status — 25 November 2026
- Separate English report: 20 main + 10 appendix pages; authoritative PDF submitted separately (see report/README.md).
- Public repository and credential-free HTTPS clone verified 25 November 2026 at base commit `6258825946139d56b486787b8caf7210a632c326`; all 14 public reviewer checks, 45 unit tests and 1,259 manifest entries passed. The documentation commit `050889604e449efa26c7bb44943c58cef8477e54` also passed anonymous clone and repeat public audit. Any later targeted revision requires its own audit; the separate report/logs identify the final audited SHA.
- S5: storage sensitivity complete; second continuous raw-to-development replay PASS; original-input policy-mode replay PASS; both clean install/import profiles PASS.
- Full live acquisition-to-model/scoring, grid/refit reproduction and execution within clean venvs remain unverified. Frozen model and test unchanged.
- Historical notes are dated records; current status is governed by this file, README and S5.

S6 adds a separate AI-assisted 26 November Linux feature audit, scaling and concurrency evidence; check returned aggregate results using the S6 verifier. The new documentation release is not audited until the new clone check completes.

## S7 — exact development artifact diagnostic (26 November)

The 26 November Windows read-only diagnostic compares the original and 25 November replay: 1,231,631 unique decision keys, all 18 non-key columns exactly equal after key alignment, zero null/NaN/float-bit mismatches. Row order and row-group layout differ; byte SHA still differs. The writer and Arrow schema metadata match. This does not establish the sole cause of byte divergence or full E2E. Original model SHA guards remain unchanged. See `evidence/development_sha_diagnostic_20261126/README.md`; public aggregate check: `python -B evidence/development_sha_diagnostic_20261126/verify_s7.py`.
