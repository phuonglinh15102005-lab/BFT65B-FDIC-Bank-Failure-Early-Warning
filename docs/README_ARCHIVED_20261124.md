# FDIC Bank Failure Early Warning — BFT65B source and evidence

**24 November submission candidate — not yet verified as a published repository.** Code is provided for an individual research report at the National Economics University. It includes E10–E12 development diagnostics and newly recovered original archived aggregate results in `evidence/verified_archive_aggregates/`. The authoritative 30-page manuscript is supplied separately in the submission bundle; see `report/README.md`. The public URL must still be inserted on its first page.

## Start here

```sh
python -B -m unittest discover -s tests -q
python -B run.py plan
python -B run.py validate --out ../bft65b_validation
python -B tools/BFT65B_PUBLICATION_PRECHECK.py . --json ../bft65b_precheck.json
```

These commands test source consistency and code contracts only; **they do not download FDIC data or rerun the selected model/final test**. A full Windows replay requires the frozen archived FDIC inputs and cached request evidence. See the workflow explanation below and `docs/SUBMISSION_AND_VERIFICATION.md`.

See `docs/CODEX_REVIEW_RECONCILIATION_20261122.md`, `docs/INPUT_AND_CLEAN_CLONE_REQUIREMENTS.md` and `docs/CODEX_FINAL_REVIEW_PROMPT.md` and `AGENTS.md` for independent Codex review; `provenance/PUBLICATION_TRANSFORMATION.json` for public-path redaction and preserved original digest references.

---

## Archived technical release README (scope and measurements)

# BFT65B — continuous upstream-to-development verified release

**The continuous raw-snapshot-to-development replay completed on Windows on 19 November 2026, and its returned evidence has been independently reviewed. The recorded replay is preserved. Full clean-room Parts1–5/model E2E remains NOT EXECUTED.**

The executed chain was:

`frozen raw snapshot → NEW preparation → NEW Part2A → NEW Part2B → NEW Part2C/PIT → NEW development features`.

Part2B consumed the newly generated Part2A reports and frozen cached HTTP evidence; Part2C consumed that new base/Part2B, and Part4 consumed the new clean/PIT/registry. No frozen intermediate-output fallback was used. This closes the independent QA's checkpoint-lineage gap for the permitted data pipeline.

## Actual execution evidence

| Check | Inspected Windows result |
|---|---|
| Documented runtime | Python 3.13.9, NumPy 2.5.4, pandas 3.1.1, Polars 2.1.0, PyArrow 26.0.1 |
| Normal-startup unit tests | 45/45 PASS; no required `-S` workaround |
| Preparation | 170 quarter files plus Institutions and Failures-all: all 172 Parquet SHAs match frozen prepared references |
| New native Part2B | 59,901 history rows and 24,064 bank-exit evidence rows match frozen CSV bytes |
| Base / clean / PIT | 1,682,616 / 1,669,802 / 1,629,398 rows; original Parquet SHAs reproduced |
| Registry | 24,064 rows; original CSV SHA reproduced |
| Development | 1,231,631 rows; schema/keys/values match, byte SHA differs |

There are 179 compared datasets: 176 Parquet and 3 CSV. 178 reproduce the original bytes; development has logical equivalence with zero observed numerical deltas. All 5,401 compared non-key column summaries report zero null/NaN/value mismatches. 506 original-input hash records agree before/after the run. The reviewer rehashed 256 exported files, checked pinned reference identities, actual commands, fresh-parent hash continuity and complete comparison records. Private Parquet/native producer JSON remain on Windows: this is independent review of the actual Windows execution evidence, not a separate cloud reread of every original data file or recalculation of native signature JSON.

See `REPRODUCTION_VERIFICATION_REPORT.md`, `REMAINING_ISSUES_CHECKLIST.md`, `config/continuous_verification.json` and `release_evidence/continuous_independent_review_20261119/INDEPENDENT_VERIFICATION.json`. Historical cloud BLOCKED/packaging failure records remain preserved and clearly scoped; they are not overwritten with PASS.

## Supported commands and reproduction boundaries

Run these stdlib metadata commands from the extracted root, with a fresh external output directory:

```text
python -B run.py plan
python -B run.py validate --out ../BFT65B_SOURCE_CHECK_NEW
```

For a separately needed reviewer replay using the verified input layout:

```text
python -B -m unittest discover -s tests -v
python -B run.py continuous --start raw --out ../BFT65B_CONTINUOUS_NEW
python -B run.py continuous --start raw --profile "%USERPROFILE%" --python-engineering "%USERPROFILE%/miniconda3/python.exe" --out "C:/BFT65B_CONTINUOUS_NEW"
```

