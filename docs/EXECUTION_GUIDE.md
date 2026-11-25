> The raw-to-development workflow below completed on Windows on 19 November 2026 and returned evidence was independently reviewed. Commands remain for reviewer reproduction; no repeat user run is requested. Full model E2E remains NOT EXECUTED.

# Executable reproduction guide after independent QA

The root README provides current commands. `run.py plan` shows both historical checkpoint replay and the new continuous-data DAG. Use `run.py continuous --start raw --out NEW_EXTERNAL_DIRECTORY` or the one root BAT for the new lineage test. Never call native model/refit/scorer sources to bypass frozen restrictions.

## Actual fresh DAG

1. Original raw snapshot plus manifest/archived raw ledger → original audit_fdic.py --prepare → NEW prepared output. Compare all 172 prepared Parquet files to the known frozen prepared references.
2. NEW prepared output → original 02_build_panel_base.py → NEW Part2A panel and reports. Compare complete base keys/schema/values.
3. NEW Part2A reports → unchanged original 02b_collect_exit_evidence.py.main via the offline cache adapter → NEW Part2B input signature, reports and bundle. Compare history/exit row multisets with archived reference reports.
4. NEW base plus NEW Part2B → original reviewed 02c_finalize_panel.py with --offline --cache-dir ORIGINAL_SCOPE_CACHE → NEW clean/PIT/registry. Native code checks actual new signatures and copies; comparisons validate panels and registry.
5. NEW clean/PIT/registry after PASS → original reviewed Part4 --production-only --asof-quarters 0 → NEW development output; complete keyed comparison.

No old Step2A/B summary is copied into the new chain, no source signature is edited, and no failed/blocked parent can be replaced with an old output. Frozen raw/cache sources and reference outputs have explicit different roles. Optional `--start prepared` skips only raw preparation and states its narrower source boundary; it is not automatic fallback.

Commands are generated as complete vectors by workflow/continuous_contract.py. The actual arguments, source hashes, cwd, selected interpreter, original/fresh-parent before-after hashes, lineage checks and comparison results are retained per stage. Changes in timestamps/paths/ZIP metadata are not numerical errors; they must genuinely bind fresh parents. SHA byte equality is recorded but is separate from keyed numerical parity.

## Status and artifact handling

PASS applies only after native producer, native provenance, lineage, full comparison and preservation checks. Missing inputs/cache/environment produce BLOCKED; changed frozen hashes/schema/keys/values produce FAIL. Descendants remain NOT EXECUTED. Every output/tempfile is in the new run. Aggregate return evidence has an exported-file SHA manifest; raw/new datasets, cache bodies and bank-row quality tables are excluded from the returned ZIP.

## Preserved historical scope

Parts1–3 archived/Windows validation, R23/R24, model selection, saved-test metrics, ablation and posthoc CI remain closed. Their source and prior aggregate evidence are retained. Historical checkpoint run.py replay remains available for inspection but does not close the new continuous raw-to-development gate. Model fitting/selection/refit and final scoring are intentionally not executed; full Parts1–5 clean-room E2E remains NOT EXECUTED.

No clean installation is performed. Current engineering/model pins and observed distribution metadata do not establish every historical native binary or a successful fresh resolver run. Public GitHub access/report identity/page/citation requirements remain separate submission checks.
