#!/usr/bin/env python3
"""BFT65B development-only, post-lock diagnostics.

Read only the hash-pinned development cohort and optionally the hash-pinned clean
panel. No final-test path is accepted. Never fit or score the frozen final model.
The selected HGB is freshly fit in each ORIGINAL development train fold solely
for an exploratory in-sample vs chronological validation diagnostic. No
hyperparameter choice or policy optimization occurs. Output never overwrites
registered results. Feature medians are group descriptions, not selection.
"""
from __future__ import annotations
import argparse, csv, hashlib, importlib.util, json, math, sys, time
from pathlib import Path

EXPECTED_DEV_SHA='d365ce25204a3dcace715db4cea259c94b1b1abba4822c7bcf2b050a1c7f6a73'
EXPECTED_CLEAN_SHA='0d1837815820e93eb71508dabd6f48143e2b596b09453606ccf0070c3717e107'
SELECTED_ID='HGB_L15_LR0p05_I150_L21_CLnone'

def sha(p:Path):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()

def out_csv(p:Path,rows:list[dict]):
 if not rows:return
 with p.open('w',encoding='utf-8',newline='') as f:
  wr=csv.DictWriter(f,fieldnames=list(rows[0]));wr.writeheader();wr.writerows(rows)

def main():
 a=argparse.ArgumentParser(description=__doc__)
 a.add_argument('--dev',required=True,type=Path,help='development_primary_binary_v2.parquet; no test accepted')
 a.add_argument('--clean',type=Path,help='Optional original panel_clean.parquet for RBCRWAJ persistence')
 a.add_argument('--source',required=True,type=Path,help='Original 05_PART5_MODELLING_VALIDATION/code/frozen_pipeline')
 a.add_argument('--out',required=True,type=Path,help='New output DIRECTORY, must not exist')
 a.add_argument('--skip-refit',action='store_true',help='Only run descriptive and RBCRWAJ checks')
 opt=a.parse_args()
 if opt.out.exists():raise SystemExit('REFUSE: output already exists; specify new directory')
 if opt.dev.name!='development_primary_binary_v2.parquet' or sha(opt.dev)!=EXPECTED_DEV_SHA:
  raise SystemExit('REFUSE: wrong development file name or content SHA')
 if opt.clean and (opt.clean.name!='panel_clean.parquet' or sha(opt.clean)!=EXPECTED_CLEAN_SHA):
  raise SystemExit('REFUSE: clean-panel name or content SHA mismatch')
 for x in ['part5_step02_hgb_grid_dev.py','part5_step01_baseline_dev_only.py','part4_v2_train_only_pipeline.py','part5_protocol_freeze.json']:
  if not (opt.source/x).is_file():raise SystemExit(f'REFUSE: source missing {x}')
 sys.path.insert(0,str(opt.source.resolve()))
 import pandas as pd
 import numpy as np
 from sklearn.metrics import average_precision_score
 from part5_step01_baseline_dev_only import audit_dev, verify_protocol, make_baseline
 from part5_step02_hgb_grid_dev import make_model, params_from_protocol
 from part4_v2_train_only_pipeline import FEATURES
 protocol,ph=verify_protocol(opt.source/'part5_protocol_freeze.json')
 cfg=next(x for x in params_from_protocol(protocol) if x['config_id']==SELECTED_ID)
 print('Reading strictly hash-checked DEV only; no test file can be passed',flush=True)
 dev=pd.read_parquet(opt.dev)
 for x in ['DECISION_DATE','SOURCE_REPDTE']:dev[x]=pd.to_datetime(dev[x],errors='raise')
 audit_dev(dev,expected=True)
 opt.out.mkdir(parents=True)
 # Development-only descriptive analysis: predictors are already registered.
 desc=[]
 for f in FEATURES:
  m={}
  for y in (0,1):
   s=pd.to_numeric(dev.loc[dev.Y_4Q.eq(y),f],errors='coerce')
   m[y]={'n':int(s.notna().sum()),'median':float(s.median()) if s.notna().any() else None,'missing':int(s.isna().sum())}
  desc.append({'feature':f,'negative_n':m[0]['n'],'negative_median':m[0]['median'],
               'positive_n':m[1]['n'],'positive_median':m[1]['median'],
               'positive_minus_negative_median': m[1]['median']-m[0]['median'] if m[1]['median'] is not None and m[0]['median'] is not None else None,
               'negative_missing':m[0]['missing'],'positive_missing':m[1]['missing'],
               'label_scope':'ALL_DEVELOPMENT_POST_HOC_DESCRIPTIVE_NOT_FOLD_VALIDATION'})
 out_csv(opt.out/'development_15_feature_group_medians.csv',desc)
 print('Saved development-only feature medians: 15 predictors',flush=True)
 folds=[]
 if not opt.skip_refit:
  seed=protocol['model_selection']['seed']
  # AP reference frozen before test: values only for verification, NEVER for selection.
  ap_ref={'early_bank_stress':0.360440,'post_stress_transition':0.246946,'global_financial_crisis':0.279913}
  for f in protocol['validation']['folds']:
   name=f['id'];tr_end=pd.Timestamp(f['train_end']);vs=pd.Timestamp(f['validation_start']);ve=pd.Timestamp(f['validation_end'])
   tr=dev.loc[dev.DECISION_DATE<=tr_end]
   va=dev.loc[dev.DECISION_DATE.between(vs,ve)]
   if vs.to_period('Q').ordinal-tr_end.to_period('Q').ordinal-1!=4:raise RuntimeError('Four-quarter purge failed')
   if tr_end.to_period('Q').ordinal+4>=vs.to_period('Q').ordinal:raise RuntimeError('Label overlap found')
   start=time.perf_counter()
   m=make_model(cfg,seed)
   m.fit(tr[FEATURES],tr.Y_4Q.to_numpy(dtype=np.int8))
   train_prob=m.predict_proba(tr[FEATURES])[:,1]
   val_prob=m.predict_proba(va[FEATURES])[:,1]
   tap=float(average_precision_score(tr.Y_4Q,train_prob))
   vap=float(average_precision_score(va.Y_4Q,val_prob))
   ref=ap_ref[name]
   folds.append({'fold':name,'train_rows':len(tr),'train_positives':int(tr.Y_4Q.sum()),'train_AP_in_sample':tap,
                 'validation_rows':len(va),'validation_positives':int(va.Y_4Q.sum()),'validation_AP':vap,
                 'historical_validation_AP_display_6dp':ref,
                 'validation_AP_matches_display_at_6dp':int(round(vap,6)==round(ref,6)),
                 'train_minus_validation_AP':tap-vap,
                 'train_prevalence':float(tr.Y_4Q.mean()),'validation_prevalence':float(va.Y_4Q.mean()),
                 'seconds_fit_and_predict':time.perf_counter()-start,'status':'POST_LOCK_DEV_ONLY_DIAGNOSTIC_NOT_MODEL_SELECTION'})
   print(f'Fold {name}: train AP {tap:.6f}; val AP {vap:.6f}; historical {ref:.6f}',flush=True)
  out_csv(opt.out/'hgb_train_vs_validation_ap_dev_only.csv',folds)
 if opt.clean:
  c=pd.read_parquet(opt.clean,columns=['CERT','REPDTE','RBCRWAJ'])
  c['REPDTE']=pd.to_datetime(c['REPDTE'],errors='raise')
  c['RBCRWAJ']=pd.to_numeric(c['RBCRWAJ'],errors='coerce')
  q=['2019-12-31','2020-03-31','2020-06-30','2020-09-30','2020-12-31','2021-03-31']
  use=c.loc[c.REPDTE.isin(pd.to_datetime(q)),['CERT','REPDTE','RBCRWAJ']].copy()
  if use.duplicated(['CERT','REPDTE']).any():raise RuntimeError('Duplicate CERT-quarter in clean panel')
  use['quarter']=use.REPDTE.dt.to_period('Q').astype(str)
  pivot=use.pivot(index='CERT',columns='quarter',values='RBCRWAJ')
  zero=pivot.get('2020Q1')
  if zero is None:raise RuntimeError('No 2020Q1 records')
  eligible=zero.eq(0)
  rows=[]
  for quarter in ['2020Q1','2020Q2','2020Q3','2020Q4','2021Q1']:
   s=pivot.get(quarter)
   if s is None:continue
   cohort=s[eligible]
   rows.append({'quarter':quarter,'2020Q1_zero_cohort_size':int(eligible.sum()),
                'cohort_observed':int(cohort.notna().sum()),'still_zero':int(cohort.eq(0).sum()),
                'nonzero':int(cohort.notna().sum()-cohort.eq(0).sum()),
                'unobserved_or_null':int(eligible.sum()-cohort.notna().sum()),
                'cohort_zero_share_observed':float(cohort.eq(0).sum()/cohort.notna().sum()) if cohort.notna().sum() else None})
  out_csv(opt.out/'rbcrwaj_2020q1_zero_cohort_persistence.csv',rows)
  print('Saved RBCRWAJ persistence; interpretation: compatible with CBLR hypothesis, not confirmed opt-in',flush=True)
 manifest={'scope':'DEVELOPMENT_ONLY_POST_LOCK_NONSELECTIVE_DIAGNOSTICS',
           'development_sha256':EXPECTED_DEV_SHA,'clean_sha256':EXPECTED_CLEAN_SHA if opt.clean else None,
           'frozen_protocol_sha256':ph,'hgb_configuration':cfg,'fit_count':len(folds),
           'test_scoring':'NEVER_EXECUTED','changes_to_registered_model_or_threshold':False,
           'caveats':['In-sample AP is optimistically biased and cannot itself rule out overfitting',
                     'Group medians are outcome-stratified descriptions and cannot claim causal directions',
                     'RBCRWAJ zeros do not prove CBLR election without individual election status']}
 (opt.out/'RUN_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
 print('DIAGNOSTICS COMPLETE. Manually inspect outputs before citing them.')
if __name__=='__main__':main()
