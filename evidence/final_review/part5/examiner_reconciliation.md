# Part 5 — Supplementary examiner evidence (25 November 2026)

Scope: current submission candidate dated 24 November, official Part 5 rubric (15 points: time-ordered imbalanced validation and metrics; data-based threshold; single test; MLlib demo, with simple baseline comparison). The subweights 3/4/4/2.5/1.5 are examiner-defined, not official. No report edit, new model fit, new threshold search, test cohort access or model inference was performed. Development OOF score arrays were read locally; individual rows are NOT included in this supplement. Test numbers below are from already released aggregates and a retained missed-event diagnostic, not newly scored test data.

## 1. Newly executed numerical verification
Source: `BFT65B_FINAL_Parts1-5_Curated.zip`, archive SHA-256 `81276c603b3139e5d952e03a2c2806208cd3972d313876995ac6eb4553cf649c`. All 21 files in the existing `completed_analyses/development_ci/INPUT_HASHES.json` matched SHA-256 before the paired development replay. Producer `paired_ci.py` used the existing fixed seed 20261117 and 1,500 replicates. 1,500/1,500 valid, 100 weighted-AP tie/zero-multiplicity synthetic checks passed; pairing and duplicate-rejection tests passed. The inputs were unchanged. Environment differs from original Windows; numerical agreement, not cross-platform byte identity, is claimed.

| Comparison | Point difference | 95% conditional percentile CI |
|---|---:|---:|
| HGB − registered LR | 0.0460049133 | [0.0325421697, 0.0611575412] |
| HGB − equity-only | 0.1142986271 | [0.0912786546, 0.1382869745] |

Pooled HGB AP = 0.2846112211973563. Registered LR on fold 1: AP 0.3350101008454883, ROC-AUC 0.9080002686396207, Brier 0.01902531536727905. These match report pp.14 and 17. The paired intervals condition on selected archived candidates and shared CERT multiplicities; not selection-adjusted, not macro-block confidence, not recovery of the original historical bootstrap. See DEV_CI_RESULT.json and DEV_CI_PAIRED_DRAWS.csv.

## 2. Code defect alleged by examiner: not reproduced
The exact Step03 producer in the public candidate and curated historical archive is byte-identical. Python AST finds nine `important_qualifications` list entries. The original Step03 audit contains the same nine strings in the same order (exact equality). The review pack Markdown also shows commas. Thus the alleged missing comma is unsupported. Do not edit historical producer. See STEP03_TEXT_CHECK.json.

## 3. Workload: arithmetic confirmed, cause qualified
| Group | Quarters | First reviews | False reviews | Median/quarter | Mean/quarter | Maximum |
|---|---:|---:|---:|---:|---:|---:|
| Q1 | 16 | 2442 | 2122 | 42.5 | 152.625 | 765 |
| Q2–Q4 | 46 | 736 | 722 | 7.5 | 16.0 | 99 |
| Q1 excluding 2010Q1 | 15 | 1677 | 1494 | 42 | 111.8 | 594 |
Q1 accounts for 76.84% of first reviews and 74.61% of false reviews. The annual-first rule permits renewed alerts each calendar year; start of test and crisis-era volume also matter. The data do not identify the causal contribution of each. Overall median 13 is correct but masks seasonality. Even excluding the first test quarter, Q1 median remains 42. No new test policy was evaluated. Lead-time audit records median 2 and IQR 1–3. Archived 15 missed-event diagnostic contains 14 with no qualifying crossing and one with a positive-window crossing but no timely annual-first detection. The latter is consistent with previously reported annual suppression; the exact earlier review was not independently re-read from individual alert rows here.

## 4. The central rubric weakness: actual review costs remain unknown
The exam specifically requires costs estimated from data. FDIC resolution COST is data-derived, but false-review fee 0.05m and missed-event penalty m imply r=20 for every positive median m. Therefore the USD scale cancels, and the selected threshold is conditional on an assumed cost ratio, not an empirically identified operating optimum. The current report already explicitly states this (p.14); clearer disclosure alone cannot close this substantive limitation. Uniform missed-event penalties are legitimate for an event-count mandate, not for loss-weighted optimization. True reviews consume capacity too, while J penalizes false reviews only.

NEW fixed-policy development diagnostic: use the exact archived OOF scores and four exact archived cutoffs; independently select earliest crossing per CERT-year and join event detections with the archived development event COST ledger. All four false-review, detection and total-review counts matched existing policy ledger. There are 1,247 positive-COST events of 1,290; 43 missing/nonpositive COST cases are excluded from the known-COST denominator, not assigned zero. Total known COST = 102.575804 billion USD.

