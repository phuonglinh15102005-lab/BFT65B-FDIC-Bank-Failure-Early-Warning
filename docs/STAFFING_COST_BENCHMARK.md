# Development-only external staffing cost benchmark — post-lock

This supplement uses archived policy aggregates, not new model scores. The registered HGB, cutoff 0.023971438944668057, 20:1 false-review/missed-event objective and final test remain unchanged. The original USD 523,313.12 false-review penalty was assumed at 5% of the positive development median FDIC COST. It is not an observed review fee. External wage scenarios below are a distinct analysis and did not determine the locked threshold.

## Primary source inputs

- FDIC Office of Inspector General, *Offsite Reviews of 1- and 2-Rated Institutions*, EVAL-20-002 (December 2019), printed p. 11: <https://www.fdicoig.gov/sites/default/files/reports/2022-08/20-002EVAL.pdf>. Of 32 interviewed case managers, six reported an average first-time review of four hours or less; five said a first-time review could take 12 hours. These are two illustrative durations, not a sample mean, percentile interval or bounds for all reviews. A first annual model alert need not be a first-time FDIC review.
- U.S. Bureau of Labor Statistics, *May 2019 OES, Federal Executive Branch* (NAICS 999100, SOC 13-2061), mean hourly wage of financial examiners USD 61.76: <https://www.bls.gov/oes/2019/may/naics4_999100.htm>. This is an occupational mean, not FDIC-specific examiner compensation.
- Source ledger: `evidence/final_execution/policy/development_threshold_scenarios.csv`, columns `ratio`, `cert_year_alerts`, `detected_failure_certs`, `fp_cert_years`, `missed_failure_certs`. Input SHA-256: `1fa674e44e9278a219edea2a230ba3cf357b83226517ab2e3c0de308f48d0366`. 1,290 distinct OOF failure CERTs. All annual-first reviews consume time, including true reviews.

## Reproducible arithmetic

For each scenario, c = hours × 61.76 = USD 247.04 (4 hours) or USD 741.12 (12 hours). Direct wage bill = c × total reviews R. All amounts are nominal 2019 USD; benefits, overhead, escalation and opportunity costs are excluded. The same unit wage is applied to historical review counts as an illustrative standard, not an estimate of actual historical payroll.

| Policy | Total reviews | Detected failures | False reviews | 4h wages (USD) | 12h wages (USD) |
|---|---:|---:|---:|---:|---:|
| 5:1 | 1,575 | 568 | 963 | 389,088.00 | 1,167,264.00 |
| 10:1 | 2,935 | 717 | 2,166 | 725,062.40 | 2,175,187.20 |
| 20:1 | 5,034 | 854 | 4,124 | 1,243,599.36 | 3,730,798.08 |
| 50:1 | 6,092 | 894 | 5,147 | 1,504,967.68 | 4,514,903.04 |

For two policies a,b, marginal wage cost per net detection = c × (R_b−R_a)/(D_b−D_a). Net gains do not imply nested event sets.

| Policy change | Extra total reviews | Net extra detections | Reviews per net detection | 4h USD/net detection | 12h USD/net detection |
|---|---:|---:|---:|---:|---:|
| 5 to 10 | 1,360 | 149 | 9.13 | 2,254.86 | 6,764.59 |
| 10 to 20 | 2,099 | 137 | 15.32 | 3,784.94 | 11,354.82 |
| 20 to 50 | 1,058 | 40 | 26.45 | 6,534.21 | 19,602.62 |

An additional illustrative all-review objective is L = cR + b(1290−D), with common effective missed-event consequence b expressed in the same units as c. Among these four fixed policies, the locked 20:1 policy minimizes L for b/c between 15.321168 and 26.450000 (ties at endpoints). Thus conditional effective consequence ranges are USD 3,784.94–6,534.21 for 4h and USD 11,354.82–19,602.62 for 12h. This is not the original false-review-only objective (whose pairwise interval is about 14.29–25.58). It identifies a conditional trade-off, not a new cutoff or an estimated optimal ratio. No preventable-loss fraction is observed. Mixed-vintage nominal FDIC COST is not directly compared with 2019 wages to claim economic benefit. No final-test records or scores were used for these calculations.

## How to reproduce the numbers

Read the four archived rows, compute `R * hours * 61.76` and `(R_b-R_a)*hours*61.76/(D_b-D_a)` for the three adjacent policy pairs. Exact Decimal arithmetic was used, then rounded to cents here. The original research and its protected artifacts remain unchanged. See the separately submitted report, Section 5.2.1 and Appendix J.3.

At the locked development policy, 5,034 annual-first reviews consist of 4,124 false reviews and 910 true reviews, covering 854 distinct failed banks. All reviews consume labor; the marginal cost unit is incremental direct wage per net additional detected event.
