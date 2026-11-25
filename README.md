# FDIC Bank Failure Early Warning — BFT65B

**26 November 2026 final submission candidate.** National Economics University, BFT65B final individual report. This source-only repository accompanies the separately submitted 30-page English report. It contains the original scientific producers, pinned protocol, tests, output summaries, and supplementary review evidence. It is not a claim that public GitHub access or a complete live-data/model rerun has already been verified.

## Reproduction levels

|Level|Command / evidence|Status|
|-|-|-|
|A. Data-free source/aggregate checks|`python -B tools/reviewer\_check.py --out ../BFT65B\_REVIEW\_NEW`|Local clone audit; anonymous remote clone pending|
|B. Original snapshot to development features|`python -B run.py continuous --start raw --out ../BFT65B\_CONTINUOUS\_NEW`|19 and 25 Nov Windows replays: 178/179 byte-identical, zero observed logical mismatches; requires retained raw snapshot and cache|
|C. Original private development policy or grid|`python -B tools/reproduce\_development.py --mode policy` (plan); see exact inputs below|25 Nov original-input policy replay PASS; grid/refit not rerun|
|D. Native live-data recipe|`docs/REPRODUCE\_REVIEWER.md`, section D|New acquisition may differ; original model guard requires historical bytes; complete fresh-data/model route not verified|
|E. Archived final test|Digest-only lock→claim→audit and aggregate verifier|Original one-time prediction retained, not re-scored|

## A. Quick start (Python standard library)

```sh
python -B tools/reviewer\_check.py --out ../BFT65B\_REVIEW\_NEW
```

Use a new directory outside the repository. This runs 14 checks and verifies every distributed file, 45 original unit tests, 131 protected source pins, S1/E10–E12 and S3 returned-aggregate arithmetic and S4 recovered acquisition manifest and S5 new execution evidence, pilot and development comparator fixtures, and a publication scanner. A PASS means source/aggregate consistency, not live acquisition or scientific rerun. After publishing, clone anonymously (`GIT\_TERMINAL\_PROMPT=0 git -c credential.helper= clone <PUBLIC\_HTTPS\_URL>`) and repeat from the clone; record commit, date and Python version outside the repository. Windows convenience: `REVIEW\_ON\_WINDOWS.cmd`.

## B. Original snapshot replay

Use Python 3.13.9 with `requirements/engineering-recorded.txt` (or the smaller `continuous-data-minimal.txt` for data stages). The root `requirements.txt` points to the recorded engineering profile. Provide original quarterly source files, two source tables, acquisition ledger and checksums, original prepared references and request caches through `config/default.json` or an external input-only config. Run `python -B run.py continuous --start raw --config <INPUT\_CONFIG\_JSON> --out ../BFT65B\_CONTINUOUS\_NEW`. See `docs/REPRODUCE\_REVIEWER.md` for exact options and paths. Outputs go outside the repository. Missing inputs BLOCK; identity/value violations FAIL; no frozen intermediate fallback. On 19 and 25 November the five stages passed through development; 230,664,115 compared cells / 5,401 non-key column summaries recorded no observed differences. Development Parquet bytes differ (19 Nov d1e566d2…, 25 Nov a7295637…, original d365ce25…), despite observed logical equality under declared tolerance. Cause unknown; do not bypass the exact-byte model guard. This was an AI-assisted review of returned Windows evidence, not third-party raw-file re-execution.

## C. Original development-only replay

Use the separate Python 3.13.7 model profile `requirements/model-and-spark-observed.txt` (recorded model/late observed dependencies, plus Spark 4.3.0; Java 17 external). Do not merge incompatible pandas/NumPy pins. Both clean installations passed on 25 Nov (install, pip check, imports; 24/16 package freezes in `requirements/\*-clean-freeze-20261125.txt`). For a new install record `python -m pip freeze`, `python -m pip check`, interpreter version and relevant imports. The optional Windows `REPRODUCE\_DEV\_POLICY\_WINDOWS.cmd` locates hash-matched original files. Alternatively invoke `tools/reproduce\_development.py --mode policy --execute` with the original development Parquet, Failures and three development evidence ZIPs; `--mode grid` performs original development grid then policy with the same protected inputs. Exact arguments in `docs/REPRODUCE\_REVIEWER.md`. No final-test read/inference, model replacement or threshold change. Original Step05/06 scripts remain present with their frozen guards; current supported adapter does not dispatch them.

