#!/usr/bin/env python3
"""Reconcile returned Part 2D evidence with saved 2A/2C review outputs.

Standard library only. Does not open the user's full Parquets, change inputs,
fit transformations or create labels. Full-value checks were performed by 2D
on the user's machine. This script checks its lineage and aggregate consistency.
AI assistance: OpenAI ChatGPT, 9 November 2026.
"""
import argparse
import calendar
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(a_path, c_path, d_path, script_path, out):
    checks = []

    def check(name, condition):
        if not condition:
            raise ValueError(name)
        checks.append({'check': name, 'status': 'PASS'})

    def j(z, name):
        return json.loads(z.read(name).decode('utf-8-sig'))

    def rows(z, name):
        return list(csv.DictReader(io.StringIO(z.read(name).decode('utf-8-sig'))))

    with zipfile.ZipFile(a_path) as za, zipfile.ZipFile(c_path) as zc, zipfile.ZipFile(d_path) as zd:
        check('All three review ZIPs pass CRC checks', all(z.testzip() is None for z in (za, zc, zd)))
        check('Part 2D contains the five expected unique files', len(zd.namelist()) == 5 and set(zd.namelist()) == {
            'financial_soft_checks.csv', 'preflight_summary.json',
            'ratio_diagnostics_by_quarter.csv', 'READ_ME.txt', 'schemas.json'})
        a = j(za, 'step2_summary.json')
        c = j(zc, 'step2c_summary.json')
        cfg = j(zc, 'step2c_config.json')
        d = j(zd, 'preflight_summary.json')
        schemas = j(zd, 'schemas.json')
        quarters = rows(zd, 'ratio_diagnostics_by_quarter.csv')
        profile_rows = rows(zc, 'review_AUDIT_ONLY/numeric_profile_after.csv')
        profile = {r['column']: r for r in profile_rows}
        old_rows = rows(zc, 'review_AUDIT_ONLY/missingness_after_by_quarter.csv')
        old = {r['REPDTE']: r for r in old_rows}
        soft = rows(zd, 'financial_soft_checks.csv')

    check('Exactly 24 distinct returned checks pass', d['status'] == 'PREFLIGHT_PASS'
          and d['check_count'] == len(d['checks']) == 24
          and len({r['check'] for r in d['checks']}) == 24
          and all(r['status'] == 'PASS' for r in d['checks']))
    check('Full-value scope and stated limitations are explicit',
          d['full_output_parquet_bytes_read'] is True
          and d['retained_value_equality_checked'] is True
          and d['soft_flags_are_not_errors'] is True
          and d['original_vintage_PIT_verified'] is False
          and d['final_labels_created'] is False)
    check('Executed preflight matches the supplied script SHA-256', digest(script_path) == d['script_sha256'])
    check('Base hash agrees across 2A, 2C configuration and 2D',
          a['panel_sha256'] == cfg['panel_sha256'] == d['output_hashes']['panel_base.parquet'])
    check('Clean and decision hashes agree with saved 2C output identities',
          all(d['output_hashes'][name] == c['output_sha256'][name]
              for name in ('panel_clean.parquet', 'panel_pit_base.parquet')))
    check('Runtime matches the successful 2C run', d['python'] == c['python'] and d['polars'] == c['polars'])
    base_schema = schemas['panel_base.parquet']
    clean_schema = schemas['panel_clean.parquet']
    check('Complete 33-field financial schemas agree', base_schema == clean_schema
          and len(clean_schema) == 33
          and clean_schema['CERT'] == 'Int64'
          and clean_schema['REPDTE'] == 'Date'
          and clean_schema['STNAME'] == 'String'
          and {k for k,v in clean_schema.items() if v == 'Float64'} == set(profile)
          and len(profile) == len(profile_rows) == 30)
    expected_pit = {('SOURCE_REPDTE' if k == 'REPDTE' else k): v for k, v in clean_schema.items()}
    expected_pit['DECISION_DATE'] = 'Date'
    check('Decision schema is exactly the financial schema plus calendar mapping',
          schemas['panel_pit_base.parquet'] == expected_pit and len(expected_pit) == 34)
    expected_dates = []
    for year in range(1984, 2027):
        for month in (3, 6, 9, 12):
            if (year, month) <= (2026, 6):
                expected_dates.append(f'{year}-{month:02d}-{calendar.monthrange(year,month)[1]:02d}')
    check('Exactly 170 ordered quarterly diagnostic records cover 1984Q1 to 2026Q2',
          [r['REPDTE'] for r in quarters] == expected_dates and len(quarters) == 170)
    check('All quarterly row counts agree with 2C and sum to the clean panel',
          len(old_rows) == len(old) == len(quarters)
          and set(old) == set(expected_dates)
          and all(r['rows'] == old[r['REPDTE']]['rows'] for r in quarters)
          and sum(int(r['rows']) for r in quarters) == c['clean_rows'])
    fields = ('ROA', 'ROE', 'RBC1AAJ', 'RBCRWAJ')
    check('All 680 quarterly null counts agree with 2C',
          all(int(r[f+'_null']) == int(old[r['REPDTE']][f]) for r in quarters for f in fields))
    totals = {f: {k: sum(int(r[f+'_'+k]) for r in quarters)
                  for k in ('null', 'zero', 'abs_gt_100_pct')} for f in fields}
    check('All eight ratio null and zero totals agree with the prior profile',
          all(totals[f][k] == int(profile[f][k]) for f in fields for k in ('null', 'zero')))
    check('Ratio counts obey nonnegative and mutually exclusive count bounds',
          all(all(int(r[f+'_'+k]) >= 0 for k in ('null', 'zero', 'abs_gt_100_pct'))
              and sum(int(r[f+'_'+k]) for k in ('null', 'zero', 'abs_gt_100_pct')) <= int(r['rows'])
              for r in quarters for f in fields))
    soft_by_name = {r['check']: r for r in soft}
    denom_fields = ('ASSET', 'DEP', 'LNLSGR', 'EQ')
    pair_names = ('DEPDOM exceeds DEP', 'LNLSNET exceeds LNLSGR')
    check('All six financial diagnostics are present exactly once', len(soft) == len(soft_by_name) == 6
          and set(soft_by_name) == set(pair_names) | {f+' <= 0 (candidate denominator)' for f in denom_fields})
    check('Four nonpositive counts and eligible populations agree with prior profile',
          all(int(soft_by_name[f+' <= 0 (candidate denominator)']['flagged_rows']) ==
              int(profile[f]['negative']) + int(profile[f]['zero'])
              and int(soft_by_name[f+' <= 0 (candidate denominator)']['eligible_rows']) ==
              c['clean_rows'] - int(profile[f]['null']) for f in denom_fields))
    check('Pairwise diagnostic counts are bounded and null eligibility is feasible',
          all(0 <= int(soft_by_name[name]['flagged_rows']) <= int(soft_by_name[name]['eligible_rows'])
              and c['clean_rows'] - int(profile[f1]['null']) - int(profile[f2]['null'])
              <= int(soft_by_name[name]['eligible_rows'])
              <= c['clean_rows'] - max(int(profile[f1]['null']), int(profile[f2]['null']))
              for name, f1, f2 in ((pair_names[0], 'DEPDOM', 'DEP'), (pair_names[1], 'LNLSNET', 'LNLSGR'))))
    early = [r for r in quarters if r['REPDTE'] < '1990-01-01']
    all_zero = [r['REPDTE'] for r in quarters if r['rows'] == r['RBCRWAJ_zero']]
    result = {
        'status': 'RETURNED_EVIDENCE_RECONCILED',
        'scope': 'Reconciles returned evidence; the 24 full-Parquet checks ran on the user machine, not here.',
        'check_count': len(checks), 'checks': checks,
        'input_sha256': {p.name: digest(p) for p in (a_path, c_path, d_path, script_path)},
        'preflight_checks': d['check_count'], 'clean_rows': c['clean_rows'],
        'ratio_totals': totals,
        'rbcrwaj_zero_pattern': {
            'all_zero_quarters': all_zero,
            'pre_1990_quarters': len(early),
            'pre_1990_rows': sum(int(r['rows']) for r in early),
            'first_quarter_with_nonzero_value': next(r['REPDTE'] for r in quarters
                if int(r['RBCRWAJ_zero'])+int(r['RBCRWAJ_null']) < int(r['rows'])),
            'latest_quarter': quarters[-1]['REPDTE'],
            'latest_zero_count': int(quarters[-1]['RBCRWAJ_zero']),
            'latest_rows': int(quarters[-1]['rows']),
            'latest_zero_share_pct': 100*int(quarters[-1]['RBCRWAJ_zero'])/int(quarters[-1]['rows']),
            'interpretation': 'Observed pattern only; zero convention and any regulatory cause are not established.'},
        'financial_soft_checks': soft,
        'pairwise_counts_independently_recomputed_from_full_parquets': False,
        'financial_flag_row_overlap_known': False,
        'final_labels_created': False, 'original_vintage_PIT_verified': False,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'{len(checks)}/{len(checks)} returned-evidence reconciliations PASS; saved {out}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--step2a-zip', type=Path, required=True)
    ap.add_argument('--step2c-zip', type=Path, required=True)
    ap.add_argument('--step2d-zip', type=Path, required=True)
    ap.add_argument('--preflight-script', type=Path, default=Path(__file__).with_name('02d_preflight_part2.py'))
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    run(args.step2a_zip, args.step2c_zip, args.step2d_zip, args.preflight_script, args.out)
