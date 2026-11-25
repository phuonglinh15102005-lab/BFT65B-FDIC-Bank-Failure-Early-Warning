#!/usr/bin/env python3
"""Read-only check of the EXISTING Part 2 Parquets before Part 3.

Run: python 02d_preflight_part2.py
Optional: --step2c-dir PATH --step2-dir PATH --out NEW_DIRECTORY
Requires only the existing Polars environment. No network access, downloads,
source modifications, new labels, imputation or clipping. Writes a small review
ZIP and aggregate checks to a NEW directory. Not a performance benchmark.
Sources: BFT65B brief; https://api.fdic.gov/banks/docs/ and saved 2A/2C evidence.
AI assistance: ChatGPT, 9 November 2026; cite in report and README.
"""
from __future__ import annotations
import argparse
from datetime import date, datetime, timezone
import gc
import hashlib
import json
from pathlib import Path
import platform
import sys
import zipfile
try:
    import polars as pl
except ImportError:
    raise SystemExit('Use the same Python environment that ran Part 2; Polars is required.')

FINANCIAL_COLUMNS = {'CERT','REPDTE','STNAME','ASSET','DEP','DEPDOM','EQ','BRO',
    'CHBAL','SC','LNLSGR','LNLSNET','LNRE','LNCI','LNCON','LNATRES','NCLNLS',
    'P3ASSET','P9ASSET','NAASSET','NTLNLS','ORE','NETINC','INTINC','EINTEXP',
    'NONII','NONIX','ELNATR','ROA','ROE','NIMY','RBC1AAJ','RBCRWAJ'}
DATE_COLUMNS = ['FIRST_REPDTE','LAST_REPDTE','EXIT_DATE','RISK_STOP_DATE',
    'FIRST_FAILURE_DATE','SNAPSHOT_ENDEFYMD','ELIGIBILITY_END']


def say(s): print(s, flush=True)
def require(ok, message):
    if not ok: raise ValueError(message)
def read_json(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def save_json(p, obj):
    p.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False,default=str)+'\n',encoding='utf-8')


def locate(explicit):
    if explicit: return explicit.expanduser().resolve()
    candidates=set()
    for root in (Path.home()/'BFT65B_outputs',Path(__file__).resolve().parent/'BFT65B_outputs'):
        if root.is_dir():
            for p in root.glob('step2c_*'):
                if (p/'STEP2C_COMPLETE.json').is_file(): candidates.add(p)
    require(bool(candidates),'Cannot find completed Part 2C. Add --step2c-dir "PATH"; no re-download is needed.')
    return max(candidates,key=lambda p:(p/'STEP2C_COMPLETE.json').stat().st_mtime).resolve()


