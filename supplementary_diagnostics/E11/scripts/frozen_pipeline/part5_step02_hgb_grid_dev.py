#!/usr/bin/env python3
"""BFT65B Part 5 Step02B: frozen development-only HistGradientBoosting grid.

Strictly follows the hash-frozen preselection protocol. No final-test access,
threshold selection, calibration, or model winner selection. Each fold fits a
fresh sklearn Pipeline using only the respective training window. Output
includes per-fold validation probabilities and independent-audit-friendly keys.
"""
from __future__ import annotations
import argparse
import gc
import hashlib
import json
import math
import os
import platform
import sys
import time
import warnings
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss
from sklearn.pipeline import Pipeline

from part4_v2_train_only_pipeline import FEATURES, make_preprocessor
from part5_step01_baseline_dev_only import (
    FOLD_EXPECTED, audit_dev, check, sha256, verify_protocol,
)

EXPECTED_ROWS=1_231_631
EXPECTED_POSITIVES=9_246


def params_from_protocol(protocol:dict)->list[dict]:
    specs=[m for m in protocol['model_selection']['models'] if m['name']=='hist_gradient_boosting']
    check(len(specs)==1,'Frozen HGB spec missing or duplicated')
    spec=specs[0];hp=spec['hyperparameters']
    check(spec['features']=='Tier1' and len(FEATURES)==len(protocol['feature_policy']['tier1_features']) and set(FEATURES)==set(protocol['feature_policy']['tier1_features']),
          'Tier1 feature set differs from protocol')
    check(hp['max_iter']==[150] and hp['l2_regularization']==[1.0],
          'HGB max_iter or regularization differs from protocol')
    check(hp['max_leaf_nodes']==[15,31] and hp['learning_rate']==[.05,.1],
          'HGB grid differs from frozen protocol')
    candidates=protocol['feature_policy']['clipping_candidates']
    check({q['name'] for q in candidates}=={'none','quantile_1_99'},'Frozen clipping candidates differ')
    out=[]
    for leaves in hp['max_leaf_nodes']:
        for rate in hp['learning_rate']:
            for clip in candidates:
                mode=clip['name']
                if mode=='quantile_1_99':
                    check((clip['lower'],clip['upper'])==(.01,.99),'Clipping quantiles changed')
                else:
                    check(clip['lower'] is None and clip['upper'] is None,'No clipping quantiles should be null')
                cid=f"HGB_L{leaves}_LR{str(rate).replace('.','p')}_I150_L21_CL{'q01_99' if mode=='quantile_1_99' else 'none'}"
                out.append({'config_id':cid,'max_leaf_nodes':int(leaves),'learning_rate':float(rate),
                            'max_iter':150,'l2_regularization':1.0,'clipping':mode})
    check(len(out)==8 and len({c['config_id'] for c in out})==8,'Expected 8 unique HGB configurations')
    return out


def make_model(cfg:dict,seed:int)->Pipeline:
    # Predeclared fixed max_iter=150 means we DO NOT use the default random
    # early-stopping split (which would be unsuitable for time-ordered data).
    return Pipeline([
        ('prep',make_preprocessor(clip=(cfg['clipping']=='quantile_1_99'),lower=.01,upper=.99)),
        ('clf',HistGradientBoostingClassifier(
            max_leaf_nodes=cfg['max_leaf_nodes'],learning_rate=cfg['learning_rate'],
            max_iter=cfg['max_iter'],l2_regularization=cfg['l2_regularization'],
            random_state=seed,early_stopping=False)),
    ])


def fold_keys(out:Path,name:str,va:pd.DataFrame)->None:
    path=out/'fold_keys'/f'{name}.npz'
    expected={'cert':va.CERT.to_numpy(dtype=np.int64),
              'decision_day':va.DECISION_DATE.to_numpy(dtype='datetime64[D]').astype(np.int64),
              'y':va.Y_4Q.to_numpy(dtype=np.uint8)}
    if path.exists():
        with np.load(path,allow_pickle=False) as old:
            check(set(old.files)==set(expected),'Existing fold keys have different schema')
            for k in expected:
                check(np.array_equal(old[k],expected[k]),f'Existing fold keys differ: {name}/{k}')
    else:
        np.savez_compressed(path,**expected)


