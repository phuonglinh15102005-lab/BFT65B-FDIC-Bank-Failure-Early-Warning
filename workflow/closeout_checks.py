"""Record real release-QA commands; never trains/scores or installs packages."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,importlib.metadata as md,json,os,platform,subprocess,sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workflow.common import ROOT,sha,read_json,save_json,verify_source_manifest

def main():
    parser=argparse.ArgumentParser();parser.add_argument('case',choices=['unit-normal','unit-no-site','unit-preloaded','plan','validate','source-audit','continuous-help','continuous-cloud'])
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    inputs={str(ROOT/n):h for n,h in verify_source_manifest().items()};inputs[str(ROOT/'config/source_manifest.json')]=sha(ROOT/'config/source_manifest.json')
    before={p:sha(Path(p)) for p in inputs};env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1'}
    cmd=[sys.executable,'-B'];expected2=False;expected_outputs=[]
    if args.case in ['unit-normal','unit-no-site']:cmd=[sys.executable,*(['-S'] if args.case=='unit-no-site' else []),'-B','-m','unittest','discover','-s','tests','-v']
    elif args.case=='unit-preloaded':
        fixture=out/'HOST_FIXTURE';fixture.mkdir()
        source=fixture/'sitecustomize.py';source.write_text('import numpy\nimport pandas\n',encoding='utf-8');before[str(source)]=sha(source)
        env['PYTHONPATH']=str(fixture)+(os.pathsep+env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
        program="import sys,unittest; assert 'numpy' in sys.modules and 'pandas' in sys.modules; print('HOST_PRELOADED numpy,pandas',flush=True); suite=unittest.defaultTestLoader.discover('tests'); r=unittest.TextTestRunner(verbosity=2).run(suite); sys.exit(0 if r.wasSuccessful() else 1)"
        cmd += ['-c',program]
    elif args.case=='plan':cmd += ['run.py','plan']
    elif args.case=='continuous-help':cmd += ['run.py','continuous','--help']
    elif args.case=='validate':
        cmd+=['run.py','validate','--out',str(out/'validation')];expected_outputs=[out/'validation/VALIDATION_RESULT.json']
    elif args.case=='source-audit':
        cmd+=['workflow/release_audit.py','--out',str(out/'source_audit')];expected_outputs=[out/'source_audit/FINAL_SOURCE_RESOURCE_AUDIT.json']
    else:
        cmd+=['run.py','continuous','--start','raw','--profile','/workspace/NO_WINDOWS_DATA','--out',str(out/'continuous')]
        expected2=True;expected_outputs=[out/'continuous/CONTINUOUS_RESULT.json',out/'continuous/PREFLIGHT.json',out/'continuous/STAGE_STATUS.csv']
    packages={}
    for name in ['numpy','pandas','polars','pyarrow','scikit-learn','joblib','pyspark']:
        try:packages[name]=md.version(name)
        except md.PackageNotFoundError:packages[name]=None
    started=datetime.now(timezone.utc).isoformat()
    with (out/'STDOUT.txt').open('w',encoding='utf-8') as stdout,(out/'STDERR.txt').open('w',encoding='utf-8') as stderr:
        p=subprocess.run(cmd,cwd=ROOT,env=env,stdout=stdout,stderr=stderr)
    status='PASS' if p.returncode==0 else 'BLOCKED' if p.returncode==2 and expected2 else 'FAIL'
    if args.case=='continuous-cloud' and p.returncode==2:
        v=read_json(out/'continuous/CONTINUOUS_RESULT.json')
        if v['continuous_data_replay']!='NOT_EXECUTED' or any(s['status']!='NOT_EXECUTED' for s in v['stages'].values()):status='FAIL'
    after={name:sha(Path(name)) for name in before}
    if before!=after:status='FAIL'
    outputs={p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file() and p.suffix in {'.txt','.json','.csv','.py'}}
    result=dict(case=args.case,status=status,exit_code=p.returncode,command=cmd,working_directory=str(ROOT),started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),
        environment=dict(python=platform.python_version(),executable=sys.executable,platform=platform.platform(),packages=packages,extra_pythonpath=env.get('PYTHONPATH') if args.case=='unit-preloaded' else None),
        input_sha256_before=before,input_sha256_after=after,output_sha256=outputs,new_model_fits=0,final_test_inference=False,
        scope='Actual source/unit/CLI/preflight invocation only. BLOCKED does not count as real-data reproduction PASS.')
    save_json(out/'EXECUTION_RECORD.json',result);print(json.dumps(dict(case=args.case,status=status,exit_code=p.returncode),indent=2))
    return 1 if status=='FAIL' else 0
if __name__=='__main__':sys.exit(main())
