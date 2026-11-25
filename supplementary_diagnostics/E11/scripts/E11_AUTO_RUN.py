#!/usr/bin/env python3
"""One-click, exact-hash-pinned Windows launcher for E11. No test labels or scores."""
from __future__ import annotations
import os,sys,hashlib,json,datetime,subprocess,zipfile,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent
EXPECTED={
'dev':('development_primary_binary_v2.parquet','d365ce25204a3dcace715db4cea259c94b1b1abba4822c7bcf2b050a1c7f6a73',('BFT65B_outputs','part4_v2_dev_only_outputs')),
'clean':('panel_clean.parquet','0d1837815820e93eb71508dabd6f48143e2b596b09453606ccf0070c3717e107',('BFT65B_outputs','step2c_20261108_145539_477509'))}
def digest(f):
 h=hashlib.sha256()
 with f.open('rb') as stream:
  for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
 return h.hexdigest()
def locate(kind):
 name,h,dirs=EXPECTED[kind]
 candidate=Path.home().joinpath(*dirs,name)
 base=Path.home()/'BFT65B_outputs'
 paths=[candidate]+(list(base.rglob(name)) if base.is_dir() else [])
 for p in dict.fromkeys(paths):
  if p.is_file() and digest(p)==h:
   print(f'PASS {kind} hash: {p.name}',flush=True)
   return p
 raise RuntimeError(f'Cannot locate an exact hash-matching {name} below {base}.')
def main():
 import pandas,pyarrow,sklearn
 pin=json.loads((HERE/'PINNED_INPUTS.json').read_text(encoding='utf-8'))
 for name,hash_expected in pin['source_code_sha256'].items():
  p=HERE/'frozen_pipeline'/name
  if digest(p)!=hash_expected:raise RuntimeError('Frozen source checksum mismatch: '+name)
 print('PASS four source/protocol SHA-256 checks; installed sklearn',sklearn.__version__,flush=True)
 dev=locate('dev');clean=locate('clean')
 stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
 root=Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'BFT65B_E11_POST_LOCK_AUDIT'
 root.mkdir(parents=True,exist_ok=True)
 run=root/(f'RUN_{stamp}_{os.getpid()}');run.mkdir()
 output=run/'outputs'
 cmd=[sys.executable,str(HERE/'E11_AUDIT.py'),'--dev',str(dev),'--clean',str(clean),'--source',str(HERE/'frozen_pipeline'),'--out',str(output)]
 log=run/'RUN_LOG.txt'
 with log.open('w',encoding='utf-8') as f:
  # Only basenames; never publish user's Windows directories
  f.write('E11 read-only audit; frozen source hash verified; data hash verified\n')
  proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace')
  for line in proc.stdout:
   print(line,end='',flush=True);f.write(line)
  rc=proc.wait()
 status={'result':'PASS' if rc==0 else 'FAIL','python':sys.version.split()[0],
         'final_test_scored':False,'originals_modified':False,'output_kind':'POST_LOCK_DIAGNOSTICS'}
 (run/'STATUS.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
 target=Path.home()/'Downloads';target=target if target.is_dir() else root
 outzip=target/f'BFT65B_E11_RESULTS_{status["result"]}_{stamp}.zip'
 with zipfile.ZipFile(outzip,'w',compression=zipfile.ZIP_DEFLATED) as z:
  for f in run.rglob('*'):
   if f.is_file():z.write(f,f.relative_to(run))
 print('\nUPLOAD THIS ZIP:',outzip,flush=True)
 print('No original .parquet files are included.',flush=True)
 return rc
if __name__=='__main__':
 try:sys.exit(main())
 except Exception as exc:
  print('FAILED:',str(exc),flush=True);traceback.print_exc();sys.exit(2)
