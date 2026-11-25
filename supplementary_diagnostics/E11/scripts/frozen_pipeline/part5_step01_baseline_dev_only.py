#!/usr/bin/env python3
"""BFT65B Part 5 / Step 01: frozen-protocol preflight + 3-fold equity-only baseline.

Never reads the final-test feature file. Never chooses hyperparameters or an
alarm threshold. Frozen preselection protocol must exactly match SHA256.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler

EXPECTED_PROTOCOL_SHA256 = '994f72de6e2446916db8c2fcd36847c45cc68eb6fef5ef67f07acc0476c6d911'
DEV_EXPECTED = {'rows':1231631,'positives':9246,'positive_certs':2410}
FOLD_EXPECTED = {
 'early_bank_stress': {'train':266127,'valid':125962,'train_pos':2627,'valid_pos':2796,'valid_certs':932},
 'post_stress_transition': {'train':459321,'valid':110844,'train_pos':7305,'valid_pos':481,'valid_certs':191},
 'global_financial_crisis': {'train':1129000,'valid':67792,'train_pos':8833,'valid_pos':406,'valid_certs':167},
}
CONTINUOUS = ['log_assets','equity_to_assets','asset_log_growth_1q','asset_log_growth_4q',
 'nclnls_to_loans','loan_allowance_to_loans','cash_to_assets',
 'cash_and_securities_to_assets','deposits_to_assets','net_loans_to_assets',
 'roa_reported_percent','nimy_reported_percent']
BINARY = ['negative_equity_flag','loss_flag_roa_negative','loan_denominator_invalid_flag']
FEATURES = CONTINUOUS+BINARY
KEYS = ['CERT','DECISION_DATE','SOURCE_REPDTE','SPLIT','Y_4Q']


def check(ok:bool, reason:str)->None:
 if not bool(ok):raise AssertionError(reason)


def sha256(path:Path)->str:
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(8*1024*1024),b''):
   h.update(chunk)
 return h.hexdigest()


def verify_protocol(path:Path)->tuple[dict,str]:
 check(path.is_file(),'Protocol JSON missing')
 digest=sha256(path)
 check(digest==EXPECTED_PROTOCOL_SHA256,
       f'PROTOCOL SHA MISMATCH: expected {EXPECTED_PROTOCOL_SHA256}, got {digest}. STOP; do not silently update it.')
 protocol=json.loads(path.read_text(encoding='utf-8'))
 check(protocol['stage']=='FROZEN_PRESELECTION_RULES_BEFORE_ANY_MODEL_COMPARISON', 'Unexpected protocol stage')
 check(protocol['data_contract']['primary_outcome']=='FIRST_FDIC_RESTYPE_FAILURE_IN_NEXT_FOUR_CALENDAR_QUARTERS', 'Unexpected label definition')
 check(protocol['data_contract']['merger_nonfailure'] is True, 'Merger policy must be nonfailure')
 check(len(protocol['feature_policy']['tier1_features'])==len(FEATURES) and set(protocol['feature_policy']['tier1_features'])==set(FEATURES), 'Feature set differs from frozen protocol')
 check(protocol['model_selection']['seed']==20261114, 'Seed mismatch')
 check(protocol['model_selection']['primary_model_selection_metric']=='mean_Average_Precision_across_three_forward_folds_unweighted', 'Metric mismatch')
 check(protocol['test_policy']['model_selection_on_test'] is False, 'Final-test selection forbidden')
 baseline=next(x for x in protocol['model_selection']['models'] if x['name']=='equity_ratio_logistic_baseline')
 check(baseline['features']==['equity_to_assets'] and baseline['hyperparameters']['C']==[1.0]
       and baseline['hyperparameters']['class_weight']==[None], 'Equity-only baseline contract mismatch')
 check(len(protocol['validation']['folds'])==3 and protocol['validation']['embargo_calendar_quarters']==4,'Unexpected folds')
 return protocol,digest


def make_baseline(seed:int)->Pipeline:
 # One original predictor only. The imputer/scaler is re-fitted in every fold.
 return Pipeline([
  ('prep',ColumnTransformer([
    ('equity',Pipeline([
      ('median',SimpleImputer(strategy='median',keep_empty_features=True)),
      ('robust',RobustScaler()),
    ]),['equity_to_assets'])
  ],remainder='drop',sparse_threshold=0)),
  ('clf',LogisticRegression(C=1.0,class_weight=None,solver='lbfgs',
                            max_iter=1000,random_state=seed)),
 ])


def quarter_ordinal(series:pd.Series)->pd.Series:
 return series.dt.to_period('Q').astype('int64')


def audit_dev(df:pd.DataFrame,expected:bool=True)->dict:
 check(set(df.columns)==set(KEYS+FEATURES),'Missing/unexpected columns in model cohort')
 check(df[KEYS].notna().all().all(),'Missing bank keys, dates, split or labels')
 check(df['SPLIT'].eq('development').all(),'Non-development split in input')
 check(df['DECISION_DATE'].dt.is_quarter_end.all(),'Decision dates not quarter ends')
 check(df['SOURCE_REPDTE'].dt.is_quarter_end.all(),'Source dates not quarter ends')
 check((quarter_ordinal(df['DECISION_DATE'])-quarter_ordinal(df['SOURCE_REPDTE'])).eq(1).all(),
       'Financial source must be previous calendar quarter')
 check(df['DECISION_DATE'].max()<=pd.Timestamp('2008-12-31'), 'Input extends past development period')
 check(not df.duplicated(['CERT','DECISION_DATE']).any(),'Duplicate bank-quarter key')
 check(df['Y_4Q'].isin([0,1]).all(),'Non-binary outcome')
 check(df['CERT'].notna().all(),'Missing CERT')
 for name in FEATURES:
  vals=pd.to_numeric(df[name],errors='coerce')
  check(not np.isinf(vals.to_numpy(dtype=float)).any(),f'Infinite feature {name}')
  check(int(vals.isna().sum())==int(df[name].isna().sum()),f'Non-numeric value in {name}')
  if name in BINARY:check(vals.dropna().isin([0,1]).all(), f'Unexpected binary flag values {name}')
  df[name]=vals
 observed={'rows':int(len(df)),'positives':int(df['Y_4Q'].sum()),
           'positive_certs':int(df.loc[df.Y_4Q.eq(1),'CERT'].nunique()),
           'first_date':str(df.DECISION_DATE.min().date()),
           'last_date':str(df.DECISION_DATE.max().date()),
           'decision_quarters':int(df.DECISION_DATE.nunique())}
 if expected:
  for k,v in DEV_EXPECTED.items():check(observed[k]==v,f'{k} mismatch {observed[k]} != {v}')
  check(observed['decision_quarters']==99 and observed['first_date']=='1984-06-30'
        and observed['last_date']=='2008-12-31','Quarter coverage mismatch')
 return observed


def run_baseline_fold(df:pd.DataFrame, fold:dict, seed:int, expected:bool=True)->tuple[dict,pd.DataFrame]:
 name=fold['id'];train_end=pd.Timestamp(fold['train_end'])
 valid_start=pd.Timestamp(fold['validation_start']);valid_end=pd.Timestamp(fold['validation_end'])
 gap=valid_start.to_period('Q').ordinal-train_end.to_period('Q').ordinal-1
 check(gap==4,f'{name}: expected four *whole* embargo quarters')
 check(train_end.to_period('Q').ordinal+4<valid_start.to_period('Q').ordinal,
       f'{name}: training outcome window overlaps validation')
 train=df.loc[df.DECISION_DATE.le(train_end)]
 valid=df.loc[df.DECISION_DATE.between(valid_start,valid_end)]
 check(len(train)>0 and len(valid)>0 and train.Y_4Q.nunique()==2 and valid.Y_4Q.nunique()==2,
       f'{name}: empty set or absent outcome class')
 observed={'train':len(train),'valid':len(valid),
           'train_pos':int(train.Y_4Q.sum()),'valid_pos':int(valid.Y_4Q.sum()),
           'valid_certs':int(valid.loc[valid.Y_4Q.eq(1),'CERT'].nunique())}
 if expected:
  for k,v in FOLD_EXPECTED[name].items():check(observed[k]==v,f'{name}/{k}: {observed[k]} != {v}')

 model=make_baseline(seed)
 model.fit(train[['equity_to_assets']],train['Y_4Q'].to_numpy(dtype=np.int8))
 clf=model.named_steps['clf']
 check(int(clf.n_iter_[0])<1000, f'{name}: baseline LogisticRegression did not converge')
 check(clf.n_features_in_==1, f'{name}: baseline must use one transformed predictor')
 imputer=model.named_steps['prep'].named_transformers_['equity'].named_steps['median']
 train_median=float(train['equity_to_assets'].median())
 check(math.isclose(float(imputer.statistics_[0]),train_median,rel_tol=1e-10,abs_tol=1e-12),
       f'{name}: median imputation was not learned from training')
 scores=model.predict_proba(valid[['equity_to_assets']])[:,1]
 check(np.isfinite(scores).all() and ((scores>=0)&(scores<=1)).all(),f'{name}: invalid probabilities')
 y=valid.Y_4Q.to_numpy(dtype=np.int8)
 # Fixed 1% capacity is a *diagnostic operating point*, NOT the final cost-based threshold.
 n_alert=max(1,int(math.ceil(len(valid)*.01)))
 ranking=valid[['CERT','DECISION_DATE']].copy()
 ranking['p_failure']=scores
 ranking['position']=np.arange(len(valid))
 rank_order=ranking.sort_values(['p_failure','CERT','DECISION_DATE'],ascending=[False,True,True],kind='mergesort')
 hit=np.zeros(len(valid),dtype=bool)
 hit[rank_order['position'].iloc[:n_alert].to_numpy(dtype=int)]=True
 tp=int(y[hit].sum()); fp=int(n_alert-tp)
 result={
  'fold':name,'train_through':str(train_end.date()),
  'validation_from':str(valid_start.date()),'validation_through':str(valid_end.date()),
  'embargo_quarters':gap,'train_rows':observed['train'],'train_positive_rows':observed['train_pos'],
  'validation_rows':observed['valid'],'validation_positive_rows':observed['valid_pos'],
  'validation_positive_certs':observed['valid_certs'],
  'average_precision':float(average_precision_score(y,scores)),
  'roc_auc':float(roc_auc_score(y,scores)),
  'brier_score':float(brier_score_loss(y,scores)),
  'validation_prevalence':float(y.mean()),
  'fixed_alert_rate':float(n_alert/len(valid)),
  'alerts_at_1pct':n_alert,'true_positive_bank_quarters_at_1pct':tp,
  'false_positive_bank_quarters_at_1pct':fp,
  'precision_at_1pct':float(tp/n_alert),
  'recall_at_1pct':float(tp/int(y.sum())),
  'false_alarms_per_1000_bank_quarters':float(1000*fp/len(valid)),
  'training_median_equity_to_assets':train_median,
  'model_coeff_equity_standardized':float(clf.coef_[0,0]),
  'fit_n_iter':int(clf.n_iter_[0]),
 }
 oof=valid[['CERT','DECISION_DATE','Y_4Q']].copy()
 oof['fold']=name;oof['p_failure']=scores;oof['alert_at_1pct']=hit.astype(np.int8)
 check(len(oof)==len(valid) and oof.Y_4Q.sum()==observed['valid_pos'], 'OOF reconciliation failed')
 return result,oof


def self_test(protocol:dict)->None:
 # Pure in-memory synthetic test: not bank-data evidence and never opens the final test.
 rng=np.random.default_rng(20261114)
 train=pd.DataFrame({'CERT':np.arange(1,101,dtype=np.int64),
                     'DECISION_DATE':pd.Timestamp('1987-12-31'),
                     'SOURCE_REPDTE':pd.Timestamp('1987-09-30'),
                     'SPLIT':'development','Y_4Q':([0,1]*50)})
 valid=pd.DataFrame({'CERT':np.arange(101,151,dtype=np.int64),
                     'DECISION_DATE':pd.Timestamp('1989-03-31'),
                     'SOURCE_REPDTE':pd.Timestamp('1988-12-31'),
                     'SPLIT':'development','Y_4Q':([0,1]*25)})
 for d in [train,valid]:
  for f in CONTINUOUS:d[f]=rng.normal(0,1,len(d))
  for f in BINARY:d[f]=rng.integers(0,2,len(d))
  d.loc[d.index[0],'equity_to_assets']=np.nan
 demo=pd.concat([train,valid],ignore_index=True)
 audit_dev(demo,expected=False)
 r, preds=run_baseline_fold(demo,protocol['validation']['folds'][0],seed=20261114,expected=False)
 check(len(preds)==50 and r['alerts_at_1pct']==1 and math.isfinite(r['average_precision']),
       'Synthetic baseline metrics mismatch')
 # Negative control: a feature sourced in the decision quarter must fail.
 invalid=demo.copy()
 invalid.loc[0,'SOURCE_REPDTE']=invalid.loc[0,'DECISION_DATE']
 try:
  audit_dev(invalid,expected=False)
 except AssertionError:
  pass
 else:
  raise AssertionError('As-of negative control was NOT detected')
 # Explicit train-only-fit invariant under validation poisoning.
 baseline=make_baseline(20261114)
 baseline.fit(train[['equity_to_assets']],train['Y_4Q'])
 center_before=baseline.named_steps['prep'].named_transformers_['equity'].named_steps['robust'].center_.copy()
 val_poison=valid[['equity_to_assets']].copy()
 val_poison.iloc[:5,0]=1e12
 baseline.predict_proba(val_poison)
 center_after=baseline.named_steps['prep'].named_transformers_['equity'].named_steps['robust'].center_.copy()
 check(np.array_equal(center_before,center_after),'Validation changed trained preprocessing')
 print('SELF-TEST PASS: as-of chronology, 4Q embargo, train-only fit, leak canary rejected, baseline metrics, OOF counts.')


def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('--protocol',type=Path,required=True)
 ap.add_argument('--dev',type=Path,help='Only development_primary_binary_v2.parquet; NO test file')
 ap.add_argument('--out',type=Path,default=Path('part5_step01_outputs'))
 ap.add_argument('--self-test',action='store_true')
 args=ap.parse_args()
 protocol,protocol_sha=verify_protocol(args.protocol)
 if args.self_test:
  self_test(protocol);return
 check(args.dev is not None and args.dev.is_file(),'Missing V2 development Parquet')
 check(args.dev.name=='development_primary_binary_v2.parquet',
       'Refusing non-development Parquet filename')
 expected_sha=protocol['data_contract']['input_shas']['development_primary_v2']
 actual_sha=sha256(args.dev)
 check(actual_sha==expected_sha,
       f'Development Parquet checksum differs. Expected {expected_sha}; actual {actual_sha}. STOP.')
 args.out.mkdir(parents=True,exist_ok=True)
 print('SOURCE VERIFIED. Reading DEVELOPMENT V2 ONLY ...',flush=True)
 dev=pd.read_parquet(args.dev)  # STRICT: never reads test or financial future table.
 for t in ['DECISION_DATE','SOURCE_REPDTE']:
  dev[t]=pd.to_datetime(dev[t],errors='raise')
 dev_audit=audit_dev(dev,expected=True)
 print(f"DEVELOPMENT VERIFIED: {dev_audit['rows']:,} rows / {dev_audit['positives']:,} positives",flush=True)
 outputs=[];oof_frames=[]
 for fold in protocol['validation']['folds']:
  result,preds=run_baseline_fold(dev,fold,seed=protocol['model_selection']['seed'])
  outputs.append(result);oof_frames.append(preds)
  print(f"{result['fold']}: AP {result['average_precision']:.6f}, ROC-AUC {result['roc_auc']:.6f}, "
        f"valid {result['validation_rows']:,}",flush=True)
 fold_csv=args.out/'baseline_fold_metrics.csv'
 pd.DataFrame(outputs).to_csv(fold_csv,index=False)
 oof=pd.concat(oof_frames,ignore_index=True).sort_values(['DECISION_DATE','CERT'],kind='mergesort')
 check(not oof.duplicated(['CERT','DECISION_DATE']).any(),'Overlapping validation predictions')
 oof_csv=args.out/'baseline_development_oof.csv'
 oof.to_csv(oof_csv,index=False,float_format='%.17g')
 audit={
  'stage':'PART5_STEP01_THREE_FOLD_EQUITY_ONLY_BASELINE',
  'status':'PASS',
  'scope':'DEVELOPMENT_ONLY; FINAL_TEST_NOT_READ',
  'protocol_sha256':protocol_sha,
  'development_parquet_sha256':actual_sha,
  'script_sha256':sha256(Path(__file__)),
  'run_utc':datetime.now(timezone.utc).isoformat(),
  'environment':{'python':platform.python_version(),'pandas':pd.__version__,
                 'scikit_learn':sklearn.__version__,'numpy':np.__version__,'os':platform.platform()},
  'data_audit':dev_audit,
  'folds':outputs,
  'unweighted_mean_validation_average_precision':float(np.mean([r['average_precision'] for r in outputs])),
  'unweighted_mean_validation_roc_auc':float(np.mean([r['roc_auc'] for r in outputs])),
  'baseline_model_spec':{'features':['equity_to_assets'],'median_imputation':'train_only',
   'scaling':'train_only_RobustScaler','C':1.0,'class_weight':None,'clipping':False},
  'not_completed':['Candidate model selection','Hyperparameter tuning','Threshold optimization',
                   'Calibration','Spark MLlib demo','Final test evaluation'],
  'outputs_sha256':{'baseline_fold_metrics.csv':sha256(fold_csv),
                    'baseline_development_oof.csv':sha256(oof_csv)},
  'note':'Fixed top-1%-alert capacity metrics are diagnostics, not a selected cost-based alarm threshold.',
 }
 out_json=args.out/'part5_step01_audit.json'
 out_json.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
 import zipfile
 zpath=args.out/'SHARE_THIS_PART5_STEP01_EVIDENCE.zip'
 with zipfile.ZipFile(zpath,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in [out_json,fold_csv,oof_csv]:z.write(p,arcname=p.name)
 check(zipfile.ZipFile(zpath).testzip() is None,'Output ZIP CRC failed')
 print('STEP 01 PASS — No test accessed. Evidence:',zpath,flush=True)

if __name__=='__main__':
 try:main()
 except Exception as e:
  print('STEP 01 FAILED — DO NOT CLAIM MODEL VALIDATION PASS:',repr(e),file=sys.stderr)
  raise
