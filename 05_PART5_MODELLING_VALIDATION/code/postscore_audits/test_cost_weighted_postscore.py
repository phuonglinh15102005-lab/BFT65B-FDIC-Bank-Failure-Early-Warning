#!/usr/bin/env python3
"""Read-only FDIC COST-weighted test-event detection from original locked events + failures snapshot.

Ex-post *descriptive* metric. It does NOT evaluate a newly fitted model on test,
select cutoff, revise labels, or infer preventable cost. Expected original source SHA enforced.
"""
from pathlib import Path
import argparse,hashlib,json
import pandas as pd, numpy as np
FAIL_SHA='a3e18c370f53c029e83708944bb91daf08ae5f664175f0fdd1bc389698c05ab3'

def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def require(ok,msg):
 if not ok:raise AssertionError(msg)

def main():
 p=argparse.ArgumentParser();p.add_argument('--failures',type=Path,required=True);p.add_argument('--events',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 require(digest(a.failures)==FAIL_SHA,'Original locked failures hash differs. Stop.')
 ev=pd.read_csv(a.events,parse_dates=['FAILDATE']);require(len(ev)==341 and int(ev.detected.sum())==326,'Test event census mismatch')
 require(not ev.CERT.duplicated().any(),'Duplicate CERT in fixed event table')
 fd=pd.read_parquet(a.failures); require({'CERT','FAILDATE','RESTYPE','COST','QBFASSET'} <= set(fd.columns),'Required FDIC columns missing')
 fd=fd.loc[fd.RESTYPE.astype(str).str.upper().eq('FAILURE')].copy()
 fd['FAILDATE']=pd.to_datetime(fd['FAILDATE'],errors='coerce');fd['CERT']=pd.to_numeric(fd.CERT,errors='coerce')
 fd=fd.dropna(subset=['FAILDATE','CERT']);fd['CERT']=fd.CERT.astype('int64')
 fd=fd.sort_values(['CERT','FAILDATE'],kind='mergesort').drop_duplicates('CERT',keep='first')
 j=ev.merge(fd[['CERT','FAILDATE','COST','QBFASSET']],on='CERT',how='left',validate='one_to_one',suffixes=('_event','_source'),indicator=True)
 require((j._merge=='both').all(),'At least one event missing FDIC FAILURE source')
 require(j.FAILDATE_event.eq(j.FAILDATE_source).all(),'Original FDIC first failure date differs from locked event table')
 j['COST_kUSD']=pd.to_numeric(j.COST,errors='coerce');j['assets_kUSD']=pd.to_numeric(j.QBFASSET,errors='coerce')
 j['valid_cost_nonnegative']=j.COST_kUSD.notna() & np.isfinite(j.COST_kUSD) & (j.COST_kUSD>=0)
 j['strictly_positive_cost']=j.valid_cost_nonnegative & (j.COST_kUSD>0)
 j['cost_kUSD_in_metric']=j.COST_kUSD.where(j.valid_cost_nonnegative)
 v=j.loc[j.valid_cost_nonnegative]; require(len(v)>0,'No nonnegative observed COST')
 total=float(v.COST_kUSD.sum());detected=float(v.loc[v.detected,'COST_kUSD'].sum());missed=float(v.loc[~v.detected,'COST_kUSD'].sum())
 require(np.isclose(total,detected+missed,rtol=1e-12,atol=1e-7),'Resolution-cost totals fail reconciliation')
 observed=pd.DataFrame({'group':['all','detected','missed'],
  'total_failure_events':[len(j),int(j.detected.sum()),int((~j.detected).sum())],
  'valid_nonnegative_COST_count':[len(v),int(v.detected.sum()),int((~v.detected).sum())],
  'positive_COST_count':[int(j.strictly_positive_cost.sum()),int((j.strictly_positive_cost & j.detected).sum()),int((j.strictly_positive_cost & ~j.detected).sum())],
  'sum_observed_COST_USD_million':[total/1000,detected/1000,missed/1000]})
 byyear=j.assign(failure_year=j.FAILDATE_event.dt.year).groupby(['failure_year','detected'],as_index=False).agg(events=('CERT','size'),observed_positive_cost=('strictly_positive_cost','sum'),sum_cost_kUSD=('cost_kUSD_in_metric','sum'))
 j['loss_over_assets']=j.COST_kUSD/j.assets_kUSD
 j.loc[(~j.valid_cost_nonnegative)|(j.assets_kUSD<=0),'loss_over_assets']=np.nan
 j[['CERT','FAILDATE_event','detected','COST_kUSD','assets_kUSD','valid_cost_nonnegative','loss_over_assets']].to_csv(a.out/'locked_test_event_COST_join.csv',index=False)
 observed.to_csv(a.out/'test_COST_detected_vs_missed.csv',index=False)
 byyear.to_csv(a.out/'test_COST_by_failure_year.csv',index=False)
 value={'status':'PASS_READONLY_TEST_COST_WEIGHTING','test_failure_events':len(j),'detected':int(j.detected.sum()),'missed':int((~j.detected).sum()),'valid_nonnegative_COST_events':len(v),'missing_or_invalid_COST_events':len(j)-len(v),'positive_COST_events':int(j.strictly_positive_cost.sum()),'COST_weighted_event_recall_observed_only':detected/total,'observed_COST_sum_USD_million':total/1000,'detected_COST_sum_USD_million':detected/1000,'missed_COST_sum_USD_million':missed/1000,'missed_COST_share':missed/total,'unweighted_event_recall':float(j.detected.mean()),'missing_Cost_handling':'Excluded from denominator rather than imputed; zero COST remains valid with zero weight','interpretation':'Ex-post share of recorded FDIC resolution loss occurring in institutions flagged by frozen annual-first policy; not a prevention or avoided-loss estimate','source_sha256':FAIL_SHA,'test_events_source':'registered saved final test event CSV, no new predictions'}
 (a.out/'test_cost_weighted_summary.json').write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
 print(json.dumps(value,indent=2))
if __name__=='__main__':main()
