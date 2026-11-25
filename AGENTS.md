# Repository-specific instructions for Codex code review

Scope: a frozen NEU BFT65B individual FDIC bank-failure early-warning research pipeline.

1. Review `docs/CODEX_FINAL_REVIEW_PROMPT.md` and the original course rubric summarized in `docs/SUBMISSION_AND_VERIFICATION.md`.
2. **Do not run** model search/tuning, reselect any alarm threshold, retrain/final-score the held-out test, or edit a frozen result/protocol. Do not use test results for post-hoc model/feature/threshold selection.
3. `python -B -m unittest discover -s tests -q`, `python -B run.py plan`, and `python -B run.py validate --out ../verification_output` are metadata/static checks; these do not establish end-to-end clean-room reproducibility.
4. Raw FDIC financial records, bank-level scores, trained models and request-cache bodies are absent intentionally. Give evidence-dependent findings the label NOT VERIFIED if you cannot rerun the underlying input.
5. The reported source code retains historical evidence, except for the documented privacy-only redaction of one Part3 preflight **docstring**, see `provenance/PUBLICATION_TRANSFORMATION.json`. Public historical log files are path-redacted copies and do not have the original byte digests.
6. Preserve licensing/citations and explicitly disclose AI assistance.
7. Produce a severity-ranked audit with exact file/line references, concrete fixes, reproducibility status, rubric mapping and explicit blocked items.
