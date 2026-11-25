# BFT65B Part 7 — Reproducibility reassessment evidence

Scope: exact 24 November submission-candidate repository ZIP, SHA-256 `b515e645a6774a5460e5625f1bcdb378abadd2f9e7a861f8e986b087a9e0329d`. No report edit, publication, acquisition, model fitting or held-out inference was performed. The following distinguishes newly executed source checks from archived Windows execution and proposed changes.

## R1 — Public access: confirmed open

The official assignment requires a public repository from the deadline until grades are released, the real URL on page 1, pinned requirements, code/outputs/fixed seeds, and no committed data files. Reproducibility criterion: “The pipeline reruns end to end from the README.” Excellent: “Public and rerunnable.” The rubric does not prescribe the examiner's numerical subweights or explicitly require a separately witnessed third-party run. Nevertheless the actual rerun capability matters. This candidate is not yet published/verified; do not award public-clone credit on the basis of a local clone.

## R2 — End-to-end: confirmed partial shortfall

- `workflow/continuous_contract.py` is explicitly a strict historical snapshot DAG. Its fixed 4,117/27,835 counts are intentional checks of historical identities, not a general fresh acquisition contract. They can reject revised API counts; not proof the historical DAG is erroneous. The README has native download instructions and parameter descriptions in `docs/REPRODUCE_REVIEWER.md` D, but no demonstrated live acquisition-to-model route.
- 19 November run: five fresh-parent stages from raw snapshot and cached HTTP bodies to development features, 179 compared datasets, 178 identical bytes; 1,231,631 development rows and 18 non-key fields, matching keys/schema and zero observed numeric differences under rtol=1e-9, atol=1e-10. The archived comparison's SHA values are `d1e566d2cc6b2e50a68fa7dce5f96a7b6b65915c14700001097aad94e34689e6` (new) and `d365ce25204a3dcace715db4cea259c94b1b1abba4822c7bcf2b050a1c7f6a73` (original). A logical equivalence result is not byte equality. The original development adapter requires the second hash and cannot consume the first under the frozen protocol. Cause of byte difference is not established; both Parquet files are unavailable for direct byte/content analysis in this audit.
- `tools/reproduce_development.py` includes policy AND grid modes. I inspected native Step01/02A/02B/03 command arguments and required output names; they agree with the adapter. Neither mode is verified on the original full private inputs here. The original exact-snapshot route does not dispatch final refit or scorer. Do not confuse the grid mode existing with it having executed.
- Fix plan: distinguish exact historical verification (strict immutable hashes), private development replay (original files), and new-snapshot methodological replication (separate provenance and protocol, newly observed API totals, no historical expected output hashes treated as new inputs). The last route is not yet implemented and executed end to end. Do not silently bypass a frozen guard or retune/re-score the primary study. A second independent held-out replication, if required, needs separate authorization and scope.

## R3 — Environments: confirmed documentation and install gap

Root `requirements.txt` includes the recorded engineering profile, not the model profile. Separate version records reflect the actual historical execution environments, rather than a single install conflict: engineering Python 3.13.9, pandas 3.1.1, NumPy 2.5.4, Polars 2.1.0, PyArrow 26.0.1; model core Python 3.13.7, pandas 2.3.3, NumPy 2.3.3, sklearn 1.9.0, joblib 1.5.2. `requirements/model-runtime-observed.txt` already records scipy 1.16.3, threadpoolctl 3.6.0 and other observed late-development runtime packages. It is not proof of original lock-time transitive versions. `spark_mllib_first_fold_metrics.csv` records Spark 4.3.0; Java 17 is an external prerequisite. A separately labelled MLlib installation profile can combine the observed compatible model record with Spark, but its installation must be tested, not claimed already tested. The sklearn 1.9.1 legacy oracle documentation is not itself a model protocol violation.

A new local Python 3.13.5 virtual environment with `include-system-site-packages=false` and pip 25.1.1 only successfully ran the data-free check suite (below). This is not installation of the scientific packages, not a clean Windows environment replay and not proof that the recorded versions resolve on a fresh machine.

## R4 — Current tree vs executed tree: new direct checks

I extracted the exact candidate ZIP, committed all files locally, cloned with `git clone --no-local`, created a fresh venv and executed `python -B tools/reviewer_check.py --out` into a new external directory. Local commit `b3f9a513dfd537a26a0b1c505ac7df907935dcc8` is an audit-only commit, not a public GitHub commit. Results:

- 930 distributed files, 929/929 manifest entries match (manifest excludes itself).
- 45/45 actual unittest executions pass on the current tree (a non-fatal ResourceWarning appeared in one test log).
- 131/131 pinned source entries match.
- 11/11 reviewer commands exit 0, including S1 nested E10 check, E10/E11/E12 and released aggregate checks, pilot and adapter self-tests, and source validation. `evidence/examiner_supplement/repository_addition/supplementary_diagnostics/E10/` exists. The earlier suspected missing-path failure is not reproduced.
- Automated publication scan: 930 files, zero flags, not privacy clearance. Git status clean after checks.

