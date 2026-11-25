#!/usr/bin/env python3
"""Read-only checks for archived public aggregates; NO FDIC data / model scoring."""
from pathlib import Path
import csv, hashlib, json, math, sys
R=Path(__file__).resolve().parents[1]; A=R/'evidence'/'verified_archive_aggregates'
def rows(name):
 with (A/name).open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def need(v,msg):
 if not v:raise AssertionError(msg)
def close(a,b,tol=1e-8):return math.isclose(float(a),float(b),abs_tol=tol,rel_tol=0)
def main():
 grid=rows('candidate_grid_21.csv');need(len(grid)==21,'candidate grid must contain 21 rows')
 need(len({r['config'] for r in grid})==21,'candidate IDs not unique')
 for x in grid:
  keys=('ap_early_bank_stress','ap_post_stress_transition','ap_global_financial_crisis')
  if all(x[k] for k in keys):
   need(close(x['mean_ap'],sum(float(x[k]) for k in keys)/3,1e-12),'mean AP mismatch: '+x['config'])
  else:
   need(x['config']=='BASELINE_EQUITY_ONLY','unexpected blank fold AP: '+x['config'])
   with (R/'evidence'/'aggregate'/'baseline_fold_metrics.csv').open(newline='',encoding='utf-8-sig') as bfile:baselines=list(csv.DictReader(bfile))
   need(len(baselines)==3 and close(x['mean_ap'],sum(float(v['average_precision']) for v in baselines)/3,1e-12),'equity baseline archive consistency')
 winner=max(grid,key=lambda x:float(x['mean_ap']))
 need(winner['config']=='HGB_L15_LR0p05_I150_L21_CLnone','incorrect winner')
 need(close(winner['mean_ap'],0.29576629263614845,1e-12),'frozen winner AP mismatch')
 scen=rows('threshold_cost_scenarios_4.csv');need({int(x['ratio']) for x in scen}=={5,10,20,50},'threshold grid ratio mismatch')
 for x in scen:need(close(x['cost_units'],float(x['fp_cert_years'])+float(x['ratio'])*float(x['missed_failure_certs']),1e-6),'scenario arithmetic')
 sel=next(x for x in scen if int(x['ratio'])==20)
 need(close(sel['threshold'],0.023971438944668057,1e-15),'frozen threshold mismatch')
 need(close(sel['cost_units'],12844),'frozen dev loss mismatch')
 spark=rows('spark_mllib_first_fold_metrics.csv');need(len(spark)==1 and int(spark[0]['rows'])==125962,'Spark first fold summary mismatch')
 can=rows('part4_step05_canary_by_quarter_29.csv');need(len(can)==29,'canary quarters')
 need(sum(int(x['sampled_rows']) for x in can)==5148,'canary n')
 need(4*sum(int(x['feature_cells_per_comparison']) for x in can)==308880,'canary feature comparisons')
 need(all(int(x['feature_mismatches'])==0 for x in can),'canary mismatch')
 bins=rows('test_calibration_bins_11.csv');need(len(bins)==11 and sum(int(x['n']) for x in bins)==364440,'test bin total')
 cert=json.loads((A/'model_lock_claim_audit_digest_certificate.json').read_text());need(cert['audit_predict_proba_calls']==1 and cert['audit_hyperparameters_or_threshold_changed'] is False,'audit recorded scoring count')
 log=rows('SOURCE_CHAIN_SHA256.csv')
 for rec in log:
  p=R/rec['file'];need(p.is_file(),'missing public file '+rec['file'])
  need(hashlib.sha256(p.read_bytes()).hexdigest()==rec['public_sha256'],'bad SHA '+rec['file'])
 print('PASS_RELEASED_AGGREGATES: 21 models; four policy scenarios; MLlib; 29 PIT canaries; 11 bins; stored lock claim; public SHA ledger ('+str(len(log))+' entries)')
 return 0
if __name__=='__main__':
 try:sys.exit(main())
 except Exception as e:print('FAIL_RELEASED_AGGREGATES:',type(e).__name__,e,file=sys.stderr);sys.exit(2)
