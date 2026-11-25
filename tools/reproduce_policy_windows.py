#!/usr/bin/env python3
"""Find exact archived private development inputs and replay policy only, in a fresh external folder."""
from pathlib import Path
import argparse,datetime,os,sys,subprocess,zipfile,json
from reproduce_development import EXPECTED,hashfile,ROOT
NAMES={'development':'development_primary_binary_v2.parquet','failures':'failures.parquet','baseline':'SHARE_THIS_PART5_STEP01_EVIDENCE.zip','logistic':'SHARE_THIS_PART5_STEP02A_EVIDENCE.zip','hgb':'SHARE_THIS_PART5_STEP02B_EVIDENCE.zip'}
def locate(roots):
 result={};visited=set()
 for root in roots:
  if not root.is_dir():continue
  for d,dirs,files in os.walk(root):
   dirs[:]=[x for x in dirs if x not in {'.git','__pycache__','node_modules'}]
   for k,n in NAMES.items():
    if k in result or n not in files:continue
    p=(Path(d)/n).resolve()
    if p in visited:continue
    visited.add(p)
    try:
     if hashfile(p)==EXPECTED[k]:result[k]=p;print('FOUND exact input:',n,flush=True)
    except OSError:pass
   if len(result)==len(NAMES):return result
 return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--search-root',type=Path,action='append',default=[]);p.add_argument('--self-test',action='store_true');a=p.parse_args()
 if a.self_test:assert len(NAMES)==5 and all(k in EXPECTED for k in NAMES);print('PASS locator contract; no private data searched');return 0
 home=Path.home(); roots=a.search_root+[home/'BFT65B_outputs',home/'data_raw',home/'Downloads',home/'Desktop',home/'Documents']
 inputs=locate(roots); missing=[NAMES[k] for k in NAMES if k not in inputs]
 if missing:
  print('BLOCKED: no exact archived match for:',*missing,sep='\n');print('Extract original private evidence archives locally or supply --search-root. Do not change digests or upload private files.');return 2
 stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f');run=Path(os.environ.get('LOCALAPPDATA',str(home)))/'BFT65B_PRIVATE_REPRO'/stamp;run.parent.mkdir(parents=True,exist_ok=True)
 cmd=[sys.executable,'-B',str(ROOT/'tools/reproduce_development.py'),'--mode','policy','--dev',str(inputs['development']),'--failures',str(inputs['failures']),'--baseline',str(inputs['baseline']),'--logistic',str(inputs['logistic']),'--hgb',str(inputs['hgb']),'--out',str(run),'--execute']
 rc=subprocess.run(cmd,cwd=ROOT).returncode
 if rc:print('BLOCKED/FAIL: see terminal and local output (never upload private scores).');return rc
 status=run/'REPRODUCTION_STATUS.json'
 if not status.is_file() or json.loads(status.read_text())['status']!='PASS_FROZEN_DEVELOPMENT_REPRODUCTION_ONLY':return 3
 target=home/'Downloads';target.mkdir(exist_ok=True);zipname=target/f'BFT65B_DEVELOPMENT_REPLAY_PASS_{stamp}.zip'
 with zipfile.ZipFile(zipname,'x',compression=zipfile.ZIP_DEFLATED) as z:
  for path in [status,run/'policy/development_model_ranking_rechecked.csv',run/'policy/development_threshold_scenarios.csv',run/'policy/selected_hgb_fold_metrics_rechecked.csv',run/'policy/chronological_calibration_diagnostics.csv']:
   z.write(path,path.name)
 print('RETURN ONLY:',zipname,'\nPrivate row-level outputs remain local; no final test inference.')
 return 0
if __name__=='__main__':sys.exit(main())
