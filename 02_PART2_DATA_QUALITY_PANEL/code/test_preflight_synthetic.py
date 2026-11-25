"""Adversarial tests for the read-only preflight. These are synthetic, not FDIC data."""
import calendar
from contextlib import redirect_stdout
from datetime import date
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import polars as pl

p=Path(__file__).with_name('02d_preflight_part2.py')
spec=importlib.util.spec_from_file_location('preflight',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def qadd(d,n):
    k=d.year*4+(d.month-1)//3+n;y,q=divmod(k,4);mo=3*(q+1)
    return date(y,mo,calendar.monthrange(y,mo)[1])


def fixture(root):
    a=root/'step2';c=root/'step2c';a.mkdir();c.mkdir();audit=c/'review_AUDIT_ONLY';audit.mkdir()
    reports=[];d=date(1984,3,31)
    while d<=date(2026,6,30):reports.append(d);d=qadd(d,1)
    # Continuing, exact-boundary failure, merger, unknown, pre-period failure.
    stops={1:None,2:date(1984,6,30),3:date(1985,5,1),4:None,5:date(1982,1,1)}
    bounds={1:date(2026,6,30),2:stops[2],3:stops[3],4:date(1985,3,31),5:stops[5]}
    rows=[]
    for cert in stops:
        for day in reports:
            r={k:100.0 for k in sorted(m.FINANCIAL_COLUMNS-{'CERT','REPDTE','STNAME'})}
            r.update(CERT=cert,REPDTE=day,STNAME='TEST',ASSET=500.,DEP=100.,DEPDOM=101. if cert==1 else 90.,EQ=-1. if cert==4 else 10.)
            rows.append(r)
    base=pl.DataFrame(rows).with_columns(pl.col('CERT').cast(pl.Int64))
    kept=[r for r in rows if not stops[r['CERT']] or r['REPDTE']<stops[r['CERT']]]
    excluded=[{'CERT':r['CERT'],'REPDTE':r['REPDTE']} for r in rows if stops[r['CERT']] and r['REPDTE']>=stops[r['CERT']]]
    clean=pl.DataFrame(kept).sort('CERT','REPDTE')
    decisions=[]
    for r in kept:
        day=qadd(r['REPDTE'],1);cert=r['CERT']
        if day>date(2025,6,30) or day>bounds[cert] or (stops[cert] and day>=stops[cert]):continue
        x={('SOURCE_REPDTE' if k=='REPDTE' else k):v for k,v in r.items()};x['DECISION_DATE']=day;decisions.append(x)
    pit=pl.DataFrame(decisions).sort('CERT','DECISION_DATE')
    base.write_parquet(a/'panel_base.parquet');clean.write_parquet(c/'panel_clean.parquet');pit.write_parquet(c/'panel_pit_base.parquet')
    pl.DataFrame(excluded).write_csv(audit/'excluded_rows_AUDIT_ONLY.csv')
    reg=[]
    for cert in stops:
        r={k:None for k in m.DATE_COLUMNS};r.update(CERT=cert,FIRST_REPDTE=reports[0],LAST_REPDTE=reports[-1],RISK_STOP_DATE=stops[cert],ELIGIBILITY_END=bounds[cert]);reg.append(r)
    pl.DataFrame(reg).write_csv(audit/'bank_event_registry_AUDIT_ONLY.csv')
    pl.DataFrame([{'column':k,'null':clean[k].null_count()} for k,t in clean.schema.items() if t.is_numeric() and k!='CERT']).write_csv(audit/'numeric_profile_after.csv')
    h=m.sha(a/'panel_base.parquet')
    m.save_json(a/'step2_summary.json',{'panel_sha256':h})
    m.save_json(c/'step2c_config.json',{'step2_dir':str(a),'panel_sha256':h})
    s={'status':'CLEAN_PANEL_READY_FOR_REVIEW','source_rows':base.height,'source_banks':5,'clean_rows':clean.height,'clean_banks':clean['CERT'].n_unique(),'clean_quarters':170,'registry_banks':5,'excluded_rows':len(excluded),'decision_rows_lag1':pit.height,'decision_banks_lag1':pit['CERT'].n_unique(),'output_sha256':{n:m.sha(c/n) for n in ['panel_clean.parquet','panel_pit_base.parquet']}}
    m.save_json(c/'step2c_summary.json',s)
    return a,c


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.a,self.c=fixture(self.root)
    def tearDown(self):self.temp.cleanup()
    def run_check(self):
        with redirect_stdout(io.StringIO()):return m.run(self.c,self.root/'result',self.a)
    def refresh_hash(self,name):
        s=m.read_json(self.c/'step2c_summary.json');s['output_sha256'][name]=m.sha(self.c/name);m.save_json(self.c/'step2c_summary.json',s)
    def test_valid_and_inputs_unchanged(self):
        paths=list(self.a.glob('*'))+list(self.c.glob('*.parquet'))
        before={str(p):m.sha(p) for p in paths}
        self.assertTrue(self.run_check().is_file())
        self.assertEqual(before,{str(p):m.sha(p) for p in paths})
        soft=pl.read_csv(self.root/'result/financial_soft_checks.csv')
        self.assertGreater(soft.filter(pl.col('check')=='DEPDOM exceeds DEP')['flagged_rows'][0],0)
    def test_corrupt_bytes_detected(self):
        with (self.c/'panel_clean.parquet').open('ab') as f:f.write(b'corrupted')
        with self.assertRaisesRegex(ValueError,'SHA-256'):self.run_check()
    def test_changed_financial_value_even_with_updated_hash(self):
        p=self.c/'panel_clean.parquet';d=pl.read_parquet(p).with_columns((pl.col('ASSET')+1).alias('ASSET'));d.write_parquet(p);self.refresh_hash(p.name)
        with self.assertRaisesRegex(ValueError,'every financial value'):self.run_check()
    def test_changed_decision_value(self):
        p=self.c/'panel_pit_base.parquet';d=pl.read_parquet(p).with_columns((pl.col('NETINC')+1).alias('NETINC'));d.write_parquet(p);self.refresh_hash(p.name)
        with self.assertRaisesRegex(ValueError,'Every decision key and financial value'):self.run_check()
    def test_wrong_lag(self):
        p=self.c/'panel_pit_base.parquet';d=pl.read_parquet(p).with_columns(pl.col('SOURCE_REPDTE').alias('DECISION_DATE'));d.write_parquet(p);self.refresh_hash(p.name)
        with self.assertRaisesRegex(ValueError,'exactly one quarter'):self.run_check()
    def test_duplicate_key(self):
        p=self.c/'panel_clean.parquet';d=pl.read_parquet(p);pl.concat([d,d.head(1)]).write_parquet(p);self.refresh_hash(p.name)
        with self.assertRaisesRegex(ValueError,'dimensions and unique keys'):self.run_check()


if __name__=='__main__':unittest.main(verbosity=2)
