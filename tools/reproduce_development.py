#!/usr/bin/env python3
"""Private-data reviewer reproduction of frozen DEVELOPMENT stages only. Never test inference."""
import argparse,hashlib,json,platform,subprocess,sys,os,importlib.metadata as md,csv,math,tempfile,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT/'05_PART5_MODELLING_VALIDATION/code/frozen_pipeline'
PROTOCOL=SRC/'part5_protocol_freeze.json'
EXPECTED={'protocol':'994f72de6e2446916db8c2fcd36847c45cc68eb6fef5ef67f07acc0476c6d911','development':'d365ce25204a3dcace715db4cea259c94b1b1abba4822c7bcf2b050a1c7f6a73','failures':'a3e18c370f53c029e83708944bb91daf08ae5f664175f0fdd1bc389698c05ab3','baseline':'27d7ab92912ede60429bcdc1b02660bf4d4d9175a8cdb62e99653d1d6cace009','logistic':'dee50122196ead42983b80f9668a769d105cf3a2e8268472dba3b80149c63a56','hgb':'8c0f41775316da61aab8f3aaa74f2e723f3adeb0d4e2069bb94c652e6b1f066d'}
def hashfile(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def require(x,m):
 if not x:raise ValueError(m)
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def compare_policy(actual,reference):
 def indexed(path):
  rs=rows(path); keys=[int(x['ratio']) for x in rs]
  require(len(keys)==len(set(keys)),'Duplicate scenario ratio')
  require(set(keys)=={5,10,20,50},'Scenario set changed')
  return dict(zip(keys,rs))
 a=indexed(actual);r=indexed(reference)
 for k in r:
  for c in ('fp_cert_years','missed_failure_certs','detected_failure_certs','cert_year_alerts','bank_quarter_alerts','cost_units'):
   require(float(a[k][c])==float(r[k][c]),f'Policy mismatch {k}/{c}')
  for c in ('threshold','COST_median_thousand_USD'):
   require(math.isclose(float(a[k][c]),float(r[k][c]),rel_tol=1e-10,abs_tol=1e-12),f'Policy numeric mismatch {k}/{c}')
def self_test(reference):
 original=rows(reference)
 cases=[('equal_reordered',list(reversed(original)),True)]
 for field in ('fp_cert_years','missed_failure_certs','detected_failure_certs','cert_year_alerts','bank_quarter_alerts','cost_units','threshold','COST_median_thousand_USD'):
  changed=copy.deepcopy(original); changed[0][field]=str(float(changed[0][field])+1.0)
  cases.append(('changed_'+field,changed,False))
 cases.extend([('missing_ratio',original[1:],False),('duplicate_ratio',original+[original[0]],False)])
 result=[]
 with tempfile.TemporaryDirectory() as d:
  p=Path(d)/'candidate.csv'
  for name,fixture,expected in cases:
   with p.open('w',encoding='utf-8',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(original[0]));writer.writeheader();writer.writerows(fixture)
   try:compare_policy(p,reference);accepted=True
   except ValueError:accepted=False
   require(accepted==expected,'Self-test failed: '+name)
   result.append({'case':name,'accepted':accepted,'status':'PASS'})
 print(json.dumps({'status':'PASS','scope':'synthetic comparison controls against archived aggregate; no model or test executed','cases':result},indent=2))
 return 0
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mode',choices=['policy','grid'],default='policy');p.add_argument('--dev',type=Path);p.add_argument('--failures',type=Path);p.add_argument('--baseline',type=Path);p.add_argument('--logistic',type=Path);p.add_argument('--hgb',type=Path);p.add_argument('--out',type=Path);p.add_argument('--execute',action='store_true');p.add_argument('--self-test',action='store_true');a=p.parse_args()
 reference=ROOT/'evidence/verified_archive_aggregates/threshold_cost_scenarios_4.csv'
 if a.self_test:return self_test(reference)
 if not a.execute:
  print(json.dumps({'status':'PLAN_ONLY','mode':a.mode,'input_sha256':EXPECTED,'stages':(['baseline','logistic','hgb'] if a.mode=='grid' else ['use original private OOF ZIPs'])+['development policy','compare to archive'],'note':'No test read/scoring. --execute requires original inputs, exact recorded runtime, fresh external directory.'},indent=2));return 0
 if not a.out:p.error('--out required')
 out=a.out.resolve();require(not out.exists() and not out.is_relative_to(ROOT),'fresh external output required')
 inputs={'protocol':PROTOCOL,'development':a.dev,'failures':a.failures}
 if a.mode=='policy':inputs.update(baseline=a.baseline,logistic=a.logistic,hgb=a.hgb)
 for k,v in inputs.items():require(v is not None and v.is_file() and hashfile(v)==EXPECTED[k],'missing/incorrect frozen input: '+k)
 require(a.dev.name=='development_primary_binary_v2.parquet' and a.failures.suffix=='.parquet','wrong input names/types')
 require(platform.python_version()=='3.13.7','recorded model Python 3.13.7 required')
 for pkg,version in {'numpy':'2.3.3','pandas':'2.3.3','scikit-learn':'1.9.0','joblib':'1.5.2'}.items():require(md.version(pkg)==version,'recorded version required: '+pkg)
 out.mkdir(); record={'status':'FAIL','mode':a.mode,'scope':'private development-only replication; never final test','input_hashes':{k:EXPECTED[k] for k in inputs},'stages':[],'python':platform.python_version()}
 def run(name,script,args):
  with (out/(name+'.log')).open('wb') as f:r=subprocess.run([sys.executable,'-B',str(SRC/script),*map(str,args)],cwd=SRC,stdout=f,stderr=subprocess.STDOUT)
  record['stages'].append({'stage':name,'exit_code':r.returncode});require(r.returncode==0,'stage failed: '+name)
 try:
  z={k:inputs[k] for k in ('baseline','logistic','hgb') if k in inputs}
  if a.mode=='grid':
   for k,script,zipname in [('baseline','part5_step01_baseline_dev_only.py','SHARE_THIS_PART5_STEP01_EVIDENCE.zip'),('logistic','part5_step02_logistic_grid_dev.py','SHARE_THIS_PART5_STEP02A_EVIDENCE.zip'),('hgb','part5_step02_hgb_grid_dev.py','SHARE_THIS_PART5_STEP02B_EVIDENCE.zip')]:
    run(k,script,['--protocol',PROTOCOL,'--dev',a.dev.resolve(),'--out',out/k]);z[k]=out/k/zipname
  run('policy','part5_step03_development_policy.py',['--protocol',PROTOCOL,'--dev',a.dev.resolve(),'--failures',a.failures.resolve(),'--step01',z['baseline'].resolve(),'--step02a',z['logistic'].resolve(),'--step02b',z['hgb'].resolve(),'--out',out/'policy'])
  compare_policy(out/'policy/development_threshold_scenarios.csv',reference)
  rank=rows(out/'policy/development_model_ranking_rechecked.csv');ref=rows(ROOT/'evidence/verified_archive_aggregates/candidate_grid_21.csv')
  r={x['config']:float(x['mean_ap']) for x in rank};e={x['config']:float(x['mean_ap']) for x in ref};require(len(r)==21 and r.keys()==e.keys(),'candidate set mismatch')
  for k in r:require(math.isclose(r[k],e[k],abs_tol=1e-10,rel_tol=1e-9),'AP mismatch: '+k)
  require(max(r,key=r.get)=='HGB_L15_LR0p05_I150_L21_CLnone','winner changed')
  require(all(hashfile(v)==EXPECTED[k] for k,v in inputs.items()),'input changed')
  record['status']='PASS_FROZEN_DEVELOPMENT_REPRODUCTION_ONLY'
 except Exception as ex:record['error']=str(ex)
 finally:(out/'REPRODUCTION_STATUS.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record,indent=2))
 return 0 if record['status'].startswith('PASS') else 1
if __name__=='__main__':sys.exit(main())
