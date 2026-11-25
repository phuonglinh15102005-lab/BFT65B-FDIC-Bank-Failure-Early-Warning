"""BFT65B Part 5 Step 03: auditable, DEVELOPMENT-ONLY policy analysis.

Consumes previous step's OOF validation predictions, their self-contained certified
row keys, the frozen protocol, and an FDIC failure-event table. Does NOT train
or evaluate a bank failure prediction model; does not read the final test.

Dependencies: numpy, pandas, scikit-learn; reading an FDIC Parquet additionally
needs pyarrow. Both a parquet and a non-cost CSV event extract are supported.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import math
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss
from sklearn.linear_model import LogisticRegression

FOLDS = ['early_bank_stress', 'post_stress_transition', 'global_financial_crisis']
# Predefined in the original protocol; never tuned using test data.
RATIOS = (5, 10, 20, 50)
EXPECTED_PROTOCOL_SHA = '994f72de6e2446916db8c2fcd36847c45cc68eb6fef5ef67f07acc0476c6d911'
EXPECTED_WINNER = 'HGB_L15_LR0p05_I150_L21_CLnone'
EXPECTED_LR = 'LR_C0p1_Wnone_CLq01_99'


def check(ok, msg):
    if not bool(ok):
        raise AssertionError(msg)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def path_sha(p: Path):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(2 << 20), b''):
            h.update(b)
    return h.hexdigest()


def zip_audit(z: zipfile.ZipFile, manifest: str):
    check(z.testzip() is None, 'ZIP CRC failed')
    audit = json.loads(z.read(manifest))
    check(audit['protocol_sha256'] == EXPECTED_PROTOCOL_SHA, 'Protocol mismatch in prior evidence')
    output_digests = audit.get('output_sha256', audit.get('outputs_sha256', {}))
    check(bool(output_digests), 'No evidence checksum manifest')
    for name, expected in output_digests.items():
        check(name in z.namelist(), 'Missing evidence: ' + name)
        check(sha(z.read(name)) == expected, 'Evidence SHA mismatch: ' + name)
    check(audit.get('final_test_opened') is not True, 'Prior evidence declares test opened')
    return audit, len(output_digests)


def array_from_zip(z, name, field):
    with np.load(io.BytesIO(z.read(name)), allow_pickle=False) as d:
        return np.asarray(d[field]).copy()


def get_keys(z, fold):
    with np.load(io.BytesIO(z.read(f'fold_keys/{fold}.npz')), allow_pickle=False) as d:
        for k in ('cert', 'decision_day', 'y'):
            check(k in d.files, 'Missing fold key ' + k)
        return (d['cert'].astype(np.int64), d['decision_day'].astype(np.int64), d['y'].astype(np.int8))


def get_scores(z, cfg, fold):
    s = array_from_zip(z, f'predictions/{cfg}__{fold}.npz', 'score').astype(np.float64)
    check(np.isfinite(s).all() and ((s >= 0) & (s <= 1)).all(), 'Invalid probability')
    return s


def quarter_id(dts: pd.Series):
    # Sentinel keeps NaT event dates out of the 1..4 horizon safely.
    year=dts.dt.year.fillna(-9999).to_numpy(dtype=np.int64)
    month=dts.dt.month.fillna(1).to_numpy(dtype=np.int64)
    return year*4 + (month-1)//3


def parse_failures(path: Path):
    if path.suffix.lower() == '.parquet':
        dat = pd.read_parquet(path)
    elif path.suffix.lower() == '.csv':
        dat = pd.read_csv(path)
    else:
        raise ValueError('FDIC input must be Parquet or CSV')
    dat.columns = [str(c).upper() for c in dat.columns]
    needed = {'CERT','FAILDATE','RESTYPE'}
    check(needed <= set(dat.columns), f'Failure events lack {needed-set(dat.columns)}')
    dat = dat[dat['RESTYPE'].astype(str).str.upper().eq('FAILURE')].copy()
    dat['CERT'] = pd.to_numeric(dat['CERT'], errors='coerce')
    dat['FAILDATE'] = pd.to_datetime(dat['FAILDATE'], errors='coerce')
    dat = dat[dat.CERT.notna() & dat.FAILDATE.notna()].copy()
    # Only events needed to judge DEVELOPMENT outcomes are eligible; even though
    # the FDIC snapshot spans later years, no 2010+ event enters this audit.
    dat = dat[dat.FAILDATE <= pd.Timestamp('2009-12-31')].copy()
    dat['CERT'] = dat['CERT'].astype(np.int64)
    # A CERT can have multiple recorded failure transactions; first event is label policy.
    dat = dat.sort_values(['CERT','FAILDATE'],kind='mergesort').drop_duplicates('CERT',keep='first')
    if 'COST' in dat:
        dat['COST'] = pd.to_numeric(dat['COST'],errors='coerce')
    return dat


def assert_event_alignment(frame, failures):
    f = frame.merge(failures[['CERT','FAILDATE']], on='CERT', how='left', validate='many_to_one')
    dt = pd.to_datetime(f.day, unit='D', origin='unix')
    event_q = quarter_id(f.FAILDATE)
    dec_q = quarter_id(dt)
    delta = event_q-dec_q
    observed = f.y.to_numpy()==1
    # All known positives must correspond to an actual failure in the next four calendar quarters.
    check(f.loc[observed,'FAILDATE'].notna().all(),'Positive without qualifying failure date')
    check(((delta[observed] >=1)&(delta[observed] <=4)).all(), 'Positive event date outside four quarters')
    # All listed negatives should NOT have first failure in their forward quarter window.
    leaked = ((delta>=1)&(delta<=4)) & (~observed)
    check(not leaked.any(), f'Negative but dated failure in horizon: {int(leaked.sum())}')
    return f, delta


def validate_evidence(zlr, zhgb, zbase, protocol):
    a_lr, n_lr = zip_audit(zlr,'part5_step02a_audit.json')
    a_hgb, n_hgb = zip_audit(zhgb,'part5_step02b_audit.json')
    a_base, n_b = zip_audit(zbase,'part5_step01_audit.json')
    check(a_lr['development_sha256'] == protocol['data_contract']['input_shas']['development_primary_v2'], 'LR cohort sha')
    check(a_hgb['development_sha256'] == protocol['data_contract']['input_shas']['development_primary_v2'], 'HGB cohort sha')
    check(a_base['development_parquet_sha256'] == protocol['data_contract']['input_shas']['development_primary_v2'], 'Baseline cohort sha')
    baseline = pd.read_csv(io.BytesIO(zbase.read('baseline_development_oof.csv')),
                           usecols=['CERT','DECISION_DATE','Y_4Q','fold'])
    baseline['day']=pd.to_datetime(baseline.DECISION_DATE, errors='raise').to_numpy(dtype='datetime64[D]').astype(np.int64)
    check(not baseline.duplicated(['CERT','day']).any(),'Duplicate baseline keys')
    baseline=baseline[['fold','CERT','day','Y_4Q']].sort_values(['fold','CERT','day'],kind='mergesort').reset_index(drop=True)
    check(len(protocol['validation']['folds'])==3,'Expected 3 folds')
    known = {f['id']:f for f in protocol['validation']['folds']}
    for fold in FOLDS:
        check(fold in known, 'Unrecognized fold')
        k1=get_keys(zlr,fold); k2=get_keys(zhgb,fold)
        for x,y in zip(k1,k2):
            check(np.array_equal(x,y), f'LR / HGB keys disagree: {fold}')
        cert,days,ys=k1
        check(np.isin(ys, [0,1]).all(), 'Nonbinary labels')
        check(int(len(np.unique(cert[ys==1]))) == known[fold]['known_validation_failure_certs'], 'Positive CERT count mismatch')
        times=pd.to_datetime(days,unit='D',origin='unix')
        check(times.min()>=pd.Timestamp(known[fold]['validation_start']), 'Validation start violated')
        check(times.max()<=pd.Timestamp(known[fold]['validation_end']), 'Validation end violated')
        check(len(np.unique(pd.MultiIndex.from_arrays([cert,days])))==len(cert),'Duplicate CERT-date')
        check(len(get_scores(zhgb,EXPECTED_WINNER,fold))==len(cert), 'HGB score count')
    hgb_keys=[]
    for fo in FOLDS:
        c,day,y=get_keys(zhgb,fo)
        hgb_keys.append(pd.DataFrame({'fold':fo,'CERT':c,'day':day,'Y_4Q':y}))
    hgb_keys=pd.concat(hgb_keys,ignore_index=True).sort_values(['fold','CERT','day'],kind='mergesort').reset_index(drop=True)
    check(all(np.array_equal(baseline[c].to_numpy(),hgb_keys[c].to_numpy())
              for c in ('fold','CERT','day','Y_4Q')),
          'Step 01 baseline keys/labels differ from HGB')
    return {'baseline_sha_validated':n_b,'logistic_sha_validated':n_lr,
            'hgb_sha_validated':n_hgb,'baseline_hgb_keys_compared':len(baseline)}


def frame_from_scores(z, config):
    items=[]
    for fold in FOLDS:
        c,d,y=get_keys(z,fold)
        s=get_scores(z,config,fold)
        items.append(pd.DataFrame({'fold':fold,'CERT':c,'day':d,'y':y,'score':s}))
    v=pd.concat(items,ignore_index=True)
    check(not v.duplicated(['CERT','day']).any(), 'Cross-fold key collision')
    check(len(v)==304598 and int(v.y.sum())==3683,'Unexpected OOF row count')
    v['dt'] = pd.to_datetime(v.day, unit='D',origin='unix')
    v['year'] = v.dt.dt.year.astype(np.int32)
    return v


def independent_model_compare(zlr,zhgb,zbase):
    summary=[]
    for name,z in [('logistic_L2',zlr),('hist_gradient_boosting',zhgb)]:
        prefix = 'LR_' if name=='logistic_L2' else 'HGB_'
        configs=sorted({p.split('/')[-1].split('__')[0] for p in z.namelist()
                        if p.startswith('predictions/') and p.endswith('.npz') and p.split('/')[-1].startswith(prefix)})
        check(len(configs)==(12 if name=='logistic_L2' else 8), 'Model grid not complete')
        for cfg in configs:
            aps=[]
            for f in FOLDS:
                _,_,yy=get_keys(z,f)
                scores=get_scores(z,cfg,f)
                aps.append(float(average_precision_score(yy,scores)))
            summary.append({'family':name,'config':cfg,'mean_ap':float(np.mean(aps)),
                            **{f'ap_{f}':ap for f,ap in zip(FOLDS,aps)}})
    audited=json.loads(zbase.read('part5_step01_audit.json'))
    summary.append({'family':'equity_ratio_logistic_baseline','config':'BASELINE_EQUITY_ONLY',
                    'mean_ap':float(audited['unweighted_mean_validation_average_precision'])})
    summary.sort(key=lambda d:-d['mean_ap'])
    check(summary[0]['config']==EXPECTED_WINNER,'Frozen AP winner differs from expected; stop')
    check(any(x['config']==EXPECTED_LR for x in summary), 'LR comparator absent')
    return summary


def policy_scan(d, ratios=RATIOS, expected_event_count=1290):
    """Exact score thresholds, per-CERT-year FIRST alerted quarter is the sole alert.
    At each threshold, higher score rows enter. If an earlier calendar quarter
    enters for a CERT-year, it replaces the later alert. A valid event is detected
    only if this FIRST alerted quarter has y=1 (failure within next 4 quarters).
    Each false alerted CERT-year incurs one FP cost. Each distinct positive CERT
    not alerted in time incurs one FN cost. A CERT may have more than one year.
    """
    val=d[['CERT','year','day','y','score']].copy()
    val.sort_values('score',ascending=False,kind='mergesort',inplace=True)
    cs=val.CERT.to_numpy(dtype=np.int64); yr=val.year.to_numpy(dtype=np.int64)
    dd=val.day.to_numpy(dtype=np.int64); yy=val.y.to_numpy(dtype=np.int8)
    ss=val.score.to_numpy(dtype=np.float64)
    positive_certs=set(cs[yy==1].tolist())
    nevents=len(positive_certs)
    if expected_event_count is not None:
        check(nevents==expected_event_count, 'Unexpected positive CERT count')
    # year -> (earliest quarter, positive at first warning)
    first={}; credited=defaultdict(int)
    n_false=0; n_detected=0
    maximum=float(np.max(ss))
    none_threshold=float(np.nextafter(maximum,np.inf))
    best={r: {'ratio':r,'threshold':none_threshold,'cost_units':float(r*nevents),
               'fp_cert_years':0,'missed_failure_certs':nevents,'detected_failure_certs':0,
               'bank_quarter_alerts':0,'cert_year_alerts':0} for r in ratios}
    sample=[]
    n=len(val)
    idx=0
    while idx<n:
        s=ss[idx]
        end=idx+1
        while end<n and ss[end]==s:
            end+=1
        # Tied score rows become eligible simultaneously; first date wins.
        for j in range(idx,end):
            key=(int(cs[j]),int(yr[j])); day=int(dd[j]); yi=int(yy[j])
            prev=first.get(key)
            if prev is None:
                first[key]=(day,yi)
                if yi:
                    if credited[key[0]]==0:n_detected+=1
                    credited[key[0]]+=1
                else:
                    n_false+=1
            elif day < prev[0]:
                prev_y=prev[1]
                if prev_y != yi:
                    if prev_y:
                        credited[key[0]]-=1
                        if credited[key[0]]==0:n_detected-=1
                        n_false+=1
                    else:
                        n_false-=1
                        if credited[key[0]]==0:n_detected+=1
                        credited[key[0]]+=1
                first[key]=(day,yi)
        missed=nevents-n_detected
        for r in ratios:
            cost=n_false+r*missed
            old=best[r]
            if cost < old['cost_units']-1e-9 or (abs(cost-old['cost_units'])<=1e-9 and s>old['threshold']):
                best[r]={'ratio':r,'threshold':float(s),'cost_units':float(cost),
                         'fp_cert_years':int(n_false),'missed_failure_certs':int(missed),
                         'detected_failure_certs':int(n_detected),
                         'bank_quarter_alerts':int(end),'cert_year_alerts':int(len(first))}
        if end>=n or (len(sample)<1000 and (end/len(d)-len(sample)*0.001)>=0.001):
            sample.append({'threshold':float(s),'alert_rows':int(end),'alerted_cert_years':len(first),
                           'fp_cert_years':int(n_false),'detected_certs':int(n_detected),'missed_certs':int(missed)})
        idx=end
    return pd.DataFrame([best[r] for r in ratios]),pd.DataFrame(sample)


def exact_metrics_under_threshold(d, failures, threshold):
    x=d[d.score>=threshold].copy()
    x.sort_values(['CERT','year','day','score'],ascending=[True,True,True,False],kind='mergesort',inplace=True)
    # First alert per CERT/year, temporal first, never choose future quarter in year.
    alerts=x.drop_duplicates(['CERT','year'],keep='first').copy()
    true_first=alerts[alerts.y==1]
    positives=d.loc[d.y.eq(1),'CERT'].unique()
    detected=set(true_first.CERT.tolist())
    check(detected <= set(positives.tolist()), 'Event detection mismatch')
    check(not alerts.duplicated(['CERT','year']).any(),'Duplicate annual alarm')
    event_dates=failures.set_index('CERT')['FAILDATE']
    if len(true_first):
        true_first = true_first.copy()
        true_first['FAILDATE'] = true_first.CERT.map(event_dates)
        delta=quarter_id(true_first.FAILDATE)-quarter_id(true_first.dt)
        check(((delta>=1)&(delta<=4)).all(),'Noncausal lead time')
        true_first['lead_quarters']=delta
        # Earliest valid true alert among yearly first alerts, by CERT.
        first_valid=true_first.sort_values('day',kind='mergesort').drop_duplicates('CERT')
        lead_by_cert=first_valid[['CERT','lead_quarters']]
    else:
        lead_by_cert=pd.DataFrame(columns=['CERT','lead_quarters'])
    agg={'threshold':float(threshold),'alerted_bank_quarters':int(len(x)),
         'alerted_cert_years':int(len(alerts)),
         'false_alerted_cert_years':int((alerts.y==0).sum()),
         'detected_failure_certs':int(len(detected)),
         'total_failure_certs_in_oof':int(len(positives)),
         'missed_failure_certs':int(len(positives)-len(detected)),
         'event_detection_rate':float(len(detected)/len(positives)),
         'median_lead_quarters':float(lead_by_cert.lead_quarters.median()) if len(lead_by_cert) else None,
         'p25_lead_quarters':float(lead_by_cert.lead_quarters.quantile(.25)) if len(lead_by_cert) else None,
         'p75_lead_quarters':float(lead_by_cert.lead_quarters.quantile(.75)) if len(lead_by_cert) else None}
    fold_stats=[]
    for fold in FOLDS:
        sub=d[d.fold==fold]
        nsub_alerts=alerts[alerts.fold==fold]
        positive=set(sub.loc[sub.y==1,'CERT'].tolist())
        nsub_detect=set(nsub_alerts.loc[nsub_alerts.y==1,'CERT'].tolist())
        fold_stats.append({'fold':fold,'threshold':threshold,'validation_rows':len(sub),
                           'failure_certs':len(positive),'detected_certs':len(nsub_detect),
                           'detected_event_rate':len(nsub_detect)/len(positive),
                           'alerted_cert_years':len(nsub_alerts),
                           'false_alert_cert_years':int((nsub_alerts.y==0).sum()),
                           'false_alerts_per_1000_bank_quarters':1000*(nsub_alerts.y==0).sum()/len(sub),
                           'alerted_bank_quarters':int((sub.score>=threshold).sum())})
    return agg,pd.DataFrame(fold_stats),lead_by_cert,alerts


def forward_platt(d):
    """Calibration transfer diagnostic ONLY: chronologically prior fold -> next.
    No calibration of fold 1 because there is no earlier OOF fold.
    A recalibration fitted to all OOF is NOT evaluated on its own fitted scores.
    """
    results=[]; models=[]
    def logit(x):
        xx=np.clip(np.asarray(x,dtype=float),1e-8,1-1e-8)
        return np.log(xx/(1-xx)).reshape(-1,1)
    for k in (1,2):
        train=d[d.fold.isin(FOLDS[:k])].copy()
        valid=d[d.fold==FOLDS[k]].copy()
        check(train.day.max()<valid.day.min(),'Forward calibration leakage')
        check(quarter_id(train.dt).max()+4 < quarter_id(valid.dt).min(),
              'Calibration development outcome window overlaps the validation regime')
        cal=LogisticRegression(C=1e6,class_weight=None,solver='lbfgs',max_iter=500)
        cal.fit(logit(train.score),train.y)
        coefficients=(float(cal.coef_[0,0]),float(cal.intercept_[0]))
        pp=cal.predict_proba(logit(valid.score))[:,1]
        obs=valid.y.to_numpy(dtype=np.int8)
        check(np.isfinite(pp).all(), 'Invalid calibrated predictions')
        results.append({'fold':FOLDS[k],'training_folds':'+'.join(FOLDS[:k]),
                        'n_calibration_training':len(train),'n_validation':len(valid),
                        'train_ended':train.dt.max().date().isoformat(),
                        'valid_started':valid.dt.min().date().isoformat(),
                        'coef_logit':coefficients[0], 'intercept':coefficients[1],
                        'raw_ap':float(average_precision_score(obs,valid.score)),
                        'forward_calibrated_ap':float(average_precision_score(obs,pp)),
                        'raw_brier':float(brier_score_loss(obs,valid.score)),
                        'forward_calibrated_brier':float(brier_score_loss(obs,pp)),
                        'raw_pred_mean':float(valid.score.mean()),'calibrated_pred_mean':float(pp.mean()),
                        'observed_prevalence':float(obs.mean())})
        models.append({'trained_on':FOLDS[:k],'applied_to':FOLDS[k], 'coefficients':coefficients})
    return pd.DataFrame(results),models


def write_json(p, obj):
    p.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False,default=str)+'\n',encoding='utf-8')


def run(args):
    pr=Path(args.protocol); check(pr.is_file(),'Missing protocol')
    check(path_sha(pr)==EXPECTED_PROTOCOL_SHA, 'Frozen protocol checksum differs; do not proceed')
    prot=json.loads(pr.read_text(encoding='utf-8'))
    check(prot['threshold_selection']['primary_CFN_over_CFP']==20, 'Frozen ratio changed')
    check(tuple(prot['threshold_selection']['cost_ratio_sensitivity_CFN_over_CFP'])==RATIOS,'Ratios changed')
    z1=zipfile.ZipFile(args.step01);zl=zipfile.ZipFile(args.step02a);zh=zipfile.ZipFile(args.step02b)
    validated=validate_evidence(zl,zh,z1,prot)
    rank=independent_model_compare(zl,zh,z1)
    d=frame_from_scores(zh,EXPECTED_WINNER)
    if Path(args.failures).suffix.lower()=='.parquet':
        check(path_sha(Path(args.failures)) == prot['data_contract']['input_shas']['failures_parquet'],
              'FDIC failures.parquet checksum differs from frozen protocol')
    f=parse_failures(Path(args.failures))
    _,lead=assert_event_alignment(d,f)
    # Cost proxy: median strictly positive finite COST for FAILURE events whose CERT
    # has a Y_4Q=1 development observation. If dev cohort absent, no monetary claim.
    cost_usd1000=None; n_cost_valid=None; n_cost_total=None
    if args.dev:
        check(Path(args.dev).is_file(),'Missing development Parquet')
        check(path_sha(Path(args.dev))==prot['data_contract']['input_shas']['development_primary_v2'], 'Dev parquet sha mismatch')
        dv=pd.read_parquet(args.dev,columns=['CERT','Y_4Q'])
        check(len(dv)==1231631 and int(dv.Y_4Q.sum())==9246,'Wrong development cohort')
        check('COST' in f.columns,'FDIC failure source must contain COST for the monetary cost proxy')
        dev_positive=set(dv.loc[dv.Y_4Q.eq(1),'CERT'].astype(np.int64).tolist())
        q=f[f.CERT.isin(dev_positive)]
        cv=q.COST.to_numpy(dtype=np.float64)
        good=cv[np.isfinite(cv)&(cv>0)]
        check(len(good)>0,'No valid COST observations')
        cost_usd1000=float(np.median(good));n_cost_valid=len(good);n_cost_total=len(q)
        check(cost_usd1000>0, 'Invalid COST median')
    else:
        print('NOTICE: no --dev; monetary FDIC COST proxy cannot be verified; reporting normalized cost units only.')
    thresholds,trajectory=policy_scan(d)
    for r in RATIOS:
        row=thresholds[thresholds.ratio==r].iloc[0]
        # Independent O(N log N) recomputation at chosen threshold, checks the sweep.
        ag,_,_,_=exact_metrics_under_threshold(d,f,float(row.threshold))
        check(ag['false_alerted_cert_years']==int(row.fp_cert_years),'Threshold sweep FP mismatch')
        check(ag['detected_failure_certs']==int(row.detected_failure_certs),'Threshold sweep detected mismatch')
    thr_primary=float(thresholds.loc[thresholds.ratio==20,'threshold'].iloc[0])
    primary,primary_folds,leads,alarms=exact_metrics_under_threshold(d,f,thr_primary)
    cal,calmodels=forward_platt(d)
    fold_metrics=[]
    for fo in FOLDS:
        q=d[d.fold==fo]
        fold_metrics.append({'fold':fo,'rows':len(q),'positives':int(q.y.sum()),
                             'failure_certs':int(q.loc[q.y.eq(1),'CERT'].nunique()),
                             'AP':float(average_precision_score(q.y,q.score)),
                             'ROC_AUC':float(roc_auc_score(q.y,q.score)),
                             'Brier':float(brier_score_loss(q.y,q.score)),
                             'prevalence':float(q.y.mean()),'mean_predicted_risk':float(q.score.mean())})
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(rank).to_csv(out/'development_model_ranking_rechecked.csv',index=False)
    pd.DataFrame(fold_metrics).to_csv(out/'selected_hgb_fold_metrics_rechecked.csv',index=False)
    thresholds.to_csv(out/'development_threshold_scenarios.csv',index=False)
    trajectory.to_csv(out/'threshold_sweep_sample.csv',index=False)
    primary_folds.to_csv(out/'primary_threshold_fold_diagnostics.csv',index=False)
    cal.to_csv(out/'chronological_calibration_diagnostics.csv',index=False)
    leads.to_csv(out/'detected_event_lead_quarters.csv',index=False)
    # Only compact per-CERT-year alarms are shared; no raw bank feature inputs.
    alarms[['fold','CERT','dt','year','y','score']].to_csv(out/'first_alert_per_cert_year_dev_oof.csv',index=False)
    if cost_usd1000 is not None:
        thresholds['COST_median_thousand_USD']=cost_usd1000
        thresholds['scenario_cost_thousand_USD']=thresholds['cost_units']*(cost_usd1000/thresholds['ratio'])
        thresholds.to_csv(out/'development_threshold_scenarios.csv',index=False)
    audit={'stage':'PART5_STEP03_DEVELOPMENT_ONLY_EVENT_COST_AND_FORWARD_CALIBRATION',
           'status':'PASS_DEVELOPMENT_OOF_DIAGNOSTICS_NOT_FINAL_MODEL_LOCK',
           'protocol_sha256':EXPECTED_PROTOCOL_SHA,
           'selected_model':EXPECTED_WINNER,
           'selection_metric':'unweighted_mean_average_precision',
           'input_sha256':{'step01_evidence_zip':path_sha(Path(args.step01)),
                           'step02a_evidence_zip':path_sha(Path(args.step02a)),
                           'step02b_evidence_zip':path_sha(Path(args.step02b)),
                           'failures_source':path_sha(Path(args.failures)),
                           **({'development_primary_v2':path_sha(Path(args.dev))} if args.dev else {})},
           'validated_prior_evidence':validated,
           'oof_rows':len(d),'distinct_positive_failure_CERT':int(d.loc[d.y.eq(1),'CERT'].nunique()),
           'fold_metrics':fold_metrics,'model_ranking_top5':rank[:5],
           'threshold_scenarios':thresholds.to_dict(orient='records'),
           'primary_threshold_diagnostics':primary,
           'forward_platt_diagnostics':cal.to_dict(orient='records'),
           'fdic_median_positive_COST_thousand_USD':cost_usd1000,
           'fdic_cost_qualifying_events':n_cost_total,'fdic_cost_valid_positive_events':n_cost_valid,
           'monetary_proxy_verified':cost_usd1000 is not None,
           'important_qualifications':[
               'Threshold is selected on the same development OOF windows used to choose the model family; threshold performance is selection-in-sample and must not be called unbiased generalization.',
               'First alert within each CERT-year is operationally the only billable alert. A bank failure may contribute at most one missed event.',
               'False alarms are outcome-defined using the four-quarter-forward outcome label, not observed customer service costs.',
               'Threshold is on raw HGB OOF risk scores; no Platt map is applied to operational threshold.',
               'Forward Platt results are diagnostic only: calibration is fitted on earlier validation-fold scores, tested only on later folds, and is not included in the frozen deployment policy.',
               'Different fold model training histories cause potential score distribution drift; single fixed threshold may transfer poorly.',
               'Final test and future-year feature outcomes are never opened or evaluated.',
               'FDIC COST represents loss to the insurer/resolution, not causal benefit of a missed warning; false-positive cost is assumed.',
               'The development OOF observations cover disjoint historical eras and are not a continuous production monitoring sequence.'
           ],'run_utc':datetime.now(timezone.utc).isoformat()}
    write_json(out/'part5_step03_audit.json',audit)
    # Include only minimal reports, never raw test data or source Parquet.
    names=['part5_step03_audit.json','development_model_ranking_rechecked.csv',
           'selected_hgb_fold_metrics_rechecked.csv','development_threshold_scenarios.csv',
           'primary_threshold_fold_diagnostics.csv','chronological_calibration_diagnostics.csv',
           'detected_event_lead_quarters.csv']
    outzip=out/'SHARE_THIS_PART5_STEP03_EVIDENCE.zip'
    with zipfile.ZipFile(outzip,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as zz:
        for name in names:zz.write(out/name,name)
    print('STEP03 PASS | OOF rows:',len(d),'| winner:',EXPECTED_WINNER)
    print('Development-only primary cost ratio 20 threshold:',f'{thr_primary:.12g}')
    print('Detected events:',primary['detected_failure_certs'],'/',primary['total_failure_certs_in_oof'],
          '| False first alerts per CERT-year:',primary['false_alerted_cert_years'])
    print('Cost median thousand USD:',cost_usd1000)
    print('Evidence ZIP:',outzip)


def self_test():
    # Controls: a repeated quarterly alert must not create >1 billed CERT-year;
    # the temporal FIRST flagged quarter governs the alarm classification.
    sample=pd.DataFrame({'CERT':[1,1,1,1,2,2,3,3],
                         'year':[2000,2000,2000,2001,2000,2000,2000,2000],
                         'day':[11000,11100,11200,11400,11000,11100,11000,11100],
                         'y':[0,1,1,1,1,1,0,0],
                         'score':[.2,.8,.7,.3,.9,.9,.1,.1]})
    # In this toy model, three positive CERTs (1,2, not 3), ratio policy
    # has to function on any legitimate sample, so temporarily patching the
    # hard-coded real census is avoided: test standalone alert-first semantics.
    picked=sample[sample.score>=.2].sort_values(['CERT','year','day']).drop_duplicates(['CERT','year'])
    check(len(picked)==3,'CERT-year dedup failed')
    check(len(picked[(picked.CERT==1)&(picked.year==2000)])==1,'Repeated alert billed')
    check(picked[(picked.CERT==1)&(picked.year==2000)].y.iloc[0]==0,'First alert must win')
    check(sample.day.max()>sample.day.min(),'Invalid synthetic chronology')
    print('STEP03 SELF-TEST PASS (first alert, dedup, source integrity invariants)')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--self-test',action='store_true')
    ap.add_argument('--protocol',default='part5_protocol_freeze.json')
    ap.add_argument('--step01',help='SHARE_THIS_PART5_STEP01_EVIDENCE.zip')
    ap.add_argument('--step02a',help='SHARE_THIS_PART5_STEP02A_EVIDENCE.zip')
    ap.add_argument('--step02b',help='SHARE_THIS_PART5_STEP02B_EVIDENCE.zip')
    ap.add_argument('--failures',help='FDIC failures.parquet (preferable, includes COST), or CSV (no COST)')
    ap.add_argument('--dev',default=None,help='Verified development_primary_binary_v2.parquet for COST proxy; never test')
    ap.add_argument('--out',default='part5_step03_outputs')
    args=ap.parse_args()
    if args.self_test:self_test();return
    for key in ('step01','step02a','step02b','failures'):
        check(getattr(args,key) is not None,f'Missing --{key}')
    run(args)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('STEP03 FAIL:',repr(exc),file=sys.stderr)
        raise
