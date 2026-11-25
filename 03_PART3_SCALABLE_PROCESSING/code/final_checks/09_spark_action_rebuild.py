#!/usr/bin/env python3
"""Local Spark ACTION-only benchmark with fresh query per trial and AQE plan checks.

Retains Step 04 SQL configuration (local[4], 8 shuffle partitions, 3g driver).
Query building and plan inspection are excluded from timer; collect() is timed.
Before/after executed plans are saved for each task, including AQE isFinalPlan
where exposed. Spark is NOT a remote cluster. Repeated actions in one JVM may
still benefit from OS cache, JIT and shuffle exchange reuse; interpret with care.

Run: python 09_spark_action_rebuild.py --data-dir DATA_DIR --reference part3_step01_polars_evidence.zip --step04 code/revised/04_spark_parity_fixed.py --out results/spark09
"""
from __future__ import annotations
import argparse,csv,importlib.util,json,random,statistics,time
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--data-dir',type=Path,required=True)
    p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--step04',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--warmups',type=int,default=2)
    p.add_argument('--repeats',type=int,default=7)
    p.add_argument('--cores',type=int,default=4)
    p.add_argument('--shuffle-partitions',type=int,default=8)
    p.add_argument('--driver-memory',default='3g')
    p.add_argument('--seed',type=int,default=20261113)
    a=p.parse_args()
    if a.warmups<1 or a.repeats<3:raise ValueError('Insufficient trials')
    src=a.step04.resolve()
    sp=importlib.util.spec_from_file_location('step04_audit',src)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
    data=a.data_dir.resolve()
    _,reference=m.check_inputs_and_reference(data,a.reference.resolve())
    from pyspark.sql import SparkSession
    spark=(SparkSession.builder.master(f'local[{a.cores}]')
         .appName('BFT65B_Spark_ActionOnly_RebuiltPerTrial')
         .config('spark.sql.adaptive.enabled','true')
         .config('spark.sql.shuffle.partitions',str(a.shuffle_partitions))
         .config('spark.driver.memory',a.driver_memory).getOrCreate())
    spark.sparkContext.setLogLevel('ERROR')
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    get=['spark.sql.adaptive.enabled','spark.sql.shuffle.partitions',
         'spark.sql.autoBroadcastJoinThreshold','spark.sql.files.maxPartitionBytes',
         'spark.sql.exchange.reuse']
    config={key:spark.conf.get(key,None) for key in get}
    sc_conf=dict(spark.sparkContext.getConf().getAll())
    audit={'status':'UNKNOWN','environment':{'spark_version':spark.version,
        'java_version':spark.sparkContext._jvm.java.lang.System.getProperty('java.version'),
        'app_id':spark.sparkContext.applicationId,'master':spark.sparkContext.master,
        'default_parallelism':spark.sparkContext.defaultParallelism,
        'driver_memory_requested':a.driver_memory,
        'driver_memory_effective':sc_conf.get('spark.driver.memory','NOT_REPORTED'),
        'sql':config}}
    results=[];final_status={}
    try:
        rng=random.Random(a.seed)
        for i in range(a.warmups+a.repeats):
            tasks=list(m.TASKS);rng.shuffle(tasks)
            for task in tasks:
                # Important: fresh DataFrame and fresh QueryExecution for EACH trial.
                plan=m.build_query(task,spark,data)
                before=plan._jdf.queryExecution().executedPlan().toString()
                (out/f'plan_before_{task}_r{i:02d}.txt').write_text(before,encoding='utf-8')
                t=time.perf_counter();rows=plan.collect();elapsed=time.perf_counter()-t
                m.verify_rows(task,[r.asDict(recursive=True) for r in rows],reference['rows'][task])
                after=plan._jdf.queryExecution().executedPlan().toString()
                (out/f'plan_after_{task}_r{i:02d}.txt').write_text(after,encoding='utf-8')
                final_status.setdefault(task,[]).append('isFinalPlan=true' in after)
                results.append({'round':i,'task':task,'warmup':i<a.warmups,
                    'seconds_collect_only':elapsed,'summary_rows':len(rows),
                    'aqe_final_plan_after_collect':'isFinalPlan=true' in after,
                    'before_contains_exchange':'Exchange' in before,
                    'after_contains_exchange':'Exchange' in after})
                print('Spark round',i,task,f'{elapsed:.3f}s',flush=True)
        with (out/'spark_action_trials.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
        medians={task:statistics.median(r['seconds_collect_only'] for r in results if r['task']==task and not r['warmup'])
                 for task in m.TASKS}
        audit.update({'status':'EXECUTED_LOCAL_ACTION_ONLY','medians_seconds':medians,
            'aqe_final_plan_observed':{task:any(flags) for task,flags in final_status.items()},
            'warmups':a.warmups,'repeats':a.repeats,'rebuilds_query_each_trial':True,
            'limitations':['Spark runs local only; no distributed cluster comparison',
                'Query build and plan materialization excluded from stopwatch',
                'OS file caching, JVM JIT and exchange-stage reuse may still affect timings',
                'Check Spark UI/event logs for skipped stages before attributing speedups']})
        (out/'spark_action_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
        print(json.dumps(audit,indent=2))
    finally:
        spark.stop()
if __name__=='__main__':main()
