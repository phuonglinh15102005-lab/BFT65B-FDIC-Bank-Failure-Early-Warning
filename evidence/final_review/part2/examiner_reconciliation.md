# BFT65B Part 2 — original evidence and additional aggregate reconciliation

Scope: the 24 November 2026 SUBMISSION_CANDIDATE report, pages 3–5 and Appendix E. This is supplemental evidence for the examiner, not a revised submission or a request to credit proposed edits. No model was fitted or final test score recomputed.

## 1. Reopened evidence and executed checks

The four original historical review archives match the previously recorded SHA-256 identities in `BFT65B_Part2_Verification/source_evidence_hashes.json`:

| Archive | SHA-256 |
|---|---|
| review_bundle.zip | e1db4e28456b8154048f6b67d1d5048ee4f836ea60d31817cdbf1d786d0d57ab |
| part2_review_bundle.zip | e732115381dc14c82997ac70c573c45f2ee3c3b15d27b4cc01d157cc2f99d357 |
| part2_clean_review_bundle.zip | 09efb2de4574f3abc278aa83ec66d8369d26330258518a7e1963cf810471c395 |
| part2_preflight_review_bundle.zip | f57ac844e9b979426c08e22383e0e79d0829440b55d052ff2af52b13b93f9d24 |

Reexecuted today: `independent_part2_review.py` on the original 2A/2B/2C ZIPs: 20/20 PASS; `review_preflight_evidence.py` on 2A/2C/2D ZIPs: 18/18 PASS. They check shared evidence, not independent sources. Historical 2D Windows preflight on full saved Parquets recorded 24 checks PASS, full output bytes read and retained value equality checked. The actual full financial Parquets are not available in this review. Earlier 29 consistency checks and these later checks overlap; do not add them as independent tests.

Historical `step2c_summary.json`, 2026-11-09T03:48:47.682882+00:00, Python 3.13.9, Polars 2.1.0:
- 1,682,616 source rows, 24,064 CERTs; 1,669,802 clean rows, 23,849 CERTs, 170 quarters.
- 11,598 scope exceptions all meet INSFDIC=0, INSAGNT1=NONE, BKCLASS=NC; zero unresolved scope exceptions; no overlap with post-exit rows. 1,211 at/after failure risk stop and 5 at/after other exit. No finite values changed, imputed or clipped in 2C.
- 1,629,398 lag-1 decisions, 23,651 CERTs; 1,605,882 lag-2 decisions. Original filing-vintage PIT flag false.

## 2. D1 — new key-matched lag comparison (executed)

`lag_key_comparison.py` reconstructs source keys from 2A first/last/count coverage and targeted 2B metadata for internal gaps, subtracts every 2C logged exclusion, applies the reconciled registry risk-stop and eligibility bounds, and intersects decision sets per CERT. All published source, clean and lag census totals reproduced. No financial values or score ledger required. These are registry-based pre-adjudication opportunities, **not** the final binary labels or a model comparison.

| Measure | Lag 1 | Lag 2 |
|---|---:|---:|
| Decision keys | 1,629,398 | 1,605,882 |
| Distinct CERTs | 23,651 | 23,394 |
| Registry-defined positive-window opportunities | 11,101 | 11,005 |
| CERTs with >=1 such opportunity | 2,811 | 2,791 |
| Development candidate keys | 1,232,375 | 1,208,974 |
| Development positive-window opportunities before adjudication | 9,319 | 9,223 |
| Development CERTs with >=1 such opportunity | 2,429 | 2,409 |

Key intersection: 1,605,722 common; 23,676 lag-1-only; 160 lag-2-only. Lag-1-only keys lack a clean t-2 report: 23,641 pre-first-source-report, 26 internal gaps, 9 source exclusions. Lag-2-only keys lack a clean t-1 report: 94 after last source report, 27 internal gaps, 39 source exclusions. Positive opportunity key intersection: 10,995 shared, 106 lag-1-only, 10 lag-2-only. Of failure CERTs with any opportunity, 2,791 shared, 20 lag-1-only, 0 lag-2-only.

