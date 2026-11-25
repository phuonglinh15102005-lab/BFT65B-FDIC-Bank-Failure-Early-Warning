BFT65B E12: Development-only robustness, not additional model selection
======================================================================
PURPOSE
  A. Evaluate archived HGB chronological out-of-time AP/AUC conditional on
     strictly observed positive equity/assets > 0 in the lagged financial report.
  B. Quantify bank-level eligible failure detection under the ALREADY LOCKED
     threshold 0.023971438944668057, as descriptive development evidence.
  C. Count near-quarter positive-label overlap in intentionally invalid random
     fivefold splits WITHOUT fitting or scoring any invalid K-fold models.

HOW TO RUN
  1. Extract ZIP. Keep all source files together.
  2. Double-click DOUBLE_CLICK_E12_WINDOWS.cmd on the Windows machine where
     E11 succeeded. Python environment must have pandas, pyarrow, sklearn.
  3. The launcher finds and hash-checks the original development Parquet under
     ~/BFT65B_outputs, verifies the four frozen source-file hashes, and executes
     three archived HGB training folds without selecting any new candidate.
  4. Send BFT65B_E12_RESULTS_PASS_YYYYMMDD_HHMMSS.zip from Downloads.

If automatic discovery fails, use manual CLI from this folder:
  python E12_AUDIT.py --dev "C:\\path\\to\\development_primary_binary_v2.parquet" --source frozen_pipeline --out "C:\\path\\to\\NEW_E12_OUTPUT_DIR"

NO final-test/held-out data are read. No trained model, input Parquet, detailed
bank-level scores or bank identifiers are included in output ZIP. The original
locked evaluation is not reopened or modified.

INTERPRETATION AND LIMITATIONS
  - EQ/ASSET > 0 is a pre-failure accounting proxy, NOT a proof of solvency
    or of actionable intervention lead time.
  - AP depends on prevalence; subgroup AP can differ through cohort selection.
    Interpret paired prevalence, AP, AP lift and AUC together.
  - AUC does not causally separate regime shift from overfitting.
  - Threshold-dependent event detection is an IN-DEVELOPMENT sensitivity since
    the threshold was selected from development OOF scores, not independent test.
  - Invalid random K-fold overlap diagnostic does NOT estimate K-fold AP
    inflation. No invalid model is fitted.
  - These analyses were designed AFTER the final locked-test result, so they
    cannot support a revised model, feature set or threshold.

SELF-TEST, safe on any machine (no user data):
  python E12_AUDIT.py --self-test
