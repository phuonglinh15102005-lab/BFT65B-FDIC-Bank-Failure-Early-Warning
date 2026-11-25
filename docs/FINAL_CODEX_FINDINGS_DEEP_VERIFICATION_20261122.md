# Independent reconciliation of the Codex review and the BFT65B manuscript

**Date:** 22 November 2026  
**Material checked:** `BFT65B_FINAL_CODE_REPORT_REVIEW_20261122.zip` (five files), original 3-page instructor rubric, the E12 report in DOCX and PDF, `BFT65B_GITHUB_REPOSITORY_FOR_CODEX_REVIEW_20261122.zip`, registered sources and archives `BFT65B_WORK_REPORT_HANDOFF_V2_VERIFIED_20261118.zip`, `BFT65B_SUPPLEMENT_2_Part5_Development.zip`, and `BFT65B_CODEX_EVIDENCE_SUPPLEMENT.zip`.

## Executive judgement

Codex's central judgement is **correct**: the technical report is materially advanced and the original repository passes metadata/source QA, but the package is **not yet compliant for final submission** because page 1 lacks an actual, independently accessible public GitHub URL. Its other material findings about missing machine-readable public evidence, E12 AP bounds, source-date versus information-availability correctness, growth endpoints, reduced benchmark scope and replay boundaries are supported by the inspected files.

**No result requires model re-selection, an altered cutoff or another scoring of the reserved test.** The saved model-lock, test-claim and test-audit bytes were directly rehashed: the lock SHA-256 in both claim and audit matches the archived lock; the claim SHA in the audit matches the archived claim. Audit records `predict_proba_calls=1`, `hyperparameters_or_threshold_changed=false`, while this cannot establish an absolute prohibition on a hypothetical run elsewhere. Nothing in this review re-executed the final test.

## What Codex got right, and nuances

