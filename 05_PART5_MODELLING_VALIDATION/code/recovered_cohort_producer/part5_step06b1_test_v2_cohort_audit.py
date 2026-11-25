#!/usr/bin/env python3
"""BFT65B Part5 / Step 06B1: construct & audit TEST V2 cohort, WITHOUT scoring.

Only prepares the previously fixed binary label policy, computes source-quarter
features using original audited Part4 code, and checks integrity. It DOES read
held-out test features and labels to materialize the cohort. It DOES NOT load or
score any model, compute predictive metrics, or select thresholds. Do not inspect
this cohort to change modelling choices. Run before the separate single-use test
scoring step and then preserve the Parquet SHA-256 as a data-contract artifact.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import platform
import sys
import zipfile
from pathlib import Path

PROTO_SHA = '994f72de6e2446916db8c2fcd36847c45cc68eb6fef5ef67f07acc0476c6d911'
LOCK_SHA = '919c84d44f4fcdf9a98bc83fd1d9fcd0315fe8c841ed579dc17f74314c3cdc6e'
MODEL_SHA = '0dac159b4400fa16f06de0918c012dc62fa80d4f7c0a117357b2251d82615b03'
STEP01_SHA = 'a651be686ca57dc65f9e59e444cab99088ce010247fed56d8986a0b7939cc763'
REG_SHA = '09efb2de4574f3abc278aa83ec66d8369d26330258518a7e1963cf810471c395'
DEV_SHA = 'd365ce25204a3dcace715db4cea259c94b1b1abba4822c7bcf2b050a1c7f6a73'
SOURCE_SHA = {
 'clean':'0d1837815820e93eb71508dabd6f48143e2b596b09453606ccf0070c3717e107',
 'pit':'3fce669406ff1898ac85d9c41c6385b7f8c6b27e29ecd041bb0a3c59f6337421',
 'failures':'a3e18c370f53c029e83708944bb91daf08ae5f664175f0fdd1bc389698c05ab3',
}
TEST_START=dt.date(2010,3,31)
TEST_END=dt.date(2025,6,30)
DEV_END=dt.date(2008,12,31)
CONFIRMED_NONFAILURE={
 'MERGER_OR_REORGANIZATION_NONFAILURE',
 'ASSISTED_OR_RESOLUTION_EXIT',
 'VOLUNTARY_CLOSURE_NONFAILURE',
}
FEATS=['log_assets','equity_to_assets','asset_log_growth_1q','asset_log_growth_4q',
 'nclnls_to_loans','loan_allowance_to_loans','cash_to_assets',
 'cash_and_securities_to_assets','deposits_to_assets','net_loans_to_assets',
 'roa_reported_percent','nimy_reported_percent','negative_equity_flag',
 'loss_flag_roa_negative','loan_denominator_invalid_flag']


def require(ok,reason):
    if not bool(ok):raise RuntimeError(reason)

def sha(path):
    d=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):d.update(block)
    return d.hexdigest()

def check(path, expected, label):
    path=Path(path)
    require(path.is_file(),f'Cannot find {label}: {path}')
    actual=sha(path)
    require(actual==expected,f'{label} HASH MISMATCH. STOP. expected {expected}, actual {actual}')
    return {'sha256':actual,'bytes':path.stat().st_size}


def self_test():
    # An independent reference truth table for primary labels (no test files).
    import pandas as pd
    import numpy as np
    records=[
      ('POSITIVE','UNKNOWN',1),
      ('NEGATIVE','UNKNOWN',0),
      ('COMPETING_EXIT_CENSORED','MERGER_OR_REORGANIZATION_NONFAILURE',0),
      ('COMPETING_EXIT_CENSORED','ASSISTED_OR_RESOLUTION_EXIT',0),
      ('COMPETING_EXIT_CENSORED','VOLUNTARY_CLOSURE_NONFAILURE',0),
      ('COMPETING_EXIT_CENSORED','ADVERSE_UNRESOLVED',None),
      ('INSUFFICIENT_FOLLOWUP_CENSORED','UNKNOWN',None),
      ('REVIEW_DATE_CONFLICT','UNKNOWN',None),
    ]
    labels=[]
    for status,exit_class,_ in records:
        labels.append(1 if status=='POSITIVE' else
                      0 if status=='NEGATIVE' or
                         (status=='COMPETING_EXIT_CENSORED' and exit_class in CONFIRMED_NONFAILURE)
                      else None)
    assert all((a is None and b is None) or a==b for a,(_,_,b) in zip(labels,records))
    require(len(FEATS)==15 and len(set(FEATS))==15,'Feature list malformed')
    require(dt.date(2008,12,31)+dt.timedelta(days=365) < TEST_START,
            'Development horizon/test split chronology wrong')
    print('STEP06B1 SELF-TEST PASS: policy truth table, calendar dates, 15 feature allowlist.',flush=True)


def run(args):
    import pandas as pd
    import numpy as np
    import polars as pl
    home=Path(__file__).resolve().parent
    require(not args.claim_file.exists(),
            'FINAL TEST EVALUATION CLAIM already exists: refuse cohort preparation after test scoring began')
    require(not args.out.exists(),'Output already exists. Refuse overwrite; preserve evidence and cohort.')
    hashes={
     'protocol':check(home/'part5_protocol_freeze.json',PROTO_SHA,'protocol'),
     'part4_reference':check(home/'part4_step01_reference_UNCHANGED.py',STEP01_SHA,'original feature/label source'),
     'registry':check(home/'part2_clean_review_bundle.zip',REG_SHA,'frozen event registry'),
     'lock':check(args.lock,LOCK_SHA,'FINAL_MODEL_LOCK'),
     'model':check(args.model,MODEL_SHA,'fitted locked model (hash only; NOT loaded)'),
     'development':check(args.development,DEV_SHA,'development V2'),
     **{key:check(getattr(args,key),val,key) for key,val in SOURCE_SHA.items()},
    }
    require(args.pretest_zip.is_file(),'Missing approved Step06A evidence ZIP')
    with zipfile.ZipFile(args.pretest_zip) as z:
        require(z.testzip() is None,'Step06A ZIP CRC failed')
        a=json.loads(z.read('part5_step06a_pretest_audit.json'))
        require(a['status']=='PASS_LOCK_MODEL_SOURCE_VERIFIED__TEST_UNOPENED','Step06A did not PASS')
        require(a['lock_sha256']==LOCK_SHA and a['model_sha256']==MODEL_SHA and
                a['protocol_sha256']==PROTO_SHA,'Step06A lock/model/protocol mismatch')
    hashes['step06a_pretest']={'sha256':sha(args.pretest_zip),'bytes':args.pretest_zip.stat().st_size}
    proto=json.loads((home/'part5_protocol_freeze.json').read_text(encoding='utf8'))
    lock=json.loads(Path(args.lock).read_text(encoding='utf8'))
    require(lock['final_estimator']['feature_names_in_dataframe_order']==FEATS,
            'Fitted feature order changed')
    require(proto['data_contract']['test_range']=='2010-03-31_to_2025-06-30',
            'Test range differs from preselection protocol')
    require(proto['data_contract']['merger_nonfailure'] is True and
            proto['data_contract']['assistance_nonfailure_in_primary'] is True,
            'Unexpected primary outcome policy')
    require(lock['alarm_policy']['raw_probability_threshold']==0.023971438944668057,
            'Changed alarm threshold; STOP')
    require(platform.python_version()=='3.13.7','Use the frozen Python3.13.7 environment')
    assert pl.__version__=='2.1.0',f'Polars changed: {pl.__version__}'
    # Load exact, audited Part4 Step01 functions, not a newly written or approximated feature builder.
    src=home/'part4_step01_reference_UNCHANGED.py'
    spec=importlib.util.spec_from_file_location('part4_exact_locked_builder',str(src))
    require(spec is not None and spec.loader is not None,'Cannot load verified Part4 reference')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    require(module.FEATURES is not None and set(module.FEATURES)==set(FEATS),'Features differ from frozen refit')
    require(module.TEST_START==TEST_START and module.MODEL_END==TEST_END,
            'Part4 original source dates inconsistent with protocol')
    registry,part2summary=module.load_registry(home/'part2_clean_review_bundle.zip')
    # Scan and filter test decision dates before expensive feature operations. Exact 1-quarter availability lag.
    base=module.prepare_source_columns(args.pit,args.clean).filter(
         (pl.col('DECISION_DATE')>=pl.lit(TEST_START)) &
         (pl.col('DECISION_DATE')<=pl.lit(TEST_END)))
    labelled=module.add_outcome_and_status(base.with_columns(module.feature_expressions()),registry)
    test=labelled.collect().sort(['DECISION_DATE','CERT'])
    require(test.height==364465,
            f'Test source cardinality changed: {test.height} expected 364465; STOP')
    require(test.select('CERT','DECISION_DATE').unique().height==test.height,
            'Duplicate CERT/decision date keys')
    require(test['SPLIT'].eq('test').all(),'Unexpected split within test cohort')
    require(test['DECISION_DATE'].min()==TEST_START and test['DECISION_DATE'].max()==TEST_END,
            'Test start or end quarter unexpectedly changed')
    require(test['DECISION_DATE'].n_unique()==62,'Expected 62 test decision quarters')
    badtime=int(test.filter(pl.col('SOURCE_REPDTE').is_null()|
        (pl.col('SOURCE_REPDTE')>=pl.col('DECISION_DATE'))|
        (pl.col('SOURCE_REPDTE').dt.offset_by('3mo').dt.month_end()!=pl.col('DECISION_DATE'))).height)
    require(badtime==0,f'Future/noncalendar source observations: {badtime}')
    horizon=pl.col('DECISION_DATE').dt.offset_by('1y').dt.month_end()
    badpos=int(test.filter((pl.col('LABEL_STATUS')=='POSITIVE') &
        ~((pl.col('FIRST_FAILURE_DATE')>pl.col('DECISION_DATE')) &
          (pl.col('FIRST_FAILURE_DATE')<=horizon))).height)
    require(badpos==0,f'Positive labels outside future four-quarter window: {badpos}')
    confirmed=((pl.col('LABEL_STATUS')=='COMPETING_EXIT_CENSORED') &
               pl.col('EXIT_CLASS').is_in(sorted(CONFIRMED_NONFAILURE)))
    test=test.with_columns([
       pl.when(pl.col('LABEL_STATUS')=='POSITIVE').then(pl.lit(1,dtype=pl.Int8))
       .when((pl.col('LABEL_STATUS')=='NEGATIVE')|confirmed).then(pl.lit(0,dtype=pl.Int8))
       .otherwise(pl.lit(None,dtype=pl.Int8)).alias('Y_PRIMARY_4Q'),
       pl.when(confirmed).then(pl.lit('CONFIRMED_NONFAILURE_EXIT_NEGATIVE'))
       .otherwise(pl.col('LABEL_STATUS')).alias('PRIMARY_LABEL_STATUS'),
    ])
    # Independent pandas interpretation of the SAME frozen label policy on EVERY test observation.
    checkdf=test.select('LABEL_STATUS','EXIT_CLASS','Y_PRIMARY_4Q').to_pandas()
    status=checkdf['LABEL_STATUS'].astype('string')
    exit_class=checkdf['EXIT_CLASS'].astype('string')
    y_ref=np.select([
       status.eq('POSITIVE').fillna(False).to_numpy(dtype=bool),
       (status.eq('NEGATIVE')|
         (status.eq('COMPETING_EXIT_CENSORED')&exit_class.isin(CONFIRMED_NONFAILURE))).fillna(False).to_numpy(dtype=bool)
    ],[1.0,0.0],default=np.nan)
    y_actual=pd.to_numeric(checkdf['Y_PRIMARY_4Q'],errors='coerce').to_numpy(dtype=float)
    mismatches=int((~np.isclose(y_ref,y_actual,rtol=0,atol=0,equal_nan=True)).sum())
    require(mismatches==0,f'Pandas/Polars label policy mismatch {mismatches}')
    legacy=test.filter(pl.col('Y_4Q').is_not_null())
    require(legacy.height==351327,'Legacy V1 test row count differs from Part4 baseline')
    require(int(legacy['Y_4Q'].sum())==1112,'V1 test positive count differs from pre-test census')
    require(int(legacy.filter(pl.col('Y_4Q')==1).select('CERT').n_unique())==341,
            'V1 test positive CERT count differs')
    primary=test.filter(pl.col('Y_PRIMARY_4Q').is_not_null())
    positives=int(primary['Y_PRIMARY_4Q'].sum())
    positive_certs=int(primary.filter(pl.col('Y_PRIMARY_4Q')==1).select('CERT').n_unique())
    require(primary.height>=legacy.height and positives==1112 and positive_certs==341,
            'V2 test sample changes known confirmed failure targets')
    need=['CERT','DECISION_DATE','SOURCE_REPDTE']+FEATS
    filtered=primary.select(need+[pl.col('Y_PRIMARY_4Q').alias('Y_4Q')])
    require(filtered.height==primary.height,'Test cohort dropped rows unexpectedly')
    require(set(filtered.columns)==set(need+['Y_4Q']),'Unexpected predictor/label columns')
    # Numeric fields permit genuine nulls; do NOT impute/fit/calibrate on test.
    invalid={f:int(filtered.filter(pl.col(f).cast(pl.Float64,strict=False).is_infinite()).height)
             for f in FEATS}
    require(not any(invalid.values()),f'Infinite test predictors: {invalid}')
    source_end=dt.date(2025,3,31)
    require(filtered['SOURCE_REPDTE'].max()==source_end,
            'Latest test source quarter violates reporting lag')
    require(not args.claim_file.exists(),'Final test already opened while B1 prepared')
    args.out.mkdir(parents=True,exist_ok=False)
    parquet=args.out/'test_primary_binary_v2_UNSCORED.parquet'
    filtered.write_parquet(parquet,compression='zstd',statistics=True,row_group_size=100000)
    status_counts=test.group_by('PRIMARY_LABEL_STATUS').agg(pl.len().alias('rows')).sort('PRIMARY_LABEL_STATUS')
    status_counts.write_csv(args.out/'primary_label_status_test_AUDIT_ONLY.csv')
    report={
       'stage':'PART5_STEP06B1_TEST_V2_COHORT_CONSTRUCTION_ONLY',
       'status':'PASS_PREPARED_NOT_SCORED',
       'test_features_and_labels_read_for_cohort_creation':True,
       'test_model_predict_called':False,
       'test_model_selection_performed':False,
       'test_threshold_or_hyperparameters_changed':False,
       'test_scored':False,
       'source_hashes':hashes,
       'new_cohort':{'filename':parquet.name,'sha256':sha(parquet),'bytes':parquet.stat().st_size,
           'all_test_source_rows':test.height,'primary_labelled_rows':primary.height,
           'primary_positive_rows':positives,'primary_negative_rows':int(primary.height-positives),
           'excluded_uncertain_rows':int(test.height-primary.height),
           'positive_distinct_CERTs':positive_certs,'test_quarters':int(test['DECISION_DATE'].n_unique()),
           'test_first_date':str(TEST_START),'test_last_date':str(TEST_END),
           'legacy_V1_labelled_rows':legacy.height,
           'confirmed_nonfailure_exit_rows_restored':int(test.filter(confirmed).height),
           'source_timing_violations':badtime,'outcome_label_oracle_mismatches':mismatches,
           'infinite_feature_cells':sum(invalid.values())},
       'frozen_lock_sha256':LOCK_SHA,'model_sha256':MODEL_SHA,'protocol_sha256':PROTO_SHA,
       'next_step':'Independent review this cohort contract; commit/tag frozen artifacts; then run a separate single-use FINAL scoring script exactly once.',
       'cautions':[
          'No model loading or inference is performed in Step06B1.',
          'Both test features and ground-truth outcomes are materialized for data-integrity purposes; do not use their distribution to change the locked model.',
          'This uses current FDIC source snapshots; not all historical publication vintages are reconstructed.',
          'The score/threshold must remain exactly as locked on development.'
       ]
    }
    fp=args.out/'part5_step06b1_cohort_audit.json'
    fp.write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    share=args.out/'SHARE_THIS_PART5_STEP06B1_COHORT_AUDIT.zip'
    with zipfile.ZipFile(share,'w',zipfile.ZIP_DEFLATED) as z:
        z.write(fp,arcname=fp.name)
        z.write(args.out/'primary_label_status_test_AUDIT_ONLY.csv',arcname='primary_label_status_test_AUDIT_ONLY.csv')
    print('STEP06B1 PASS: Test V2 cohort prepared, NO model inference and NO evaluation.')
    print('Keep local cohort:',parquet,'SHA256:',sha(parquet))
    print('Send audit ONLY:',share)
    print('DO NOT evaluate final test until Step06B1 audit is independently checked.')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--self-test',action='store_true')
    for k in ['lock','model','development','clean','pit','failures','pretest_zip','claim_file','out']:
        ap.add_argument('--'+k.replace('_','-'),type=Path)
    a=ap.parse_args()
    if a.self_test:self_test();return
    for k in ['lock','model','development','clean','pit','failures','pretest_zip','claim_file','out']:
        require(getattr(a,k) is not None,f'Missing --{k.replace("_","-")}')
    run(a)

if __name__=='__main__':
    try:main()
    except Exception as e:
        print('STEP06B1 FAILED (NO TEST SCORING RUN):',type(e).__name__,str(e),file=sys.stderr,flush=True)
        raise