def run(step2c, out, step2=None):
    sc=read_json(step2c/'step2c_summary.json');cfg=read_json(step2c/'step2c_config.json')
    require(sc['status']=='CLEAN_PANEL_READY_FOR_REVIEW','Part 2C is not complete.')
    step2=(step2 or Path(cfg['step2_dir'])).expanduser().resolve()
    require(not out.exists(),'Choose a NEW output directory; existing results will not be overwritten.')
    require(all(not out.is_relative_to(p) and not p.is_relative_to(out) for p in (step2,step2c)),'Output must be separate from inputs.')
    out.mkdir(parents=True)
    checks=[];hashes={}
    def check(name, ok):
        require(ok, name)
        checks.append({'check':name,'status':'PASS'})
    try:
        say('[1/6] Reading and verifying existing Parquet checksums...')
        sa=read_json(step2/'step2_summary.json')
        files={'panel_base.parquet':step2/'panel_base.parquet','panel_clean.parquet':step2c/'panel_clean.parquet','panel_pit_base.parquet':step2c/'panel_pit_base.parquet'}
        expected={'panel_base.parquet':cfg['panel_sha256'],**{n:sc['output_sha256'][n] for n in ('panel_clean.parquet','panel_pit_base.parquet')}}
        check('Base identity agrees with Part 2A',sa['panel_sha256']==cfg['panel_sha256'])
        for name,path in files.items():
            require(path.is_file(),'Missing existing file: '+str(path))
            hashes[name]=sha(path)
            check('SHA-256 '+name,hashes[name]==expected[name])
        say('[2/6] Checking complete schemas and keys...')
        schemas={n:pl.read_parquet_schema(p) for n,p in files.items()}
        clean_schema=schemas['panel_clean.parquet'];pit_schema=schemas['panel_pit_base.parquet']
        check('Financial schema matches base',clean_schema==schemas['panel_base.parquet'])
        check('Financial field allowlist',set(clean_schema)==FINANCIAL_COLUMNS)
        check('Typed financial keys',clean_schema['CERT']==pl.Int64 and clean_schema['REPDTE']==pl.Date and clean_schema['STNAME']==pl.String)
        check('Numeric financial fields',all(t.is_numeric() for c,t in clean_schema.items() if c not in {'CERT','REPDTE','STNAME'}))
        wanted={('SOURCE_REPDTE' if c=='REPDTE' else c):t for c,t in clean_schema.items()};wanted['DECISION_DATE']=pl.Date
        check('Decision field allowlist and schema',dict(pit_schema)==wanted)
        save_json(out/'schemas.json',{n:{c:str(t) for c,t in s.items()} for n,s in schemas.items()})
        audit=step2c/'review_AUDIT_ONLY'
        exclusions=pl.read_csv(audit/'excluded_rows_AUDIT_ONLY.csv',try_parse_dates=True,infer_schema_length=None).select('CERT','REPDTE').cast({'CERT':pl.Int64,'REPDTE':pl.Date})
        registry=pl.read_csv(audit/'bank_event_registry_AUDIT_ONLY.csv',schema_overrides={c:pl.String for c in DATE_COLUMNS},infer_schema_length=None).with_columns(*[pl.col(c).str.to_date('%Y-%m-%d',strict=True) for c in DATE_COLUMNS],pl.col('CERT').cast(pl.Int64))
        check('Registry has unique bank keys',registry.height==registry['CERT'].n_unique()==sc['registry_banks'])
        base=pl.read_parquet(files['panel_base.parquet'])
        clean=pl.read_parquet(files['panel_clean.parquet'])
        for name,df,rows,banks in [('Base',base,sc['source_rows'],sc['source_banks']),('Clean',clean,sc['clean_rows'],sc['clean_banks'])]:
            check(name+' dimensions and unique keys',df.height==rows and df['CERT'].n_unique()==banks and df.select('CERT','REPDTE').unique().height==rows)
            check(name+' valid quarter-end keys',df.filter(pl.col('CERT').is_null()|(pl.col('CERT')<=0)|pl.col('REPDTE').is_null()|(pl.col('REPDTE')!=pl.col('REPDTE').dt.month_end())|(~pl.col('REPDTE').dt.month().is_in([3,6,9,12]))).height==0)
        check('Clean quarter coverage',clean['REPDTE'].n_unique()==sc['clean_quarters'] and clean['REPDTE'].min()==date(1984,3,31) and clean['REPDTE'].max()==date(2026,6,30))
        check('Exclusion keys unique and present',exclusions.unique().height==exclusions.height==sc['excluded_rows'] and exclusions.join(base.select('CERT','REPDTE'),on=['CERT','REPDTE'],how='anti').height==0)
        say('[3/6] Comparing every retained financial value with panel_base...')
        expected_clean=base.join(exclusions,on=['CERT','REPDTE'],how='anti').sort('CERT','REPDTE')
        del base;gc.collect()
        check('Clean keys and every financial value match base minus logged exclusions',expected_clean.equals(clean.sort('CERT','REPDTE'),null_equal=True))
        del expected_clean;gc.collect()
        check('Clean keys all have registry evidence',clean.select('CERT').unique().join(registry.select('CERT'),on='CERT',how='anti').height==0)
        check('No retained report at/after risk stop',clean.select('CERT','REPDTE').join(registry.select('CERT','RISK_STOP_DATE'),on='CERT',validate='m:1').filter(pl.col('REPDTE')>=pl.col('RISK_STOP_DATE')).height==0)
        numeric=[c for c,t in clean.schema.items() if t.is_numeric() and c!='CERT']
        nf=clean.select([(~pl.col(c).is_finite()).sum().alias(c) for c in numeric]).row(0)
        check('All numeric cells finite or null',all(v==0 for v in nf))
        profile=pl.read_csv(audit/'numeric_profile_after.csv',infer_schema_length=None)
        calculated=clean.select(*[pl.col(c).null_count().alias(c) for c in numeric]).row(0,named=True)
        check('Full-file null counts match saved profile',all(calculated[r['column']]==r['null'] for r in profile.iter_rows(named=True)))
        say('[4/6] Comparing every decision row and value with the exact prior quarter...')
        pit=pl.read_parquet(files['panel_pit_base.parquet'])
        check('Decision dimensions and unique keys',pit.height==sc['decision_rows_lag1'] and pit['CERT'].n_unique()==sc['decision_banks_lag1'] and pit.select('CERT','DECISION_DATE').unique().height==pit.height)
        check('Decision dates exactly one quarter after source',pit.filter(pl.col('DECISION_DATE').is_null()|pl.col('SOURCE_REPDTE').is_null()|(pl.col('DECISION_DATE')!=pl.col('SOURCE_REPDTE').dt.offset_by('3mo').dt.month_end())|(pl.col('DECISION_DATE')>date(2025,6,30))).height==0)
        expected_pit=(clean.rename({'REPDTE':'SOURCE_REPDTE'}).with_columns(pl.col('SOURCE_REPDTE').dt.offset_by('3mo').dt.month_end().alias('DECISION_DATE'))
            .join(registry.select('CERT','RISK_STOP_DATE','ELIGIBILITY_END'),on='CERT',validate='m:1')
            .filter((pl.col('DECISION_DATE')<=date(2025,6,30))&(pl.col('DECISION_DATE')<=pl.col('ELIGIBILITY_END'))&(pl.col('RISK_STOP_DATE').is_null()|(pl.col('DECISION_DATE')<pl.col('RISK_STOP_DATE'))))
            .drop('RISK_STOP_DATE','ELIGIBILITY_END').select(pit.columns).sort('CERT','DECISION_DATE'))
        check('Every decision key and financial value match clean calendar mapping',expected_pit.equals(pit.sort('CERT','DECISION_DATE'),null_equal=True))
        del pit,expected_pit;gc.collect()
        say('[5/6] Recording financial soft checks without changing values...')
        soft=[]
        for label,a,b in [('DEPDOM exceeds DEP','DEPDOM','DEP'),('LNLSNET exceeds LNLSGR','LNLSNET','LNLSGR')]:
            eligible=pl.col(a).is_finite()&pl.col(b).is_finite()
            tol=pl.max_horizontal(pl.col(a).abs(),pl.col(b).abs())*1e-9+1e-6
            s=clean.select(eligible.sum().alias('eligible'),(eligible&(pl.col(a)>pl.col(b)+tol)).sum().alias('flagged')).row(0,named=True)
            soft.append({'check':label,'eligible_rows':s['eligible'],'flagged_rows':s['flagged'],'treatment':'Review only; no automatic correction','tolerance':'1e-6 + 1e-9 * max(abs(a),abs(b)); USD thousands'})
        for c,op in [('ASSET','nonpositive'),('DEP','nonpositive'),('LNLSGR','nonpositive'),('EQ','nonpositive')]:
            n=clean.filter(pl.col(c)<=0).height
            soft.append({'check':c+' <= 0 (candidate denominator)','eligible_rows':clean[c].len()-clean[c].null_count(),'flagged_rows':n,'treatment':'Do not divide by a nonpositive denominator; EQ sign itself is retained','tolerance':'0'})
        pl.DataFrame(soft).write_csv(out/'financial_soft_checks.csv')
        ratio_cols=['ROA','ROE','RBC1AAJ','RBCRWAJ']
        clean.group_by('REPDTE').agg(pl.len().alias('rows'),*[e for c in ratio_cols for e in [pl.col(c).null_count().alias(c+'_null'),(pl.col(c)==0).sum().alias(c+'_zero'),(pl.col(c).abs()>100).sum().alias(c+'_abs_gt_100_pct')]]).sort('REPDTE').write_csv(out/'ratio_diagnostics_by_quarter.csv')
        # Reported ratio denominators include average assets/equity and regulatory
        # amounts not present in this 33-field snapshot. These diagnostics do not
        # prove that a small denominator caused an extreme reported ratio.
        save_json(out/'preflight_summary.json',{'status':'PREFLIGHT_PASS','checks':checks,'check_count':len(checks),'full_output_parquet_bytes_read':True,'retained_value_equality_checked':True,'output_hashes':hashes,'soft_flags_are_not_errors':True,'original_vintage_PIT_verified':False,'final_labels_created':False,'python':platform.python_version(),'polars':pl.__version__,'run_time_utc':datetime.now(timezone.utc).isoformat(),'step2c_dir':str(step2c),'step2_dir':str(step2),'script_sha256':sha(Path(__file__))})
        (out/'READ_ME.txt').write_text('Existing Parquets were checked without modification or network access. PASS verifies stored bytes, schemas, keys and retained values against the existing source panel; it does not verify every number against original FDIC filings or establish historical vintages. Financial soft checks flag candidates only. Review these aggregate outputs before feature engineering. Do not interpret quarter-end EQ/ASSET as the exact average/regulatory denominator of a reported ratio.\n',encoding='utf-8')
        bundle=out/'part2_preflight_review_bundle.zip'
        with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for p in sorted(out.iterdir()):
                if p.is_file() and p!=bundle:z.write(p,p.name)
        say('[6/6] DONE - PREFLIGHT_PASS')
        say(f'SEND THIS FILE: {bundle}')
        return bundle
    except Exception as exc:
        save_json(out/'preflight_failed.json',{'status':'STOPPED','error':str(exc),'passed_checks':checks})
        raise


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--step2c-dir',type=Path);ap.add_argument('--step2-dir',type=Path);ap.add_argument('--out',type=Path)
    args=ap.parse_args()
    step2c=locate(args.step2c_dir)
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    out=(args.out or Path.home()/'BFT65B_outputs'/('step2d_preflight_'+stamp)).expanduser().resolve()
    run(step2c,out,args.step2_dir)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        say(f'STOPPED: {type(exc).__name__}: {exc}')
        say('Send this message. Existing data were not changed; do not re-download or rerun Part 2A-2C.')
        sys.exit(1)
