"""Execute one source-pinned upstream/development producer, isolated and offline."""
from pathlib import Path
import argparse,os,runpy,sys,tempfile,traceback
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workflow.common import ROOT,Blocked,read_json,save_json,sha,utc,verify_source_manifest,inputs_for,load_config
from workflow.continuous_contract import SOURCES,assert_arguments,artifact
from workflow.policy import Guard

def main():
    p=argparse.ArgumentParser();p.add_argument('--spec',type=Path,required=True);a=p.parse_args();s=read_json(a.spec)
    run=Path(s['run']).resolve();stage=s['stage'];job=run/stage
    if stage not in SOURCES or not job.is_dir() or run.is_relative_to(ROOT):raise ValueError('Invalid continuous job')
    inputs={k:Path(v) for k,v in s['inputs'].items()};args=s['arguments']
    assert_arguments(stage,args,run,inputs,s['start']);verify_source_manifest()
    scratch=job/'scratch';scratch.mkdir(exist_ok=False)
    for k in ['TMP','TEMP','TMPDIR','MPLCONFIGDIR','POLARS_TEMP_DIR']:os.environ[k]=str(scratch)
    os.environ.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1',POLARS_MAX_THREADS='2',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2')
    tempfile.tempdir=str(scratch);os.chdir(job)
    source=ROOT/SOURCES[stage];sys.path.insert(0,str(source.parent));sys.argv=[str(source),*args]
    started=utc();status='FAIL';error=None
    try:
        Guard(job).install()
        if stage=='exits':
            from workflow.offline_part2b import run as run_exits
            code=run_exits(args,artifact(run,stage))
            if code not in [None,0]:raise ValueError('Native Part2B nonzero result '+str(code))
        else:
            runpy.run_path(str(source),run_name='__main__')
        status='PASS_PRODUCER_EXECUTION_COMPARISON_REQUIRED'
    except SystemExit as e:
        if e.code in [None,0]:status='PASS_PRODUCER_EXECUTION_COMPARISON_REQUIRED'
        else:error='Native SystemExit '+str(e.code)
    except Exception as e:
        error=type(e).__name__+': '+str(e)
        status='BLOCKED' if isinstance(e,(FileNotFoundError,ModuleNotFoundError,Blocked)) or 'Offline test cache missing' in str(e) else 'FAIL'
        (job/'ERROR_TRACEBACK.txt').write_text(traceback.format_exc(),encoding='utf-8')
    save_json(job/'WORKER_RESULT.json',dict(stage=stage,status=status,error=error,started_utc=started,finished_utc=utc(),
        source=str(source),source_sha256=sha(source),recorded_producer_arguments=args,offline=stage in {'exits','clean'},
        new_model_fits=0,final_test_inference=False,guard='Python audit hooks, not native-library OS sandbox'))
    return 0 if status.startswith('PASS') else 2 if status=='BLOCKED' else 1
if __name__=='__main__':sys.exit(main())
