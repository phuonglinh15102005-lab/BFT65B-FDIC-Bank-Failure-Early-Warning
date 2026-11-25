# Original rubric and release boundaries

Authoritative source: the student-supplied three-page BFT65B assignment, `00_ASSIGNMENT/final_report_bft65b.pdf` in the original archive. Its byte digest is recorded in `config/assignment_provenance.json`; the original has not been edited. The following are rubric/task requirements, not a self-awarded grade.

| Part | Points | Excellent-level requirement (assignment pp. 2–3) |
|---|---:|---|
| Acquisition and storage | 15 | Complete verified data; efficient format/schema/partitioning/compression justified by measurements. |
| Quality and panel | 20 | Systematic quality audit, justified treatments, correct exits and point-in-time handling. |
| Scalable processing | 25 | Efficient Polars and execution explanation, fair pandas benchmark, matching Spark results/plans, evidence-based scaling argument. |
| Features | 15 | Motivated point-in-time features, label join and training-only preprocessing. |
| Modelling and validation | 15 | Time-ordered imbalanced validation/metrics, simple baseline, MLlib demo, data-based alarm threshold, one final test. |
| Conclusions | 5 | Evidence-based answers to Q1–Q3, limitations and Vietnam implications. Excluded from this code release. |
| Reproducibility | 5 | Public repository and pipeline reruns end to end from the README. Full clean-room reproduction and public access are not established here. |

The leakage gate caps Parts 4 and 5 together at 30% of their combined points if future information is used. The task requires Financials 1984Q1–2026Q2, complete Institutions/Failures, labels through 2025Q2, a chronological final test after a gap of at least four quarters, at least 50 test failures, and development-only tuning/feature/threshold selection.

Submission requires an English PDF/DOCX report with at most 20 main pages plus a 10-page appendix. First-page identity, GitHub URL, acquisition method/date, row counts and development/test failure counts are required. A public repository must remain accessible from the deadline until grades are released; it needs README, pinned requirements, code/notebooks with outputs and fixed seeds. Do not commit data. Cite code, papers and AI tools in both README and report. Report/page/identity checks remain outside this source-only release.

The instructor clarification, as relayed by the user, permits one justified optimization direction. The chosen direction is maximum unweighted mean chronological validation AP, followed by a separate development-only cost-sensitive alarm policy. This statement records user-provided clarification and does not backdate or alter the frozen protocol.
