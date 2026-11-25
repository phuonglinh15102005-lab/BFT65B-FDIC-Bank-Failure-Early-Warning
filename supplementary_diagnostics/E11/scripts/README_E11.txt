BFT65B E11 – Independent post-lock diagnostic (22 November 2026)

1. Extract the entire ZIP on your Windows computer.
2. Double-click DOUBLE_CLICK_E11_WINDOWS.cmd. It finds previously verified development and clean-panel .parquet files under %USERPROFILE%\BFT65B_outputs and SHA-256 verifies both.
3. Once complete, upload BFT65B_E11_RESULTS_PASS_*.zip from Downloads. A failure log should also be shared if the command fails.

E11 reruns only 3 frozen HGB train folds to produce train/validation ROC-AUC and AP/lift.
It also generates grouped validation-era medians and binary flag frequencies on the 1984-2008 development cohort, and a matched 2019Q4->2020Q1 RBCRWAJ state transition on the unlabeled clean accounting panel.
No final-test outcome labels, saved predictions, final full-fit model, or final scoring are accessed. Existing files are read-only and there is no model selection or threshold optimization.
Results are EXPLORATORY, produced AFTER the registered model/test lock. Do not use them to select features/models or change thresholds. Historical reporting-vintage limitations remain.

Needs your existing Python environment with pandas, pyarrow, numpy, scikit-learn installed.
Source SHA-256 digests and input data SHA-256 digests are pinned in PINNED_INPUTS.json.
If the exact inputs are not at the expected locations, the script scans only your BFT65B_outputs directory. It will fail closed rather than use unmatched data.
