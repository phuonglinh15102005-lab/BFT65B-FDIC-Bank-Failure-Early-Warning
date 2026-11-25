#!/usr/bin/env python3
"""Synthetic multi-copy scaling, NOT a measured result until this script is run.

Replicates clean bank-quarter data with non-overlapping synthetic certificate IDs.
Keeps temporal histories intact for each synthetic bank. Measures the SAME crisis
aggregation across 1, 5, 10 and optionally 25 copies. Does not infer that
synthetic replicas replicate the skew, concurrency or I/O conditions of real growth.

python code/revised/08_synthetic_scaling.py --clean data/panel_clean.parquet \
 --out results/scale --factors 1 5 10 --warmups 2 --repeats 5

Requires Polars and pyarrow. Pandas comparison is attempted only where memory
allows. Optional Spark local benchmarks are separate and are NOT assumed here.
"""
import argparse,csv,json,statistics,time,hashlib
from pathlib import Path
import psutil

def read_backend(engine,paths):
    if engine=='polars':
        import polars as pl
        return pl.scan_parquet([str(x) for x in paths])
    import pandas as pd
    return pd.concat([pd.read_parquet(p,columns=['REPDTE','ASSET','EQ','CERT']) for p in paths],ignore_index=True)

def run(engine,paths):
    if engine=='polars':
        import polars as pl
        return (read_backend(engine,paths)
          .filter(pl.col('REPDTE').is_between(__import__('datetime').date(2008,3,31),
                                               __import__('datetime').date(2014,12,31)))
          .group_by('REPDTE').agg(pl.len().alias('rows'),pl.col('ASSET').mean().alias('mean_asset'))
          .sort('REPDTE').collect())
    import pandas as pd
    df=read_backend(engine,paths)
    stamp=pd.to_datetime(df.REPDTE)
    df=df.loc[(stamp>=pd.Timestamp(2008,3,31))&(stamp<=pd.Timestamp(2014,12,31)),['REPDTE','ASSET']]
    return df.groupby('REPDTE',as_index=False).agg(rows=('ASSET','size'),mean_asset=('ASSET','mean')).sort_values('REPDTE')

def fingerprint(frame,engine):
    d=frame.to_dicts() if engine=='polars' else frame.to_dict('records')
    return [(str(x['REPDTE'])[:10],int(x['rows']),float(x['mean_asset'])) for x in d]

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--clean',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--factors',type=int,nargs='+',default=[1,5,10])
    p.add_argument('--warmups',type=int,default=2)
    p.add_argument('--repeats',type=int,default=5)
    p.add_argument('--threads',type=int,default=4)
    a=p.parse_args()
    import polars as pl
    factors=sorted(set(a.factors))
    if factors[0]!=1 or any(x<1 or x>25 for x in factors):raise ValueError('Include 1, factors <=25')
    if a.repeats<3:raise ValueError('At least 3 measured runs')
    input=a.clean.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    if input.is_relative_to(out):raise ValueError('Output cannot contain input')
    meta=pl.scan_parquet(input).select(pl.col('CERT').max().alias('mx'),
                                     pl.col('CERT').min().alias('mn'),
                                     pl.len().alias('n')).collect().row(0)
    mx,mn,n=meta;stride=int(mx-mn+1)
    source_hash=hashlib.sha256(input.read_bytes()).hexdigest()
    files=[]
    # One replica per file prevents building a single 42m-row Python DataFrame
    # while preserving the same schema and all date/financial values.
    for i in range(max(factors)):
        target=out/f'synthetic_{i:03d}.parquet'
        if i==0:
            # Use original path for single-copy benchmark to avoid needless rewrite
            files.append(input)
            continue
        if not target.exists():
            (pl.scan_parquet(input)
             .with_columns((pl.col('CERT')+i*stride).alias('CERT'))
             .sink_parquet(target,compression='zstd'))
        files.append(target)
    trials=[];reference=None
    for factor in factors:
        paths=files[:factor]
        for engine in ('polars','pandas'):
            for i in range(a.warmups+a.repeats):
                process=psutil.Process();rss_before=process.memory_info().rss
                try:
                    t0=time.perf_counter();result=run(engine,paths);seconds=time.perf_counter()-t0
                    fp=fingerprint(result,engine)
                    if reference is None:
                        reference=fp
                    if len(fp)!=len(reference):raise AssertionError('Summary periods changed')
                    for current,base in zip(fp,reference):
                        assert current[0]==base[0] and current[1]==base[1]*factor
                        assert abs(current[2]-base[2])<=1e-8*max(1,abs(base[2]))
                    trials.append(dict(factor=factor,engine=engine,trial=i,
                                       warmup=i<a.warmups,rows=n*factor,seconds=seconds,
                                       rss_end_bytes=process.memory_info().rss,
                                       rss_start_bytes=rss_before,status='PASS'))
                except (MemoryError, OSError) as exc:
                    trials.append(dict(factor=factor,engine=engine,trial=i,
                                       warmup=i<a.warmups,rows=n*factor,
                                       seconds='',rss_start_bytes=rss_before,
                                       rss_end_bytes='',status=f'FAILED:{type(exc).__name__}:{exc}'))
                    break
        print('Finished factor',factor,flush=True)
    with (out/'scale_trials.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['factor','engine','trial','warmup','rows','seconds',
             'rss_start_bytes','rss_end_bytes','status']);w.writeheader();w.writerows(trials)
    audit={'status':'MEASURED_SCALING_WITH_LIMITATIONS','source_sha256':source_hash,
         'factors':factors,'bank_id_offset_stride':stride,'copies_created':max(factors)-1,
         'warning':'rss_end_bytes IS NOT peak RSS; use process-sampled peak for claims. Synthetic replication does not model data skew or real distributed shuffle.',
         'speedup_limitations':'Run schedule factor/engine ordered and OS cache warm; use randomized interleaving for stable inference.'}
    (out/'scale_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')

if __name__=='__main__':main()
