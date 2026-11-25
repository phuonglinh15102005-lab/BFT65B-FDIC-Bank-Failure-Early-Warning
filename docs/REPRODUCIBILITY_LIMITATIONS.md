> Current status: the 19 November continuous Windows run has now been reviewed. No further user rerun is requested. See REPRODUCTION_VERIFICATION_REPORT.md and REMAINING_ISSUES_CHECKLIST.md; the text below preserves earlier history.

> Current closeout: see the root README and REPRODUCTION_VERIFICATION_REPORT.md. The earlier checkpoint history below does not establish continuous real-data execution.

# Reproducibility scope and remaining limitations

Finalized release date: **19 November 2026** (prepared 18–19 November).

The scientific validation and model optimization phases are closed. The primary objective remains the highest unweighted mean Average Precision across the three original chronological validation folds, followed by a separate development-only cost-sensitive alarm policy. This release does not change the selected HGB, its hyperparameters, the frozen threshold or final-test results.

**All three new producer replays were completed on Windows and independently reviewed on 19 November 2026. Full clean-room end-to-end reproduction is NOT EXECUTED.** Source inspection, successful imports, a recorded environment or an existing audit PASS cannot replace those execution requirements.

## What the current workflow may execute

The supported entry point is `run.py`. Its plan and allowlist distinguish historical stages from the three data-producer stages permitted in this release. The current configuration is documented in `config/default.json`; environment requirements are in `config/environments.json` and the named files under `requirements/`.

| Stage | Current status | Permitted new work |
|---|---|---|
| Acquisition and storage | Prior archived/source verification retained | Source and dependency inspection only. No new bulk download or live HTTP acquisition is dispatched. |
| `p2-base` | VERIFIED Windows return | Run the original prepared-snapshot-to-base producer into a new directory and compare its schema, keys and values with the immutable original base. |
| `p2-clean` | VERIFIED Windows return | Run the clean/PIT producer from the original Step2A/Step2B provenance checkpoints and existing read-only cache. Compare new clean/PIT outputs with the original references. |
| `development-features` | VERIFIED Windows return | Run development feature/cohort production without model fitting, canary reruns, R23 or R24. Compare the output with the immutable original development cohort. |
| Part3 Polars, pandas and Spark SQL | Previously verified; retained | No repeat of the already verified real-data transformations, parity checks or benchmarks. |
| R23 preprocessing and R24 development COST | Closed | No repeat. |
| Registered ablation specification | New late execution verified previously | No additional fit. Its actual execution on 18 November 2026 remains explicitly later than the original final-test lock. |
| Model selection, threshold selection and posthoc intervals | Previously verified; retained | No new search, threshold optimization or repeated metric calculation. |
| Selected-model refit and final-test inference | Immutable; not rerun | The release workflow does not dispatch them. Their historical source remains available for inspection. |

The three new producer stages are not additional modelling experiments. They must create new datasets only under an isolated, versioned output directory. Missing original inputs, an incomplete offline cache or an incompatible environment must produce **BLOCKED**, rather than a substitute dataset, automatic download, package installation or relaxed version gate.

## The replay is an explicit checkpoint workflow

The distinction between source reconstruction and numerical equivalence matters:

1. A fresh `p2-base` result is compared with the original base. It does **not** silently replace the original Step2A checkpoint supplied to `p2-clean`. The original Part2C provenance contract refers to the original Step2A/Step2B checkpoint set, not just a numerically equivalent Parquet file.
2. Consequently, `p2-clean` retains those original immutable checkpoints and source evidence. This is a native producer replay from verified checkpoints, not a claim that every stage now forms a newly acquired, continuous DAG.
3. A successful `p2-clean` result may feed `development-features` **only after** the required schema, key and value comparisons have passed. A failed comparison must never be consumed downstream.
4. Where the workflow permits the original frozen clean/PIT/registry inputs because the parent stage was not requested or was blocked, it records that checkpoint fallback explicitly. Such a result is an isolated checkpoint replay, not a fresh end-to-end chain. A failed parent is not a valid fallback source.

