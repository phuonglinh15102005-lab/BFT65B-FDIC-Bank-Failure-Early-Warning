from pathlib import Path
import csv, json, hashlib, math, statistics, random
R=Path(__file__).parent
J=lambda x:json.loads((R/x).read_text(encoding='utf-8-sig'))
def C(x):
    with (R/x).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def close(a,b):assert math.isclose(float(a),float(b),rel_tol=1e-8,abs_tol=1e-10),(a,b)
for x in J('archive_member_provenance.json'):
    assert hashlib.sha256((R/x['supplement_path']).read_bytes()).hexdigest()==x['supplement_sha256']
ft=C('fair/trial_times.csv')
for x in C('fair/timing_summary.csv'):
    v=[float(r['seconds']) for r in ft if r['task']==x['task'] and r['engine']==x['engine'] and r['warmup']=='False'];assert len(v)==15;close(statistics.median(v),x['median_seconds'])
lt=C('layout/layout_trials.csv');la=J('layout/layout_audit.json');
for k in ['original','date_sorted']:close(statistics.median(float(x['seconds']) for x in lt if x['label']==k and x['warmup']=='False'),la['median_seconds'][k])
pt=C('paired/interleaved_trials.csv')
for x in C('paired/paired_speedup_bootstrap.csv'):
    task=x['task']; base=x['pandas_baseline'];a={int(r['round']):float(r['seconds']) for r in pt if r['task']==task and r['engine']=='polars' and r['warmup']=='False'};b={int(r['round']):float(r['seconds']) for r in pt if r['task']==task and r['engine']==base and r['warmup']=='False'};assert len(a)==len(b)==12 and set(a)==set(b);rat=[b[k]/a[k] for k in sorted(a)];close(statistics.median(rat),x['median_paired_speedup']); rng=random.Random(20261112+2026+sum(map(ord,task+base))); v=sorted(statistics.median([rat[rng.randrange(len(rat))] for _ in rat]) for i in range(2500));
    for p,key in [(0.025,'bootstrap_95_low'),(0.975,'bootstrap_95_high')]:
        q=(len(v)-1)*p;i=int(q);close(v[i]+(v[i+1]-v[i])*(q-i),x[key])
sa=J('spark_action/spark_action_audit.json');at=C('spark_action/spark_action_trials.csv');
for task,seconds in sa['medians_seconds'].items():
    v=[float(r['seconds_collect_only']) for r in at if r['task']==task and r['warmup']=='False'];assert len(v)==7;close(statistics.median(v),seconds)
for task,x in J('spark/spark_audit.json')['tasks'].items():
    p=C('polars/'+task+'.csv');s=C('spark/spark_'+task+'.csv');assert len(p)==len(s)==x['rows'];keys=next(iter(p[0])); pp={r[keys]:r for r in p};ss={r[keys]:r for r in s};assert set(pp)==set(ss);m=rel=0
    for k,r in pp.items():
        for c,v in r.items():
            w=ss[k][c]
            if c==keys or not v or not w or c in {'REPORTS','DECISIONS','MATCHED_PRIOR_QUARTER','VALID_ASSET_GROWTH','INVALID_LOAN_DENOM','MISSING_P3ASSET','INVALID_ASSET_DENOM'}:assert v==w
            else:
                a,b=float(v),float(w);assert math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-6);m=max(m,abs(a-b));rel=max(rel,abs(a-b)/max(abs(a),1e-12))
    assert math.isclose(m,x['max_absolute_difference'],rel_tol=1e-8,abs_tol=1e-20);assert math.isclose(rel,x['max_relative_difference'],rel_tol=1e-8,abs_tol=1e-20)
assert sum(int(r['rows']) for r in C('replay_summary.csv'))==1089
print('PASS: supplemental file hashes, blocked/paired/layout/action medians, bootstrap endpoints, original 363-row Spark–Polars parity, archived replay census. No engine execution.')