Executed source manifest: 130 entries. Current source manifest: 131 entries. Comparison identifies three changed paths and one added metadata file:

| Path | Executed SHA prefix | Current SHA prefix | Scope |
|---|---|---|---|
| `workflow/continuous.py` | 941f2b588458 | 05bce4ccc42f | Original file recovered as `release_evidence/continuous_independent_review_20261119/EXECUTED_CONTINUOUS_CONTROLLER.py.txt`; original SHA matches. AST and text diff prove changes confined to `plan()`, not `execute()` or other code. |
| `config/stages.json` | 8c6e5b4be0bf | 1e429fecae8d | Historical closeout documents stage verification metadata updates; original bytes not recovered for direct diff here. |
| `03_PART3_SCALABLE_PROCESSING/code/00_preflight_user.py` | b084abe87e06 | c76a2f3d27bd | Path redaction documented in `provenance/PUBLICATION_TRANSFORMATION.json`; do not claim original bytes unchanged. |
| `config/continuous_verification.json` | absent | 7102c1c947c3 | Added execution status metadata. |

All other 127 shared protected entries retain matching hashes. New unit-test execution applies to current bytes, not a claim that full native Windows producers have been rerun after publication transformations. The stale sentence in `requirements/README.md` about Windows chain not demonstrated is confirmed and must be corrected; retain dated notes as historical, move non-English convenience material under labelled supplementary docs. No changes to the baseline ZIP in this audit.

## R5 — Evidence scope and comparator controls

`provenance/ORIGINAL_FROZEN_FILE_MANIFEST_SHA256.csv` has exactly 799 historical entries. These are a different scope from 130 executed/131 current protected source paths, 256 returned evidence items, and 929 current release manifest entries. A direct comparison against the available `BFT65B_GITHUB_SOURCE_ONLY_READY_20261122.zip` found 797/799 exact size+SHA matches; README.md and .gitignore differ. Therefore avoid an unqualified current claim of 799/799 unchanged. Cite the named historical manifest, the current fresh local clone result and the historical review's distinct 256-file return scope. Redacted public logs are not asserted byte-identical to private originals.

“Independent” describes an AI-assisted separate checker reviewing exported evidence, not an unaffiliated third party reading all raw data. The report already discloses returned evidence boundaries; change captions to precise wording: “AI-assisted returned-evidence verification of the Windows raw-snapshot-to-development replay.” Do not imply the checker reread all raw Parquet bytes.

The old `--self-test` indeed only compares the reference CSV with itself. I directly tested the existing comparator with five fixtures: reordered identical rows accepted; modified false review count rejected; modified threshold rejected; missing ratio rejected; **duplicate ratio accepted (a new comparator weakness)**, because dictionary construction overwrites duplicate keys. The proposed audit-layer-only patch rejects duplicate ratio rows and replaces self-comparison with 11 synthetic positive/negative checks (one reordered identical case, eight changed numeric fields, missing ratio, duplicate ratio). All 11 passed in the fresh local venv. Proposed patch is separately packaged; it has not been applied to the official source ZIP. It does not modify the scientific producers, version/hash guards, model, threshold or test. New full reviewer audit and manifest regeneration are required after integrating it into the final release.

## Actual open work and scoring boundary

1. Correct documentation, provenance and current/archive statements, integrate the tested comparator patch, regenerate manifests and repeat reviewer checks on the final tree.
2. On the original Windows machine, execute `REPRODUCE_DEV_POLICY_WINDOWS.cmd` on exact hash-matched private files. Return aggregate evidence only. This validates development policy, not fresh model fitting or full E2E.
3. Verify the two scientific install profiles in clean Windows environments, with package freeze, imports, Java and Spark smoke test. A failure is a recorded blocker, not grounds to weaken historical guards.
4. If both development Parquets survive, compare keyed canonical content (including exact numeric/null representations) and Parquet metadata, using a separate verifier; do not alter either file. Identical logical content cannot by itself explain the file-byte difference.
5. Create and validate a public-source fresh-snapshot replication route or explicitly document the remaining scope limitation. No data files should be committed. Public availability and a PASS from lightweight checks are not full E2E.
6. Publish only the final approved tree, verify anonymous remote clone, record the real commit and URL, insert it on report page 1, and retain public visibility until grades are released. No public action has been taken here.

The current candidate's public-source and archived-aggregate verification has now been actually executed on a fresh LOCAL clone; the anonymous remote clone, real-data adapter and full clean-room acquisition-to-model run remain unverified. Do not award credit for proposed edits or unexecuted stages.
