# Reproducibility: execution map and acceptance gates

The final report and GitHub source are separate course deliverables. This document is the current entry point; dated closeout notes describe historical execution, not current publication status. All work directories below must be outside the source repository. Never add source data, fitted artifacts, row-level scores or private OOF evidence ZIPs to Git.

## A. Anonymous clone and full public verification (stdlib only)

Install Git and Python 3.10+; no scientific dependencies are required for this level. From a terminal, clone the real public HTTPS URL while not authenticated. From the clone root:

```text
python -B tools/reviewer_check.py --out ../BFT65B_REVIEW_NEW
```

The output contains a status JSON, numbered command logs, privacy scan, source validation and S1 aggregate calculations. The full manifest is checked against every distributed file (except the manifest itself and Git/Python metadata). The PASS status means public-source and archived-aggregate checks, **not** raw-to-model execution. Record the public URL, commit SHA (`git rev-parse HEAD`), Python version and date in the submission record. Keep the log outside the repo. Do not commit a changed report placeholder or any log containing private paths. `git status --short` should remain empty.

## B. Private exact historical data replay (executed on 19 and 25 November)

Use the original Windows engineering interpreter (Python 3.13.9, versions in `requirements/engineering-recorded.txt`). For a new installation use the recorded pins and save `python -m pip freeze`; both pinned profile installs passed on 25 November; availability may change. Provide original raw snapshot, retained request caches and reference identities using `config/default.json` or an external input-only JSON as described in the root README. Run:

```text
python -B run.py continuous --start raw --out ../BFT65B_CONTINUOUS_NEW
```

This executes the archived source-to-development lineage: raw → preparation → Part2A → Part2B → Part2C/PIT → development. The 19 and 25 November evidence each matched 178 of 179 objects byte-for-byte and the development table logically; the new development Parquet bytes did not match the original SHA. Do not replace the frozen development Parquet or bypass its SHA guard. This is not a live acquisition or model fit. Inspect stage statuses, actual commands, dependency record, before/after hashes and keyed comparisons. A missing input is BLOCKED, not PASS.

## C. Private development reproduction (policy-only real-data execution verified 25 November)

For an independent reviewer, use the exact original `development_primary_binary_v2.parquet` and `failures.parquet`, not a logically equal replay file with a different hash. Use the recorded model runtime (Python 3.13.7, NumPy 2.3.3, pandas 2.3.3, scikit-learn 1.9.0, joblib 1.5.2; other requirements recorded in `requirements/development-recorded.txt`; full transitive lock unavailable). Do not relax hashes or version guards.

```text
python -B tools/reproduce_development.py --mode policy
python -B tools/reproduce_development.py --self-test
```

These commands print a plan and validate the comparison routine only. For a **private reviewer** who has the exact original three development evidence ZIPs:

```text
python -B tools/reproduce_development.py --mode policy --dev PRIVATE/development_primary_binary_v2.parquet --failures PRIVATE/failures.parquet --baseline PRIVATE/SHARE_THIS_PART5_STEP01_EVIDENCE.zip --logistic PRIVATE/SHARE_THIS_PART5_STEP02A_EVIDENCE.zip --hgb PRIVATE/SHARE_THIS_PART5_STEP02B_EVIDENCE.zip --out ../BFT65B_PRIVATE_POLICY_NEW --execute
```

Substitute the real paths and use the exact interpreter. This repeats only the original development OOF policy computation, without fitting or test inference. It checks the original input digests, the four scenarios, all 21 mean AP values and the winner against the archive. It does not use the outcome of the comparison to alter the manuscript's registered model/threshold. This mode is lower cost than refitting grids. The additional `--mode grid` with `--dev`, `--failures`, `--out`, `--execute` repeats the original baseline/12 logistic/8 HGB development candidates before the same policy computation in an isolated output tree. The original outputs remain read-only. Policy mode passed on 25 November with six exact input digests, all 21 ranking rows and four scenarios matching. Grid mode has not been rerun. Original Step04 MLlib and Step05 refit accept pinned original evidence archives, not new ZIPs whose timestamps/digests differ. Their native interfaces are listed below. A new grid archive is not interchangeable with an original frozen archive. The adapter does **not** dispatch Step05 or final test. Its logs may contain private input paths; never commit the generated outputs.

## D. Native producers and acquisition route

