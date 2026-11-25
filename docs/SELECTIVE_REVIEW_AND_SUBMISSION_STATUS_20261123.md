# BFT65B — Independent selective reconciliation of GPT Work draft, 23 November 2026

## Decision and source of truth

- **Authoritative base:** `BFT65B_REPORT_INDEPENDENT_REVIEW_REVISED_20261123.docx` (the existing 30-page report), not `BFT65B_FINAL_REPORT_DRAFT.docx` supplied as a GPT Work alternative.
- **Edited output:** `BFT65B_REPORT_SELECTIVE_FINAL_REVISION_20261123.docx` and its PDF. Exactly **12 of 322 report paragraphs** were altered; **all 34 tables, nine figure drawings and section/appendix structure were retained**. The extra draft was not used as the replacement manuscript.
- The alternative draft contains 300 paragraphs, 32 tables and nine pictures, and its editorial QA reports 29 rendered pages; it would remove some defensible evidence and commentary from the author's established report. It also introduces an unsupported formulation, “instructor-approved primary objective,” which was **not** adopted: the archived protocol supports a prespecified selection objective, not a direct documentary record of instructor approval.
- Prespecified HGB, original chronological folds, development threshold, held-out test outputs and E1–E12 execution ledgers have **not** been changed. No model was refitted or test predictions regenerated in this edit.

## Changes adopted after verifying code or source

| Priority | Final section | Finding and actual change | Verification / inference boundary |
|---|---|---|---|
| 1 | §5.3 | Adds a transparent **constant-development-rate Brier reference**: development prevalence `9,246/1,231,631 = 0.7507119%`; constant-score test Brier `0.0030618013`; locked HGB test Brier `0.0021632930` (29.3457% lower). | Calculated from locked cohort counts and Brier definition, **not** a newly selected model; conditional score calibration remains uneven. |
| 2 | §5.2 | Explains **nonmonotone bank-level event recall** under a first-alert-per-CERT-year policy. Lowering a cutoff can advance the first alert into a quarter outside the failure-label horizon, suppressing a later qualifying review in the same bank-year. | Derived from the actual `drop_duplicates(['CERT','year'],keep='first')` policy, not an assertion that this occurred for a specific archived cutoff. |
| 3 | §4.1.1 | Adds the independent **post-lock 5,466,600-cell test-feature formula audit**, with zero discrepancies, alongside the already documented development oracle and Step05 canary. | Verified in `evidence/verified_archive_aggregates/part4_feature_formula_oracle_summary.json`; this is a **read-only formula audit after scoring**, not proof of historical receipt/amendment vintages. |
| 4 | §§3.4–3.5, Appendix G | Replaces speculative row-count/OOM crossover extrapolations with the **measured 1×–5× resource envelope**, 6,144 MiB test guard, and a falsifiable full-job cluster acceptance criterion. Removes unsupported process-import-startup explanation for timer variation. | Archived scale evidence and producer timing, including observed 8.349m rows, 8.567 s Polars, 27.834 s pandas, 2,689.71 MiB vs 1,785.09 MiB RSS. No cluster benchmark claimed. |
| 5 | §2.2 | Changes P3ASSET phrasing to **first nonmissing in the archived snapshot**, avoiding a claim about a regulatory field's introduction date. Makes small equity denominators a **plausible, unverified** explanation for ROE extremes. | Snapshot/ratio audit does not trace every original denominator. |
| 6 | §6.2, Ref [11] | Adds a **specific Vietnamese accounting crosswalk proposal** (debt groups 3–5 / documented eligible gross-credit denominator) rather than equating it with FDIC noncurrent loans. Uses official government links for Circular 31/2024 and its amendment Circular 37/2025. | Proposal for a prospective pilot; not an empirical validation of transferability. Official texts and effective dates verified. |
| 7 | Cover | Corrects the manuscript update date to 23 November 2026. | Does not imply submission. |

## GPT Work observations already covered in the existing report — do not re-edit or deduct again

- Figure 3 already uses **“FEATURE INPUTS UNDER THE ONE-QUARTER REPORTING LAG”**; it does not claim the archived snapshot proves original publication time.
- §3.1.2 already separates the **count/mean-ASSET physical-layout benchmark** from the broader crisis profile and distinguishes ratio-of-medians from median paired speedup.
- §4.2.1 already calls the 504 entries **preprocessing and missingness comparisons**, not 504 learned parameters.
- §5.5 already has the **Spark MLlib equity-only** first-fold validation AP 0.3688066 and AUC 0.9573586, separate from matched 23-column logistic.
- §5.6 already compares full-fold and equity-positive validation AUC, labels fold-refitted HGB correctly and distinguishes bank-quarter recall, eligible-CERT crossings and the annual-first policy.
- Main report already notes **326/341 event recall vs 40.98% COST coverage**, severe 2023 misses, calibration-bin misalignment, outcome-censoring and historical filing-vintage limitations.

