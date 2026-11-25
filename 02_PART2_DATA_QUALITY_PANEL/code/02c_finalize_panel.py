#!/usr/bin/env python3
"""BFT65B Part 2C: scope, exits, clean panel and calendar-timed decision base.

Run: python 02c_finalize_panel.py
Keep 02b_collect_exit_evidence.py in the same directory. Requires the existing
Polars environment and the completed step 2A/2B outputs. A small, cached FDIC
query checks insurance-scope exceptions across the full acquisition period.
Original Financials, panel_base and earlier evidence are never modified.

No imputation, winsorisation, scaling, model fitting or final labels are applied.
Latest-vintage financials plus an availability lag are not original-vintage PIT.
Sources: course final_report_bft65b.pdf; https://api.fdic.gov/banks/docs/;
https://docs.pola.rs/api/python/stable/;
https://cdr.ffiec.gov/Public/HelpFiles/WelcomeAdditionalInfo.htm.
AI assistance: ChatGPT, 9 November 2026. Disclose in report and README.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import shutil
import sys
import time
import zipfile

try:
    import polars as pl
except ImportError:
    raise SystemExit('Use the Python environment that ran step 2A; Polars is required.')

VERSION = '1.0'
PART2B_SHA = '9935d369667b4b5ff17dc5853bc81ccc7ee0af9f87792d2fb62f30c9f021f3ec'
START = date(1984, 3, 31)
END = date(2026, 6, 30)
MODEL_END = date(2025, 6, 30)
TERMINAL = {211, 213, 215, 216, 217, 221, 222, 223, 224, 230, 235, 240, 260}
MERGER = {221, 222, 223, 224}
ADVERSE = {211, 215, 230, 235, 260}
RESOLUTION = {213, 216, 217}
FORBIDDEN = {'FAILDATE', 'RESTYPE', 'COST', 'ACTIVE', 'ENDEFYMD', 'CHANGEC1',
             'RISK_STOP_DATE', 'FIRST_FAILURE_DATE', 'EXIT_CLASS', 'EXIT_DATE',
             'QBFASSET', 'QBFDEP', 'INSFDIC', 'INSAGNT1', 'BKCLASS', 'ACTEVT'}


def say(s):
    print(s, flush=True)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def helper():
    p = Path(__file__).with_name('02b_collect_exit_evidence.py')
    require(p.is_file(), 'Place 02b_collect_exit_evidence.py beside this script; no need to rerun 2B.')
    require(sha(p) == PART2B_SHA, 'The 2B helper differs from the reviewed version. Keep files and send this message.')
    spec = importlib.util.spec_from_file_location('bft65b_2b', p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = helper()


def parse_date(value):
    text = B.day(value)
    if text and not text.startswith('9999'):
        return date.fromisoformat(text)
    return None


def iso(value):
    return value.isoformat() if value else None


def exit_class(codes):
    if codes and codes <= MERGER:
        return 'MERGER_OR_REORGANIZATION_NONFAILURE'
    if codes == {240}:
        return 'VOLUNTARY_CLOSURE_NONFAILURE'
    if codes & ADVERSE:
        return 'ADVERSE_EXIT_WITHOUT_MATCHED_FAILURE'
    if codes and codes <= RESOLUTION:
        return 'ASSISTED_OR_RESOLUTION_EXIT'
    return 'UNRESOLVED_EXIT_TYPE'


def build_registry(coverage, history, failures):
    """Future event data are restricted to outcome/eligibility audit tables.

    Only institution-level terminal change codes define an exit. In particular,
    810 is the acquirer's participation record and 225 is a partial transaction.
    Neither ends a bank's risk spell. The first register FAILURE ends its spell;
    later resolutions/failures are retained as evidence, never a fresh episode.
    """
    by_history, by_failure = defaultdict(list), defaultdict(list)
    used_events = []
    for r in history:
        code = B.integer(r.get('CHANGECODE'))
        if code not in TERMINAL or r.get('ORG_ROLE_CDE', '').upper() != 'FI':
            continue
        owner, outgoing = B.positive_cert(r.get('CERT')), B.positive_cert(r.get('OUT_CERT'))
        require(not (owner and outgoing and owner != outgoing),
                'Terminal history record has inconsistent institution roles: '+str(r.get('API_ID')))
        cert = outgoing or owner
        dt = parse_date(r.get('EFFDATE'))
        require(cert and dt, 'Terminal history has no valid subject/date.')
        e = {'CERT': cert, 'EVENT_DATE': dt, 'CODE': code, 'API_ID': r['API_ID'],
             'DESCRIPTION': r.get('CHANGECODE_DESC', '')}
        by_history[cert].append(e)
        used_events.append({**e, 'EVENT_DATE': iso(dt)})
    for r in failures:
        require(r.get('RESTYPE') == 'FAILURE', 'Failure coverage contains a non-FAILURE record.')
        cert, dt = B.positive_cert(r.get('CERT')), parse_date(r.get('FAILDATE'))
        require(cert and dt, 'Invalid linked failure record.')
        by_failure[cert].append(dt)
    result = []
    for bank in coverage:
        cert = B.positive_cert(bank['CERT'])
        first, last = parse_date(bank['FIRST_REPDTE']), parse_date(bank['LAST_REPDTE'])
        require(cert and first and last, 'Invalid bank coverage key/dates.')
        events = by_history[cert]
        dates = sorted({e['EVENT_DATE'] for e in events})
        fd = sorted(set(by_failure[cert]))
        faildate = fd[0] if fd else None
        snapshot = parse_date(bank.get('SNAPSHOT_ENDEFYMD'))
        snapshot_code = B.integer(bank.get('SNAPSHOT_CHANGEC1'))
        inactive = B.integer(bank.get('SNAPSHOT_ACTIVE')) == 0
        history_date = dates[0] if dates else None
        codes = {e['CODE'] for e in events if e['EVENT_DATE'] == history_date}
        flags = []
        exitdate, riskstop = None, None
        if faildate:
            kind, source = 'FIRST_REGISTER_FAILURE', 'FAILURES_RESTYPE_FAILURE'
            exitdate = faildate
            riskstop = min(faildate, history_date) if history_date else faildate
            if history_date and history_date < faildate:
                flags.append('HISTORY_EARLIER_THAN_REGISTER_FAILURE')
            if len(fd) > 1:
                flags.append('FIRST_FAILURE_POLICY_MULTIPLE_REGISTER_EVENTS')
        elif history_date:
            kind, source = exit_class(codes), 'HISTORY_TERMINAL_EVENT'
            exitdate = riskstop = history_date
            if len(dates) > 1:
                flags.append('MULTIPLE_TERMINAL_DATES_FIRST_USED')
            if B.integer(bank.get('SNAPSHOT_ACTIVE')) == 1:
                flags.append('TERMINAL_HISTORY_CONFLICTS_WITH_CURRENT_ACTIVE')
        elif inactive and snapshot_code in TERMINAL and snapshot and first < snapshot <= END:
            # A reason-coded, finite date is a fallback outcome source, not a
            # historical predictor. Missing history is recorded explicitly.
            kind, source = exit_class({snapshot_code}), 'INSTITUTIONS_REASON_CODED_FALLBACK'
            exitdate = riskstop = snapshot
            codes = {snapshot_code}
            flags.append('NO_MATCHED_TERMINAL_HISTORY_FALLBACK_USED')
        elif B.integer(bank.get('SNAPSHOT_ACTIVE')) == 1:
            kind, source = 'NO_REGISTERED_EXIT_AT_SNAPSHOT', 'CURRENT_STATUS_OUTCOME_AUDIT_ONLY'
        else:
            kind, source = 'UNRESOLVED_OR_UNOBSERVED_EXIT', 'LAST_REPORT_IS_CENSORING_BOUND_NOT_EXIT'
            flags.append('DO_NOT_ASSUME_NEGATIVE_LABEL_AFTER_LAST_REPORT')
        if source == 'HISTORY_TERMINAL_EVENT' and snapshot and snapshot != exitdate:
            flags.append('HISTORY_OVERRIDES_SNAPSHOT_END_DATE')
        if riskstop and first >= riskstop:
            flags.append('NO_OBSERVED_REPORT_BEFORE_RISK_STOP')
        if kind == 'NO_REGISTERED_EXIT_AT_SNAPSHOT':
            eligibility_end = END
        elif riskstop:
            eligibility_end = min(riskstop, END)
        else:
            eligibility_end = last
        result.append({'CERT': cert, 'FIRST_REPDTE': iso(first), 'LAST_REPDTE': iso(last),
                       'OBSERVED_QUARTERS': int(bank['OBSERVED_QUARTERS']),
                       'EXIT_CLASS': kind, 'EXIT_SOURCE': source,
                       'EXIT_DATE': iso(exitdate), 'RISK_STOP_DATE': iso(riskstop),
                       'FIRST_FAILURE_DATE': iso(faildate), 'REGISTER_FAILURE_EVENTS': len(fd),
                       'ALL_REGISTER_FAILURE_DATES': '|'.join(map(iso, fd)),
                       'HISTORY_TERMINAL_DATES': '|'.join(map(iso, dates)),
                       'HISTORY_TERMINAL_CODES': '|'.join(map(str, sorted(codes))),
                       'SNAPSHOT_ENDEFYMD': iso(snapshot),
                       'SNAPSHOT_ACTIVE': B.integer(bank.get('SNAPSHOT_ACTIVE')),
                       'ELIGIBILITY_END': iso(eligibility_end),
                       'UNRESOLVED_EXIT': riskstop is None and kind != 'NO_REGISTERED_EXIT_AT_SNAPSHOT',
                       'REVIEW_FLAGS': '|'.join(flags)})
    return result, used_events


def registry_frame(records):
    df = pl.DataFrame(records, infer_schema_length=None)
    dates = ['FIRST_REPDTE','LAST_REPDTE','EXIT_DATE','RISK_STOP_DATE',
             'FIRST_FAILURE_DATE','SNAPSHOT_ENDEFYMD','ELIGIBILITY_END']
    return df.with_columns(pl.col('CERT').cast(pl.Int64),
                           *[pl.col(c).cast(pl.String).str.to_date('%Y-%m-%d', strict=True) for c in dates])


def scope_frame(records):
    rows = []
    for r in records:
        cert, dt = B.positive_cert(r.get('CERT')), parse_date(r.get('REPDTE'))
        require(cert and dt, 'Scope query contains an invalid bank-quarter key.')
        insured = B.integer(r.get('INSFDIC'))
        agent = str(r.get('INSAGNT1') or '').strip().upper()
        klass = str(r.get('BKCLASS') or '').strip().upper()
        require(insured != 1, 'Negative insurance-scope query returned INSFDIC=1.')
        # Evidence must agree; unknown or contradictory flags are kept for review.
        excluded = insured == 0 and agent == 'NONE' and klass == 'NC'
        rows.append({'CERT':cert,'REPDTE':dt,'CONFIRMED_UNINSURED_NC':excluded,
                     'INSFDIC_OBSERVED':insured,'INSAGNT1_OBSERVED':agent,
                     'BKCLASS_OBSERVED':klass,'API_ID':str(r['ID'])})
    df = pl.DataFrame(rows, schema={'CERT':pl.Int64,'REPDTE':pl.Date,
           'CONFIRMED_UNINSURED_NC':pl.Boolean,'INSFDIC_OBSERVED':pl.Int64,
           'INSAGNT1_OBSERVED':pl.String,'BKCLASS_OBSERVED':pl.String,'API_ID':pl.String})
    require(df.select('CERT','REPDTE').unique().height == df.height, 'Duplicate scope-exception keys.')
    return df


def row_decisions(keys, registry, scope):
    r = keys.join(registry.select('CERT','RISK_STOP_DATE','FIRST_FAILURE_DATE','EXIT_CLASS'),
                  on='CERT', how='left', validate='m:1')
    r = r.join(scope.select('CERT','REPDTE','CONFIRMED_UNINSURED_NC'),
               on=['CERT','REPDTE'], how='left', validate='1:1')
    r = r.with_columns(pl.col('CONFIRMED_UNINSURED_NC').fill_null(False),
        (pl.col('RISK_STOP_DATE').is_not_null() & (pl.col('REPDTE') >= pl.col('RISK_STOP_DATE'))).fill_null(False).alias('AT_OR_AFTER_RISK_STOP'))
    return r.with_columns(
        pl.when(pl.col('CONFIRMED_UNINSURED_NC')).then(pl.lit('CONFIRMED_UNINSURED_NC'))
        .when(pl.col('AT_OR_AFTER_RISK_STOP') & pl.col('FIRST_FAILURE_DATE').is_not_null())
        .then(pl.lit('AT_OR_AFTER_FAILURE_RISK_STOP'))
        .when(pl.col('AT_OR_AFTER_RISK_STOP')).then(pl.lit('AT_OR_AFTER_OTHER_EXIT'))
        .otherwise(pl.lit('RETAIN')).alias('ROW_ACTION'))


def decision_base(clean, registry, lag):
    require(lag in {1, 2}, 'Supported availability lag: one or two calendar quarters.')
    p = clean.rename({'REPDTE':'SOURCE_REPDTE'}).with_columns(
        pl.col('SOURCE_REPDTE').dt.offset_by(f'{3*lag}mo').dt.month_end().alias('DECISION_DATE'))
    p = p.join(registry.select('CERT','RISK_STOP_DATE','ELIGIBILITY_END'),
               on='CERT', how='left', validate='m:1')
    p = p.filter((pl.col('DECISION_DATE') <= pl.lit(MODEL_END)) &
                 (pl.col('DECISION_DATE') <= pl.col('ELIGIBILITY_END')) &
                 (pl.col('RISK_STOP_DATE').is_null() | (pl.col('DECISION_DATE') < pl.col('RISK_STOP_DATE'))))
    return p.drop('RISK_STOP_DATE','ELIGIBILITY_END').sort('CERT','DECISION_DATE')


def numeric_profiles(df):
    cols = [c for c,t in df.schema.items() if t.is_numeric() and c != 'CERT']
    exprs = []
    for i,c in enumerate(cols):
        v = pl.col(c)
        for name,e in [('null',v.is_null().sum()),('nonfinite',(~v.is_finite()).sum()),
                       ('negative',(v<0).sum()),('zero',(v==0).sum()),
                       ('min',v.min()),('q01',v.quantile(.01)),('median',v.median()),
                       ('q99',v.quantile(.99)),('max',v.max())]:
            exprs.append(e.alias(f'{i}_{name}'))
    values = df.select(exprs).row(0,named=True)
    return [{'column':c,'rows':df.height,**{name:values[f'{i}_{name}']
            for name in ['null','nonfinite','negative','zero','min','q01','median','q99','max']}}
            for i,c in enumerate(cols)]


def find_step2b(explicit):
    if explicit:
        return explicit.expanduser().resolve()
    candidates = set()
    for root in [Path.home()/'BFT65B_outputs', Path(__file__).parent/'BFT65B_outputs']:
        if root.is_dir():
            candidates.update(p for p in root.glob('step2b_*') if (p/'STEP2B_COMPLETE.json').is_file())
    require(candidates, 'Cannot find completed step 2B. Use --step2b-dir PATH; do not redownload Financials.')
    return max(candidates,key=lambda p:(p/'STEP2B_COMPLETE.json').stat().st_mtime).resolve()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--step2b-dir', type=Path)
    parser.add_argument('--step2-dir', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--cache-dir', type=Path, default=None,
                        help='Read-only existing request cache; requires --offline and a separate output directory.')
    args = parser.parse_args()
    read_only_cache = None
    if args.cache_dir is not None:
        require(args.offline, '--cache-dir requires --offline; network fallback is forbidden.')
        read_only_cache = args.cache_dir.expanduser().resolve()
        require(read_only_cache.is_dir(), 'Existing read-only request cache directory is missing.')
    started = time.perf_counter()
    step2b = find_step2b(args.step2b_dir)
    summary_b = B.read_json(step2b/'step2b_summary.json')
    require(summary_b['status']=='EXIT_EVIDENCE_READY_FOR_REVIEW','Step 2B did not finish.')
    require(summary_b['script_sha256']==PART2B_SHA,'Unexpected step 2B producer version.')
    require(summary_b['supplemental_count_or_date_bound_mismatches']==0,'Resolve metadata coverage mismatches first.')
    require(sha(step2b/'part2_review_bundle.zip')==B.read_json(step2b/'STEP2B_COMPLETE.json')['bundle_sha256'],
            'Completed step 2B bundle changed.')
    step2 = (args.step2_dir or Path(summary_b['step2_dir'])).expanduser().resolve()
    panel_path = step2/'panel_base.parquet'
    summary_a = B.read_json(step2/'step2_summary.json')
    require(summary_a['quarters']==170 and summary_a['rows_input']==summary_a['rows_output'], 'Need full step 2A.')
    require(summary_a['panel_sha256']==summary_b['source_panel_sha256_recorded_in_step2A'], 'Step 2A and 2B refer to different panels.')
    say('[1/6] Verifying inputs and the existing panel checksum...')
    require(sha(panel_path)==summary_a['panel_sha256'], 'panel_base differs from the reviewed step 2A file.')
    config_b = B.read_json(step2b/'step2b_config.json')
    require(B.input_signature(step2)==config_b['source_sha256'], 'Step 2A review inputs changed.')
    review_b = step2b/'review_AUDIT_ONLY'
    for name in B.REQUIRED_REPORTS:
        require(sha(review_b/('step2A_'+name))==config_b['source_sha256'][name], 'Copied step 2A evidence changed: '+name)
    # Verify all members actually consumed from the completed 2B ZIP.
    with zipfile.ZipFile(step2b/'part2_review_bundle.zip') as z:
        for name in ['review_AUDIT_ONLY/history_events_AUDIT_ONLY.csv',
                     'review_AUDIT_ONLY/bank_exit_evidence_AUDIT_ONLY.csv','sources_manifest.json']:
            require(hashlib.sha256(z.read(name)).hexdigest()==sha(step2b/name), 'Step 2B evidence changed: '+name)
    signature = {str(p.relative_to(step2b)):sha(p) for p in
                 [step2b/'step2b_summary.json',step2b/'sources_manifest.json',
                  review_b/'history_events_AUDIT_ONLY.csv',
                  review_b/'bank_exit_evidence_AUDIT_ONLY.csv',step2b/'part2_review_bundle.zip']}
    out = (args.out or Path.home()/'BFT65B_outputs'/('step2c_'+step2b.name.removeprefix('step2b_'))).expanduser().resolve()
    require(all(not out.is_relative_to(p) and not p.is_relative_to(out) for p in [step2,step2b]), 'Output must be separate from input folders.')
    if read_only_cache is not None:
        require(not out.is_relative_to(read_only_cache) and not read_only_cache.is_relative_to(out),
                'Output and existing read-only cache must be separate.')
    out.mkdir(parents=True,exist_ok=True)
    config = {'version':VERSION,'script_sha256':sha(Path(__file__)),'step2_dir':str(step2),
              'step2b_dir':str(step2b),'panel_sha256':summary_a['panel_sha256'],'step2b_inputs':signature}
    if read_only_cache is not None:
        config['read_only_cache_dir'] = str(read_only_cache)
    if (out/'step2c_config.json').is_file():
        require(B.read_json(out/'step2c_config.json')==config,'Inputs/script changed. Choose a new --out directory.')
    else:
        require(not any(out.iterdir()),'Output directory is not empty.')
        B.save_json(out/'step2c_config.json',config)
    bundle = out/'part2_clean_review_bundle.zip'
    if (out/'STEP2C_COMPLETE.json').is_file():
        old = B.read_json(out/'STEP2C_COMPLETE.json')
        require(all((out/n).is_file() and sha(out/n)==v for n,v in old['output_sha256'].items()),'Completed step 2C output changed.')
        say('DONE - CLEAN_PANEL_READY_FOR_REVIEW (already completed)')
        say(f'SEND THIS FILE: {bundle}')
        return 0
    audit = out/'review_AUDIT_ONLY';audit.mkdir(exist_ok=True)
    collector = B.Collector(out,offline=args.offline)
    if read_only_cache is not None:
        # Collector.get verifies URL/body SHA and never writes a cached hit.
        # The required offline mode rejects every miss without network fallback.
        collector.cache = read_only_cache
    indexes = B.read_json(step2b/'sources_manifest.json')['api_indexes']
    collector.indexes['financials'] = json.dumps(indexes['financials'],sort_keys=True)
    say('[2/6] Checking insurance-scope exceptions across all 170 quarters (cached API)...')
    _, total = collector.api('financials','REPDTE:[19840331 TO 20260630]',['CERT','REPDTE'])
    require(total==summary_a['rows_output'],'Current Financials API scope differs from the input snapshot.')
    scope_raw = collector.complete('financials','REPDTE:[19840331 TO 20260630] AND NOT INSFDIC:1',
             ['CERT','REPDTE','INSFDIC','BKCLASS','INSAGNT1'],'Insurance-scope exceptions')
    scope = scope_frame(scope_raw)
    scope.write_csv(audit/'insurance_scope_exceptions.csv',include_bom=True)
    B.save_json(out/'scope_sources_manifest.json',{'requests':collector.records,'indexes':indexes,
                  'full_scope_api_total':total,'negative_scope_api_rows':len(scope_raw),
                  'filter':'REPDTE:[19840331 TO 20260630] AND NOT INSFDIC:1'})
    B.write_csv(audit/'scope_api_checks.csv',collector.query_checks)

    say('[3/6] Resolving event roles, first failures and other exits...')
    coverage = B.read_csv(review_b/'step2A_bank_coverage_AUDIT_ONLY.csv')
    history = B.read_csv(review_b/'history_events_AUDIT_ONLY.csv')
    failures = B.read_csv(review_b/'step2A_failure_event_coverage.csv')
    records, terminal_events = build_registry(coverage,history,failures)
    registry = registry_frame(records)
    require(registry.height==summary_a['banks'] and registry['CERT'].n_unique()==registry.height,'Registry must be one row per bank.')
    registry.write_csv(audit/'bank_event_registry_AUDIT_ONLY.csv',include_bom=True)
    B.write_csv(audit/'terminal_history_used.csv',terminal_events)
    registry.filter(pl.col('REVIEW_FLAGS')!='').write_csv(audit/'registry_review_flags.csv',include_bom=True)
    registry.group_by('EXIT_CLASS','EXIT_SOURCE').agg(pl.len().alias('banks')).sort('EXIT_CLASS','EXIT_SOURCE').write_csv(audit/'exit_class_counts.csv',include_bom=True)
    multiple_before = B.read_csv(review_b/'bank_exit_evidence_AUDIT_ONLY.csv')
    paired = {int(r['CERT']) for r in multiple_before if r['REVIEW_GROUP_2B']=='REVIEW_MULTIPLE_EVENT_CODES_AT_INACTIVE_DATE'}
    registry.filter(pl.col('CERT').is_in(sorted(paired))).select('CERT','EXIT_CLASS','EXIT_SOURCE','EXIT_DATE','REVIEW_FLAGS').write_csv(audit/'multiple_code_flags_reinterpreted.csv',include_bom=True)

    say('[4/6] Applying documented row exclusions and creating clean Financials...')
    source = pl.read_parquet(panel_path)
    require(source.height==summary_a['rows_output'] and source['CERT'].n_unique()==summary_a['banks'], 'Input panel count mismatch.')
    require(source.schema['CERT']==pl.Int64 and source.schema['REPDTE']==pl.Date,'Unexpected panel key schema.')
    require(not FORBIDDEN.intersection(source.columns),'Current/event metadata leaked into Financials.')
    require(source['CERT'].null_count()==0 and source['REPDTE'].null_count()==0,'Null panel keys.')
    keys = source.select('CERT','REPDTE')
    require(keys.unique().height==keys.height,'Duplicate source keys; no automatic deduplication.')
    require(keys['REPDTE'].n_unique()==170 and keys['REPDTE'].min()==START and keys['REPDTE'].max()==END,'Unexpected quarter scope.')
    require(scope.select('CERT','REPDTE').join(keys,on=['CERT','REPDTE'],how='anti').height==0,'Scope exceptions not found in the saved panel.')
    decisions = row_decisions(keys,registry,scope)
    excluded = decisions.filter(pl.col('ROW_ACTION')!='RETAIN')
    excluded.write_csv(audit/'excluded_rows_AUDIT_ONLY.csv',include_bom=True)
    actions = decisions.group_by('ROW_ACTION').agg(pl.len().alias('rows')).sort('ROW_ACTION')
    actions.write_csv(audit/'row_accounting.csv',include_bom=True)
    retained_keys = decisions.filter(pl.col('ROW_ACTION')=='RETAIN').select('CERT','REPDTE')
    clean = source.join(retained_keys,on=['CERT','REPDTE'],how='semi').sort('CERT','REPDTE')
    require(source.height==clean.height+excluded.height,'Row conservation failed.')
    require(clean.columns==source.columns and clean.schema==source.schema,'Unexpected financial schema change.')
    require(clean.select('CERT','REPDTE').join(excluded.select('CERT','REPDTE'),on=['CERT','REPDTE'],how='inner').height==0,'Retained/excluded keys overlap.')
    clean.write_parquet(out/'panel_clean.parquet',compression='zstd',row_group_size=100_000)
    profiles = numeric_profiles(clean)
    require(all(r['nonfinite']==0 for r in profiles),'Non-finite values remain in clean input; resolve the step 2A mismatch.')
    B.write_csv(audit/'numeric_profile_after.csv',profiles)
    numeric = [r['column'] for r in profiles]
    clean.group_by('REPDTE').agg(pl.len().alias('rows'),*[pl.col(c).null_count().alias(c) for c in numeric]).sort('REPDTE').write_csv(audit/'missingness_after_by_quarter.csv',include_bom=True)
    decisions.group_by('REPDTE','ROW_ACTION').agg(pl.len().alias('rows')).sort('REPDTE','ROW_ACTION').write_csv(audit/'row_accounting_by_quarter.csv',include_bom=True)
    # These sign checks are review flags, not automatic claims of error. Keep
    # negative income/equity/net charge-offs and do not fit full-sample thresholds.
    stock_review = [c for c in ['CHBAL','SC','LNLSGR','LNLSNET','LNRE','LNCI','LNCON','LNATRES','NCLNLS','NAASSET','ORE'] if c in clean.columns]
    sign_frames = [clean.filter(pl.col(c)<0).select('CERT','REPDTE',pl.lit(c).alias('column'),pl.col(c).cast(pl.Float64).alias('value')) for c in stock_review]
    if sign_frames:
        pl.concat(sign_frames).write_csv(audit/'negative_stock_values_REVIEW.csv',include_bom=True)
    observations = clean.group_by('CERT').agg(pl.col('REPDTE').min().alias('first'),pl.col('REPDTE').max().alias('last'),pl.len().alias('observed'))
    observations = observations.with_columns(((pl.col('last').dt.year()-pl.col('first').dt.year())*4+
                            pl.col('last').dt.quarter().cast(pl.Int32)-pl.col('first').dt.quarter().cast(pl.Int32)+1-pl.col('observed')).alias('internal_missing_quarters'))
    observations.filter(pl.col('internal_missing_quarters')>0).write_csv(audit/'internal_gaps_after.csv',include_bom=True)

    say('[5/6] Creating the decision base with an exact one-calendar-quarter lag...')
    pit = decision_base(clean,registry,1)
    require(pit.height>0 and pit.select('CERT','DECISION_DATE').unique().height==pit.height,'Invalid decision keys.')
    require(not FORBIDDEN.intersection(pit.columns),'Outcome/current metadata leaked into decision base.')
    require(pit.filter(pl.col('DECISION_DATE')!=pl.col('SOURCE_REPDTE').dt.offset_by('3mo').dt.month_end()).height==0,'Calendar timing violation.')
    require(pit.filter(pl.col('SOURCE_REPDTE')>=pl.col('DECISION_DATE')).height==0,'Source report does not precede decision.')
    pit.write_parquet(out/'panel_pit_base.parquet',compression='zstd',row_group_size=100_000)
    pit.group_by('DECISION_DATE').agg(pl.len().alias('rows')).sort('DECISION_DATE').write_csv(audit/'decision_rows_by_quarter.csv',include_bom=True)
    sensitivity = decision_base(clean.select('CERT','REPDTE'),registry,2)
    B.write_csv(audit/'availability_lag_sensitivity_counts.csv',[
        {'lag_calendar_quarters':1,'rows':pit.height,'banks':pit['CERT'].n_unique()},
        {'lag_calendar_quarters':2,'rows':sensitivity.height,'banks':sensitivity['CERT'].n_unique()}])
    potential = pit.select('CERT','DECISION_DATE').join(registry.select('CERT','FIRST_FAILURE_DATE'),on='CERT',how='left',validate='m:1')
    potential = potential.filter((pl.col('FIRST_FAILURE_DATE')>pl.col('DECISION_DATE')) &
                  (pl.col('FIRST_FAILURE_DATE')<=pl.col('DECISION_DATE').dt.offset_by('1y').dt.month_end()))
    potential.group_by('CERT','FIRST_FAILURE_DATE').agg(pl.len().alias('eligible_decisions_in_positive_window')).sort('FIRST_FAILURE_DATE','CERT').write_csv(audit/'first_failure_positive_window_coverage_AUDIT_ONLY.csv',include_bom=True)
    # This is a coverage diagnostic only. Negative labels and competing-event
    # censoring are deliberately deferred to the dedicated feature/label stage.
    timing = {
        'reporting_period':'SOURCE_REPDTE', 'decision_time':'DECISION_DATE',
        'baseline_lag_calendar_quarters':1,'sensitivity_lag_calendar_quarters':2,
        'decision_max':MODEL_END.isoformat(),'label_window_for_next_stage':'(q, q + 4 calendar quarters]',
        'availability_is_assumption':True,'original_historical_vintages_available':False,
        'current_and_future_metadata_excluded_from_predictors':True,
        'negative_labels_created':False,'competing_exit_label_policy_finalized':False,
        'missing_quarter_policy':'Never fill or substitute the previous observed row for a missing calendar quarter.',
        'unknown_exit_policy':'Censor at last observed report; this is not an asserted exit date.',
        'first_failure_policy':'First RESTYPE=FAILURE per CERT ends the risk spell; no re-entry.'}
    B.save_json(out/'timing_contract.json',timing)
    actions_text = '''# Part 2C decision log

This stage implements a first-failure risk set for the course's insured-bank
early-warning task. The acquired files remain unchanged and retain all banks.

1. Exclude a report from the analytical panel only when the full-scope exception
   query confirms INSFDIC=0, INSAGNT1=NONE and BKCLASS=NC, or the report date is
   on/after an evidenced risk stop. Insurance scope uses the report's own quarter.
   Missing Institutions links alone never trigger deletion. Negative-scope rows
   with unknown/contradictory insurance metadata remain flagged, not excluded.
2. Use the first dated RESTYPE=FAILURE event per CERT as the target event. Keep
   subsequent events in the registry but do not create post-first-failure spells.
   Where terminal History predates that event, use the earlier date for risk-set
   eligibility and preserve the register date as the target. Report disagreements.
3. Only the specified institution-level terminal History codes end a spell.
   Code 810 records acquirer participation; 225 describes a partial transaction.
   The departing bank's own event and the acquirer's participation are not two
   contradictory exits. Never transfer a predecessor's failure to its acquirer.
4. Prefer terminal History dates to snapshot ENDEFYMD. Without terminal History,
   a finite reason-coded Institutions date is an explicitly flagged fallback.
   No date is invented from the disappearance of a bank from Financials.
5. Preserve unresolved exit reasons. Assisted/resolution or history-only adverse
   events are not automatically labelled failure. Their horizons need an explicit
   censoring/competing-event rule at the label stage; unknown is never healthy.
6. Retain nulls, zeros and finite negative values. Negative income/equity/net
   charge-offs can contain risk information. Questionable stock signs are listed
   for review because aggregate data do not establish that every sign is an error.
   Full-sample quantiles describe data only; no winsorisation thresholds are fitted.
   Imputation, scaling and any clipping must be fitted on training data later.
7. P3ASSET's historical structural missingness is preserved. Do not convert it to
   zero or discard the pre-2001 sample solely because this field is unavailable.
8. Build decisions from the exact prior calendar quarter, not a row-based shift.
   No forward-filled artificial bank reports are created. Decisions stop at 2025Q2.
   A two-quarter-lag count sensitivity is supplied, not a model-performance test.
9. One-quarter availability is an explicit assumption. REPDTE is a period end,
   not a release date. Latest-vintage revised FDIC data cannot establish original
   historical availability; report this residual limitation rather than claiming
   complete vintage-level point-in-time correctness.

Files containing event dates, current status or future evidence are AUDIT_ONLY.
Only panel_pit_base contains timed financial inputs, with no final label column.
Before modelling: define negative labels/censoring, verify item definitions and
YTD conversions, implement features, and fix temporal development/test splits.

Sources: course final_report_bft65b.pdf; https://api.fdic.gov/banks/docs/;
https://cdr.ffiec.gov/Public/HelpFiles/WelcomeAdditionalInfo.htm;
https://docs.pola.rs/api/python/stable/.
AI assistance: ChatGPT, 9 November 2026.
'''
    B.atomic_bytes(out/'PART2_DECISION_LOG.md',actions_text.encode('utf-8'))
    for name in ['step2A_numeric_profile.csv','step2A_column_availability.csv','step2A_text_cleanup.csv','step2A_multiple_failure_events.csv']:
        shutil.copy2(review_b/name,audit/name)
    say('[6/6] Checking row accounting and packaging review evidence...')
    require(sha(panel_path)==summary_a['panel_sha256'] and B.input_signature(step2)==config_b['source_sha256'],'Source inputs changed during the run.')
    require(all(sha(step2b/n)==v for n,v in signature.items()),'Step 2B evidence changed during the run.')
    file_hashes = {n:sha(out/n) for n in ['panel_clean.parquet','panel_pit_base.parquet']}
    result = {'status':'CLEAN_PANEL_READY_FOR_REVIEW','version':VERSION,
       'run_time_utc':datetime.now(timezone.utc).isoformat(),'python':platform.python_version(),'polars':pl.__version__,
       'source_rows':source.height,'clean_rows':clean.height,'excluded_rows':excluded.height,
       'source_banks':source['CERT'].n_unique(),'clean_banks':clean['CERT'].n_unique(),
       'clean_quarters':clean['REPDTE'].n_unique(),'row_accounting':actions.to_dicts(),
       'scope_exception_rows':scope.height,'confirmed_uninsured_rows':scope.filter(pl.col('CONFIRMED_UNINSURED_NC')).height,
       'scope_exceptions_needing_review':scope.filter(~pl.col('CONFIRMED_UNINSURED_NC')).height,
       'overlapping_uninsured_and_post_exit_rows':decisions.filter(pl.col('CONFIRMED_UNINSURED_NC')&pl.col('AT_OR_AFTER_RISK_STOP')).height,
       'registry_banks':registry.height,'exit_classes':dict(Counter(r['EXIT_CLASS'] for r in records)),
       'registry_fallback_banks':sum(r['EXIT_SOURCE']=='INSTITUTIONS_REASON_CODED_FALLBACK' for r in records),
       'registry_unknown_exit_banks':sum(r['UNRESOLVED_EXIT'] for r in records),
       'step2b_multiple_code_review_banks':len(paired),
       'decision_rows_lag1':pit.height,'decision_banks_lag1':pit['CERT'].n_unique(),
       'decision_start':iso(pit['DECISION_DATE'].min()),'decision_end':iso(pit['DECISION_DATE'].max()),
       'decision_rows_lag2':sensitivity.height,
       'first_failure_events_with_eligible_positive_window':potential['CERT'].n_unique(),
       'financial_values_imputed':0,'financial_values_clipped':0,'finite_values_changed':0,
       'input_checksums_unchanged':True,'output_sha256':file_hashes,
       'final_labels_created':False,'model_ready':False,
       'availability_lag_is_assumption':True,'original_vintage_PIT_verified':False,
       'elapsed_seconds':time.perf_counter()-started}
    B.save_json(out/'step2c_summary.json',result)
    with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(audit.glob('*.csv')):
            z.write(p,p.relative_to(out))
        for name in ['step2c_summary.json','step2c_config.json','scope_sources_manifest.json','timing_contract.json','PART2_DECISION_LOG.md']:
            z.write(out/name,name)
    file_hashes['part2_clean_review_bundle.zip'] = sha(bundle)
    B.save_json(out/'STEP2C_COMPLETE.json',{'status':result['status'],'output_sha256':file_hashes})
    say('DONE - CLEAN_PANEL_READY_FOR_REVIEW')
    say(f'Input rows: {source.height:,}; clean rows: {clean.height:,}; excluded: {excluded.height:,}')
    say(f'Decision base: {pit.height:,} rows; lag: 1 calendar quarter; final labels not created.')
    say(f'SEND THIS FILE: {bundle}')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        say('Stopped. Run the same command to reuse completed cached requests.')
        raise SystemExit(1)
    except Exception as exc:
        say(f'STOPPED: {type(exc).__name__}: {exc}')
        say('Keep inputs and output/cache. Send this error; do not redownload the full panel.')
        raise SystemExit(1)
