# Final submission checklist

S4 and S5 are complete evidence: no more storage, preprocessing, policy or upstream reruns are needed for this report. Both clean installs passed. Public HTTPS base clone and its data-free audit passed 25 November 2026 (`6258825946139d56b486787b8caf7210a632c326`). The 25 November documentation commit `050889604e449efa26c7bb44943c58cef8477e54` also passed public HTTPS clone and data-free audit. Any later documentation revision must be checked again after publication; record the actual final audited SHA in the separate report. The original upload checklist below describes the historical first publication; do not recreate the existing repository.

1. Extract the source-only ZIP to a short path. Review privacy; do not add the separate report, private return ZIPs, raw files, caches, per-row scores or fitted models.
2. Create a public GitHub repository. Replace the URL placeholder in README and in the separate DOCX's first page. Refresh `FILE_MANIFEST_SHA256.csv` using `python -B tools/refresh_distribution_manifest.py`; do not modify scientific source pins. Commit/upload the source tree including dotfiles.
3. Clone the public HTTPS URL anonymously (disable credential helper and interactive login), record commit SHA, date and Python version, then run `python -B tools/reviewer_check.py --out ../BFT65B_REVIEW_PUBLIC` from the clone. Keep logs outside Git. Record actual outcome before asserting anonymous-clone verification.
4. Export the separate report to PDF and verify 20+10 pages. Keep repository public until grades are released; later commits are ignored.

Scientific boundaries: fresh acquisition-to-scoring was not rerun; original model guards require original development bytes; historical filing vintages, actual review costs and preventability are not identified. Do not re-score the final test. S5 is separate upstream and policy evidence, not full E2E.

26 November: run the S6 aggregate verifier in addition to the original 14 reviewer checks. The report should identify the final audited commit, not claim that the new feature experiment reran fitting or held-out scoring.

## S7 — exact development artifact diagnostic (26 November)

The 26 November Windows read-only diagnostic compares the original and 25 November replay: 1,231,631 unique decision keys, all 18 non-key columns exactly equal after key alignment, zero null/NaN/float-bit mismatches. Row order and row-group layout differ; byte SHA still differs. The writer and Arrow schema metadata match. This does not establish the sole cause of byte divergence or full E2E. Original model SHA guards remain unchanged. See `evidence/development_sha_diagnostic_20261126/README.md`; public aggregate check: `python -B evidence/development_sha_diagnostic_20261126/verify_s7.py`.
