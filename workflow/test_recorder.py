"""Run one new safe release check and retain exact code inputs and output hashes."""
from pathlib import Path
import argparse,hashlib,importlib.metadata as metadata,json,os,platform,subprocess,sys
from datetime import datetime,timezone
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('id');args=parser.parse_args()
    case=next(c for c in json.loads((ROOT/'config/release_tests.json').read_text()) if c['id']==args.id)
    log=ROOT/'release_evidence'/args.id;log.mkdir(exist_ok=False)
    input_hashes={}
    snapshots=log/'INPUT_SNAPSHOTS';snapshots.mkdir()
    for name in case['inputs']:
        path=ROOT/name;input_hashes[name]=sha(path)
        (snapshots/(input_hashes[name]+'.txt')).write_bytes(path.read_bytes())
    command=[sys.executable if x=='{python}' else x.replace('{root}',str(ROOT)) for x in case['command']]
    environment={'python':platform.python_version(),'executable':sys.executable,'packages':{}}
    for name in ['numpy','pandas','polars','pyarrow','scikit-learn','pyspark','joblib','scipy']:
        try:environment['packages'][name]=metadata.version(name)
        except metadata.PackageNotFoundError:environment['packages'][name]=None
    started=datetime.now(timezone.utc).isoformat()
    with (log/'STDOUT.txt').open('w',encoding='utf-8') as stdout,(log/'STDERR.txt').open('w',encoding='utf-8') as stderr:
        child=subprocess.run(command,cwd=ROOT,stdout=stdout,stderr=stderr,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1'})
    status='PASS' if child.returncode==0 else 'BLOCKED' if child.returncode==2 and case.get('exit2_is_blocked') else 'FAIL'
    outputs={p.name:sha(p) for p in log.iterdir() if p.is_file()}
    for name in case.get('outputs',[]):
        p=Path(name.replace('{root}',str(ROOT)));outputs[str(p)]=sha(p) if p.is_file() else None
    before=input_hashes;after={name:sha(ROOT/name) for name in before}
    if before!=after:status='FAIL'
    record=dict(id=args.id,status=status,exit_code=child.returncode,command=command,started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),environment=environment,input_sha256_before=before,input_sha256_after=after,output_sha256=outputs,scope=case['scope'],new_model_fits=0)
    (log/'EXECUTION_RECORD.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(dict(id=args.id,status=status,exit_code=child.returncode),indent=2));return 1 if status=='FAIL' else 0

if __name__=='__main__':sys.exit(main())
