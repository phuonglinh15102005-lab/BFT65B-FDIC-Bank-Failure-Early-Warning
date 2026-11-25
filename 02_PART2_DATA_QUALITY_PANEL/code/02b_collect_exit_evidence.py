#!/usr/bin/env python3
"""BFT65B Part 2B: collect official definitions and bank-exit evidence.

Run: python 02b_collect_exit_evidence.py
Optional: --step2-dir PATH --out PATH
Python standard library only. Uses the completed step 2A CSV reports.
Does not alter Financials, panel_base, audit inputs or model labels.
Only supplemental FDIC history and metadata are downloaded. Requests are cached
for resumption in a separate output directory. All outputs are AUDIT ONLY.

Sources: BFT65B course brief; FDIC https://api.fdic.gov/banks/docs/;
FFIEC https://cdr.ffiec.gov/Public/HelpFiles/WelcomeAdditionalInfo.htm.
AI assistance: ChatGPT, 9 November 2026; cite in report and README.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import zipfile

VERSION = '1.0'
API = 'https://api.fdic.gov/banks'
LIMIT = 10000
HISTORY_FIELDS = ['CERT', 'OUT_CERT', 'ACQ_CERT', 'INSTNAME', 'OUT_INSTNAME',
                  'ACQ_INSTNAME', 'CHANGECODE', 'CHANGECODE_DESC', 'EFFDATE',
                  'PROCDATE', 'ORG_ROLE_CDE', 'TRANSNUM', 'OUT_UNINUM', 'ACQ_UNINUM', 'UNINUM']
META_FIELDS = ['CERT', 'REPDTE', 'NAME', 'INSFDIC', 'BKCLASS', 'INSAGNT1', 'ACTEVT']
FIN_FIELDS = ['CERT', 'REPDTE', 'STNAME', 'ASSET', 'DEP', 'DEPDOM', 'EQ', 'BRO',
              'CHBAL', 'SC', 'LNLSGR', 'LNLSNET', 'LNRE', 'LNCI', 'LNCON', 'LNATRES',
              'NCLNLS', 'P3ASSET', 'P9ASSET', 'NAASSET', 'NTLNLS', 'ORE', 'NETINC',
              'INTINC', 'EINTEXP', 'NONII', 'NONIX', 'ELNATR', 'ROA', 'ROE', 'NIMY',
              'RBC1AAJ', 'RBCRWAJ']
DICT_URLS = {
    'financials': API + '/docs/risview_properties.yaml',
    'institutions': API + '/docs/institution_properties.yaml',
    'failures': API + '/docs/failure_properties.yaml',
    'history': API + '/docs/history_properties.yaml',
}
REQUIRED_REPORTS = ['bank_coverage_AUDIT_ONLY.csv', 'failure_event_coverage.csv',
                    'unmatched_institutions.csv', 'banks_with_internal_gaps.csv',
                    'multiple_failure_events.csv', 'reports_after_inactive_date_REVIEW.csv',
                    'numeric_profile.csv', 'missingness_by_quarter.csv',
                    'column_availability.csv', 'text_cleanup.csv', 'rows_by_quarter.csv']


def say(message):
    print(message, flush=True)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def atomic_bytes(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.partial')
    temp.write_bytes(content)
    temp.replace(path)


def save_json(path, data):
    atomic_bytes(path, (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8'))


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write_csv(path, records, columns=None):
    if columns is None:
        columns = list(dict.fromkeys(k for r in records for k in r)) or ['status']
    with Path(path).open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='raise')
        writer.writeheader()
        writer.writerows(records)


def integer(value):
    if value is None or str(value).strip() == '':
        return None
    try:
        n = float(value)
        return int(n) if n.is_integer() else None
    except (ValueError, TypeError, OverflowError):
        return None


def positive_cert(value):
    n = integer(value)
    return n if n is not None and n > 0 else None


def day(value):
    if value is None or str(value).strip() == '':
        return None
    text = str(value).strip()
    for candidate, fmt in [(text[:10], '%Y-%m-%d'), (text[:8], '%Y%m%d'),
                           (text[:10], '%m/%d/%Y')]:
        try:
            return datetime.strptime(candidate, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def true(value):
    return str(value).strip().lower() in {'true', '1'}


def input_signature(step2):
    files = [step2 / 'step2_summary.json'] + [step2 / 'review_AUDIT_ONLY' / n for n in REQUIRED_REPORTS]
    for p in files:
        require(p.is_file(), f'Missing step 2A input: {p}')
    hashes = {p.name: digest(p.read_bytes()) for p in files}
    return hashes


def find_step2(explicit=None):
    if explicit:
        return Path(explicit).expanduser().resolve()
    candidates = set()
    for root in [Path.home() / 'BFT65B_outputs', Path(__file__).resolve().parent / 'BFT65B_outputs']:
        if root.is_dir():
            candidates.update(root.glob('step2_*'))
    valid = []
    for p in candidates:
        try:
            s = read_json(p / 'step2_summary.json')
            if (s.get('status') == 'BASE_PANEL_READY_FOR_REVIEW' and s.get('quarters') == 170
                    and s.get('rows_input') == s.get('rows_output') and s.get('rows_dropped') == 0
                    and all((p / 'review_AUDIT_ONLY' / n).is_file() for n in REQUIRED_REPORTS)):
                valid.append(p)
        except (OSError, ValueError):
            continue
    require(valid, 'Cannot find completed step 2A. Use --step2-dir "PATH_TO_STEP2_OUTPUT". Do not redownload Financials.')
    return max(valid, key=lambda p: (p / 'step2_summary.json').stat().st_mtime).resolve()


class Collector:
    def __init__(self, root, offline=False):
        self.root = Path(root)
        self.cache = self.root / 'request_cache'
        self.cache.mkdir(exist_ok=True)
        self.offline = offline
        self.records = []
        self.indexes = {}
        self.query_checks = []

    def get(self, url):
        key = digest(url.encode('utf-8'))
        data_path = self.cache / (key + '.body')
        meta_path = self.cache / (key + '.json')
        cached = data_path.is_file() and meta_path.is_file()
        if cached:
            data = data_path.read_bytes()
            meta = read_json(meta_path)
            require(meta.get('url') == url and meta.get('sha256') == digest(data),
                    f'Cached request integrity failed: {key}. Keep files and send this error.')
        else:
            require(not self.offline, f'Offline test cache missing: {url}')
            last = None
            for attempt in range(1, 6):
                try:
                    request = Request(url, headers={'User-Agent': 'BFT65B-Part2-review/1.0',
                                                   'Accept': 'application/json, text/yaml, text/html, */*'})
                    with urlopen(request, timeout=45) as response:
                        data = response.read()
                        meta = {'url': url, 'retrieved_at_utc': utcnow(), 'http_status': response.status,
                                'content_type': response.headers.get('Content-Type'), 'sha256': digest(data)}
                    atomic_bytes(data_path, data)
                    save_json(meta_path, meta)
                    time.sleep(.2)
                    break
                except HTTPError as exc:
                    last = exc
                    if exc.code not in {408, 429, 500, 502, 503, 504}:
                        detail = exc.read(700).decode('utf-8', errors='replace')
                        raise RuntimeError(f'FDIC HTTP {exc.code}: {detail}') from exc
                except (URLError, TimeoutError, OSError) as exc:
                    last = exc
                if attempt == 5:
                    raise RuntimeError(f'Download failed after retries: {last}. Run the same command again to resume.')
                say(f'  Network retry {attempt}/4: {type(last).__name__}')
                time.sleep(min(8, 2**(attempt-1)))
        self.records.append({**meta, 'cache_key': key, 'reused_cache': cached})
        return data

    def api(self, endpoint, filters, fields):
        params = {'filters': filters, 'fields': ','.join(fields), 'limit': LIMIT,
                  'offset': 0, 'sort_by': 'EFFDATE' if endpoint == 'history' else 'REPDTE',
                  'sort_order': 'ASC', 'format': 'json'}
        url = API + '/' + endpoint + '?' + urlencode(params)
        payload = json.loads(self.get(url))
        require(isinstance(payload.get('meta'), dict) and isinstance(payload.get('data'), list),
                'Unexpected FDIC API response structure.')
        total = integer(payload['meta'].get('total'))
        require(total is not None and total >= 0, 'Invalid API total.')
        index = payload['meta'].get('index')
        require(isinstance(index, dict) and index.get('name'), 'API index identity is unavailable.')
        current = json.dumps(index, sort_keys=True)
        previous = self.indexes.setdefault(endpoint, current)
        require(previous == current, f'{endpoint} API index changed during/resuming collection. Keep the output and send this error; do not mix snapshots.')
        records = [r['data'] for r in payload['data']]
        require(len(records) <= total and len(records) <= LIMIT, 'API page length inconsistent with total.')
        return records, total

    def complete(self, endpoint, filters, fields, label, lower=1800, upper=2200, depth=0):
        records, total = self.api(endpoint, filters, fields)
        if total <= LIMIT:
            require(len(records) == total, f'Incomplete API response for {label}: {len(records)}/{total}.')
            ids = [str(r.get('ID', '')) for r in records]
            require(all(ids) and len(set(ids)) == len(ids), f'Missing or repeated API IDs inside {label}.')
            self.query_checks.append({'label': label, 'endpoint': endpoint, 'filter': filters,
                                      'rows': len(records), 'api_total': total, 'complete': True})
            say(f'  {label}: {total:,} records (checked)')
            return records
        # Avoid unstable offset paging on non-unique history sort fields. Split
        # into complementary date predicates until every query fits one page.
        require(depth < 12 and upper-lower > 1, f'{label} cannot be safely split further; no partial result accepted.')
        mid = (lower+upper)//2
        field = 'EFFDATE' if endpoint == 'history' else 'REPDTE'
        cutoff = f'{mid}-12-31' if endpoint == 'history' else f'{mid}1231'
        predicate = f'{field}:[* TO {cutoff}]'
        say(f'  {label}: {total:,} records; splitting the request...')
        left = self.complete(endpoint, f'({filters}) AND ({predicate})', fields, label+' L', lower, mid+1, depth+1)
        right = self.complete(endpoint, f'({filters}) AND NOT ({predicate})', fields, label+' R', mid+1, upper, depth+1)
        result = left+right
        ids = [str(r['ID']) for r in result]
        require(len(result) == total and len(set(ids)) == total, f'Date partitions overlap or omit rows for {label}.')
        return result


def yaml_field_blocks(text):
    """Extract exact blocks from the documented FDIC properties indentation.

    This is a checked extraction of source text, not a general YAML parser.
    Do not interpret formulas or execute content from the dictionary.
    """
    matches = list(re.finditer(r'^      ([A-Za-z0-9_]+):\s*$', text, re.MULTILINE))
    require(matches, 'FDIC dictionary layout changed; cannot safely extract field blocks.')
    return {m.group(1): text[m.end():matches[i+1].start() if i+1<len(matches) else len(text)]
            for i,m in enumerate(matches)}


def yaml_text_property(block, name):
    lines = block.splitlines()
    for index,line in enumerate(lines):
        match = re.match(r'^        '+re.escape(name)+r':\s*(.*)$', line)
        if not match:
            continue
        first = match.group(1).strip()
        values = [] if first in {'', '>', '>-', '|', '|-'} else [first.strip('"\'')]
        for following in lines[index+1:]:
            if following.strip() and not following.startswith('          '):
                break
            if following.strip():
                values.append(following.strip())
        return ' '.join(values)
    return ''


def definitions(collector, out):
    folder = out / 'source_documents'
    folder.mkdir(exist_ok=True)
    all_rows = []
    dictionaries = {}
    for table,url in DICT_URLS.items():
        content = collector.get(url)
        atomic_bytes(folder / (table+'_properties.yaml'), content)
        dictionaries[table] = yaml_field_blocks(content.decode('utf-8-sig'))
    fields = {
        'financials': list(dict.fromkeys(FIN_FIELDS+META_FIELDS)),
        'institutions': ['CERT','ACTIVE','ENDEFYMD','ESTYMD','INSDATE','CHANGEC1','BKCLASS'],
        'failures': ['CERT','FAILDATE','RESTYPE','COST'],
        'history': HISTORY_FIELDS,
    }
    for table,names in fields.items():
        for field in names:
            block = dictionaries[table].get(field)
            require(block is not None, f'Official dictionary missing {table}.{field}.')
            title = yaml_text_property(block, 'title')
            description = yaml_text_property(block, 'description')
            all_rows.append({'table': table, 'field': field, 'source_title': title,
                             'source_description': description, 'api_type': yaml_text_property(block,'type'),
                             'definition_status': 'DESCRIPTION_PRESENT' if description else 'TITLE_ONLY_REQUIRES_ITEM_INSTRUCTIONS',
                             'unit_and_ytd_status': 'VERIFY_FROM_ITEM_INSTRUCTIONS_BEFORE_FEATURES',
                             'source_url': DICT_URLS[table]})
    write_csv(out/'review_AUDIT_ONLY'/'field_dictionary_sources.csv', all_rows)
    return all_rows


def history_subject(record):
    # OUT_CERT is the departing/divesting party. ACQ_CERT is the acquirer and
    # must never be turned into a failed/exited bank just because it is present.
    out = positive_cert(record.get('OUT_CERT'))
    cert = positive_cert(record.get('CERT'))
    return out or cert, 'OUT_CERT' if out else 'CERT', bool(out and cert and out != cert)


def descriptive_kind(description):
    d = str(description or '').casefold()
    if 'failure' in d or 'failed' in d:
        return 'FAILURE_HISTORY_CHECK_FAILURE_REGISTER'
    if 'with assistance' in d or ('assisted' in d and 'unassisted' not in d):
        return 'ASSISTED_EVENT_REVIEW'
    if 'without assistance' in d and any(w in d for w in ['merger','consolidat','absorb']):
        return 'BUSINESS_COMBINATION_WITHOUT_ASSISTANCE'
    if 'voluntary' in d and any(w in d for w in ['closing','liquidat']):
        return 'VOLUNTARY_CLOSURE'
    return 'OTHER_EVENT_REVIEW'


def normalize_history(records):
    normalized = []
    for r in records:
        subject, role, conflict = history_subject(r)
        normalized.append({
            'API_ID': r['ID'], 'SUBJECT_CERT': subject, 'SUBJECT_FIELD': role,
            'CERT_OUT_CERT_CONFLICT': conflict, 'CERT': positive_cert(r.get('CERT')),
            'OUT_CERT': positive_cert(r.get('OUT_CERT')), 'ACQ_CERT': positive_cert(r.get('ACQ_CERT')),
            'CHANGECODE': integer(r.get('CHANGECODE')), 'CHANGECODE_DESC': r.get('CHANGECODE_DESC'),
            'EFFDATE': day(r.get('EFFDATE')), 'EFFDATE_RAW': r.get('EFFDATE'),
            'PROCDATE': day(r.get('PROCDATE')), 'ORG_ROLE_CDE': r.get('ORG_ROLE_CDE'),
            'INSTNAME': r.get('INSTNAME'), 'OUT_INSTNAME': r.get('OUT_INSTNAME'),
            'ACQ_INSTNAME': r.get('ACQ_INSTNAME'), 'TRANSNUM': r.get('TRANSNUM'),
            'DESCRIPTION_BASED_REVIEW_KIND': descriptive_kind(r.get('CHANGECODE_DESC'))})
    return normalized


def bank_review(coverage, history, failures):
    by_bank = defaultdict(list)
    for r in history:
        # This table proposes checks, never final labels or historical features.
        if r['SUBJECT_CERT'] and str(r.get('ORG_ROLE_CDE')).upper() == 'FI':
            by_bank[r['SUBJECT_CERT']].append(r)
    f_by_bank = defaultdict(list)
    for r in failures:
        c = positive_cert(r.get('CERT'))
        if c:
            f_by_bank[c].append(r)
    result = []
    for bank in coverage:
        cert = positive_cert(bank['CERT']);end = day(bank.get('SNAPSHOT_ENDEFYMD'))
        candidates = by_bank[cert]
        same_date = [h for h in candidates if end and h['EFFDATE'] == end]
        distinct_exits = {(h['CHANGECODE'],h['CHANGECODE_DESC']) for h in same_date}
        f = f_by_bank[cert]
        if len(f) > 1:
            group = 'REVIEW_MULTIPLE_FAILURE_EVENTS'
        elif f and any(true(r.get('REPORT_ON_OR_AFTER_EVENT_REVIEW')) for r in f):
            group = 'REVIEW_REPORTS_ON_OR_AFTER_FAILURE'
        elif f:
            group = 'FAILURE_REGISTER_PRESENT_REVIEW_ELIGIBILITY'
        elif not true(bank.get('HAS_INSTITUTION_METADATA')):
            group = 'REVIEW_MISSING_INSTITUTION_METADATA'
        elif integer(bank.get('SNAPSHOT_ACTIVE')) == 1:
            group = 'ACTIVE_SNAPSHOT_NO_FAILURE_REGISTER_RECORD'
        elif len(distinct_exits) == 1:
            group = 'HISTORY_MATCHES_INACTIVE_DATE_REVIEW_CANDIDATE'
        elif len(distinct_exits) > 1:
            group = 'REVIEW_MULTIPLE_EVENT_CODES_AT_INACTIVE_DATE'
        else:
            group = 'REVIEW_INACTIVE_DATE_WITHOUT_MATCHING_HISTORY'
        result.append({'CERT': cert, 'REVIEW_GROUP_2B': group,
                       'FIRST_REPDTE': bank['FIRST_REPDTE'], 'LAST_REPDTE': bank['LAST_REPDTE'],
                       'OBSERVED_QUARTERS': bank['OBSERVED_QUARTERS'],
                       'SNAPSHOT_ACTIVE': bank.get('SNAPSHOT_ACTIVE'),
                       'SNAPSHOT_ENDEFYMD': end, 'SNAPSHOT_CHANGEC1': bank.get('SNAPSHOT_CHANGEC1'),
                       'FAILURE_REGISTER_EVENTS': len(f),
                       'FAILURE_DATES': '|'.join(sorted(day(r['FAILDATE']) or '' for r in f)),
                       'COLLECTED_HISTORY_ROWS_AS_SUBJECT': len(candidates),
                       'HISTORY_MATCHES_END_DATE': len(same_date),
                       'MATCHING_HISTORY_CODES': '|'.join(sorted({str(x['CHANGECODE']) for x in same_date})),
                       'MATCHING_HISTORY_DESCRIPTIONS': '|'.join(sorted({str(x['CHANGECODE_DESC']) for x in same_date})),
                       'FINAL_EXIT_CLASSIFICATION': 'NOT_ASSIGNED'})
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--step2-dir', type=Path)
    ap.add_argument('--out', type=Path)
    ap.add_argument('--offline', action='store_true', help='Use only existing request cache, for reproducibility checks.')
    args = ap.parse_args()
    step2 = find_step2(args.step2_dir)
    prior = read_json(step2/'step2_summary.json')
    require(prior.get('status') == 'BASE_PANEL_READY_FOR_REVIEW' and prior.get('quarters') == 170,
            'Choose the full, completed step 2A review output.')
    signature = input_signature(step2)
    suffix = step2.name.removeprefix('step2_')
    out = (args.out or (Path.home()/'BFT65B_outputs'/('step2b_'+suffix))).expanduser().resolve()
    require(not out.is_relative_to(step2) and not step2.is_relative_to(out), 'Output must be separate from step 2A inputs.')
    out.mkdir(parents=True, exist_ok=True)
    config = {'version': VERSION, 'step2_dir': str(step2), 'source_sha256': signature}
    config_path = out/'step2b_config.json'
    if config_path.exists():
        require(read_json(config_path) == config, 'Input files or script version changed. Choose a new --out folder.')
    else:
        require(not any(out.iterdir()), 'New output directory must be empty; existing unrelated files are not changed.')
        save_json(config_path, config)
    bundle = out/'part2_review_bundle.zip'
    if (out/'STEP2B_COMPLETE.json').is_file() and bundle.is_file():
        completed = read_json(out/'STEP2B_COMPLETE.json')
        require(completed.get('bundle_sha256') == digest(bundle.read_bytes()),
                'Completed review ZIP has changed. Keep the files and send this error.')
        say('DONE - EXIT_EVIDENCE_READY_FOR_REVIEW (already completed)')
        say(f'SEND THIS FILE: {bundle}')
        return 0
    review = out/'review_AUDIT_ONLY';review.mkdir(exist_ok=True)
    collector = Collector(out, offline=args.offline)
    src = step2/'review_AUDIT_ONLY'
    coverage = read_csv(src/'bank_coverage_AUDIT_ONLY.csv')
    failures = read_csv(src/'failure_event_coverage.csv')
    require(len(coverage) == prior['banks'] and len({r['CERT'] for r in coverage}) == len(coverage), 'Bank coverage does not match step 2A.')
    require(sum(int(r['OBSERVED_QUARTERS']) for r in coverage) == prior['rows_output'], 'Quarter counts do not match step 2A.')
    targets = set()
    for name in ['unmatched_institutions.csv','banks_with_internal_gaps.csv','multiple_failure_events.csv','reports_after_inactive_date_REVIEW.csv']:
        targets.update(positive_cert(r.get('CERT')) for r in read_csv(src/name))
    targets.update(positive_cert(r.get('CERT')) for r in failures if true(r.get('REPORT_ON_OR_AFTER_EVENT_REVIEW')))
    targets.discard(None)
    target_list = sorted(targets)
    say('BFT65B - Part 2B starts. Existing inputs remain unchanged.')
    say(f'Step 2A: {step2}')
    say(f'Output/cache: {out}')
    say(f'Targeted follow-up: {len(target_list)} banks flagged by step 2A.')
    say('[1/5] Saving official field definitions...')
    dictionary_rows = definitions(collector, out)

    say('[2/5] Collecting institution exit/structural events from FDIC History...')
    extra_codes = sorted({integer(r.get('SNAPSHOT_CHANGEC1')) for r in coverage
                          if integer(r.get('SNAPSHOT_ACTIVE')) == 0
                          and integer(r.get('SNAPSHOT_CHANGEC1')) is not None
                          and not 200 <= integer(r['SNAPSHOT_CHANGEC1']) <= 299})
    code_filter = 'CHANGECODE:[200 TO 299]'
    if extra_codes:
        code_filter = '('+code_filter+' OR CHANGECODE:('+' OR '.join(map(str,extra_codes))+'))'
    history_filter = 'ORG_ROLE_CDE:FI AND '+code_filter
    history = collector.complete('history', history_filter, HISTORY_FIELDS, 'Exit history')
    history_map = {str(r['ID']): r for r in history}
    batch_size = 30
    for start in range(0, len(target_list), batch_size):
        certs = ' OR '.join(map(str,target_list[start:start+batch_size]))
        filters = f'ORG_ROLE_CDE:FI AND (CERT:({certs}) OR OUT_CERT:({certs}) OR ACQ_CERT:({certs}))'
        got = collector.complete('history', filters, HISTORY_FIELDS, f'Target history {start//batch_size+1}/{(len(target_list)+batch_size-1)//batch_size}')
        for r in got:
            key = str(r['ID'])
            require(key not in history_map or history_map[key] == r, f'Conflicting responses for history ID {key}.')
            history_map[key] = r
    normalized = normalize_history(list(history_map.values()))
    write_csv(review/'history_events_AUDIT_ONLY.csv', normalized)
    observed_codes = Counter((r['CHANGECODE'],r['CHANGECODE_DESC'],r['DESCRIPTION_BASED_REVIEW_KIND']) for r in normalized)
    write_csv(review/'event_codes_observed.csv', [
        {'code':c,'official_description':d,'description_based_review_kind':k,'rows_in_collected_history':n}
        for (c,d,k),n in sorted(observed_codes.items(),key=lambda x: str(x[0]))])

    say('[3/5] Collecting only supplemental metadata for flagged banks...')
    metadata = []
    for start in range(0,len(target_list),batch_size):
        certs = ' OR '.join(map(str,target_list[start:start+batch_size]))
        filters = f'CERT:({certs}) AND REPDTE:[19840331 TO 20260630]'
        metadata += collector.complete('financials',filters,META_FIELDS,
                                       f'Financial metadata {start//batch_size+1}/{(len(target_list)+batch_size-1)//batch_size}')
    metadata_rows = [{**{k:r.get(k) for k in META_FIELDS},'API_ID':r['ID']} for r in metadata]
    keys = [(positive_cert(r['CERT']),day(r['REPDTE'])) for r in metadata_rows]
    require(len(keys) == len(set(keys)) and all(c and d for c,d in keys), 'Duplicate/invalid supplemental bank-quarter keys.')
    require(all(c in targets for c,d in keys), 'Supplemental API response contains an unrequested bank.')
    write_csv(review/'financial_metadata_AUDIT_ONLY.csv',metadata_rows,columns=META_FIELDS+['API_ID'])
    by_cert = defaultdict(list)
    for r in metadata_rows:
        by_cert[positive_cert(r['CERT'])].append(r)
    metadata_check = []
    for bank in coverage:
        cert = positive_cert(bank['CERT'])
        if cert not in targets:
            continue
        rr = by_cert[cert];dates = sorted(day(r['REPDTE']) for r in rr)
        counts_match = len(rr) == int(bank['OBSERVED_QUARTERS'])
        bounds_match = bool(dates) and dates[0] == bank['FIRST_REPDTE'] and dates[-1] == bank['LAST_REPDTE']
        metadata_check.append({'CERT':cert,'expected_quarters_step2A':bank['OBSERVED_QUARTERS'],
                               'metadata_rows':len(rr),'row_count_matches':counts_match,'date_bounds_match':bounds_match,
                               'INSFDIC_values_observed':'|'.join(sorted({str(r['INSFDIC']) for r in rr})),
                               'INSAGNT1_values_observed':'|'.join(sorted({str(r['INSAGNT1']) for r in rr})),
                               'BKCLASS_values_observed':'|'.join(sorted({str(r['BKCLASS']) for r in rr}))})
    write_csv(review/'supplemental_metadata_coverage.csv',metadata_check)

    say('[4/5] Building audit-only exit evidence and quality action tables...')
    bank_rows = bank_review(coverage,normalized,failures)
    write_csv(review/'bank_exit_evidence_AUDIT_ONLY.csv',bank_rows)
    groups = Counter(r['REVIEW_GROUP_2B'] for r in bank_rows)
    write_csv(review/'exit_review_counts.csv',[{'review_group':k,'banks':n} for k,n in sorted(groups.items())])
    # Retain the already-measured profiles; no whole-panel rescan or auto-deletion.
    for name in REQUIRED_REPORTS:
        shutil.copy2(src/name,review/('step2A_'+name))
    action_rows = [
        {'issue':'Missing numeric values','evidence':'step2A_numeric_profile.csv; step2A_missingness_by_quarter.csv','action':'Keep nulls and structural availability information; fit any later imputation on training data only.'},
        {'issue':'Blank strings and non-finite values','evidence':'step2A_text_cleanup.csv; step2A_numeric_profile.csv','action':'Step 2A normalized these to null with counts; retain raw/prepared provenance.'},
        {'issue':'Zero or negative values','evidence':'step2A_numeric_profile.csv','action':'Do not blanket-delete. Negative income/equity can be meaningful; validate denominator and item-specific constraints later.'},
        {'issue':'Internal missing quarters','evidence':'step2A_banks_with_internal_gaps.csv','action':'Do not invent observations. Calendar-based lag joins must not substitute the previous observed row for the previous quarter.'},
        {'issue':'Inactive banks and business combinations','evidence':'bank_exit_evidence_AUDIT_ONLY.csv; history_events_AUDIT_ONLY.csv','action':'Confirm subject versus acquirer and event dates before final exit classification. Inactive alone is not failure.'},
        {'issue':'Failure-date/report-date conflicts and repeat events','evidence':'step2A_failure_event_coverage.csv; step2A_multiple_failure_events.csv','action':'Resolve first-failure/episode and risk-set policy before labels. Preserve all evidence at this stage.'},
        {'issue':'Missing institution links','evidence':'supplemental_metadata_coverage.csv; financial_metadata_AUDIT_ONLY.csv','action':'Inspect per-quarter insurance/class evidence; do not classify as healthy or delete merely because the current institution join is missing.'},
        {'issue':'Publication delay and revisions','evidence':'timing_and_scope_notes.md; source_documents/','action':'Use historical decision/report dates and an explicit lag assumption. A current revised snapshot is not proven historical vintage data.'},
    ]
    write_csv(review/'quality_actions.csv',action_rows)
    notes = '''# Timing and scope decisions for the next step

These outputs are evidence for review, not a completed point-in-time panel.

- The course label is failure in (decision quarter q, q + four calendar quarters].
  Modelling decision quarters stop at 2025Q2. Financials through 2026Q2 remain stored.
- A report's REPDTE is the end of its reporting period, not its publication date.
  FFIEC describes submission-dependent publication and amended bulk data. That is
  not a universal publication rule for all FDIC/FSLIC history since 1984.
- Proposed baseline for review: quarter-end decisions with financial observations
  from at least the previous calendar quarter, plus a stricter lag sensitivity.
  This is an availability assumption, not proof of original vintage availability.
  Exact lags and eligibility must be fixed before feature generation.
- Calendar gaps must remain gaps; no backfill from future reports. Do not treat
  the previous observed row as the previous calendar quarter.
- Bank eligibility is separate from event labels. No observations after an
  established exit; voluntary closure/merger is not a bank failure. Resolve
  horizon censoring and repeat-failure episodes before assigning negative labels.
- CERT, OUT_CERT and ACQ_CERT play different roles in History. An acquirer must
  not inherit the acquired institution's failure or exit.
- Current ACTIVE/CHANGEC1 and retrospective event dates may support audit/outcomes;
  they are not historical predictors. Future metadata stays in AUDIT_ONLY files.
- This History extract is complete for its explicit filters, not all History.
  Financial metadata covers only the banks flagged in step 2A, not the full panel.
- Missing dictionary descriptions and units/YTD conventions require official item
  instructions. No unit is guessed from a field code.
- A statement that the panel is fully point-in-time correct would be premature.

Official sources:
https://api.fdic.gov/banks/docs/
https://cdr.ffiec.gov/Public/HelpFiles/WelcomeAdditionalInfo.htm

AI assistance: ChatGPT, 9 November 2026. Keep source and AI citations in the report.
'''
    atomic_bytes(out/'timing_and_scope_notes.md',notes.encode('utf-8'))
    # Save the live explanatory source if accessible; API evidence remains useful
    # even when this separate HTML website temporarily refuses automated requests.
    timing_url = 'https://cdr.ffiec.gov/Public/HelpFiles/WelcomeAdditionalInfo.htm'
    timing_saved = False
    try:
        atomic_bytes(out/'source_documents'/'ffiec_publication_notes.html',collector.get(timing_url))
        timing_saved = True
    except Exception as exc:
        say(f'  Note: publication webpage not saved ({type(exc).__name__}); URL retained.')
    write_csv(out/'api_query_checks.csv',collector.query_checks)
    save_json(out/'sources_manifest.json',{'requests':collector.records,
                                          'api_indexes':{k:json.loads(v) for k,v in collector.indexes.items()},
                                          'filtered_history_scope':history_filter})
    mismatches = sum(not r['row_count_matches'] or not r['date_bounds_match'] for r in metadata_check)
    result = {'status':'EXIT_EVIDENCE_READY_FOR_REVIEW','version':VERSION,'run_time_utc':utcnow(),
              'step2_dir':str(step2),'output_dir':str(out),'python':platform.python_version(),
              'source_panel_rows':prior['rows_output'],'source_panel_banks':prior['banks'],
              'source_panel_sha256_recorded_in_step2A':prior['panel_sha256'],
              'source_csv_inputs_verified_unchanged':input_signature(step2)==signature,
              'targeted_banks':len(target_list),'history_unique_records':len(normalized),
              'history_global_filtered_records':len(history),'supplemental_financial_metadata_rows':len(metadata_rows),
              'supplemental_count_or_date_bound_mismatches':mismatches,
              'bank_review_groups':dict(groups),'dictionary_fields':len(dictionary_rows),
              'dictionary_fields_without_description':sum(not r['source_description'] for r in dictionary_rows),
              'api_filtered_requests_verified':len(collector.query_checks),'publication_webpage_saved':timing_saved,
              'financial_rows_deleted':0,'financial_values_imputed':0,'labels_created':False,
              'final_exit_classification_created':False,'model_ready':False,
              'script_sha256':digest(Path(__file__).read_bytes()),
              'limitations':['Collected from current FDIC API indexes; not original historical vintages.',
                             'Review categories are not labels, predictors, or final exit classifications.',
                             'Supplemental count/date-bound agreement is not proof of all interior key/value equality.',
                             'Current metadata and later history can inform outcome audit but must not leak into features.']}
    require(result['source_csv_inputs_verified_unchanged'],'Input review files changed during this run.')
    save_json(out/'step2b_summary.json',result)
    say('[5/5] Packaging the review results...')
    with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(review.glob('*.csv')):
            z.write(p,p.relative_to(out))
        for name in ['step2b_summary.json','step2b_config.json','sources_manifest.json','api_query_checks.csv','timing_and_scope_notes.md']:
            z.write(out/name,name)
        for p in sorted((out/'source_documents').iterdir()):
            z.write(p,p.relative_to(out))
    save_json(out/'STEP2B_COMPLETE.json',{'status':result['status'],'bundle_sha256':digest(bundle.read_bytes())})
    say('DONE - EXIT_EVIDENCE_READY_FOR_REVIEW')
    say(f'Target banks: {len(target_list)}; history records: {len(normalized):,}; metadata rows: {len(metadata_rows):,}')
    say(f'Supplemental coverage items requiring review: {mismatches}')
    say(f'SEND THIS FILE: {bundle}')
    say('Existing data were preserved. Next: review evidence, then finalize Part 2 panel rules.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        say('Stopped. Completed requests are cached. Run the same command to resume.')
        raise SystemExit(1)
    except Exception as exc:
        say(f'STOPPED: {type(exc).__name__}: {exc}')
        say('Keep the output/cache folder. Send this error for help; do not redownload the full panel.')
        raise SystemExit(1)