## D. Native acquisition and boundaries

`docs/REPRODUCE\_REVIEWER.md` lists every native producer from FDIC API through modelling and the necessary artifacts/options. The original scope is 1984Q1–2026Q2 Financials and complete Institutions/Failures. Fresh API totals must be observed anew, and revised data require a new research provenance/protocol; current historical expected counts and byte identities cannot be treated as guarantees for a new snapshot. Full fresh-snapshot acquisition-to-scoring remains unexecuted. Scientific execution inside the new clean venvs was not tested. Do not retune or re-score the frozen test. No data files, row-level scores, fitted artifacts or HTTP cache bodies should be committed.

## Scientific evidence and integrity

* Original protocol: `00\_ASSIGNMENT/part5\_protocol\_freeze.json`; HGB selected by unweighted chronological validation AP, threshold 0.023971438944668057 fixed on development. Exact-quarter source rule and four-quarter purges.
* `evidence/E1\_E9\_PUBLIC\_EVIDENCE\_INDEX.md` maps E1–E12; `evidence/verified\_archive\_aggregates/` contains recovered outputs. S3: `evidence/final\_review/README.md`, with original archive-member/released hash ledger. R23 is recovered 17 Nov V2 preprocessing evidence, not a fresh estimator run. S3 Part 5 includes newly replayed development-only bootstrap and fixed-policy known-COST analysis; no test re-inference.
* `provenance/FINAL\_REVIEW\_SOURCE\_SCOPE.md` records historical vs current source hashes. The later oracle compatibility copy has a legacy name; original oracle and DEP-only difference documented in S3. The dormant helper is unused.
* `docs/README\_ARCHIVED\_20261124.md` is dated historical documentation; historical statuses in other notes are not new claims. Vietnamese launchers and notes are supplementary convenience material.
* Actual per-review cost and preventable loss are unknown. The 20:1 policy is assumed, not identified by observed costs. Latest-vintage data do not recover historical receipt/amendment history.

## Sources and acknowledgments

Course assignment and starter: NEU BFT65B (2026), optional `fdic\_download\_starter.py`; initial acquisition used the starter, later code hardened safeguards. FDIC BankFind Suite [https://api.fdic.gov/banks/docs/](https://api.fdic.gov/banks/docs/) and [https://banks.data.fdic.gov/bankfind-suite/bulkData](https://banks.data.fdic.gov/bankfind-suite/bulkData). Polars [https://docs.pola.rs/user-guide/lazy/optimizations/](https://docs.pola.rs/user-guide/lazy/optimizations/), Apache Spark [https://spark.apache.org/docs/latest/sql-performance-tuning.html](https://spark.apache.org/docs/latest/sql-performance-tuning.html), scikit-learn [https://scikit-learn.org/stable/common\_pitfalls.html](https://scikit-learn.org/stable/common_pitfalls.html). Cole \& White (2012), doi:10.1007/s10693-011-0116-9; BCBS supervisory risk assessment and EWS [https://www.bis.org/publ/bcbs\_wp04.pdf](https://www.bis.org/publ/bcbs_wp04.pdf); Basel Core Principles and BCBS 239; FFIEC CDR; Vietnamese law and circulars; WTO WT/TPR/S/490. Full references in the separate report and `docs/CITATIONS\_AND\_AI.md`. ChatGPT assisted code, drafting and numerical verification; Codex supported code and replay audit; ChatGPT Work, Claude and NotebookLM provided critique. AI-assisted review is not an independent unaided experimental observation.

## S4 and final closeout

The recovered original Financials manifest (170 complete quarters, 1,682,616 rows) and quarterly reconciliation are in `evidence/final\_review/part1/recovered\_manifest/`. The 170 recorded totals and prepared digest ledger agree with the historical Windows replay. Raw HTTP bodies were not accessed. See `docs/FINAL\_CLOSEOUT.md` for optional controlled storage sensitivity, clean-install and publication checks. S5 contains completed storage sensitivity, original-input policy replay, second continuous replay and both clean-install records; see `evidence/final\_execution/README.md`.

## Submission URL

https://github.com/phuonglinh15102005-lab/BFT65B-FDIC-Bank-Failure-Early-Warning.git

Publication remains an owner action. Use a short extraction path (e.g. D:/BFT) and do not run CMD files from inside ZIPs. The private original evidence ZIPs are not part of the public tree.

