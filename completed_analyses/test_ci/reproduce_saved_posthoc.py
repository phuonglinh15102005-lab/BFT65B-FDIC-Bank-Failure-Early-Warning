"""Reproduce the ALREADY SAVED post-hoc 1500 draws using identical fixed seed.
No new hypothesis/CI specification, fitting, inference or threshold selection.
Independent grouped-weight AP implementation, no execution of attached producer.
"""
from pathlib import Path
import json,hashlib,sys,time,platform
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
import argparse
R=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--locked-dir',type=Path,required=True,help='Existing immutable saved-test output directory, never a fitted model')
parser.add_argument('--evidence-dir',type=Path,default=R/'EVIDENCE/POSTHOC_ALREADY_SAVED')
parser.add_argument('--out',type=Path,required=True,help='NEW output directory separate from all inputs')
args=parser.parse_args();P=args.locked_dir.resolve();E=args.evidence_dir.resolve();O=args.out.resolve()
for inp in [P,E]:
 if O==inp or O.is_relative_to(inp) or inp.is_relative_to(O):parser.error('Output must be separate from immutable inputs')
O.mkdir(parents=True,exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
summary=json.loads((E/'008_NEW_POSTHOC_BOOTSTRAP_RESULTS.json').read_text());before={n:sha(P/n) for n in summary['source_hashes_sha256']};assert before==summary['source_hashes_sha256'];assert summary['seed']==20261117 and summary['num_replicates']==1500
s=pd.read_csv(P/'final_test_scored_rows.csv.gz',usecols=['CERT','Y_4Q','score']);events=pd.read_csv(P/'final_test_event_detection_by_cert.csv',usecols=['CERT','detected']);saved=pd.read_csv(E/'007_NEW_POSTHOC_BOOTSTRAP_DRAWS.csv',float_precision='round_trip')
cert,bank=np.unique(s.CERT.to_numpy(dtype='int64'),return_inverse=True);idx=np.argsort(-s.score.to_numpy(),kind='stable');ps=s.score.to_numpy()[idx];y=s.Y_4Q.to_numpy(dtype='int64')[idx];banks=bank[idx];starts=np.r_[0,1+np.flatnonzero(ps[1:]!=ps[:-1])];ec=np.searchsorted(cert,events.CERT.to_numpy(dtype='int64'));assert np.array_equal(cert[ec],events.CERT);det=events.detected.to_numpy(dtype='int64');rng=np.random.default_rng(20261117);results=[];t0=time.monotonic()
with threadpool_limits(limits=1):
 for i in range(1500):
  m=np.bincount(rng.integers(0,len(cert),size=len(cert)),minlength=len(cert));w=m[banks]
  group_pos=np.add.reduceat(w*y,starts);group_all=np.add.reduceat(w,starts);cp=np.cumsum(group_pos);ca=np.cumsum(group_all);precision=np.divide(cp,ca,out=np.zeros(len(cp),dtype='float64'),where=ca!=0);ap=float(np.sum(precision*group_pos)/cp[-1]);ew=m[ec];er=float(np.sum(ew*det)/np.sum(ew));results.append((i+1,ap,er))
  if (i+1)%100==0:print('REPRODUCED_SAME_SPEC',i+1,'of1500',round(time.monotonic()-t0,1),'s',flush=True)
new=pd.DataFrame(results,columns=['replicate','AP','event_recall']);assert np.array_equal(new.replicate,saved.replicate)
diff={c:float(np.abs(new[c]-saved[c]).max()) for c in ['AP','event_recall']};matched={c:int(np.isclose(new[c],saved[c],rtol=1e-11,atol=2e-12).sum()) for c in diff};status='PASS' if all(v==1500 for v in matched.values()) else 'FAIL'
new.to_csv(O/'REPRODUCED_FIXED_SPEC_DRAWS.csv',index=False,float_format='%.17g')
r={'status':status,'same_spec_replicates':1500,'seed':20261117,'bank_universe':len(cert),'max_absolute_difference':diff,'matched_replicates':matched,'input_sha256_before':before,'input_sha256_after':{n:sha(P/n) for n in before},'producer_source_sha256':sha(E/'005_bootstrap_locked_scores.py.txt'),'saved_draws_sha256':sha(E/'007_NEW_POSTHOC_BOOTSTRAP_DRAWS.csv'),'scope':'Independent exact same posthoc seed/spec replay against existing1500draws; not originalhistoricalCI recovery; no model fitting/inference or tuning','environment':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__},'elapsed_seconds':time.monotonic()-t0}
assert r['input_sha256_before']==r['input_sha256_after'];(O/'RESULT.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2));assert status=='PASS'