For a new independent study using a fresh FDIC snapshot (not the frozen November study), begin with the original documented scope. These are the actual native CLI interfaces; they are not a claim that today's API, all counts, caches and runtime recreate the historical snapshot. Run each stage in order, stop on an error, retain manifest and environment, and do not weaken native checks.

| Stage | Producer and required options | Status/boundary |
|---|---|---|
| Download | `01_PART1_ACQUISITION_STORAGE/code/fdic_download_starter.py --start 1984-03-31 --end 2026-06-30 --out NEW_RAW` | Network acquisition; live data may contain amendments. |
| Audit and typed preparation | `01_PART1_ACQUISITION_STORAGE/code/audit_fdic.py --data-dir NEW_RAW --out NEW_PREP --prepare` | Use API download-log totals for `--expected-failures` and `--expected-institutions`. |
| Base | `02_PART2_DATA_QUALITY_PANEL/code/02_build_panel_base.py --audit-dir NEW_PREP --out NEW_BASE` | Native DQ and keys. |
| History | `02_PART2_DATA_QUALITY_PANEL/code/02b_collect_exit_evidence.py --step2-dir NEW_BASE --out NEW_HISTORY` | Live dated event collection; offline mode needs exact cache. |
| Final panel | `02_PART2_DATA_QUALITY_PANEL/code/02c_finalize_panel.py --step2-dir NEW_BASE --step2b-dir NEW_HISTORY --out NEW_PANEL` | Native exit/PIT contracts; do not substitute original registry for new data. |
| Development features | `04_PART4_FEATURE_PIPELINE/code/part4_v2_relabel_asof_gate.py --clean CLEAN --pit PIT --registry-zip REGISTRY --step01-source ORIGINAL_FEATURE_SOURCE --out-dir NEW_DEV` | Native audited producer; frozen contracts may fail on changed snapshots. Locate actual source and references under Part4; a changed study requires its own protocol and validation. |
| Model comparison and policy | `tools/reproduce_development.py` (see C) | **Exact historical inputs only**, not a new-snapshot training interface. |
| MLlib | `05_PART5_MODELLING_VALIDATION/code/frozen_pipeline/part5_step04_spark_mllib.py --protocol PROTOCOL --dev ORIGINAL_DEV --step01 ORIGINAL_BASELINE_ZIP --out NEW_MLLIB` | Requires original pinned baseline ZIP, compatible model/Spark/Java environment. |
| Final refit | `05_PART5_MODELLING_VALIDATION/code/frozen_pipeline/part5_step05_refit_and_lock.py` | Native `--help` enumerates private protocol/dev/Step01/02a/02b/03/04 inputs. Hardcoded archived digests guard scientific history. Not dispatched in the current release. |
| Held-out assessment | `05_PART5_MODELLING_VALIDATION/code/frozen_pipeline/part5_step06b2_one_time_final_evaluation.py` | Original scorer requires exact model, lock, cohort, failures, pretest and B1 ZIP, exclusive claim. The actual one-score archived result is preserved; do not delete or reset its claim or re-evaluate as part of student editing. Independent scientific replication requires separate authorization, exact private artifacts and a distinct audit record. |

**Important:** the original fresh-acquisition-to-final-score path cannot be guaranteed to be rerunnable with only public GitHub files because archival versions and caches are deliberately omitted, and the locked model guards require exact historical bytes. A new study using current API data is not a reproduction of the frozen test. The above native route and development adapter make the prerequisites and stop conditions explicit; they do not establish an executed clean-room end-to-end result. No real-data run is represented as PASS unless supported by its returned logs. In particular, do not use results of a new test to revise this locked study.

## Optional Windows convenience launcher
`REPRODUCE_DEV_POLICY_WINDOWS.cmd` locates five exact digest-matching files in the usual user Downloads/Desktop/Documents, BFT65B_outputs and data_raw folders. It uses the Python launcher (the adapter requires the original 3.13.7 model environment). If a private archive is nested, extract it locally or use the explicit `--search-root` option. It refuses a missing/mismatched input and will not search or score the test. On PASS it exports only the aggregate `BFT65B_DEVELOPMENT_REPLAY_PASS_*.zip` to Downloads; raw and per-row OOF outputs stay outside Git. The locator and comparison contracts have passed synthetic/aggregate self-checks; the native Windows policy-only replay passed on 25 November.
