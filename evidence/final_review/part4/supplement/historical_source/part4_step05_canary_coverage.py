#!/usr/bin/env python3
"""BFT65B Part 4: development-only temporal canary and Tier-2 source coverage.

Purpose
-------
1. Audit a stratified set of development decision quarters against the actual
   Step-01 financial feature builder. Rebuild its 15 outputs from original,
   as-of-truncated, post-cutoff-poisoned, and row-shuffled financial inputs.
2. Ensure the temporal gate REJECTS a deliberately constructed feature that
   reads an institution's DECISION-quarter financial statement (future at t).
3. Profile availability/zero frequency of candidate Tier-2 fields by SOURCE
   reporting year. This is diagnostic profiling; no Tier-2 feature is admitted
   to modelling here, and no validation/test predictions or thresholds exist.

Important scope
---------------
Source financial records in panel_clean cover dates after the development
period, so this audit reads those SOURCE records to perturb them. It never
reads the final-test FEATURE table, labels, predictions, or any final-test
performance. Financial source vintages remain unverified.

Tests do NOT prove a universal absence of leakage. The original builder reads
11 current-report numeric fields from the frozen PIT input and ASSET for its
past-quarter joins from clean. Full-development source/PIT parity and the
independent pandas formula oracle were established in V2 upstream. This script
adds functional as-of/canary sensitivity on explicitly sampled quarters.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import sys
import tempfile
import traceback
import zipfile
from pathlib import Path


DEV_END = dt.date(2008, 12, 31)
MAX_SOURCE_END = dt.date(2008, 9, 30)  # last financial source for 2008Q4 decision
TEST_START = dt.date(2010, 3, 31)
CANDIDATE_SOURCE_FIELDS = [
    'NAASSET', 'P3ASSET', 'P9ASSET', 'NTLNLS', 'ORE', 'BRO',
    'LNRE', 'LNCI', 'LNCON', 'NETINC', 'INTINC', 'EINTEXP',
    'NONII', 'NONIX', 'ELNATR', 'ROE', 'RBC1AAJ', 'RBCRWAJ', 'DEPDOM',
]
EXPECTED_PREDICTORS = [
    'log_assets', 'equity_to_assets', 'negative_equity_flag',
    'asset_log_growth_1q', 'asset_log_growth_4q',
    'nclnls_to_loans', 'loan_allowance_to_loans',
    'cash_to_assets', 'cash_and_securities_to_assets',
    'deposits_to_assets', 'net_loans_to_assets',
    'roa_reported_percent', 'nimy_reported_percent',
    'loss_flag_roa_negative', 'loan_denominator_invalid_flag',
]


def require(ok: bool, reason: str) -> None:
    if not bool(ok):
        raise AssertionError(reason)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def qid(date: dt.date) -> int:
    if hasattr(date, 'date') and not isinstance(date, dt.date):
        date = date.date()
    return date.year * 4 + (date.month - 1) // 3


class FutureDataRejected(AssertionError):
    pass


def assert_point_in_time(source_date: dt.date, decision_date: dt.date) -> None:
    """For this project, the most recent permitted reporting QUARTER is t-1.

    This is a temporal lineage control. It is NOT an availability-date oracle.
    """
    if qid(source_date) > qid(decision_date) - 1:
        raise FutureDataRejected(
            f'Financial report {source_date} cannot be used for decision {decision_date}'
        )


def self_test() -> None:
    # Tests are intentionally standard-library-only so they run before packages.
    assert_point_in_time(dt.date(2001, 12, 31), dt.date(2002, 3, 31))
    assert_point_in_time(dt.date(2001, 9, 30), dt.date(2002, 3, 31))
    detected = 0
    for source in (dt.date(2002, 3, 31), dt.date(2002, 6, 30)):
        try:
            assert_point_in_time(source, dt.date(2002, 3, 31))
        except FutureDataRejected:
            detected += 1
    require(detected == 2, 'Temporal gate did not reject decision/future quarter canaries')
    require(qid(DEV_END) + 4 < qid(TEST_START), 'Development horizon overlaps test')
    print('SELF-TEST PASS: q-1 source accepted; decision/future canary rejected; test gap valid.')


def imported_reference(path: Path):
    spec = importlib.util.spec_from_file_location('bft65b_step01_audited_source', path)
    require(spec is not None and spec.loader is not None, 'Unable to load Step01 reference')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for item in ('RAW_REPORT_FIELDS', 'FEATURES', 'prepare_source_columns', 'feature_expressions'):
        require(hasattr(mod, item), f'Missing Step01 symbol: {item}')
    require(list(mod.FEATURES) == EXPECTED_PREDICTORS,
            'Unexpected Step01 feature allowlist; inspect revision before proceeding')
    require(set(EXPECTED_PREDICTORS).isdisjoint({
        'CERT', 'REPDTE', 'DECISION_DATE', 'SOURCE_REPDTE',
        'Y_4Q', 'SPLIT', 'FIRST_FAILURE_DATE', 'LAST_REPDTE',
        'RISK_STOP_DATE', 'EXIT_CLASS', 'HORIZON_END', 'LABEL_STATUS',
    }), 'Forbidden identifier/outcome included as a predictor')
    return mod


def compare_features(a, b, columns, context: str) -> int:
    import numpy as np
    import polars as pl

    keys = ['CERT', 'DECISION_DATE']
    a = a.select(keys + columns).sort(keys)
    b = b.select(keys + columns).sort(keys)
    require(a.height == b.height, f'{context}: differing number of rows')
    require(a.select(keys).equals(b.select(keys)), f'{context}: mismatched bank/decision keys')
    mismatches = {}
    for col in columns:
        x = a[col].cast(pl.Float64).to_numpy()
        y = b[col].cast(pl.Float64).to_numpy()
        bad = ~np.isclose(x, y, rtol=1e-9, atol=1e-10, equal_nan=True)
        if bad.any():
            mismatches[col] = int(bad.sum())
    require(not mismatches, f'{context}: feature mismatch counts: {mismatches}')
    return int(a.height * len(columns))


def selected_dates(dev, quarter_target: int):
    import numpy as np
    import polars as pl
    stats = (dev.group_by('DECISION_DATE')
             .agg(pl.len().alias('rows'), pl.col('Y_4Q').sum().alias('positive'))
             .sort('DECISION_DATE'))
    dates = stats['DECISION_DATE'].to_list()
    require(len(dates) >= 26, 'Unexpectedly short development history')
    indices = np.unique(np.round(np.linspace(0, len(dates)-1, quarter_target)).astype(int))
    selected = [dates[i] for i in indices]
    hot = stats.sort('positive', descending=True).head(5)['DECISION_DATE'].to_list()
    return sorted(set(selected + hot))


def rebuilt(mod, pit_subset, clean_subset, root, name: str):
    import polars as pl
    path = root / (name + '.parquet')
    clean_subset.write_parquet(path)
    return (mod.prepare_source_columns(root / 'pit_sample.parquet', path)
            .with_columns(mod.feature_expressions())
            .select(['CERT','DECISION_DATE'] + EXPECTED_PREDICTORS)
            .collect())


def profile_candidates(clean_path: Path, out_dir: Path):
    import polars as pl
    import pandas as pd

    source = pl.scan_parquet(clean_path)
    available = set(source.collect_schema().names())
    present = [x for x in CANDIDATE_SOURCE_FIELDS if x in available]
    missing = sorted(set(CANDIDATE_SOURCE_FIELDS) - set(present))
    require(bool(present), 'No candidate financial fields found; wrong clean panel?')

    base = (source.filter(pl.col('REPDTE') <= pl.lit(MAX_SOURCE_END))
            .with_columns(pl.col('REPDTE').dt.year().alias('source_year')))
    aggs = [pl.len().alias('total_rows')]
    for col in present:
        val = pl.col(col).cast(pl.Float64, strict=False)
        aggs.extend([
            pl.col(col).is_not_null().sum().alias(col + '__source_present'),
            val.is_not_null().sum().alias(col + '__numeric_present'),
            (val == 0).fill_null(False).sum().alias(col + '__zero'),
            (val < 0).fill_null(False).sum().alias(col + '__negative'),
        ])
    yearly = base.group_by('source_year').agg(aggs).sort('source_year').collect()
    records = []
    for row in yearly.to_dicts():
        for col in present:
            den = int(row['total_rows'])
            reported = int(row[col + '__source_present'])
            numeric = int(row[col + '__numeric_present'])
            records.append({
                'source_year': int(row['source_year']), 'field': col, 'bank_quarters': den,
                'non_null_source': reported, 'numeric_parseable': numeric,
                'reported_pct': 100 * reported / den,
                'zero_numeric': int(row[col + '__zero']),
                'negative_numeric': int(row[col + '__negative']),
            })
    tab = pd.DataFrame(records).sort_values(['field', 'source_year'])
    tab.to_csv(out_dir / 'tier2_field_coverage_by_source_year.csv', index=False)
    summary = (tab.groupby('field', as_index=False)
               .agg(source_rows=('bank_quarters', 'sum'),
                    reported_rows=('non_null_source', 'sum'),
                    numeric_rows=('numeric_parseable', 'sum'),
                    zero_numeric=('zero_numeric','sum'),
                    negative_numeric=('negative_numeric','sum'),
                    first_year_reported=('source_year',
                        lambda s: int(s.min()))))
    # Correct first year from the actual non-null data rather than schema presence.
    for idx, row in summary.iterrows():
        eligible = tab[(tab['field'] == row['field']) & (tab['non_null_source'] > 0)]
        summary.at[idx, 'first_year_reported'] = (
            int(eligible['source_year'].min()) if not eligible.empty else None
        )
    summary['reported_pct'] = (100 * summary['reported_rows'] / summary['source_rows'])
    summary.to_csv(out_dir / 'tier2_field_coverage_summary.csv', index=False)
    return {
        'status': 'SOURCE_COVERAGE_MEASURED_NOT_MODEL_FEATURES',
        'source_years_count': int(yearly.height),
        'present_fields': present,
        'absent_fields': missing,
        'source_rows_by_year': int(yearly['total_rows'].sum()),
    }


def run(args) -> None:
    import numpy as np
    import polars as pl
    import pandas as pd

    for p in (args.clean, args.pit, args.dev, args.v2_audit,
              args.fold_audit, args.step01_reference):
        require(p is not None and p.is_file(), f'Required input is missing: {p}')
    require(args.dev.name == 'development_primary_binary_v2.parquet',
            'Only primary-V2 DEVELOPMENT Parquet is accepted. Never pass test files.')
    require(args.quarters >= 25 and args.quarters <= 50,
            'Require 25–50 requested quarters for meaningful historical coverage')
    args.out.mkdir(parents=True, exist_ok=True)

    upstream = json.loads(args.v2_audit.read_text(encoding='utf-8'))
    fold = json.loads(args.fold_audit.read_text(encoding='utf-8'))
    require(upstream.get('status') == 'PASS' and fold.get('status') == 'PASS',
            'Upstream V2 or fold audit is not PASS')
    require(sha256(args.clean) == upstream['code_and_source_sha256']['clean'],
            'Clean Parquet SHA-256 differs from V2 audit')
    require(sha256(args.pit) == upstream['code_and_source_sha256']['pit'],
            'PIT Parquet SHA-256 differs from V2 audit')
    require(sha256(args.dev) == fold['input_sha256']['development_primary_binary_v2_parquet'],
            'V2 development Parquet hash differs from fold audit')
    require(sha256(args.step01_reference) == upstream['code_and_source_sha256']['original_step01'],
            'The Step01 builder file differs from the V2-reviewed source version')
    mod = imported_reference(args.step01_reference)

    print('[1/4] Reading PRIMARY V2 development only; checking keys and source timing...',flush=True)
    dev = pl.read_parquet(args.dev)
    require(dev.height == upstream['counts']['primary_labelled_rows'],
            'Development population differs from V2 audit')
    require(int(dev['Y_4Q'].sum()) == upstream['counts']['primary_positive_rows'],
            'Development positives differ from V2 audit')
    require(dev['SPLIT'].eq('development').all(), 'Non-development split was included')
    require(dev['DECISION_DATE'].max() <= DEV_END, 'Development decision-date cutoff breached')
    require(dev.select(['CERT','DECISION_DATE']).unique().height == dev.height,
            'Duplicate bank-decision keys')
    bad_quarters = dev.filter(
        (pl.col('DECISION_DATE').dt.year()*4 + (pl.col('DECISION_DATE').dt.month()-1)//3)
        - (pl.col('SOURCE_REPDTE').dt.year()*4 + (pl.col('SOURCE_REPDTE').dt.month()-1)//3)
        != 1
    ).height
    require(bad_quarters == 0, f'{bad_quarters} decision rows have invalid source quarter')
    for col in EXPECTED_PREDICTORS:
        require(col in dev.columns, f'Missing predictor {col}')
    require(set(dev.columns) == set(['CERT','DECISION_DATE','SOURCE_REPDTE','SPLIT','Y_4Q']+EXPECTED_PREDICTORS),
            'Unexpected columns in the model-ready V2 development table')
    selected = selected_dates(dev, args.quarters)

    print('[2/4] Rebuilding true as-of features and detecting a deliberate future-data canary...',flush=True)
    raw = [x for x in mod.RAW_REPORT_FIELDS if x not in ('CERT','SOURCE_REPDTE','DECISION_DATE')]
    clean = pl.read_parquet(args.clean, columns=['CERT','REPDTE']+raw)
    pit_lazy = pl.scan_parquet(args.pit)
    counts = []
    canary_rejected_count = 0
    canary_feature_comparator_rejected_count = 0
    poison_input_row_count = 0
    comparisons = {'baseline': 0,'truncation': 0,'future_poison': 0,'row_shuffle': 0}
    for ix, decision_date in enumerate(selected, 1):
        pos=(dev.filter((pl.col('DECISION_DATE')==pl.lit(decision_date)) & (pl.col('Y_4Q')==1))
             .sort('CERT').head(args.positive_per_quarter))
        neg=(dev.filter((pl.col('DECISION_DATE')==pl.lit(decision_date)) & (pl.col('Y_4Q')==0))
             .sort('CERT').head(args.negative_per_quarter))
        expected=pl.concat([pos,neg]).select(['CERT','DECISION_DATE','SOURCE_REPDTE']+EXPECTED_PREDICTORS)
        require(expected.height>0, f'No development observations at {decision_date}')
        certs=expected['CERT'].to_list()
        pit=(pit_lazy.filter(pl.col('DECISION_DATE')==pl.lit(decision_date))
             .filter(pl.col('CERT').is_in(certs))
             .select(mod.RAW_REPORT_FIELDS).collect())
        require(pit.height==expected.height, f'PIT population mismatch for {decision_date}')
        cutoff=pit['SOURCE_REPDTE'][0]
        require(pit['SOURCE_REPDTE'].eq(cutoff).all(), 'Multiple source dates in the same decision quarter')
        assert_point_in_time(cutoff, decision_date)
        require(qid(cutoff)==qid(decision_date)-1, 'Unexpected reporting lag')
        part=clean.filter(pl.col('CERT').is_in(certs))
        future = part.filter(pl.col('REPDTE') > pl.lit(cutoff))
        poison_input_row_count += future.height
        truncated=part.filter(pl.col('REPDTE') <= pl.lit(cutoff))
        poisoned=part.with_columns([
            pl.when(pl.col('REPDTE') > pl.lit(cutoff))
              .then(-11.0*pl.col(c).cast(pl.Float64).fill_null(0.0)+12345.0)
              .otherwise(pl.col(c).cast(pl.Float64))
              .alias(c)
            for c in raw
        ])
        shuffled=part.sample(fraction=1.0, shuffle=True, seed=20261114+ix)
        with tempfile.TemporaryDirectory(prefix='bft65b_asof_',dir=str(args.out)) as td:
            root=Path(td)
            pit.write_parquet(root/'pit_sample.parquet')
            original=rebuilt(mod,pit,part,root,'original')
            trunc=rebuilt(mod,pit,truncated,root,'truncated')
            changed=rebuilt(mod,pit,poisoned,root,'poisoned')
            reordered=rebuilt(mod,pit,shuffled,root,'shuffled')
        comparisons['baseline'] += compare_features(original,expected,EXPECTED_PREDICTORS,'builder-v2')
        comparisons['truncation'] += compare_features(original,trunc,EXPECTED_PREDICTORS,'as-of-truncated')
        comparisons['future_poison'] += compare_features(original,changed,EXPECTED_PREDICTORS,'post-cutoff-poison')
        comparisons['row_shuffle'] += compare_features(original,reordered,EXPECTED_PREDICTORS,'row-order-shuffle')

        # Negative-control CANARY: deliberately create a financially plausible
        # (but illegal) feature from decision-quarter ASSET. The gate must reject
        # its source date, and its value must respond to post-cutoff perturbation.
        future_asset=(part.filter((pl.col('REPDTE')==pl.lit(decision_date)) &
                                  pl.col('ASSET').is_not_null())
                        .select(['CERT','REPDTE','ASSET']))
        illegal_count=0
        illegal_feature_detected=0
        if future_asset.height:
            # Use a real post-cutoff financial observation, not a fake timestamp.
            for canary in future_asset.head(1).iter_rows(named=True):
                try:
                    assert_point_in_time(canary['REPDTE'], decision_date)
                except FutureDataRejected:
                    canary_rejected_count += 1
                    illegal_count += 1
                else:
                    raise AssertionError('CANARY WAS NOT REJECTED: future financial input accepted')
                poison_value = -11.0 * float(canary['ASSET']) + 12345.0
                require(not np.isclose(float(canary['ASSET']),poison_value,
                                       rtol=1e-10,atol=1e-10),
                        'Canary poison failed to change a future value')
                # Functional negative-control: the same numerical-comparison
                # gate used above MUST reject a deliberately future-derived
                # fake predictor against its as-of-truncated counterpart.
                fake_full=pl.DataFrame({
                    'CERT':[int(canary['CERT'])],
                    'DECISION_DATE':[decision_date],
                    'illegal_future_asset':[float(canary['ASSET'])],
                })
                fake_asof=pl.DataFrame({
                    'CERT':[int(canary['CERT'])],
                    'DECISION_DATE':[decision_date],
                    'illegal_future_asset':pl.Series([None],dtype=pl.Float64),
                })
                try:
                    compare_features(fake_full,fake_asof,
                                     ['illegal_future_asset'],'CANARY: full vs as-of')
                except AssertionError:
                    illegal_feature_detected += 1
                    canary_feature_comparator_rejected_count += 1
                else:
                    raise AssertionError('CANARY FAILED: feature comparator accepted future-data feature')
        counts.append({
            'decision_quarter':str(decision_date), 'source_cutoff':str(cutoff),
            'sampled_rows':int(expected.height), 'sampled_positive_rows':int(pos.height),
            'post_cutoff_financial_rows_changed':int(future.height),
            'canary_future_input_rejected':illegal_count,
            'canary_illegal_feature_comparator_rejected':illegal_feature_detected,
            'feature_cells_per_comparison':int(expected.height)*len(EXPECTED_PREDICTORS),
            'future_poisoned_fields':len(raw),
            'feature_mismatches':0,
        })
        print(f'  [{ix}/{len(selected)}] {decision_date}: {expected.height} rows; '
              f'{future.height} post-cutoff rows altered; canary {illegal_count}; PASS', flush=True)
    require(canary_rejected_count>0, 'No real future-row canary exercised; cannot claim gate effectiveness')
    require(canary_feature_comparator_rejected_count == canary_rejected_count,
            'Functional negative-control did not reject every future-source canary')
    require(poison_input_row_count>0, 'No post-cutoff financial rows actually poisoned')

    print('[3/4] Source-year coverage profiling for candidate Tier-2 fields (no feature selection)...',flush=True)
    tier2=profile_candidates(args.clean,args.out)
    pd.DataFrame(counts).to_csv(args.out/'asof_canary_by_quarter.csv',index=False)
    audit={
        'stage':'PART4_STEP05_DEV_SOURCE_CANARY_AND_TIER2_COVERAGE',
        'status':'PASS',
        'scope':'DEVELOPMENT_ONLY; FINAL_TEST_FEATURES_LABELS_AND_METRICS_NEVER_READ',
        'reference_v2_counts':{
            'development_decisions_labelled':int(dev.height),
            'positive_bank_quarters':int(dev['Y_4Q'].sum()),
        },
        'source_time_contract':{
            'decision_source_quarter_lag':1,
            'development_ended':str(DEV_END),
            'last_source_for_dev':str(MAX_SOURCE_END),
            'first_reserved_test_decision':str(TEST_START),
            'future_data_rejected_by_canary':int(canary_rejected_count),
            'illegal_feature_rejected_by_comparator':int(canary_feature_comparator_rejected_count),
        },
        'asof_experiment':{
            'quarters_tested':len(selected),'sampled_bank_quarters':int(sum(x['sampled_rows'] for x in counts)),
            'positive_rows_sampled':int(sum(x['sampled_positive_rows'] for x in counts)),
            'post_cutoff_financial_rows_altered':int(poison_input_row_count),
            'raw_fields_poisoned_after_cutoff':raw,
            'feature_values_compared_by_check':comparisons,
            'feature_mismatches_by_check':{k:0 for k in comparisons},
            'canary_control':'deliberately reads financial ASSET from decision quarter; must be rejected by source-date guard',
        },
        'candidate_tier2_source_coverage':tier2,
        'sha256':{
            'clean':sha256(args.clean),'pit':sha256(args.pit),
            'development_primary_v2':sha256(args.dev),
            'step01_reference':sha256(args.step01_reference),
            'v2_audit_json':sha256(args.v2_audit),
            'v2_fold_audit_json':sha256(args.fold_audit),
            'this_script':sha256(Path(__file__)),
        },
        'limitations':[
            'The decision-quarter future-ASSET canary proves that the source-date guard rejects a deliberately leaky feature; it is not a proof against all conceivable leaks.',
            'The current Step01 financial builder reads 11 current-report fields from prepared PIT and historical ASSET from clean; post-cutoff poisoning in clean does not directly mutate the frozen PIT.',
            'Field coverage by source year is not equivalent to fully validated candidate feature coverage, field-unit semantics, or availability at the historical publication vintage.',
            'No Tier-2 feature, model, calibration, threshold, or final test evaluation was fitted or selected.',
        ],
    }
    audit_file=args.out/'part4_step05_audit.json'
    audit_file.write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf-8')
    files=[audit_file,args.out/'asof_canary_by_quarter.csv',
           args.out/'tier2_field_coverage_by_source_year.csv',
           args.out/'tier2_field_coverage_summary.csv']
    package=args.out/'SHARE_THIS_PART4_STEP05_EVIDENCE.zip'
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as archive:
        for f in files:
            archive.write(f,f.name)
    with zipfile.ZipFile(package) as archive:
        require(archive.testzip() is None, 'Evidence ZIP CRC failed')
    print('[4/4] PART4 STEP05 PASS. Upload ONLY:', package,flush=True)


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test',action='store_true')
    p.add_argument('--clean',type=Path)
    p.add_argument('--pit',type=Path)
    p.add_argument('--dev',type=Path)
    p.add_argument('--v2-audit',type=Path)
    p.add_argument('--fold-audit',type=Path)
    p.add_argument('--step01-reference',type=Path)
    p.add_argument('--out',type=Path)
    p.add_argument('--quarters',type=int,default=26)
    p.add_argument('--positive-per-quarter',type=int,default=120)
    p.add_argument('--negative-per-quarter',type=int,default=120)
    args=p.parse_args()
    self_test()
    if args.self_test:
        return
    required=[args.clean,args.pit,args.dev,args.v2_audit,args.fold_audit,
              args.step01_reference,args.out]
    require(all(x is not None for x in required), 'Missing CLI input; use the included RUN_WINDOWS.bat')
    try:
        run(args)
    except Exception as exc:
        args.out.mkdir(parents=True,exist_ok=True)
        err={
            'status':'FAIL_NOT_VALIDATED','error_type':type(exc).__name__,
            'error':str(exc),'traceback':traceback.format_exc(),
        }
        (args.out/'part4_step05_ERROR.json').write_text(json.dumps(err,indent=2),encoding='utf-8')
        raise


if __name__=='__main__':
    main()
