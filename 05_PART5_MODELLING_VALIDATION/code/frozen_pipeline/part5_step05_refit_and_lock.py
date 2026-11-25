#!/usr/bin/env python3
"""BFT65B Part 5 Step05 - DEVELOPMENT ONLY HGB refit and immutable-ish lock.

Never loads a test data file, never evaluates final test, and never changes the
preselected model or the development-selected threshold. Verifies prior evidence
and requires an explicit subsequent Step06 to evaluate test exactly once.
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
import tempfile
import zipfile

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.pipeline import Pipeline

from part4_v2_train_only_pipeline import FEATURES, CONTINUOUS, BINARY, make_preprocessor
from part5_step01_baseline_dev_only import audit_dev, verify_protocol, sha256, check

PROTOCOL_SHA = '994f72de6e2446916db8c2fcd36847c45cc68eb6fef5ef67f07acc0476c6d911'
DEV_SHA = 'd365ce25204a3dcace715db4cea259c94b1b1abba4822c7bcf2b050a1c7f6a73'
STEP01_SHA = '27d7ab92912ede60429bcdc1b02660bf4d4d9175a8cdb62e99653d1d6cace009'
STEP02A_SHA = 'dee50122196ead42983b80f9668a769d105cf3a2e8268472dba3b80149c63a56'
STEP02B_SHA = '8c0f41775316da61aab8f3aaa74f2e723f3adeb0d4e2069bb94c652e6b1f066d'
MODEL_ID = 'HGB_L15_LR0p05_I150_L21_CLnone'
EXPECTED_MEAN_AP = 0.29576629263614845
EXPECTED_THRESH = 0.023971438944668057
EXPECTED_COST_MED = 10466.26235
EXPECTED_FAILURE_CERTS = 1290
EXPECTED_DETECTED_CERTS = 854
EXPECTED_FPS = 4124


def load_json(z, n):
    return json.loads(z.read(n).decode('utf-8'))


def validate_input_evidence(args, protocol):
    paths = {'step01': args.step01,'step02a': args.step02a,'step02b': args.step02b,
             'step03': args.step03,'step04': args.step04}
    expected={'step01':STEP01_SHA,'step02a':STEP02A_SHA,'step02b':STEP02B_SHA}
    output = {}
    for k,p in paths.items():
        check(p.is_file(), f'Missing {k} evidence ZIP: {p}')
        actual=sha256(p)
        if k in expected:check(actual==expected[k], f'{k} SHA mismatch: {actual}')
        with zipfile.ZipFile(p) as z:
            check(z.testzip() is None, f'{k} corrupt ZIP')
        output[k] = actual
    with zipfile.ZipFile(args.step01) as z:
        a=load_json(z,'part5_step01_audit.json')
        check(a['protocol_sha256']==PROTOCOL_SHA and a['development_parquet_sha256']==DEV_SHA,
              'Step01 protocol/development mismatch')
        check(a['data_audit']['rows']==1231631 and a['data_audit']['positives']==9246,
              'Step01 census mismatch')
    with zipfile.ZipFile(args.step02a) as z:
        a=load_json(z,'part5_step02a_audit.json')
        check(a['protocol_sha256']==PROTOCOL_SHA and a['development_sha256']==DEV_SHA,
              'Step02A protocol/dev mismatch')
    with zipfile.ZipFile(args.step02b) as z:
        a=load_json(z,'part5_step02b_audit.json')
        check(a['protocol_sha256']==PROTOCOL_SHA and a['development_sha256']==DEV_SHA,
              'Step02B protocol/dev mismatch')
        check(a['measured_fits']==24 and a['configs']==8 and a['folds']==3,
              'Step02B grid incomplete')
        summ=pd.read_csv(io.BytesIO(z.read('hgb_candidate_summary.csv')))
        check(len(summ)==8 and summ['folds'].eq(3).all(), 'Incomplete HGB summary')
        ranked=summ.sort_values(['mean_ap','config_id'],ascending=[False,True]).reset_index(drop=True)
        check(ranked.loc[0,'config_id']==MODEL_ID, 'HGB winner differs from frozen Step03 selection')
        check(abs(float(ranked.loc[0,'mean_ap'])-EXPECTED_MEAN_AP)<1e-12,
              'Selected HGB AP differs')
        check(float(ranked.loc[0,'mean_ap'])-float(ranked.loc[1,'mean_ap'])>0.0002,
              'HGB winner tie-break requires review')
        for n in ['hgb_candidate_summary.csv','hgb_candidate_fold_metrics.csv']:
            check(hashlib.sha256(z.read(n)).hexdigest()==a['output_sha256'][n],
                  f'Step02B {n} hash mismatch')
    with zipfile.ZipFile(args.step03) as z:
        a=load_json(z,'part5_step03_audit.json')
        check(a['protocol_sha256']==PROTOCOL_SHA,'Step03 protocol differs')
        check(a['selected_model']==MODEL_ID and a['oof_rows']==304598,
              'Step03 model/OOF count differs')
        check(a['input_sha256']['step01_evidence_zip']==STEP01_SHA and
              a['input_sha256']['step02a_evidence_zip']==STEP02A_SHA and
              a['input_sha256']['step02b_evidence_zip']==STEP02B_SHA and
              a['input_sha256']['development_primary_v2']==DEV_SHA,
              'Step03 does not refer to frozen development evidence')
        rank=a['model_ranking_top5'][0]
        check(rank['config']==MODEL_ID and abs(rank['mean_ap']-EXPECTED_MEAN_AP)<1e-12,
              'Step03 selected-model ranking mismatch')
        t=a['primary_threshold_diagnostics']
        check(abs(float(t['threshold'])-EXPECTED_THRESH)<1e-13,
              'Selected development threshold differs')
        check(t['detected_failure_certs']==EXPECTED_DETECTED_CERTS and
              t['total_failure_certs_in_oof']==EXPECTED_FAILURE_CERTS and
              t['false_alerted_cert_years']==EXPECTED_FPS,
              'Step03 event/cost policy is inconsistent')
        scenarios=a['threshold_scenarios']
        check([int(s['ratio']) for s in scenarios]==[5,10,20,50],
              'Unexpected cost ratios')
        selected=[s for s in scenarios if s['ratio']==20][0]
        check(abs(float(selected['threshold'])-EXPECTED_THRESH)<1e-13 and
              abs(float(selected['COST_median_thousand_USD'])-EXPECTED_COST_MED)<1e-7,
              'Step03 main cost scenario mismatch')
        for s in scenarios:
            check(s['detected_failure_certs']+s['missed_failure_certs']==EXPECTED_FAILURE_CERTS,
                  f"Failure events not reconciled for cost ratio {s['ratio']}")
            check(abs(float(s['cost_units']) - (float(s['fp_cert_years']) +
                  float(s['missed_failure_certs'])*float(s['ratio'])))<1e-9,
                  'Cost units arithmetic mismatch')
    with zipfile.ZipFile(args.step04) as z:
        a=load_json(z,'part5_step04_audit.json')
        check(a['status']=='PASS_FOLD_PREPROCESSING_AND_RANKING_PARITY' and
              a['protocol_sha256']==PROTOCOL_SHA and a['development_sha256']==DEV_SHA and
              a['baseline_evidence_sha256']==STEP01_SHA,
              'Spark Step04 did not pass original contract')
        check(a['fold']=='early_bank_stress' and a['valid_rows']==125962,
              'Spark fold mismatch')
        for n,h in a['output_sha256'].items():
            check(hashlib.sha256(z.read(n)).hexdigest()==h,
                  f'Spark output hash mismatch: {n}')
        check(float(a['metrics']['absolute_AP_delta'])<0.015 and
              float(a['metrics']['absolute_AUC_delta'])<0.015,
              'Spark parity failed')
    check(set(FEATURES)==set(protocol['feature_policy']['tier1_features']) and len(FEATURES)==15,
          'Tier1 feature set changed')
    check(protocol['feature_policy']['fixed_missingness_indicators']==15,
          'Missingness indicator policy changed')
    check(protocol['validation']['extra_quiet_period_fold'] is False,
          'Fold decision differs from freeze')
    check(protocol['threshold_selection']['primary_CFN_over_CFP']==20,
          'Cost ratio selection differs')
    check(protocol['test_policy']['model_selection_on_test'] is False and
          protocol['test_policy']['test_evaluated_exactly_once'] is True,
          'Test policy changed')
    return output


def build_hgb(seed):
    return Pipeline([
        ('prep',make_preprocessor(clip=False)),
        ('clf',HistGradientBoostingClassifier(
            max_leaf_nodes=15,learning_rate=0.05,max_iter=150,
            l2_regularization=1.0,early_stopping=False,random_state=seed)),
    ])


def make_lock(args, protocol, evidence_sha, audit, model_sha):
    return {
        'lock_id':'BFT65B_PART5_FINAL_MODEL_LOCK_V1',
        'status':'DEVELOPMENT_REFIT_COMPLETE__AWAIT_INDEPENDENT_AUDIT__TEST_UNOPENED',
        'purpose':'Freeze final HGB estimator, features, preprocessing and cost threshold BEFORE test',
        'frozen_preselection_protocol_sha256':PROTOCOL_SHA,
        'source_development_parquet_sha256':DEV_SHA,
        'evidence_zip_sha256':evidence_sha,
        'source_files_sha256':{
            'refit_script':sha256(Path(__file__).resolve()),
            'preprocessor_factory':sha256(Path(__file__).with_name('part4_v2_train_only_pipeline.py')),
            'dev_data_audit':sha256(Path(__file__).with_name('part5_step01_baseline_dev_only.py')),
            'hgb_config_source':sha256(Path(__file__).with_name('part5_step02_hgb_grid_dev.py')),
        },
        'selection_provenance':{
            'folds':[f['id'] for f in protocol['validation']['folds']],
            'embargo_quarters':4,
            'primary_selection_metric':'unweighted_mean_Average_Precision',
            'selected_model_config':MODEL_ID,
            'development_mean_AP':EXPECTED_MEAN_AP,
            'development_heldout_OOF_rows':304598,
            'assistance_is_positive_in_primary':False,
            'adverse_exits_in_primary':'excluded_if_unresolved',
        },
        'final_estimator':{
            'family':'HistGradientBoostingClassifier',
            'feature_names_in_dataframe_order':FEATURES,
            'continuous_feature_names':CONTINUOUS,
            'binary_feature_names':BINARY,
            'input_feature_count':15,
            'output_transformed_feature_count':30,
            'fixed_missing_flags_count':15,
            'imputation':'median_fit_on_full_development_only_for_continuous',
            'scaling':'RobustScaler_fit_on_full_development_only',
            'binary_imputation':'constant_0_for_binary_flags',
            'clipping':'none',
            'calibration':'none_due_to_unstable_forward_diagnostics',
            'max_leaf_nodes':15,'learning_rate':0.05,'max_iter':150,
            'l2_regularization':1.0,'early_stopping':False,
            'random_state':protocol['model_selection']['seed'],
        },
        'alarm_policy':{
            'raw_probability_threshold':EXPECTED_THRESH,
            'threshold_comparison':'>=',
            'C_FN_over_C_FP':20,
            'false_alert_unit':'first_positive_alert_per_CERT_calendar_year',
            'missed_failure_unit':'one_DISTINCT_CERT_FAILURE_event',
            'cost_proxy_median_thousand_USD':EXPECTED_COST_MED,
            'OOF_detected_failure_CERTs':EXPECTED_DETECTED_CERTS,
            'OOF_total_failure_CERTs':EXPECTED_FAILURE_CERTS,
            'OOF_false_alert_CERT_years':EXPECTED_FPS,
            'operational_calibration_note':'raw HGB scores; frozen threshold tuned from dev OOF only; transfer to refit model not guaranteed',
        },
        'fitting_data_audit':audit,
        'model_artifact':{'filename':'final_hgb_refit.joblib','sha256':model_sha,
                          'serialization':'joblib (trusted local artifact only)'},
        'environment':{
            'python':platform.python_version(),'numpy':np.__version__,
            'pandas':pd.__version__,'sklearn':sklearn.__version__,'joblib':joblib.__version__,
            'os':platform.platform(),
        },
        'test_policy':{
            'test_file_was_not_read':True,
            'final_test_evaluations_permitted':1,
            'no_config_or_threshold_change_after_test':True,
            'final_test_evaluation_status':'NOT_RUN',
            'next_step':'Audit this lock; commit/tag hash and model, then one-time Step06 test evaluation',
        },
        'scientific_limits':[
            'Development OOF results were used to select model and threshold; they are not unbiased test estimates.',
            'FDIC reported COST is a loss proxy, not a measured causal gain from warning.',
            'The historical FDIC snapshot is not a publication-vintage archive.',
            'Train/refit preprocessing statistics belong to full development; test must only transform.',
        ],
    }


def save_atomic_new_bytes(path, content):
    # Exclusive create: lock files are never silently overwritten.
    with path.open('xb') as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def refit(args):
    proto,prot_sha=verify_protocol(args.protocol)
    check(prot_sha==PROTOCOL_SHA,'Wrong preselection protocol')
    check(args.dev.name=='development_primary_binary_v2.parquet',
          'Refuse a non-development data filename')
    check(args.dev.is_file() and sha256(args.dev)==DEV_SHA,
          'Development Parquet missing or bytes differ from prior audited input')
    hashes=validate_input_evidence(args,proto)
    args.out.mkdir(parents=True,exist_ok=True)
    modelp=args.out/'final_hgb_refit.joblib'
    lockp=args.out/'FINAL_MODEL_LOCK.json'
    digestp=args.out/'FINAL_MODEL_LOCK.sha256'
    existing=[p.exists() for p in [modelp,lockp,digestp]]
    if any(existing):
        check(all(existing),'Incomplete existing lock/model. STOP, preserve files for investigation; do not overwrite.')
        lock=json.loads(lockp.read_text(encoding='utf-8'))
        check(lock['frozen_preselection_protocol_sha256']==PROTOCOL_SHA and
              lock['source_development_parquet_sha256']==DEV_SHA and
              lock['evidence_zip_sha256']==hashes and
              lock['model_artifact']['sha256']==sha256(modelp),
              'Existing final lock differs from current evidence; refuse')
        expected=hashlib.sha256(lockp.read_bytes()).hexdigest()
        check(digestp.read_text(encoding='ascii').strip()==expected,
              'Existing lock SHA file differs')
        print('EXISTING FINAL MODEL LOCK VERIFIED; no refit performed; TEST still not touched.')
        write_small_evidence(args.out,lockp,digestp,hashes,sha256(modelp))
        return
    print('All prior evidence reconciled; reading DEVELOPMENT parquet only.',flush=True)
    dev=pd.read_parquet(args.dev)
    dev['DECISION_DATE']=pd.to_datetime(dev['DECISION_DATE'],errors='raise')
    dev['SOURCE_REPDTE']=pd.to_datetime(dev['SOURCE_REPDTE'],errors='raise')
    audit=audit_dev(dev,expected=True)
    check(audit['rows']==1231631 and audit['positives']==9246 and audit['positive_certs']==2410,
          'Development dataset unexpected')
    # HGB fit exactly with Step02B factory and frozen hyperparameters.
    model=build_hgb(proto['model_selection']['seed'])
    print('Training HGB ON FULL DEVELOPMENT only (1,231,631 labelled bank-quarters)...',flush=True)
    model.fit(dev[FEATURES],dev['Y_4Q'].to_numpy(dtype='int8'))
    clf=model.named_steps['clf']
    check(int(clf.n_iter_)==150 and model.named_steps['prep'].transform(dev.iloc[:16][FEATURES]).shape==(16,30),
          'Final fitted estimator width or iterations differ')
    prep=model.named_steps['prep'];cont=prep.named_transformers_['continuous']
    med=cont.named_steps['training_median'].statistics_
    scl=cont.named_steps['training_robust_scale'].scale_
    check(len(med)==12 and np.isfinite(med).all() and len(scl)==12 and
          np.isfinite(scl).all() and np.all(scl>0),'Invalid fitted training statistics')
    # Full development refit is in-sample. No metric from it used to change policy.
    probe=dev.iloc[np.linspace(0,len(dev)-1,num=32,dtype=int)][FEATURES].copy()
    before=model.predict_proba(probe)[:,1]
    check(np.isfinite(before).all() and np.all((before>=0)&(before<=1)),
          'Invalid training probe scores')
    # Save to a temporary file in output, then atomically publish the model.
    tmp=args.out/'final_hgb_refit.joblib.partial'
    check(not tmp.exists(),'Previous partial model exists; inspect it before retry')
    try:
        joblib.dump(model,tmp,compress=3)
        # Only load our own fresh joblib serialization (pickle-based, never untrusted input).
        reloaded=joblib.load(tmp)
        after=reloaded.predict_proba(probe)[:,1]
        check(np.allclose(before,after,atol=1e-14,rtol=0),
              'Joblib round-trip changed predictions')
        os.replace(tmp,modelp)
    finally:
        if tmp.exists():tmp.unlink()
    model_sha=sha256(modelp)
    audit.update({'fit_rows':len(dev),'fit_positive_rows':int(dev.Y_4Q.sum()),
                  'fit_positive_certs':int(dev.loc[dev.Y_4Q.eq(1),'CERT'].nunique()),
                  'hgb_n_iterations':int(clf.n_iter_),
                  'preprocessor_output_columns':30,
                  'train_only_fitted_medians':{name:float(val) for name,val in zip(CONTINUOUS,med)},
                  'train_only_fitted_robust_scales':{name:float(val) for name,val in zip(CONTINUOUS,scl)},
                  'joblib_roundtrip_max_abs_score_difference':float(np.max(np.abs(before-after)))})
    lock=make_lock(args,proto,hashes,audit,model_sha)
    content=(json.dumps(lock,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8')
    save_atomic_new_bytes(lockp,content)
    save_atomic_new_bytes(digestp,(hashlib.sha256(content).hexdigest()+'\n').encode('ascii'))
    write_small_evidence(args.out,lockp,digestp,hashes,model_sha)
    print('STEP05 PASS: model refitted on development and FINAL_MODEL_LOCK created.',flush=True)
    print('DO NOT EVALUATE TEST yet. Share ZIP for independent audit first.',flush=True)
    print('MODEL SHA256:',model_sha)
    print('LOCK SHA256:',hashlib.sha256(content).hexdigest(),flush=True)


def write_small_evidence(out,lockp,digestp,hashes,model_sha):
    lock=json.loads(lockp.read_text(encoding='utf-8'))
    evidence={'stage':'PART5_STEP05_REFIT_AND_FINAL_MODEL_LOCK','status':'PASS_DEV_ONLY_AWAIT_INDEPENDENT_REVIEW',
        'frozen_protocol_sha256':PROTOCOL_SHA,'development_sha256':DEV_SHA,
        'prior_evidence_zip_shas':hashes,'final_model_lock_sha256':sha256(lockp),
        'model_artifact_sha256':model_sha,
        'model_file_bytes':(out/'final_hgb_refit.joblib').stat().st_size,
        'development_rows':lock['fitting_data_audit']['rows'],
        'development_positive_rows':lock['fitting_data_audit']['positives'],
        'selected_model':MODEL_ID,'selected_raw_threshold':EXPECTED_THRESH,
        'test_was_evaluated':False,
        'notes':'Large joblib stays on user local disk; ZIP contains lock and model SHA, not model bytes.'}
    auditp=out/'part5_step05_audit.json'
    auditp.write_text(json.dumps(evidence,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    outzip=out/'SHARE_THIS_PART5_STEP05_EVIDENCE.zip'
    with zipfile.ZipFile(outzip,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for p in [auditp,lockp,digestp]:z.write(p,arcname=p.name)
    with zipfile.ZipFile(outzip) as z:
        check(z.testzip() is None,'Step05 evidence CRC error')
    print('SEND:',outzip,flush=True)


def self_test():
    import tempfile
    rng=np.random.default_rng(20261114)
    train=pd.DataFrame({c:rng.normal(size=280) for c in CONTINUOUS})
    for c in BINARY:train[c]=rng.integers(0,2,size=len(train)).astype(float)
    train.loc[::19,'asset_log_growth_4q']=np.nan
    y=np.zeros(len(train),dtype=int);y[rng.choice(len(train),35,replace=False)]=1
    m=build_hgb(20261114)
    m.fit(train,y)
    check(m.named_steps['clf'].n_iter_==150,'HGB must train exactly 150 iterations')
    check(m.named_steps['prep'].transform(train.iloc[:6]).shape==(6,30),'Expected 30 transformed cols')
    p=m.predict_proba(train.iloc[:6])[:,1]
    with tempfile.TemporaryDirectory() as temp:
        path=Path(temp)/'m.joblib'
        joblib.dump(m,path,compress=3)
        q=joblib.load(path).predict_proba(train.iloc[:6])[:,1]
        check(np.allclose(p,q,atol=1e-14,rtol=0), 'Serialization roundtrip mismatch')
    noisy=train.iloc[:6].copy();noisy.iloc[0,0]=1e12
    pre=m.named_steps['prep']
    before=pre.named_transformers_['continuous'].named_steps['training_median'].statistics_.copy()
    _=m.predict_proba(noisy)[:,1]
    after=pre.named_transformers_['continuous'].named_steps['training_median'].statistics_.copy()
    check(np.array_equal(before,after),'Transform may not mutate fitting statistics')
    print('SELF-TEST PASS: 15-to-30 features; fixed HGB; serialization; immutable training medians.')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--self-test',action='store_true')
    for n in ['protocol','dev','step01','step02a','step02b','step03','step04','out']:
        ap.add_argument('--'+n, type=Path)
    a=ap.parse_args()
    if a.self_test:self_test();return
    for n in ['protocol','dev','step01','step02a','step02b','step03','step04','out']:
        check(getattr(a,n) is not None, f'Missing --{n}')
    refit(a)


if __name__=='__main__':
    try:main()
    except Exception as ex:
        print('STEP05 FAIL:',type(ex).__name__+':',str(ex),file=sys.stderr,flush=True)
        raise