def one_fold(dev:pd.DataFrame, fold:dict, cfg:dict, seed:int,out:Path)->dict:
    name=fold['id']; train_end=pd.Timestamp(fold['train_end']);start=pd.Timestamp(fold['validation_start']);end=pd.Timestamp(fold['validation_end'])
    gap=start.to_period('Q').ordinal-train_end.to_period('Q').ordinal-1
    check(gap==4,f'{name}: embargo must be four whole calendar quarters')
    tr=dev.loc[dev.DECISION_DATE<=train_end]
    va=dev.loc[dev.DECISION_DATE.between(start,end)]
    observed={'train':len(tr),'valid':len(va),'train_pos':int(tr.Y_4Q.sum()),
              'valid_pos':int(va.Y_4Q.sum()),'valid_certs':int(va.loc[va.Y_4Q.eq(1),'CERT'].nunique())}
    for k,v in FOLD_EXPECTED[name].items():check(observed[k]==v,f'{name}/{k}: {observed[k]} != {v}')
    check(tr.DECISION_DATE.max()+pd.offsets.QuarterEnd(4)<va.DECISION_DATE.min(),
          'Training label horizon intersects validation')
    fold_keys(out,name,va)
    path=out/'predictions'/f'{cfg["config_id"]}__{name}.npz'
    rowpath=out/'trials'/f'{cfg["config_id"]}__{name}.json'
    y=va.Y_4Q.to_numpy(dtype=np.int8)
    if path.exists() and rowpath.exists():
        row=json.loads(rowpath.read_text(encoding='utf-8'))
        check(row['prediction_sha256']==sha256(path),'Existing prediction hash differs')
        with np.load(path,allow_pickle=False) as z:
            p=z['score']
            check(len(p)==len(y),'Resumed score length mismatch')
            check(abs(average_precision_score(y,p)-row['average_precision'])<1e-12,
                  'Resumed AP does not match')
        print('[RESUME]',cfg['config_id'],name,flush=True)
        return row
    check(not path.exists() and not rowpath.exists(), 'Incomplete resume pair: inspect both files before retry')
    xtr=tr[FEATURES];xva=va[FEATURES]
    model=make_model(cfg,seed)
    starttime=time.perf_counter()
    model.fit(xtr,tr.Y_4Q.to_numpy(dtype=np.int8))
    seconds=time.perf_counter()-starttime
    prep=model.named_steps['prep'];cont=prep.named_transformers_['continuous']
    med=cont.named_steps['training_median'].statistics_.copy()
    scl=cont.named_steps['training_robust_scale'].scale_.copy()
    check(len(med)==12 and np.isfinite(med).all(),'Training median invalid')
    check(len(scl)==12 and np.isfinite(scl).all() and np.all(scl>0),'Robust scaling invalid')
    if cfg['clipping']=='quantile_1_99':
        clip=cont.named_steps['training_quantile_clip']
        lower=clip.lower_.copy();upper=clip.upper_.copy()
        check(np.isfinite(lower).all() and np.isfinite(upper).all() and np.all(lower<=upper),'Clipping bounds invalid')
    else:
        clip=None
    check(int(model.named_steps['clf'].n_iter_)==150,'HGB did not fit 150 iterations')
    # Validate transformation cannot mutate fit params.
    p=model.predict_proba(xva)[:,1]
    check(len(p)==len(va) and np.isfinite(p).all() and np.all((p>=0)&(p<=1)),
          'Invalid probability array')
    check(np.array_equal(med,cont.named_steps['training_median'].statistics_) and
          np.array_equal(scl,cont.named_steps['training_robust_scale'].scale_),
          'Validation mutated imputer or scaler')
    if clip is not None:
        check(np.array_equal(lower,clip.lower_) and np.array_equal(upper,clip.upper_),
              'Validation mutated clipping bounds')
    k=max(1,math.ceil(.01*len(va)))
    ordered=np.lexsort((va.DECISION_DATE.to_numpy(dtype='datetime64[D]').astype(np.int64),
                        va.CERT.to_numpy(dtype=np.int64), -p))
    hit=y[ordered[:k]];tp=int(hit.sum())
    row={**cfg,'fold':name,'train_rows':len(tr),'train_positives':int(tr.Y_4Q.sum()),
         'validation_rows':len(va),'validation_positives':int(y.sum()),
         'validation_positive_certs':int(va.loc[va.Y_4Q.eq(1),'CERT'].nunique()),
         'average_precision':float(average_precision_score(y,p)),
         'roc_auc':float(roc_auc_score(y,p)),
         'brier_score':float(brier_score_loss(y,p)),
         'prevalence':float(y.mean()),'mean_prediction':float(p.mean()),
         'prediction_to_prevalence_ratio':float(p.mean()/y.mean()),
         'alerts_at_1pct_capacity':k,'tp_at_1pct_capacity':tp,
         'fp_at_1pct_capacity':int(k-tp),
         'precision_at_1pct_capacity':float(tp/k),
         'recall_at_1pct_capacity':float(tp/y.sum()),
         'fit_seconds':float(seconds),'n_iter':int(model.named_steps['clf'].n_iter_),
         'preprocessing_fitted_on_training_only':True,'final_test_opened':False,
         'early_stopping':False}
    np.savez_compressed(path,score=np.asarray(p,dtype=np.float64))
    row['prediction_sha256']=sha256(path)
    rowpath.write_text(json.dumps(row,indent=2,allow_nan=False),encoding='utf-8')
    print(f'[FIT] {cfg["config_id"]}/{name} AP={row["average_precision"]:.6f} AUC={row["roc_auc"]:.6f}',flush=True)
    del model,tr,va,xtr,xva,p
    gc.collect()
    return row


