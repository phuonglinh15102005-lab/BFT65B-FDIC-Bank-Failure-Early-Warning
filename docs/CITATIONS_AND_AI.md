> Current closeout: see the root README and REPRODUCTION_VERIFICATION_REPORT.md. The earlier checkpoint history below does not establish continuous real-data execution.

# Sources, citations and AI assistance

Finalized release date: **19 November 2026** (prepared 18–19 November).

This file records the sources relevant to the code release. Preserve the original project's more specific field, method, code and report citations. A documentation link is a reference, not proof that the live page matches the historical software version or that every source was newly reviewed during this release.

## Assignment and optimization direction

- **Course assignment supplied by the student:** *BFT65B — Big Data Analytics in Finance, Final Examination — Individual Research Report: A Big-Data Pipeline for Bank Failure Early Warning*, National Economics University. The original assignment is authoritative for scope, rubric, required tools, the temporal label, single final-test use, repository requirements and academic integrity. Pages 2–3 specify the Parts 1–5 tasks, reproducibility, submission and grading requirements.
- **Instructor clarification as relayed by the user on 18 November 2026:** one clearly justified optimization direction is permitted. The project uses the highest unweighted mean Average Precision over the original chronological validation folds, followed by a separate development-only cost-sensitive alarm threshold selection. This release records the user's clarification; it does not claim to have independently authenticated a separate instructor communication. It does not amend or backdate the frozen protocol.
- **Original project code and archived evidence supplied by the student:** retain attribution for course starter code and any other adopted code. Newly added workflow code does not make the original source authorship disappear. Do not invent author names, student IDs, download dates or repository URLs.

## FDIC data and definitions

- FDIC BankFind Suite API and field documentation: <https://api.fdic.gov/banks/docs/>.
- FDIC BankFind Suite bulk-data portal: <https://banks.data.fdic.gov/bankfind-suite/bulkData>.

The shared assignment scope is Financials 1984Q1–2026Q2 and the complete Institutions and Failures tables. Record the actual acquisition method, snapshot dates, selected fields, units and completeness evidence from the archived acquisition logs. The present release does not claim to download that historical snapshot again. Distinguish FAILURE from ASSISTANCE transactions, institution records from bank-quarter observations, amounts in thousands of USD from ratios reported in percent, and resolution COST from causal avoided loss.

## Software and implementation documentation

Use the actual runtime versions recorded with each execution. The following official documentation describes the relevant libraries; a live `stable` or `latest` URL is not a historical environment lock.

| Component | Relevant use | Official reference |
|---|---|---|
| Python | CLI, paths, hashing and execution records | <https://docs.python.org/3/> |
| NumPy | Arrays and numerical calculations | <https://numpy.org/doc/> |
| pandas | Panel processing and reference comparisons | <https://pandas.pydata.org/docs/> |
| Polars | Scalable transformations, lazy execution and plans | <https://docs.pola.rs/> |
| Apache Arrow/PyArrow | Parquet schemas, serialization and data IO | <https://arrow.apache.org/docs/python/> |
| scikit-learn | Pipelines, HGB, logistic baseline and validation metrics | <https://scikit-learn.org/stable/> |
| Apache Spark SQL and MLlib | SQL transformation parity and the archived MLlib demonstration | <https://spark.apache.org/docs/latest/> |
| joblib | Original model-artifact provenance and runtime utilities | <https://joblib.readthedocs.io/> |

For adapted code or a particular method, give the precise source and describe the adaptation rather than citing only a library homepage. Keep any original paper citations already supporting the project. Do not add unverified papers, quotations, DOIs, timings or confidence intervals merely to make the bibliography longer.

## AI-tool acknowledgment

**OpenAI Codex assisted with the technical audit, repaired imports and paths, evidence reconciliation, development-only ablation verification and the final release workflow. The current release work was performed on 18–19 November 2026.** Earlier AI assistance documented in the original reports and README must also remain disclosed.

During this release, the scientific phases are closed: no new hyperparameter search, repeated ablation, selected-HGB refit, threshold optimization or final-test inference is authorized. The only new real-data execution requested by the release workflow is the isolated replay of the `p2-base`, `p2-clean` and `development-features` data producers. Their actual Windows execution status must be reported from inspected returned evidence, not from generated code, synthetic tests or an AI assertion.

The student remains responsible for reviewing the source, executing the permitted workflow, validating outputs, checking citations and preparing the final academic submission. Do not claim an AI audit guarantees correctness, reproducibility, absence of every possible leakage mechanism or a particular grade.

## Where acknowledgments must appear

The assignment requires source and AI acknowledgments in **both the README and the academic report**. The final README should point to this file and identify the data, course/starter-code provenance and AI assistance directly. This file is technical documentation only; the academic report and Part 6 have not been written or edited by this release task.

## 24 November report revision — additional primary sources

- FFIEC CDR, About the data: <https://www.cdr.ffiec.gov/Public/HelpFiles/WelcomeAdditionalInfo.htm> (public bulk data regenerated monthly to capture amendments).
- Basel Committee, Core Principles for effective banking supervision (2024): <https://www.bis.org/publications/202404-standards-core-principles-effective-banking-supervision>; BCBS 239: <https://www.bis.org/publ/bcbs239.htm>. Used as supervisory/data design principles, not as claims of SBV legal implementation.
- SBV Circular 31/2024 and 37/2025: <https://vanban.chinhphu.vn/?docid=210625&pageid=27160>, <https://vanban.chinhphu.vn/?docid=215867&pageid=27160>.
- Viet Nam consolidated Law on Credit Institutions, 143/2026/VBHN-LQ-VPQH: <https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-143-2026-vbhn-lq-vpqh-470556.htm>.
- WTO WT/TPR/S/490: <https://www.wto.org/english/news_e/news_docs/S490.pdf>; roster is illustrative and requires deduplication.
- Cole & White (2012), <https://doi.org/10.1007/s10693-011-0116-9>; FDIC Risk Review Glossary (2019), <https://www.fdic.gov/analysis/risk-review/2019-risk-review/2019-risk-review-glossary.pdf>.
- S1 aggregate supplement is derived from the student's archived evidence; see its provenance and verifier. ChatGPT and GPT Work assisted with critical review, writing, aggregate arithmetic, prototype/verification code and release documentation; Codex and Claude provided technical and critical review; NotebookLM provided review suggestions. No new empirical score run is asserted.

## 25 November corrected release
The registered development selection objective is stated as prespecified; direct instructor approval is not independently authenticated. The report and README cite the course starter and the recovered original Financials manifest (S4). ChatGPT assisted this correction and archive reconciliation; exact identifiers for earlier AI sessions were not consistently retained. No new model fit or final-test prediction.
