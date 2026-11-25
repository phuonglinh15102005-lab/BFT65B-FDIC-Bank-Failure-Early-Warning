from pathlib import Path
import csv, json, hashlib, math, subprocess, sys
R=Path(__file__).resolve().parents[1]; E=R/'evidence/final_review'
def check(b,msg):
    if not b: raise ValueError(msg)
def load(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def close(a,b):return math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-10)
ledger=load(E/'ARCHIVE_MEMBER_LEDGER.json'); seen=set()
for r in ledger:
    p=R/r['released']; check(p.resolve().is_relative_to(E) and p not in seen and sha(p)==r['released_sha256'],'Archive member: '+r['released']);seen.add(p)
    if r['transformation']=='unchanged':check(r['original_sha256']==r['released_sha256'],'Unchanged-member digest')
print('PASS archive member ledger:',len(seen))
p=load(E/'part2/supplement/lag_key_comparison.json');c=p['counts'];check(c['shared']+c['lag1_only']==c['lag1'] and c['shared']+c['lag2_only']==c['lag2'],'Lag keys'); check(c['lag1']-c['lag2']==23516,'Lag net');check(sum(p['lost_decision_keys_by_lag2_source_absence'].values())==c['lag1_only'],'Lag losses');check(sum(p['gained_decision_keys_by_lag1_source_absence'].values())==c['lag2_only'],'Lag gains');check(all(sum(x.values())==c['clean'] for x in p['source_row_flow'].values()),'Source flow');o=p['positive_key_overlap'];check(o['shared']+o['lag1_only']==c['positive_lag1'] and o['shared']+o['lag2_only']==c['positive_lag2'],'Positive windows'); print('PASS lag overlap, source flow, registry positive windows')
subprocess.run([sys.executable,'-B',str(E/'part3/supplement/verify_supplement.py')],check=True)
p=E/'part4/R23'; a=rows(p/'source/engine/reference/expected_fold_preprocessing.csv');b=rows(p/'returned/FOLD_PREPROCESSING/fold_preprocessing_recomputed.csv');key=lambda r:(r['fold'],r['clip'],r['feature']); A={key(r):r for r in a};B={key(r):r for r in b};check(len(a)==len(b)==len(A)==len(B)==72 and A.keys()==B.keys(),'R23 key mismatch'); cols=[k for k in a[0] if k not in ('fold','clip','feature')]; n=z=0
for k,x in A.items():
    y=B[k];check(y['status']=='PASS','R23 producer status')
    for f in cols:
        if x[f]=='' or y[f]=='':check(x[f]==y[f]=='','R23 blank mismatch');z+=1
        else:check(close(float(x[f]),float(y[f])),'R23 numeric mismatch');n+=1
check((n,z)==(432,72),'R23 field counts');print('PASS R23 returned/reference reconciliation: 432 numeric + 72 not applicable')
p=load(E/'part4/supplement/recheck_results.json');check(p['dev_candidate_rows']*15==p['dev_formula_cells'] and p['dev_candidate_rows']*11==p['PIT_source_cells'],'Feature cells');check(close(p['structural_4q_missing_minimum']/p['first_fold_4q_missing'],p['structural_share_of_first_fold_missing']),'Structural missing');print('PASS feature oracle denominators and structural missingness')
p=E/'part5/supplement'; a=load(p/'AGGREGATE_RECHECK.json');pol={r['ratio']:r for r in a['policy_cost']};k=pol[20]; lower=[];upper=[]
for ratio,r in pol.items():
    check(close(r['known_cost_detected_kUSD']+r['known_cost_missed_kUSD'],a['total_known_COST_kUSD']),'COST totals');check(close(r['known_cost_detected_kUSD']/a['total_known_COST_kUSD'],r['known_cost_coverage']),'Coverage')
    if ratio==20:continue
    # c R20 + alpha missed20 <= c Rr + alpha missedr; use USD per review
    bound=(k['known_cost_detected_kUSD']-r['known_cost_detected_kUSD'])*1000/(k['total_reviews']-r['total_reviews'])
    (upper if k['total_reviews']>r['total_reviews'] else lower).append(bound)
lo=max(lower);hi=min(upper);check(round(lo/1e6,3)==1.766 and round(hi/1e6,3)==10.269,'Severity bounds')
print(f'PASS four fixed policies: c/alpha in [{lo:.2f}, {hi:.2f}] USD/review among these policies only')
b=rows(p/'DEV_CI_PAIRED_DRAWS.csv');d=load(p/'DEV_CI_RESULT.json');check(len(b)==1500 and all(r['valid']=='True' for r in b) and len({r['replicate'] for r in b})==1500,'Bootstrap counts')
def quant(x,q):
    x=sorted(x);h=(len(x)-1)*q;i=int(h);return x[i]+(x[min(i+1,len(x)-1)]-x[i])*(h-i)
for f in ('HGB_minus_LR','HGB_minus_equity'):
    v=[float(r[f]) for r in b];check(all(close(x,y) for x,y in zip([quant(v,.025),quant(v,.975)],d['percentile95_CI'][f])),'CI '+f)
print('PASS 1500 saved paired development bootstrap draws and percentile intervals')
print('PASS S3: archived and returned aggregate checks only; no raw data, fitting or test inference.')
