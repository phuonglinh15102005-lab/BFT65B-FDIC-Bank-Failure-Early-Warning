#!/usr/bin/env python3
"""Post-lock development-only sensitivity audit for a frozen FDIC HGB.

No test files, no hyperparameter selection, no threshold search, and no substitution
of primary metrics. Reports out-of-time discrimination conditional on observed
positive equity and the structural label-horizon overlap in intentionally INVALID
random K-fold partitions. A random K-fold MODEL IS NEVER FIT.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, sys, math
from pathlib import Path

EXPECTED_DEV_SHA = 'd365ce25204a3dcace715db4cea259c94b1b1abba4822c7bcf2b050a1c7f6a73'
MODEL_ID = 'HGB_L15_LR0p05_I150_L21_CLnone'
REF_AP = {'early_bank_stress':0.36044019935122096,
          'post_stress_transition':0.24694556511510515,
          'global_financial_crisis':0.27991311344211933}
LOCKED_POLICY_THRESHOLD = 0.023971438944668057


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def check(ok,msg):
    if not ok:
        raise RuntimeError(msg)


def save_csv(path, rows):
    if not rows:
        return
    with path.open('w',encoding='utf-8',newline='') as stream:
        wr=csv.DictWriter(stream,fieldnames=list(rows[0]));wr.writeheader();wr.writerows(rows)


def scores(y,p):
    """Subgroup performance, with explicit degenerate-class handling."""
    import numpy as np
    from sklearn.metrics import average_precision_score,roc_auc_score
    y=np.asarray(y).astype(int);p=np.asarray(p,dtype=float)
    out={'n_rows':int(len(y)),'n_positive':int(y.sum()),'prevalence':float(y.mean()) if len(y) else None,
         'AP':None,'AUC':None,'AP_over_prevalence':None,
         'n_alert_at_frozen_cutoff':int((p>=LOCKED_POLICY_THRESHOLD).sum()),
         'n_true_alert_at_frozen_cutoff':int((y[p>=LOCKED_POLICY_THRESHOLD]==1).sum()),
         'recall_at_frozen_cutoff':None,'precision_at_frozen_cutoff':None}
    if len(y) and 0<y.sum()<len(y):
        out['AP']=float(average_precision_score(y,p))
        out['AUC']=float(roc_auc_score(y,p))
        out['AP_over_prevalence']=float(out['AP']/out['prevalence'])
        out['recall_at_frozen_cutoff']=float(out['n_true_alert_at_frozen_cutoff']/int(y.sum()))
    if out['n_alert_at_frozen_cutoff']:
        out['precision_at_frozen_cutoff']=float(out['n_true_alert_at_frozen_cutoff']/out['n_alert_at_frozen_cutoff'])
    return out


def random_fold_overlap_positive(dev):
    """Quantify shared same-bank/near-quarter positive labels in INVALID random K-fold.

    Only counts structural overlapping future-four-quarter outcomes. Does not fit
    invalid models and does not calculate a hypothetical random-K-fold AP. The
    five-fold assignments are illustrative and are NOT an alternative CV design.
    """
    import numpy as np
    import pandas as pd
    rng=np.random.default_rng(20261122)
    assigned=np.empty(len(dev),dtype=np.int8)
    permutation=rng.permutation(len(dev))
    assigned[permutation] = np.arange(len(dev),dtype=np.int64)%5
    positive=dev.loc[dev.Y_4Q.eq(1),['CERT','DECISION_DATE']].copy()
    positive['fold']=assigned[dev.Y_4Q.to_numpy()==1]
    dates=pd.to_datetime(positive.DECISION_DATE)
    positive['quarter_index']=(dates.dt.year.astype('int32')*4+dates.dt.quarter.astype('int32')).to_numpy()
    eligible=np.zeros(len(positive),dtype=bool)
    for _, group in positive.groupby('CERT',sort=False):
        if len(group)<2:
            continue
        locs=positive.index.get_indexer(group.index)
        quarters=group['quarter_index'].to_numpy()
        folds=group['fold'].to_numpy()
        for j in range(len(group)):
            eligible[locs[j]] = bool(np.any((np.abs(quarters-quarters[j])<=3)&(folds!=folds[j])))
    result=[]
    for fold in range(5):
        fmask=(positive['fold'].to_numpy()==fold)
        n=int(fmask.sum());hits=int(eligible[fmask].sum())
        result.append(dict(invalid_random_fold=fold+1,validation_positive_decisions=n,
                           validation_positive_decisions_with_other_fold_same_CERT_positive_within_3_quarters=hits,
                           share=hits/n if n else None,random_state=20261122,
                           interpretation='STRUCTURAL_OVERLAP_ONLY_NOT_AN_AP_ESTIMATE'))
    return result


def run(dev_path,source,out):
    import numpy as np
    import pandas as pd
    check(dev_path.name=='development_primary_binary_v2.parquet','Refuse nondevelopment source name')
    check(sha(dev_path)==EXPECTED_DEV_SHA,'Development SHA mismatch. Do not run on other inputs')
    check(not out.exists(),'Output already exists. Create a fresh directory')
    sys.path.insert(0,str(source.resolve()))
    from part5_step01_baseline_dev_only import audit_dev, verify_protocol
    from part5_step02_hgb_grid_dev import make_model, params_from_protocol
    from part4_v2_train_only_pipeline import FEATURES
    protocol,protocol_sha=verify_protocol(source/'part5_protocol_freeze.json')
    check(protocol_sha=='994f72de6e2446916db8c2fcd36847c45cc68eb6fef5ef67f07acc0476c6d911', 'Protocol SHA mismatch')
    cfg=next(x for x in params_from_protocol(protocol) if x['config_id']==MODEL_ID)
    check(cfg['max_iter']==150 and cfg['max_leaf_nodes']==15 and cfg['clipping']=='none','HGB configuration drift')
    dev=pd.read_parquet(dev_path)
    for col in ['DECISION_DATE','SOURCE_REPDTE']:
        dev[col]=pd.to_datetime(dev[col],errors='raise')
    audit_dev(dev,expected=True)
    check('equity_to_assets' in FEATURES,'Equity predictor not present in frozen schema')
    check('CERT' in dev.columns and 'Y_4Q' in dev.columns,'Missing keys/labels')
    out.mkdir(parents=True)
    detail=[]
    event=[]
    for spec in protocol['validation']['folds']:
        name=spec['id'];train_end=pd.Timestamp(spec['train_end']);va_start=pd.Timestamp(spec['validation_start']);va_end=pd.Timestamp(spec['validation_end'])
        check((va_start.to_period('Q').ordinal-train_end.to_period('Q').ordinal-1)==4,'Label-horizon gap altered')
        tr=dev.loc[dev.DECISION_DATE.le(train_end)]
        va=dev.loc[dev.DECISION_DATE.between(va_start,va_end)]
        model=make_model(cfg,protocol['model_selection']['seed'])
        model.fit(tr[FEATURES],tr.Y_4Q.to_numpy(dtype=np.int8))
        p=model.predict_proba(va[FEATURES])[:,1]
        check(np.isfinite(p).all() and ((p>=0)&(p<=1)).all(),'Predicted values invalid')
        overall=scores(va.Y_4Q.to_numpy(),p)
        check(abs(overall['AP']-REF_AP[name])<5e-6,f'Frozen validation AP changed in {name}')
        eq=pd.to_numeric(va['equity_to_assets'],errors='coerce').to_numpy()
        # Use observed data ONLY. Unknown/missing equity is excluded, never imputed to positive.
        conditions=[('all_validation',np.ones(len(va),dtype=bool)),
                    ('observed_positive_equity',np.isfinite(eq)&(eq>0)),
                    ('observed_nonpositive_equity',np.isfinite(eq)&(eq<=0)),
                    ('equity_missing',~np.isfinite(eq))]
        for subgroup,mask in conditions:
            s=scores(va.Y_4Q.to_numpy()[mask],p[mask])
            detail.append({'fold':name,'subgroup':subgroup,**s,'positive_equity_condition':'source-report EQ/ASSET > 0; no future accounting data',
                           'note':'POST_LOCK_DEV_ONLY_SUBGROUP_NOT_FOR_MODEL_OR_THRESHOLD_SELECTION'})
        y=va.Y_4Q.to_numpy(dtype=int)
        cert=va.CERT.to_numpy()
        # A bank is eligible when a positive-equity label-positive decision is observable in that fold.
        pos_eligible=(y==1)&np.isfinite(eq)&(eq>0)
        eligible_cert=set(cert[pos_eligible].tolist())
        hit_cert=set(cert[pos_eligible&(p>=LOCKED_POLICY_THRESHOLD)].tolist())
        event.append({'fold':name,'failure_CERT_with_positive_equity_positive_decision':len(eligible_cert),
                      'failure_CERT_with_at_least_one_positive_equity_alert':len(hit_cert),
                      'within_eligible_CERT_detection_share':len(hit_cert)/len(eligible_cert) if eligible_cert else None,
                      'policy_threshold':LOCKED_POLICY_THRESHOLD,
                      'note':'EXPLORATORY_IN_DEVELOPMENT_OUT_OF_FOLD; THRESHOLD_CHOSEN_ON_DEVELOPMENT_AND_NOT_INDEPENDENT'})
        print(f'{name}: archived AP {overall["AP"]:.6f}, positive-equity AP {detail[-3]["AP"] if detail[-3]["AP"] is not None else "undefined"}',flush=True)
        del model,tr,va,p
    save_csv(out/'positive_equity_subgroup_fold_metrics.csv',detail)
    save_csv(out/'positive_equity_eligible_event_detection.csv',event)
    overlap=random_fold_overlap_positive(dev)
    save_csv(out/'invalid_random_kfold_label_overlap_demo.csv',overlap)
    manifest={'scope':'FROZEN_SELECTED_HGB_POST_LOCK_DEVELOPMENT_ONLY_EXPLORATORY','development_sha256':EXPECTED_DEV_SHA,
              'protocol_sha256':protocol_sha,'frozen_model_id':MODEL_ID,'refits':3,'invalid_random_kfold_models_fitted':0,
              'locked_test_opened':False,'locked_test_scored':False,'threshold_modified':False,
              'important_limits':['Positive equity means EQ/ASSET>0 at lagged source report, not a regulatory solvency certification',
                                  'Conditional AP comparisons are affected by selection and subgroup prevalence',
                                  'Development policy threshold and event-detection summaries are exploratory, not external validation',
                                  'Random K-fold diagnostic identifies shared positive label-horizon structure but DOES NOT measure AP inflation',
                                  'Neither overfitting nor temporal drift is identified causally by these diagnostics'],
              'output_sha256':{p.name:sha(p) for p in sorted(out.glob('*.csv'))}}
    (out/'E12_MANIFEST.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    print('PASS: no final test files accessed; no model/threshold changes; 3 chronological refits.',flush=True)


def synthetic_check():
    """Test overlap and subgroup arithmetic without any private user data."""
    import pandas as pd
    import numpy as np
    d=pd.DataFrame({'CERT':[1,1,1,1,2,2,2,3,3],
                    'DECISION_DATE':pd.to_datetime(['1987-03-31','1987-06-30','1987-09-30','1987-12-31','1987-03-31','1987-06-30','1987-09-30','1987-03-31','1987-06-30']),
                    'Y_4Q':[1,1,1,1,0,0,1,0,1]})
    out=random_fold_overlap_positive(d)
    check(len(out)==5 and sum(x['validation_positive_decisions'] for x in out)==6,'Overlap self-test failed')
    m=scores([0,0,1,1],[0.1,0.2,0.8,0.9]);check(abs(m['AP']-1)<1e-12,'Metrics self-test failed')
    print('PASS: synthetic arithmetic, random-Kfold structural check (NO model), no data files opened')

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--self-test',action='store_true')
    ap.add_argument('--dev',type=Path)
    ap.add_argument('--source',type=Path)
    ap.add_argument('--out',type=Path)
    args=ap.parse_args()
    if args.self_test: synthetic_check()
    else:
        if not args.dev or not args.source or not args.out: ap.error('--dev, --source and --out are required')
        run(args.dev,args.source,args.out)
