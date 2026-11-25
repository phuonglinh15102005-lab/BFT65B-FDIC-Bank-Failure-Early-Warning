"""One-click controller. No install/discovery sweep; exact known development path."""
from pathlib import Path
from datetime import datetime
import importlib.metadata as metadata,json,os,shutil,subprocess,sys,uuid,zipfile,traceback

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent

def main():
    base=Path(os.environ.get('LOCALAPPDATA',os.environ.get('TEMP',str(Path.home()))))/'BFT65B_ABLATION_20261118'
    base.mkdir(parents=True,exist_ok=True)
    claim=base/'THREE_FITS_EXECUTION_CLAIM.json'
    if claim.is_file():
        previous=json.loads(claim.read_text(encoding='utf-8'))
        print('NO NEW TRAINING: a previous execution claim exists. Send the previous output for review.')
        print(previous)
        folder=Path(previous['out']).parent
        if os.name=='nt':subprocess.Popen(['explorer.exe',str(folder)])
        return
    result=base/(datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]);result.mkdir(exist_ok=False)
    status={'status':'BLOCKED','HGB_training_authorized':3,'final_test_permitted':False}
    packages={}
    for distribution in metadata.distributions():
        name=distribution.metadata.get('Name')
        if name:packages[name]=distribution.version
    (result/'LAUNCHER_ENVIRONMENT.json').write_text(json.dumps(dict(python=sys.version,executable=sys.executable,packages=packages),indent=2),encoding='utf-8')
    try:
        profile=Path(os.environ.get('USERPROFILE',str(Path.home())))
        args=[sys.executable,'-B',str(HERE/'ablation_runner.py'),'--profile',str(profile),'--out',str(result/'ABLATION_RUN'),'--claim-file',str(claim)]
        (result/'LAUNCHER_COMMAND.json').write_text(json.dumps(args,indent=2),encoding='utf-8')
        config=json.loads((HERE/'CONFIG.json').read_text())
        (result/'LAUNCHER_EXPECTED_INPUTS.json').write_text(json.dumps(dict(development_profile_relative_path=config['development_profile_relative_path'],expected_development_sha256=config['development_sha256'],runtime_hashes=json.loads((HERE/'RUNTIME_HASHES.json').read_text())),indent=2),encoding='utf-8')
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1'}
        print('Exactly three development HGB fits. No final test. Do not close this window. Logs are written under:',result,flush=True)
        with (result/'STDOUT.txt').open('w',encoding='utf-8') as stdout,(result/'STDERR.txt').open('w',encoding='utf-8') as stderr:
            child=subprocess.Popen(args,env=env,stdout=subprocess.PIPE,stderr=stderr,text=True,encoding='utf-8',bufsize=1)
            for line in child.stdout:
                print(line,end='',flush=True);stdout.write(line);stdout.flush()
            child.wait()
        record=result/'ABLATION_RUN/RUN_RECORD.json'
        if record.is_file():status=json.loads(record.read_text())
        else:status={'status':'BLOCKED' if 'ModuleNotFoundError' in (result/'STDERR.txt').read_text() else 'FAIL','detail':'Child did not produce RUN_RECORD; inspect stderr','command':args,'exit_code':child.returncode}
        # Supply exact executed source and development-only reference bytes for independent review.
        shutil.copytree(HERE,result/'EXECUTED_ABLATION_CODE',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        # Do NOT read/copy root closeout reports here: they may contain saved TEST metrics.
        # The execution/return bundle contains only this development runtime and its outputs.
        for name in ['ABLATION_RESULTS.md','ABLATION_FOLD_METRICS.csv']:
            if (result/'ABLATION_RUN'/name).is_file():shutil.copy2(result/'ABLATION_RUN'/name,result/name)
    except Exception as error:
        status={'status':'FAIL','detail':str(error),'traceback':traceback.format_exc()}
    (result/'WINDOWS_STATUS.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
    # Per-run code/evidence manifest; intentionally no raw data or fitted model.
    import hashlib,csv
    files=[]
    for p in sorted(result.rglob('*')):
        if p.is_file():files.append(dict(path=p.relative_to(result).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    with (result/'FINAL_CODE_AND_EVIDENCE_MANIFEST.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['path','bytes','sha256']);writer.writeheader();writer.writerows(files)
    zpath=result.with_name(result.name+'_GUI_LAI_CHO_CODEX.zip')
    with zipfile.ZipFile(zpath,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for p in result.rglob('*'):
            if p.is_file():archive.write(p,p.relative_to(result).as_posix())
    print('STATUS:',status.get('status'));print('SEND THIS ZIP:',zpath,flush=True)
    if os.name=='nt':subprocess.Popen(['explorer.exe','/select,'+str(zpath)])

if __name__=='__main__':main()
