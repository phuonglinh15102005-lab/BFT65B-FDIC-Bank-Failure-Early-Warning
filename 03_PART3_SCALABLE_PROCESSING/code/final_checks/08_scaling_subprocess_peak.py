#!/usr/bin/env python3
"""Synthetic bank-quarter scaling: paired workloads, isolated processes, peak RSS sampler.

Runs crisis_profile and exact calendar_lag at 1x/5x/10x (optional 25x),
with CERT-offset replicas on disk. Each engine/factor/task trial executes in a
NEW subprocess; an external parent sampler records PEAK process-tree RSS and
kills a hung or memory-exceeding run. Processes are serial, tasks are shuffled
within each repetition. This is local synthetic scaling, not a Spark cluster test.

Example (Windows):
  py 08_scaling_subprocess_peak.py --clean C:\\path\\panel_clean.parquet --out results/scale08 --factors 1 5 10
Output: scale_trials.csv, scale_summary.csv, scale_audit.json.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, os, random, statistics, subprocess, sys, time, shutil
from pathlib import Path
from datetime import date
import psutil

TASKS=('crisis_profile','calendar_lag')
ENGINES=('polars','pandas')
START,END=date(2008,3,31),date(2014,12,31)

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def write_csv(path,rows):
    if not rows:return
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def make_replicas(original,out,factors):
    import polars as pl
    info=pl.scan_parquet(original).select(pl.col('CERT').min().alias('mn'),
        pl.col('CERT').max().alias('mx'),pl.len().alias('n')).collect().row(0)
    mn,mx,n=info
    if mn is None or mx is None:raise ValueError('Empty CERT bounds')
    stride=int(mx-mn+1)
    replicas=[original]
    for i in range(1,max(factors)):
        target=out/f'replica_{i:02d}.parquet'
        if target.exists():raise FileExistsError('Refuse to trust existing replica: '+str(target))
        (pl.scan_parquet(original).with_columns((pl.col('CERT')+i*stride).alias('CERT'))
         .sink_parquet(target,compression='zstd'))
        replicas.append(target)
        print('Prepared replica',i+1,'/',max(factors),flush=True)
    return replicas,n,stride

def compute(task,engine,paths,threads):
    import pyarrow as pa
    import pyarrow.parquet as pq  # all pyarrow imports before clock
    pa.set_cpu_count(threads)
    if hasattr(pa,'set_io_thread_count'):pa.set_io_thread_count(threads)
    if engine=='polars':
        import polars as pl
        t=time.perf_counter()
        lf=pl.scan_parquet(paths).select('CERT','REPDTE','ASSET')
        if task=='crisis_profile':
            query=(lf.filter(pl.col('REPDTE').is_between(START,END))
                .group_by('REPDTE').agg(pl.len().alias('n'),pl.col('ASSET').mean().alias('mean_asset')))
        else:
            prev=(lf.select('CERT',pl.col('REPDTE').dt.offset_by('3mo').dt.month_end().alias('REPDTE'),
                       pl.lit(1).alias('prior_present')))
            query=(lf.join(prev,on=['CERT','REPDTE'],how='left',validate='1:1')
                .group_by('REPDTE').agg(pl.len().alias('n'),pl.col('prior_present').is_not_null().sum().alias('matched')))
        res=query.collect().sort('REPDTE');seconds=time.perf_counter()-t
        result=res.to_dicts()
    else:
        import pandas as pd
        t=time.perf_counter()
        df=pd.concat([pd.read_parquet(p,columns=['CERT','REPDTE','ASSET']) for p in paths],ignore_index=True)
        if task=='crisis_profile':
            mask=(df.REPDTE>=pd.Timestamp(START))&(df.REPDTE<=pd.Timestamp(END))
            r=(df.loc[mask].groupby('REPDTE',as_index=False).agg(n=('ASSET','size'),mean_asset=('ASSET','mean')))
        else:
            qid=pd.to_datetime(df.REPDTE).dt.to_period('Q').astype('int64')
            df['QID']=qid
            prev=df[['CERT','QID']].rename(columns={'QID':'PREV_QID'}).copy()
            prev['prior_present']=1
            df['PREV_QID']=qid-1
            merged=df.merge(prev,on=['CERT','PREV_QID'],how='left',sort=False,validate='1:1')
            r=merged.groupby('REPDTE',as_index=False).agg(n=('CERT','size'),matched=('prior_present','count'))
        seconds=time.perf_counter()-t
        result=r.sort_values('REPDTE').to_dict('records')
    # Compact output parity contract: original mean is preserved by replicating identical values;
    # n/matched are multiplied by factor.
    canonical=[]
    for row in result:
        date_s=str(row['REPDTE'])[:10]
        if task=='crisis_profile': canonical.append((date_s,int(row['n']),float(row['mean_asset'])))
        else:canonical.append((date_s,int(row['n']),int(row['matched'])))
    return seconds,canonical

def run_worker(a):
    paths=[str(x) for x in json.loads(a.paths_json)]
    seconds,result=compute(a.task,a.engine,paths,a.threads)
    Path(a.worker_json).write_text(json.dumps({'seconds':seconds,'result':result}),encoding='utf-8')

def subprocess_peak(cmd,env,timeout_s,cap_mib):
    proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
    root=psutil.Process(proc.pid)
    peak=0;start=time.monotonic();reason=None
    while proc.poll() is None:
        try:
            procs=[root]+root.children(recursive=True)
            total=sum(p.memory_info().rss for p in procs if p.is_running())
            peak=max(peak,total)
            if peak>cap_mib*1048576:reason='MEMORY_CAP';proc.kill();break
        except (psutil.NoSuchProcess,psutil.AccessDenied):pass
        if time.monotonic()-start>timeout_s:reason='TIMEOUT';proc.kill();break
        time.sleep(.05)
    try:stdout,stderr=proc.communicate(timeout=15)
    except subprocess.TimeoutExpired:proc.kill();stdout,stderr=proc.communicate()
    if reason:return reason,peak/1048576,stderr[-600:]
    if proc.returncode!=0:return 'PROCESS_FAILED',peak/1048576,stderr[-600:]
    return 'OK',peak/1048576,''

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--clean',type=Path)
    p.add_argument('--out',type=Path)
    p.add_argument('--factors',nargs='+',type=int,default=[1,5,10])
    p.add_argument('--warmups',type=int,default=1)
    p.add_argument('--repeats',type=int,default=5)
    p.add_argument('--threads',type=int,default=4)
    p.add_argument('--seed',type=int,default=20261113)
    p.add_argument('--timeout-sec',type=int,default=240)
    p.add_argument('--memory-cap-mib',type=int,default=0)
    p.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    p.add_argument('--paths-json',help=argparse.SUPPRESS)
    p.add_argument('--worker-json',help=argparse.SUPPRESS)
    p.add_argument('--task',choices=TASKS,help=argparse.SUPPRESS)
    p.add_argument('--engine',choices=ENGINES,help=argparse.SUPPRESS)
    a=p.parse_args()
    if a.worker:return run_worker(a)
    if not a.clean or not a.out: p.error('--clean and --out are required')
    factors=sorted(set(a.factors))
    if not factors or factors[0]!=1 or factors[-1]>25 or a.repeats<3 or a.warmups<1:
        p.error('Include 1x; use max 25x, >=3 measured trials and >=1 warmup')
    original=a.clean.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    if original.is_relative_to(out):raise ValueError('Do not place original input inside output')
    cap=a.memory_cap_mib or int(min(psutil.virtual_memory().available*.60/1048576,8192))
    if cap<384:raise RuntimeError('Insufficient memory for controlled experiment')
    original_hash=digest(original)
    needed=int(original.stat().st_size*max(0,max(factors)-1)*1.25)
    if shutil.disk_usage(out).free < needed:
        raise RuntimeError(f'Insufficient disk for synthetic replicas; need about {needed/2**30:.1f} GiB')
    replicas,n,stride=make_replicas(original,out,factors)
    records=[];references={};rng=random.Random(a.seed)
    env={**os.environ,'POLARS_MAX_THREADS':str(a.threads),
         'OMP_NUM_THREADS':str(a.threads),'ARROW_NUM_THREADS':str(a.threads)}
    for factor in factors:
        for round_id in range(a.warmups+a.repeats):
            jobs=[(task,engine) for task in TASKS for engine in ENGINES]
            rng.shuffle(jobs)
            for task,engine in jobs:
                dest=out/f'_worker_{factor}_{round_id}_{task}_{engine}.json'
                cmd=[sys.executable,str(Path(__file__).resolve()),'--worker',
                    '--paths-json',json.dumps([str(x) for x in replicas[:factor]]),
                    '--task',task,'--engine',engine,'--threads',str(a.threads),
                    '--worker-json',str(dest)]
                status,rss,error=subprocess_peak(cmd,env,a.timeout_sec,cap)
                seconds=None
                if status=='OK' and dest.exists():
                    worker=json.loads(dest.read_text());seconds=worker['seconds']
                    result=worker['result']
                    key=task
                    if key not in references and factor==1:references[key]=result
                    elif key in references:
                        expected=references[key]
                        if len(result)!=len(expected):raise AssertionError('Different quarterly output dimensions')
                        for now,base in zip(result,expected):
                            if now[0]!=base[0] or now[1]!=base[1]*factor:
                                raise AssertionError('Wrong date/count under synthetic replication')
                            if task=='calendar_lag' and now[2]!=base[2]*factor:
                                raise AssertionError('Calendar match count failed scaling parity')
                            if task=='crisis_profile' and abs(now[2]-base[2])>1e-7*max(1,abs(base[2])):
                                raise AssertionError('Mean asset failed synthetic parity')
                    dest.unlink()
                records.append(dict(factor=factor,task=task,engine=engine,round=round_id,
                        warmup=round_id<a.warmups,rows=n*factor,seconds=seconds,
                        sampled_peak_rss_mib=round(rss,2),status=status,error=error))
                print(f'{factor}x {task} {engine}: {status} {seconds}',flush=True)
            # End factor if any failed -> avoid repeating a hung run.
            if any(r['factor']==factor and r['round']==round_id and r['status']!='OK' for r in records):
                print('Stopping repetitions for factor',factor,'due to resource failure');break
    write_csv(out/'scale_trials.csv',records)
    summary=[]
    for factor in factors:
        for task in TASKS:
            for engine in ENGINES:
                good=[r for r in records if r['factor']==factor and r['task']==task and r['engine']==engine
                       and not r['warmup'] and r['status']=='OK']
                summary.append(dict(factor=factor,task=task,engine=engine,n=len(good),
                    median_seconds=statistics.median([r['seconds'] for r in good]) if good else '',
                    median_sampled_peak_rss_mib=statistics.median([r['sampled_peak_rss_mib'] for r in good]) if good else '',
                    max_sampled_peak_rss_mib=max([r['sampled_peak_rss_mib'] for r in good],default=''),
                    incomplete=len(good)<a.repeats))
    write_csv(out/'scale_summary.csv',summary)
    audit={'status':'EXECUTED_WITH_REPORTED_FAILURES' if any(r['status']!='OK' for r in records) else 'MEASURED',
        'input_sha256':original_hash,'base_rows':n,'cert_offset_stride':stride,
        'factors':factors,'engines':ENGINES,'tasks':TASKS,'memory_limit_mib':cap,
        'timeout_seconds':a.timeout_sec,'sample_interval_sec':.05,
        'threads':a.threads,'warmups':a.warmups,'repeats':a.repeats,
        'important_limits':['Synthetic copies preserve financial values, not realistic bank diversity',
          'Observed process-tree RSS at 50ms cadence; may miss instantaneous peaks',
          'Resource cap/timeout may terminate a paging run before OS failure',
          'Local process scaling does NOT establish a remote cluster crossover']}
    (out/'scale_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    if digest(original)!=original_hash:raise AssertionError('Source Parquet changed')
    print(json.dumps(audit,indent=2))
if __name__=='__main__':main()
