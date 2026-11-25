# BFT65B — Independent verification of the 23 November examiner critique

**Manuscript audited:** `BFT65B_REPORT_CODEX_RECONCILED_20261122.docx`, SHA-256 `8dfcdd38b61de5e20277c6c1e4104c85b5efa1f6ccd10815685c709ce8c1e59f` — exact match to the manuscript identified in the supplied `BFT65B_STRICT_EXAMINER_REVIEW_20261123(1).md`.

**Revision:** `BFT65B_REPORT_INDEPENDENT_REVIEW_REVISED_20261123.docx` and its visually checked PDF. **Scope:** source and archive consistency checks plus verified official definitions; **not** a new FDIC-data-to-test independent model replay, nor proof of any public GitHub URL.

## 1. Verdict on the 86/100 provisional mark

- `14 + 17.5 + 22 + 13.5 + 12.5 + 4.5 + 2 = 86`. Content is `84/95`. If the instructor assigns zero rather than two of five Reproducibility points to an absent/inaccessible public repository, the same fixed content assessment yields **84/100**.
- The precise score is an examiner estimate, not an outcome uniquely implied by the qualitative rubric. In particular the cost-based threshold remains **partly rather than completely data estimated**, and full clean-environment reproduction remains unexecuted.
- Main methodological strengths are source-to-panel reconciliation, cause-specific exit handling, strict temporal train/validation separation, multi-engine numerical parity, source manifest integrity and the archived single-test lock→claim→audit chain.
- The leakage gate applies if prohibited future information is actually used. Source-quarter checks, excluded future-event predictor fields and fold-fitted preprocessing offer strong protection against obvious look-ahead. They do **not** establish exact historic filing vintages. Retrospective risk-set construction can induce selection; this is an important limitation, not conclusive proof of illegal future predictors.

## 2. Code/archived result checks performed in the current review

- Audited actual DOCX and PDF, not only the reviewer notes; original DOCX hash matched.
- Inspected archived repository source, including `02_PART2_DATA_QUALITY_PANEL/code/02c_finalize_panel.py` for `LAST_REPDTE`/`ELIGIBILITY_END` and exact `SOURCE_REPDTE`→`DECISION_DATE` mapping, and `04_PART4_FEATURE_PIPELINE` for exact-quarter features and training-only preprocessing.
- Executed `python -B -m unittest discover -s tests -q`: **45 tests passed**. Some tests intentionally report simulated blocked stages; the suite itself finished OK.
- Executed `python -B run.py plan`: **PASS** as an archived execution-plan read.
- Executed `python -B run.py validate --out <separate-output>`: **PASS_SOURCE_RELEASE_VALIDATION**, **131 paths**, `no_scientific_replay=true` and `full_E2E=NOT_EXECUTED` per tool response.
- No bank-row Parquet inputs, live acquisition or independent locked-test `predict_proba` were rerun in this review. Archived metrics are treated as recorded evidence, not newly observed results.

## 3. Major critique findings and exact disposition

