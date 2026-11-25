#!/usr/bin/env python3
"""Blocked randomized repeated benchmark of unchanged Part 3 workload definitions.

Strict snapshot comparison only. Uses original Step01, Step02 and Step05 source
functions, except source-file validation and per-trial parity run OUTSIDE timings.
Each trial is a clean subprocess (imports are NOT timed) and all 9 combinations
are randomized within each round; Python processes may have different allocator
states and the OS page cache remains warm/uncontrolled.

Example:
 python code/revised/07_interleaved_benchmark.py --data-dir data \
   --scripts code/original --reference evidence/part3_step01_polars_evidence.zip \
   --out results/step07 --warmups 3 --repeats 15

Requires original audited scripts 01_polars_core.py, 02_pandas_parity.py and
05_fair_baseline_sensitivity.py. Python 3.13 / pandas / Polars / PyArrow / psutil.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,os,random,statistics,subprocess,sys,time
from pathlib import Path
TASKS=('crisis_profile','calendar_lag','decision_profile')
ENGINES=('polars','pandas_original','pandas_optimized')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir',type=Path,default=Path('data'))
    parser.add_argument('--scripts',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--out',type=Path,default=Path('results/step07'))
    parser.add_argument('--warmups',type=int,default=3)
    parser.add_argument('--repeats',type=int,default=15)
    parser.add_argument('--threads',type=int,default=4)
    parser.add_argument('--seed',type=int,default=20261112)
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--task',choices=TASKS,help=argparse.SUPPRESS)
    parser.add_argument('--engine',choices=ENGINES,help=argparse.SUPPRESS)
    parser.add_argument('--json',type=Path,help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.warmups<1 or args.repeats<3:raise ValueError('Need >=1 warmup and >=3 repeats')
    if args.worker: return worker(args)
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    script=Path(__file__).resolve()
    runpath=args.scripts.resolve();datapath=args.data_dir.resolve();ref=args.reference.resolve()
    from importlib.util import spec_from_file_location,module_from_spec
    required=['01_polars_core.py','02_pandas_parity.py','05_fair_baseline_sensitivity.py']
    absent=[str(runpath/name) for name in required if not (runpath/name).is_file()]
    if absent:
        raise FileNotFoundError('Required archived producer not supplied locally: '+', '.join(absent)+
                                '. Set --scripts to the directory containing the recovered original sources.')
    sp=spec_from_file_location('legacy_sensitivity',runpath/'05_fair_baseline_sensitivity.py')
    old=module_from_spec(sp);sp.loader.exec_module(old)
    # This mode deliberately refuses mixing old evidence with new data.
    old.check_sources(datapath)
    old.read_reference(ref)
    order=[];rng=random.Random(args.seed)
    for i in range(args.warmups+args.repeats):
        jobs=[(task,engine) for task in TASKS for engine in ENGINES]
        rng.shuffle(jobs)
        order.extend((i,k,task,engine) for k,(task,engine) in enumerate(jobs))
    with (out/'randomized_schedule.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['round','within_round','task','engine']);w.writerows(order)
    records=[]
    for round_id,k,task,engine in order:
        report=out/f'worker_r{round_id:02d}_{k:02d}.json'
        cmd=[sys.executable,str(script),'--worker','--data-dir',str(datapath),
             '--scripts',str(runpath),'--reference',str(ref),'--task',task,
             '--engine',engine,'--threads',str(args.threads),'--json',str(report)]
        proc=subprocess.run(cmd,capture_output=True,text=True,timeout=180,check=False,
            env={**os.environ,'POLARS_MAX_THREADS':str(args.threads),
                 'OMP_NUM_THREADS':str(args.threads)})
        if proc.returncode!=0:raise RuntimeError(f'Worker {task}/{engine} failed: {proc.stderr[-1000:]}')
        record=json.loads(report.read_text())
        if not record.get('parity_passed'):raise AssertionError('Reference mismatch: '+str(report))
        records.append({'round':round_id,'within_round':k,'warmup':round_id<args.warmups,
                        'task':task,'engine':engine,'seconds':record['seconds'],
                        'parity_max':record['parity_max']})
        report.unlink()
        print(round_id,task,engine,f"{record['seconds']:.4f}s",flush=True)
    with (out/'interleaved_trials.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    measured=[r for r in records if not r['warmup']]
    summary=[]
    for task in TASKS:
        for engine in ENGINES:
            t=[r['seconds'] for r in measured if r['task']==task and r['engine']==engine]
            summary.append({'task':task,'engine':engine,'n':len(t),'median_seconds':statistics.median(t),
                            'first5_median':statistics.median(t[:5]),
                            'last5_median':statistics.median(t[-5:]),
                            'drift_last_over_first':statistics.median(t[-5:])/statistics.median(t[:5])})
    with (out/'interleaved_summary.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
    audit={'status':'PASS','warmups':args.warmups,'measured_rounds':args.repeats,
           'schedule':'random order of 9 engine/task combinations inside each round',
           'parity':'outside timed block on each run; original Step 01 reference and fixed source hashes',
           'caveats':['OS caches remain warm','Individual process startup is not included in timing',
                      'Separate subprocesses may cause system-level interference','No cold-cache randomization'],
           'outputs':['interleaved_trials.csv','interleaved_summary.csv','randomized_schedule.csv']}
    (out/'interleaved_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    print('PASS: measured trials and parity checks saved under',out)

def worker(a):
    import importlib.util
    import pandas as pd,polars as pl
    sp=importlib.util.spec_from_file_location('old_step05',a.scripts.resolve()/'05_fair_baseline_sensitivity.py')
    b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
    sp1=importlib.util.spec_from_file_location('original_polars',a.scripts.resolve()/'01_polars_core.py')
    s1=importlib.util.module_from_spec(sp1);sp1.loader.exec_module(s1)
    sp2=importlib.util.spec_from_file_location('original_pandas',a.scripts.resolve()/'02_pandas_parity.py')
    s2=importlib.util.module_from_spec(sp2);sp2.loader.exec_module(s2)
    # Imports, reference read and verification excluded from timing.
    ref=b.read_reference(a.reference.resolve())
    engine=a.engine;lib=pl if engine=='polars' else pd
    src={'query_crisis':s1.query_crisis,'query_calendar':s1.query_calendar,
         'query_decision':s1.query_decision,'run_crisis':s2.run_crisis,
         'run_calendar':s2.run_calendar,'run_decision':s2.run_decision}
    t0=time.perf_counter()
    result=b.run_task(engine,a.task,a.data_dir.resolve(),src,lib)
    duration=time.perf_counter()-t0
    diff=b.compare(a.task,engine,result,ref)
    a.json.write_text(json.dumps({'seconds':duration,'parity_passed':True,'parity_max':diff}),encoding='utf-8')

if __name__=='__main__':main()
