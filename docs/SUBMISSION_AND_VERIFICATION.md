# Academic submission and reproducibility checklist

## What is inside this GitHub candidate
- Complete inherited source-only research code for Parts1–5, fixed protocol, tests, requirements, aggregate evidence and recorded validation.
- Added E11/E12 development-only diagnostic code and verified aggregate CSV outputs.
- The current report is supplied separately in the submission bundle.
- An original frozen content digest ledger and a separate public redaction ledger; no raw/fitted banks data or row-level scores.

## Separate deliverables required by the course
- **Report**: English PDF or DOCX, max 20 body pages + 10 appendix. First page must have student name and ID, **working public GitHub URL**, download method/date, row counts, development/test eras and failure counts. The included draft **still lacks the verified URL**.
- **GitHub**: public from deadline through grades; README, pinned requirements, full code/notebooks with fixed seeds and reproducible method, no datasets. Code citation and AI-use disclosure required.
- **Validation**: fresh clone and safe commands below, plus real-data E2E only if original archived FDIC inputs/cache and environment are supplied. This release cannot establish full anonymous clean-room reproduction.

## Reviewer commands (cross-platform metadata-only)

```sh
python -B -m unittest discover -s tests -q
python -B run.py plan
python -B run.py validate --out ../bft65b_validation
python -B tools/BFT65B_PUBLICATION_PRECHECK.py . --json ../bft65b_precheck.json
```

A pass on these commands **is not** proof that downloads, full model fitting or locked test scoring reran. `continuous` requires private raw snapshots/cached HTTP responses; do not accidentally rerun test.

## Redaction and original SHA provenance

The original archive contains machine-specific local account paths. Public copies replace only absolute user-root tokens with placeholders. All transformed files and digest pairs are listed in `provenance/PUBLIC_PATH_REDACTION_LEDGER.csv`, with original frozen manifest preserved under `provenance/`. The public source manifest is rehashed for a path string in a Part3 documentation docstring; **numerical algorithms, frozen model specification, metrics and test scores have not been changed**. These redacted logs are *not* byte-identical to private originals.

## Before real submission

1. Review all public personal details, especially the report's student ID. Consider publishing only code and uploading report separately.
2. Create a NEW public GitHub repository; upload **the extracted folder contents** (do not upload the ZIP as a single file). Publish no `.zip` evidence bundles or raw FDIC data.
3. Clone the exact public repo into a separate empty folder; run the four safe commands; record any failures.
4. Replace the report front-page URL with that verified public repository URL, re-render the final PDF, check 20+10 page cap. Replace pre-publication report in repo if keeping it there.
5. Confirm public visibility without signing in and keep the repo public through grade release.

Latest authoritative reviewer instructions: `docs/REPRODUCE_REVIEWER.md`. Run `python -B tools/reviewer_check.py --out ../BFT65B_REVIEW_NEW` on the actual public clone; do not use an old report draft.
