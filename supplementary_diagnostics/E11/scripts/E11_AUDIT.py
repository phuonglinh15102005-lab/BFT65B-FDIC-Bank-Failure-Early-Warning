#!/usr/bin/env python3
"""Post-lock E11 audit. Reads hash-pinned DEV and optionally clean FINANCIAL panel.
Three original HGB train-fold refits; no held-out test labels or scores; no threshold search.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,sys,math
from pathlib import Path
from datetime import datetime, timezone

EXPECTED_DEV_SHA='d365ce25204a3dcace715db4cea259c94b1b1abba4822c7bcf2b050a1c7f6a73'
EXPECTED_CLEAN_SHA='0d1837815820e93eb71508dabd6f48143e2b596b09453606ccf0070c3717e107'
SELECTED_ID='HGB_L15_LR0p05_I150_L21_CLnone'
AP_REFERENCE={'early_bank_stress':0.36044019935122096,
 'post_stress_transition':0.24694556511510515,
 'global_financial_crisis':0.27991311344211933}


def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
 return h.hexdigest()


def write_csv(path,records):
 if not records:return
 with open(path,'w',newline='',encoding='utf-8') as fh:
  wr=csv.DictWriter(fh,fieldnames=list(records[0]));wr.writeheader();wr.writerows(records)


def check(cond,msg):
 if not cond:raise RuntimeError(msg)


def diagnostics(dev_path,clean_path,source,out):
 import numpy as np
 import pandas as pd
 from sklearn.metrics import average_precision_score,roc_auc_score
 sys.path.insert(0,str(source.resolve()))
 from part5_step01_baseline_dev_only import audit_dev,verify_protocol
 from part5_step02_hgb_grid_dev import make_model,params_from_protocol
 from part4_v2_train_only_pipeline import FEATURES,BINARY

 check(dev_path.name=='development_primary_binary_v2.parquet','Unexpected development file name')
 check(sha(dev_path)==EXPECTED_DEV_SHA,'Development Parquet SHA-256 mismatch')
 if clean_path:
  check(clean_path.name=='panel_clean.parquet','Unexpected clean file name')
  check(sha(clean_path)==EXPECTED_CLEAN_SHA,'Clean panel SHA-256 mismatch')
 protocol,ph=verify_protocol(source/'part5_protocol_freeze.json')
 cfg=next(c for c in params_from_protocol(protocol) if c['config_id']==SELECTED_ID)
 check(cfg['clipping']=='none' and cfg['max_leaf_nodes']==15 and cfg['max_iter']==150 and cfg['learning_rate']==0.05,'HGB parameters changed')
 check(not out.exists(),'Fresh output directory required; refusing overwrite')
 dev=pd.read_parquet(dev_path)
 for col in ['DECISION_DATE','SOURCE_REPDTE']:
  dev[col]=pd.to_datetime(dev[col],errors='raise')
 audit_dev(dev,expected=True)
 out.mkdir(parents=True)
 seed=protocol['model_selection']['seed']
 folds=[]
 medians=[]
 for spec in protocol['validation']['folds']:
  name=spec['id'];train_end=pd.Timestamp(spec['train_end']);val_start=pd.Timestamp(spec['validation_start']);val_end=pd.Timestamp(spec['validation_end'])
  gap=val_start.to_period('Q').ordinal-train_end.to_period('Q').ordinal-1
  check(gap==4,f'{name}: four-quarter embargo changed')
  tr=dev.loc[dev.DECISION_DATE.le(train_end)];va=dev.loc[dev.DECISION_DATE.between(val_start,val_end)]
  check(tr.Y_4Q.nunique()==2 and va.Y_4Q.nunique()==2,f'{name}: only one label class')
  model=make_model(cfg,seed)
  model.fit(tr[FEATURES],tr.Y_4Q.to_numpy(dtype=np.int8))
  pred_t=model.predict_proba(tr[FEATURES])[:,1];pred_v=model.predict_proba(va[FEATURES])[:,1]
  train_ap=float(average_precision_score(tr.Y_4Q,pred_t));val_ap=float(average_precision_score(va.Y_4Q,pred_v))
  check(abs(val_ap-AP_REFERENCE[name])<5e-6,f'{name}: validation AP differs from locked reference')
  train_auc=float(roc_auc_score(tr.Y_4Q,pred_t));val_auc=float(roc_auc_score(va.Y_4Q,pred_v))
  tp=float(tr.Y_4Q.mean());vp=float(va.Y_4Q.mean())
  folds.append(dict(fold=name,train_rows=len(tr),train_positive=int(tr.Y_4Q.sum()),validation_rows=len(va),
   validation_positive=int(va.Y_4Q.sum()),train_AP=train_ap,validation_AP=val_ap,
   train_prevalence=tp,validation_prevalence=vp,train_AP_lift=train_ap/tp,
   validation_AP_lift=val_ap/vp,train_ROC_AUC=train_auc,validation_ROC_AUC=val_auc,
   difference_AP_train_minus_validation=train_ap-val_ap,difference_AUC_train_minus_validation=train_auc-val_auc,
   validation_AP_reference_match=True,status='POST_LOCK_DEV_FOLDS_ONLY_NOT_FOR_MODEL_SELECTION'))
  # The validation-era medians are retrospective descriptive groups, not fold-train imputation.
  for feature in FEATURES:
   neg=pd.to_numeric(va.loc[va.Y_4Q.eq(0),feature],errors='coerce')
   pos=pd.to_numeric(va.loc[va.Y_4Q.eq(1),feature],errors='coerce')
   medians.append(dict(fold=name,feature=feature,negative_nonmissing=int(neg.notna().sum()),positive_nonmissing=int(pos.notna().sum()),
    negative_median=float(neg.median()) if neg.notna().any() else None,
    positive_median=float(pos.median()) if pos.notna().any() else None,
    negative_missing=int(neg.isna().sum()),positive_missing=int(pos.isna().sum()),
    note='DESCRIPTIVE_POST_LOCK_DEV_VALIDATION_ERA_NO_FEATURE_SELECTION'))
  print(name,'TRAIN AP',round(train_ap,6),'VALID AP',round(val_ap,6),
        'TRAIN AUC',round(train_auc,6),'VALID AUC',round(val_auc,6),flush=True)
 write_csv(out/'development_fold_AP_AUC_lift.csv',folds)
 write_csv(out/'development_validation_era_feature_medians.csv',medians)

 flags=[]
 for feat in BINARY:
  for y in (0,1):
   s=pd.to_numeric(dev.loc[dev.Y_4Q.eq(y),feat],errors='coerce')
   flags.append(dict(feature=feat,label=y,nonmissing=int(s.notna().sum()),positive_flags=int(s.eq(1).sum()),
      flag_rate_among_nonmissing=float(s.eq(1).sum()/s.notna().sum()) if s.notna().sum() else None,
      missing=int(s.isna().sum()),note='DEVELOPMENT_ONLY_DESCRIPTIVE'))
 write_csv(out/'development_binary_flag_rates.csv',flags)

 if clean_path:
  clean=pd.read_parquet(clean_path,columns=['CERT','REPDTE','RBCRWAJ'])
  clean['REPDTE']=pd.to_datetime(clean['REPDTE'],errors='raise')
  clean['RBCRWAJ']=pd.to_numeric(clean['RBCRWAJ'],errors='coerce')
  # This checks matched CERT transitions, not subtraction of two unrelated quarterly totals.
  q4=clean.loc[clean.REPDTE.eq(pd.Timestamp('2019-12-31')),['CERT','RBCRWAJ']].rename(columns={'RBCRWAJ':'rbcr_2019q4'})
  q1=clean.loc[clean.REPDTE.eq(pd.Timestamp('2020-03-31')),['CERT','RBCRWAJ']].rename(columns={'RBCRWAJ':'rbcr_2020q1'})
  check(q4.CERT.is_unique and q1.CERT.is_unique,'Duplicate CERT in quarter')
  joined=q1.merge(q4,on='CERT',how='left',indicator=True,validate='one_to_one')
  def prior(v,matched):
   if matched=='left_only':return 'not_observed'
   if pd.isna(v):return 'missing_value'
   return 'zero' if v==0 else 'nonzero'
  def now(v):
   if pd.isna(v):return 'missing_value'
   return 'zero' if v==0 else 'nonzero'
  joined['prior_category']=[prior(v,x) for v,x in zip(joined.rbcr_2019q4,joined._merge)]
  joined['current_category']=[now(x) for x in joined.rbcr_2020q1]
  outrows=[]
  for a in ['zero','nonzero','missing_value','not_observed']:
   for b in ['zero','nonzero','missing_value']:
    n=int((joined.prior_category.eq(a)&joined.current_category.eq(b)).sum())
    outrows.append(dict(quarter_from='2019Q4',quarter_to='2020Q1',prior_state=a,current_state=b,count=n,
     population='2020Q1 clean-panel CERTs; 2019Q4 matched where available'))
  write_csv(out/'RBCRWAJ_2019Q4_to_2020Q1_matched_CERT_transition.csv',outrows)
  check(sum(x['count'] for x in outrows)==len(q1),'Transition crosstab row sum does not match 2020Q1 banks')
  print('RBC transitions: 2019Q4 nonzero -> 2020Q1 zero =',int((joined.prior_category.eq('nonzero')&joined.current_category.eq('zero')).sum()),flush=True)

 manifest=dict(scope='POST_LOCK_DEV_REFITS_PLUS_UNLABELED_FULL_CLEAN_PANEL_AUDIT',
    code_protocol_SHA256=ph,dev_SHA256=EXPECTED_DEV_SHA,clean_SHA256=EXPECTED_CLEAN_SHA if clean_path else None,
    frozen_model_id=SELECTED_ID,train_refit_count=3,diagnostic_fold_count=3,
    final_test_labels_or_scores_read=False,final_test_scored=False,model_or_threshold_modified=False,
    provenance='Post-lock exploratory evidence only; not part of frozen model selection',
    limitations=['AP lift is not a prevalence-invariant discrimination metric',
     'AUC is class-prevalence invariant under fixed conditional score distributions, but not immune to temporal regime shifts',
     'CBLR election is unverified; zeros may reflect encoding/missingness',
     'Report-level clean financials include 2020-2021 but contain no test labels/scores'])
 manifest['outputs_sha256']={p.name:sha(p) for p in sorted(out.glob('*.csv'))}
 (out/'E11_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 print('PASS; 3 development refits, no test scoring; read-only input files.',flush=True)

if __name__=='__main__':
 a=argparse.ArgumentParser()
 a.add_argument('--dev',type=Path,required=True)
 a.add_argument('--clean',type=Path)
 a.add_argument('--source',type=Path,required=True)
 a.add_argument('--out',type=Path,required=True)
 args=a.parse_args()
 diagnostics(args.dev,args.clean,args.source,args.out)
