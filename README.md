# FDIC Bank Failure Early Warning — BFT65B

**Final submission release — documentation updated 26 November 2026.** National Economics University, BFT65B final individual report. This source-only repository accompanies the separately submitted 30-page English report. It contains the original scientific producers, pinned protocol, tests, output summaries, and supplementary review evidence. Public HTTPS cloning and the data-free audit were verified on 25 November 2026 for the original release and the documentation revision `050889604e449efa26c7bb44943c58cef8477e54`. A full live-data/model rerun has not been verified. See the separately submitted report for the final audited commit.

## Reproduction levels

|Level|Command / evidence|Status|
|-|-|-|
|A. Data-free source/aggregate checks|`python -B tools/reviewer_check.py --out ../BFT65B_REVIEW_NEW`|Anonymous HTTPS base clone and 14/14 public checks PASS; final release audit recorded separately|
|B. Original snapshot to development features|`python -B run.py continuous --start raw --out ../BFT65B_CONTINUOUS_NEW`|19 and 25 Nov Windows replays: 178/179 byte-identical, zero observed logical mismatches; requires retained raw snapshot and cache|
|C. Original private development policy or grid|`python -B tools/reproduce_development.py --mode policy` (plan); see exact inputs below|25 Nov original-input policy replay PASS; grid/refit not rerun|
|D. Native live-data recipe|`docs/REPRODUCE_REVIEWER.md`, section D|New acquisition may differ; original model guard requires historical bytes; complete fresh-data/model route not verified|
|E. Archived final test|Digest-only lock→claim→audit and aggregate verifier|Original one-time prediction retained, not re-scored|

## Environment map

- Public source/aggregate audit: Python 3.10+; standard library only.
- Historical engineering/data replay: Python 3.13.9; `requirements.txt` (engineering profile).
- Development/model replay: separate Python 3.13.7 environment; `requirements/model-and-spark-observed.txt` (includes scikit-learn and PySpark); Java 17 for Spark.

Do not merge the two scientific profiles: their NumPy/pandas pins differ. Clean installs/import checks passed on 25 November; scientific jobs in the new environments were not rerun.

## A. Quick start (Python standard library)

```sh
python -B tools/reviewer_check.py --out ../BFT65B_REVIEW_NEW
```

Use a new directory outside the repository. This runs 14 checks and verifies every distributed file, 45 original unit tests, 131 protected source pins, S1/E10–E12 and S3 returned-aggregate arithmetic and S4 recovered acquisition manifest and S5 new execution evidence, pilot and development comparator fixtures, and a publication scanner. A PASS means source/aggregate consistency, not live acquisition or scientific rerun. After publishing, clone anonymously (`GIT_TERMINAL_PROMPT=0 git -c credential.helper= clone <PUBLIC_HTTPS_URL>`) and repeat from the clone; record commit, date and Python version outside the repository. Windows convenience: `REVIEW_ON_WINDOWS.cmd`. The command above is valid in Windows PowerShell as well as POSIX shells. For credential-free cloning in PowerShell, set `$env:GIT_TERMINAL_PROMPT = "0"` and use `git -c credential.helper= -c http.extraHeader= clone <PUBLIC_HTTPS_URL>` (replace the placeholder).

## B. Original snapshot replay

Use Python 3.13.9 with `requirements/engineering-recorded.txt` (or the smaller `continuous-data-minimal.txt` for data stages). The root `requirements.txt` points to the recorded engineering profile. Provide original quarterly source files, two source tables, acquisition ledger and checksums, original prepared references and request caches through `config/default.json` or an external input-only config. Run `python -B run.py continuous --start raw --config <INPUT_CONFIG_JSON> --out ../BFT65B_CONTINUOUS_NEW`. See `docs/REPRODUCE_REVIEWER.md` for exact options and paths. Outputs go outside the repository. Missing inputs BLOCK; identity/value violations FAIL; no frozen intermediate fallback. On 19 and 25 November the five stages passed through development; 230,664,115 compared cells / 5,401 non-key column summaries recorded no observed differences. Development Parquet bytes differ (19 Nov d1e566d2…, 25 Nov a7295637…, original d365ce25…), despite observed logical equality under declared tolerance. Cause unknown; do not bypass the exact-byte model guard. This was an AI-assisted review of returned Windows evidence, not third-party raw-file re-execution.

