import sys, json, hashlib, zipfile, io, pathlib
import numpy as np,pandas as pd
from sklearn.metrics import average_precision_score,roc_auc_score,brier_score_loss
root=pathlib.Path('/tmp/p5dev/development_ci'); sys.path.insert(0,str(root/'CODE'))
from paired_ci import load
frames,d,hashes=load(); d['year']=pd.to_datetime(d.day,unit='D').dt.year
R=pathlib.Path('/tmp/p5check/BFT65B_GITHUB_SUBMISSION_20261124/evidence/verified_archive_aggregates')
z=zipfile.ZipFile('/mnt/data/final24/BFT65B_FINAL_Parts1-5_Curated.zip'); pre='BFT65B_FINAL/05_PART5_MODELLING_VALIDATION/'
def read(name):return z.read(pre+name)
cost=pd.read_csv(io.BytesIO(read('evidence/extended_source_audits/A_source_cost/development_oof_failure_event_costs.csv')))
assert len(cost)==1290 and cost.CERT.is_unique
assert set(cost.CERT)==set(d.loc[d.y.eq(1),'CERT'])
valid=cost[cost.COST_valid==True]; total=valid.COST_kUSD.sum(); rows=[]
for r in pd.read_csv(R/'threshold_cost_scenarios_4.csv').itertuples():
 a=d[d.HGB>=r.threshold].sort_values(['CERT','year','day']).drop_duplicates(['CERT','year']); hits=set(a.loc[a.y.eq(1),'CERT']); fp=int(a.y.eq(0).sum()); assert (len(hits),fp,len(a))==(r.detected_failure_certs,r.fp_cert_years,r.cert_year_alerts)
 known=valid[valid.CERT.isin(hits)]; loss=known.COST_kUSD.sum(); fee=10466.26235*.05
 rows.append(dict(ratio=r.ratio,threshold=r.threshold,total_reviews=len(a),false_reviews=fp,detected_events=len(hits),known_cost_events_detected=len(known),unknown_cost_events_detected=len(hits)-len(known),known_cost_detected_kUSD=loss,known_cost_missed_kUSD=total-loss,known_cost_coverage=loss/total,break_even_avoidable_share_false_fee=fp*fee/loss,break_even_avoidable_share_all_fee=len(a)*fee/loss))
w=pd.read_csv(R/'locked_policy_quarterly_workload_62.csv');w['q']=pd.to_datetime(w.decision_quarter_end).dt.quarter
wl=[]
for name,g in [('Q1',w[w.q.eq(1)]),('Q2_Q4',w[~w.q.eq(1)]),('Q1_excluding_2010Q1',w[w.q.eq(1)&w.decision_quarter_end.ne('2010-03-31')])]:
 wl.append(dict(group=name,quarters=len(g),reviews=int(g.first_reviews.sum()),false_reviews=int(g.false_first_reviews.sum()),median=float(g.first_reviews.median()),mean=float(g.first_reviews.mean()),max=int(g.first_reviews.max()),share_of_all=float(g.first_reviews.sum()/w.first_reviews.sum()),share_of_all_false=float(g.false_first_reviews.sum()/w.false_first_reviews.sum())))
first=frames[0]; lr=dict(AP=average_precision_score(first.y,first.LR),AUC=roc_auc_score(first.y,first.LR),Brier=brier_score_loss(first.y,first.LR)); print('LR',lr)
# read only already-produced test audit and missed-event ledger; no raw test rows or inference
au=json.loads(read('evidence/06_test_locked/final_test_evaluation_audit.json'));miss=pd.read_csv(io.BytesIO(read('evidence/extended_source_audits/A_source_cost/test_15_missed_events_with_FDIC_size_COST.csv'))); assert len(miss)==15
assert int(miss.positive_row_ever_crossed_threshold.sum())==1
result=dict(scope='Development-only saved OOF numerical recomputation; test information read only from existing aggregate and archived missed-event diagnostic, no test cohort or predictions opened, no model inference/refit or selection',input_hashes=hashes,archive_sha256=hashlib.sha256(pathlib.Path(z.filename).read_bytes()).hexdigest(),pooled_AP=average_precision_score(d.y,d.HGB),registered_LR_first_fold=lr,validation_fraction=304598/1231631,validation_positive_fraction=3683/9246,known_cost_events=len(valid),total_known_COST_kUSD=total,policy_cost=rows,workload=wl,lead={k:au['fixed_threshold_policy'][k] for k in ['median_lead_quarters','p25_lead_quarters','p75_lead_quarters']},missed_events_no_crossing=14,missed_events_crossing_but_not_detected=1,notes='One positive-window crossing without a timely annual-first detection; exact earlier false review mechanism separately recorded in existing audit/report. COST weighting evaluates four fixed development policies, not a new threshold search.')
print(json.dumps(result,indent=2,default=lambda x:x.item())); out=pathlib.Path('/tmp/p5dev/aggregate_result.json');out.write_text(json.dumps(result,indent=2,default=lambda x:x.item()))