def finish(out:Path,rows:list[dict], protocol_sha:str,dev_sha:str,script:Path,factory:Path,nrows:int,seed:int)->None:
    detail=pd.DataFrame(rows).sort_values(['config_id','fold']).reset_index(drop=True)
    check(len(detail)==24 and detail[['config_id','fold']].drop_duplicates().shape[0]==24,
          'Incomplete 8-config x 3-fold HGB results')
    mpath=out/'hgb_candidate_fold_metrics.csv';detail.to_csv(mpath,index=False,float_format='%.17g')
    summ=detail.groupby(['config_id','max_leaf_nodes','learning_rate','max_iter','l2_regularization','clipping'],as_index=False).agg(
        folds=('fold','nunique'),mean_ap=('average_precision','mean'),
        mean_roc_auc=('roc_auc','mean'),mean_brier=('brier_score','mean'),
        mean_precision_at_1pct=('precision_at_1pct_capacity','mean'),
        mean_recall_at_1pct=('recall_at_1pct_capacity','mean'),
        total_fit_seconds=('fit_seconds','sum'))
    check(len(summ)==8 and summ.folds.eq(3).all(),'Incomplete HGB configuration summary')
    summ=summ.sort_values(['mean_ap','config_id'],ascending=[False,True])
    spath=out/'hgb_candidate_summary.csv';summ.to_csv(spath,index=False,float_format='%.17g')
    preds=sorted((out/'predictions').glob('*.npz'))
    trials=sorted((out/'trials').glob('*.json'))
    keys=sorted((out/'fold_keys').glob('*.npz'))
    check(len(preds)==24 and len(trials)==24 and len(keys)==3,'Missing prediction/trial/key files')
    allfiles=[mpath,spath,*keys,*preds]
    audit={'stage':'PART5_STEP02B_FROZEN_HGB_GRID_DEVELOPMENT_ONLY',
           'status':'COMPLETE_NO_MODEL_SELECTED',
           'protocol_sha256':protocol_sha,'development_sha256':dev_sha,
           'rows_in_development':nrows,'script_sha256':sha256(script),
           'factory_sha256':sha256(factory), 'seed':seed,'folds':3,
           'configs':8,'measured_fits':24,'early_stopping':False,
           'final_test_opened':False,'threshold_selected':False,'calibration_fit':False,
           'environment':{'python':platform.python_version(),'pandas':pd.__version__,
                          'sklearn':sklearn.__version__,'numpy':np.__version__},
           'output_sha256':{p.relative_to(out).as_posix():sha256(p) for p in allfiles},
           'limitations':['No calibration or cost-based threshold yet',
                          '1% capacity is pooled validation diagnostic, not deployable time-local threshold',
                          'No final-test files accessed']}
    apath=out/'part5_step02b_audit.json';apath.write_text(json.dumps(audit,indent=2),encoding='utf-8')
    zipname=out/'SHARE_THIS_PART5_STEP02B_EVIDENCE.zip'
    with zipfile.ZipFile(zipname,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=4) as z:
        for p in [apath,*allfiles]:z.write(p,arcname=p.relative_to(out).as_posix())
    with zipfile.ZipFile(zipname) as z:check(z.testzip() is None,'Output ZIP CRC error')
    print('STEP 02B COMPLETE: 24 HGB fits, NO test or threshold evaluation')
    print('SEND THIS FILE:',zipname)