## Suggestions not adopted

- No wholesale replacement with the alternate 29-page/32-table draft; 34 original tables and nine figures preserved.
- No causal partition of overfitting versus temporal drift from a group-vs-time split; such a subtraction would not identify either cause.
- No additional model tuning, threshold search, raw test scoring, cost scenarios chosen on test, or an unrun 1–2%-quota comparison.
- No "instructor-approved" protocol claim without actual primary evidence of instructor approval.
- No assumption that **national sector LDR** or **FDIC COST** yields a bank-specific intervention threshold or observed savings.
- The GPT Work additional **review-load peak by quarter** was not promoted: the existing report already states the observed annual-review burden and more material severity mismatch, and the extra post hoc statistic is not needed to answer the rubric.

## Rubric and grading status

The assignment requires English PDF/DOCX, at most 20 main + 10 appendix pages, a public repository URL on the **first page**, documented acquisition/completeness, data quality, Polars+pandas+Spark, leak-safe features, chronological model validation, cost-based alert policy, MLlib demo, conclusions and reproducibility. All major sections are present. The 86/100 or 8.6/10 reported by GPT Work was a **subjective dry-run grade**, not a score one can guarantee; this editorial revision alone cannot eliminate data limitations or make actual review costs observable.

The **two highest remaining grading risks** are: (1) public GitHub URL/anonymous clone and README execution; (2) Part 5's *assumed* false-review-to-missed-event penalty ratio of 1:20. The latter is stated as a transparent development-COST-anchored economic scenario, not an empirical estimate of true intervention costs. Historical filing-version reconstruction remains unavailable; the test-based source-quarter join and training-only preprocessing do not prove full historical information availability. **No verified evidence of leakage-rule violation has been identified**; do not apply the rubric's special cap speculatively.

## Verification of the edited manuscript

- Bytewise compare: 12/322 paragraphs changed; 34 tables have identical cell text to the base; 9 displayed inline images have identical source bytes.
- The edited DOCX rendered to **30 A4 PDF pages**; Appendix A starts on page 21. No extra page was introduced.
- Required calculations, dates and key labels visible in rendered PDF; contact sheets visually inspected across pages 1–30.
- The Word/PDF still carry `[INSERT VERIFIED PUBLIC REPOSITORY URL BEFORE SUBMISSION]`. **This is a blocker, not a completed field**.

## Has it been submitted? What to do next

**There is no evidence that the user has already submitted the assignment.** The currently connected GitHub account shows no verifiable BFT65B public repository; the academic LMS confirmation has not been presented. Even a correctly prepared local ZIP does **not** constitute submission.

1. Upload the *repository contents*, not the ZIP as one file, to a GitHub **Public** repository. Confirm whether the author consents to student name and ID being public in the report (assignment requires them on the cover). Run an anonymous HTTPS clone on a separate folder and verify README commands, pinned requirements, source/aggregate tests, and output links. Record actual URL and commit SHA.
2. Add the verified public repository URL as an actual **clickable hyperlink** on report page 1. Regenerate PDF from the **same edited DOCX**, then check exactly 20 main + 10 appendix pages and verify the URL opens without logging in. The final published repo/report should point to the same commit and manuscript.
3. Submit the PDF/DOCX and public GitHub URL through the **course's official submission channel before its deadline**. Save proof of receipt. No assistant in this exchange has verified an LMS submission or a remotely accessible BFT65B repo.
4. If the instructor explicitly demands an independent full fresh FDIC acquisition→model/test rerun, run it separately with the retained exact protocol, without overwriting or claiming that it reproduces the historical one-time held-out score claim. The available Windows continuity test covers archived-snapshot/cache→development; all external dependencies and historical vintage limits must be stated.

### Web verification (external sources, not local experiment)

- FFIEC 031/041 General Instructions: 30-day receipt deadline for most banks, 35 days for specified foreign-office reporters, and amended-file process. Official source: https://www.ffiec.gov/sites/default/files/data/reporting-forms/FFIEC031_FFIEC041_202503_i.pdf
- SBV Circular 31/2024/TT-NHNN and amending Circular 37/2025/TT-NHNN; 37/2025 amendment effective 15 December 2025. Official sources: https://vanban.chinhphu.vn/?docid=210625&pageid=27160 and https://vanban.chinhphu.vn/?docid=215867&pageid=27160