`BAM_CHAY_REPRO_CODE_CUOI.cmd` is retained as the Windows one-click entrypoint for that same workflow. The completed run is evidence of the historical replay, not a new independent run. The controller uses an existing exact engineering interpreter and runs the unit suite before producers. No package installation, HTTP download, model fitting or scoring occurs. All outputs/tempfiles go to the configured Windows user-local output directory; a new directory is required and original sources/references are read-only. A stage passes only after native execution, lineage, complete comparison and preservation checks. Missing prerequisites are BLOCKED; altered pinned identities/schema/keys/values are FAIL; unrun descendants are NOT EXECUTED. No parent fallback exists in continuous mode.

Relative input paths in `config/default.json` resolve under `--profile`/USERPROFILE, never cwd. An external copy may override only input paths:

```text
python -B run.py continuous --start raw --config "C:/BFT65B_CONFIG/input_paths.json" --out "C:/BFT65B_CONTINUOUS_NEW"
```

Raw inputs comprise 170 Financials quarter files, Institutions, Failures and the acquisition manifest; the original audit supplies `file_checksums.csv`. Prepared/output references and full original Step2B/Step2C request caches are also required. The raw ledger is checked and hashed at execution; it was not independently pre-pinned in the compact release. Known prepared/output digests provide separate downstream anchors.

`--start prepared` is an explicit narrower alternative, never automatic fallback. Historical `run.py replay` remains a checkpoint workflow and should not be confused with the verified continuous mode. The historical run.py CLI retains these blocks. An explicit separate reviewer development-only reproduction adapter and native acquisition recipe are now documented in `docs/REPRODUCE_REVIEWER.md`; neither changes the frozen record. A `plan` invocation executes no data stage; its historical evidence status is read from the protected verification metadata.

## Source layout, comparisons and environments

Canonical Parts1–5 source remains under `01_PART1_ACQUISITION_STORAGE/` through `05_PART5_MODELLING_VALIDATION/`. The full stage registry is `config/stages.json`; workflow adapters and guards are under `workflow/`. `completed_analyses/` preserves already-closed ablation/posthoc-CI source/config, not authorization to rerun them. The public release preserves the executed scientific procedures. One Part 3 preflight docstring was edited to remove a private path; the original and distributed digests are recorded in `provenance/PUBLICATION_TRANSFORMATION.json`.

The original Part2B source is unchanged. `workflow/offline_part2b.py` redirects only Collector.cache and calls the original main to generate new signatures/reports/bundle. It does not copy old Part2B outputs or edit provenance. Native Part2C retains its original source-SHA/signature checks. Actual argv and parent before/after hashes independently corroborate the fresh chain; native signature validations were executed by those pinned producers, while their native metadata bytes were not exported for a separate cloud recalculation.

Parquet comparison covers schema, row count, unique nonnull keys, key sets, null/NaN masks and all non-key columns. Preparation/base/clean/PIT values use exact comparison. Development floats permit rtol=1e-9, atol=1e-10, but observed deltas were zero; integer/date/string values are exact. CSV row multisets preserve duplicate multiplicity and compare complete rows. Byte SHA is reported separately; a different development SHA is not labelled byte identity or explained by an unverified serialization hypothesis.

Root requirements retains the pinned engineering profile; `requirements/continuous-data-minimal.txt` records the data-only core. Model-core Python/NumPy/pandas pins stay in separate profiles. The existing environment ran successfully; clean dependency resolution/installation and full historical native-binary recovery were not executed. `.gitattributes` preserves exact bytes under Git/Windows autocrlf so pinned source/evidence hashes remain valid.

## Frozen science, publication and acknowledgments

The unchanged primary direction is maximum unweighted mean chronological validation AP, followed by a separate development-only cost-sensitive alarm policy. Selected HGB, hyperparameters, threshold 0.023971438944668057, cohort and original final-test outputs stay frozen. No new training/search, repeated ablation, threshold change, CI/model-metric recalculation or final-test inference occurred. Prior R23/R24 and Parts1–3/MLlib/model-validation evidence remains closed.

The public payload excludes raw/new Parquet, cache bodies, private bank-row scores/OOF arrays, fitted models and nested evidence ZIPs. Vetted aggregate evidence and fixed seeds/protocol/source manifests are included. Public GitHub URL/visibility/deadline and final report/page/identity requirements remain NOT VERIFIED; no remote commit/push was performed in this release preparation.

FDIC data/definitions: <https://api.fdic.gov/banks/docs/> and <https://banks.data.fdic.gov/bankfind-suite/bulkData>. Retain the National Economics University BFT65B assignment/starter attribution and original code headers. Original assignment digest/rubric scope are in config/docs. **OpenAI Codex assisted with audit, repair, evidence reconciliation and independent review of the 19 November Windows replay.** Preserve earlier AI disclosures and cite sources/AI in the later academic report. See `docs/CITATIONS_AND_AI.md`.

Historical filing/revision vintages, assumed review costs/r=20/avoidability, incomplete historical bootstrap provenance versus verified posthoc intervals, the late ablation date, and event-vs-COST recall distinctions remain disclosed limitations. A successful continuous data replay does not establish full live-acquisition/model clean-room E2E or eliminate those limitations.

