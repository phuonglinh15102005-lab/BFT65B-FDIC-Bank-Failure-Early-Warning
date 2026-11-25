#!/usr/bin/env python3
"""Development-only Spark MLlib-vs-original-registered-sklearn logistic numerical parity.

Reuses the exact frozen train-only 15 raw feature -> 30 transformed column
preprocessor (1st-99th training quantile clipping, median, RobustScaler,
3 flags and 15 fixed missingness indicators); evaluates ONLY validation 1989-90.
Unaltered registered original sklearn predictions bundled for reference.
Does not access test or replace originally selected HGB.
"""
from __future__ import annotations
import argparse,os,sys,json,hashlib,warnings
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.linear_model import LogisticRegression as SkLogistic
from sklearn.metrics import average_precision_score,roc_auc_score,brier_score_loss
from sklearn.exceptions import ConvergenceWarning
from part4_v2_train_only_pipeline import FEATURES,CONTINUOUS,BINARY,make_preprocessor
DEV_SHA='d365ce25204a3dcace715db4cea259c94b1b1abba4822c7bcf2b050a1c7f6a73'
C=0.1
SEED=20261114

def check(ok,msg):
 if not bool(ok):raise AssertionError(msg)
def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(4<<20),b''):h.update(b)
 return h.hexdigest()
def metric(y,p):
 return {'AP':float(average_precision_score(y,p)),'ROC_AUC':float(roc_auc_score(y,p)),'Brier':float(brier_score_loss(y,p))}

def coefficient_feature_names(active):
 """Names in actual ColumnTransformer order; metadata only, no estimator fit."""
 names=CONTINUOUS+BINARY+[f'missing_{f}' for f in FEATURES]
 indices=np.asarray(active)
 check(indices.ndim==1 and np.issubdtype(indices.dtype,np.integer),'Active indices must be integers')
 check(((indices>=0)&(indices<len(names))).all(),'Active index outside transformed matrix')
 check(len(set(indices.tolist()))==len(indices),'Duplicate active column indices')
 return [names[int(i)] for i in indices]

