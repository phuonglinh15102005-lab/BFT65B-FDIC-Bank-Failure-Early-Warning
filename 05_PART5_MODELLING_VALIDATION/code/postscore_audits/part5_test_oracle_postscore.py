#!/usr/bin/env python3
"""Post-scoring READ-ONLY final-test label/source-lag integrity oracle.

Checks original SHA-matched frozen test cohort against locked saved score rows and
reconstructs Y_4Q independently from ORIGINAL SHA-matched FDIC first failures.
It NEVER imports a fitted model, predicts, refits, retunes, or revises scores.
This is not an independent point-in-time FEATURE FORMULA oracle; it verifies
cohort bytes/keys/source lag/label and saved-score consistency only.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import numpy as np,pandas as pd
from part4_v2_train_only_pipeline import FEATURES

COHORT_SHA='15ee908a4faf197dba8787821b8fd83bf2c7de5da2a325939b5b5e078a348298'
FAIL_SHA='a3e18c370f53c029e83708944bb91daf08ae5f664175f0fdd1bc389698c05ab3'

def check(ok,msg):
 if not bool(ok):raise AssertionError(msg)
def sha256(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for z in iter(lambda:f.read(1<<20),b''):h.update(z)
 return h.hexdigest()
def qi(v):
 d=pd.to_datetime(v)
 return d.dt.year*4+(d.dt.month-1)//3

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--cohort',type=Path,required=True)
 p.add_argument('--failures',type=Path,required=True)
 p.add_argument('--prior-revision-dir',type=Path,required=True)
 p.add_argument('--out',type=Path,default=Path('part5_test_oracle_results'))
 a=p.parse_args()
 for source,digest in [(a.cohort,COHORT_SHA),(a.failures,FAIL_SHA)]:
  check(source.is_file() and sha256(source)==digest,
        f'Frozen original source SHA mismatch: {source}; STOP. Do not use a refreshed cohort.')
 file=a.prior_revision_dir/'evidence/step06/final_test_scored_rows.csv.gz'
 check(file.is_file(),'Unzip previous revision package; locked final score file missing')
 cohort=pd.read_parquet(a.cohort)
 scored=pd.read_csv(file,parse_dates=['DECISION_DATE','SOURCE_REPDTE'])
 required={'CERT','DECISION_DATE','SOURCE_REPDTE','Y_4Q'}|set(FEATURES)
 check(required<=set(cohort.columns),'Frozen cohort required cols missing')
 cohort['DECISION_DATE']=pd.to_datetime(cohort.DECISION_DATE)
 cohort['SOURCE_REPDTE']=pd.to_datetime(cohort.SOURCE_REPDTE)
 check(len(cohort)==len(scored)==364440,'Test census mismatch')
 check(not cohort.duplicated(['CERT','DECISION_DATE']).any(),'Duplicate cohort bank-quarter')
 check(not scored.duplicated(['CERT','DECISION_DATE']).any(),'Duplicate archived score bank-quarter')
 k=['CERT','DECISION_DATE']
 joined=cohort[['CERT','DECISION_DATE','SOURCE_REPDTE','Y_4Q']].merge(
   scored[['CERT','DECISION_DATE','SOURCE_REPDTE','Y_4Q','score']],on=k,
   how='outer',validate='one_to_one',suffixes=('_cohort','_score'),indicator=True)
 check(joined._merge.eq('both').all(),'Saved score row keys differ from frozen cohort')
 check((joined.SOURCE_REPDTE_cohort==joined.SOURCE_REPDTE_score).all(),'Saved score timing differs from original cohort')
 check((joined.Y_4Q_cohort==joined.Y_4Q_score).all(),'Saved score labels differ from frozen cohort')
 check(((qi(joined.DECISION_DATE)-qi(joined.SOURCE_REPDTE_cohort))==1).all(),'Financial source lag is not exactly one quarter')
 fail=pd.read_parquet(a.failures)
 check({'CERT','RESTYPE','FAILDATE'}<=set(fail.columns),'FDIC source fields unavailable')
 fail=fail.loc[fail.RESTYPE.astype(str).str.upper().eq('FAILURE')].copy()
 fail['CERT']=pd.to_numeric(fail.CERT,errors='coerce')
 fail['FAILDATE']=pd.to_datetime(fail.FAILDATE,errors='coerce')
 fail=fail.dropna(subset=['CERT','FAILDATE'])
 fail['CERT']=fail.CERT.astype('int64')
 fail=fail.sort_values(['CERT','FAILDATE']).drop_duplicates('CERT')
 m=joined.merge(fail[['CERT','FAILDATE']],on='CERT',how='left',validate='many_to_one')
 lead=qi(m.FAILDATE)-qi(m.DECISION_DATE)
 independent_y=lead.between(1,4).fillna(False).astype('int8')
 disagreements=int((independent_y!=m.Y_4Q_cohort).sum())
 check(disagreements==0, f'CRITICAL: reconstructed test labels disagree on {disagreements} rows; do not change scored data, investigate!')
 for c in FEATURES:
  numeric=pd.to_numeric(cohort[c],errors='coerce')
  check(int(numeric.isna().sum())==int(cohort[c].isna().sum()),f'{c} cannot parse numeric')
  check(np.isfinite(numeric.dropna()).all(),f'{c} nonfinite input')
 summary={'status':'PASS_READ_ONLY_TEST_COHORT_OUTCOME_AND_LAG_ORACLE',
 'cohort_original_sha256':COHORT_SHA,'failures_original_sha256':FAIL_SHA,
 'rows':int(len(cohort)),'positive_rows':int(independent_y.sum()),
 'positive_unique_CERT':int(m.loc[independent_y.eq(1),'CERT'].nunique()),
 'key_mismatch':0,'label_mismatch':0,'source_quarter_lag_mismatch':0,
 'features_15_all_numeric_and_finite_except_NaN':True,
 'boundaries':['Does not validate the feature construction formulas against raw financial panel.',
               'Does not validate unresolved/excluded 25 rows absent from frozen cohort.',
               'This is a post-scoring read-only independent first-failure label reconstruction.',
               'No model predictions were invoked; threshold remained frozen.']}
 a.out.mkdir(parents=True,exist_ok=True)
 (a.out/'test_source_oracle.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
 print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