## Post-lock targeted development diagnostics (optional; not part of registered model selection)

The `tools/dev_only_targeted_diagnostics.py` utility can run on the original Windows host where the pinned development Parquet and clean panel remain available. It verifies SHA-256 before any calculation, computes outcome-stratified medians for the 15 original features, optionally fits the already selected HGB once for each original chronological **training** fold to measure in-sample AP versus out-of-fold AP, and optionally checks RBCRWAJ zero persistence for the fixed 2020Q1 cohort. It does not read held-out outcome labels/scores or perform held-out inference; its label-free reporting-field audit can read clean financial records from the test era. It does **not** select any feature/threshold or overwrite the locked model. Its outputs are exploratory and must be reviewed before they enter any report.

Use a new output directory and specify the exact inputs (or double-click `tools/WINDOWS_RUN_DEV_ONLY_DIAGNOSTICS.cmd`):

```bash
python tools/dev_only_targeted_diagnostics.py --dev /path/to/development_primary_binary_v2.parquet --clean /path/to/panel_clean.parquet --source 05_PART5_MODELLING_VALIDATION/code/frozen_pipeline --out ../BFT65B_NEW_DEV_ONLY_DIAGNOSTICS
```

Report-source E1–E9 public summary files are mapped in `evidence/E1_E9_PUBLIC_EVIDENCE_INDEX.md`. See `REPORT_STATUS.md` for the remaining public-GitHub verification tasks.

## Source-archive aggregates recovered for independent review

The report already contains the 21-row candidate table and the 4-scenario table, but the prior repository lacked independently readable versions. This release adds the **unaltered original archived CSVs**, an archive-member SHA-256 provenance ledger, the Step05 canary, MLlib summary and digest-only lock→claim→audit certificate under `evidence/verified_archive_aggregates/`. Use `python -B tools/verify_released_aggregates.py` to verify cross-table arithmetic and archive-ledger hashes locally; it does **not** re-execute the FDIC pipeline. `evidence/E1_E9_PUBLIC_EVIDENCE_INDEX.md` maps E1–E12 and disclosure boundaries.

For reproducibility levels, correct Windows shell examples and remaining scientific limitations see `docs/INPUT_AND_CLEAN_CLONE_REQUIREMENTS.md`. The paper credits ChatGPT (writing, source and numerical review), Codex (code and reproducibility review), ChatGPT Work (earlier draft), and Claude/NotebookLM (critique). These tools do not substitute for the author's responsibility to verify source evidence and comply with the course academic-integrity policy.

**Submission status remains PRE-PUBLICATION:** no verified public GitHub URL/fresh remote clone, and no clean-room live API-to-scoring replay.

## Reviewed report and manuscript-critique verification (24 November 2026)

The single current Word/PDF pair is identified in `report/README.md` and is delivered separately, not duplicated publicly. The scientific release and locked score ledger are unchanged; the manuscript, recovered E10 evidence and read-only workload aggregates were updated. Reviewer findings and limitations are itemized in `docs/FINAL_SELECTIVE_AUDIT_20261124.md`. Full live-FDIC acquisition and clean-install model/test scoring remain outside the executed public reproduction boundary.

Recovered E10 original result hashes and 62-quarter locked-policy workload summaries can be checked using `python -B tools/verify_e10_workload_aggregate.py`. The archived row-level source ledgers are intentionally not published.

## New: one-command reviewer audit (no FDIC data, stdlib only)

```sh
python -B tools/reviewer_check.py --out ../BFT65B_REVIEW_NEW
```

The command verifies **every file** listed in the release manifest, runs the 45 original tests, source validation, aggregate verifiers and the examiner supplement (S1), checks the prospective pilot fixture contract, and records command exit codes. Use an output directory that does not exist and is outside the repository. It does not fit or score a model. After publishing, use the same command in an anonymous clone. See `docs/REPRODUCE_REVIEWER.md` for the complete stage map, private-data requirements, and exact recorded reproduction boundaries.

S1 is an arithmetic verification of archived null counts, lag sensitivity, paired trial timing, and four fixed development policies. It is not E13 model training. The pilot contract in `docs/PILOT_VALIDATION_CONTRACT.md` is a synthetic engineering demonstration only; no historical filing vintages, local supervisory cost records or Vietnamese bank records were invented.

Additional source citations for the revised Part 6: FFIEC CDR amendment documentation, Basel Core Principles (2024), BCBS 239, Vietnamese accounting/credit-institution rules and WTO roster are indexed in `docs/CITATIONS_AND_AI.md`. The new synthetic pilot contract is separately labeled; it is not FDIC or Vietnamese empirical evidence.

For the original Windows host, `REPRODUCE_DEV_POLICY_WINDOWS.cmd` is an optional exact-hash private OOF-policy replay (no model fitting or test scoring). A PASS output must come from an actual run, not the public fixture checks.
