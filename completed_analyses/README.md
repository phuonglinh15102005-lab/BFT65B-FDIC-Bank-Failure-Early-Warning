# Completed analyses: source preservation ONLY

These exact source/config records belong to analyses already completed and independently verified. The final release workflow NEVER dispatches them. Do not rerun ablation,model/test metrics or bootstrap checks. No bank-row predictions,fold-keyNPZ,raw data or fitted models are committed.

- ablation/:exact executed three-fold development source,original factory copies,protocol/config/manifests and aggregate full-model reference metrics. The private NPZ references required by REFERENCE_HASHES/RUNTIME_HASHES are external inputs. Their absence is intentional,not permission to fabricate rows or rerun.
- development_ci/:exact completed posthoc paired-CERT development CI code/spec/input digests. INPUTS/ row-level CSV/NPZ references stay private and external.
- test_ci/:exact completed NEWposthoc producer and independent same-seed reproducer source plus a small summary. Original locked score/event rows and draw-ledger inputs remain private/external. This does not recover original historical bootstrap provenance. The reproducer requires explicit input and NEWoutputarguments;do not execute it in this release.

Source copies are preserved for scientific traceability and future controlled review,not exposed as extra supported workflow stages. All current outputs are the prior aggregate records under outputs/verification. No new computation occurred when assembling these files.

The test_ci/evidence folder preserves the exact small source/method/summary names required by the recorded independent reproducer,plus its already-verified1500aggregate AP/event-recall draw output. This draw table contains no bank identifiers or bank rows and is explicitly whitelisted as a statistical output,not raw data. A future separately authorized historical check would need an explicit --evidence-dir pointing there and the private locked scores directory;no such check is requested now.
