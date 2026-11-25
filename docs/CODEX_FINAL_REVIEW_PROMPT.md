# Senior Codex final code/report review brief — BFT65B FDIC

**Act as** an independent senior data engineer, quantitative model validation reviewer and academic marker.

Read `AGENTS.md`, `README.md`, `report/BFT65B_E12_RESEARCH_REPORT_PENDING_GITHUB_URL.pdf`, `config/source_manifest.json`, `00_ASSIGNMENT/part5_protocol_freeze.json`, the Part1–5 canonical sources, `supplementary_diagnostics/E11` and `supplementary_diagnostics/E12`, and `docs/SUBMISSION_AND_VERIFICATION.md`.

## Required audit

1. Map each rubric requirement to exact code, public aggregate evidence and report page. Flag missing primary evidence vs measured evidence.
2. Check date/quarter construction, as-of joins, lag dates, event/competing-exit/censoring labels, train-only preprocessing, 4-quarter embargo, test-split isolation and one-time evaluation. Show counterexamples if leakage is possible.
3. Audit whether the frozen model selection objective was mean *unweighted chronological fold AP*, and the cost-policy/threshold was separate and development-only; verify that no test result influenced selection.
4. Recalculate from aggregate CSV where possible: train/validation AP and ROC-AUC, prevalence, positive-equity subgroup Do not fabricate missing statistics; check bank-level detection denominator, fixed-threshold recall and distinct-event vs bank-quarter units.
5. Verify benchmark fairness, Polars plans, Spark parity and scaler explanation against actual evidence. Separate replay from fresh-download E2E.
6. Review `requirements.txt`, `requirements/*`, `run.py plan`, `run.py validate`, unit tests, Windows quick-start, cache prerequisites, and fresh-clone usability. Report specific broken commands and platform incompatibility.
7. Inspect publication hygiene: credentials, home paths, raw datasets, row-level predictions, fitted models, embedded archives, reports containing personal identifiers, attribution and AI disclosures. Historical log outputs are public location-redacted copies; do not treat changed hashes as hidden misconduct.
8. Verify numerical claims and the strength of conclusions: model overfit vs temporal drift, positive lagged equity robustness, CBLR caveat, 20:1 review-cost scenario, locked-test data use, external validity and Vietnam transfer.
9. Check first-page GitHub URL, final PDF <=20 main + 10 appendix, dates, rows and failures. URL is currently NOT VERIFIED.

## Allowed commands (safe)

```sh
python -B -m unittest discover -s tests -q
python -B run.py plan
python -B run.py validate --out ../bft65b_codex_source_validation
python -B tools/BFT65B_PUBLICATION_PRECHECK.py . --json ../bft65b_publication_scan.json
```

Do not run original test scoring or mutate protected frozen evidence. Do not assume external FDIC datasets are available. If a command cannot run, state why.

## Output required

Produce a markdown table with `severity (blocking/high/medium/low)`, `rubric part`, `exact path:line`, `evidence`, `consequence`, `proposed fix`, `requires Windows raw dataset?`; list pass/fail per safe command. Distinguish defects from optional enhancements. Prioritize true score/reproducibility risks, not cosmetic edits. **Do not claim the repository is final until public URL, access, clean clone and report cover are checked.**
