#!/usr/bin/env python3
"""Repeated local Spark ACTION-only benchmark with recorded effective SQL config.

Unlike old diagnostic Step 04, this excludes build_query() and explain() from
per-iteration timed sections. The first query is NOT an unbiased cold-cache run.
The Spark JVM is reused across iterations, so cache/GC behavior still matters.

python code/revised/09_spark_action_benchmark.py --data-dir data \
 --reference evidence/part3_step01_polars_evidence.zip --out results/spark09

Full execution is not certified until a Java/Spark-equipped environment runs it.
"""
import argparse,csv,importlib.util,json,statistics,time
from pathlib import Path

def main():
    pa=argparse.ArgumentParser()
    pa.add_argument('--data-dir',type=Path,required=True)
    pa.add_argument('--reference',type=Path,required=True)
    pa.add_argument('--out',type=Path,required=True)
    pa.add_argument('--warmups',type=int,default=3)
    pa.add_argument('--repeats',type=int,default=10)
    pa.add_argument('--cores',type=int,default=4)
    a=pa.parse_args()
    if a.repeats<3 or a.warmups<1:raise ValueError('Insufficient trials')
    src=Path(__file__).with_name('04_spark_parity_fixed.py')
    spec=importlib.util.spec_from_file_location('step04_fixed',src)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    data=a.data_dir.resolve();_,reference=m.check_inputs_and_reference(data,a.reference.resolve())
    from pyspark.sql import SparkSession
    spark=(SparkSession.builder.master(f'local[{a.cores}]')
           .appName('BFT65B_Spark_ActionOnly_Benchmark')
           .config('spark.sql.adaptive.enabled','true')
           .config('spark.sql.shuffle.partitions',str(a.cores))
           .getOrCreate())
    spark.sparkContext.setLogLevel('ERROR')
    config={key:spark.conf.get(key,None) for key in (
        'spark.sql.adaptive.enabled','spark.sql.shuffle.partitions',
        'spark.sql.autoBroadcastJoinThreshold','spark.sql.files.maxPartitionBytes',
        'spark.sql.execution.arrow.pyspark.enabled')}
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    rows=[]
    try:
        for task in m.TASKS:
            plan=m.build_query(task,spark,data)
            # Plans are captured outside the timed loop.
            (out/f'plan_{task}.txt').write_text(plan._jdf.queryExecution().executedPlan().toString(),encoding='utf-8')
            for i in range(a.warmups+a.repeats):
                t=time.perf_counter();result=plan.collect();duration=time.perf_counter()-t
                m.verify_rows(task,[r.asDict(recursive=True) for r in result],reference["rows"][task])
                rows.append({'task':task,'trial':i,'warmup':i<a.warmups,
                             'seconds':duration,'summary_rows':len(result)})
        with (out/'spark_action_trials.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        medians={task:statistics.median(r['seconds'] for r in rows if r['task']==task and not r['warmup'])
                 for task in m.TASKS}
        report={'status':'EXECUTED_ACTION_ONLY','environment':{'spark_version':spark.version,
                    'app_id':spark.sparkContext.applicationId,'master':spark.sparkContext.master,
                    'default_parallelism':spark.sparkContext.defaultParallelism,'effective_sql':config},
                'medians_seconds':medians,'limitations':['Spark is local, not a cluster',
                   'Session and JVM reused','Timings are not interleaved with Python engines',
                   'Plan creation and explain excluded from measured collect()']}
        (out/'spark_action_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))
    finally:
        spark.stop()

if __name__=='__main__':main()
