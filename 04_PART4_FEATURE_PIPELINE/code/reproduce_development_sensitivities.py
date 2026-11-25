"""BFT65B | Independent development-only outcome-sensitivity audit.

Recreates the audited V2 primary label from FDIC quarter keys and the Part 2
institution-event registry. Uses official Failures RESTYPE/FAILDATE/CERT data.
No final-test model files or final-test labels are read or evaluated.

Requirements: pandas, pyarrow, numpy.  Usage:
 python reproduce_development_sensitivities.py --pit panel_pit_base.parquet \
   --failures failures.parquet --registry part2_clean_review_bundle.zip --out audit_output
"""
import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path
import numpy as np
import pandas as pd

DEV_END = pd.Timestamp('2008-12-31')
GOOD_EXIT = {
    'MERGER_OR_REORGANIZATION_NONFAILURE',
    'ASSISTED_OR_RESOLUTION_EXIT',
    'VOLUNTARY_CLOSURE_NONFAILURE',
}
REGISTRY_CSV = 'review_AUDIT_ONLY/bank_event_registry_AUDIT_ONLY.csv'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def load_registry(path):
    with zipfile.ZipFile(path) as z:
        df = pd.read_csv(io.BytesIO(z.read(REGISTRY_CSV)), dtype={'CERT':'Int64'}, low_memory=False)
    required = {'CERT','FIRST_FAILURE_DATE','RISK_STOP_DATE','LAST_REPDTE','EXIT_CLASS'}
    assert required <= set(df.columns), 'Registry does not contain expected fields'
    if df['CERT'].isna().any() or df['CERT'].duplicated().any():
        raise ValueError('Registry CERT must be non-null and unique')
    for col in ['FIRST_FAILURE_DATE','RISK_STOP_DATE','LAST_REPDTE']:
        df[col] = pd.to_datetime(df[col], errors='coerce')
    return df[list(required)]


def extract_events(path):
    f = pd.read_parquet(path, columns=['CERT','FAILDATE','RESTYPE'])
    if len(f) != 4117: raise ValueError(f'Expected 4,117 FDIC transaction records, got {len(f)}')
    f['RESTYPE'] = f['RESTYPE'].astype(str).str.upper().str.strip()
    if not {'FAILURE','ASSISTANCE'} <= set(f.RESTYPE):
        raise ValueError('Unexpected RESTYPE values')
    if (f.RESTYPE == 'ASSISTANCE').sum() != 593:
        raise ValueError('Source snapshot does not contain 593 ASSISTANCE transactions')
    a = f.loc[f.RESTYPE.eq('ASSISTANCE')].copy()
    a['ASSISTANCE_DATE'] = pd.to_datetime(a['FAILDATE'], format='%m/%d/%Y', errors='raise')
    if a['ASSISTANCE_DATE'].isna().any(): raise ValueError('Null assistance event date')
    a['CERT'] = pd.to_numeric(a['CERT'], errors='coerce')
    valid = a['CERT'].notna()
    if ((a.loc[valid,'CERT'] % 1) != 0).any(): raise ValueError('Noninteger CERT in assistance events')
    without_cert = int((~valid).sum())
    a = a.loc[valid, ['CERT','ASSISTANCE_DATE']].copy()
    a['CERT'] = a['CERT'].astype('int64')
    return a.drop_duplicates(), {'total_ASSISTANCE_records':593,
        'missing_CERT_records':without_cert,
        'usable_CERT_dated_events':len(a),
        'unique_CERT':int(a.CERT.nunique())}


def derive_primary(df):
    decision = df['DECISION_DATE']
    horizon = df['HORIZON_END']
    ff = df['FIRST_FAILURE_DATE']
    stop = df['RISK_STOP_DATE']
    last = df['LAST_REPDTE']
    conflict = ff.notna() & stop.notna() & stop.lt(ff)
    postfailure = ff.notna() & ff.le(decision)
    positive = ff.notna() & ff.gt(decision) & ff.le(horizon)
    competing = stop.notna() & stop.gt(decision) & stop.le(horizon)
    covered = (stop.notna() & stop.gt(horizon)) | last.ge(horizon)
    status = np.select([conflict, postfailure, positive, competing, covered],
       ['REVIEW_DATE_CONFLICT','INVALID_POST_FAILURE','POSITIVE',
        'COMPETING_EXIT_CENSORED','NEGATIVE'],
        default='INSUFFICIENT_FOLLOWUP_CENSORED')
    status = pd.Series(status, index=df.index, dtype='string')
    good_exit = status.eq('COMPETING_EXIT_CENSORED') & df['EXIT_CLASS'].isin(GOOD_EXIT)
    y = pd.Series(pd.NA, index=df.index, dtype='Int8')
    y.loc[status.eq('NEGATIVE') | good_exit] = 0
    y.loc[status.eq('POSITIVE')] = 1
    df['LABEL_STATUS'] = status
    df['Y_PRIMARY'] = y
    return df


def attach_assistance(df, events):
    # Same historical horizon (q,q+4Q]; joining is outcome adjudication only.
    tmp = df[['CERT','DECISION_DATE','HORIZON_END']].reset_index().rename(columns={'index':'_ROW_ID'})
    candidates = tmp.merge(events, on='CERT', how='inner', validate='many_to_many')
    hits = candidates.loc[
        candidates.ASSISTANCE_DATE.gt(candidates.DECISION_DATE)
        & candidates.ASSISTANCE_DATE.le(candidates.HORIZON_END), '_ROW_ID'
    ].drop_duplicates()
    exposed = pd.Series(False,index=df.index)
    exposed.loc[hits.to_numpy(dtype=int)] = True
    y = df.Y_PRIMARY.copy()
    # A verified dated ASSISTANCE is a positive outcome only for this sensitivity.
    # Observed failure positives remain positive. The standard target is unchanged.
    y.loc[exposed] = 1
    df['ASSISTANCE_IN_HORIZON'] = exposed
    df['Y_FAILURE_ASSISTANCE_SENS'] = y
    return df


