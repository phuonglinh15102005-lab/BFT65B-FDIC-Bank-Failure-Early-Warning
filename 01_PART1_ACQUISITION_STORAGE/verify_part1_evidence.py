#!/usr/bin/env python3
"""Recompute Part 1 evidence checks from saved logs; no API or data downloads.

Default input: source_evidence/ beside this script. Outputs: verification/.
This checks recorded fingerprints/checksums, not the unavailable Financials bytes.
AI assistance: ChatGPT, 8 November 2026. Python standard library only.
"""
from pathlib import Path
import argparse
from collections import Counter
import csv
from datetime import date
import hashlib
import json
import math
import re
import statistics


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write_csv(path, records):
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def close(a, b):
    return math.isclose(float(a), float(b), rel_tol=1e-10, abs_tol=1e-10)


def quarterly_checksums(records):
    result = {}
    for row in records:
        match = re.search(r'REPDTE=(\d{8})\.parquet$', row['path'])
        if match:
            key = match.group(1)
            require(key not in result, f'Duplicate checksum key: {key}')
            result[key] = row
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parent
    ap.add_argument('--evidence', type=Path, default=root / 'source_evidence')
    ap.add_argument('--out', type=Path, default=root / 'verification')
    args = ap.parse_args()
    base = args.evidence
    bench = base / 'benchmark_reports'
    summary = json.loads((bench / 'storage_summary.json').read_text(encoding='utf-8-sig'))
    audit = json.loads((base / 'acquisition_audit_summary.json').read_text(encoding='utf-8-sig'))
    panel = json.loads((base / 'panel_summary.json').read_text(encoding='utf-8-sig'))
    expected = {date(y, m, d).strftime('%Y%m%d')
                for y in range(1984, 2027)
                for m, d in [(3, 31), (6, 30), (9, 30), (12, 31)]
                if date(y, m, d) <= date(2026, 6, 30)}
    before = quarterly_checksums(rows(base / 'panel_input_checksums.csv'))
    after = quarterly_checksums(rows(bench / 'source_checksums.csv'))
    require(set(before) == set(after) == expected, 'Quarter sets do not match all 170 expected quarters.')
    comparisons = []
    for quarter in sorted(expected):
        a, b = before[quarter], after[quarter]
        same = a['sha256'] == b['sha256'] and int(a['bytes']) == int(b['bytes'])
        require(same, f'Prepared input differs for {quarter}')
        comparisons.append({'quarter': quarter, 'panel_bytes': a['bytes'],
                            'benchmark_bytes': b['bytes'], 'panel_sha256': a['sha256'],
                            'benchmark_sha256': b['sha256'], 'match': same})
    require(audit['errors'] == 0 and audit['expected_quarters'] == 170
            and audit['quarter_files_found'] == 170
            and audit['duplicate_valid_panel_key_extra_rows'] == 0,
            'Acquisition summary does not pass the required scope checks.')
    require(audit['total_financial_rows'] == panel['rows_input'] == summary['rows'] == 1682616,
            'Row counts disagree.')
    reference = json.loads((bench / 'reference_fingerprints.json').read_text(encoding='utf-8-sig'))
    measurements = rows(bench / 'measurements.csv')
    require(len(measurements) == 80, 'Expected 80 run records.')
    require(sum(r['warmup'].lower() == 'true' for r in measurements) == 20, 'Expected 20 warm-ups.')
    groups = {}
    for r in measurements:
        run = json.loads((bench / 'runs' / f"{int(r['run_order']):03d}.json").read_text(encoding='utf-8-sig'))
        require(run['fingerprint'] == reference[r['query']], 'Fingerprint mismatch.')
        require(run['variant'] == r['variant'] and run['query'] == r['query'], 'Run identity mismatch.')
        require(close(run['seconds'], r['seconds']), 'Timing differs between run JSON and CSV.')
        require(close(run['peak_rss_mib'], r['peak_rss_mib']), 'RSS differs between run JSON and CSV.')
        if r['warmup'].lower() == 'false':
            groups.setdefault((r['variant'], r['query']), []).append(r)
    require(len(groups) == 20 and all(len(v) == 3 for v in groups.values()), 'Expected 20 groups of three timed runs.')
    medians = {}
    checked = []
    for row in rows(bench / 'benchmark_summary.csv'):
        key = row['variant'], row['query']
        rr = groups[key]
        times = [float(r['seconds']) for r in rr]
        values = {'median_seconds': statistics.median(times), 'min_seconds': min(times),
                  'max_seconds': max(times), 'stdev_seconds': statistics.stdev(times),
                  'median_peak_rss_mib': statistics.median(float(r['peak_rss_mib']) for r in rr)}
        require(all(close(value, row[col]) for col, value in values.items()), f'Aggregate mismatch: {key}')
        medians[key] = values['median_seconds']
        checked.append({'variant': key[0], 'query': key[1], **values, 'matches_reported': True})
    for row in rows(bench / 'benchmark_summary.csv'):
        ratio = medians[('csv_uncompressed', row['query'])] / medians[(row['variant'], row['query'])]
        require(close(ratio, row['speedup_vs_csv']), 'Speedup calculation mismatch.')
    sizes = rows(bench / 'storage_sizes.csv')
    require(len(sizes) == 5, 'Expected five storage variants.')
    size_map = {r['variant']: int(r['bytes']) for r in sizes}
    csv_bytes = size_map['csv_uncompressed']
    for row in sizes:
        b = int(row['bytes'])
        require(close(b / 2**20, row['mib']) and close(100 * (1 - b / csv_bytes), row['storage_reduction_pct'])
                and close(csv_bytes / b, row['csv_to_variant_size_ratio']), 'Storage conversion mismatch.')
    schema = rows(bench / 'schema.csv')
    require(Counter(r['dtype'] for r in schema) == {'Float64': 30, 'Int64': 1, 'Date': 1, 'String': 1}, 'Schema differs.')
    benchmark_script = root / 'code' / '01b_benchmark_storage.py'
    script_hash = hashlib.sha256(benchmark_script.read_bytes()).hexdigest()
    require(script_hash == summary['script_sha256'], 'Benchmark script differs from the measured script.')
    null_cells = sum(reference['all_rows_all_columns']['null_counts'])
    null_token_bytes = len('__BFT65B_NULL_20261108__'.encode('utf-8'))
    marker_bytes = null_cells * null_token_bytes
    sensitivity_csv_bytes = csv_bytes - marker_bytes
    result = {
        'status': 'SAVED_EVIDENCE_VERIFIED',
        'prepared_quarter_checksum_pairs': len(comparisons),
        'prepared_quarter_checksum_matches': len(comparisons),
        'run_fingerprints_matching_reference': len(measurements),
        'warmups': 20, 'timed_runs': 60, 'recomputed_aggregate_groups': len(checked),
        'reported_storage_sizes_arithmetically_consistent': True,
        'benchmark_script_matches_recorded_sha256': True,
        'rows': summary['rows'], 'quarters': summary['quarters'],
        'zstd_reduction_vs_csv_pct': 100 * (1 - size_map['parquet_zstd'] / csv_bytes),
        'zstd_reduction_vs_snappy_pct': 100 * (1 - size_map['parquet_zstd'] / size_map['parquet_snappy']),
        'zstd_full_scan_speedup_vs_csv': medians[('csv_uncompressed', 'all_rows_all_columns')] / medians[('parquet_zstd', 'all_rows_all_columns')],
        'csv_null_marker_sensitivity_not_a_new_measurement': {
            'null_cells': null_cells, 'marker_bytes_per_null': null_token_bytes,
            'marker_bytes': marker_bytes, 'marker_mib': marker_bytes / 2**20,
            'counterfactual_csv_bytes': sensitivity_csv_bytes,
            'counterfactual_csv_mib': sensitivity_csv_bytes / 2**20,
            'counterfactual_zstd_reduction_pct': 100 * (1 - size_map['parquet_zstd'] / sensitivity_csv_bytes),
            'assumption': 'Remove only 24 marker bytes for each null, holding delimiters, quoting and all other bytes fixed. Not an observed alternative CSV file or timing.'
        },
        'limitations': [
            'Checksums compared here identify prepared inputs, not original FDIC HTTP payloads.',
            'This verification recomputes saved-log consistency; it does not reread all Financials files or rerun queries.',
            'Input checksum equality is demonstrated across panel-review and benchmark logs, not against a new live API download.',
            'Raw-file completeness relies on the acquisition audit and its recorded API totals.',
            'Three timed observations do not establish statistical superiority.'
        ]
    }
    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / 'prepared_checksums_comparison.csv', comparisons)
    write_csv(args.out / 'benchmark_recomputed.csv', checked)
    (args.out / 'verification_summary.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
