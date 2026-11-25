# NEW post-hoc uncertainty check — not recovered historical bootstrap

`bootstrap_locked_scores.py` reads the two hash-pinned **immutable** archived final-test outputs on a local computer and computes 1500 CERT-cluster samples with seed 20261117, using multiplicities at the CERT level (all quarters for a bank resampled together). It validates the weighted AP formula against sklearn for unweighted and 5 random-weighted samples. It computes separate event recall as a 341-event sample weighted using those same sampled bank CERT multiplicities. Ties in probability scores are grouped at each threshold.

Point metrics from saved predictions match original AP/AUC/Brier/logloss. **New posthoc** AP 95% percentile CI and event recall CI in JSON. This is numerical uncertainty, not validation of model selection or common macro shocks, and not a reproduction of the unrecovered historical CI.

Reproducibility test: Two sequential runs produced byte-identical JSON and per-draw CSV. No model loads, training, test inference, thresholds tuning or source file writes. The 2 results are identical only in the local environment; package versions and numerical library may affect bit-level values across systems.
