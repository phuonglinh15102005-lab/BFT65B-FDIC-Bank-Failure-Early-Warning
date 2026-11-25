#!/usr/bin/env python3
"""Audit V2 PRIMARY development cohort and train-only preprocessing; NO test access.

This is NOT a model benchmark or final model fit. A fresh pipeline is fitted
inside each training period, then validation is transformed without refitting.
The only data input is development_primary_binary_v2.parquet and its V2 audit.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import platform
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from part4_v2_train_only_pipeline import (
    FEATURES, CONTINUOUS, BINARY, make_preprocessor,
)

FOLDS = [
    ("early_bank_stress", "1987-12-31", "1989-03-31", "1990-12-31"),
    ("post_stress_transition", "1990-12-31", "1992-03-31", "1993-12-31"),
    ("global_financial_crisis", "2005-12-31", "2007-03-31", "2008-12-31"),
]
DEV_END = pd.Timestamp("2008-12-31")
EXACT_COLUMNS = set(["CERT", "DECISION_DATE", "SOURCE_REPDTE", "SPLIT", "Y_4Q"] + FEATURES)


def check(value, reason):
    if not bool(value):
        raise AssertionError(reason)


def sha256(path: Path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def make_outputs(dev: pd.DataFrame, src: Path, audit: Path, out: Path) -> dict:
    a = json.loads(audit.read_text(encoding='utf-8'))
    check(a['stage']=='PART4_V2_DEV_LABEL_AND_INPUT_PIT_AUDIT' and a['status']=='PASS',
          'V2 audit JSON not valid PASS')
    for sub in ['full_pit_source_parity','independent_formula_oracle','asof_future_poison']:
        check(a[sub]['status']=='PASS', f'Missing PASS for {sub}')
    check(set(dev.columns) == EXACT_COLUMNS,
          f'Unexpected/missing feature columns: {set(dev.columns)^EXACT_COLUMNS}')
    check(dev['SPLIT'].eq('development').all(), 'Non-development rows present')
    check(dev['DECISION_DATE'].notna().all() and dev['SOURCE_REPDTE'].notna().all(),
          'Missing chronology dates')
    check(dev['DECISION_DATE'].dt.is_quarter_end.all() and dev['SOURCE_REPDTE'].dt.is_quarter_end.all(),
          'Dates not calendar quarter ends')
    check(dev['DECISION_DATE'].max() <= DEV_END, 'Decisions extend past development cutoff')
    qdelta = (dev['DECISION_DATE'].dt.to_period('Q').astype('int64') -
              dev['SOURCE_REPDTE'].dt.to_period('Q').astype('int64'))
    check(qdelta.eq(1).all(), 'Financial source quarter not exactly one before decision')
    check(not dev.duplicated(['CERT','DECISION_DATE']).any(), 'Duplicate decision keys')
    check(dev['Y_4Q'].isin([0, 1]).all() and dev['Y_4Q'].notna().all(), 'Invalid labels')
    for f in FEATURES:
        arr = pd.to_numeric(dev[f], errors='coerce').to_numpy(dtype=float)
        check(not np.isinf(arr).any(), f'Infinite predictor {f}')
        check(int(np.isnan(arr).sum()) == int(dev[f].isna().sum()),
              f'Non-numeric non-null feature {f}')
        dev[f] = arr
    for f in BINARY:
        check(dev[f].dropna().isin([0,1]).all(),f'Invalid binary flag {f}')
    c = a['counts']
    check(len(dev) == c['primary_labelled_rows'], 'V2 row count mismatch')
    check(int(dev['Y_4Q'].sum()) == c['primary_positive_rows'], 'Positive count mismatch')
    check(len(dev)-int(dev['Y_4Q'].sum()) == c['primary_negative_rows'], 'Negative count mismatch')
    print(f'V2 cohort verified: rows={len(dev):,} positive={int(dev.Y_4Q.sum()):,} negative={len(dev)-int(dev.Y_4Q.sum()):,}', flush=True)

    fold_rows = []
    feature_rows = []
    for name, tr_end_str, va_start_str, va_end_str in FOLDS:
        tr_end, va_start, va_end = map(pd.Timestamp, [tr_end_str,va_start_str,va_end_str])
        gap = va_start.to_period('Q').ordinal - tr_end.to_period('Q').ordinal - 1
        check(gap == 4 and va_end <= DEV_END, f'Invalid embargo window {name}')
        train = dev.loc[dev['DECISION_DATE'] <= tr_end]
        valid = dev.loc[dev['DECISION_DATE'].between(va_start,va_end)]
        check(len(train)>0 and len(valid)>0, f'Empty training/validation {name}')
        trpos = int(train['Y_4Q'].sum()); vapos = int(valid['Y_4Q'].sum())
        check(trpos>0 and vapos>0, f'No failure positives for {name}')
        for clip in [False, True]:
            prep = make_preprocessor(clip=clip,lower=.01,upper=.99)
            Xtr = prep.fit_transform(train[FEATURES]); Xval = prep.transform(valid[FEATURES])
            check(Xtr.shape == (len(train),30), f'{name}/{clip}: train feature width incorrect')
            check(Xval.shape == (len(valid),30), f'{name}/{clip}: valid feature width incorrect')
            check(np.isfinite(Xtr).all() and np.isfinite(Xval).all(),
                  f'{name}/{clip}: transformed arrays contain NaN or infinity')
            cont = prep.named_transformers_['continuous']
            med = cont.named_steps['training_median'].statistics_
            robust = cont.named_steps['training_robust_scale']
            cl = cont.named_steps.get('training_quantile_clip')
            check(len(med)==12 and len(robust.scale_)==12, 'Unexpected number of continuous columns')
            check((np.asarray(robust.scale_)>0).all(), 'Non-positive scale')
            for j,f in enumerate(CONTINUOUS):
                feature_rows.append({
                    'fold':name,'clip':clip,'feature':f,
                    'training_median_post_clip':float(med[j]),
                    'train_robust_center':float(robust.center_[j]),
                    'train_robust_scale':float(robust.scale_[j]),
                    'train_clip_lower':float(cl.lower_[j]) if cl else None,
                    'train_clip_upper':float(cl.upper_[j]) if cl else None,
                    'train_missing_count':int(train[f].isna().sum()),
                    'validation_missing_count':int(valid[f].isna().sum()),
                })
            fold_rows.append({
                'fold':name,'train_through':tr_end_str,'embargo_quarters':gap,
                'validation_from':va_start_str,'validation_to':va_end_str,
                'clipping_fit_on_train':clip,'train_rows':len(train),
                'validation_rows':len(valid),'train_positive_rows':trpos,
                'validation_positive_rows':vapos,
                'train_positive_certs':train.loc[train.Y_4Q.eq(1),'CERT'].nunique(),
                'validation_positive_certs':valid.loc[valid.Y_4Q.eq(1),'CERT'].nunique(),
                'training_only_fit_rows':len(train),'transformed_width':30,
            })
            del Xtr, Xval, prep, cont, robust, cl
        print(f'FOLD PASS {name}: train {len(train):,} / valid {len(valid):,}, train positive {trpos:,} / valid positive {vapos:,}', flush=True)

    pd.DataFrame(fold_rows).to_csv(out/'v2_temporal_folds.csv', index=False)
    pd.DataFrame(feature_rows).to_csv(out/'v2_preprocessing_params.csv', index=False)
    result={
        'stage':'PART4_V2_REAUDIT_TRAIN_ONLY_PREPROCESSING',
        'status':'PASS',
        'scope':'DEVELOPMENT_ONLY; FINAL_TEST_NOT_READ',
        'development_rows':len(dev),'positive_rows':int(dev.Y_4Q.sum()),
        'positive_certs':int(dev.loc[dev.Y_4Q.eq(1),'CERT'].nunique()),
        'folds_checked':3,'preprocessor_variants_checked':2,
        'fold_preprocessing_runs':len(fold_rows),'transformed_width':30,
        'train_only_preprocessing':True,'estimator_fitted':False,'threshold_selected':False,
        'input_sha256':{'development_primary_binary_v2_parquet':sha256(src),
                        'part4_v2_development_audit_json':sha256(audit),
                        'this_script':sha256(Path(__file__)),
                        'preprocessor_factory':sha256(Path(__file__).parent/'part4_v2_train_only_pipeline.py')},
        'limits':['No labelled test features or labels opened','No model tuning or final-test evaluation',
                  'Feature-level formula and event-date checks are evidenced in upstream V2, not rerun here'],
        'python':platform.python_version(), 'pandas':pd.__version__, 'sklearn':sklearn.__version__,
    }
    (out/'v2_train_only_audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    with zipfile.ZipFile(out/'SHARE_THIS_PART4_V2_FOLD_AUDIT.zip','w',zipfile.ZIP_DEFLATED) as z:
        for n in ('v2_train_only_audit.json','v2_temporal_folds.csv','v2_preprocessing_params.csv'):
            z.write(out/n,n)
    return result


def self_test():
    from part4_v2_train_only_pipeline import _self_test
    _self_test()
    # Minimal parsing of required fields and date boundary.
    q=pd.to_datetime(['1984-03-31','1984-06-30'])
    check((q.to_period('Q').astype('int64')[1] - q.to_period('Q').astype('int64')[0]) == 1,
          'Quarter calculation failed')
    print('INDEPENDENT SCRIPT SELF-TEST PASS')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dev',type=Path,help='V2 primary development Parquet')
    p.add_argument('--v2-audit',type=Path,help='V2 development audit JSON')
    p.add_argument('--out',type=Path,help='Output directory')
    p.add_argument('--self-test',action='store_true')
    args=p.parse_args()
    if args.self_test:
        self_test(); return
    check(all(v is not None for v in (args.dev,args.v2_audit,args.out)), 'Required --dev --v2-audit --out')
    check(args.dev.is_file() and args.v2_audit.is_file(),'Missing V2 development data or audit')
    check(args.dev.name == 'development_primary_binary_v2.parquet',
          'Only V2 development-primary Parquet allowed; refusing potential final test file')
    args.out.mkdir(parents=True,exist_ok=True)
    d = pd.read_parquet(args.dev,engine='pyarrow')
    for f in ['DECISION_DATE','SOURCE_REPDTE']:
        d[f]=pd.to_datetime(d[f],errors='raise')
    make_outputs(d,args.dev,args.v2_audit,args.out)
    print('PASS. Send:',args.out/'SHARE_THIS_PART4_V2_FOLD_AUDIT.zip',flush=True)

if __name__=='__main__':
    main()
