#!/usr/bin/env python3
"""One-time held-out evaluation of the previously frozen HGB model.

This script must be run exactly once on the original frozen cohort. No fitting,
calibration, threshold search, or feature selection occurs here. It requires
frozen exact byte hashes and writes an exclusive on-disk claim BEFORE the
only model predict_proba call. Validation of the unscored cohort is allowed
before the claim (Step06B1 already accessed test outcome labels). If anything fails after the claim, preserve
all files and seek review; DO NOT remove the claim or repeat the test.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.metadata as metadata
import json
import math
import os
from pathlib import Path
import platform
import sys
import zipfile

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss, log_loss

PROTO_SHA = '994f72de6e2446916db8c2fcd36847c45cc68eb6fef5ef67f07acc0476c6d911'
PREP_SHA = '168a08f0e3ffb0de3fa9e12e00c6671172a4ecb952fd8f67fc4254469f31b9a3'
LOCK_SHA = '919c84d44f4fcdf9a98bc83fd1d9fcd0315fe8c841ed579dc17f74314c3cdc6e'
MODEL_SHA = '0dac159b4400fa16f06de0918c012dc62fa80d4f7c0a117357b2251d82615b03'
COHORT_SHA = '15ee908a4faf197dba8787821b8fd83bf2c7de5da2a325939b5b5e078a348298'
FAILURES_SHA = 'a3e18c370f53c029e83708944bb91daf08ae5f664175f0fdd1bc389698c05ab3'
PRETEST_SHA = 'b8b51563e71ee36906aeeb834a36fe6f24ea163a3a0f3f9b5fc89e5810245d39'
B1_SHA = '8e1c4c544c24c1a85c952c03d90540a0915e5764437676384bf242b865c26022'
THRESHOLD = 0.023971438944668057
FEATS = [
 'log_assets','equity_to_assets','asset_log_growth_1q','asset_log_growth_4q',
 'nclnls_to_loans','loan_allowance_to_loans','cash_to_assets',
 'cash_and_securities_to_assets','deposits_to_assets','net_loans_to_assets',
 'roa_reported_percent','nimy_reported_percent','negative_equity_flag',
 'loss_flag_roa_negative','loan_denominator_invalid_flag',
]
TEST_START = pd.Timestamp('2010-03-31')
TEST_END = pd.Timestamp('2025-06-30')


def require(ok, message):
    if not bool(ok):
        raise RuntimeError(message)


def sha(path):
    h = hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):
            h.update(b)
    return h.hexdigest()


def verify(path, expected, what):
    p=Path(path)
    require(p.is_file(),f'Cannot find {what}: {p}')
    digest=sha(p)
    require(digest==expected,f'{what} SHA256 MISMATCH; STOP. expected {expected}, got {digest}')
    return {'sha256':digest,'bytes':p.stat().st_size}


def quarter_index(d):
    if isinstance(d,pd.Series):
        d=pd.to_datetime(d,errors='coerce')
        return d.dt.year*4+(d.dt.month-1)//3
    d=pd.to_datetime(d,errors='coerce')
    return d.year*4+(d.month-1)//3


def metric_row(frame, label):
    yy=frame['Y_4Q'].to_numpy(dtype=np.int8)
    pp=frame['score'].to_numpy(dtype=np.float64)
    n=len(yy)
    positive=int(yy.sum())
    out={'segment':label,'rows':int(n),'positives':positive,'negatives':int(n-positive),
         'prevalence':float(positive/n) if n else None,
         'mean_predicted_probability':float(pp.mean()) if n else None}
    if not n:
        out.update({k:None for k in ['average_precision','roc_auc','brier_score','log_loss','ap_divided_by_prevalence']})
        return out
    ap=float(average_precision_score(yy,pp)) if positive else None
    auc=float(roc_auc_score(yy,pp)) if positive and positive<n else None
    out.update({'average_precision':ap,'roc_auc':auc,
                'brier_score':float(brier_score_loss(yy,pp)),
                'log_loss':float(log_loss(yy,np.clip(pp,1e-15,1-1e-15),labels=[0,1])),
                'ap_divided_by_prevalence':ap/(positive/n) if positive and ap is not None else None})
    return out


def failure_event_table(path):
    d=pd.read_parquet(path)
    d.columns=[str(c).upper() for c in d.columns]
    required={'CERT','RESTYPE','FAILDATE'}
    require(required<=set(d.columns),f'FDIC failures file lacks {required-set(d.columns)}')
    d=d[d['RESTYPE'].astype('string').str.upper().eq('FAILURE').fillna(False)].copy()
    d['CERT']=pd.to_numeric(d['CERT'],errors='coerce')
    d['FAILDATE']=pd.to_datetime(d['FAILDATE'],errors='coerce')
    d=d.dropna(subset=['CERT','FAILDATE'])
    d['CERT']=d['CERT'].astype('int64')
    d=d.sort_values(['CERT','FAILDATE'],kind='mergesort').drop_duplicates('CERT',keep='first')
    return d[['CERT','FAILDATE']]


def check_outcomes(frame,events):
    d=frame[['CERT','DECISION_DATE','Y_4Q']].merge(events,on='CERT',how='left',validate='many_to_one')
    diff=(quarter_index(d['FAILDATE'])-quarter_index(d['DECISION_DATE']))
    within=diff.between(1,4).fillna(False)
    pos=d['Y_4Q'].eq(1)
    require(bool((within==pos).all()),
            f'Test label and independent FDIC first failure date disagree in {int((within!=pos).sum())} rows')
    return {'compared_rows':len(d),'positive_rows_confirmed':int(pos.sum()),
            'positive_distinct_certs':int(d.loc[pos,'CERT'].nunique()),'mismatches':0}


def annual_alert_policy(frame,events,threshold):
    """Exactly Step03 policy: first flagged quarter per (CERT, year), true only if y=1.

    Threshold is frozen, not searched. Events are first FDIC failures and are
    credited once per CERT (even if alerted in multiple calendar years).
    """
    d=frame.copy()
    d['year']=d['DECISION_DATE'].dt.year.astype('int16')
    flagged=d[d['score']>=threshold].copy()
    flagged=flagged.sort_values(['CERT','year','DECISION_DATE','score'],
                                 ascending=[True,True,True,False],kind='mergesort')
    alerts=flagged.drop_duplicates(['CERT','year'],keep='first').copy()
    require(not alerts.duplicated(['CERT','year']).any(),'Duplicate annual alerts after first-quarter rule')
    true_first=alerts.loc[alerts['Y_4Q'].eq(1)].copy()
    detected=set(true_first['CERT'].astype('int64'))
    event_positive=set(d.loc[d['Y_4Q'].eq(1),'CERT'].astype('int64'))
    require(detected<=event_positive,'Detected events outside positive population')
    true_first=true_first.merge(events,on='CERT',how='left',validate='many_to_one')
    if len(true_first):
        true_first['lead_quarters']=(quarter_index(true_first['FAILDATE'])-
                                     quarter_index(true_first['DECISION_DATE'])).astype('int64')
        require(true_first['lead_quarters'].between(1,4).all(),
                'Event lead time outside horizon')
    earliest=true_first.sort_values(['CERT','DECISION_DATE'],kind='mergesort').drop_duplicates('CERT')
    pos_events=d[d['Y_4Q'].eq(1)][['CERT']].drop_duplicates().merge(events,on='CERT',how='left',validate='one_to_one')
    pos_events['detected']=pos_events['CERT'].isin(detected)
    first_map=earliest.set_index('CERT')[['DECISION_DATE','lead_quarters']]
    pos_events['first_valid_alert_date']=pos_events['CERT'].map(first_map['DECISION_DATE'])
    pos_events['lead_quarters']=pos_events['CERT'].map(first_map['lead_quarters'])
    n_events=len(event_positive)
    n_detected=len(detected)
    fp=int((alerts['Y_4Q']==0).sum())
    summary={
      'threshold':float(threshold),
      'positive_bank_quarter_alerts':int((flagged['Y_4Q']==1).sum()),
      'all_bank_quarter_alerts':int(len(flagged)),
      'alerted_cert_years':int(len(alerts)),
      'false_alert_cert_years':fp,
      'true_first_alert_cert_years':int((alerts['Y_4Q']==1).sum()),
      'total_failure_certs':int(n_events),
      'detected_failure_certs':int(n_detected),
      'missed_failure_certs':int(n_events-n_detected),
      'event_detection_rate':float(n_detected/n_events) if n_events else None,
      'median_lead_quarters':float(earliest['lead_quarters'].median()) if n_detected else None,
      'p25_lead_quarters':float(earliest['lead_quarters'].quantile(.25)) if n_detected else None,
      'p75_lead_quarters':float(earliest['lead_quarters'].quantile(.75)) if n_detected else None,
      'distinct_cert_years':int(d[['CERT','year']].drop_duplicates().shape[0]),
    }
    require(summary['alerted_cert_years']==summary['false_alert_cert_years']+summary['true_first_alert_cert_years'],
            'Annual alert breakdown does not reconcile')
    require(summary['total_failure_certs']==summary['detected_failure_certs']+summary['missed_failure_certs'],
            'Failure-event breakdown does not reconcile')
    return summary,alerts,pos_events


def quarterly_capacity_1pct(frame):
    """Diagnostic top 1% WITHIN each quarter, NOT the locked cost threshold."""
    rows=[]
    for dt,d in frame.groupby('DECISION_DATE',sort=True):
        n=len(d)
        k=int(math.ceil(.01*n))
        leaders=d.sort_values(['score','CERT'],ascending=[False,True],kind='mergesort').head(k)
        tp=int(leaders['Y_4Q'].sum())
        rows.append({'quarter':dt.date().isoformat(),'banks':n,'alerts':k,
                     'true_positive_bank_quarters':tp,'false_positive_bank_quarters':k-tp,
                     'precision':tp/k if k else None,
                     'recall':tp/int(d['Y_4Q'].sum()) if d['Y_4Q'].sum() else None})
    return pd.DataFrame(rows)


def wilson_ci(k,n,z=1.959963984540054):
    if not n:return (None,None)
    p=k/n;den=1+z*z/n
    center=(p+z*z/(2*n))/den
    width=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/den
    return (max(0.,center-width),min(1.,center+width))


def json_ready(obj):
    if isinstance(obj,(np.integer,)):return int(obj)
    if isinstance(obj,(np.floating,)):return float(obj)
    if isinstance(obj,pd.Timestamp):return obj.isoformat()
    if isinstance(obj,Path):return str(obj)
    if isinstance(obj,dict):return {str(k):json_ready(v) for k,v in obj.items()}
    if isinstance(obj,(list,tuple)):return [json_ready(x) for x in obj]
    if isinstance(obj,(float,)) and not np.isfinite(obj):return None
    return obj


def self_test():
    # This self-test uses synthetic scores ONLY; it does not read any user files.
    dd=pd.to_datetime(['2020-03-31','2020-06-30','2020-09-30','2020-03-31','2020-06-30','2021-03-31'])
    data=pd.DataFrame({'CERT':[10,10,10,11,11,12],
        'DECISION_DATE':dd,'Y_4Q':[0,1,1,0,0,1],
        'score':[.9,.8,.7,.1,.2,.6]})
    ev=pd.DataFrame({'CERT':[10,12], 'FAILDATE':pd.to_datetime(['2021-03-31','2021-09-30'])})
    pol,alert,events=annual_alert_policy(data,ev,.5)
    # CERT 10 first alarm in 2020Q1 (y=0), later positive Q2 does not count.
    assert pol['all_bank_quarter_alerts']==4
    assert pol['alerted_cert_years']==2
    assert pol['false_alert_cert_years']==1
    assert pol['detected_failure_certs']==1
    assert pol['missed_failure_certs']==1
    assert pol['median_lead_quarters']==2.0
    assert len(events)==2
    # Quiet quarters, single-class metrics, capacity per-quarter and CI.
    m=metric_row(data,'synthetic'); assert 0<=m['average_precision']<=1
    cm=quarterly_capacity_1pct(data);assert cm['alerts'].sum()==4
    lo,hi=wilson_ci(1,2);assert 0<lo<.5<hi<1
    print('STEP06B2 SELF-TEST PASS: first annual alert, event credit, metrics, top-1%-quarter.',flush=True)


def _claim_atomic(path,payload):
    """Create an exclusive on-disk marker. Never remove automatically."""
    path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(str(path),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as f:
        f.write(json.dumps(payload,indent=2,allow_nan=False)+'\n')
        f.flush();os.fsync(f.fileno())


def preflight(args):
    home=Path(__file__).resolve().parent
    require(not args.claim_file.exists(),'FINAL TEST CLAIM EXISTS. DO NOT SCORE AGAIN.')
    require(not args.out.exists(),'Final evaluation output directory already exists; refuse overwrite.')
    require(args.claim_file.resolve()==(args.out/'FINAL_TEST_EVALUATION_CLAIM.json').resolve(),
            'The one-use claim must be stored INSIDE the immutable final-test output directory')
    fp={}
    fp['protocol']=verify(home/'part5_protocol_freeze.json',PROTO_SHA,'preselection protocol')
    fp['preprocessor_source']=verify(home/'part4_v2_train_only_pipeline.py',PREP_SHA,'original preprocessing code')
    fp['final_lock']=verify(args.lock,LOCK_SHA,'final-model lock')
    fp['final_model']=verify(args.model,MODEL_SHA,'locked HGB model')
    fp['test_cohort']=verify(args.cohort,COHORT_SHA,'unscored V2 final-test cohort')
    fp['fdic_failures']=verify(args.failures,FAILURES_SHA,'original FDIC failures source')
    fp['pretest_evidence']=verify(args.pretest_zip,PRETEST_SHA,'Step06A successful pretest evidence')
    fp['step06b1_evidence']=verify(args.b1_zip,B1_SHA,'Step06B1 audited unscored cohort ZIP')
    lock=json.loads(Path(args.lock).read_text(encoding='utf8'))
    protocol=json.loads((home/'part5_protocol_freeze.json').read_text(encoding='utf8'))
    with zipfile.ZipFile(args.b1_zip) as z:
        require(z.testzip() is None,'Step06B1 ZIP CRC failed')
        cohort_audit=json.loads(z.read('part5_step06b1_cohort_audit.json'))
    with zipfile.ZipFile(args.pretest_zip) as z:
        require(z.testzip() is None,'Step06A ZIP CRC failed')
        pretest=json.loads(z.read('part5_step06a_pretest_audit.json'))
    require(cohort_audit['status']=='PASS_PREPARED_NOT_SCORED','B1 not accepted')
    require(cohort_audit['new_cohort']['sha256']==COHORT_SHA,'B1 cohort differs from frozen SHA')
    require(cohort_audit['new_cohort']['primary_labelled_rows']==364440 and
            cohort_audit['new_cohort']['primary_positive_rows']==1112 and
            cohort_audit['new_cohort']['positive_distinct_CERTs']==341,
            'B1 heldout census incompatible with expected source')
    require(cohort_audit['model_sha256']==MODEL_SHA and cohort_audit['frozen_lock_sha256']==LOCK_SHA,
            'B1 frozen model/lock differs')
    require(pretest['status']=='PASS_LOCK_MODEL_SOURCE_VERIFIED__TEST_UNOPENED',
            'Step06A pretest did not PASS')
    require(pretest['model_sha256']==MODEL_SHA and pretest['lock_sha256']==LOCK_SHA,
            'Step06A model/lock mismatch')
    require(lock['frozen_preselection_protocol_sha256']==PROTO_SHA and
            lock['model_artifact']['sha256']==MODEL_SHA,'Frozen model lock disagree')
    require(lock['final_estimator']['feature_names_in_dataframe_order']==FEATS and
            lock['final_estimator']['output_transformed_feature_count']==30,'Feature order/count changed')
    require(lock['final_estimator']['family']=='HistGradientBoostingClassifier',
            'Expected frozen HGB')
    require(lock['final_estimator']['early_stopping'] is False and
            lock['final_estimator']['clipping']=='none','Model choice drift')
    require(lock['alarm_policy']['raw_probability_threshold']==THRESHOLD and
            lock['alarm_policy']['threshold_comparison']=='>=','Threshold drift')
    require(lock['alarm_policy']['false_alert_unit']=='first_positive_alert_per_CERT_calendar_year' and
            lock['alarm_policy']['missed_failure_unit']=='one_DISTINCT_CERT_FAILURE_event',
            'Event/annual alarm policy changed')
    require(protocol['data_contract']['test_range']=='2010-03-31_to_2025-06-30',
            'Test date range differs from protocol')
    require(protocol['threshold_selection']['primary_CFN_over_CFP']==20,
            'Cost scenario changed')
    versions={'python':platform.python_version()}
    require(versions['python']=='3.13.7',f'Python 3.13.7 required (got {versions["python"]})')
    for package,version in [('scikit-learn','1.9.0'),('numpy','2.3.3'),('pandas','2.3.3'),('joblib','1.5.2')]:
        got=metadata.version(package)
        require(got==version,f'Environment mismatch {package}: expected {version}, actual {got}')
        versions[package]=got
    return fp,lock,versions


def run(args):
    fp,lock,versions=preflight(args)
    # All byte-for-byte input verification is complete. The test cohort was
    # already opened for integrity checks in Step06B1. Confirm contract and
    # source event alignment BEFORE consuming the single model-scoring claim.
    claim={'stage':'FINAL_TEST_EVALUATION_EXCLUSIVE_CLAIM',
        'status':'SCORING_START_RESERVED__DO_NOT_DELETE_OR_REPEAT',
        'utc':datetime.now(timezone.utc).isoformat(),
        'model_sha256':MODEL_SHA,'lock_sha256':LOCK_SHA,
        'cohort_sha256':COHORT_SHA,'threshold':THRESHOLD,
        'script_sha256':sha(__file__),
        'note':'Preserve this marker even if scoring is interrupted; DO NOT rerun without an independent incident review.'}
    import joblib
    # Import exact custom transformer classes for loading a trusted local artifact.
    from part4_v2_train_only_pipeline import FEATURES
    require(set(FEATS)==set(FEATURES),'Frozen preprocessor feature set mismatch')
    model=joblib.load(args.model)  # TRUST ONLY THE PREVIOUSLY HASHED, LOCALLY FITTED MODEL.
    require(hasattr(model,'predict_proba'),'Fitted model has no probability inference method')
    df=pd.read_parquet(args.cohort)
    needed=set(FEATS)|{'CERT','DECISION_DATE','SOURCE_REPDTE','Y_4Q'}
    require(needed<=set(df.columns),'Cohort missing required columns')
    require(len(df)==364440,'Test V2 cohort row count changed')
    require(not df.duplicated(['CERT','DECISION_DATE']).any(),'Duplicate bank-quarter keys')
    df['CERT']=pd.to_numeric(df['CERT'],errors='raise').astype('int64')
    df['DECISION_DATE']=pd.to_datetime(df['DECISION_DATE'],errors='raise')
    df['SOURCE_REPDTE']=pd.to_datetime(df['SOURCE_REPDTE'],errors='raise')
    y=pd.to_numeric(df['Y_4Q'],errors='raise')
    require(y.notna().all() and y.isin([0,1]).all(),'Test labels not valid binary')
    df['Y_4Q']=y.astype('int8')
    require(len(df)==364440 and int(df['Y_4Q'].sum())==1112 and
            df.loc[df['Y_4Q'].eq(1),'CERT'].nunique()==341,'Frozen cohort census mismatch')
    require(df['DECISION_DATE'].min()==TEST_START and df['DECISION_DATE'].max()==TEST_END and
            df['DECISION_DATE'].nunique()==62,'Test quarter range mismatch')
    require((df['SOURCE_REPDTE']<df['DECISION_DATE']).all() and
            (quarter_index(df['DECISION_DATE'])-quarter_index(df['SOURCE_REPDTE'])==1).all(),
            'Source quarter may not be exact one-quarter lag')
    X=df[FEATS].astype('float64')  # critical: avoid int64/float64 imputer failure
    require(not np.isinf(X.to_numpy(dtype=np.float64)).any(),'Infinite predictor value')
    # Verify event alignment BEFORE the scoring claim, without any model inference.
    check_df=df[['CERT','DECISION_DATE','Y_4Q']].copy()
    events=failure_event_table(args.failures)
    event_alignment=check_outcomes(check_df,events)
    _claim_atomic(args.claim_file,claim)
    print('FINAL TEST CLAIM CREATED. Scoring will happen once.',flush=True)
    args.out.mkdir(parents=True,exist_ok=True)
    # FROZEN MODEL INFERENCE; EXACTLY ONE predict_proba CALL IN THIS SCRIPT.
    score=np.asarray(model.predict_proba(X),dtype='float64')
    require(score.shape==(len(df),2),'Unexpected predict_proba shape')
    score=score[:,1]
    require(np.isfinite(score).all() and ((score>=0)&(score<=1)).all(),
            'Invalid test predicted probabilities')
    d=df[['CERT','DECISION_DATE','SOURCE_REPDTE','Y_4Q']].copy()
    d['score']=score
    # Metrics are evaluated only AFTER the model and threshold were frozen.
    overall=metric_row(d,'FULL_FINAL_TEST_2010Q1_to_2025Q2')
    periods=[]
    period_defs=[('2010Q1_to_2013Q4',d['DECISION_DATE']<=pd.Timestamp('2013-12-31')),
                 ('2014Q1_to_2025Q2',d['DECISION_DATE']>=pd.Timestamp('2014-03-31'))]
    for lab,mask in period_defs:
        periods.append(metric_row(d.loc[mask],lab))
    require(sum(r['rows'] for r in periods)==len(d),'Period split coverage mismatch')
    years=[metric_row(q,f'year_{int(y)}') for y,q in d.groupby(d['DECISION_DATE'].dt.year,sort=True)]
    policy,first_alerts,event_certs=annual_alert_policy(d,events,THRESHOLD)
    ci=wilson_ci(policy['detected_failure_certs'],policy['total_failure_certs'])
    policy['event_detection_wilson_ci95_lower']=ci[0]
    policy['event_detection_wilson_ci95_upper']=ci[1]
    policy['false_alert_cert_year_rate']=policy['false_alert_cert_years']/policy['distinct_cert_years']
    policy['normalized_cost_ratio_20']=policy['false_alert_cert_years']+20*policy['missed_failure_certs']
    for ratio in (5,10,20,50):
        policy[f'fixed_threshold_normalized_cost_at_ratio_{ratio}']=policy['false_alert_cert_years']+ratio*policy['missed_failure_certs']
    # Explicitly no re-optimization of the 4 cost-ratio scenarios on test.
    quarterly=quarterly_capacity_1pct(d)
    capacity_summary={
      'alerts':int(quarterly['alerts'].sum()),
      'true_positive_bank_quarters':int(quarterly['true_positive_bank_quarters'].sum()),
      'false_positive_bank_quarters':int(quarterly['false_positive_bank_quarters'].sum()),
      'precision':float(quarterly['true_positive_bank_quarters'].sum()/quarterly['alerts'].sum()),
      'recall':float(quarterly['true_positive_bank_quarters'].sum()/int(d['Y_4Q'].sum())),
      'status':'diagnostic top 1 pct per quarter; NOT an operational threshold; not tuned on test',
    }
    # Report by period with the SAME frozen threshold (not period-specific thresholds).
    policy_period=[]
    for label,mask in period_defs:
        sub=d.loc[mask]
        p,_,_=annual_alert_policy(sub,events,THRESHOLD)
        p['period']=label
        policy_period.append(p)
    out=args.out
    pd.DataFrame([overall]).to_csv(out/'final_test_overall_metrics.csv',index=False)
    pd.DataFrame(periods).to_csv(out/'final_test_period_metrics.csv',index=False)
    pd.DataFrame(years).to_csv(out/'final_test_year_metrics.csv',index=False)
    pd.DataFrame(policy_period).to_csv(out/'final_test_fixed_policy_by_period.csv',index=False)
    quarterly.to_csv(out/'final_test_quarterly_capacity_diagnostic.csv',index=False)
    first_alerts.to_csv(out/'final_test_first_alert_per_cert_year.csv.gz',index=False,compression='gzip')
    event_certs.to_csv(out/'final_test_event_detection_by_cert.csv',index=False)
    d.to_csv(out/'final_test_scored_rows.csv.gz',index=False,compression='gzip',float_format='%.17g')
    review={'stage':'PART5_STEP06B2_SINGLE_FINAL_TEST_EVALUATION',
      'status':'FINAL_TEST_EVALUATION_COMPLETED__NO_MORE_TEST_TUNING',
      'claim_sha256':sha(args.claim_file),'execution_utc':datetime.now(timezone.utc).isoformat(),
      'input_hashes':fp,'environment':versions,
      'protocol_sha256':PROTO_SHA,'final_lock_sha256':LOCK_SHA,
      'model_sha256':MODEL_SHA,'test_cohort_sha256':COHORT_SHA,
      'predict_proba_calls':1,'hyperparameters_or_threshold_changed':False,
      'frozen_threshold':THRESHOLD,'outcome_alignment':event_alignment,
      'overall':overall,'periods':periods,'fixed_threshold_policy':policy,
      'top1pct_per_quarter_capacity':capacity_summary,
      'interpretation_limits':[
        'Test has already been evaluated once. Do not change the model, feature set, threshold, exclusions or preprocessing based on its outcomes.',
        'Test bank-quarter rows are dependent; do not interpret row metrics as independent failures.',
        'First alarm per CERT-calendar-year is used for false-alarm cost; one failure event per distinct CERT.',
        'Separate period reports use the SAME fixed threshold; no period-specific retuning.',
        'FDIC COST is a resolution loss proxy, not a causal benefit caused by advance warning.',
        'Contemporary FDIC snapshots are not true historical release vintages.',
        '25 test observations with unknown outcomes were excluded under the pre-frozen V2 labelling policy.'
      ]}
    (out/'final_test_evaluation_audit.json').write_text(
        json.dumps(json_ready(review),indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf8')
    # The manifest hashes every user-visible result; no circular hash of the ZIP itself.
    files=sorted([p for p in out.iterdir() if p.is_file() and p.name!='SHARE_THIS_PART5_STEP06B2_FINAL_EVIDENCE.zip'])
    manifest={'stage':'FINAL_TEST_FILE_MANIFEST','files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in files}}
    (out/'final_test_output_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
    share=out/'SHARE_THIS_PART5_STEP06B2_FINAL_EVIDENCE.zip'
    with zipfile.ZipFile(share,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(out.iterdir()):
            if p.is_file() and p!=share:
                z.write(p,arcname=p.name)
    require(zipfile.ZipFile(share).testzip() is None,'Output ZIP integrity check failed')
    print('STEP06B2 FINAL TEST EVALUATION COMPLETE: SCORE CALCULATED EXACTLY ONCE.',flush=True)
    print('RETAIN claim, frozen model, test cohort, all outputs. DO NOT rerun or retune.',flush=True)
    print('SEND:',share,flush=True)
    print('No claims of final performance should be made until the output ZIP is independently audited.',flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--self-test',action='store_true')
    for name in ['model','lock','cohort','failures','pretest_zip','b1_zip','claim_file','out']:
        ap.add_argument('--'+name.replace('_','-'),type=Path)
    a=ap.parse_args()
    if a.self_test:
        self_test();return
    for k in ['model','lock','cohort','failures','pretest_zip','b1_zip','claim_file','out']:
        require(getattr(a,k) is not None,f'Missing --{k.replace("_","-")}')
    run(a)


if __name__=='__main__':
    try:main()
    except Exception as e:
        print('STEP06B2 STOPPED:',repr(e),file=sys.stderr,flush=True)
        print('IMPORTANT: if a FINAL_TEST_EVALUATION_CLAIM.json exists, DO NOT delete it or rerun.',file=sys.stderr,flush=True)
        raise