def main():
 arg=argparse.ArgumentParser();arg.add_argument('--dev',type=Path,required=True);arg.add_argument('--reference-dir',type=Path,required=True);arg.add_argument('--out',type=Path,required=True);a=arg.parse_args()
 check(sha(a.dev)==DEV_SHA,'Locked original development Parquet checksum mismatch')
 try:
  from pyspark.sql import SparkSession
  from pyspark.ml.feature import VectorAssembler
  from pyspark.ml.classification import LogisticRegression
  from pyspark.ml.functions import vector_to_array
  import pyspark
 except Exception as e:raise RuntimeError(f'Spark unavailable: {e}')
 a.out.mkdir(parents=True,exist_ok=True)
 dev=pd.read_parquet(a.dev)
 dev['DECISION_DATE']=pd.to_datetime(dev.DECISION_DATE)
 check(len(dev)==1231631 and int(dev.Y_4Q.sum())==9246,'Development cohort census mismatch')
 train=dev.loc[dev.DECISION_DATE<=pd.Timestamp('1987-12-31')]
 val=dev.loc[dev.DECISION_DATE.between('1989-03-31','1990-12-31')]
 check(len(train)==266127 and len(val)==125962,'Frozen train/validation boundaries disagree')
 expected_keys=np.load(a.reference_dir/'registered_fold1_keys.npz',allow_pickle=False)
 check(np.array_equal(val.CERT.to_numpy(dtype=np.int64),expected_keys['cert']),'Registered fold CERT sequence mismatch')
 check(np.array_equal(val.DECISION_DATE.to_numpy(dtype='datetime64[D]').astype('int64'),expected_keys['decision_day']),'Registered fold date sequence mismatch')
 check(np.array_equal(val.Y_4Q.to_numpy(dtype=np.int8),expected_keys['y']),'Registered labels mismatch')
 original=np.load(a.reference_dir/'registered_fold1_LR_scores.npz',allow_pickle=False)['score']
 prep=make_preprocessor(clip=True,lower=.01,upper=.99)
 xx=prep.fit_transform(train[FEATURES]);xv=prep.transform(val[FEATURES])
 assert xx.shape==(266127,30) and xv.shape==(125962,30)
 xx=np.asarray(xx,dtype=np.float64);xv=np.asarray(xv,dtype=np.float64)
 check(np.isfinite(xx).all() and np.isfinite(xv).all(),'Preprocessed numeric matrix contains nonfinite values')
 ytr=train.Y_4Q.to_numpy(dtype=np.int8);yval=val.Y_4Q.to_numpy(dtype=np.int8)
 # Exact archived sklearn objective, solver and convergence settings.
 original_skl=SkLogistic(C=C,class_weight=None,solver='lbfgs',max_iter=1000,tol=1e-4,random_state=SEED)
 with warnings.catch_warnings(record=True) as msgs:
  warnings.simplefilter('always',ConvergenceWarning);original_skl.fit(xx,ytr)
 orig_conv_warnings=[str(z.message) for z in msgs if issubclass(z.category,ConvergenceWarning)]
 p_original_refit=original_skl.predict_proba(xv)[:,1]
 archive_ap=average_precision_score(yval,original)
 ap_refit=average_precision_score(yval,p_original_refit)
 refit_maxabs=float(np.max(np.abs(p_original_refit-original)))
 check(abs(archive_ap-.3350101008454883)<1e-12,'Archived LR AP differs from registered record')
 # A refit discrepancy is an audit finding, not permission to modify the frozen model.
 refit_within_tolerance=bool(abs(ap_refit-archive_ap)<.0005)
 # Only columns truly constant IN TRAINING are excluded from the Spark solver.
 # Their original L2-optimal coefficient is zero; validate reduced sklearn metrics.
 variations=np.ptp(xx,axis=0)
 active=np.flatnonzero(variations>1e-12);dropped=np.flatnonzero(variations<=1e-12)
 check(len(active)>0,'All predictors are constant')
 xtr=xx[:,active]; xva=xv[:,active]
 # Tighter reference optimization on identical reduced design matrix.
 tight=SkLogistic(C=C,class_weight=None,solver='lbfgs',max_iter=2000,tol=1e-8,random_state=SEED)
 with warnings.catch_warnings(record=True) as w:
  warnings.simplefilter('always',ConvergenceWarning);tight.fit(xtr,ytr)
 tight_conv_warnings=[str(z.message) for z in w if issubclass(z.category,ConvergenceWarning)]
 ptight=tight.predict_proba(xva)[:,1]
 tight_ap=float(average_precision_score(yval,ptight))
 # IMPORTANT: numerically tighter convergence may materially change the ranking
 # even without changing the theoretical LR objective. Archive equivalence and
 # optimized-solver parity are distinct questions. LOG, do not prevent Spark fit.
 diagnostic={'registered_AP':float(archive_ap),'sklearn_registered_refit_AP':float(ap_refit),
       'sklearn_refit_vs_registered_AP_delta':float(ap_refit-archive_ap),
       'sklearn_refit_vs_registered_max_abs_p':refit_maxabs,
       'tight_reduced_sklearn_AP':tight_ap,
       'tight_vs_registered_AP_delta':float(tight_ap-archive_ap),
       'constant_columns_removed':dropped.tolist(), 'n_active_columns':int(len(active)),
       'warning_tight_differs_from_registered':bool(abs(tight_ap-archive_ap)>=.001),
       'registered_refit_within_AP_0p0005':refit_within_tolerance,
       'original_sklearn_convergence_warnings':orig_conv_warnings,
       'tight_sklearn_convergence_warnings':tight_conv_warnings,
       'scope':'Development 1989-90 only; no test predictions; no threshold changes.'}
 (a.out/'sklearn_pre_spark_diagnostics.json').write_text(json.dumps(diagnostic,indent=2,allow_nan=False)+'\n',encoding='utf-8')
 print('SKLEARN PRE-SPARK DIAGNOSTIC:',json.dumps(diagnostic,indent=2),flush=True)
 # Spark minimizes mean log-loss + 0.5*regParam*||beta||^2; sklearn minimizes
 # sum log-loss + 0.5/C*||beta||^2, so regParam = 1/(C * n_train).
 reg=1.0/(C*len(train));check(np.isclose(reg,1/(.1*266127)),'Incorrect Spark regularization mapping')
 colnames=[f'x{i:02d}' for i in range(len(active))]
 def stage(arr,labels,path):
  block=pd.DataFrame(arr,columns=colnames)
  block['rowid']=np.arange(len(block),dtype=np.int64)
  block['label']=labels.astype(np.float64)
  block.to_parquet(path,index=False)
 scratch=Path(os.environ.get('BFT65B_SPARK_STABLE_TMP',str(a.out/'spark_stable_tmp')))
 scratch.mkdir(parents=True,exist_ok=True)
 tr_path=scratch/'parity_development_train.parquet';va_path=scratch/'parity_development_validation.parquet'
 stage(xtr,ytr,tr_path);stage(xva,yval,va_path)
 spark=(SparkSession.builder.master('local[1]').appName('BFT65B_DEV_registered_LR_parity')
        .config('spark.ui.enabled','false').config('spark.sql.shuffle.partitions','2')
        .config('spark.local.dir',str(scratch)).config('spark.driver.memory','4g')
        .getOrCreate())
 spark.sparkContext.setLogLevel('WARN')
 try:
  assembler=VectorAssembler(inputCols=colnames,outputCol='features',handleInvalid='error')
  tr=assembler.transform(spark.read.parquet(str(tr_path))).select('rowid','label','features').cache()
  va=assembler.transform(spark.read.parquet(str(va_path))).select('rowid','label','features').cache()
  check(tr.count()==len(ytr) and va.count()==len(yval),'Spark row count differs from local dataset')
  lr=LogisticRegression(featuresCol='features',labelCol='label',regParam=reg,elasticNetParam=0.0,
      maxIter=2000,tol=1e-8,fitIntercept=True,standardization=False,probabilityCol='probability')
  fitted=lr.fit(tr)
  pred=fitted.transform(va).select('rowid',vector_to_array('probability').getItem(1).alias('p_spark')).toPandas().sort_values('rowid',kind='mergesort')
  check(len(pred)==len(yval) and np.array_equal(pred.rowid.to_numpy(),np.arange(len(yval))),'Spark prediction ordering changed')
  pp=pred.p_spark.to_numpy(dtype=float); check(np.isfinite(pp).all(),'Nonfinite probabilities')
  delta=np.abs(pp-ptight);met=metric(yval,pp);mref=metric(yval,ptight)
  dd={'Spark_vs_exact_sklearn_AP':abs(met['AP']-mref['AP']),'Spark_vs_exact_sklearn_AUC':abs(met['ROC_AUC']-mref['ROC_AUC']),'max_abs_probability_diff':float(delta.max()),'mean_abs_probability_diff':float(delta.mean()),
      'Spark_vs_registered_AP':abs(met['AP']-archive_ap),'Spark_vs_registered_max_abs_probability_diff':float(np.max(np.abs(pp-original)))}
  coeff=fitted.coefficients.toArray();skcoeff=tight.coef_[0]
  featnames=coefficient_feature_names(active)
  pd.DataFrame({'feature':featnames,'Spark_coef':coeff,'sklearn_coef':skcoeff}).to_csv(a.out/'lr_parity_coefficients.csv',index=False)
  pd.DataFrame({'CERT':val.CERT.to_numpy(),'DECISION_DATE':val.DECISION_DATE.to_numpy(),'Y_4Q':yval,
      'registered_sklearn_score':original,'local_refit_sklearn_score':p_original_refit,
      'tight_sklearn_score':ptight,'Spark_score':pp}).to_csv(a.out/'lr_parity_validation_scores.csv.gz',index=False,compression='gzip')
  result={'stage':'DEV_ONLY_SPARK_REGISTERED_LOGISTIC_PARITY','fold':'1989Q1_1990Q4','n_train':len(train),'n_valid':len(val),
       'raw_features':15,'transformed_features':30,'nonconstant_features':len(active),'constant_feature_indices':dropped.tolist(),
       'registered_C':C,'class_weight':None,'clipping':'TRAIN_1_99','imputation':'TRAIN_MEDIAN','scaler':'TRAIN_ROBUST',
       'sklearn_refit_AP':float(ap_refit),'registered_original_AP':float(archive_ap),'registered_reproduction_max_abs_score_error':refit_maxabs,
       'tight_reduced_AP':tight_ap,'tight_vs_registered_AP_delta':float(tight_ap-archive_ap),
       'tight_reference':mref,'Spark':met,'differences':dd,'Spark_regParam':reg,'Spark_elasticNetParam':0.0,
       'Spark_standardization':False,'Spark_tol':1e-8,'Spark_maxIter':2000,
       'max_coef_diff':float(np.max(abs(coeff-skcoeff))),'intercept_Spark':float(fitted.intercept),'intercept_sklearn':float(tight.intercept_[0]),
       'Spark_sklearn_AP_parity_within_0p001':bool(dd['Spark_vs_exact_sklearn_AP']<.001),
       'Spark_sklearn_max_abs_probability_below_0p001':bool(dd['max_abs_probability_diff']<.001),
       'Spark_sklearn_AUC_parity_within_0p001':bool(dd['Spark_vs_exact_sklearn_AUC']<.001),
       'note':'Dev-only reimplementation parity diagnostic. Spark and sklearn saw identical train-only transformed numeric matrices; neither HGB nor test was refitted or rescored. Intercept magnitude alone is not a ranking metric. Non-negligible differences require caution and should not be hidden.',
       'Spark_version':pyspark.__version__}
  (a.out/'lr_registered_parity.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
  print(json.dumps(result,indent=2),flush=True)
 finally:
  spark.stop()
if __name__=='__main__':main()
