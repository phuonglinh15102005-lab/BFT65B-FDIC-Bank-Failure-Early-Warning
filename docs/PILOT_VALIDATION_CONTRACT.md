# Proposed Vietnam pilot: acceptance contract, not a deployed system

Sources: Basel Core Principles (2024), BCBS 239 risk-data aggregation principles, FFIEC CDR amendment documentation, SBV Circular 31/2024 as amended by 37/2025 and Law on Credit Institutions. These sources support risk-based and forward-looking design and comparable data definitions; they do not establish that this prototype or the illustrative two-case capacity is an SBV system.

Run `python -B tools/pilot_contract.py --self-test`. Synthetic fixtures test exact-quarter endpoints, revision cutoff, absent required predecessor, rejection of ambiguous duplicate filing versions, and retention of all three candidates when two review slots exist. The 121→125 amendment changes log growth only after the hypothetical acceptance timestamp. The synthetic A/B/C queue is not a Vietnamese bank dataset and does not prove the retrospective FDIC inputs were point-in-time accurate. The fixture covers the ordinary capacity queue, not emergency statutory escalation or complete production access control.

Operational data contract for a real pilot:

| Object | Required fields | Acceptance rule |
|---|---|---|
| Filing/version | legal institution ID, period, receipt and regulatory acceptance time, version sequence, original hash, supersession, scope | At a historical cutoff, select latest accepted version then available. Reject ambiguous identities; preserve all originals. |
| Score | decision timestamp, registry version, filing hashes, feature and model versions, score and eligibility | Exact as-of join; same cutoff and inputs reproduce score. No future outcome columns. |
| Queue | rank, severity screen, allocation timestamp, review status, reason, reviewer/approver, deferred timestamp, override and reason | Keep all eligible cases, including deferred. Separate urgent legal escalation from ordinary quota. Review waiting times and override rates. |
| Outcome | independent adjudicator, legally defined endpoint, date, competing exit, observation end, label maturity | Label only after the four-quarter horizon closes; unresolved follow-up not silently negative. |
| Review effort | case ID, activity, role, hours, loaded hourly rate, attributable overhead, quarter and final matured outcome | Cost = sum(hours × rates) + attributable overhead. Report both all-review and false-review costs after outcome maturation; avoid double counting. |

A prospective pilot must separately estimate missed-event avoidable harm: baseline severity, uncertainty and credible causal intervention evidence. FDIC COST is not a substitute. Compare a risk rank and an independently governed severity queue; report workload distribution (median/p95/maximum), delays, event and severity-weighted coverage, and calibration conditional on observed events. Zero-event cycles cannot identify recall. No cost values, local filing history or hypothetical Vietnamese outcome data were generated as empirical results.
