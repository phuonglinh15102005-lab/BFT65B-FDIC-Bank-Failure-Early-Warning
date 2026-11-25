#!/usr/bin/env python3
"""Low-memory, read-only independent verification of 72 fold parameter rows.

Read the HASH-VERIFIED original development Parquet one column at a time using
PyArrow's ParquetFile.iter_batches; keep only metadata vectors and one feature
vector in RAM. Never load models or the held-out test set.

The archived parameter comparison is unchanged (rtol=1e-10, atol=1e-12).
This code is a verification helper, not a reimplementation of the training
pipeline for inference. A PASS is 504 parameter-statistic comparisons, not E2E.
"""
from __future__ import annotations
import gc
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from verify_fold_preprocessing_readonly import (
    CONTINUOUS, BINARY, FEATURES, OUTPUT_COLUMNS, KEYS, PARAM_FIELDS,
    FROZEN_COUNTS, require, _clip_bool, continuous_parameters, transform_numpy,
)

BATCH_SIZE = 32_768


def read_col(parquet, name, kind):
    """Process one column in bounded batches; null handling matches pandas."""
    chunks=[]
    for batch in parquet.iter_batches(batch_size=BATCH_SIZE, columns=[name], use_threads=False):
        part=batch.column(0).to_pandas()
        if kind=='date':
            val=pd.to_datetime(part,errors='raise').to_numpy(dtype='datetime64[ns]')
        elif kind=='int':
            val=pd.to_numeric(part,errors='raise').to_numpy(dtype=np.float64)
            require(np.isfinite(val).all(),name+' has invalid/null keys')
            require(np.equal(val,np.floor(val)).all(),name+' has non-integer values')
            val=val.astype(np.int64)
        elif kind=='binary':
            val=pd.to_numeric(part,errors='raise').to_numpy(dtype=np.float64)
            require(np.isin(val,[0.0,1.0]).all(),'Invalid binary '+name)
            val=val.astype(np.uint8)
        elif kind=='str':
            require(part.notna().all(),name+' contains null')
            require(part.astype(str).eq('development').all(),'Non-development split')
            continue
        elif kind=='float':
            val=pd.to_numeric(part,errors='raise').to_numpy(dtype=np.float64)
            require(not np.isinf(val).any(),name+' contains infinite values')
        else:
            raise ValueError('Unknown column kind')
        chunks.append(val)
    if kind=='str':return None
    return np.concatenate(chunks) if chunks else np.array([],dtype=np.float64)


