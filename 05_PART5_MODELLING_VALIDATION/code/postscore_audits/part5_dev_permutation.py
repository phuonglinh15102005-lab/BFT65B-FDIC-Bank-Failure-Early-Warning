#!/usr/bin/env python3
"""Strictly DEVELOPMENT-ONLY, fixed HGB configuration, time-fold permutation AP.

No new model selection. Does not access final test or choose any threshold.
Fits the already-frozen HGB specification to each historical training fold and
perturbs one raw feature at a time in held-out DEV validation quarters.
This is an explanatory sensitivity analysis, not causal feature importance.
"""
from __future__ import annotations
import argparse,hashlib,json,sys,time
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.metrics import average_precision_score,roc_auc_score
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.pipeline import Pipeline
from part4_v2_train_only_pipeline import FEATURES,make_preprocessor

DEV_SHA='d365ce25204a3dcace715db4cea259c94b1b1abba4822c7bcf2b050a1c7f6a73'
SEED=20261114
HGB='HGB_L15_LR0p05_I150_L21_CLnone'
FOLDS={
 'early_bank_stress':('1987-12-31','1989-03-31','1990-12-31'),
 'post_stress_transition':('1990-12-31','1992-03-31','1993-12-31'),
 'global_financial_crisis':('2005-12-31','2007-03-31','2008-12-31')}

def require(b,m):
 if not bool(b):raise AssertionError(m)
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(2**20),b''):h.update(block)
 return h.hexdigest()
