#!/usr/bin/env python3
"""BFT65B Part5 / Step04: ONE development fold Spark MLlib pipeline demo.

Frozen 1989--1990 validation fold, equity-only logistic control.
Strictly development-only input; never reads test, never changes the chosen HGB.
Spark approximate quantiles and differently regularized LR are NOT claimed
coefficient-identical to scikit-learn. Independent row-key/method audit is retained.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import sys
import zipfile
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss

PROTOCOL_HASH = '994f72de6e2446916db8c2fcd36847c45cc68eb6fef5ef67f07acc0476c6d911'
DEV_HASH = 'd365ce25204a3dcace715db4cea259c94b1b1abba4822c7bcf2b050a1c7f6a73'
BASE_ZIP_HASH = '27d7ab92912ede60429bcdc1b02660bf4d4d9175a8cdb62e99653d1d6cace009'
FOLD='early_bank_stress'; TRAIN_END='1987-12-31'; VALID_START='1989-03-31'; VALID_END='1990-12-31'
N_TRAIN=266127; N_VALID=125962; P_TRAIN=2627; P_VALID=2796; N_POS_CERTS=932


def require(cond, message):
    if not bool(cond): raise AssertionError(message)


def sha256file(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as stream:
        for chunk in iter(lambda:stream.read(8<<20), b''):h.update(chunk)
    return h.hexdigest()


def parse_protocol(p):
    require(sha256file(p)==PROTOCOL_HASH, 'Protocol SHA differs; do not replace or amend silently')
    d=json.loads(Path(p).read_text(encoding='utf8'))
    folds={f['id']:f for f in d['validation']['folds']}
    require(FOLD in folds,'Baseline development fold not specified')
    f=folds[FOLD]
    for k,v in {'train_end':TRAIN_END,'validation_start':VALID_START,'validation_end':VALID_END}.items():
        require(f[k]==v,f'Frozen fold {k} mismatch')
    require(d['validation']['embargo_calendar_quarters']==4,'Embargo changed')
    require(d['data_contract']['input_shas']['development_primary_v2']==DEV_HASH,'Cohort changed')
    require(d['test_policy']['model_selection_on_test'] is False,'Test use forbidden')
    return d


def baseline_scores(zip_file):
    require(sha256file(zip_file)==BASE_ZIP_HASH,'Step01 baseline evidence SHA differs')
    with zipfile.ZipFile(zip_file) as z:
        require(z.testzip() is None,'Baseline evidence ZIP CRC failure')
        a=json.loads(z.read('part5_step01_audit.json'))
        require(a['protocol_sha256']==PROTOCOL_HASH,'Baseline protocol mismatch')
        require(a['development_parquet_sha256']==DEV_HASH,'Baseline cohort mismatch')
        raw=z.read('baseline_development_oof.csv')
        require(hashlib.sha256(raw).hexdigest()==a['outputs_sha256']['baseline_development_oof.csv'],
                'Baseline OOF CSV SHA differs')
        b=pd.read_csv(io.BytesIO(raw),usecols=['CERT','DECISION_DATE','Y_4Q','fold','p_failure'])
        b=b[b.fold==FOLD].copy()
        require(len(b)==N_VALID,'Baseline fold size mismatch')
        b['CERT']=b.CERT.astype('int64')
        b['DECISION_DATE']=pd.to_datetime(b.DECISION_DATE).dt.strftime('%Y-%m-%d')
        require(not b.duplicated(['CERT','DECISION_DATE']).any(),'Duplicate baseline keys')
        return b


def compare_predictions(spark_pred,baseline):
    require(set(['CERT','DECISION_DATE','Y_4Q','spark_score'])<=set(spark_pred),'Incomplete Spark output')
    spark_pred=spark_pred.copy()
    spark_pred['DECISION_DATE']=pd.to_datetime(spark_pred['DECISION_DATE']).dt.strftime('%Y-%m-%d')
    require(len(spark_pred)==N_VALID,'Unexpected Spark validation size')
    require(not spark_pred.duplicated(['CERT','DECISION_DATE']).any(),'Duplicate Spark keys')
    both=spark_pred.merge(baseline,on=['CERT','DECISION_DATE'],how='outer',validate='one_to_one',indicator=True,
                          suffixes=('_spark','_sklearn'))
    require(both._merge.eq('both').all() and len(both)==N_VALID,'Baseline/Spark keys not identical')
    require((both.Y_4Q_spark==both.Y_4Q_sklearn).all(),'Baseline/Spark labels not identical')
    require(both.spark_score.between(0,1).all() and np.isfinite(both.spark_score).all(), 'Invalid Spark scores')
    require(both.p_failure.between(0,1).all(),'Invalid sklearn scores')
    y=both.Y_4Q_spark.to_numpy(dtype='int8'); p=both.spark_score.to_numpy(dtype='float64'); q=both.p_failure.to_numpy(dtype='float64')
    stats={'rows':len(both),'positives':int(y.sum()),
           'spark_AP':float(average_precision_score(y,p)),
           'spark_ROC_AUC':float(roc_auc_score(y,p)),
           'spark_Brier':float(brier_score_loss(y,p)),
           'sklearn_AP':float(average_precision_score(y,q)),
           'sklearn_ROC_AUC':float(roc_auc_score(y,q)),
           'sklearn_Brier':float(brier_score_loss(y,q)),
           'score_pearson_correlation':float(np.corrcoef(p,q)[0,1]),
           'absolute_AP_delta':float(abs(average_precision_score(y,p)-average_precision_score(y,q))),
           'absolute_AUC_delta':float(abs(roc_auc_score(y,p)-roc_auc_score(y,q)))}
    require(stats['positives']==P_VALID,'Validation positive count differs')
    require(len(both.loc[both.Y_4Q_spark.eq(1),'CERT'].unique())==N_POS_CERTS,'Positive CERT count differs')
    # This is a ranking-parity sanity bound, not an assertion that algorithms/coefficients are identical.
    require(stats['score_pearson_correlation']>0.95,'Spark vs scikit probability ranking orientation differs')
    require(stats['absolute_AP_delta']<0.015,'Spark vs baseline AP gap too large; investigate Spark preprocessing')
    require(stats['absolute_AUC_delta']<0.015,'Spark vs baseline AUC gap too large; investigate Spark preprocessing')
    return stats,both


def pure_self_test():
    y=np.array([0,0,1,0,1,0],dtype='int8')
    cert=np.array([1,2,3,4,5,6]);date='1989-03-31'
    p=pd.DataFrame({'CERT':cert,'DECISION_DATE':date,'Y_4Q':y,'spark_score':[.01,.03,.92,.04,.89,.02]})
    b=pd.DataFrame({'CERT':cert,'DECISION_DATE':date,'Y_4Q':y,'p_failure':[.02,.06,.87,.08,.81,.04], 'fold':FOLD})
    # Independent harness logic for small data (avoid real-data count assertions)
    j=p.merge(b,on=['CERT','DECISION_DATE'],validate='one_to_one')
    require(len(j)==6 and np.array_equal(j.Y_4Q_x,j.Y_4Q_y),'Synthetic matching failed')
    require(average_precision_score(j.Y_4Q_x,j.spark_score)==1.,'Synthetic AP check failed')
    require(roc_auc_score(j.Y_4Q_x,j.spark_score)==1.,'Synthetic ROC check failed')
    bad=p.copy();bad.loc[0,'Y_4Q']=1
    jj=bad.merge(b,on=['CERT','DECISION_DATE'],validate='one_to_one')
    require(not np.array_equal(jj.Y_4Q_x,jj.Y_4Q_y),'Synthetic label canary not caught')
    print('PURE PYTHON SELF-TEST PASS: keys, label mismatch canary, metrics (no Spark used).')


def run(a):
    parse_protocol(a.protocol)
    require(a.dev.is_file() and a.dev.name=='development_primary_binary_v2.parquet','Development-only Parquet required')
    require(sha256file(a.dev)==DEV_HASH,'Development Parquet hash differs; refusing')
    base=baseline_scores(a.step01)
    from pyspark.sql import SparkSession, functions as F
    from pyspark.ml import Pipeline
    from pyspark.ml.feature import Imputer, VectorAssembler, RobustScaler
    from pyspark.ml.classification import LogisticRegression
    from pyspark.ml.functions import vector_to_array
    import pyspark
    spark=(SparkSession.builder.appName('BFT65B_PART5_DEV_ONLY_MLLIB')
           .master('local[4]')
           .config('spark.driver.memory','3g')
           .config('spark.sql.shuffle.partitions','8')
           .config('spark.ui.enabled','false')
           .getOrCreate())
    spark.sparkContext.setLogLevel('ERROR')
    try:
        s=spark.read.parquet(a.dev.resolve().as_uri()).select('CERT','DECISION_DATE','SOURCE_REPDTE','Y_4Q','SPLIT','equity_to_assets')
        require(s.filter(F.col('SPLIT')!='development').limit(1).count()==0,'Input contains nondevelopment split')
        require(s.count()==1231631,'Unexpected development row census')
        s=s.withColumn('decision_day',F.col('DECISION_DATE').cast('date'))
        s=s.withColumn('source_day',F.col('SOURCE_REPDTE').cast('date'))
        # Exact calendar quarter lag, not a 90-day or add_months approximation.
        q_dec=(F.year('decision_day')*F.lit(4)+F.floor((F.month('decision_day')-F.lit(1))/F.lit(3)))
        q_src=(F.year('source_day')*F.lit(4)+F.floor((F.month('source_day')-F.lit(1))/F.lit(3)))
        require(s.filter((q_dec-q_src)!=F.lit(1)).limit(1).count()==0,
                'Financial source must be exactly one prior CALENDAR quarter')
        require(s.filter(~F.month('decision_day').isin(3,6,9,12) | ~F.month('source_day').isin(3,6,9,12)
                         | (F.last_day('decision_day')!=F.col('decision_day'))
                         | (F.last_day('source_day')!=F.col('source_day'))).limit(1).count()==0,
                'Decision/source dates must both be quarter ends')
        train=s.filter(F.col('decision_day')<=F.lit(TRAIN_END).cast('date')).select('CERT','DECISION_DATE','Y_4Q','equity_to_assets').cache()
        valid=s.filter(F.col('decision_day').between(F.lit(VALID_START).cast('date'),F.lit(VALID_END).cast('date'))).select('CERT','DECISION_DATE','Y_4Q','equity_to_assets').cache()
        trn=train.agg(F.count('*').alias('n'),F.sum('Y_4Q').alias('p')).first()
        val=valid.agg(F.count('*').alias('n'),F.sum('Y_4Q').alias('p')).first()
        require((int(trn.n),int(trn.p))==(N_TRAIN,P_TRAIN),'Training fold count mismatch')
        require((int(val.n),int(val.p))==(N_VALID,P_VALID),'Validation fold count mismatch')
        # Deliberately independent MLlib preprocessing fit: only train sees Imputer/RobustScaler fit.
        # Spark uses approximate quantiles; scikit uses exact NumPy quantiles.
        ml=Pipeline(stages=[
            Imputer(strategy='median',inputCols=['equity_to_assets'],outputCols=['equity_imp'],relativeError=0.001),
            VectorAssembler(inputCols=['equity_imp'],outputCol='unscaled',handleInvalid='error'),
            RobustScaler(inputCol='unscaled',outputCol='features',withCentering=True,withScaling=True,
                         lower=0.25,upper=0.75,relativeError=0.001),
            LogisticRegression(featuresCol='features',labelCol='Y_4Q',predictionCol='prediction',
                               probabilityCol='probability',regParam=0.0,elasticNetParam=0.0,
                               fitIntercept=True,standardization=False,maxIter=300,tol=1e-6)
        ])
        print('Spark fitting on TRAINING fold only...',flush=True)
        fitted=ml.fit(train)
        print('Spark predicting on FROZEN validation fold...',flush=True)
        pred=(fitted.transform(valid)
                .select(F.col('CERT').cast('long').alias('CERT'),
                        F.date_format(F.col('DECISION_DATE').cast('date'),'yyyy-MM-dd').alias('DECISION_DATE'),
                        F.col('Y_4Q').cast('int').alias('Y_4Q'),
                        vector_to_array('probability')[1].alias('spark_score'))).toPandas()
        info,merged=compare_predictions(pred,base)
        scaler=fitted.stages[2]
        clf=fitted.stages[3]
        imp=fitted.stages[0]
        surrogate=imp.surrogateDF.collect()[0]
        info.update({'spark_mllib_version':pyspark.__version__,
                    'spark_logistic_coefficient':float(clf.coefficients[0]),
                    'spark_logistic_intercept':float(clf.intercept),
                    'spark_imputer_training_median':float(surrogate[0]),
                    'spark_robust_scaler_training_median':float(scaler.median[0]),
                    'spark_robust_scaler_training_iqr':float(scaler.range[0]),
                    'spark_logistic_num_iterations':int(clf.summary.totalIterations)})
        # Reference median must be computed only from training; exact PySpark median can be approximate.
        require(np.isfinite(info['spark_imputer_training_median']), 'Invalid imputer median')
        print('Spark MLlib verification metrics:',json.dumps(info,indent=2),flush=True)
        a.out.mkdir(parents=True,exist_ok=True)
        merged[['CERT','DECISION_DATE','Y_4Q_spark','spark_score','p_failure']].rename(columns={'Y_4Q_spark':'Y_4Q','p_failure':'sklearn_baseline_score'}).sort_values(['DECISION_DATE','CERT']).to_csv(a.out/'spark_vs_sklearn_dev_validation.csv',index=False)
        pd.DataFrame([info]).to_csv(a.out/'spark_mllib_fold_metrics.csv',index=False)
        report={'stage':'PART5_STEP04_DEVELOPMENT_ONLY_SPARK_MLLIB_DEMO',
                'status':'PASS_FOLD_PREPROCESSING_AND_RANKING_PARITY',
                'scope':'FIRST_DEVELOPMENT_FOLD_ONLY; NO FINAL TEST',
                'protocol_sha256':PROTOCOL_HASH,'development_sha256':DEV_HASH,
                'baseline_evidence_sha256':BASE_ZIP_HASH,'fold':FOLD,
                'train_through':TRAIN_END,'validation_start':VALID_START,'validation_end':VALID_END,
                'train_rows':N_TRAIN,'train_positives':P_TRAIN,'valid_rows':N_VALID,'valid_positives':P_VALID,
                'imputer_and_scaler_fitted_on':'train_only',
                'classifier':'Spark MLlib LogisticRegression - unregularized reference demo',
                'important_limitations':['This is a one-feature equity baseline port, not Spark HGB and not a new model selection trial.',
                  'Spark uses approximate median/IQR and unregularized objective; scikit comparator is the earlier C=1 L2 baseline.',
                  'Scores and coefficients need not be equal; ranking sanity bound AP/AUC<0.015 only.',
                  'No threshold changed; no test features or labels read.'],
                'metrics':info,'env':{'python':sys.version.split()[0], 'pandas':pd.__version__,
                                      'numpy':np.__version__, 'pyspark':pyspark.__version__, 'os':platform.platform()}}
        targets=['spark_vs_sklearn_dev_validation.csv','spark_mllib_fold_metrics.csv']
        report['output_sha256']={k:sha256file(a.out/k) for k in targets}
        audit=a.out/'part5_step04_audit.json';audit.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        with zipfile.ZipFile(a.out/'SHARE_THIS_PART5_STEP04_EVIDENCE.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=7) as z:
            for p in [audit]+[a.out/k for k in targets]:z.write(p,arcname=p.name)
        print('STEP04 PASS; share '+str(a.out/'SHARE_THIS_PART5_STEP04_EVIDENCE.zip'),flush=True)
        return info
    finally:
        spark.stop()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--self-test',action='store_true')
    p.add_argument('--protocol',type=Path)
    p.add_argument('--dev',type=Path)
    p.add_argument('--step01',type=Path)
    p.add_argument('--out',type=Path,default=Path('part5_step04_spark_outputs'))
    a=p.parse_args()
    if a.self_test: pure_self_test(); return
    for k in ('protocol','dev','step01'):
        require(getattr(a,k) is not None and getattr(a,k).is_file(),f'Missing {k}')
    run(a)

if __name__=='__main__':
    try:main()
    except Exception as ex:
        print('PART5 STEP04 FAIL:',repr(ex),file=sys.stderr)
        raise
