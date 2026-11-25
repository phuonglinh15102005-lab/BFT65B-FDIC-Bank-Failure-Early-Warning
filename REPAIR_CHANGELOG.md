# Reproducibility QA closeout changelog — 19 November 2026

All edits occur in BFT65B_REPRO_CLOSEOUT_20261119. Original archives and prior releases are preserved. No scientific refit/scoring/report work occurs.

| File | Exact change and rationale |
|---|---|
| tests/test_release_contracts.py | Replace global absence assertion with normally-started child import guard and post-startup module delta; accept host preload without allowing workflow scientific imports. |
| tests/test_continuous_contracts.py | Add 23 stdlib tests for actual argument DAG, native signature/copy checks, offline cache behavior, comparison semantics, cwd and fail-stop/export behavior. |
| workflow/continuous.py | Add complete raw/prepared-to-development controller, pinned/preflight input checks, exact fresh DAG, per-stage lineage/comparisons, no fallback, aggregate evidence export and truthful statuses. |
| workflow/continuous_contract.py | Define exact producer vectors and validate genuine native fresh-parent metadata/signatures without editing metadata. |
| workflow/offline_part2b.py | Redirect original Collector cache only; invoke unchanged native Part2B.main offline. No old outputs copied or source-SHA checks relaxed. |
| workflow/continuous_worker.py | Source-pinned producer execution with isolated writes/tempfiles and network/model/test guards. |
| workflow/continuous_compare.py | Reuse Parquet comparator and add exact CSV multiset comparison preserving duplicate multiplicity, with aggregate hashes/results only. |
| workflow/engine.py | Expose continuous CLI/plan and optional explicit cwd plus recorded cwd for subprocesses. Historical checkpoint command retained. |
| workflow/windows_start.py | One-click default changed to continuous --start raw and separate continuous output root. |
| workflow/closeout_checks.py | Record actual normal/no-site/preload/unit/CLI/source/preflight commands and hashes. |
| requirements/continuous-data-minimal.txt | Document exact existing engineering core; no install/resolver claim. |
| .gitattributes; .gitignore | Preserve pinned byte identities under Windows autocrlf; include vetted aggregate QA evidence only. |
| README/config stage metadata/manifests/rubric | Separate previous checkpoint PASS from continuous mode still unexecuted; specify actual order, inputs, outputs, blockers and immutable model boundaries. |

Byte hashes for each modified/new Python source are in release_evidence/repro_closeout_20261119/SOURCE_CHANGES.json. Canonical Parts1–5 science producers remain byte-identical; no frozen output is rewritten. Actual logs are retained, including BLOCKED and synthetic expected-failure tests.
