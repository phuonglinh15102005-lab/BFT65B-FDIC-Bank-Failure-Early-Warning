#!/usr/bin/env python3
"""Independent pandas re-derivation of ALL 15 frozen test features using original PIT and clean data.

Reference definition is the already-reviewed Part 4 pandas oracle (NOT the Polars builder).
Read-only postscore verification; no model prediction, training, threshold or label change.
"""
from pathlib import Path
import argparse,hashlib,json
import pandas as pd,numpy as np
from part4_step03_pandas_oracle_UNCHANGED import independent_features, FEATURES, RAW, qid
SHA={'cohort':'15ee908a4faf197dba8787821b8fd83bf2c7de5da2a325939b5b5e078a348298',
     'clean':'0d1837815820e93eb71508dabd6f48143e2b596b09453606ccf0070c3717e107',
     'pit':'3fce669406ff1898ac85d9c41c6385b7f8c6b27e29ecd041bb0a3c59f6337421'}
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(4<<20),b''):h.update(b)
 return h.hexdigest()
def check(ok,why):
 if not bool(ok):raise AssertionError(why)
def main():
 p=argparse.ArgumentParser();p.add_argument('--cohort',type=Path,required=True);p.add_argument('--pit',type=Path,required=True);p.add_argument('--clean',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 for role in SHA:
  source=getattr(a,role);check(source.is_file() and sha(source)==SHA[role],f'Locked {role} mismatch. Refusing nonoriginal source.')
 a.out.mkdir(parents=True,exist_ok=True)
 test=pd.read_parquet(a.cohort)
 for c in ['DECISION_DATE','SOURCE_REPDTE']: test[c]=pd.to_datetime(test[c],errors='raise')
 check(len(test)==364440 and int(test.Y_4Q.sum())==1112,'Frozen cohort census mismatch')
 check(not test.duplicated(['CERT','DECISION_DATE']).any(),'Duplicate frozen test bank-quarter keys')
 pit=pd.read_parquet(a.pit,columns=RAW)
 for c in ['DECISION_DATE','SOURCE_REPDTE']:pit[c]=pd.to_datetime(pit[c],errors='raise')
 pit=pit.loc[pit.DECISION_DATE.between(pd.Timestamp('2010-03-31'),pd.Timestamp('2025-06-30'))].copy()
 check(not pit.duplicated(['CERT','DECISION_DATE']).any(),'PIT source duplicated bank quarters')
 left=test[['CERT','DECISION_DATE','SOURCE_REPDTE']+FEATURES]
 joined=left.merge(pit,on=['CERT','DECISION_DATE'],how='left',validate='one_to_one',suffixes=('','_PIT'),indicator=True)
 check(len(joined)==len(test),'PIT joined rowcount mismatch')
 check(joined['_merge'].eq('both').all(),'Test decision key missing from source PIT')
 check(joined.SOURCE_REPDTE.eq(joined.SOURCE_REPDTE_PIT).all(),'Previous quarter PIT report date mismatch')
 clean=pd.read_parquet(a.clean,columns=['CERT','REPDTE','ASSET'])
 clean['REPDTE']=pd.to_datetime(clean.REPDTE,errors='raise')
 # Include full history: exact-calendar growth can refer to quarters preceding 2010.
 check(not clean.duplicated(['CERT','REPDTE']).any(),'Duplicate raw statement bank/report dates')
 expected=independent_features(joined,clean)
 stats=[]; examples=[]; issues=0
 for feature in FEATURES:
  rec=pd.to_numeric(joined[feature],errors='coerce').to_numpy(dtype=np.float64)
  oracle=expected[feature].to_numpy(dtype=np.float64)
  same=np.isclose(rec,oracle,rtol=1e-8,atol=1e-9,equal_nan=True)
  nbad=int(np.count_nonzero(~same));issues+=nbad
  maxerr=float(np.nanmax(abs(rec[~same]-oracle[~same]))) if nbad and np.any(np.isfinite(rec[~same]-oracle[~same])) else None
  stats.append({'feature':feature,'rows':len(test),'mismatches':nbad,'max_abs_discrepancy':maxerr,'stored_missing':int(np.isnan(rec).sum()),'reconstructed_missing':int(np.isnan(oracle).sum())})
  if nbad:
   for ix in np.flatnonzero(~same)[:6]:
    examples.append({'feature':feature,'CERT':int(joined.iloc[ix].CERT),'DECISION_DATE':str(joined.iloc[ix].DECISION_DATE.date()),'stored':None if np.isnan(rec[ix]) else float(rec[ix]),'oracle':None if np.isnan(oracle[ix]) else float(oracle[ix])})
 pd.DataFrame(stats).to_csv(a.out/'test_15_feature_formula_comparison.csv',index=False)
 if examples:pd.DataFrame(examples).to_csv(a.out/'mismatch_examples.csv',index=False)
 s={'status':'PASS_INDEPENDENT_TEST_FEATURE_FORMULAS' if issues==0 else 'FAIL_TEST_FEATURE_FORMULA_MISMATCH','rows':len(test),'n_features':15,'total_cell_comparisons':15*len(test),'total_mismatches':issues,'source_hashes':SHA,'reference':'Independent Part 4 pandas quarter-ID oracle, matched exact sha original PIT, clean and cohort','boundary':'Test feature formulas and missingness are audited after scoring; this does not establish historical statement-vintage availability, assess 25 excluded test rows or change model scores.','details':stats}
 (a.out/'feature_oracle_summary.json').write_text(json.dumps(s,indent=2,allow_nan=False)+'\n')
 print(json.dumps({k:v for k,v in s.items() if k!='details'},indent=2),flush=True)
 check(issues==0,f'{issues} mismatching feature cells; see mismatch report. Do not alter locked scores.')
if __name__=='__main__':main()
