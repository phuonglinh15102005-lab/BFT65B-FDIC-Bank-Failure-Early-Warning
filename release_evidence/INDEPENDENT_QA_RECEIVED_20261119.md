# BFT65B — Independent source-release review (19 November 2026)

**Scope:** `BFT65B_SUBMISSION_CODE_VERIFIED_20261119.zip`, 389 ZIP entries, fully extracted to an independent directory. Review is of delivered source, bundled provenance, and returned Windows evidence; the raw FDIC Parquet and fitted model remain on the student's computer. This report does NOT claim a fresh full-data recomputation by the reviewer.

## Re-executed checks

| Test | Independent observation | Conclusion |
|---|---|---|
| ZIP CRC | `ZipFile.testzip() is None` | PASS |
| Standalone file manifest | 388/388 file sizes and SHA-256 exactly match; no unlisted files at extraction | PASS |
| Protected source/config manifest | 122/122 SHA-256 exactly match | PASS |
| Python AST parse | 88/88 `.py` files parse | PASS (syntax only) |
| `python -B run.py plan` | Successful; correctly lists three permitted replay stages; full E2E `NOT_EXECUTED` | PASS for planning |
| `python -B run.py validate --out <fresh path>` | `PASS_SOURCE_RELEASE_VALIDATION`, 122 files checked | PASS for source validation |
| `python -S -B -m unittest discover -s tests -v` | 22 tests PASS | PASS with isolated Python startup |
| `python -B -m unittest discover -s tests -v` | 20 pass, 2 failures from a test asserting NumPy/pandas are absent in `sys.modules` when this host's `sitecustomize` imports them before the tests | NON-PORTABLE TEST ASSUMPTION, not a confirmed scientific defect |
| Windows replay dataset summary | Base 1,682,616; clean 1,669,802; PIT 1,629,398; development 1,231,631 | AGREES with bundled Windows evidence |
| Windows replay 112 nonkey column summaries | 31 base +31 clean +32 PIT +18 development columns, zero reported null/NaN/value mismatch, max finite delta 0, all statuses PASS | CONSISTENT with returned logs; underlying Parquet not available here |
| Aggregate comparisons | 178,235,052 compared row-column cells by multiplying reported per-column row counts | Arithmetic consistent |
| Windows exported output hashes | Independently rehashed 34/34 bundled files against exported hash table | PASS |
| Independent Windows review summary outputs | 3/3 independent-review CSV files match hashes declared in the returned review JSON | PASS |
| Public Git file inclusion | `git init`, `git ls-files --others --exclude-standard`: 388 file candidates, none with `.parquet`, `.npz`, `.joblib`, `.pkl`, `.gz`, `.zip` | PASS for local release contents/ignore pattern; NOT evidence GitHub published |

## Evidence boundaries and caveats

1. **Real Windows replay:** The 19 November Windows-return records state that the base, clean, PIT and development datasets match archived references. The independent checker can rehash the exported logs, counts and comparison CSVs, but cannot directly rehash or reread private Windows Parquet from this ZIP. The original CodeX review already acknowledged this.
2. **Important lineage boundary:** The `p2-clean` producer was run with original `step2_20261108_...` and `step2b_20261108_...` checkpoints (see `release_evidence/windows_return_20261119/p2-clean/ARGUMENTS.json`), not with the newly produced `p2-base` artifact. `development-features` DID consume the new `p2-clean` outputs. Hence this demonstrates **checkpoint replay**, not an uninterrupted freshly constructed chain.
3. **Full clean-room E2E:** `NOT_EXECUTED`. Acquisition, original Step2B lineage, full train/search/refit, and final scoring were not executed in the new clean-room sequence. The supported `run.py` deliberately blocks train/grid/refit/score, so the current README is honest about its limitations but cannot substantiate the strict rubric wording *the pipeline reruns end to end from the README*. This is the only material engineering/submission evidence gap still worth explicitly addressing if pursuing all 5 reproducibility points.
4. **Environment:** Version-pinned engineering and model profiles are recorded separately; a clean installation of all dependencies/historical native binaries was not tested. The unit-test import assumption is brittle under hosts preloading NumPy/pandas. A minimal QA-only patch is possible; it does not justify retraining the frozen model.
5. **Science:** Saved final-test metrics, R23/R24, prior Polars/Spark comparisons, ablation and posthoc bootstrap were accepted in prior audited archives and were not rerun in this source-only review. This source ZIP does not itself contain all row-level model outputs. Preserve the original test lock and the instructor's chosen direction: optimize mean chronological validation AP in the prespecified candidate set, with a separate conditional cost-sensitive alarm policy. Do not make universal model optimality or causal savings claims.
6. **Remaining scientific disclosures:** historical filing/revision vintages unavailable; historical bootstrap provenance incomplete (posthoc outputs available); assumed review fees/r=20/avoidability; ablation executed on 18 November after original test lock; event recall and COST-weighted recall have different meanings.
7. **Submission/documentation:** public GitHub URL and accessibility, first-page identity/required download and cohort metadata, citations and AI disclosures in the report, and 20 main + 10 appendix page limit remain to be verified separately. The academic Part 6 is not in the code-release ZIP.

## Decision

**ACCEPT the package as a source-and-evidence checkpoint release for report drafting, with clear limitations. Do NOT label it a proven full end-to-end reproducible release or a completed submission.** No evidence from these checks requires model retraining, changing the locked threshold, or re-evaluating final-test scores.

**Recommended next action:** begin preparing an integrated, claim-to-evidence-grounded Parts 1–6 report draft using the prior verified Work handoff **plus** this new source release and QA note. In parallel, if maximizing the strict 5-point reproducibility criterion, design a separate clean-room reproduction entrypoint and verify its feasibility in an isolated environment; keep original test/model artifacts immutable and explicitly record unexecuted stages. Finalize and publish the repository only after checking real GitHub access. Do not imply unverified full E2E PASS in the report.
