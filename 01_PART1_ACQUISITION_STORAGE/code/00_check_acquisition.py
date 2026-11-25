#!/usr/bin/env python3
"""Read-only local acquisition validation, not a live FDIC completeness assertion.

Old snapshots need original saved API totals and checksums, not totals invented
from the files being checked. No data repair or network calls occur here.
"""
import argparse
import calendar
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from acquisition_validation import atomic_json, manifest_issues, metadata_issues, saved_table_issues


def quarters():
    return [f'{y}{m:02d}{calendar.monthrange(y,m)[1]:02d}'
            for y in range(1984,2027) for m in (3,6,9,12) if y<2026 or m<=6]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--raw-dir', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True, help='New JSON path outside raw directory')
    ap.add_argument('--small-tables-manifest', type=Path,
                    help='Original saved API totals/digests; default raw-dir/manifest_small_tables.json')
    ap.add_argument('--manifest-only', action='store_true', help='Metadata check only, never source PASS')
    args = ap.parse_args()
    root = args.raw_dir.resolve(); output = args.output.resolve()
    if output.is_relative_to(root): ap.error('--output must be outside raw-dir')
    if output.exists(): ap.error('Refusing to overwrite output: '+str(output))
    expected = quarters(); issues = []; records = []; small_records = {}
    try:
        manifest = json.loads((root/'manifest_financials.json').read_text(encoding='utf-8-sig'))
        sp = args.small_tables_manifest or root/'manifest_small_tables.json'
        small = json.loads(sp.read_text(encoding='utf-8-sig')); small = small.get('tables', small)
        issues += manifest_issues(manifest, expected)
        for table in ('failures','institutions'): issues += metadata_issues(small.get(table), table)
        if args.manifest_only:
            status = 'FAIL_METADATA' if issues else 'METADATA_ONLY_NOT_SOURCE_VERIFIED'
            code = 2 if issues else 0
        elif importlib.util.find_spec('pyarrow') is None:
            status='BLOCKED_MISSING_DEPENDENCY'; code=3
            issues.append('PyArrow unavailable; no Parquet contents checked. Install only with authorization.')
        else:
            for q in expected:
                problem, rec = saved_table_issues(root/'financials'/f'REPDTE={q}.parquet',
                                                 manifest.get(q),'financials',q)
                issues += problem
                if rec: records.append(rec)
            actual = {p.name for p in (root/'financials').glob('*.parquet')}
            allowed = {f'REPDTE={q}.parquet' for q in expected}
            issues += ['Unexpected Financials file: '+name for name in sorted(actual-allowed)]
            for table in ('failures','institutions'):
                problem, rec = saved_table_issues(root/(table+'.parquet'),small.get(table),table)
                issues += problem
                if rec: small_records[table]=rec
            status = 'FAIL_LOCAL_SOURCE' if issues else 'PASS_LOCAL_SAVED_TOTALS_KEYS_AND_DIGESTS'
            code = 2 if issues else 0
    except (OSError, ValueError, TypeError, AttributeError, ImportError) as exc:
        status='BLOCKED_OR_INVALID_INPUT'; code=3; issues.append(f'{type(exc).__name__}: {exc}')
    result = {'checked_at_utc':datetime.now(timezone.utc).isoformat(), 'status':status,
              'scope':'1984Q1–2026Q2; local saved API totals, not a new FDIC API query',
              'requested_quarters':len(expected),'quarters_read':len(records),
              'financial_rows_read':sum(x['rows'] for x in records),'financial_files':records,
              'small_tables':small_records,'issues':issues,
              'vintage_point_in_time_verified':False,'network_calls':0,
              'warning':'A metadata-only result does not verify source bytes, keys or API completeness.'}
    atomic_json(output,result)
    print(status)
    for issue in issues: print(issue)
    return code

if __name__=='__main__': raise SystemExit(main())
