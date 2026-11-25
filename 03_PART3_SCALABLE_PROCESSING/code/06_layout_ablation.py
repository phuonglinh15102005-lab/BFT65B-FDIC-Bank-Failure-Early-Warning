#!/usr/bin/env python3
"""Part 3 controlled physical-layout ablation. Requires Polars + PyArrow.

Creates a NEW date-sorted Parquet; NEVER overwrites panel_clean.parquet.
Checks identical row counts, column order/dtypes and order-independent hash sums,
then measures identical crisis filter+groupby workloads on original versus sorted.

python code/revised/06_layout_ablation.py --clean data/panel_clean.parquet \
  --output-dir outputs/layout_ablation --warmups 3 --repeats 15

The newly produced output is NOT a replacement for the verified Part 2 snapshot;
re-run all downstream snapshot checks before changing the production pipeline.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,statistics,time
from pathlib import Path
from datetime import date

START=date(2008,3,31);END=date(2014,12,31)

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def meta(path):
    import pyarrow.parquet as pq
    pf=pq.ParquetFile(path);i=pf.schema_arrow.names.index('REPDTE')
    rows=[]
    for idx in range(pf.metadata.num_row_groups):
        g=pf.metadata.row_group(idx);s=g.column(i).statistics
        over=not (s.max<START or s.min>END) if s is not None and s.has_min_max else None
        rows.append(dict(rowgroup=idx,rows=g.num_rows,min=str(s.min) if s else '',
                         max=str(s.max) if s else '',overlaps=over))
    return rows

def fingerprint(frame):
    import polars as pl
    out={"rows":frame.height,"schema":list(map(lambda x:(x,str(frame.schema[x])),frame.columns)),
         "nulls":frame.null_count().row(0)}
    for seed in [0,42]:
        out[f'hash_sum_seed_{seed}']=str(frame.hash_rows(seed=seed).sum())
    return out

def query(pl,path):
    return (pl.scan_parquet(path)
       .filter(pl.col('REPDTE').is_between(START,END))
       .group_by('REPDTE').agg(pl.len().alias('n'),pl.col('ASSET').mean().alias('mean_asset'))
       .sort('REPDTE'))

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--clean',required=True,type=Path)
    p.add_argument('--output-dir',required=True,type=Path)
    p.add_argument('--warmups',type=int,default=3)
    p.add_argument('--repeats',type=int,default=15)
    p.add_argument('--row-group-size',type=int,default=100000)
    a=p.parse_args()
    import polars as pl
    if a.repeats<3 or a.warmups<1:raise ValueError('Need at least three trials and one warmup')
    src=a.clean.resolve();out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    target=out/'panel_clean_by_date.parquet'
    if src==target:raise ValueError('Refuse to overwrite original')
    if target.exists():raise FileExistsError('Choose a new output directory: '+str(target))
    source_hash=sha(src)
    original=pl.read_parquet(src)
    pre=fingerprint(original)
    # Sorted table is deliberately isolated; keep original schema and all rows.
    original.sort(['REPDTE','CERT']).write_parquet(target,compression='zstd',
                                    row_group_size=a.row_group_size,statistics=True)
    del original
    after=pl.read_parquet(target)
    post=fingerprint(after)
    if pre!=post:raise AssertionError('Rearrangement changed row content or schema')
    del after
    data=[];compare={}
    for label,path in [('cert_sorted_original',src),('date_sorted_alternative',target)]:
        plan=query(pl,path)
        reference=plan.collect()
        compare[label]=reference
        for k in range(a.warmups+a.repeats):
            t0=time.perf_counter();frame=plan.collect();duration=time.perf_counter()-t0
            if not frame.equals(reference):raise AssertionError('Query result shifted during timing')
            data.append(dict(layout=label,trial=k,warmup=k<a.warmups,seconds=duration))
    if not compare['cert_sorted_original'].equals(compare['date_sorted_alternative']):
        raise AssertionError('Layout changes queried results')
    import pandas as pd
    pd.DataFrame(data).to_csv(out/'layout_trials.csv',index=False)
    rg=[]
    for label,path in [('cert_sorted_original',src),('date_sorted_alternative',target)]:
        for row in meta(path):rg.append({'layout':label,**row})
    pd.DataFrame(rg).to_csv(out/'layout_rowgroups.csv',index=False)
    times={label:statistics.median(d['seconds'] for d in data if not d['warmup'] and d['layout']==label)
           for label in compare}
    summary={'status':'MEASURED_ON_LOCAL_MACHINE','source_sha256':source_hash,
       'new_sha256':sha(target),'content_fingerprint':pre,'parquet_rowgroups':{
        label:{'total':sum(r['layout']==label for r in rg),
               'overlap':sum(r['layout']==label and r['overlaps'] is True for r in rg),
               'prunable':sum(r['layout']==label and r['overlaps'] is False for r in rg)}
        for label in compare}, 'median_seconds':times,
       'limitations':'Warm OS cache; sequential layout schedule; no paired randomization; only one query.'}
    (out/'layout_audit.json').write_text(json.dumps(summary,indent=2,default=str),encoding='utf-8')
    print(json.dumps(summary,indent=2,default=str))
    if sha(src)!=source_hash:raise AssertionError('Original source changed during study')

if __name__=='__main__':main()
