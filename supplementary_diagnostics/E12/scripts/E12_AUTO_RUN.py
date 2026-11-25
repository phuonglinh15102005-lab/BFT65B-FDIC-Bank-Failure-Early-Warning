#!/usr/bin/env python3
"""One-click Windows launcher. Hash-locked development data; no test path."""
from __future__ import annotations
import os,sys,hashlib,json,datetime,subprocess,zipfile,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent
DEV_NAME='development_primary_binary_v2.parquet'
DEV_SHA='d365ce25204a3dcace715db4cea259c94b1b1abba4822c7bcf2b050a1c7f6a73'

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):
            h.update(block)
    return h.hexdigest()

def locate():
    base=Path.home()/'BFT65B_outputs'
    direct=base/'part4_v2_dev_only_outputs'/DEV_NAME
    candidates=[direct]+(list(base.rglob(DEV_NAME)) if base.is_dir() else [])
    for file in dict.fromkeys(candidates):
        if file.is_file() and sha(file)==DEV_SHA:
            print('PASS exact development data SHA-256 (file:',file.name+')',flush=True)
            return file
    raise RuntimeError('No hash-matching development_primary_binary_v2.parquet found under ~/BFT65B_outputs. Do not substitute test files.')

def main():
    import pandas,pyarrow,sklearn
    hashes=json.loads((HERE/'SOURCE_HASHES.json').read_text(encoding='utf8'))
    for name,h in hashes['frozen_pipeline'].items():
        p=HERE/'frozen_pipeline'/name
        if sha(p)!=h:
            raise RuntimeError('Frozen source SHA-256 mismatch: '+name)
    print('PASS all four original frozen science source SHA-256 checks',flush=True)
    dev=locate()
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    root=Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'BFT65B_E12_DEV_ONLY'
    root.mkdir(parents=True,exist_ok=True)
    run=root/f'RUN_{stamp}_{os.getpid()}'
    run.mkdir()
    cmd=[sys.executable,str(HERE/'E12_AUDIT.py'),'--dev',str(dev),'--source',str(HERE/'frozen_pipeline'),'--out',str(run/'outputs')]
    log=run/'RUN_LOG.txt'
    with log.open('w',encoding='utf8') as f:
        f.write('E12 input and frozen source hashes verified. No test data loaded.\n')
        proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace')
        for line in proc.stdout:
            # Output E12 is deliberately free of full path or machine usernames.
            print(line,end='',flush=True)
            f.write(line)
        status=proc.wait()
    result={'status':'PASS' if status==0 else 'FAIL','private_dev_input_verified':True,
            'original_data_modified':False,'final_test_read_or_scored':False,
            'threshold_or_hyperparameters_changed':False,'python':sys.version.split()[0]}
    (run/'STATUS.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    downloads=Path.home()/'Downloads'
    if not downloads.is_dir():downloads=root
    output=downloads/f'BFT65B_E12_RESULTS_{result["status"]}_{stamp}.zip'
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(run.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(run))
    print('Saved output:',output,flush=True)
    print('Upload only this ZIP; no Parquet or score-level arrays included.',flush=True)
    return status

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as exc:
        print('E12 FAILED:',exc,flush=True)
        traceback.print_exc();sys.exit(2)
