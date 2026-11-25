"""BFT65B Part 4 / Step 01 — Polars leak-aware feature and four-quarter-label builder.

Status: SOURCE REVIEW + PYTHON SYNTAX VERIFIED. The full Parquet execution must
run in the Windows environment that has Polars 2.1.0 and PyArrow installed.

Inputs:
  --clean:    panel_clean.parquet from verified Part 2C
  --pit:      panel_pit_base.parquet from verified Part 2C
  --bundle:   part2_clean_review_bundle.zip (bank_event_registry_AUDIT_ONLY.csv)

Outputs:
  feature_label_development.parquet, feature_label_test.parquet,
  feature_label_embargo_AUDIT_ONLY.parquet (optional; excluded from modelling),
  part4_step01_summary.json, label_status_counts.csv,
  feature_missingness_by_split.csv, positive_labels_by_decision_quarter.csv

NO model is trained and NO statistics are fitted to test data. In Step 02,
scikit-learn preprocessing will be fitted on development training folds only.
The test set must not be used for tuning.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

import polars as pl

DEV_END = dt.date(2008, 12, 31)
TEST_START = dt.date(2010, 3, 31)
MODEL_END = dt.date(2025, 6, 30)

RAW_REPORT_FIELDS = [
    'CERT', 'SOURCE_REPDTE', 'DECISION_DATE',
    'ASSET', 'EQ', 'NCLNLS', 'LNLSGR', 'LNATRES',
    'CHBAL', 'SC', 'DEP', 'LNLSNET', 'ROA', 'NIMY',
]

FEATURES = [
    'log_assets', 'equity_to_assets', 'negative_equity_flag',
    'asset_log_growth_1q', 'asset_log_growth_4q',
    'nclnls_to_loans', 'loan_allowance_to_loans',
    'cash_to_assets', 'cash_and_securities_to_assets',
    'deposits_to_assets', 'net_loans_to_assets',
    'roa_reported_percent', 'nimy_reported_percent',
    'loss_flag_roa_negative', 'loan_denominator_invalid_flag',
]

FORBIDDEN_FEATURE_WORDS = (
    'FAIL', 'COST', 'EXIT', 'RESTYPE', 'ACTIVE', 'CHANGEC',
    'RISK_STOP', 'SNAPSHOT', 'FUTURE', 'HORIZON', 'Y_4Q',
)


def fail(message):
    raise RuntimeError('PART4-STEP01: ' + message)


def sha256(path: Path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def ratio(numerator: str, denominator: str, *, nonnegative_num=False):
    ok = pl.col(denominator).is_not_null() & (pl.col(denominator) > 0)
    ok &= pl.col(numerator).is_not_null()
    if nonnegative_num:
        ok &= pl.col(numerator) >= 0
    return pl.when(ok).then(
        pl.col(numerator).cast(pl.Float64) /
        pl.col(denominator).cast(pl.Float64)
    ).otherwise(pl.lit(None, dtype=pl.Float64))


def ratio_sum(nonnegative_parts: list[str], denominator: str):
    ok = pl.col(denominator).is_not_null() & (pl.col(denominator) > 0)
    for name in nonnegative_parts:
        ok &= pl.col(name).is_not_null() & (pl.col(name) >= 0)
    total = sum((pl.col(name).cast(pl.Float64) for name in nonnegative_parts), pl.lit(0.0))
    return pl.when(ok).then(total / pl.col(denominator)).otherwise(pl.lit(None, dtype=pl.Float64))


def load_registry(archive_path: Path):
    with zipfile.ZipFile(archive_path) as archive:
        name = 'review_AUDIT_ONLY/bank_event_registry_AUDIT_ONLY.csv'
        data = archive.read(name)
        summary = json.loads(archive.read('step2c_summary.json'))
    # Explicitly read all text to avoid inference surprises in mixed type CSVs.
    registry = pl.read_csv(io.BytesIO(data), infer_schema_length=0)
    registry = registry.select([
        pl.col('CERT').cast(pl.Int64),
        *[pl.col(x).str.strptime(pl.Date, format='%Y-%m-%d', strict=False)
          for x in ('FIRST_FAILURE_DATE', 'RISK_STOP_DATE', 'LAST_REPDTE')],
        pl.col('EXIT_CLASS').cast(pl.Utf8),
        pl.col('REVIEW_FLAGS').fill_null('').cast(pl.Utf8),
    ])
    if registry.height != registry.select(pl.col('CERT').n_unique()).item():
        fail('Duplicate CERTs in outcome registry')
    if registry.height != summary['registry_banks']:
        fail('Event-registry cardinality not reconciled to Step 2C')
    return registry, summary


def prepare_source_columns(pit_path: Path, clean_path: Path):
    pit_lazy = pl.scan_parquet(pit_path)
    missing = set(RAW_REPORT_FIELDS) - set(pit_lazy.collect_schema().names())
    if missing:
        fail('Missing PIT columns: ' + repr(sorted(missing)))

    # The self-joins use exact calendar dates, never a previous observed row.
    clean = pl.scan_parquet(clean_path).select('CERT', 'REPDTE', 'ASSET')
    prev_1q = clean.select(
        'CERT',
        pl.col('REPDTE').dt.offset_by('3mo').dt.month_end().alias('SOURCE_REPDTE'),
        pl.col('ASSET').alias('ASSET_PREV_1Q'),
    )
    prev_4q = clean.select(
        'CERT',
        pl.col('REPDTE').dt.offset_by('1y').dt.month_end().alias('SOURCE_REPDTE'),
        pl.col('ASSET').alias('ASSET_PREV_4Q'),
    )
    pit = pit_lazy.select(RAW_REPORT_FIELDS)
    pit = pit.join(prev_1q, on=['CERT', 'SOURCE_REPDTE'], how='left', validate='1:1')
    pit = pit.join(prev_4q, on=['CERT', 'SOURCE_REPDTE'], how='left', validate='1:1')
    return pit


def feature_expressions():
    good_asset = pl.col('ASSET') > 0
    growth_1 = pl.when(good_asset & (pl.col('ASSET_PREV_1Q') > 0)).then(
        (pl.col('ASSET') / pl.col('ASSET_PREV_1Q')).log()
    ).otherwise(pl.lit(None, dtype=pl.Float64))
    growth_4 = pl.when(good_asset & (pl.col('ASSET_PREV_4Q') > 0)).then(
        (pl.col('ASSET') / pl.col('ASSET_PREV_4Q')).log()
    ).otherwise(pl.lit(None, dtype=pl.Float64))
    return [
        pl.when(good_asset).then(pl.col('ASSET').log()).otherwise(None).alias('log_assets'),
        ratio('EQ', 'ASSET').alias('equity_to_assets'),
        (pl.col('EQ') < 0).cast(pl.Int8).alias('negative_equity_flag'),
        growth_1.alias('asset_log_growth_1q'),
        growth_4.alias('asset_log_growth_4q'),
        ratio('NCLNLS', 'LNLSGR', nonnegative_num=True).alias('nclnls_to_loans'),
        ratio('LNATRES', 'LNLSGR', nonnegative_num=True).alias('loan_allowance_to_loans'),
        ratio('CHBAL', 'ASSET', nonnegative_num=True).alias('cash_to_assets'),
        ratio_sum(['CHBAL','SC'], 'ASSET').alias('cash_and_securities_to_assets'),
        ratio('DEP','ASSET', nonnegative_num=True).alias('deposits_to_assets'),
        ratio('LNLSNET','ASSET', nonnegative_num=True).alias('net_loans_to_assets'),
        pl.col('ROA').cast(pl.Float64).alias('roa_reported_percent'),
        pl.col('NIMY').cast(pl.Float64).alias('nimy_reported_percent'),
        (pl.col('ROA') < 0).cast(pl.Int8).alias('loss_flag_roa_negative'),
        (pl.col('LNLSGR').is_null() | (pl.col('LNLSGR') <= 0)).cast(pl.Int8).alias('loan_denominator_invalid_flag'),
    ]


def add_outcome_and_status(frame: pl.LazyFrame, registry: pl.DataFrame):
    frame = frame.join(registry.lazy(), on='CERT', how='left', validate='m:1')
    decision = pl.col('DECISION_DATE')
    horizon = pl.col('HORIZON_END')
    first_fail = pl.col('FIRST_FAILURE_DATE')
    risk_stop = pl.col('RISK_STOP_DATE')
    
    conflict = first_fail.is_not_null() & risk_stop.is_not_null() & (risk_stop < first_fail)
    post_failure = first_fail.is_not_null() & (first_fail <= decision)
    fail_in_horizon = first_fail.is_not_null() & (first_fail > decision) & (first_fail <= horizon)
    competing_exit = risk_stop.is_not_null() & (risk_stop > decision) & (risk_stop <= horizon)
    observed_through_horizon = ((risk_stop.is_not_null() & (risk_stop > horizon)) |
                                (pl.col('LAST_REPDTE') >= horizon))
    frame = frame.with_columns(decision.dt.offset_by('1y').dt.month_end().alias('HORIZON_END'))
    # Critical: lazy optimizer resolves HORIZON_END after with_columns when status is built.
    label = (
        pl.when(conflict).then(pl.lit('REVIEW_DATE_CONFLICT'))
        .when(post_failure).then(pl.lit('INVALID_POST_FAILURE'))
        .when(fail_in_horizon).then(pl.lit('POSITIVE'))
        .when(competing_exit).then(pl.lit('COMPETING_EXIT_CENSORED'))
        .when(observed_through_horizon).then(pl.lit('NEGATIVE'))
        .otherwise(pl.lit('INSUFFICIENT_FOLLOWUP_CENSORED'))
    )
    frame = frame.with_columns(label.alias('LABEL_STATUS'))
    frame = frame.with_columns(
        pl.when(pl.col('LABEL_STATUS') == 'POSITIVE').then(pl.lit(1, dtype=pl.Int8))
        .when(pl.col('LABEL_STATUS') == 'NEGATIVE').then(pl.lit(0, dtype=pl.Int8))
        .otherwise(pl.lit(None, dtype=pl.Int8)).alias('Y_4Q'),
        pl.when(decision <= pl.lit(DEV_END)).then(pl.lit('development'))
        .when(decision >= pl.lit(TEST_START)).then(pl.lit('test'))
        .otherwise(pl.lit('embargo')).alias('SPLIT'),
    )
    return frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clean', type=Path, default=Path('panel_clean.parquet'))
    parser.add_argument('--pit', type=Path, default=Path('panel_pit_base.parquet'))
    parser.add_argument('--bundle', type=Path, default=Path('part2_clean_review_bundle.zip'))
    parser.add_argument('--out-dir', type=Path, default=Path('part4_step01_outputs'))
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for x in (args.clean, args.pit, args.bundle):
        if not x.is_file(): fail(f'Input does not exist: {x}')

    registry, upstream = load_registry(args.bundle)
    print('[1/5] Scan prepared panel and construct exact-calendar asset-growth joins...',flush=True)
    base = prepare_source_columns(args.pit, args.clean)
    print('[2/5] Create financial features strictly from source-quarter statements...',flush=True)
    base = base.with_columns(feature_expressions())
    print('[3/5] Add audited first-failure dates ONLY in the label branch...',flush=True)
    labelled = add_outcome_and_status(base, registry)

    # Output restricted exclusively to known feature columns and identifiers.
    # No outcome-registry dates, metadata, or cost fields enter the feature table.
    if any(any(word in feature.upper() for word in FORBIDDEN_FEATURE_WORDS)
           for feature in FEATURES):
        fail('Forbidden future/outcome field among model predictors')

    # Use one materialized frame to ensure all counts agree with exported rows.
    print('[4/5] Materialize and verify label, temporal and key invariants...',flush=True)
    result = labelled.collect()
    if result.height != upstream['decision_rows_lag1']:
        fail(f'Output rows differ from PIT: {result.height} vs {upstream["decision_rows_lag1"]}')
    if result.select('CERT','DECISION_DATE').unique().height != result.height:
        fail('Duplicate (CERT, DECISION_DATE) keys')
    calendar_bad = result.filter(
        pl.col('SOURCE_REPDTE').dt.offset_by('3mo').dt.month_end() != pl.col('DECISION_DATE')
    ).height
    if calendar_bad:
        fail(f'{calendar_bad} source-date / decision-date violations')
    if result.filter(pl.col('SOURCE_REPDTE') >= pl.col('DECISION_DATE')).height:
        fail('Future source report found')
    if result.filter(pl.col('DECISION_DATE') > pl.lit(MODEL_END)).height:
        fail('Decision dates extend beyond four-quarter label completeness cutoff')
    if result.filter((pl.col('LABEL_STATUS') == 'POSITIVE') &
                     ~((pl.col('FIRST_FAILURE_DATE') > pl.col('DECISION_DATE')) &
                       (pl.col('FIRST_FAILURE_DATE') <= pl.col('HORIZON_END')))).height:
        fail('Positive label outside the prescribed four-quarter horizon')

    model_cols = ['CERT','DECISION_DATE','SOURCE_REPDTE','SPLIT','Y_4Q'] + FEATURES
    eligible = result.filter(pl.col('Y_4Q').is_not_null()).select(model_cols)
    positives_by_quarter = (eligible.filter(pl.col('Y_4Q') == 1)
                            .group_by('SPLIT','DECISION_DATE')
                            .agg(pl.len().alias('positive_decisions'),
                                 pl.col('CERT').n_unique().alias('failing_cert_in_quarter'))
                            .sort('DECISION_DATE'))
    status = (result.group_by('SPLIT','LABEL_STATUS')
              .agg(pl.len().alias('rows'),pl.col('CERT').n_unique().alias('distinct_certs'))
              .sort('SPLIT','LABEL_STATUS'))
    missing = eligible.group_by('SPLIT').agg(
        pl.len().alias('rows'),
        *[pl.col(f).null_count().alias(f'{f}_missing') for f in FEATURES],
    )
    test = eligible.filter(pl.col('SPLIT') == 'test')
    failing_test_certs = int(test.filter(pl.col('Y_4Q') == 1).select(pl.col('CERT').n_unique()).item())
    if failing_test_certs < 50:
        fail(f'Test-set eligibility gate FAILED: {failing_test_certs} independent failing CERTs (<50)')

    for split in ('development','test'):
        part = eligible.filter(pl.col('SPLIT') == split)
        part.write_parquet(args.out_dir / f'feature_label_{split}.parquet', compression='zstd')
    # The embargo has no modelling role; retain only its outcome-status counts.
    status.write_csv(args.out_dir / 'label_status_counts.csv')
    missing.write_csv(args.out_dir / 'feature_missingness_by_split.csv')
    positives_by_quarter.write_csv(args.out_dir / 'positive_labels_by_decision_quarter.csv')

    counts = {}
    for split in ('development','embargo','test'):
        g = result.filter(pl.col('SPLIT') == split)
        y = g.filter(pl.col('Y_4Q').is_not_null())
        counts[split] = {
            'all_decision_rows': g.height,
            'labelled_rows': y.height,
            'positive_decision_rows': y.filter(pl.col('Y_4Q') == 1).height,
            'negative_decision_rows': y.filter(pl.col('Y_4Q') == 0).height,
            'distinct_positive_certs': int(y.filter(pl.col('Y_4Q') == 1).select(pl.col('CERT').n_unique()).item()),
        }
    audit = {
        'stage':'PART4_STEP01_FEATURES_AND_LABELS',
        'status':'BUILT_AND_AUDITED_IN_THIS_RUN',
        'polars_version':pl.__version__,
        'input_sha256':{'panel_clean':sha256(args.clean),'panel_pit':sha256(args.pit),'part2_evidence_zip':sha256(args.bundle)},
        'source_rows': result.height,
        'source_lag_calendar_quarters':1,
        'forward_label_quarters':4,
        'labels_positive_event_type':'FIRST_RESTYPE_FAILURE_ONLY',
        'unresolved_merger_or_competing_exit':'CENSORED_NOT_NEGATIVE',
        'unresolved_19_date_conflicts':'ALL_EXCLUDED_FROM_MODELLED_LABELS',
        'splits':counts,
        'test_has_at_least_50_distinct_failing_certs':failing_test_certs>=50,
        'test_evaluated':False,
        'predictors':FEATURES,
        'imputation_standardization_clipping_fitted':False,
        'original_vintage_replay_verified':False,
        'next_step':'Fit preprocessing on development training folds only and evaluate temporal validation in Part 5.',
    }
    (args.out_dir / 'part4_step01_summary.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    print('[5/5] Output audit and partitioned train/test feature tables complete.',flush=True)
    print('Positive CERTs in test:',failing_test_certs)
    print('Split summary:',json.dumps(counts,indent=2))
    print('Files saved in:',args.out_dir.resolve())

if __name__ == '__main__':
    main()
