#!/usr/bin/env python3
"""Independent, read-only DEVELOPMENT preprocessing audit; no sklearn or model API.

Recompute all 72 original Part4 rows (3 folds x 2 clipping modes x 12
continuous columns) from the frozen development Parquet. Only NumPy/pandas
are used. This audits archived preprocessing summaries; it does not load a
fitted pipeline or prove equivalence of an unavailable transformed matrix.

CLI example:
 python verify_fold_preprocessing_readonly.py --dev DEVELOPMENT.parquet \
   --expected-params v2_preprocessing_params.csv \
   --protocol part5_protocol_freeze.json --out NEW_OUTPUT_DIRECTORY

No training, prediction, final-test read, network or dependency installation.
Outputs are created exclusively; existing output filenames are never replaced.
The caller should verify the original development SHA256 before calling the
DataFrame function. The CLI enforces the frozen development SHA256 itself.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

CONTINUOUS = [
    'log_assets', 'equity_to_assets', 'asset_log_growth_1q',
    'asset_log_growth_4q', 'nclnls_to_loans', 'loan_allowance_to_loans',
    'cash_to_assets', 'cash_and_securities_to_assets', 'deposits_to_assets',
    'net_loans_to_assets', 'roa_reported_percent', 'nimy_reported_percent',
]
BINARY = [
    'negative_equity_flag', 'loss_flag_roa_negative',
    'loan_denominator_invalid_flag',
]
FEATURES = CONTINUOUS + BINARY
OUTPUT_COLUMNS = CONTINUOUS + BINARY + ['missing__' + x for x in FEATURES]
KEYS = ['CERT', 'DECISION_DATE', 'SOURCE_REPDTE', 'SPLIT', 'Y_4Q']
DEV_SHA256 = 'd365ce25204a3dcace715db4cea259c94b1b1abba4822c7bcf2b050a1c7f6a73'
PROTOCOL_SHA256 = '994f72de6e2446916db8c2fcd36847c45cc68eb6fef5ef67f07acc0476c6d911'
PARAM_FIELDS = [
    'training_median_post_clip', 'train_robust_center', 'train_robust_scale',
    'train_clip_lower', 'train_clip_upper', 'train_missing_count',
    'validation_missing_count',
]
FROZEN_COUNTS = {
    'early_bank_stress': (266127, 125962, 2627, 2796, 775, 932),
    'post_stress_transition': (459321, 110844, 7305, 481, 1948, 191),
    'global_financial_crisis': (1129000, 67792, 8833, 406, 2242, 167),
}


def require(ok, message):
    if not bool(ok):
        raise ValueError(message)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def continuous_parameters(train, validation, clip):
    """NumPy equivalent of clip -> median impute -> RobustScaler.

    Quantiles use the original default linear interpolation. An all-missing
    training column is preserved and imputed to 0, as keep_empty_features=True.
    RobustScaler changes numerical near-zero IQR (<10*float64 epsilon) to 1.
    Validation is used ONLY to count missing values, never to estimate params.
    """
    x = np.asarray(train, dtype=np.float64)
    v = np.asarray(validation, dtype=np.float64)
    require(x.ndim == v.ndim == 2 and x.shape[1] == v.shape[1],
            'Expected 2-D train/validation arrays with equal column width')
    require(x.shape[0] > 0, 'Empty training fold')
    require(not np.isinf(x).any() and not np.isinf(v).any(),
            'Infinite feature value; upstream must normalize/reject it')
    results = []
    for j in range(x.shape[1]):
        original = x[:, j]
        present = original[np.isfinite(original)]
        lower = float(np.quantile(present, .01)) if clip and len(present) else -np.inf
        upper = float(np.quantile(present, .99)) if clip and len(present) else np.inf
        z = np.clip(original, lower, upper) if clip else original.copy()
        finite = z[np.isfinite(z)]
        median = float(np.median(finite)) if len(finite) else 0.0
        filled = np.where(np.isnan(z), median, z)
        center = float(np.median(filled))
        q25, q75 = np.quantile(filled, [.25, .75])
        scale = float(q75 - q25)
        if scale < 10 * np.finfo(np.float64).eps:
            scale = 1.0
        results.append({
            'training_median_post_clip': median,
            'train_robust_center': center,
            'train_robust_scale': scale,
            # Original CSV leaves no-clipping bounds blank.
            'train_clip_lower': lower if clip else np.nan,
            'train_clip_upper': upper if clip else np.nan,
            'train_missing_count': int(np.isnan(original).sum()),
            'validation_missing_count': int(np.isnan(v[:, j]).sum()),
        })
    return results


def transform_numpy(raw, parameters, clip):
    """Transform a small DEVELOPMENT sample with fixed parameters, no fitting.

    Missing flags are taken from the original 15 columns, before imputation and
    clipping. Order: 12 continuous, 3 binary, then 15 original missing flags.
    """
    x = raw.loc[:, FEATURES].to_numpy(dtype=np.float64)
    require(not np.isinf(x).any(), 'Infinite transform input')
    require(len(parameters) == len(CONTINUOUS), 'Expected 12 parameter rows')
    continuous = x[:, :len(CONTINUOUS)].copy()
    for j, p in enumerate(parameters):
        z = continuous[:, j]
        if clip:
            z = np.clip(z, p['train_clip_lower'], p['train_clip_upper'])
        z = np.where(np.isnan(z), p['training_median_post_clip'], z)
        continuous[:, j] = (z - p['train_robust_center']) / p['train_robust_scale']
    binary = np.where(np.isnan(x[:, 12:15]), 0.0, x[:, 12:15])
    return np.column_stack((continuous, binary, np.isnan(x).astype(np.float64)))


def _clip_bool(value):
    text = str(value).strip().lower()
    require(text in {'true', 'false'}, 'Invalid archived clipping flag: ' + text)
    return text == 'true'


def verify_fold_preprocessing(dev_dataframe, expected_param_csv,
                              temporal_protocol_dict, out_dir, *,
                              enforce_frozen_counts=True):
    """Recompute archived 72-row summary from an already identified dev DataFrame.

    `enforce_frozen_counts=False` exists solely for isolated synthetic tests.
    Production callers must retain the default. No DataFrame mutation occurs.
    Numerical comparison uses rtol=1e-10/atol=1e-12; counts must be exact.
    This function never imports sklearn, deserializes a model or reads a test.
    """
    require(set(dev_dataframe.columns) == set(KEYS + FEATURES),
            'Development columns differ from the frozen 20-column contract')
    dev = dev_dataframe.loc[:, KEYS + FEATURES].copy()
    for c in ['DECISION_DATE', 'SOURCE_REPDTE']:
        dev[c] = pd.to_datetime(dev[c], errors='raise')
        require(dev[c].notna().all() and dev[c].dt.is_quarter_end.all(),
                c + ' must be nonmissing quarter ends')
    require(dev.SPLIT.eq('development').all(), 'Only development rows are allowed')
    require(dev.DECISION_DATE.max() <= pd.Timestamp('2008-12-31'),
            'Input includes dates after development cutoff')
    require(not dev.duplicated(['CERT', 'DECISION_DATE']).any(), 'Duplicate dev keys')
    require(dev.CERT.notna().all() and dev.Y_4Q.isin([0, 1]).all(),
            'Invalid CERT or binary label')
    delta = (dev.DECISION_DATE.dt.to_period('Q').astype('int64') -
             dev.SOURCE_REPDTE.dt.to_period('Q').astype('int64'))
    require(delta.eq(1).all(), 'Source is not exactly q-1')
    for c in FEATURES:
        dev[c] = pd.to_numeric(dev[c], errors='raise')
    require(not np.isinf(dev[FEATURES].to_numpy(dtype=np.float64)).any(),
            'Infinite development feature')
    for c in BINARY:
        require(dev[c].dropna().isin([0, 1]).all(), 'Invalid binary feature ' + c)
    if enforce_frozen_counts:
        require(len(dev) == 1231631 and int(dev.Y_4Q.sum()) == 9246 and
                int(dev.loc[dev.Y_4Q.eq(1), 'CERT'].nunique()) == 2410,
                'Frozen development counts differ')

    validation = temporal_protocol_dict['validation']
    folds = validation['folds']
    require(validation['embargo_calendar_quarters'] == 4,
            'Protocol must contain a four-quarter embargo')
    if enforce_frozen_counts:
        require({f['id'] for f in folds} == set(FROZEN_COUNTS),
                'Frozen fold identifiers differ')
    feature_policy = temporal_protocol_dict.get('feature_policy', {})
    require(set(feature_policy.get('tier1_features', FEATURES)) == set(FEATURES),
            'Protocol feature set differs')
    expected = pd.read_csv(expected_param_csv)
    needed = {'fold', 'clip', 'feature'} | set(PARAM_FIELDS)
    require(needed.issubset(expected.columns), 'Archived parameter columns missing')
    expected['clip'] = expected['clip'].map(_clip_bool)
    require(not expected.duplicated(['fold', 'clip', 'feature']).any(),
            'Duplicate archived parameter key')
    required_keys = {(f['id'], mode, c) for f in folds
                     for mode in (False, True) for c in CONTINUOUS}
    observed_keys = set(expected[['fold', 'clip', 'feature']].itertuples(index=False, name=None))
    require(required_keys == observed_keys, 'Incomplete/unexpected archived parameter keys')
    expected = expected.set_index(['fold', 'clip', 'feature'])
    rows, differences, fold_rows = [], [], []
    for f in folds:
        name = f['id']
        end = pd.Timestamp(f['train_end'])
        start = pd.Timestamp(f['validation_start'])
        finish = pd.Timestamp(f['validation_end'])
        gap = start.to_period('Q').ordinal - end.to_period('Q').ordinal - 1
        require(gap == 4 and finish <= pd.Timestamp('2008-12-31'),
                name + ': invalid temporal fold dates')
        train = dev.loc[dev.DECISION_DATE.le(end)]
        valid = dev.loc[dev.DECISION_DATE.between(start, finish)]
        require(len(train) > 0 and len(valid) > 0, name + ': empty fold')
        require(train.DECISION_DATE.max() + pd.offsets.QuarterEnd(4) < valid.DECISION_DATE.min(),
                name + ': training-label horizon overlaps validation')
        actual_counts = (len(train), len(valid), int(train.Y_4Q.sum()),
                         int(valid.Y_4Q.sum()),
                         int(train.loc[train.Y_4Q.eq(1), 'CERT'].nunique()),
                         int(valid.loc[valid.Y_4Q.eq(1), 'CERT'].nunique()))
        if enforce_frozen_counts:
            require(actual_counts == FROZEN_COUNTS[name], name + ': archived fold counts differ')
        for mode in (False, True):
            params = continuous_parameters(train[CONTINUOUS], valid[CONTINUOUS], mode)
            snapshot = [p.copy() for p in params]
            transformed = transform_numpy(valid.head(128), params, mode)
            require(transformed.shape == (min(128, len(valid)), 30) and
                    np.isfinite(transformed).all(), 'Invalid 30-column preprocessing sample')
            require(params == snapshot, 'Transform mutated training parameters')
            for c, p in zip(CONTINUOUS, params):
                row = {'fold': name, 'clip': mode, 'feature': c, **p}
                row_ok = True
                for metric in PARAM_FIELDS:
                    reference = float(expected.loc[(name, mode, c), metric])
                    observed = p[metric]
                    if metric.endswith('_count'):
                        same = observed == reference
                    else:
                        same = bool(np.isclose(observed, reference, rtol=1e-10,
                                               atol=1e-12, equal_nan=True))
                    if not same:
                        row_ok = False
                        differences.append({'fold': name, 'clip': mode, 'feature': c,
                                            'statistic': metric, 'observed': observed,
                                            'archived': reference})
                row['status'] = 'PASS' if row_ok else 'FAIL'
                rows.append(row)
            fold_rows.append({
                'fold': name, 'clip': mode, 'train_rows': actual_counts[0],
                'validation_rows': actual_counts[1], 'train_positive_rows': actual_counts[2],
                'validation_positive_rows': actual_counts[3],
                'train_positive_certs': actual_counts[4],
                'validation_positive_certs': actual_counts[5],
                'embargo_quarters': gap, 'transformed_width': transformed.shape[1],
                'validation_transform_does_not_mutate_parameters': True,
            })
    summary = {
        'status': 'FAIL' if differences else 'PASS',
        'scope': ('FROZEN_DEVELOPMENT_FOLD_PARAMETERS' if enforce_frozen_counts
                  else 'SYNTHETIC_TEST_ONLY'),
        'rows_compared': len(rows), 'statistics_compared': len(rows) * len(PARAM_FIELDS),
        'mismatches': len(differences), 'continuous_features': CONTINUOUS,
        'binary_features': BINARY, 'transformed_columns_in_exact_order': OUTPUT_COLUMNS,
        'original_missing_flags_before_imputation': True,
        'no_sklearn_import': True, 'no_classifier_fit': True, 'no_model_load': True,
        'no_final_test_read': True, 'no_inference': True,
        'evidence_limit': ('Checks original archived preprocessing summaries and an independent '
                           'NumPy transform. Does not inspect fitted model internals or compare '
                           'an archived sklearn/Spark transformed design matrix.'),
    }
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    for filename, data in [('fold_preprocessing_recomputed.csv', rows),
                           ('fold_preprocessing_comparisons.csv', differences),
                           ('fold_preprocessing_temporal_counts.csv', fold_rows)]:
        with (output / filename).open('x', encoding='utf-8-sig', newline='') as handle:
            pd.DataFrame(data).to_csv(handle, index=False)
    with (output / 'fold_preprocessing_summary.json').open('x', encoding='utf-8') as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False, allow_nan=False)
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dev', type=Path, required=True)
    ap.add_argument('--expected-params', type=Path, required=True)
    ap.add_argument('--protocol', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    inputs = [args.dev.resolve(), args.expected_params.resolve(), args.protocol.resolve()]
    target = args.out.resolve()
    require(all(not target.is_relative_to(p.parent) for p in inputs),
            'Output must be outside every original input directory')
    require(sha256(args.dev) == DEV_SHA256, 'Frozen development SHA256 differs; STOP')
    require(sha256(args.protocol) == PROTOCOL_SHA256, 'Frozen protocol SHA256 differs; STOP')
    before = {str(p): sha256(p) for p in inputs}
    protocol = json.loads(args.protocol.read_text(encoding='utf-8-sig'))
    summary = verify_fold_preprocessing(pd.read_parquet(args.dev), args.expected_params,
                                        protocol, args.out)
    require(all(sha256(p) == h for p, h in before.items()), 'Input hash changed during audit')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
