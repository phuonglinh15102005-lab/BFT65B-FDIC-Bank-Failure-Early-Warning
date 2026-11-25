# Submission-code release changelog — finalized 19 November 2026

The release was prepared on 18–19 November 2026. Original archived code, data, models, threshold, cohort, predictions, protocol and reports were preserved. No new fit, search, CI computation, test scoring or GitHub action was performed.

| File or scope | Change and rationale | Evidence |
|---|---|---|
| `run.py`, `workflow/`, `config/` | Replace the obsolete repair dispatcher with explicit plan/validate/replay commands, strict configuration contracts and three permitted data producers. Model/search/scoring commands are disabled. | Executed command records in `release_evidence/`; stage registry. |
| Canonical Parts 1–5 source | Include same-directory factory imports, protocol copies and the missing protocol SHA sidecar. Keep intentional compatibility copies; exclude raw data and fitted artifacts. | `config/source_manifest.json`; source/resource audit. |
| `02_PART2_DATA_QUALITY_PANEL/code/02c_finalize_panel.py` | Add offline-only `--cache-dir`; keep original Step2A/B signatures and isolate all new outputs. Adjacent Part2B source remains byte-identical. | `release_evidence/WORKFLOW_PRODUCER_PATCHES.diff` and `.json`. |
| `04_PART4_FEATURE_PIPELINE/code/part4_v2_relabel_asof_gate.py` | Add `--production-only --asof-quarters 0` to replay the original development producer without repeating closed oracle/canary audits. Preserve primary feature/label calculations. | Same producer diff and hash record. |
| `01_PART1_ACQUISITION_STORAGE/code/plot_part1_latency.py` | Require explicit summary and new external output; defer optional plotting imports. | `release_evidence/AUXILIARY_CLI_FIXES.diff` and `.json`. |
| `05_PART5_MODELLING_VALIDATION/code/registered_lr_parity/run_registered_spark_recheck.py` | Preserve NOFIT preflight; replace broken reference/output defaults with explicit CLI inputs. | Same auxiliary diff; actual CLI help checks. |
| `workflow/compare.py`, synthetic controls | Compare schema, keys, null/NaN masks and values; reject finite/infinite mismatches. Keep byte SHA separate from numerical equality. | Contract tests; real Arrow/Polars controls BLOCKED in cloud and mandatory before Windows producers. |
| `workflow/engine.py`, Windows controller | Isolate outputs/tempfiles, retain before/after input hashes, export diagnostics even after source-integrity failure, and never consume failed parent outputs. | Fault-injection tests and controller smoke evidence. |
| `completed_analyses/` | Preserve exact already-completed ablation and posthoc CI source/configuration and aggregate outputs; private row-level inputs remain external. No execution added. | Source manifest; prior verification records. |
| Requirements and documentation | Separate incompatible engineering/model environments, include actual observed version metadata, execution order, lineage boundaries, citations/AI acknowledgment and rubric gates. | Requirements records, README and final audit documents. |

The new native producer comparison was completed on Windows and independently inspected on 19 November 2026. Full clean-room E2E is NOT EXECUTED. This is technical release documentation, not an academic report or Part 6.


## Verified return update — 19 November 2026

- Preserved the uploaded return as 56 individual unmodified evidence files; independently checked config/source identity, actual runtime/commands, frozen input hashes, before/after preservation, controls, all-column parity and new-parent lineage.
- Closed p2-base, p2-clean and development-features checkpoint replay gates. Updated status tables, README/rubric/remaining-limitations documentation. Kept all historical cloud BLOCKED records intact.
- Kept scientific and workflow Python source bytes unchanged from the executed release. Updated status metadata and source/package manifests in a new directory; retained the exact executed manifest separately.
- Fixed `.gitignore` to permit vetted root CSV matrices and nested aggregate return/review CSVs. Raw-data/model ignore rules remain active; verify with actual read-only Git ignore checks.
- No R23/R24/ablation/model/CI/test metrics were rerun. No new selected-model fit, threshold change, final scoring, GitHub commit/push, report edit or Part 6 work occurred.


### Release-QA correction record

After Windows verification, C16 source/config validation PASS. C17 actual Git-ignore checking failed because `/workspace/.git` was not a usable Git context; this was a test-harness prerequisite error, not a failed bank-data comparison. The original FAIL record and output remain intact. C18 used an empty temporary local bare Git context to read the source worktree ignore rules: all 15 visible/ignored cases PASS. No commit, remote, push or network operation occurred; temporary scaffolding was removed. C19 final metadata/source validation PASS after registering the corrected command.

There are 19 historical release-QA command records: 16 PASS, 2 cloud BLOCKED, and 1 corrected historical harness FAIL. These counts are separate from the three actual Windows producers, ten comparator controls and independent returned-evidence review. The final relevant QA checks PASS; there is no request to repeat bank-data/model checks. No historical status is rewritten to force a perfect history.

## Continuous Windows verification closeout — 19 November 2026

Preserved all 257 return files unchanged; independently rehashed 256 exported files and checked 506 original input records, all fresh parent bindings and 179 comparison datasets. Closed the continuous-data and target-environment unit gates. Updated README/report/checklist/rubric/status metadata. Plan reports historical execution evidence separately from its own non-executing invocation. Exact executed source manifest/controller snapshot retained; no science producer, frozen model, threshold, cohort or score changed. No new data/model execution performed in cloud.
