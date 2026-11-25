# Independent reviewer: what is actually reproducible

## Level A: no private data
From an internet-reachable fresh public clone (once published) use the documented Python interpreter and run:

```sh
python -B -m unittest discover -s tests -q
python -B run.py plan
python -B run.py validate --out ../bft65b_source_validation
python -B tools/BFT65B_PUBLICATION_PRECHECK.py . --json ../bft65b_privacy_scan.json
python -B tools/verify_released_aggregates.py
```

These commands test the public source and *existing* outputs only. `plan` does no data processing; `validate` pins only its historical 131 source-manifest entries, **not** all uploaded evidence files. Use `tools/verify_released_aggregates.py` for the separate released-aggregate checks.

## Level B: archived Windows continuous replay
Needs **private** 170 Financials quarterly snapshots + two small source tables, raw manifest/checksums, exact prepared reference outputs and original Step2B/Step2C request cache, plus configured Windows engineering interpreter and exact package versions. Input paths resolve from `config/default.json` under the Windows user profile (unless provided explicitly with an input-only config). Run the documented `run.py continuous --start raw` only after providing these inputs and an *empty external* output path. It does not re-download from FDIC and does not refit or re-score the locked model. The recorded 19 Nov run passed; an unrelated new host is not yet tested.

## Level C: fresh acquisition→model/test replication
**NOT EXECUTED.** Requires a fresh network snapshot (which may differ from the November 2026 original), rebuilt caches, compatible dependencies and a separately registered experiment; it cannot reproduce historical model outcomes byte-for-byte under changing input vintages. Do not rerun final test as an optimization or use test outputs to revise the frozen model.

## Windows shell distinction
In **cmd.exe**: `echo %USERPROFILE%`. In **PowerShell**: `echo $env:USERPROFILE`. The old root BAT and E11/E12 double-click scripts require Windows-specific prerequisites; `py -3` resolves the Python Launcher default and does *not* guarantee the pinned interpreter. Prefer an explicit full path to the verified interpreter when reproducing archived diagnostics. Avoid treating PowerShell as cmd.exe.

## Archived test claim
The stored model lock→claim→audit hash chain records one evaluation. Its exclusive file claim guard is output-location scoped, not a universal technical prevention of new scoring by someone possessing private inputs. It provides historical process evidence, not a tamperproof cross-machine counter.

## Missing input and crash recovery
The original API reader used count/key/hash controls with resumable manifests; page-level row identity and absence of replaced API rows were not independently verified. On a crashed future download, inspect for orphan output Parquet without a committed manifest entry; revalidate the quarter before resuming instead of silently trusting partial files.