Separate exclusive **source-row** accounting (not key-set overlap): beyond 2025Q2 21,700 -> 26,171 (+4,471); at/after risk stop 18,673 -> 37,687 (+19,014); beyond eligibility end 31 -> 62 (+31). The increments sum to 23,516. Distinguish these two views: shifting source rows later changes right-boundary/exit eligibility, whereas comparing decision keys at the same t chiefly exposes first-report boundaries. Neither establishes actual filing-date robustness. No AP impact measured. Do not use these post-lock descriptive checks to change the registered model or threshold.

## 3. D2 — period-specific quality diagnostics, recomputed from original ledgers

| Field / flag | 1984–1989 (417,921 reports) | 1990–2026Q2 (1,251,881 reports) |
|---|---:|---:|
| RBCRWAJ zero | 417,921 (100%) | 47,561 (3.799%) |
| RBC1AAJ zero | 75,137 (17.979%) | 2,413 (0.193%) |
| NTLNLS null | 75,653 (18.102%) | 2,357 (0.188%) |
| NAASSET null | 76,865 (18.392%) | 0 (0%) |

Sources: `ratio_diagnostics_by_quarter.csv`, `missingness_after_by_quarter.csv`. Of 465,482 RBCRWAJ zeros, 89.78% are pre-1990; of 77,550 RBC1AAJ zeros, 96.89% are pre-1990. 77,550 is a denominator of zero observations across the full history, NOT the number of pre-1990 reports. The 1989 adoption of risk-based capital standards offers a plausible context (FDIC press release PR-53-89, https://archive.fdic.gov/view/fdic/10155); zero is not proven synonymous with not reported. Keep recorded zeros intact; both regulatory capital fields are absent from the registered predictor whitelist. The original 9 Nov verification README already explicitly documented the all-zero early RBCRWAJ regime. This finding was omitted from the compressed final report, not from the original audit.

## 4. D3 — accounting time conventions

Saved FDIC Financials YAML defines ROA as annualized net income relative to average assets (percent), ROE as annualized net income relative to average equity (percent), and distinguishes NETINC from NETINCQ (quarterly) and NTLNLS from NTLNLSQ. FDIC BankFind methodology describes deriving quarterly income/expense from cumulative amounts: https://banks.data.fdic.gov/bankfind-suite/help?helpTopic=disclaimers-and-methodologies. FFIEC Schedule RI uses calendar YTD income/expenses, and RI-B uses calendar YTD charge-offs/recoveries; see https://www.fdic.gov/bank-financial-reports/051-ri-b-charge-offs-and-recoveries-loans-and-leases-and-changes-allowances . Historical mapping for every reporting regime and TFR field is not established merely from modern guidance. Count of 169,702 negative NETINC cells is a sign count of recorded amounts, not a quarterly loss count. The model uses reported ROA and NIMY (percent), not NETINC, ROE, INTINC, EINTEXP, NONII, NONIX, ELNATR or NTLNLS. No YTD differencing or flow-to-stock ratio using these excluded fields is performed. The model's 15 feature expressions are in `part4_step01_reference_UNCHANGED.py`. Qualify the period convention without retroactively altering the input data or model.

## 5. D4/D5 — actual automated quality outputs, including soft flags

Original `financial_soft_checks.csv` (2D):

| Check | Eligible rows | Flagged rows |
|---|---:|---:|
| DEPDOM > DEP | 1,669,801 | 0 |
| LNLSNET > LNLSGR | 1,669,801 | 15 |
| ASSET <= 0 | 1,669,802 | 0 |
| DEP <= 0 | 1,669,801 | 1,777 |
| LNLSGR <= 0 | 1,669,801 | 8,691 |
| EQ <= 0 | 1,666,705 | 14,592 |

Pairwise tolerance: 1e-6 + 1e-9 * max(abs(a),abs(b)), in USD thousands. Nulls excluded from eligible denominator; flags overlap. 15 net/gross loan flags are review candidates, not confirmed erroneous observations. DEP flags are zero, LNLSGR flags include 8,660 zeros + 31 negatives; EQ flags include 21 zeros + 14,571 negatives. Preserve raw values, guard applicable denominators, do not automatically delete rows. ROA abs >100%: 207/1,669,802 (0.0124%); ROE abs >100%: 11,553/1,669,802 (0.6919% of all clean reports, or 0.6988% of nonmissing ROE). ROE excluded from model; finite ROA retained, no full-sample clipping, final specification unclipped. A large value is not proof of invalid accounting. Negative stocks: 822 cells in 790 reports from 290 CERTs. 169,702 negative NETINC, 14,571 negative EQ; source `numeric_profile_after.csv`.

Automated CSV/JSON outputs are a valid machine-readable data-quality report; the rubric does not prescribe a single rendered report. The final synthesis should better reference them. 2A: 235 CERTs (10,996 rows) initially lack Institutions metadata; 32 CERTs have internal gaps; three repeated-failure CERTs; 273 failure events with reports on/after event; five banks with reports after recorded inactive date; 191 blank STNAME cleaned. 2B: 538 targeted banks; 59,901 unique History records, 20,043 supplementary metadata rows; 51 checked filtered API requests. 2C: 25 clean-panel CERTs with internal gaps; 19 History-before-register conflicts (1–22 days), 4 History-overrides-snapshot-date flags; 354 reason-coded fallback CERTs, 109 unresolved/unobserved exits. No automatic deletion merely because a bank has missing Institutions metadata or an internal gap. The original audit classified reasons, verified the population and preserved the audit-only ledgers.

## 6. D6/D7 — exit rules and scope

`02c_finalize_panel.py::build_registry` selects first dated RESTYPE=FAILURE from the **Failures register**. A prior terminal History record may shorten the risk spell, without replacing the register target date. 810 (acquirer) and 225 (partial transaction) are not terminal. Terminal codes 221–224 identify merger/reorganization; 240 voluntary closure; 213/216/217 assisted/resolution; 211/215/230/235/260 adverse without a matched failure. Mixed/unresolved cases require adjudication. Historical 2C initially specified outcome policy for Part 4, not final labels. The final V2 `part4_v2_relabel_asof_gate.py` restores competing-exit negatives only for three confirmed nonfailure classes (merger/reorganization, assisted/resolution, voluntary closure), with conflict/status precedence from original Step01. This refers to absence of the specified first registered FAILURE target, not absence of distress. Unmatched adverse outcomes remain unresolved where they interrupt follow-up. Development restored counts: 46,839 merger/reorganization, 2,160 assisted/resolution, 973 voluntary closure = 49,972. 317 adverse unresolved; 90 insufficient follow-up; 337 date conflicts. These are decision counts, not bank counts. 354 snapshot fallback registry banks = 204 merger/reorganization + 140 assisted/resolution + 10 adverse. This is across the entire source bank registry, not the final modeled cohort. Actual per-class final-test labeled counts not asserted here.

## 7. Proposed minimal report changes (not yet in the submitted report)

- §2.1.1: state that all 11,598 scope exceptions satisfy the triple and none remains unresolved; missing metadata alone is not a deletion criterion.
- §2.1.2: replace net-count-only discussion with key intersection, source-row boundary decomposition and positive-window opportunity sensitivity. Explicitly separate cohort coverage from prediction performance and filing vintages.
- §2.2 / Appendix E: add early zero/missing regimes, reporting-period conventions, accounting soft-flag counts and disposition of ROA/ROE; compress CBLR repetition rather than remove evidence.
- §2.3: first FAILURE register event defines target; History determines earlier risk stop and nonfailure exits; summarize codes, fallback counts and V2 competing-negative rationale. Do not interpret a resolved assistance exit as a healthy institution.
- Add archived aggregate tables and verifier outputs to public evidence index after privacy review. Do not publish original record-level audit ZIPs. Keep frozen model, threshold and test unchanged.
