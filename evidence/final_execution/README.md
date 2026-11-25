# S5 — 25 November execution evidence

This is a publication-safe subset of the author's returned output bundles. The original ZIPs (including unredacted local-path logs) are retained privately; their SHA-256 digests are listed in `ORIGINAL_RETURN_ARCHIVES.json`. The reviewer rechecked the original return archives, 256 exported replay-file hashes, and the full aggregate ledgers before constructing this subset.

- `storage/`: four layouts, 112 timed observations + 32 warmups, 144 recorded fingerprint matches, 170 source digests. Exact executed script is `tools/storage_sensitivity.py` (SHA in storage summary). The source was the prepared snapshot, not original HTTP CSV. Gzip decompresses completely in memory within timing.
- `policy/`: native original-input policy-only computation; six pinned inputs, all 21 candidate ranking rows and four scenarios match the original archive. No estimator fitting.
- `replay/`: second offline five-stage success; 179 datasets, 178 byte matches, 5,401 column summaries, 230,664,115 compared cells. 506 unchanged input digests. `EXPORTED_FILE_MANIFEST.json` is the original private manifest, not a manifest of the public subset; its 256 entries were checked before redaction.
- `install/`: both new virtual environments passed install, pip freeze, pip check and imports. These do not certify a new Spark session or scientific execution in the new venvs.
- Prior failed attempts retained as status summaries. No new acquisition, model grid/refit, or final-test scoring was performed.

Run `python -B tools/verify_final_execution.py` to recalculate the distributed summaries. This is aggregate evidence verification, not raw-data rerun.
