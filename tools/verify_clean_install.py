#!/usr/bin/env python3
"""User-invoked clean environment installation. No changes to existing environments, no data or test access."""
import argparse, json, platform, subprocess, sys, venv
from pathlib import Path
R=Path(__file__).resolve().parents[1]
P={'engineering':('3.13.9','engineering-recorded.txt',['numpy','pandas','polars','pyarrow','psutil','pyspark','matplotlib','requests','yaml']), 'model':('3.13.7','model-and-spark-observed.txt',['numpy','pandas','polars','pyarrow','sklearn','joblib','scipy','threadpoolctl','pyspark'])}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',choices=P,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();version,req,modules=P[a.profile]
    if platform.python_version()!=version:p.error('Expected Python '+version+'; found '+platform.python_version())
    if out.exists() or out.is_relative_to(R):p.error('Choose new external output directory')
    out.mkdir(parents=True); status={'status':'FAIL','profile':a.profile,'python':platform.python_version(),'recipe':req,'steps':[],'scope':'clean install and synthetic imports, not scientific pipeline'}
    def run(name,cmd):
        with (out/(name+'.log')).open('wb') as log:rc=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT).returncode
        status['steps'].append({'name':name,'exit_code':rc});return rc
    try:
        env=out/'venv';venv.EnvBuilder(with_pip=True,system_site_packages=False).create(env);py=env/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
        if run('install',[str(py),'-m','pip','install','-r',str(R/'requirements'/req)]):raise RuntimeError('Install failed')
        if run('freeze',[str(py),'-m','pip','freeze']):raise RuntimeError('Freeze failed')
        if run('pip_check',[str(py),'-m','pip','check']):raise RuntimeError('Dependency check failed')
        if run('imports',[str(py),'-c','import importlib; '+ '; '.join('importlib.import_module('+repr(x)+')' for x in modules)]):raise RuntimeError('Imports failed')
        status['status']='PASS_CLEAN_INSTALL_IMPORTS_ONLY'
    except Exception as e:status['error']=str(e)
    finally:
        (out/'STATUS.json').write_text(json.dumps(status,indent=2));print(json.dumps(status,indent=2))
    return 0 if status['status'].startswith('PASS') else 1
if __name__=='__main__':sys.exit(main())