## C. Original development-only replay

Use the separate Python 3.13.7 model profile `requirements/model-and-spark-observed.txt` (recorded model/late observed dependencies, plus Spark 4.3.0; Java 17 external). Do not merge incompatible pandas/NumPy pins. Both clean installations passed on 25 Nov (install, pip check, imports; 24/16 package freezes in `requirements/*-clean-freeze-20261125.txt`). For a new install record `python -m pip freeze`, `python -m pip check`, interpreter version and relevant imports. The optional Windows `REPRODUCE_DEV_POLICY_WINDOWS.cmd` locates hash-matched original files. Alternatively invoke `tools/reproduce_development.py --mode policy --execute` with the original development Parquet, Failures and three development evidence ZIPs; `--mode grid` performs original development grid then policy with the same protected inputs. Exact arguments in `docs/REPRODUCE_REVIEWER.md`. No final-test read/inference, model replacement or threshold change. Original Step05/06 scripts remain present with their frozen guards; current supported adapter does not dispatch them.

## D. Native acquisition and boundaries

`docs/REPRODUCE_REVIEWER.md` lists every native producer from FDIC API through modelling and the necessary artifacts/options. The original scope is 1984Q1–2026Q2 Financials and complete Institutions/Failures. Fresh API totals must be observed anew, and revised data require a new research provenance/protocol; current historical expected counts and byte identities cannot be treated as guarantees for a new snapshot. Full fresh-snapshot acquisition-to-scoring remains unexecuted. Scientific execution inside the new clean venvs was not tested. Do not retune or re-score the frozen test. No data files, row-level scores, fitted artifacts or HTTP cache bodies should be committed.

## Scientific evidence and integrity

