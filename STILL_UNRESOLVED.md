> Historical record, superseded for current execution status by `REPORT_STATUS.md` and S5 (25 November): second upstream replay, policy-only replay, four-layout storage sensitivity and both clean installs passed. Public HTTPS base clone verified 25 November 2026 (`6258825946139d56b486787b8caf7210a632c326`); full E2E remains unverified. The older checklist below is retained solely as dated history, not current status.

> Current status: the 19 November continuous Windows run has now been reviewed. No further user rerun is requested. See REPRODUCTION_VERIFICATION_REPORT.md and REMAINING_ISSUES_CHECKLIST.md; the text below preserves earlier history.

> **Superseded for current reproducibility status:** this document preserves the earlier checkpoint-release history. The new QA discrepancy is addressed by `REPRODUCTION_VERIFICATION_REPORT.md`, `REMAINING_ISSUES_CHECKLIST.md` and the root README. Prior checkpoint PASS does not prove the new continuous chain; one new upstream-only Windows run is required.

# Remaining limitations after verified Windows checkpoint replay

## No further Windows rerun requested

The returned 19 November 2026 run closes the three native producer gates: base, clean/PIT and development features. The ten comparator controls also ran successfully on Windows. Commands, environments, input/output hashes, all-column comparisons and parent lineage were independently inspected. No checkpoint fallback was used. Do not rerun R23, R24, ablation, selection, threshold, Part3 parity, CI or model/test metrics.

The original cloud controls/preflight logs remain historically BLOCKED; they are not rewritten. Their missing-environment blocker was addressed by the successful actual Windows run. Raw Parquet remains on Windows and was not directly read or independently rehashed in the cloud review.

## Reproduction/submission claims still limited

- **Full clean-room E2E — NOT EXECUTED.** The permitted work is checkpoint replay; fresh acquisition, original grids/refit and one-time final scoring were not replayed. Current restrictions prohibit selected-model training and final-test inference. A scoped replay PASS cannot become full E2E PASS.
- **Clean install/full historical environment — NOT EXECUTED.** Named pins and current observed distribution exports do not recover every historical native binary/transitive dependency or prove dependency resolution.
- **Public repository — BASE CLONE VERIFIED (current update).** Public HTTPS access and the base commit audit passed; continuous public availability until grades are released is an ongoing obligation.
- **Academic report/Part 6 — outside this release.** Identity, first-page metadata, final report citations/AI acknowledgment and the previously oversized appendix must be handled separately. No report was edited.

## Scientific disclosures remain necessary

1. Historical publication/revision vintages are unavailable: retain the historical PIT limitation.
2. The independently verified intervals are posthoc. Historical bootstrap producer/seed/draw provenance is still not recovered.
3. FDIC COST is observed ex post; review fees, ratio r=20 and avoidability are assumptions. Threshold optimality is conditional on the specified development proxy/units; resolution cost is not causal preventable loss.
4. Detected events 326/341 and approximately 40.98% COST-weighted recall have different denominators and meanings.
5. The registered ablation was newly completed on 18 November 2026 after the original final-test lock. Preserve its late date and mixed fold outcomes; it cannot revise the frozen model or threshold.

These are data/provenance limitations, assumptions or unexecuted submission checks, not newly identified model errors. No implementation defect was found in the returned producer/comparator evidence. The new release also fixes the root/nested aggregate CSV `.gitignore` whitelist, with a separate real ignore-rule check.
