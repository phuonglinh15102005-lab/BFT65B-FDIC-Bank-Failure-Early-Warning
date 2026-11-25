#!/usr/bin/env python3
"""BFT65B Part5 Step02A: frozen development-only Logistic L2 grid.

No final test, model selection, threshold tuning or calibration.
Emits fold-level OOF predictions as npz with a strict provenance manifest.
The entire candidate family and hyperparameter grid come from immutable
part5_protocol_freeze.json (SHA256 enforced).
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
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss
from sklearn.pipeline import Pipeline

from part4_v2_train_only_pipeline import FEATURES, make_preprocessor
from part5_step01_baseline_dev_only import (
    EXPECTED_PROTOCOL_SHA256, FOLD_EXPECTED, audit_dev, check,
    sha256, verify_protocol,
)

EXPECTED_PRIMARY_ROWS = 1_231_631
EXPECTED_POSITIVES = 9_246


def params_from_protocol(protocol: dict) -> list[dict]:
    spec = [x for x in protocol['model_selection']['models'] if x['name'] == 'logistic_L2']
    check(len(spec) == 1, 'Frozen logistic_L2 family missing/duplicated')
    spec = spec[0]
    hp = spec['hyperparameters']
    check(hp['solver'] == ['lbfgs'] and hp['max_iter'] == [1000],
          'Unexpected solver or maximum iterations')
    check(spec['features'] == 'Tier1' and set(FEATURES) == set(protocol['feature_policy']['tier1_features']),
          'Tier1 feature contract mismatch')
    cl = protocol['feature_policy']['clipping_candidates']
    check({x['name'] for x in cl} == {'none','quantile_1_99'}, 'Clipping protocol changed')
    grid=[]
    for C in hp['C']:
        for cw in hp['class_weight']:
            for clip in cl:
                clip_name = clip['name']
                if clip_name == 'quantile_1_99':
                    check(clip['lower'] == 0.01 and clip['upper'] == 0.99,
                          'Quantile candidate differs from frozen protocol')
                else:
                    check(clip['lower'] is None and clip['upper'] is None,
                          'No-clipping candidate changed')
                code=f"LR_C{str(C).replace('.','p')}_W{'balanced' if cw=='balanced' else 'none'}_CL{'q01_99' if clip_name=='quantile_1_99' else 'none'}"
                grid.append({'config_id':code,'C':float(C),'class_weight':cw,
                             'clipping':clip_name,'clip_lower':clip['lower'],'clip_upper':clip['upper']})
    check(len(grid)==12 and len({v['config_id'] for v in grid})==12,
          'Expected exactly 12 unique logistic candidates')
    return grid


def build_pipeline(cfg: dict, seed: int) -> Pipeline:
    return Pipeline([
        ('prep', make_preprocessor(clip=(cfg['clipping']=='quantile_1_99'),
                                   lower=0.01, upper=0.99)),
        ('clf', LogisticRegression(C=cfg['C'], class_weight=cfg['class_weight'],
                                   solver='lbfgs',max_iter=1000,random_state=seed))
    ])


def keep_fold_keys(out:Path, fold:str, valid:pd.DataFrame)->None:
    dest=out/'fold_keys'/f'{fold}.npz'
    expected={'cert': valid['CERT'].to_numpy(dtype=np.int64),
              'decision_day':valid['DECISION_DATE'].to_numpy(dtype='datetime64[D]').astype(np.int64),
              'y':valid['Y_4Q'].to_numpy(dtype=np.uint8)}
    if dest.is_file():
        with np.load(dest,allow_pickle=False) as a:
            check(set(a.files)==set(expected),'Existing fold-keys schema differs')
            for k,v in expected.items():
                check(np.array_equal(a[k],v),f'Fold-key snapshot changed: {fold}/{k}')
    else:
        np.savez_compressed(dest, **expected)


def one_fold(df:pd.DataFrame, fold:dict, cfg:dict, seed:int, out:Path)->dict:
    name=fold['id']; train_end=pd.Timestamp(fold['train_end']);start=pd.Timestamp(fold['validation_start']);end=pd.Timestamp(fold['validation_end'])
    embargo_q = start.to_period('Q').ordinal-train_end.to_period('Q').ordinal-1
    check(embargo_q==4,'Not four full embargo quarters')
    train=df.loc[df['DECISION_DATE'].le(train_end)]
    valid=df.loc[df['DECISION_DATE'].between(start,end)]
    observed={'train':len(train),'valid':len(valid),'train_pos':int(train.Y_4Q.sum()),
              'valid_pos':int(valid.Y_4Q.sum()),'valid_certs':int(valid.loc[valid.Y_4Q.eq(1),'CERT'].nunique())}
    for k,v in FOLD_EXPECTED[name].items():check(observed[k]==v,f'{name}/{k}: {observed[k]} != {v}')
    check(train['DECISION_DATE'].max()+pd.offsets.QuarterEnd(4)<valid['DECISION_DATE'].min(),
          'Training label horizon overlaps validation')
    keep_fold_keys(out,name,valid)
    pred_path=out/'predictions'/f"{cfg['config_id']}__{name}.npz"
    row_path=out/'trials'/f"{cfg['config_id']}__{name}.json"
    if pred_path.is_file() and row_path.is_file():
        row=json.loads(row_path.read_text(encoding='utf-8'))
        check(row.get('prediction_sha256')==sha256(pred_path),'Saved prediction hash mismatch during resume')
        with np.load(pred_path,allow_pickle=False) as arr:
            score=arr['score']; y=valid['Y_4Q'].to_numpy(dtype=np.int8)
            check(len(score)==len(y),'Resume prediction length mismatch')
            check(np.isclose(row['average_precision'],average_precision_score(y,score),atol=1e-12),
                  'Cached metric/predictions mismatch')
        print('[RESUME]',cfg['config_id'],name,flush=True)
        return row
    if pred_path.exists() or row_path.exists():
        raise RuntimeError('Incomplete resume pair; inspect or remove both '+str(pred_path)+' / '+str(row_path))
    Xtr=train[FEATURES]; ytr=train.Y_4Q.to_numpy(dtype=np.int8)
    Xva=valid[FEATURES];y=valid.Y_4Q.to_numpy(dtype=np.int8)
    model=build_pipeline(cfg,seed)
    t0=time.perf_counter()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always',ConvergenceWarning)
        model.fit(Xtr,ytr)
    fit_seconds=time.perf_counter()-t0
    conv_msgs=[str(w.message) for w in caught if issubclass(w.category,ConvergenceWarning)]
    check(not conv_msgs,'Logistic convergence warning: '+repr(conv_msgs))
    check(int(model.named_steps['clf'].n_iter_[0]) < 1000,'Logistic solver did not converge')
    check(int(model.named_steps['clf'].n_features_in_)==30,'Preprocessor width must be 30')
    prep=model.named_steps['prep']; cont=prep.named_transformers_['continuous']
    median=cont.named_steps['training_median'].statistics_
    check(len(median)==12 and np.isfinite(median).all(),'Training medians invalid')
    robust=cont.named_steps['training_robust_scale']
    check(len(robust.scale_)==12 and np.isfinite(robust.scale_).all() and np.all(robust.scale_>0),
          'Train-only scaling invalid')
    if cfg['clipping']=='quantile_1_99':
        clipper=cont.named_steps['training_quantile_clip']
        check(np.all(clipper.upper_>=clipper.lower_) and np.isfinite(clipper.upper_).all() and np.isfinite(clipper.lower_).all(),
              'Invalid training-fitted clipping quantiles')
    else:
        clipper=None
    median_snapshot=median.copy();scale_snapshot=robust.scale_.copy()
    if clipper is not None:qlo,qhi=clipper.lower_.copy(),clipper.upper_.copy()
    score=model.predict_proba(Xva)[:,1]
    check(np.isfinite(score).all() and np.all((score>=0)&(score<=1)), 'Invalid candidate probability')
    # Predictor transform must not mutate trained preprocessing.
    check(np.array_equal(median_snapshot,cont.named_steps['training_median'].statistics_) and
          np.array_equal(scale_snapshot,cont.named_steps['training_robust_scale'].scale_),
          'Validation unexpectedly modified fitted preprocessing')
    if clipper is not None:
        check(np.array_equal(qlo,clipper.lower_) and np.array_equal(qhi,clipper.upper_),
              'Validation modified clipping thresholds')
    k=max(1,math.ceil(.01*len(valid)))
    # The 1%-capacity ranking is a descriptive operating point, not a selected alarm threshold.
    ordered=np.lexsort((valid['DECISION_DATE'].to_numpy(dtype='datetime64[D]').astype(np.int64),
                        valid['CERT'].to_numpy(dtype=np.int64), -score))
    idx=ordered[:k]
    tp=int(y[idx].sum());fp=int(k-tp)
    row={**cfg,'fold':name,'train_rows':len(train),'train_positives':int(ytr.sum()),
         'validation_rows':len(valid),'validation_positives':int(y.sum()),
         'validation_positive_certs':int(valid.loc[valid.Y_4Q.eq(1),'CERT'].nunique()),
         'average_precision':float(average_precision_score(y,score)),
         'roc_auc':float(roc_auc_score(y,score)),
         'brier_score':float(brier_score_loss(y,score)),
         'prevalence':float(y.mean()),'mean_prediction':float(np.mean(score)),
         'prediction_to_prevalence_ratio':float(np.mean(score)/np.mean(y)),
         'alerts_at_1pct_capacity':k,'tp_at_1pct_capacity':tp,'fp_at_1pct_capacity':fp,
         'precision_at_1pct_capacity':float(tp/k),'recall_at_1pct_capacity':float(tp/int(y.sum())),
         'fit_seconds':float(fit_seconds),'n_iter':int(model.named_steps['clf'].n_iter_[0]),
         'preprocessing_fitted_on_training_only':True,'final_test_opened':False}
    np.savez_compressed(pred_path,score=np.asarray(score,dtype=np.float64))
    row['prediction_sha256']=sha256(pred_path)
    row_path.write_text(json.dumps(row,indent=2,allow_nan=False),encoding='utf-8')
    del model,train,valid,score
    gc.collect()
    print(f"[FIT] {cfg['config_id']} / {name}: AP={row['average_precision']:.6f}, AUC={row['roc_auc']:.5f}, {fit_seconds:.1f}s",flush=True)
    return row


def complete_outputs(out:Path, rows:list[dict], protocol_sha:str, dev_sha:str, script:Path, factory:Path, dataset_rows:int, seed:int)->Path:
    detail=pd.DataFrame(rows).sort_values(['config_id','fold']).reset_index(drop=True)
    check(len(detail)==36 and detail[['config_id','fold']].drop_duplicates().shape[0]==36,
          'Incomplete frozen logistic grid: expected 12 x 3 fold fits')
    detail_path=out/'logistic_candidate_fold_metrics.csv'; detail.to_csv(detail_path,index=False,float_format='%.17g')
    summary=detail.groupby(['config_id','C','class_weight','clipping'],dropna=False,as_index=False).agg(
       folds=('fold','nunique'),mean_ap=('average_precision','mean'),mean_roc_auc=('roc_auc','mean'),
       mean_brier=('brier_score','mean'),mean_precision_at_1pct=('precision_at_1pct_capacity','mean'),
       mean_recall_at_1pct=('recall_at_1pct_capacity','mean'),total_fit_seconds=('fit_seconds','sum'))
    check(len(summary)==12 and summary.folds.eq(3).all(),'Missing configuration or fold')
    summary=summary.sort_values(['mean_ap','config_id'],ascending=[False,True])
    summary_path=out/'logistic_candidate_summary.csv';summary.to_csv(summary_path,index=False,float_format='%.17g')
    trial_files=sorted((out/'trials').glob('*.json'))
    pred_files=sorted((out/'predictions').glob('*.npz'))
    check(len(trial_files)==36 and len(pred_files)==36,'Inconsistent prediction/trial counts')
    manifest={'stage':'PART5_STEP02A_FROZEN_LOGISTIC_GRID_DEVELOPMENT_ONLY',
              'status':'COMPLETE_NO_MODEL_SELECTED','protocol_sha256':protocol_sha,'development_sha256':dev_sha,
              'rows_in_development':dataset_rows,'script_sha256':sha256(script),
              'factory_sha256':sha256(factory),'seed':seed,'folds':3,'configs':12,'measured_fits':36,
              'final_test_opened':False,'threshold_selected':False,'calibration_fit':False,
              'system':{'python':platform.python_version(),'pandas':pd.__version__,
                        'sklearn':sklearn.__version__,'numpy':np.__version__, 'platform':platform.platform()},
              'output_sha256':{x.relative_to(out).as_posix():sha256(x) for x in [detail_path,summary_path, *sorted((out/'fold_keys').glob('*.npz')), *pred_files]},
              'limitations':['No HGB fits yet, so no cross-family model choice',
                             'Top 1 percent alert counts are descriptive and not a deployed threshold',
                             'Repeated bank-quarter outcomes require clustered uncertainty in later analysis']}
    audit=out/'part5_step02a_audit.json';audit.write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    # Store probability arrays to permit independent AP and threshold recalculation.
    archive=out/'SHARE_THIS_PART5_STEP02A_EVIDENCE.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=4) as z:
        for file in [audit,detail_path,summary_path,*sorted((out/'fold_keys').glob('*.npz')), *pred_files]:
            z.write(file,arcname=file.relative_to(out).as_posix())
    with zipfile.ZipFile(archive) as z:check(z.testzip() is None,'Evidence ZIP CRC failed')
    print('\nDONE. All 36 frozen Logistic L2 fits completed; NO final test; NO winner selected.')
    print('SEND:',archive)
    return archive


def self_test(protocol:dict)->None:
    cfg=params_from_protocol(protocol)
    rng=np.random.default_rng(20261114)
    a=pd.DataFrame({f:rng.normal(0,1,600) for f in FEATURES})
    a.loc[a.index[::11],'asset_log_growth_4q']=np.nan
    for f in ['negative_equity_flag','loss_flag_roa_negative','loan_denominator_invalid_flag']:
        a[f]=rng.integers(0,2,len(a)).astype(float)
    y=np.zeros(600,dtype=int)
    y[rng.choice(600,size=60,replace=False)]=1
    for c in (cfg[0],cfg[-1]):
        model=build_pipeline(c,protocol['model_selection']['seed'])
        model.fit(a.iloc[:500],y[:500]);p=model.predict_proba(a.iloc[500:])[:,1]
        check(len(p)==100 and np.isfinite(p).all(),'Synthetic model failed')
        check(model.named_steps['clf'].n_features_in_==30,'Synthetic preprocessor wrong width')
        med=model.named_steps['prep'].named_transformers_['continuous'].named_steps['training_median'].statistics_.copy()
        aa=a.iloc[500:].copy();aa.iloc[0,0]=1e20;model.predict_proba(aa)
        check(np.array_equal(med,model.named_steps['prep'].named_transformers_['continuous'].named_steps['training_median'].statistics_),
              'Validation mutated learned median')
    print('SELF-TEST PASS: protocol grid, 30-column pipeline, clipping, validation-invariance, predictions')


def main()->None:
    ap=argparse.ArgumentParser(description='BFT65B Part5 Step02A: frozen DEV-ONLY Logistic L2 grid')
    ap.add_argument('--protocol',type=Path,required=True)
    ap.add_argument('--dev',type=Path)
    ap.add_argument('--out',type=Path,default=Path('part5_step02a_outputs'))
    ap.add_argument('--self-test',action='store_true')
    args=ap.parse_args()
    protocol,sha=verify_protocol(args.protocol)
    configs=params_from_protocol(protocol)
    if args.self_test:
        self_test(protocol);return
    check(args.dev is not None and args.dev.name=='development_primary_binary_v2.parquet' and args.dev.is_file(),
          'Development-only Parquet required; refuse all other names')
    devsha=sha256(args.dev)
    check(devsha==protocol['data_contract']['input_shas']['development_primary_v2'],
          'Development snapshot SHA256 changed; refuse experiment')
    out=args.out;out.mkdir(parents=True,exist_ok=True)
    for sub in ['predictions','fold_keys','trials']:(out/sub).mkdir(exist_ok=True)
    meta=out/'run_contract.json'
    contract={'protocol_sha256':sha,'development_sha256':devsha,
              'script_sha256':sha256(Path(__file__)),'factory_sha256':sha256(Path(__file__).with_name('part4_v2_train_only_pipeline.py'))}
    if meta.is_file():
        check(json.loads(meta.read_text())==contract,'Output dir contains results from different source/protocol/code; STOP')
    else:meta.write_text(json.dumps(contract,indent=2),encoding='utf-8')
    print('Reading ONLY development V2; no test file is accessed.',flush=True)
    dev=pd.read_parquet(args.dev)
    for c in ['DECISION_DATE','SOURCE_REPDTE']:dev[c]=pd.to_datetime(dev[c],errors='raise')
    observed=audit_dev(dev,expected=True)
    check(observed['rows']==EXPECTED_PRIMARY_ROWS and observed['positives']==EXPECTED_POSITIVES,
          'Unexpected development cohort size')
    check(len(configs)*len(protocol['validation']['folds'])==36,'Unexpected number of candidate fits')
    rows=[]
    for cfg in configs:
        for fold in protocol['validation']['folds']:
            rows.append(one_fold(dev,fold,cfg,protocol['model_selection']['seed'],out))
    complete_outputs(out,rows,sha,devsha,Path(__file__),Path(__file__).with_name('part4_v2_train_only_pipeline.py'),len(dev),protocol['model_selection']['seed'])


if __name__=='__main__':
    try:main()
    except Exception as e:
        print('STEP02A FAILED:',type(e).__name__+':',str(e),file=sys.stderr,flush=True)
        raise