def run(args):
 require(args.dev.is_file(),'Missing original development Parquet')
 sha=digest(args.dev)
 require(sha==DEV_SHA,'ORIGINAL DEVELOPMENT HASH MISMATCH! Got '+sha+'; expected '+DEV_SHA)
 require(args.prior_revision_dir.is_dir(),'Unpack prior revision package and pass --prior-revision-dir')
 args.out.mkdir(parents=True,exist_ok=True)
 dev=pd.read_parquet(args.dev)
 require(set(FEATURES)|{'CERT','DECISION_DATE','Y_4Q'} <= set(dev.columns),'Missing fixed model columns')
 dev['DECISION_DATE']=pd.to_datetime(dev['DECISION_DATE'])
 require(len(dev)==1231631 and int(dev.Y_4Q.sum())==9246,'Development cohort totals differ')
 for f in FEATURES:
  dev[f]=pd.to_numeric(dev[f],errors='coerce')
  require(not np.isinf(dev[f].to_numpy(dtype=float)).any(),f+': infinite values')
 out=[];meta=[]
 for name in args.folds:
  print('\n===== DEVELOPMENT validation:',name,'=====',flush=True)
  tr_end,va_start,va_end=[pd.Timestamp(d) for d in FOLDS[name]]
  require(va_start.to_period('Q').ordinal-tr_end.to_period('Q').ordinal-1==4,'Embargo is not 4 quarters')
  tr=dev.loc[dev.DECISION_DATE<=tr_end]
  va=dev.loc[dev.DECISION_DATE.between(va_start,va_end)]
  require(len(tr)>0 and len(va)>0 and tr.Y_4Q.nunique()==2 and va.Y_4Q.nunique()==2,'Bad cohort')
  refbase=args.prior_revision_dir/'evidence/step02b'
  with np.load(refbase/'fold_keys'/f'{name}.npz',allow_pickle=False) as z:
   require(np.array_equal(z['cert'],va.CERT.to_numpy(dtype=np.int64)),'Validation row/order differs')
   require(np.array_equal(z['y'],va.Y_4Q.to_numpy(dtype=np.int8)),'Validation labels differ')
   require(np.array_equal(z['decision_day'],va.DECISION_DATE.to_numpy(dtype='datetime64[D]').astype('int64')),'Validation date differs')
  m=Pipeline([('prep',make_preprocessor(clip=False)),
              ('clf',HistGradientBoostingClassifier(max_leaf_nodes=15,learning_rate=.05,max_iter=150,
                                     l2_regularization=1.0,early_stopping=False,random_state=SEED))])
  tic=time.perf_counter();m.fit(tr[FEATURES],tr.Y_4Q.to_numpy(dtype=np.int8))
  p=m.predict_proba(va[FEATURES])[:,1];y=va.Y_4Q.to_numpy(dtype=np.int8)
  with np.load(refbase/'predictions'/f'{HGB}__{name}.npz',allow_pickle=False) as z:ref=z['score']
  ref_ap=float(average_precision_score(y,ref));got_ap=float(average_precision_score(y,p))
  mae=float(np.mean(np.abs(p-ref)));maxdiff=float(np.max(np.abs(p-ref)))
  # Different versions may produce small numerical differences; stop rather than invent parity.
  status='COMPARABLE' if abs(ref_ap-got_ap)<.002 else 'NOT_PARITY_CHECKED_DO_NOT_CITE'
  meta.append({'fold':name,'train_rows':len(tr),'valid_rows':len(va),'reference_AP':ref_ap,
     'refitted_AP':got_ap,'mean_abs_probability_delta':mae,'max_abs_probability_delta':maxdiff,
     'fit_seconds':time.perf_counter()-tic,'parity_status':status})
  print(f'AP new={got_ap:.6f}, locked evidence={ref_ap:.6f}; status={status}',flush=True)
  require(status=='COMPARABLE',f'Fold {name} disagrees with locked evidence. Inspect sklearn version; NO importance results should be used.')
  # Full validation is the default. Optional max sample is a simple random sample
  # without changing class proportions by design; report sample prevalence.
  if args.max_validation_rows and len(va)>args.max_validation_rows:
   rng=np.random.default_rng(SEED)
   chosen=np.sort(rng.choice(len(va),size=args.max_validation_rows,replace=False))
   vx=va[FEATURES].iloc[chosen].reset_index(drop=True)
   vy=y[chosen]
  else:vx=va[FEATURES].copy().reset_index(drop=True);vy=y
  require(0<vy.sum()<len(vy),'Sample has no failures or only failures')
  base_ap=float(average_precision_score(vy,m.predict_proba(vx)[:,1]))
  arr=vx.to_numpy(dtype='float64',copy=True)
  for j,feature in enumerate(FEATURES):
   for repeat in range(args.repeats):
    rng=np.random.default_rng(SEED+1000*list(FOLDS).index(name)+100*j+repeat)
    q=arr.copy();q[:,j]=q[rng.permutation(len(q)),j]
    shifted=pd.DataFrame(q,columns=FEATURES)
    perm_ap=float(average_precision_score(vy,m.predict_proba(shifted)[:,1]))
    out.append({'fold':name,'feature':feature,'repeat':repeat,'valid_rows':len(vy),
      'positive_rows':int(vy.sum()),'baseline_AP':base_ap,'permuted_AP':perm_ap,
      'delta_AP':base_ap-perm_ap})
   print('  ',feature,'done',flush=True)
  pd.DataFrame(out).to_csv(args.out/'permutation_fold_repeats.csv',index=False)
  pd.DataFrame(meta).to_csv(args.out/'refit_reproduced_fold_metrics.csv',index=False)
 g=pd.DataFrame(out)
 if len(g):
  summ=(g.groupby('feature',as_index=False).agg(mean_delta_AP=('delta_AP','mean'),
     min_delta_AP=('delta_AP','min'),max_delta_AP=('delta_AP','max'),
     negative_count=('delta_AP',lambda x:int((x<0).sum())),n=('delta_AP','size'))
     .sort_values('mean_delta_AP',ascending=False))
  summ.to_csv(args.out/'permutation_importance_summary.csv',index=False)
  print('\n--- Top development-only descriptive permutation AP drops ---')
  print(summ.head(15).to_string(index=False))
 print('\nFinished. No test labels/scores were opened. Training fit was limited to registered development folds.')

def main():
 a=argparse.ArgumentParser(description=__doc__)
 a.add_argument('--dev',type=Path,required=True,help='ORIGINAL hash-matched development_primary_v2.parquet')
 a.add_argument('--prior-revision-dir',type=Path,required=True)
 a.add_argument('--out',type=Path,default=Path('part5_dev_importance_results'))
 a.add_argument('--folds',nargs='+',default=list(FOLDS),choices=list(FOLDS))
 a.add_argument('--repeats',type=int,default=2)
 a.add_argument('--max-validation-rows',type=int,default=0,
                help='0 uses ALL validation rows. If positive, subsampling is descriptive and changes AP base rate.')
 x=a.parse_args();require(1<=x.repeats<=10,'repeats outside reasonable range')
 run(x)
if __name__=='__main__':main()