| Critique claim | Independent finding | Revision |
|---|---|---|
| Report exceeds 20+10 | Original and updated DOCX both render to 30 A4 pages; appendix begins p.21. | Confirmed layout after edits. |
| GitHub URL missing | **Correct; submission blocker**. Current cover is explicitly marked as unverified. | Remains pending actual anonymous public clone; no invented URL inserted. |
| Part 1 schema 33 columns unclear | **Correct**: 30 accounting fields plus `CERT`, `REPDTE`, `STNAME`. | Clarified in §1.1. |
| ZSTD and row groups unspecified | Archived producer settings support ZSTD level 3 and 100,000-row groups. | Added to §1.2 with the 2023/2023Q1 predicate examples. |
| Original receipts/filing vintages absent | **Correct**: `REPDTE` is reporting period; FFIEC deadline/possible amendments are separate facts. | Figure 3 header rewritten; risk-set limitation clarified in §2, §4, H2, Q2. |
| 31 versus 744/25 removed rows | Different stages of PIT and outcome resolution; must not add as a single filter. | Appendix H now distinguishes stages. |
| Layout benchmark equals full crisis aggregation | **Incorrect description in former report**; the producer measures count and mean-ASSET by quarter under date filtering, not Table 2's full crisis profile. | Corrected §3.1.2. 2.82× is ratio of medians; ~2.79× median paired speedup. |
| Spark shuffle bytes 63.7 MiB measured | Only `sizeInBytes` in a plan is documented, not measured remote shuffle bytes. | Corrected §3.3. |
| 1,900 years / 35–48m extrapolation as decision | Too remote from 1×–5× stress scope. | Removed speculative two-millennia claims from main text, made Q1 evidence-driven. |
| 504 are all training-fitted parameters | **Incorrect**: this includes training/validation missingness comparisons; clipped bounds only apply to clipped candidate branch. | Corrected §4.2, Appendix H. |
| FDIC COST directly estimates 20:1 | **False as an empirical ratio**: if false-review fee=0.05m and miss=m, ratio is always 20 for any positive m. | Explicit algebra and cost limitations in §5.2 and §6. |
| MLlib demo results absent from prose | Correct: archived equity-only MLlib AP 0.3688066, ROC-AUC 0.9573586 on earliest development fold. | Added to §5.5; distinct from 23-column Table 7. |
| E12 AP range wrong | This is an **outdated critique** for the Codex-reconciled report; §5.6 already says 0.2854–0.3035. | Preserved correct range; added whole-fold versus subgroup AUC comparison. |
| Table 8 'Frozen HGB' is imprecise | Correct: E12 refits the *selected specification* in each development train fold, not the final model. | Corrected caption and denominators. |
| I2 repeats I4 | Correct: selected-year I2 duplicates rows of full-year I4. | Removed the subset table and renumbered surviving I2–I4; preserved source caveat about undefined AP/AUC at zero positives. |
| Annual 2020 AUC 1.000 is exactly perfect | False; archived point estimate is 0.999795 rounded to 3 decimals. | Reported 0.9998. |
| QBFASSET = 'failure-time' assets | Overstates timing. FDIC defines last reported total assets before effective failure date. | Renamed J2/J4, clarified brackets and source. |
| Wilson intervals express deployment uncertainty | False. They are conditional intervals from small observed subgroups. | Tightened J4 caveat. |
| External Vietnam/FDIC sources questionable | Checked primary/official sources; government consolidated-law identifier and date, WTO 4+27+2+9 figures, Banking Academy 107% are authentic. | Kept citations; added concrete FDIC noncurrent-vs-Vietnamese classified-debt and liquidity/funding-definition caveats. |

## 4. Scientific interpretation to retain

