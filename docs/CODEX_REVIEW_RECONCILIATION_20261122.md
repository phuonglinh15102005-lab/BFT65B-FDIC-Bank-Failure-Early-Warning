# Reconciliation with independent Codex review — 22 Nov 2026

The independent Codex report identified 18 findings. Changes below were applied to a **new candidate** without altering canonical source code, selected model, threshold or frozen test.

| Finding | Resolution / remaining risk |
|---|---|
| Public GitHub URL | **UNRESOLVED BLOCKER**. No public remote URL or signed-out clone verified. Update page 1 and re-render only when verified. |
| Full clean-room end-to-end | **NOT EXECUTED**. New `INPUT_AND_CLEAN_CLONE_REQUIREMENTS.md` distinguishes metadata, frozen-input replay and fresh API→model/test. |
| Missing selected primary aggregate files | Exported original archived 21-candidate grid, 4 threshold scenarios, forward Platt summary, 11 calibration bins, Spark MLlib, 29-quarter canary, preprocessing aggregate and digest-only lock chain under `evidence/verified_archive_aggregates/`, with archive SHA provenance. Bank-row records not exported. Some E1 row-group/interleaved primary ledgers remain outside the public package. |
| E12 AP and threshold comparator | Corrected AP range 0.2854–0.3035; comparator is >=; no numerical outputs changed. |
| PIT overclaim | Report now explicitly distinguishes exact REPDTE alignment from missing historical receipt/revision vintages, with a concrete 2009Q4/2010Q1 example. |
| Part4 canary producer | Explicit Step05 producer linked to 29-quarter source record; independent formula oracle is separately described. |
| Part3 stress workload and defaults | Labeled reduced count/mean and join/count tasks; documented 1/3/5, 3 repeats, 6144 MiB override and conditional extrapolation. |
| Part1/3 public trials | Added available archived aggregate trials; **still not all** modern layout/paired logs, so do not overstate public reproduction. |
| One-time test guard | Correctly described as selected-output-path claim plus archived digest chain, not global anti-reexecution. |
| Windows shell issue | Distinguish cmd.exe `%USERPROFILE%` from PowerShell `$env:USERPROFILE`; discuss explicit interpreter. |
| Identity/AI attribution | Current report includes course-required identity; README aligned with reported tool roles, with author-review responsibilities. |
| COST scenario | Kept data-anchored FDIC median but assumed review cost and avoidability; exported all 4 scenarios, no new cutoff search. |
| Growth null semantics | Fixed: no decision without exact t−1; valid 4Q growth requires only exact endpoints. |
| Field/status and GiB | Financial and institution tables distinguished; 2,689.71 MiB = 2.627 GiB, not 2.69 GiB. |
| Near-tie selection policy | Near-tie did not occur in recorded grid; no retroactive change to selection procedure. |
| COST verifier input pin | Archived results reconcile; future method should hash every event-ledger input independently, not rerun locked scorer. |
| Acquisition orphan handling | Documented limitation and future recovery procedure; no live downloader modification. |
| QA coverage and stdout warning | Historical tests still pass; original source manifest remains historical and E11/E12 pins are checked separately by released-aggregate tool. ResourceWarning is nonfatal and not represented as fixed. |

**No claims** of a new FDIC download, a repeated test score, an independently fresh Python environment or a remote GitHub verification are made.