* Original protocol: `00_ASSIGNMENT/part5_protocol_freeze.json`; HGB selected by unweighted chronological validation AP, threshold 0.023971438944668057 fixed on development. Exact-quarter source rule and four-quarter purges.
* `evidence/E1_E9_PUBLIC_EVIDENCE_INDEX.md` maps E1–E12; `evidence/verified_archive_aggregates/` contains recovered outputs. S3: `evidence/final_review/README.md`, with original archive-member/released hash ledger. R23 is recovered 17 Nov V2 preprocessing evidence, not a fresh estimator run. S3 Part 5 includes newly replayed development-only bootstrap and fixed-policy known-COST analysis; no test re-inference.
* `provenance/FINAL_REVIEW_SOURCE_SCOPE.md` records historical vs current source hashes. The later oracle compatibility copy has a legacy name; original oracle and DEP-only difference documented in S3. The dormant helper is unused.
* `docs/README_ARCHIVED_20261124.md` is dated historical documentation; historical statuses in other notes are not new claims. Vietnamese launchers and notes are supplementary convenience material.
* Actual all-in review cost and preventable loss are unknown. The 20:1 policy is assumed, not identified by observed costs. A post-lock, development-only staffing benchmark uses [FDIC OIG (2019, EVAL-20-002, p. 11)](https://www.fdicoig.gov/sites/default/files/reports/2022-08/20-002EVAL.pdf) and [BLS May 2019 federal financial-examiner wages](https://www.bls.gov/oes/2019/may/naics4_999100.htm); formulas, the four fixed policies and source links are in `docs/STAFFING_COST_BENCHMARK.md`. Latest-vintage data do not recover historical receipt/amendment history.

## Sources and acknowledgments

Course assignment and starter: NEU BFT65B (2026), optional `fdic_download_starter.py`; initial acquisition used the starter, later code hardened safeguards. FDIC BankFind Suite [https://api.fdic.gov/banks/docs/](https://api.fdic.gov/banks/docs/) and [https://banks.data.fdic.gov/bankfind-suite/bulkData](https://banks.data.fdic.gov/bankfind-suite/bulkData). Polars [https://docs.pola.rs/user-guide/lazy/optimizations/](https://docs.pola.rs/user-guide/lazy/optimizations/), Apache Spark [https://spark.apache.org/docs/latest/sql-performance-tuning.html](https://spark.apache.org/docs/latest/sql-performance-tuning.html), scikit-learn [https://scikit-learn.org/stable/common\_pitfalls.html](https://scikit-learn.org/stable/common_pitfalls.html). Cole \& White (2012), doi:10.1007/s10693-011-0116-9; BCBS supervisory risk assessment and EWS [https://www.bis.org/publ/bcbs\_wp04.pdf](https://www.bis.org/publ/bcbs_wp04.pdf); Basel Core Principles and BCBS 239; FFIEC CDR; Vietnamese law and circulars; WTO WT/TPR/S/490. Full references in the separate report and `docs/CITATIONS_AND_AI.md`. ChatGPT assisted code, drafting and numerical verification; Codex supported code and replay audit; ChatGPT Work, Claude and NotebookLM provided critique. AI-assisted review is not an independent unaided experimental observation.

## S4 and final closeout

The recovered original Financials manifest (170 complete quarters, 1,682,616 rows) and quarterly reconciliation are in `evidence/final_review/part1/recovered_manifest/`. The 170 recorded totals and prepared digest ledger agree with the historical Windows replay. Raw HTTP bodies were not accessed. See `docs/FINAL_CLOSEOUT.md` for optional controlled storage sensitivity, clean-install and publication checks. S5 contains completed storage sensitivity, original-input policy replay, second continuous replay and both clean-install records; see `evidence/final_execution/README.md`.

## Submission URL

https://github.com/phuonglinh15102005-lab/BFT65B-FDIC-Bank-Failure-Early-Warning

Repository publication is complete. Keep the repository public until grades are released. Use a short extraction path (e.g. D:/BFT) and do not run CMD files from inside ZIPs. The private original evidence ZIPs are not part of the public tree.



## 26 November supplemental evidence and sources

S6, AI-assisted Linux feature-stage checks and scaling/concurrency trials: `evidence/feature_supplement_20261126/README.md`. Data-free check: `python -B evidence/feature_supplement_20261126/verify_summary.py`. This verifies returned aggregate hashes and arithmetic, not a raw-data rerun. Scientific sources and the held-out model remain unchanged. The 26 November candidate must be audited again after publication.

- Vietnamese Government Portal, 15 October 2022, SCB special-control announcement: <https://xaydungchinhsach.chinhphu.vn/nhnn-cu-can-bo-gioi-tham-gia-quan-tri-dieu-hanh-ngan-hang-scb-119221016071238476.htm>. Publication and legal effective date must be recorded separately.
- FFIEC CDR public retrieval services: <https://cdr.ffiec.gov/Public/PWS/WebServices/RetrievalService.asmx>. Reporting rosters and submission timestamps do not establish original filing-vintage restoration.
- WTO WT/TPR/S/490, para. 4.119 and Table 4.6, pp. 178–179: <https://www.wto.org/english/news_e/news_docs/S490.pdf#page=178>.
- Viet Nam Law 23/2026/QH16, effective 1 December 2026: <https://congbao.chinhphu.vn/van-ban/luat-so-23-2026-qh16-470457.htm>.
- FDIC OIG EVAL-20-002, printed p. 11: <https://www.fdicoig.gov/sites/default/files/reports/2022-08/20-002EVAL.pdf>; BLS May 2019 federal financial examiners, SOC 13-2061: <https://www.bls.gov/oes/2019/may/naics4_999100.htm>. Direct wages are post-lock scenarios, distinct from the assumed false-review penalty.
- ChatGPT Work supplied S6 scripts and reported execution; ChatGPT verified the returned archive and integrated it. No new model inference.

## S7 — exact development artifact diagnostic (26 November)

The 26 November Windows read-only diagnostic compares the original and 25 November replay: 1,231,631 unique decision keys, all 18 non-key columns exactly equal after key alignment, zero null/NaN/float-bit mismatches. Row order and row-group layout differ; byte SHA still differs. The writer and Arrow schema metadata match. This does not establish the sole cause of byte divergence or full E2E. Original model SHA guards remain unchanged. See `evidence/development_sha_diagnostic_20261126/README.md`; public aggregate check: `python -B evidence/development_sha_diagnostic_20261126/verify_s7.py`.