| # | Issue | Independent conclusion | Treatment in revised deliverable |
|---:|---|---|---|
| 1 | Missing GitHub URL | **Correct, blocking.** First page is a placeholder and neither remote access nor remote clone is verified. | **Open.** Report still marks required URL explicitly. Only a real remote URL can close it. |
| 2 | Incomplete fresh-input E2E | **Correct.** Source tests and saved-cache replay do not equal FDIC live download + clean install + model train/test. | README/reproduction boundaries explicitly distinguish metadata, historical frozen-input replay and unexecuted full E2E. |
| 3 | Missing public candidate, threshold, MLlib and lock evidence | **Correct for the original GitHub ZIP, not the PDF.** The PDF already contains Table I5 with 21 candidates and Table 5 with four cost scenarios. | Exported original archived aggregate CSVs, 11 calibration bins, Spark summary, canary, preprocessing and digest-only lock/claim/audit certificate into the revised repo, each with archive member and SHA-256. No score rows, CERT-level event ledgers or fitted model uploaded. |
| 4 | E12 AP `0.2929–0.3035` | **Clear textual error**: 2007–08 positive-equity AP is `0.285358`. Code uses `>=`, not strictly `>`. | Report §5.6 now says `0.2854–0.3035`, *at or above τ*. Table 8 unchanged. |
| 5 | Historical PIT claim | **Correct caveat.** Exact REPDTE/calendar joins prevent one kind of leakage, not late amendments to a historical quarter. | Revised §4.1 and 2010Q1/2009Q4 example: historical filing-vintage gap explicit. No claim that historical availability was fully proven. |
| 6 | Wrong canary producer conflation | **Correct.** The 29-quarter/5,148-row/308,880-cell experiment belongs to Part4 Step05, not the earlier V2 as-of gate. | Corrected report and published the original Step05 audit plus 29-quarter aggregate CSV. |
| 7 | Scaling measures a reduced workload | **Correct.** Stress results do not benchmark every final feature transform. Script defaults differ from the recorded CLI overrides. | Report specifies 1×/3×/5×, 3 repeats and 6,144 MiB guard; identifies simplified crisis count/mean and lag count/match workloads. Extrapolations remain explicitly hypothetical. |
| 8 | Incomplete public trial/size ledgers | **Correct in scope.** Original private archive and published summarized measurements contain more than the GitHub ZIP previously exposed. | Added archived scale and early benchmarking summaries; some current layout, interleaved and detailed source-size trials remain offline. These are still not publicly reproduced. |
| 9 | Test claim path-local | **Correct.** Exclusive creation in selected output path is not a global study-level one-time register. | Precisely disclosed. Stored lock→claim→audit chain is archival process evidence; no modification to frozen scorer. |
| 10 | README Windows shell portability | **Correct.** `%USERPROFILE%` works in `cmd.exe` but not PowerShell; `py -3` may not select pinned Python. | Added explicit shell/interpreter guide and reviewer commands for metadata checks. |
| 11 | Identity and AI credit | **Mostly a publication-control issue, not a scientific error.** Course requires name/ID on the submitted cover; public repo may disclose them. | README matches report's AI-tool role disclosure and warns about public identity. |
| 12 | COST ratio 20:1 | **Correct qualification.** Median failure COST is observed, but reviewer fee at 5% of median and preventable severity are assumptions. | Kept frozen scenario, restored all four archived threshold scenarios and two distinct break-even calculations; no claim of empirically measured cost per review. |
| 13 | Missing intermediate quarters in 4Q growth | **Correct.** Exact `t−1` determines decision-row existence; 4Q growth at decision `t` compares ASSET at exact `t−1` and `t−5` only. | Corrected report §4.1 and Appendix H; missing a *required endpoint* yields null, not an arbitrary intermediate quarter. |
| 14 | Field/status and memory units | **Correct for identified prose.** `STNAME` is a state field, not institutional activity; `2,689.71 MiB / 1,024 = 2.6267 GiB`, not 2.69 GiB. | Separately describes Financials versus Institutions, uses 2.627 GiB, marks row-group pruning as metadata-supported rather than physical IO traced. |
| 15 | Near-tie family logic | **A future code-hardening suggestion, not an actual selection failure.** Winner 0.295766 versus runner-up 0.293978 differs by ~0.001789, well beyond 0.0002. | Frozen selection remains unchanged. |
| 16 | COST verifier missing one input pin | **Valid engineering hardening observation.** Event-flag permutations could leave counts unchanged and shift weighted results. | Keep archived cross-check and warn that future verifier should pin full event-ledger digest; do not re-score. |
| 17 | Crash orphan output/page identity | **Valid forward-looking improvement.** Checks on counts/hashes are not proof that every API page's identity was complete. | Documented for future acquisition; no retroactive claim of a new live download. |
| 18 | Nonfatal ResourceWarning and QA scope | **Valid limited QA caveat.** Unit test suite succeeds despite ResourceWarning; `validate` pins 131 canonical paths but omits new supplementary archives. | Added separate stdlib verifier of public aggregate SHA ledger and cross-table arithmetic. ResourceWarning remains documented, not hidden. |

## Direct arithmetic and source verification

- **21 candidate configurations:** archived `development_model_ranking_rechecked.csv` contains 21 distinct configurations. For 20 rows, three fold APs are present and mean to each recorded objective; the equity-only row has a valid `mean_ap=0.181467665525...` but **blank fold APs**. Those are sourced independently from `evidence/aggregate/baseline_fold_metrics.csv`, rather than filled with approximations. Winner: HGB_L15_LR0p05_I150_L21_CLnone, mean 0.295766292636; runner-up 0.293977580711; best logistic 0.249761379305.
- **Four cost scenarios:** ratios r = 5, 10, 20, 50. Selected r=20 gives 4,124 false first CERT-year reviews + 20 × 436 missed institutions = 12,844 review-equivalents, threshold 0.023971438944668057. The ratio is a policy assumption anchored to FDIC COST, not directly observed false-review expense.
- **Test event and COST coverage:** 326/341 = 95.6012% detected events; covered COST approximately 40.9778%. These describe very different evaluation units. Neither annual AP nor annual ROC-AUC can be averaged to reconstruct pooled test ranking.
- **E12 equity-positive results:** AP 0.292921, 0.303452, 0.285358 across the three fixed validation folds, with AUC 0.932636, 0.965065, 0.940521. This shows separation conditional on lagged positive *book* equity, not confirmed economic solvency or causal early intervention.
- **Part4 canary:** `part4_step05_audit.json` and `asof_canary_by_quarter.csv` are the correct archived producer/evidence: 29 quarters, 5,148 sampled decisions, four checks over 77,220 cells each = 308,880 comparisons. A fixed REPDTE is not a filing receipt timestamp.
- **Test lock chronology:** archived claim UTC `2026-11-15T02:20:39.220108+00:00`, audit UTC `2026-11-15T02:21:10.247182+00:00`. These are saved process records, **not** evidence of independent reconstruction from historical FDIC files on a new machine.

