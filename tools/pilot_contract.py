#!/usr/bin/env python3
"""Synthetic reference contract for prospective supervisory design, not FDIC evidence."""
from dataclasses import dataclass
from datetime import datetime,timezone
from math import log,isfinite
import argparse,json
@dataclass(frozen=True)
class Filing:
 bank:str; quarter:int; accepted:datetime; revision:int; asset:float

def asof(filings,bank,quarter,cutoff):
 eligible=[f for f in filings if f.bank==bank and f.quarter==quarter and f.accepted<=cutoff]
 if not eligible:return None
 keys=[(f.accepted,f.revision) for f in eligible]
 if len(keys)!=len(set(keys)):raise ValueError('ambiguous versions')
 return max(eligible,key=lambda f:(f.accepted,f.revision))
def features(filings,bank,t,cutoff):
 current=asof(filings,bank,t-1,cutoff)
 if current is None:return None
 def growth(q):
  prior=asof(filings,bank,q,cutoff)
  return log(current.asset/prior.asset) if prior and current.asset>0 and prior.asset>0 else None
 return {'1q':growth(t-2),'4q':growth(t-5)}
def allocate(cases,slots,cutoff,approver):
 if slots<0 or not approver: raise ValueError('invalid capacity or approver')
 if len({c['bank'] for c in cases})!=len(cases):raise ValueError('duplicate bank')
 if any(not isfinite(c['score']) for c in cases):raise ValueError('invalid score')
 result=[]
 for rank,c in enumerate(sorted(cases,key=lambda c:(-c['score'],c['bank'])),1):
  result.append({'bank':c['bank'],'rank':rank,'score':c['score'],'cutoff':cutoff.isoformat(),'status':'review' if rank<=slots else 'deferred','reason':'capacity available' if rank<=slots else 'capacity exhausted','approver':approver})
 return result
def self_test():
 cutoff=datetime(2007,3,31,tzinfo=timezone.utc); earlier=datetime(2007,1,30,tzinfo=timezone.utc); later=datetime(2007,5,1,tzinfo=timezone.utc)
 files=[Filing('A',4,earlier,0,121),Filing('A',0,earlier,0,100),Filing('A',4,later,1,125)]
 a=features(files,'A',5,cutoff); assert a['1q'] is None and abs(a['4q']-log(1.21))<1e-12
 assert abs(features(files,'A',5,later)['4q']-log(1.25))<1e-12
 assert features(files,'A',6,cutoff) is None
 try:asof(files+[files[0]],'A',4,cutoff);raise AssertionError('duplicate was accepted')
 except ValueError:pass
 queue=allocate([{'bank':'C','score':.2},{'bank':'A','score':.5},{'bank':'B','score':.3}],2,cutoff,'fixture_supervisor')
 assert len(queue)==3 and [q['bank'] for q in queue]==['A','B','C'] and queue[2]['status']=='deferred' and queue[2]['approver']
 print(json.dumps({'status':'PASS_SYNTHETIC_CONTRACT_ONLY','checks':5,'before_amendment_growth':a['4q'],'after_amendment_growth':log(1.25),'queue':queue},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--self-test',action='store_true',required=True);p.parse_args();self_test()