def make_masks(parquet, protocol, frozen):
    fields=set(parquet.schema_arrow.names)
    require(set(KEYS+FEATURES).issubset(fields),'Frozen 20-column development schema differs (missing columns)')
    require(not (fields-set(KEYS+FEATURES)-{'__index_level_0__','index'}),'Unexpected Parquet source schema columns')
    cert=read_col(parquet,'CERT','int')
    y=read_col(parquet,'Y_4Q','binary')
    date=read_col(parquet,'DECISION_DATE','date')
    source=read_col(parquet,'SOURCE_REPDTE','date')
    read_col(parquet,'SPLIT','str')
    n=parquet.metadata.num_rows
    require(all(len(a)==n for a in [cert,y,date,source]),'Metadata length differs')
    require(not np.isnat(date).any() and not np.isnat(source).any(), 'Null decision/source date')
    require(pd.DatetimeIndex(date).is_quarter_end.all() and pd.DatetimeIndex(source).is_quarter_end.all(), 'Date not quarter-end')
    require(date.max()<=np.datetime64('2008-12-31'),'Development includes post-2008 decision')
    qdec=date.astype('datetime64[M]').astype(np.int64)//3
    qsrc=source.astype('datetime64[M]').astype(np.int64)//3
    require(np.all(qdec-qsrc==1),'Source is not exactly q-1')
    # Sort two compact int64 columns, not a million Python object tuples.
    dcode=date.astype('datetime64[D]').astype(np.int64)
    order=np.lexsort((dcode,cert))
    require(not np.any((cert[order][1:]==cert[order][:-1]) & (dcode[order][1:]==dcode[order][:-1])), 'Duplicate CERT/date keys')
    del order,dcode,source,qsrc
    if frozen:
        require(n==1_231_631 and int(y.sum())==9246 and np.unique(cert[y==1]).size==2410,'Frozen development counts differ')
    validation=protocol['validation']
    require(validation['embargo_calendar_quarters']==4,'Not 4-quarter embargo')
    folds=validation['folds']
    require({f['id'] for f in folds}==set(FROZEN_COUNTS),'Fold ids differ')
    masks={}
    for fold in folds:
        end=np.datetime64(fold['train_end'])
        start=np.datetime64(fold['validation_start'])
        finish=np.datetime64(fold['validation_end'])
        gap=int(start.astype('datetime64[M]').astype('int64')//3-end.astype('datetime64[M]').astype('int64')//3-1)
        require(gap==4 and finish<=np.datetime64('2008-12-31'),'Incorrect fold embargo/date bounds')
        train=date<=end; valid=(date>=start)&(date<=finish)
        require(train.any() and valid.any(),'Empty training/validation')
        require(int(qdec[valid].min()) - int(qdec[train].max())>=5,'Overlapping train-label horizon')
        actual=(int(train.sum()),int(valid.sum()),int(y[train].sum()),int(y[valid].sum()),
                int(np.unique(cert[train & (y==1)]).size),int(np.unique(cert[valid & (y==1)]).size))
        if frozen:require(actual==FROZEN_COUNTS[fold['id']], fold['id']+' fold counts differ: '+str(actual))
        masks[fold['id']]={'train':train,'valid':valid,'counts':actual,'gap':gap,'sample_indices':np.flatnonzero(valid)[:128]}
    return masks


def verify_fold_preprocessing_lowmem(dev_path, expected_csv, protocol, output_dir):
    parquet=pq.ParquetFile(str(dev_path))
    masks=make_masks(parquet,protocol,True)
    require(set(protocol['feature_policy']['tier1_features'])==set(FEATURES),'Feature protocol differs')
    expected=pd.read_csv(expected_csv)
    need={'fold','clip','feature'}|set(PARAM_FIELDS)
    require(need.issubset(expected.columns),'Missing parameter columns')
    expected['clip']=expected['clip'].map(_clip_bool)
    require(not expected.duplicated(['fold','clip','feature']).any(),'Duplicate archived parameter key')
    required={(f,clip,c) for f in masks for clip in [False,True] for c in CONTINUOUS}
    keys=set(expected[['fold','clip','feature']].itertuples(index=False,name=None))
    require(keys==required,'Expected parameter keys do not cover all 72 rows')
    expected=expected.set_index(['fold','clip','feature'])
    rows=[]; differences=[]; fold_rows=[]
    # Store only 128 validation rows (15 columns) per fold for an independent
    # transform-shape and finite-value check; this is not actual model scoring.
    sample={fold:np.full((len(m['sample_indices']),15),np.nan) for fold,m in masks.items()}
    frozen_params={fold:{False:[],True:[]} for fold in masks}
    for j,feature in enumerate(FEATURES):
        print('R23 column',j+1,'/',len(FEATURES),feature,flush=True)
        x=read_col(parquet,feature,'float')
        require(len(x)==parquet.metadata.num_rows,feature+' row count differs')
        if feature in BINARY:require(np.isin(x[np.isfinite(x)],[0.,1.]).all(),'Invalid binary feature '+feature)
        for fold,m in masks.items():
            sample[fold][:,j]=x[m['sample_indices']]
            if j>=len(CONTINUOUS):continue
            train=x[m['train']]; val=x[m['valid']]
            for clip in (False,True):
                p=continuous_parameters(train.reshape(-1,1),val.reshape(-1,1),clip)[0]
                frozen_params[fold][clip].append(p)
                row={'fold':fold,'clip':clip,'feature':feature,**p}
                valid_row=True
                for metric in PARAM_FIELDS:
                    ref=float(expected.loc[(fold,clip,feature),metric])
                    got=p[metric]
                    if metric.endswith('_count'):ok=(got==ref)
                    else:ok=bool(np.isclose(got,ref,rtol=1e-10,atol=1e-12,equal_nan=True))
                    if not ok:
                        valid_row=False
                        differences.append({'fold':fold,'clip':clip,'feature':feature,'statistic':metric,
                                           'observed':got,'archived':ref})
                row['status']='PASS' if valid_row else 'FAIL'
                rows.append(row)
            del train,val
        del x
        gc.collect()
    for fold,m in masks.items():
        raw=pd.DataFrame(sample[fold],columns=FEATURES)
        for clip in [False,True]:
            params=frozen_params[fold][clip]
            after=transform_numpy(raw,params,clip)
            require(after.shape==(len(raw),30) and np.isfinite(after).all(),'Invalid 30-column transformed validation sample')
            ntr,nva,npos,nvpos,ncert,nvcert=m['counts']
            fold_rows.append({'fold':fold,'clip':clip,'train_rows':ntr,'validation_rows':nva,
              'train_positive_rows':npos,'validation_positive_rows':nvpos,
              'train_positive_certs':ncert,'validation_positive_certs':nvcert,
              'embargo_quarters':m['gap'],'transformed_width':after.shape[1],
              'validation_transform_does_not_mutate_parameters':True})
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=False)
    for file,data in [('fold_preprocessing_recomputed.csv',rows),('fold_preprocessing_comparisons.csv',differences),
                      ('fold_preprocessing_temporal_counts.csv',fold_rows)]:
        with (output_dir/file).open('x',encoding='utf-8-sig',newline='') as h:
            pd.DataFrame(data).to_csv(h,index=False)
    report={'status':'FAIL' if differences else 'PASS', 'scope':'FROZEN_DEVELOPMENT_FOLD_PARAMETERS_READONLY_LOW_MEMORY',
      'rows_compared':len(rows),'statistics_compared':len(rows)*len(PARAM_FIELDS),
      'mismatches':len(differences),'transformed_columns_in_exact_order':OUTPUT_COLUMNS,
      'independent_feature_scans':len(FEATURES),'batch_size':BATCH_SIZE,
      'validation_transform_sample_rows_per_fold':{f:len(s) for f,s in sample.items()},
      'read_only':True,'training_or_inference_performed':False,
      'limitations':['Archived preprocessing parameter identity only; not a full sklearn estimator fit.',
                     'No final-test dataset or model artifact opened.',
                     'Historical filing/revision vintage not established.']}
    with (output_dir/'fold_preprocessing_summary.json').open('x',encoding='utf-8') as h:
        json.dump(report,h,indent=2,ensure_ascii=False,allow_nan=False)
    return report
