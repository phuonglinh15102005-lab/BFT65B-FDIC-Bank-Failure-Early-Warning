from pathlib import Path
import argparse,os,sys,tempfile,traceback
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workflow.common import Blocked,read_json,save_json,sha,utc
from workflow.compare import compare_parquet
from workflow.policy import Guard

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--spec',type=Path,required=True);args=parser.parse_args()
    spec=read_json(args.spec);out=Path(spec['out']).resolve();out.mkdir(exist_ok=False)
    scratch=out/'scratch';scratch.mkdir()
    for name in ['TMP','TEMP','TMPDIR','POLARS_TEMP_DIR']:os.environ[name]=str(scratch)
    tempfile.tempdir=str(scratch)
    os.environ['POLARS_MAX_THREADS']='2'
    status='FAIL';results=[];start=utc()
    try:
        Guard(out).install()
        for dataset in spec['datasets']:
            result=compare_parquet(Path(dataset['new']),Path(dataset['reference']),dataset['keys'],dataset['id'],out/(dataset['id']+'.json'),dataset['rtol'],dataset['atol'])
            results.append(result)
        status='PASS' if all(r['status'].startswith('PASS') for r in results) else 'FAIL'
    except Blocked as error:status='BLOCKED';save_json(out/'BLOCKER.json',dict(reason=str(error)))
    except Exception as error:save_json(out/'ERROR.json',dict(error=str(error),traceback=traceback.format_exc()))
    save_json(out/'COMPARISON_RESULT.json',dict(status=status,started_utc=start,finished_utc=utc(),command=[sys.executable,'-B',str(Path(__file__)),*sys.argv[1:]],spec_sha256=sha(args.spec),results=results))
    print(status,flush=True);return 0 if status=='PASS' else 2 if status=='BLOCKED' else 1

if __name__=='__main__':sys.exit(main())