## Revised report scope

A targeted modification of 26 original paragraphs produced `BFT65B_REPORT_CODEX_RECONCILED_20261122.docx` and its rendered PDF. Neither the 35 existing Word tables nor the nine existing images was changed. The PDF still has **30 pages (20 main + 10 appendix)**. The most important corrections appear in the executive/source description, §3.4 stress scope, §4.1 growth/PIT, §5.1 ranking interpretation, §5.3 test claim, §5.6 E12, §6 limits and Appendices D/G/H.

Crucially, the corrective passages state **what the experiments established** and **what they cannot establish**, without mechanically repeating uninformative disclaimers. The original threshold, model, final test and empirical tables are unchanged. There is **no additional E13 model run**.

## Newly reconstructed GitHub candidate

The updated repository contains vetted primary aggregate exports in `evidence/verified_archive_aggregates/`, `SOURCE_CHAIN_SHA256.csv` with original archive members and hashes, a digest-only model lock certificate, a stdlib `tools/verify_released_aggregates.py` and explicit reviewer instructions. The initial attempt at a local fresh Git clone found the new CSVs were ignored by a blanket `*.csv` rule; that **real defect was fixed** with a directory-specific `.gitignore` exception before final packaging.

Executed checks on a **new clone of the local Git repository**:

| Test | Verified result |
|---|---|
| Git tracked files | 885 / 885; the recovered aggregate CSVs are included |
| `python -B -m unittest discover -s tests -q` | 45/45 PASS |
| `python -B run.py plan` | PASS, metadata only |
| `python -B run.py validate --out ...` | PASS, 131 historical pinned source entries |
| `python -B tools/verify_released_aggregates.py` | PASS, 21 candidates, 4 policy scenarios, 29 canary quarters, 11 calibration bins, MLlib and 17 aggregate/digest provenance records |
| `python -B tools/BFT65B_PUBLICATION_PRECHECK.py . --json ...` | PASS, 885 files, zero automatic flags |
| PDF rendering/page count | PASS, 30 pages; checked page thumbnails and critical pages |

The Git clone was **LOCAL**, not from an actual public GitHub remote; a clean dependency install and fresh FDIC acquisition-to-model scoring remain **NOT EXECUTED**. Static scanner PASS is not an absolute guarantee that all document content is appropriate for public release, especially when the required report contains the author's identity.

## Must-do actions before the course deadline

1. Create/publish the actual public GitHub repository; verify accessibility while logged out and clone it from the **remote HTTPS URL**, then rerun the five safe reviewer commands listed in README. Check tracked-file and manifest coverage. No raw data or private score ledgers should be committed.
2. Replace the placeholder URL on the report's first page in the DOCX; export the PDF again and confirm it remains 20 pages plus a 10-page appendix. Submit that URL-corrected PDF and the public GitHub link.
3. If course assessment interprets end-to-end reproduction as a fresh API download and full model execution, disclose the actual frozen-input replay boundary; do not claim a run which never occurred. Only a separately audited live acquisition and pipeline execution could establish full E2E, and no additional locked-test trial should be done to improve reported metrics.

**Overall:** Codex's blocking conclusion about publication is valid; its source/methodology criticisms are mainly correct, with the important distinction that some tables already existed in PDF and were missing only from public machine-readable evidence. Technical fixes have been implemented in a new candidate. The publication URL/remote clone and full live end-to-end remain genuinely unresolved.