def self_test(protocol:dict)->None:
    configs=params_from_protocol(protocol)
    rng=np.random.default_rng(42)
    d=pd.DataFrame({col:rng.normal(size=480) for col in FEATURES})
    for col in ['negative_equity_flag','loss_flag_roa_negative','loan_denominator_invalid_flag']:
        d[col]=rng.integers(0,2,len(d)).astype(float)
    d.loc[::13,'asset_log_growth_4q']=np.nan
    y=np.zeros(480,dtype=np.uint8);y[rng.choice(480,35,replace=False)]=1
    for c in [configs[0],configs[-1]]:
        model=make_model(c,protocol['model_selection']['seed'])
        model.fit(d.iloc[:400],y[:400]);p=model.predict_proba(d.iloc[400:])[:,1]
        check(p.shape==(80,) and np.isfinite(p).all(),'Synthetic HGB predict failed')
        check(model.named_steps['clf'].n_iter_==150,'HGB iter count wrong')
        check(model.named_steps['prep'].transform(d.iloc[400:]).shape==(80,30),'Preprocessor width wrong')
        median=model.named_steps['prep'].named_transformers_['continuous'].named_steps['training_median'].statistics_.copy()
        noisy=d.iloc[400:].copy();noisy.iloc[0,0]=1e12
        model.predict_proba(noisy)
        check(np.array_equal(median,model.named_steps['prep'].named_transformers_['continuous'].named_steps['training_median'].statistics_),
              'Synthetic validation changed training medians')
    print('STEP 02B SYNTHETIC SELF-TEST PASS (two HGB configs, 150 fixed iterations, 30 features, no validation fit)')


def main()->None:
    ap=argparse.ArgumentParser()
    ap.add_argument('--protocol',type=Path,required=True)
    ap.add_argument('--dev',type=Path)
    ap.add_argument('--out',type=Path,default=Path('part5_step02b_outputs'))
    ap.add_argument('--self-test',action='store_true')
    a=ap.parse_args()
    protocol,ph=verify_protocol(a.protocol)
    cfg=params_from_protocol(protocol)
    if a.self_test:self_test(protocol);return
    check(a.dev is not None and a.dev.is_file() and a.dev.name=='development_primary_binary_v2.parquet',
          'Development V2 parquet required; refuse other file names')
    dsha=sha256(a.dev)
    check(dsha==protocol['data_contract']['input_shas']['development_primary_v2'],'Development file hash differs from frozen contract')
    out=a.out;out.mkdir(parents=True,exist_ok=True)
    for sub in ['fold_keys','predictions','trials']:(out/sub).mkdir(exist_ok=True)
    script=Path(__file__).resolve();factory=script.with_name('part4_v2_train_only_pipeline.py')
    contract={'protocol_sha256':ph,'development_sha256':dsha,
              'script_sha256':sha256(script),'factory_sha256':sha256(factory)}
    metap=out/'run_contract.json'
    if metap.exists():
        check(json.loads(metap.read_text())==contract,'Run contract differs; refuse to mix predictions')
    else:metap.write_text(json.dumps(contract,indent=2))
    print('Read development V2 only; final test is not read.',flush=True)
    dev=pd.read_parquet(a.dev)
    for c in ['DECISION_DATE','SOURCE_REPDTE']:dev[c]=pd.to_datetime(dev[c],errors='raise')
    observed=audit_dev(dev,expected=True)
    check(observed['rows']==EXPECTED_ROWS and observed['positives']==EXPECTED_POSITIVES,'Unexpected development rows/positives')
    check(len(cfg)*len(protocol['validation']['folds'])==24,'Unexpected number of HGB trials')
    rows=[]
    for config in cfg:
        for fold in protocol['validation']['folds']:
            rows.append(one_fold(dev,fold,config,protocol['model_selection']['seed'],out))
    finish(out,rows,ph,dsha,script,factory,len(dev),protocol['model_selection']['seed'])

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('STEP02B FAILED:',type(exc).__name__+':',str(exc),file=sys.stderr,flush=True)
        raise
