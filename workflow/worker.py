"""Run exactly one source-hash-pinned data-only producer in a private job directory."""
from pathlib import Path
import argparse,json,os,runpy,sys,tempfile,traceback
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workflow.common import ROOT,Blocked,read_json,save_json,sha,utc,verify_source_manifest
from workflow.policy import ALLOWED,permitted_stage,validate_arguments,Guard

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=sorted(ALLOWED),required=True)
    parser.add_argument('--job',type=Path,required=True)
    parser.add_argument('--arguments-file',type=Path,required=True)
    args=parser.parse_args();out=args.job.resolve()
    if not out.is_dir() or out.is_relative_to(ROOT):parser.error('Parent must create isolated job outside code')
    start=utc();source=ROOT/permitted_stage(args.stage);arguments=read_json(args.arguments_file)
    validate_arguments(args.stage,arguments,out);verify_source_manifest()
    scratch=out/'scratch';scratch.mkdir(exist_ok=False)
    for key in ['TMP','TEMP','TMPDIR','MPLCONFIGDIR','POLARS_TEMP_DIR']:os.environ[key]=str(scratch)
    tempfile.tempdir=str(scratch);os.chdir(out)
    os.environ.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1',POLARS_MAX_THREADS='2',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2')
    sys.path.insert(0,str(source.parent));sys.argv=[str(source),*arguments]
    status='FAIL';error=None
    try:
        Guard(out).install()
        runpy.run_path(str(source),run_name='__main__')
        status='PASS_PRODUCER_EXECUTION_COMPARISON_REQUIRED'
    except SystemExit as exc:
        if exc.code in {None,0}:status='PASS_PRODUCER_EXECUTION_COMPARISON_REQUIRED'
        else:error='Producer exited with '+str(exc.code)
    except Exception as exc:
        error=type(exc).__name__+': '+str(exc)
        status='BLOCKED' if isinstance(exc,(FileNotFoundError,ModuleNotFoundError)) or 'Offline test cache missing' in str(exc) else 'FAIL'
        (out/'ERROR_TRACEBACK.txt').write_text(traceback.format_exc(),encoding='utf-8')
    finally:
        save_json(out/'WORKER_RESULT.json',dict(status=status,error=error,stage=args.stage,started_utc=start,finished_utc=utc(),source_sha256=sha(source),
                 command=[sys.executable,'-B',str(source),*arguments],guard='Python write/network/frozen-model guard,not an OS/native-Arrow sandbox',
                 closed_checks_reexecuted=False,new_model_fits=0,final_test_inference=False))
    return 0 if status.startswith('PASS') else 2 if status=='BLOCKED' else 1

if __name__=='__main__':sys.exit(main())
