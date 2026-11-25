"""Unit tests for Step03 alarm semantics; run before the real evidence audit."""
import unittest
import itertools
import numpy as np
import pandas as pd
from part5_step03_development_policy import policy_scan, exact_metrics_under_threshold, quarter_id

class TestThresholdSemantics(unittest.TestCase):
    def setUp(self):
        self.d=pd.DataFrame({
            'fold':['toy']*11,
            'CERT':[1,1,1,1,2,2,2,3,3,4,4],
            'year':[2000,2000,2000,2001,2000,2000,2001,2000,2000,2000,2000],
            'day':[11000,11100,11200,11400,11000,11100,11400,11000,11100,11000,11100],
            'y':[0,1,1,1,1,1,0,0,0,0,1],
            'score':[.2,.8,.7,.3,.9,.9,.3,.1,.1,.08,.4]})
        self.d['dt']=pd.to_datetime(self.d.day,unit='D',origin='unix')
        # Synthetic 4-event positive universe contains CERT 1,2,4.
        self.failures=pd.DataFrame({'CERT':[1,2,4],
            'FAILDATE':pd.to_datetime(['2001-06-30','2001-06-30','2001-06-30'])})
    def test_exact_threshold_matches_brute_force(self):
        d=self.d
        out,_=policy_scan(d,ratios=[5,20],expected_event_count=3)
        scores=np.r_[np.nextafter(d.score.max(),np.inf), sorted(d.score.unique(),reverse=True)]
        best={5:None,20:None}
        positives=set(d.loc[d.y.eq(1),'CERT'])
        for t in scores:
            x=d[d.score>=t].sort_values(['CERT','year','day']).drop_duplicates(['CERT','year'])
            nfp=int((x.y==0).sum())
            nfound=x[x.y==1].CERT.nunique()
            for r in best:
                cost=nfp+r*(len(positives)-nfound)
                if best[r] is None or cost < best[r][0] or (cost == best[r][0] and t>best[r][1]):
                    best[r]=(cost,t,nfp,len(positives)-nfound)
        for row in out.itertuples(index=False):
            x=best[row.ratio]
            self.assertEqual(int(row.cost_units),x[0])
            self.assertAlmostEqual(row.threshold,x[1],places=13)
            self.assertEqual(int(row.fp_cert_years),x[2])
            self.assertEqual(int(row.missed_failure_certs),x[3])

    def test_first_alarm_only_and_source_quarter(self):
        d=self.d
        x=d[d.score>=.2].sort_values(['CERT','year','day']).drop_duplicates(['CERT','year'])
        t=x[(x.CERT==1)&(x.year==2000)].iloc[0]
        self.assertEqual(int(t.y),0)  # earlier low-score alert makes later true alerts suppressed
        s=pd.Series(pd.to_datetime(['2000-03-31','2000-12-31',None]))
        np.testing.assert_array_equal(quarter_id(s),np.array([8000,8003,-39996]))

if __name__=='__main__':unittest.main()