Original reference files are identified by fixed checksums. New outputs also receive checksums, but a fresh Parquet file need not have the same byte checksum as an original file written with different metadata or serialization details. Schema, key uniqueness, null handling and numerical comparisons must pass the predefined comparison contract; a byte hash alone is not a substitute. The current workflow uses exact comparisons for Part2 base/clean/PIT values and declared tolerances for development numerical features. Consult each comparison result for the actual columns, tolerances and mismatches.

## Evidence required to close a new stage

Only actual returned evidence may change a new stage from PENDING/BLOCKED to VERIFIED. Each executed stage should provide:

- The command and arguments actually executed, selected interpreter and observed package versions.
- Input checksums before and after the stage, together with the expected reference identities.
- Captured stdout/stderr, producer status and output checksums.
- Schema, key and column-level numerical comparison results against immutable references.
- The declared lineage, including whether a fresh verified parent or an original checkpoint was used.

A producer finishing successfully is not sufficient if its comparator is missing, blocked or reports a mismatch. An aggregate workflow PASS applies only to the requested, completed data-producer replay. It does not imply that original model fitting, final scoring or full clean-room reproduction was executed.

The workflow exports aggregate comparison results and execution records. Generated Parquet files, row-level quality tables, prediction vectors and fitted artifacts must remain outside the public source repository. Prior verified aggregate evidence is retained with its original scope; copying an existing result does not make it a newly executed test.

## Environments and portability

The environment profiles have different purposes and must not be presented as one interchangeable installation:

- **Engineering:** the recorded existing Windows Python 3.13.9 profile for data producers, with the exact package gates listed in `config/environments.json`.
- **Recorded model core:** Python 3.13.7 with the original model-core pins. It is a provenance record in this release, not authorization to refit or score.
- **Audit:** the observed cloud profile used for source, contract and release checks. It is not evidence that Windows producer execution occurred.

Pinned records document versions; they do not establish a successful clean installation, availability of every historical wheel, identical native libraries or recovery of the full historical transitive environment. Existing Windows inputs and installed environments are external prerequisites. The workflow does not install packages or broaden its model execution permissions to work around a mismatch.

Python write/network guards, explicit arguments and before/after input checksums provide complementary controls. They are not an OS-level sandbox for all native libraries. Real execution and returned comparisons remain necessary to validate the new workflow on the user's machine.

## Scientific limitations are separate from code defects

| Matter | Classification | Honest statement |
|---|---|---|
| Historical filing and revision vintages | Data limitation | The contemporary FDIC snapshot supports audited quarter-lag alignment; it does not reconstruct every original publication or revision vintage. |
| Operational error costs | Scientific assumptions | FDIC resolution COST is observed. Review fees, the primary ratio r=20 and avoidability assumptions define scenarios; they are not measured causal savings. Threshold optimality is conditional on the development proxy, cohort and alarm units. |
| Event detection and loss coverage | Evaluation-unit distinction | Detected failure events and COST-weighted recall have different denominators and interpretations. High event recall does not imply equal coverage of resolution costs. |
| Original bootstrap provenance | Historical provenance gap | Separately verified posthoc intervals do not recover an unavailable historical producer, seed or draw definition. Preserve the posthoc label and uncertainty scope. |
| Late ablation execution | Required disclosure | The development-only robustness analysis was newly executed after the original test lock; it does not establish pre-lock completion and cannot revise the frozen primary model. |

Broken imports, missing required source/configuration files, unsafe output paths and incorrect numerical comparisons are implementation defects that can be repaired. The limitations above must not be hidden or converted into PASS by running unrelated checks or inventing evidence.

## Submission status

The original assignment requires a public repository, pinned requirements, executable instructions, code or notebooks with outputs and fixed seeds, no committed data files, and source/AI acknowledgments. A locally assembled ZIP is not proof of public availability. The actual repository URL, access permissions and deadline compliance remain **NOT VERIFIED** until they can be checked. This release performs no commit or push.

Full acquisition-to-original-grid-to-refit-to-single-test reproduction has not been executed under the current restrictions. Its status must remain **NOT EXECUTED**, even if all three new producer replays pass. This document is technical release documentation; it does not write the academic report or Part 6.

The final returned run used fresh verified Part2C outputs for development, without fallback. Detailed hashes and all-column comparisons are preserved in `release_evidence/windows_return_20261119/`; independent inspection is in the adjacent review directory. No additional user rerun is required.
