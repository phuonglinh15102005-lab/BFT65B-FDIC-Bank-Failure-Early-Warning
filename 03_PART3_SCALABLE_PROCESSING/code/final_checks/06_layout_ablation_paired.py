#!/usr/bin/env python3
"""Physical-layout paired benchmark; creates a new date-sorted file without changing panel_clean.

Requires polars>=2.1, pyarrow and pandas. Reports exact-date Parquet row-group
pruning and paired timings under blocked randomized AB/BA order. The query is a
single CRISIS aggregation and does not stand in for all Part 3 workloads.

Run: python 06_layout_ablation_paired.py --clean panel_clean.parquet --out results/layout06
"""
from __future__ import annotations
import argparse, hashlib, json, random, statistics, time, csv, math
from pathlib import Path
from datetime import date

START, END = date(2008,3,31), date(2014,12,31)

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def parquet_info(path):
    import pyarrow.parquet as pq
    pf=pq.ParquetFile(path)
    idx=pf.schema_arrow.names.index('REPDTE')
    info=[]
    codecs=set()
    for j in range(pf.metadata.num_row_groups):
        g=pf.metadata.row_group(j)
        for k in range(g.num_columns):codecs.add(str(g.column(k).compression).lower())
        stats=g.column(idx).statistics
        minv, maxv=(stats.min,stats.max) if stats and stats.has_min_max else (None,None)
        prune=bool(minv is not None and (maxv<START or minv>END))
        info.append(dict(group=j,rows=g.num_rows,min=str(minv),max=str(maxv),prunable=prune))
    return {'codecs':sorted(codecs),'groups':info,'rows':pf.metadata.num_rows}

def fingerprint(f):
    return {'rows':f.height,'schema':[(name,str(f.schema[name])) for name in f.columns],
            'nulls':f.null_count().row(0),
            'hash0':int(f.hash_rows(seed=0).sum()),'hash42':int(f.hash_rows(seed=42).sum())}

def query(pl,path):
    return (pl.scan_parquet(path).filter(pl.col('REPDTE').is_between(START,END))
      .group_by('REPDTE').agg(pl.len().alias('n'),pl.col('ASSET').mean().alias('mean_asset'))
      .sort('REPDTE'))

