#!/usr/bin/env python3
"""Verify public aggregates only; no FDIC download, fitting or test inference."""
import csv,json,hashlib,statistics
from pathlib import Path
r=Path(__file__).resolve().parents[1]; e=r/'supplementary_diagnostics/E10'; a=r/'evidence/verified_archive_aggregates'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((e/'RUN_ACCEPTANCE.json').read_text()); assert manifest['test_scoring']=='NEVER_EXECUTED'
for n,h in manifest['result_hashes'].items(): assert sha(e/n)==h,n
for rec in json.loads((e/'PUBLIC_LOG_REDACTION.json').read_text()): assert sha(e/rec['file'])==rec['public_sha256']
for rec in json.loads((a/'20261124_SOURCE_PROVENANCE.json').read_text()):assert sha(a/rec['public_file'])==rec['public_sha256']
summary=json.loads((a/'locked_policy_workload_and_metrics_audit.json').read_text()); p=a/'locked_policy_quarterly_workload_62.csv'; assert sha(p)==summary['aggregate_sha256']
with p.open(newline='') as f:rows=list(csv.DictReader(f))
assert len(rows)==62 and len({x['decision_quarter_end'] for x in rows})==62
x=[int(v['first_reviews']) for v in rows]; y=[int(v['positive_first_reviews']) for v in rows]; z=[int(v['false_first_reviews']) for v in rows]; assert all(a==b+c for a,b,c in zip(x,y,z))
assert (sum(x),sum(y),sum(z),statistics.median(x),max(x))==(3178,334,2844,13,765)
assert rows[x.index(max(x))]['decision_quarter_end']=='2010-03-31' and z[x.index(max(x))]==628
assert all(summary[k]==v for k,v in [('test_rows',364440),('positive_rows',1112),('events',341),('detected_events',326),('total_first_reviews',3178),('median_first_reviews',13)])
print('PASS_E10_WORKLOAD_AGGREGATES: four original E10 digests, redacted logs, three archival metadata digests, 62-quarter workload and counts. Score metrics are archived read-only calculations, not independently recomputable from these aggregate tables alone.')
