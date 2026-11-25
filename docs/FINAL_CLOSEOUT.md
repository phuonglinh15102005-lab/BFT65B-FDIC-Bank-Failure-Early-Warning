# Final submission checklist

S4 and S5 are complete evidence: no more storage, preprocessing, policy or upstream reruns are needed for this report. Both clean installs passed. Public HTTPS base clone and its data-free audit passed 25 November 2026 (`6258825946139d56b486787b8caf7210a632c326`). The final documentation commit must be checked again after publication; record its SHA in the separate report.

1. Extract the source-only ZIP to a short path. Review privacy; do not add the separate report, private return ZIPs, raw files, caches, per-row scores or fitted models.
2. Create a public GitHub repository. Replace the URL placeholder in README and in the separate DOCX's first page. Refresh `FILE_MANIFEST_SHA256.csv` using `python -B tools/refresh_distribution_manifest.py`; do not modify scientific source pins. Commit/upload the source tree including dotfiles.
3. Clone the public HTTPS URL anonymously (disable credential helper and interactive login), record commit SHA, date and Python version, then run `python -B tools/reviewer_check.py --out ../BFT65B_REVIEW_PUBLIC` from the clone. Keep logs outside Git. Record actual outcome before asserting anonymous-clone verification.
4. Export the separate report to PDF and verify 20+10 pages. Keep repository public until grades are released; later commits are ignored.

Scientific boundaries: fresh acquisition-to-scoring was not rerun; original model guards require original development bytes; historical filing vintages, actual review costs and preventability are not identified. Do not re-score the final test. S5 is separate upstream and policy evidence, not full E2E.