def main():
    a=argparse.ArgumentParser()
    a.add_argument('--clean',type=Path,required=True)
    a.add_argument('--out',type=Path,required=True)
    a.add_argument('--warmups',type=int,default=3)
    a.add_argument('--repeats',type=int,default=12)
    a.add_argument('--row-group-size',type=int,default=100000)
    a.add_argument('--seed',type=int,default=20261113)
    v=a.parse_args()
    if v.warmups<1 or v.repeats<6:raise ValueError('Use >=1 warmup and >=6 paired repetitions')
    import polars as pl
    original=v.clean.resolve();out=v.out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    target=out/'panel_clean_by_date.parquet'
    if original==target or target.exists():raise RuntimeError('Never overwrite a source or prior layout alternative')
    before=parquet_info(original)
    # Match compression codec to avoid confounding row-order effects with format changes.
    if len(before['codecs'])!=1 or before['codecs'][0] not in {'zstd','snappy','uncompressed'}:
        raise RuntimeError(f'Nonhomogeneous or unsupported input Parquet codecs: {before["codecs"]}')
    codec={'zstd':'zstd','snappy':'snappy','uncompressed':'uncompressed'}[before['codecs'][0]]
    original_hash=sha(original)
    src=pl.read_parquet(original)
    fp_before=fingerprint(src)
    src.sort(['REPDTE','CERT']).write_parquet(target,compression=codec,
        row_group_size=v.row_group_size,statistics=True)
    del src
    alt=pl.read_parquet(target)
    if fingerprint(alt)!=fp_before:raise AssertionError('Sorted copy differs in logical contents')
    del alt
    after=parquet_info(target)
    if before['codecs']!=after['codecs']:raise AssertionError('Parquet codecs differ across layouts')
    plans={'original':query(pl,original),'date_sorted':query(pl,target)}
    ref={label:lf.collect() for label,lf in plans.items()}
    # Floating-point means can differ in their last few bits after physical row order changes.
    # Require exact dates/counts and numerically equivalent means, not bitwise equality.
    reference_records = ref['original'].to_dicts()
    alternative_records = ref['date_sorted'].to_dicts()
    if len(reference_records) != len(alternative_records):
        raise AssertionError('Different summary-row counts across physical layouts')
    maximum_mean_difference = 0.0
    for left, right in zip(reference_records, alternative_records):
        if left['REPDTE'] != right['REPDTE'] or left['n'] != right['n']:
            raise AssertionError('Different crisis dates or row counts')
        x, y = left['mean_asset'], right['mean_asset']
        if x is None or y is None:
            if x is not None or y is not None:
                raise AssertionError('Missing mean differs across layouts')
        else:
            maximum_mean_difference = max(maximum_mean_difference, abs(x-y))
            if not math.isclose(x, y, rel_tol=1e-10, abs_tol=1e-6):
                raise AssertionError('Different crisis mean beyond numerical tolerance')
    records=[];rng=random.Random(v.seed)
    for i in range(v.warmups+v.repeats):
        order=['original','date_sorted'];rng.shuffle(order)
        for position,label in enumerate(order):
            t0=time.perf_counter();actual=plans[label].collect();elapsed=time.perf_counter()-t0
            if len(actual) != len(ref[label]):
                raise AssertionError('In-run summary-row count mismatch')
            for left, right in zip(actual.to_dicts(), ref[label].to_dicts()):
                if left['REPDTE'] != right['REPDTE'] or left['n'] != right['n']:
                    raise AssertionError('In-run group key/count mismatch')
                x, y = left['mean_asset'], right['mean_asset']
                if x is None or y is None:
                    if x is not None or y is not None:raise AssertionError('In-run missing-value mismatch')
                elif not math.isclose(x, y, rel_tol=1e-10, abs_tol=1e-6):
                    raise AssertionError('In-run mean beyond tolerance')
            records.append(dict(round=i,position=position,label=label,warmup=i<v.warmups,seconds=elapsed))
        print('completed paired round',i+1,flush=True)
    with (out/'layout_trials.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    paired=[]
    for i in range(v.warmups,v.warmups+v.repeats):
        m={row['label']:row['seconds'] for row in records if row['round']==i}
        paired.append(m['original']/m['date_sorted'])
    assert len(paired)==v.repeats
    measured={name:[r['seconds'] for r in records if not r['warmup'] and r['label']==name] for name in plans}
    output={'status':'MEASURED_NO_CLUSTER','input_sha256':original_hash,
            'alternate_sha256':sha(target),'content_fingerprint':fp_before,'codec':codec,
            'row_groups':{label:{'total':len(m['groups']),
             'prunable':sum(x['prunable'] for x in m['groups'])}
             for label,m in [('original',before),('date_sorted',after)]},
            'median_seconds':{label:statistics.median(a) for label,a in measured.items()},
            'paired_speedup_median':statistics.median(paired),
            'max_mean_asset_abs_diff_between_layouts':maximum_mean_difference,
            'warmups':v.warmups,'paired_repetitions':v.repeats,
            'limitations':['Warm OS cache','Same laptop only','Codec matched, row-group size may change',
              'Paired timing randomizes order but cannot remove systemic OS effects']}
    (out/'layout_audit.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    rg=[]
    for label,meta in [('original',before),('date_sorted',after)]:
        rg.extend({'layout':label,**r} for r in meta['groups'])
    with (out/'layout_rowgroups.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rg[0]));w.writeheader();w.writerows(rg)
    if sha(original)!=original_hash:raise AssertionError('Original Parquet changed during run')
    print(json.dumps(output,indent=2))
if __name__=='__main__':main()
