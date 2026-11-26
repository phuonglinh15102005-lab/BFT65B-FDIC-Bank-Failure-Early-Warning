# S6 — 26 November 2026, AI-assisted feature-stage verification

Returned experiment from ChatGPT Work using original hash-matched financial panels and scientific sources at `050889604e449efa26c7bb44943c58cef8477e54`. This directory preserves only scripts, dependency record and aggregate JSON; the original panel files, replicas, scores, labels and fitted models are not distributed. SHA256SUMS covers the distributed supplement files. The release maintainer checked archive digests, source pins and aggregate arithmetic; this is not an additional raw-data execution. `feature_audit.py` uses the historical oracle; the archived panel has no negative DEP, and the recorded formula check passed. For the native full Part 4 gate, use the compatible oracle in the execution guide instead.

**Scope:** all 15 financial predictors on 1,232,375 pre-label development decisions, not the final labeled cohort, preprocessing, fitting or test. Returned result: 18,485,625 feature cells, 13,556,125 source cells, zero reported null-mask or tolerance violations; rtol 1e-8 and atol 1e-9 for the feature comparison. This tests dated source identity, not historical filing-vintage availability.

Scaling: Linux, Python 3.12.14, Polars 2.1.0, four threads per process; three measured trials at each scale after one warmup, balanced order, warm OS cache. ZSTD rewritten development inputs, disjoint CERT offsets, exact normalized-replica digest check. Plan construction + materialization only; excludes startup, replica generation, validation and writes. 1×/2×/3× median 1.124/1.939/2.540 s, RSS 915/1,639/2,599 MiB. Replication preserves historical shapes rather than introducing new skew or independent banks. Concurrency is a separate test using the original input files, six paired blocks; one/two simultaneous jobs took median batch 1.091/1.268 s, sampled simultaneous summed worker RSS 1,031/2,082 MiB (shared pages can be counted twice; parent excluded). These do not establish a Spark cluster crossover, p95 SLA or production refresh latency, nor are they Windows timings.

## Data-free checks

From repo root: `python -B evidence/feature_supplement_20261126/verify_summary.py`. This recomputes aggregate medians, ranges, dimensions and archive hashes. It does not open private data or fit a model.

## Scientific replay (private inputs only)

Use a separate Python 3.12 environment with the recorded `requirements-supplement.txt` (installation in a new environment is not verified by this supplement). From repo root, replace PANELS with the directory containing the exact original panel Parquets, and use a new external output folder. No scoring or labels required. Results and scratch paths must remain outside the public repository.

```text
python -B evidence/feature_supplement_20261126/feature_audit.py --repo . --panels PANELS --out ../S6_AUDIT.json
python -B evidence/feature_supplement_20261126/feature_scaling.py run --repo . --panels PANELS --reference ../S6_AUDIT.json --out ../S6_SCALE.json
python -B evidence/feature_supplement_20261126/feature_benchmark.py --repo . --panels PANELS --reference ../S6_AUDIT.json --out ../S6_CONCURRENT.json
```

The code verifies scientific source and input hashes before reading. Do not substitute newly downloaded panels or bypass checks. New timing depends on hardware and cache. External evidence and AI assistance: ChatGPT Work generated this supplemental run and scripts; ChatGPT checked the returned aggregates and integrated the report. Original model, policy and test remain locked.
