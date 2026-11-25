#!/usr/bin/env python3
"""REPAIRED COPY: legacy filename retained for import compatibility.
DEP now uses the same nonnegative numerator domain as the feature builder.
Historical oracle bytes and audit hashes remain in the original archive.

BFT65B Part 4 / Step 03: INDEPENDENT FULL-DEVELOPMENT LEAKAGE GATE.

Reads ONLY the labelled DEVELOPMENT feature table, Step01/02 audit manifests,
original PIT and clean source panels and Part2 event registry. DOES NOT OPEN
feature_label_test.parquet, fit a predictive model or select a threshold.

Checks ALL labelled development rows using an independent pandas feature oracle,
not the Polars functions that originally constructed the features. Recomputes
failure labels and reviews train-only preprocessing statistics on all 3 folds.
Tests whether perturbing future failure dates changes labels but leaves source-
only predictors unchanged. This is NOT a proof of historical FDIC data vintages.

Install: pandas==3.1.1 pyarrow==26.0.1 numpy==2.5.4 scikit-learn==1.9.1
Run with run_part4_step03_WINDOWS.bat beside Step02 script and Step01 output.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import traceback
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import RobustScaler

DEV_END = pd.Timestamp('2008-12-31')
FEATURES = [
    'log_assets', 'equity_to_assets', 'negative_equity_flag',
    'asset_log_growth_1q', 'asset_log_growth_4q',
    'nclnls_to_loans', 'loan_allowance_to_loans', 'cash_to_assets',
    'cash_and_securities_to_assets', 'deposits_to_assets',
    'net_loans_to_assets', 'roa_reported_percent', 'nimy_reported_percent',
    'loss_flag_roa_negative', 'loan_denominator_invalid_flag',
]
CONTINUOUS = [x for x in FEATURES if x not in {
    'negative_equity_flag','loss_flag_roa_negative','loan_denominator_invalid_flag'
}]
META = ['CERT','DECISION_DATE','SOURCE_REPDTE','SPLIT','Y_4Q']
RAW = ['CERT','DECISION_DATE','SOURCE_REPDTE','ASSET','EQ','NCLNLS','LNLSGR',
       'LNATRES','CHBAL','SC','DEP','LNLSNET','ROA','NIMY']
FOLDS = [
 ('early_bank_stress','1987-12-31','1989-03-31','1990-12-31'),
 ('post_stress_transition','1990-12-31','1992-03-31','1993-12-31'),
 ('global_financial_crisis','2005-12-31','2007-03-31','2008-12-31'),
]

def require(condition, message):
    if not bool(condition):
        raise AssertionError(message)

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()

def qid(dates):
    return dates.dt.year.astype('int32')*4 + ((dates.dt.month-1)//3).astype('int32')

def safe_ratio(n, d, nonnegative=False):
    n=pd.to_numeric(n,errors='coerce').astype('float64')
    d=pd.to_numeric(d,errors='coerce').astype('float64')
    mask=n.notna() & d.notna() & d.gt(0)
    if nonnegative: mask &= n.ge(0)
    return (n/d).where(mask)

def independent_features(raw: pd.DataFrame, clean: pd.DataFrame):
    """Independent pandas/quarter-ID specification of all 15 Step01 features."""
    src=raw.reset_index(drop=True).copy()
    src['_ROW']=np.arange(len(src),dtype='int64')
    asset=pd.to_numeric(src['ASSET'],errors='coerce').astype('float64')
    equity=pd.to_numeric(src['EQ'],errors='coerce').astype('float64')
    loans=pd.to_numeric(src['LNLSGR'],errors='coerce').astype('float64')
    cash=pd.to_numeric(src['CHBAL'],errors='coerce').astype('float64')
    sc=pd.to_numeric(src['SC'],errors='coerce').astype('float64')
    roa=pd.to_numeric(src['ROA'],errors='coerce').astype('float64')
    nimy=pd.to_numeric(src['NIMY'],errors='coerce').astype('float64')
    with np.errstate(divide='ignore',invalid='ignore',over='ignore'):
        calculated={
          'log_assets':np.log(asset.where(asset.gt(0))),
          'equity_to_assets':safe_ratio(equity,asset),
          'negative_equity_flag':equity.lt(0).astype(float).where(equity.notna()),
          'nclnls_to_loans':safe_ratio(src['NCLNLS'],loans,True),
          'loan_allowance_to_loans':safe_ratio(src['LNATRES'],loans,True),
          'cash_to_assets':safe_ratio(cash,asset,True),
          'cash_and_securities_to_assets':((cash+sc)/asset).where(
              cash.notna() & sc.notna() & cash.ge(0) & sc.ge(0) & asset.gt(0)),
          'deposits_to_assets':safe_ratio(src['DEP'],asset,nonnegative=True),
          'net_loans_to_assets':safe_ratio(src['LNLSNET'],asset,True),
          'roa_reported_percent':roa,
          'nimy_reported_percent':nimy,
          'loss_flag_roa_negative':roa.lt(0).astype(float).where(roa.notna()),
          'loan_denominator_invalid_flag':(loans.isna() | loans.le(0)).astype(float),
        }
    # Quarter-index equality, not row shift and not date arithmetic approximation.
    clean=clean[['CERT','REPDTE','ASSET']].copy()
    clean['REPDTE']=pd.to_datetime(clean['REPDTE'],errors='raise')
    clean['QID']=qid(clean['REPDTE'])
    require(not clean.duplicated(['CERT','QID']).any(),
            'Clean source has duplicate (CERT, quarter) keys')
    source_qid=qid(pd.to_datetime(src['SOURCE_REPDTE']))
    prior_base=clean[['CERT','QID','ASSET']].rename(columns={'ASSET':'PRIOR_ASSET'})
    for lag in (1,4):
        keys=src[['CERT','_ROW']].copy()
        keys['QID']=source_qid-lag
        matched=keys.merge(prior_base,on=['CERT','QID'],how='left',validate='m:1',sort=False)
        require(len(matched)==len(src),'Prior-quarter merge changed cardinality')
        matched=matched.sort_values('_ROW')
        require(np.array_equal(matched['_ROW'].to_numpy(),src['_ROW'].to_numpy()),
                'Prior-quarter merge changed row order')
        prior=pd.to_numeric(matched['PRIOR_ASSET'],errors='coerce').reset_index(drop=True)
        with np.errstate(divide='ignore',invalid='ignore',over='ignore'):
            calc=np.log(asset/prior).where(asset.gt(0) & prior.gt(0))
        calculated[f'asset_log_growth_{lag}q']=calc
    result=pd.DataFrame({k:pd.to_numeric(v,errors='coerce').to_numpy(dtype='float64')
                         for k,v in calculated.items()})
    require(set(result)==set(FEATURES), 'Independent feature oracle did not produce all 15 features')
    return result[FEATURES]

def load_registry(path:Path):
    with zipfile.ZipFile(path) as z:
        registry=pd.read_csv(io.BytesIO(z.read('review_AUDIT_ONLY/bank_event_registry_AUDIT_ONLY.csv')),
                             dtype={'CERT':'int64'},low_memory=False)
    require(not registry.CERT.duplicated().any(),'Duplicated CERT in registry')
    for c in ['FIRST_FAILURE_DATE','RISK_STOP_DATE','LAST_REPDTE']:
        registry[c]=pd.to_datetime(registry[c],errors='coerce')
    return registry[['CERT','FIRST_FAILURE_DATE','RISK_STOP_DATE','LAST_REPDTE']]

def label_oracle(dev,registry):
    j=dev[['CERT','DECISION_DATE','Y_4Q']].merge(registry,on='CERT',how='left',validate='m:1',sort=False)
    require(len(j)==len(dev),'Registry join changed row count')
    D=j['DECISION_DATE']; H=D+pd.DateOffset(years=1)
    F=j['FIRST_FAILURE_DATE']; S=j['RISK_STOP_DATE']; L=j['LAST_REPDTE']
    conflict=F.notna() & S.notna() & (S<F)
    post=F.notna() & F.le(D)
    positive=F.notna() & F.gt(D) & F.le(H)
    competing=S.notna() & S.gt(D) & S.le(H)
    observed=(S.notna() & S.gt(H)) | L.ge(H)
    is_pos=~conflict & ~post & positive
    is_neg=~conflict & ~post & ~positive & ~competing & observed
    expected=np.full(len(j),-1,dtype='int8')
    expected[is_neg.to_numpy()]=0
    expected[is_pos.to_numpy()]=1
    return expected

def check_preprocessing(dev,fold_csv,stats_csv):
    fold_ref=pd.read_csv(fold_csv).set_index('fold')
    stat_ref=pd.read_csv(stats_csv).set_index(['fold','feature'])
    rows=[]; deviations=[]
    for name,end,start,finish in FOLDS:
        t_end,v_start,v_end=map(pd.Timestamp,(end,start,finish))
        gap=v_start.to_period('Q').ordinal-t_end.to_period('Q').ordinal-1
        require(gap>=4 and v_end<=DEV_END, f'Invalid fold-gap dates: {name}')
        train=dev.loc[dev['DECISION_DATE'].le(t_end)]
        valid=dev.loc[dev['DECISION_DATE'].between(v_start,v_end)]
        removed=dev.loc[(dev['DECISION_DATE']>t_end) & (dev['DECISION_DATE']<v_start)]
        ref=fold_ref.loc[name]
        exact={'train_rows':len(train),'train_positive_rows':int(train.Y_4Q.sum()),
               'train_positive_certs':int(train.loc[train.Y_4Q==1,'CERT'].nunique()),
               'validation_rows':len(valid),'validation_positive_rows':int(valid.Y_4Q.sum()),
               'validation_positive_certs':int(valid.loc[valid.Y_4Q==1,'CERT'].nunique()),
               'gap_rows_excluded':len(removed),'preprocessing_fit_rows':len(train),
               'gap_quarters':gap, 'output_dimensions':30}
        for key,value in exact.items():
            require(int(ref[key])==value,f'{name}: {key}: observed {value}, audit {ref[key]}')
        require(str(ref['validation_only_transformed']).lower()=='true',
                f'{name}: validation-only transform not confirmed')
        require(str(ref['test_dataset_opened']).lower()=='false',
                f'{name}: the referenced audit reports test access')
        # Refit independently, using ONLY the past train fold, never validation or test.
        median=SimpleImputer(strategy='median',keep_empty_features=True)
        X=median.fit_transform(train[CONTINUOUS])
        scaler=RobustScaler(quantile_range=(25,75)).fit(X)
        for i,feature in enumerate(CONTINUOUS):
            z=stat_ref.loc[(name,feature)]
            actual={'training_impute_median':float(median.statistics_[i]),
                    'train_scaled_center':float(scaler.center_[i]),
                    'train_scaled_IQR_or_fallback':float(scaler.scale_[i]),
                    'train_missing':int(train[feature].isna().sum()),
                    'validation_missing':int(valid[feature].isna().sum())}
            for metric,value in actual.items():
                rec=float(z[metric]); atol=1e-8; rtol=1e-6
                require(np.isclose(value,rec,atol=atol,rtol=rtol),
                        f'{name}/{feature}: {metric} changed ({value} vs {rec})')
                deviations.append({'fold':name,'feature':feature,'statistic':metric,
                                   'recalculated':value,'recorded':rec})
        rows.append({'fold':name,**exact,'training_median_and_scale_checks':len(CONTINUOUS)*3})
    return rows,deviations

def audit(args):
    for p in (args.development,args.pit,args.clean,args.registry,args.step01_summary,
              args.step02_audit,args.folds,args.stats):
        require(p.is_file(),f'Missing required input: {p}')
    require(args.development.name=='feature_label_development.parquet',
            'ONLY development feature Parquet is allowed')
    s01=json.loads(args.step01_summary.read_text(encoding='utf-8'))
    s02=json.loads(args.step02_audit.read_text(encoding='utf-8'))
    require(s02['status']=='PASS','Step02 did not report PASS')
    actual_hashes={'development':sha256(args.development),'clean':sha256(args.clean),
                   'pit':sha256(args.pit),'registry':sha256(args.registry),
                   'step01_summary':sha256(args.step01_summary)}
    expected={'development':s02['development_parquet_sha256'],
              'clean':s01['input_sha256']['panel_clean'],
              'pit':s01['input_sha256']['panel_pit'],
              'registry':s02['registry_zip_sha256'],
              'step01_summary':s02['step01_summary_sha256']}
    require(actual_hashes==expected,f'Input snapshot hashes differ: {actual_hashes} vs {expected}')
    print('[1/5] Read sealed DEVELOPMENT feature table; validate keys and timing...',flush=True)
    dev=pd.read_parquet(args.development,engine='pyarrow')
    require(set(dev.columns)==set(META+FEATURES),'Model feature schema is not the strict allowlist')
    for c in ('DECISION_DATE','SOURCE_REPDTE'):
        dev[c]=pd.to_datetime(dev[c],errors='raise')
    require(dev['SPLIT'].eq('development').all(),'Non-development record in development file')
    require(dev['DECISION_DATE'].le(DEV_END).all(),'Post-development decision found')
    require(not dev.duplicated(['CERT','DECISION_DATE']).any(),'Duplicate development decision keys')
    require(dev['DECISION_DATE'].dt.is_quarter_end.all() and dev['SOURCE_REPDTE'].dt.is_quarter_end.all(),
            'Decision/source dates not quarter-ends')
    require(((qid(dev['DECISION_DATE'])-qid(dev['SOURCE_REPDTE']))==1).all(),
            'Source reports are not exactly one calendar quarter before decisions')
    require(dev.Y_4Q.notna().all() and dev.Y_4Q.isin([0,1]).all(),'Unknown model labels detected')
    require(len(dev)==int(s02['development']['rows']),'Development row count changed')
    require(int(dev.Y_4Q.sum())==int(s02['development']['positive_rows']),'Positive count changed')
    require(int(dev.loc[dev.Y_4Q==1,'CERT'].nunique())==int(s02['development']['positive_certs']),
            'Positive CERT count changed')
    for feature in FEATURES:
        x=pd.to_numeric(dev[feature],errors='coerce').to_numpy(dtype='float64')
        require(not np.isinf(x).any(),f'Infinite feature present: {feature}')
    print('[2/5] Independent pandas reconstruction of ALL 15 features...',flush=True)
    pit=pd.read_parquet(args.pit,columns=RAW,engine='pyarrow')
    pit['DECISION_DATE']=pd.to_datetime(pit['DECISION_DATE'],errors='raise')
    pit['SOURCE_REPDTE']=pd.to_datetime(pit['SOURCE_REPDTE'],errors='raise')
    pit=pit.loc[pit['DECISION_DATE'].le(DEV_END)].copy()
    require(not pit.duplicated(['CERT','DECISION_DATE']).any(),'PIT development source keys are duplicated')
    # No model preprocessing is fitted; outside-development financial rows are discarded.
    joined=dev[['CERT','DECISION_DATE','SOURCE_REPDTE']+FEATURES].merge(
        pit,on=['CERT','DECISION_DATE'],how='left',validate='1:1',sort=False,
        suffixes=('','_PIT'),indicator=True)
    require(len(joined)==len(dev),'Source join changed development row count')
    require(joined['_merge'].eq('both').all(),'Development feature key is absent from PIT')
    require(joined['SOURCE_REPDTE'].eq(joined['SOURCE_REPDTE_PIT']).all(),
            'Source reporting dates disagree')
    clean=pd.read_parquet(args.clean,columns=['CERT','REPDTE','ASSET'],engine='pyarrow')
    clean['REPDTE']=pd.to_datetime(clean['REPDTE'],errors='raise')
    clean=clean.loc[clean['REPDTE'].le(DEV_END)].copy()
    expected_X=independent_features(joined,clean)
    mismatches={}; missing_counts={}
    for f in FEATURES:
        actual=pd.to_numeric(joined[f],errors='coerce').to_numpy(dtype='float64')
        exp=expected_X[f].to_numpy(dtype='float64')
        same=np.isclose(actual,exp,rtol=1e-8,atol=1e-9,equal_nan=True)
        mismatches[f]=int(np.count_nonzero(~same))
        missing_counts[f]=int(np.isnan(actual).sum())
    require(not any(mismatches.values()),f'Feature mismatches in full development: {mismatches}')
    print('[3/5] Independent label oracle and future-outcome perturbation...',flush=True)
    registry=load_registry(args.registry)
    expected_labels=label_oracle(dev,registry)
    mismatch_labels=int(np.count_nonzero(expected_labels != dev.Y_4Q.to_numpy(dtype='int8')))
    require(mismatch_labels==0,f'Full development label discrepancies: {mismatch_labels}')
    poisoned=registry.copy()
    poisoned.loc[poisoned.FIRST_FAILURE_DATE.notna(),'FIRST_FAILURE_DATE'] += pd.DateOffset(years=1)
    altered=label_oracle(dev,poisoned)
    altered_rows=int(np.count_nonzero(expected_labels != altered))
    require(altered_rows>0,'Future-event perturbation did not affect any outcome labels')
    # The independent X oracle takes only PIT/clean financial source fields;
    # zero registry fields are inputs, while deliberately altered labels differ.
    require(set(FEATURES).isdisjoint(set(registry.columns)),'Event fields among model features')
    print('[4/5] Independently recalculate TRAIN-ONLY preprocessing across folds...',flush=True)
    folds,statistics=check_preprocessing(dev,args.folds,args.stats)
    print('[5/5] Save attestable outputs; FINAL TEST FEATURE FILE NOT OPENED...',flush=True)
    report={'status':'PASS_INDEPENDENT_FULL_DEVELOPMENT',
            'development_rows':len(dev),'positive_bank_quarters':int(dev.Y_4Q.sum()),
            'distinct_failing_certs':int(dev.loc[dev.Y_4Q==1,'CERT'].nunique()),
            'source_lag_exact_one_quarter':True,'full_rows_feature_compared':len(dev),
            'features_checked':len(FEATURES),'feature_mismatch_counts':mismatches,
            'all_development_labels_audited':len(dev),'label_mismatch_count':mismatch_labels,
            'future_failure_perturbation_changed_label_rows':altered_rows,
            'financial_feature_oracle_uses_event_registry':False,
            'final_test_feature_file_opened':False,'test_predictions_generated':False,
            'training_folds_checked':len(folds),'preprocessing_statistics_checked':len(statistics),
            'source_hashes':actual_hashes,
            'limitations':['An independent source-only oracle tests formula correctness but does not establish exact historical FDIC release vintages.',
                           'Event dates from present-day historical registry are used only to construct labels and censoring.',
                           'The experiment does not test model accuracy, test-set metrics or threshold selection.',
                           'Source Parquet scanning can physically read mixed-year row groups; only development rows participate in this audit.']}
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'part4_step03_leakage_gate.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    pd.DataFrame([{'feature':f,'full_development_mismatches':mismatches[f],
                   'development_missing':missing_counts[f]} for f in FEATURES]).to_csv(
                   args.output/'full_feature_audit.csv',index=False)
    pd.DataFrame(folds).to_csv(args.output/'fold_recheck.csv',index=False)
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ('development','pit','clean','registry','step01_summary','step02_audit','folds','stats'):
        parser.add_argument('--'+arg.replace('_','-'),type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    try:
        result=audit(a)
        print('PASS: '+json.dumps({k:result[k] for k in ('development_rows','all_development_labels_audited',
             'full_rows_feature_compared','future_failure_perturbation_changed_label_rows')},indent=2))
        with zipfile.ZipFile(a.output/'SHARE_THIS_PART4_STEP03_EVIDENCE.zip','w',zipfile.ZIP_DEFLATED) as z:
            for file in ('part4_step03_leakage_gate.json','full_feature_audit.csv','fold_recheck.csv'):
                z.write(a.output/file,arcname=file)
        print('SEND: '+str(a.output/'SHARE_THIS_PART4_STEP03_EVIDENCE.zip'))
    except Exception as e:
        error={'status':'FAIL','error_type':type(e).__name__,'message':str(e),
               'traceback':traceback.format_exc(),'test_file_opened':False}
        (a.output/'part4_step03_ERROR.json').write_text(json.dumps(error,indent=2),encoding='utf-8')
        print('FAILED: '+str(e),flush=True)
        print('ERROR LOG: '+str(a.output/'part4_step03_ERROR.json'),flush=True)
        raise
if __name__=='__main__':
    main()
