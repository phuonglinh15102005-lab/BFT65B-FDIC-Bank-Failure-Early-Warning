#!/usr/bin/env python3
"""Data-free, fail-closed audit of an extracted or cloned release. No network or fitting."""
import argparse,csv,hashlib,json,platform,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): h.update(b)
 return h.hexdigest()
def verify_manifest():
 with (ROOT/'FILE_MANIFEST_SHA256.csv').open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
 seen=set()
 for r in rows:
  rel=r['relative_path']; p=ROOT/rel
  if not p.resolve().is_relative_to(ROOT) or rel in seen or not p.is_file() or p.stat().st_size!=int(r['bytes']) or digest(p)!=r['sha256']: raise ValueError('Manifest mismatch: '+rel)
  seen.add(rel)
 actual={p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and '.git' not in p.relative_to(ROOT).parts and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.name!='FILE_MANIFEST_SHA256.csv'}
 if seen!=actual: raise ValueError('Unexpected or missing manifest paths: '+str(sorted(seen^actual)))
 return len(rows)
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True,type=Path);a=ap.parse_args();out=a.out.resolve()
 if out.is_relative_to(ROOT) or out.exists():ap.error('Output must be new and outside repo')
 out.mkdir(parents=True); status={'scope':'data-free source and archived aggregate audit, not E2E','python':platform.python_version(),'commands':[],'status':'FAIL'}
 try:
  status['manifest_entries']=verify_manifest()
  for i,args in enumerate([
   ['-m','unittest','discover','-s','tests','-q'],['run.py','plan'],['run.py','validate','--out',str(out/'source_validation')],['tools/verify_released_aggregates.py'],['tools/verify_e11_e12_aggregate.py'],['tools/verify_e10_workload_aggregate.py'],['evidence/examiner_supplement/verify_evidence.py','--output',str(out/'S1_results.json')],['tools/pilot_contract.py','--self-test'],['tools/reproduce_development.py','--self-test'],['tools/reproduce_policy_windows.py','--self-test'],['tools/verify_final_review.py'],['tools/verify_recovered_acquisition.py'],['tools/verify_final_execution.py'],['tools/BFT65B_PUBLICATION_PRECHECK.py','.','--json',str(out/'publication_scan.json')]]):
   with (out/f'{i+1:02d}.log').open('wb') as log: r=subprocess.run([sys.executable,'-B',*args],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
   # output argument path is local and stays outside publication; record command template only
   status['commands'].append({'script':args[0],'exit_code':r.returncode,'log':f'{i+1:02d}.log'})
   if r.returncode:raise RuntimeError(f'Check {i+1} failed, see {i+1:02d}.log')
  status['status']='PASS_PUBLIC_SOURCE_AND_ARCHIVED_AGGREGATES'
 except Exception as e:
  status['error']=str(e)
 finally:
  (out/'reviewer_status.json').write_text(json.dumps(status,indent=2)+'\n',encoding='utf8');print(json.dumps(status,indent=2))
 return 0 if status['status'].startswith('PASS') else 1
if __name__=='__main__':sys.exit(main())