| Registered scenario r | Reviews | Detected events | Detected events with valid COST | Known COST detected (USD bn) | Known COST coverage | Hypothetical break-even avoidability, all reviews charged at 0.05m |
|---|---:|---:|---:|---:|---:|---:|
| 5 | 1575 | 568 | 558 | 28.8143 | 28.09% | 2.860% |
| 10 | 2935 | 717 | 706 | 41.3532 | 40.31% | 3.714% |
| 20 (locked) | 5034 | 854 | 839 | 64.3357 | 62.72% | 4.095% |
| 50 | 6092 | 894 | 875 | 66.2042 | 64.54% | 4.815% |
The r=20 to r=50 transition adds 1,058 reviews but only USD 1.869bn NET known detected resolution COST, whereas r=10 to r=20 adds 2,099 reviews and USD 22.983bn net known COST. Different annual-first alert identities can change; these are net gains, not nested event sets. This is empirical severity coverage, not preventable loss or realized savings, and no new cutoff was selected. The hypothetical all-review fee sensitivity uses the same unobserved fee, so it is not a new cost estimate. For the locked test only, using already reported totals, charging all 3,178 reviews instead of only 2,844 false reviews raises the hypothetical break-even fraction from 6.18% to 6.91%. No test-based policy selection.

## 5. Other examiner findings
- Validation windows cover 24.731% of development rows and 39.833% of positive rows; no matching sparse 2014–2025 regime. A temporal purge and ex ante metric are justified; the assignment does not require full OOF coverage. Top HGB candidates differ in mean AP by 0.001789 and 0.003448, small relative to across-fold variability. This does not establish that differences are statistically indistinguishable (fold regimes are not IID replicates). No change to locked selection.
- Step06B1 verifies lock/model hashes before accessing labels, does not load model, and constructs/audits the held-out cohort. Step06B2 verifies label alignment before exclusive inference claim. Label access before claim is not before model lock; describe openly. One inference call, output-location-scoped guard. No baseline was scored on final test; this is not an explicit rubric violation. Baseline comparison is on development; held-out AP versus prevalence and Brier versus constant development rate are contextual benchmarks, not held-out LR/HGB comparison.
- MLlib one-feature logistic demo: identical AP/AUC expected when rankings are monotonic in the same transformed feature with matching sign and ties, not a universal theorem that one-feature models must match. The stronger 23-column experiment has AP delta 0.0000104812 and max absolute probability difference 0.0000965021 between matched tight objectives; compared to registered LR, AP delta 0.0018223 and max probability diff 0.0279785. Report distinguishes these. Rubric asks short demo, not HGB replication or identical solver solutions.
- Test bootstrap: original historical CI producer remains unrecovered. The recorded new 1500-draw posthoc procedure on saved scores is not original historical CI recovery. The repo additionally contains a separate same-spec grouped-weight reproducer (`reproduce_saved_posthoc.py`), not merely two calls to the producer. Its execution result was not recovered in this turn, so do not claim a new independent test bootstrap replay. The newly executed paired-development replay above is separately verified. Clarify p.17 provenance and dependence on macro shocks/model selection.

## 6. Proposed report edits (not yet applied; no score credit for proposals)
1. p.13: "The three two-year validation windows represent 24.7% of development decisions and 39.8% of positive decisions; none has incidence as low as the later sparse test regime. The top-three HGB mean-AP gaps (0.0018–0.0035) are small relative to cross-regime variation, so the frozen winner is a protocol decision rather than proof of universal superiority."
2. p.14: retain registered loss and conditional optimum, explicitly state the median cancels. Add four fixed-policy severity coverage values (28.09%, 40.31%, 62.72%, 64.54%), with known-COST denominator, and marginal trade-off. Do not assert cost-weighted optimality.
3. p.15: "The locked model preceded the Step06B1 label-integrity audit; test labels were also checked before the one-use inference claim, but were not used for model, feature or threshold selection."
4. p.15: "Q1 contains 76.8% of reviews (74.6% false); median Q1 workload was 42.5 versus 7.5 in other quarters. Annual reset, start-of-test and crisis-era workload jointly limit interpretation of the peak."
5. p.16: include 62.72% development known-COST coverage against 66.2% event recall, and distinguish false-only versus all-review capacity/cost assumptions. No causal savings claim.
6. p.17: "The test intervals are from the separately documented new post-lock CERT-cluster bootstrap (1,500 draws, seed 20261117), not recovery of the original historical bootstrap. The paired development intervals were replayed from 21 hash-verified inputs; all 1,500 draws were valid and rounded intervals matched. Neither method captures shared macro shocks or selection uncertainty."
7. p.16–17: state one-feature demo's limited ranking test and the stronger matched-objective 23-column result.

Remaining material limitation: obtain defensible actual per-review time and costs or explicitly report partial cost identification, without changing the already scored model/cutoff. A supervisor pilot is a proposal, not data already observed. No test baseline scoring, new threshold, feature selection, or model refit is recommended. Reproducibility and public URL are scored separately.