**Point-in-time:** This implementation establishes exact **reporting-quarter** joins (the previous quarter's REPDTE), not original acceptance/amendment vintage. A one-quarter delay is plausible under usual 30/35-day filing deadlines, but it is not enough to prove that present-day revised values match the original supervisory information set. Similarly, retrospective eligibility is a conditional adjudicated population; future risk-set selection merits explicit sensitivity discussion. The absence of verified vintages cannot be resolved by inventing timestamps.

**Model selection:** HGB specification chosen by unweighted mean AP across three expanding chronological folds and a four-quarter prevalidation gap. This differs from pooled AP or row-weighted AP, which are post hoc context only. The archived final test result (AP 0.434925, AUC 0.981621, 326/341 captured, 40.98% COST captured) is *not* a reason to retune.

**E12:** Validation ROC-AUC restricted to bank-quarters with positive lagged equity changed little relative to the full folds, but these are not exchangeable cohorts and AP depends on prevalence. This supports ranking information beyond a negative-book-equity flag, not a causal inference about features or high threshold recall on every macro regime. The E12 CERT-crossing measure does not impose the annual-first review policy used in main event recall.

**Cost:** If the mean/median positive development FDIC estimated failure COST is `m`, with hypothetical costs `c_FP=0.05m` and `c_FN=m`, ratio `c_FN/c_FP=20` is *fixed by assumption*. FDIC data supply a USD anchor, whereas development scores select the cutoff conditional on this assumed policy and annual-review rule. Real examiner hours, real review costs, preventability and counterfactual losses are unmeasured. Avoidable-COST sensitivity on the locked test is an exploratory scenario, not causal proof and not a new threshold selector.

**Cluster decision:** At 5× the sampled local lag, Polars took 8.567 s / 2689.71 MiB RSS, pandas took 27.834 s / 1785.09 MiB. A full pipeline or real Spark cluster was not benchmarked at these sizes. Cluster migration should be based on measured end-to-end p95, memory headroom, fault recovery and workload skew, not extrapolated years or row counts.

## 5. Submission-critical to-do that cannot be certified from the provided records

1. Publish the exact reviewed revision in a **public GitHub repository**. Check via anonymous HTTPS clone from the actual remote URL, and rerun tests, plan, source validation and public aggregate verification from that clone. Insert the actual URL on page one, export PDF and visually check the page limit again.
2. If the course expects a literal fresh API download→full model/test rerun, provide original snapshot and cache inputs or a legally compliant documented re-download workflow with credentials/settings; current README and evidence cannot certify full clean-room E2E. Do not rescore the locked test merely to strengthen the manuscript.
3. The original historical filing-vintage and supervisory review-cost data are not supplied. Preserve them as explicit limitations, do not fabricate or imply they were measured.
4. Report is currently **reviewed pre-submission draft**, not verified ready-to-submit; the cover placeholder is intentionally unfilled pending actual URL.

## Primary sources independently checked (23 November 2026)

- Official BFT65B assignment/rubric: the user-supplied three-page final examination specification, Sections 2–5.
- [FDIC BankFind API documentation](https://api.fdic.gov/banks/docs/)
- [FDIC Failed Bank List / BankFind Failures help: COST and last reported assets before effective date](https://banks.data.fdic.gov/bankfind-suite/failures/help)
- [FFIEC 031/041 General Instructions: standard 30-/35-day filing deadline, amended reports](https://www.fdic.gov/bank-financial-reports/ffiec-031-041-general-instructions-december-2024.pdf)
- [FDIC Glossary: noncurrent loans/leases](https://www.fdic.gov/analysis/risk-review/2019-risk-review/2019-risk-review-glossary.pdf)
- [VCCI legal-document text of SBV Circular 31/2024/TT-NHNN](https://www.vcci.com.vn/legal-document/31-2024-tt-nhnn)
- [Polars lazy optimizer docs](https://docs.pola.rs/user-guide/lazy/optimizations/)
- [Scikit-learn AP is noninterpolated](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html)
- [Official consolidated Law on Credit Institutions, 143/2026/VBHN-LQ-VPQH, 23 September 2026](https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-143-2026-vbhn-lq-vpqh-470556.htm)
- [2026 amendment Law 23/2026/QH16 effective 1 December 2026](https://congbao.chinhphu.vn/van-ban/luat-so-23-2026-qh16-470457.htm)
- [WTO WT/TPR/S/490, pp. 178–179](https://www.wto.org/english/news_e/news_docs/S490.pdf)
- [Banking Academy Vietnam Banking Sector Report 2025](https://hvnh.edu.vn/nckh/vi/nghien-cuu-chuyen-de/vietnam-banking-sector-report-2025-11002.html)

**Final assessment:** Provisional 86/100 is arithmetically valid and professionally plausible, but not a statistically identifiable grade. The edits improve accuracy and defensibility; they cannot compensate for missing genuine public GitHub verification or observationally unidentified review economics.
