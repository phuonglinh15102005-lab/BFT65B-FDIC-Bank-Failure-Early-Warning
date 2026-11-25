"""Local validation only. Saved API totals are evidence, never inferred from row counts."""
from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import tempfile


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix=path.name+'.', suffix='.tmp', delete=False) as f:
            temporary = Path(f.name)
            json.dump(data, f, indent=2, allow_nan=False)
            f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def atomic_parquet(frame, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name+'.',
                                     suffix='.parquet', delete=False) as f:
        temporary = Path(f.name)
    try:
        frame.to_parquet(temporary, index=False)
        os.replace(temporary, path)
    finally:
        if temporary.exists(): temporary.unlink()


def metadata_issues(entry, label):
    problems = []
    if not isinstance(entry, dict): return [label+': missing manifest entry']
    for key in ('rows', 'api_total'):
        value = entry.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            problems.append(f'{label}: {key} must be a nonnegative integer')
    if entry.get('complete') is not True: problems.append(label+': complete flag is not True')
    if entry.get('rows') != entry.get('api_total'): problems.append(label+': rows != saved API total')
    return problems


def manifest_issues(manifest, expected):
    if not isinstance(manifest, dict): return ['Financial manifest must be an object']
    expected = set(expected)
    problems = [f'Missing quarter: {q}' for q in sorted(expected-set(manifest))]
    problems += [f'Unexpected quarter: {q}' for q in sorted(set(manifest)-expected)]
    for q in sorted(expected & set(manifest)): problems += metadata_issues(manifest[q], q)
    return problems


def parsed_dates(series):
    import pandas as pd
    text = series.astype('string').str.strip()
    compact = text.str.fullmatch(r'\d{8}').fillna(False)
    a = pd.to_datetime(text.where(compact), format='%Y%m%d', errors='coerce')
    b = pd.to_datetime(text.where(~compact), format='mixed', errors='coerce')
    return a.fillna(b)


def frame_issues(frame, table, quarter=None):
    import pandas as pd
    problems = []
    required = {'financials': {'CERT','REPDTE'}, 'institutions': {'CERT'},
                'failures': {'CERT','FAILDATE','RESTYPE'}}[table]
    absent = sorted(required-set(frame.columns))
    if absent: return [f'{table}: missing columns {absent}']
    cert = pd.to_numeric(frame.CERT, errors='coerce')
    valid = cert.notna() & cert.gt(0) & cert.mod(1).eq(0)
    # Unlinkable legacy failure events stay in the source, not invented CERTs.
    bad = ~valid if table != 'failures' else frame.CERT.notna() & ~valid
    if bad.any(): problems.append(f'{table}: invalid CERT rows={int(bad.sum())}')
    if table == 'institutions' and cert[valid].duplicated().any():
        problems.append('institutions: duplicate CERT')
    if table == 'financials':
        dates = parsed_dates(frame.REPDTE)
        if dates.isna().any(): problems.append('financials: invalid/missing REPDTE')
        if not dates.dropna().dt.is_quarter_end.all(): problems.append('financials: non-quarter-end REPDTE')
        if quarter is not None and not dates.dt.strftime('%Y%m%d').eq(quarter).all():
            problems.append('financials: report dates do not match requested quarter '+quarter)
        keys = pd.DataFrame({'CERT':cert, 'REPDTE':dates})
        if keys.duplicated().any(): problems.append('financials: duplicate CERT/REPDTE')
    elif table == 'failures':
        dates = parsed_dates(frame.FAILDATE)
        types = frame.RESTYPE.astype('string').str.strip().str.upper()
        if dates.isna().any(): problems.append('failures: invalid/missing FAILDATE')
        if not types.isin(['FAILURE','ASSISTANCE']).all(): problems.append('failures: unknown/missing RESTYPE')
        linked = pd.DataFrame({'CERT':cert[valid], 'FAILDATE':dates[valid], 'RESTYPE':types[valid]})
        if linked.duplicated().any(): problems.append('failures: duplicate linked event key')
    return problems


def saved_table_issues(path, entry, table, quarter=None, reader=None):
    import pandas as pd
    path = Path(path); label = quarter or table
    problems = metadata_issues(entry, label)
    if not path.is_file(): return problems+[f'Missing file: {path}'], None
    frame = (reader or pd.read_parquet)(path)
    problems += frame_issues(frame, table, quarter)
    digest = sha256(path)
    if isinstance(entry, dict):
        if len(frame) != entry.get('rows'): problems.append(label+': actual rows != manifest rows')
        expected_hash = entry.get('sha256')
        if not expected_hash: problems.append(label+': missing saved SHA-256; integrity not verified')
        elif digest != expected_hash: problems.append(label+': SHA-256 mismatch')
        if entry.get('bytes') is not None and entry['bytes'] != path.stat().st_size:
            problems.append(label+': byte count mismatch')
    return problems, {'path':str(path), 'rows':len(frame), 'bytes':path.stat().st_size,
                      'sha256':digest, 'schema':{c:str(t) for c,t in frame.dtypes.items()}}