def scenario_counts(name,y,n_all):
    p=int(y.eq(1).sum()); n=int(y.eq(0).sum());u=int(y.isna().sum())
    if p+n+u != n_all: raise AssertionError(f'Count reconciliation failed for {name}')
    return {'scenario':name,'positive_bank_quarters':p,'negative_bank_quarters':n,
            'unresolved_bank_quarters':u,'labelled_bank_quarters':p+n,
            'positive_rate_pct':100*p/(p+n)}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--pit', type=Path, required=True)
    ap.add_argument('--failures', type=Path, required=True)
    ap.add_argument('--registry', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    for p in [args.pit,args.failures,args.registry]:
        if not p.is_file():raise FileNotFoundError(p)
    data=pd.read_parquet(args.pit, columns=['CERT','DECISION_DATE'])
    data['DECISION_DATE']=pd.to_datetime(data['DECISION_DATE'])
    data=data.loc[data.DECISION_DATE.le(DEV_END)].reset_index(drop=True)
    if len(data)!=1_232_375:raise ValueError('Development cohort size mismatch')
    if data[['CERT','DECISION_DATE']].duplicated().any():raise ValueError('Duplicate decision key')
    data['CERT']=data['CERT'].astype('int64')
    data['HORIZON_END']=(data.DECISION_DATE.dt.to_period('Q')+4).dt.end_time.dt.normalize()
    data=data.merge(load_registry(args.registry),on='CERT',how='left',validate='many_to_one')
    if data.EXIT_CLASS.isna().any():raise ValueError('Missing bank-event registry entry')
    data=derive_primary(data)
    assert (data.Y_PRIMARY.eq(1).sum(),data.Y_PRIMARY.eq(0).sum(),data.Y_PRIMARY.isna().sum()) == (9246,1222385,744), 'Primary V2 snapshot mismatch'
    ass, meta=extract_events(args.failures)
    data=attach_assistance(data,ass)
    assert (int(data.ASSISTANCE_IN_HORIZON.sum()),int((data.ASSISTANCE_IN_HORIZON & data.Y_PRIMARY.eq(0).fillna(False)).sum())) == (1569,1505), 'Assistance windows mismatch independent verification'
    adverse=(data.LABEL_STATUS.eq('COMPETING_EXIT_CENSORED') & data.EXIT_CLASS.eq('ADVERSE_EXIT_WITHOUT_MATCHED_FAILURE'))
    if int(adverse.sum())!=317:raise ValueError('Expected 317 adverse-exit bank-quarter observations')
    lower=data.Y_PRIMARY.copy();lower.loc[adverse]=0
    upper=data.Y_PRIMARY.copy();upper.loc[adverse]=1
    rows=[scenario_counts('primary_FAILURE_only',data.Y_PRIMARY,len(data)),
          scenario_counts('sensitivity_FAILURE_plus_ASSISTANCE',data.Y_FAILURE_ASSISTANCE_SENS,len(data)),
          scenario_counts('bound_317_adverse_as_negative',lower,len(data)),
          scenario_counts('bound_317_adverse_as_positive',upper,len(data))]
    pd.DataFrame(rows).to_csv(args.out/'outcome_sensitivity_development.csv',index=False)
    q=data.assign(decision_quarter=data.DECISION_DATE.dt.strftime('%Y-%m-%d')).groupby('decision_quarter',sort=True).agg(
      primary_positive=('Y_PRIMARY',lambda s:s.eq(1).sum()),
      assistance_exposed=('ASSISTANCE_IN_HORIZON','sum'),
      assistance_positive=('Y_FAILURE_ASSISTANCE_SENS',lambda s:s.eq(1).sum()),
    ).reset_index()
    q.to_csv(args.out/'outcome_sensitivity_by_quarter.csv',index=False)
    report={'status':'PASS','scope':'DEVELOPMENT_ONLY','input_sha256':{k:digest(v) for k,v in [('panel_pit',args.pit),('failures',args.failures),('registry',args.registry)]},
       'assistance_source':meta,'scenarios':rows,'event_exposures':{'development_exposed':int(data.ASSISTANCE_IN_HORIZON.sum()),
        'negative_to_positive':int((data.ASSISTANCE_IN_HORIZON & data.Y_PRIMARY.eq(0).fillna(False)).sum()),
        'unresolved_to_positive':int((data.ASSISTANCE_IN_HORIZON & data.Y_PRIMARY.isna()).sum()),
        'distinct_assistance_exposed_cert':int(data.loc[data.ASSISTANCE_IN_HORIZON,'CERT'].nunique())},
       'notes':['Outcome sensitivity only; no model fitted and no final-test labels evaluated.',
       'ASSISTANCE dates come from FDIC RESTYPE=ASSISTANCE and FAILDATE; source records without CERT are excluded from the matched experiment.',
       'Adverse 0/1 scenarios are observation-level bounding cases, not verified new failure events.']}
    (args.out/'outcome_sensitivity_development_audit.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps({'status':'PASS','scenarios':rows,'assistance':meta},indent=2))

if __name__=='__main__':main()
