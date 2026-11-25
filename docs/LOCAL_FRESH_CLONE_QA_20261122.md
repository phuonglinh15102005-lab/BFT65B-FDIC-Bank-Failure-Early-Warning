# Local clean-clone packaging QA — 22 November 2026

## Procedures actually executed

A new local Git repository was staged and committed using the full public candidate, then cloned into a separate empty local folder (no GitHub remote and no private FDIC data). This is an integrity smoke test of the candidate; **it is not** a public GitHub clone, a fresh dependency-install test, or a raw-data-to-model clean-room reproduction.

| Check | Observed result |
|---|---|
| Git staging of all candidate files before final documentation | All 860 files staged, none excluded by `.gitignore` |
| `python -B -m unittest discover -s tests -q` in fresh local clone | 45/45 PASS (code-contract tests; blocked data stages expected) |
| `python -B run.py plan` | Exit 0, metadata plan only |
| `python -B run.py validate --out ../...` | `PASS_SOURCE_RELEASE_VALIDATION`, 131 pinned source paths |
| `python -B workflow/release_audit.py --out ../...` | `PASS_SOURCE_RESOURCE_AND_PUBLICATION_CONTENT`, 108 Python files, 61 science source files |
| `python -B tools/verify_e11_e12_aggregate.py` | `PASS_AGGREGATE_HASHES`, 7 aggregate CSV hash checks |
| `python -B tools/BFT65B_PUBLICATION_PRECHECK.py .` | Zero automatic findings for local-user paths and listed secrets / forbidden extensions |
| Research PDF included with candidate | 30 pages; **public GitHub URL not yet added** |

## Scope and limitations

A PASS above does **not** demonstrate that independent readers can rerun FDIC raw data acquisition, recover exact original historical snapshots/caches, refit all development candidate models, or rescore the held-out test. Those are explicitly not claimed. The public evidence logs were location-redacted; the original private hashes are preserved in the `provenance/` files and should be compared only against privately archived originals.

Codex was **not executed** as an external agent in this packaging run. The request for Codex review is supplied as `docs/CODEX_FINAL_REVIEW_PROMPT.md` and guardrails as `AGENTS.md`.
