#!/usr/bin/env python3
"""BFT65B Part 4 v2 — DEVELOPMENT-ONLY label-policy correction and adversarial PIT checks.

Read-only with respect to existing panels, original Step01 artifacts and test.
Uses the exact *recorded* Step01 financial feature builder, then creates a new
versioned DEVELOPMENT-ONLY primary binary label. Future events are used ONLY for
supervised outcome ascertainment, never as predictors.

Primary 4Q label: qualifying first FAILURE -> 1; observed nonfailure -> 0;
confirmed merger, assistance-only/resolution and voluntary closure -> 0;
unresolved adverse exit, unknown followup and event-date conflicts -> NULL.
Legacy censoring policy is retained as a development-only sensitivity cohort.
An assistance-positive scenario is only generated when an independently
verified CERT/ASSISTANCE_DATE event file is explicitly provided; no event
identities or dates are invented.

As-of leakage check: for selected decision quarters, rerun the ACTUAL Step01
feature construction from (i) original inputs, (ii) inputs truncated at each
source report date, (iii) inputs with financial observations *after* that date
poisoned. Values must agree at the specified decision date. This cannot prove
absence of retrospective revisions in today's FDIC snapshot.

Do not open, transform, predict or inspect the final-test feature table here.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

DEV_END = dt.date(2008, 12, 31)
CONFIRMED_NONFAILURE_EXIT_CLASSES = (
    'MERGER_OR_REORGANIZATION_NONFAILURE',
    'ASSISTED_OR_RESOLUTION_EXIT',
    'VOLUNTARY_CLOSURE_NONFAILURE',
)


def require(ok, reason):
    if not bool(ok):
        raise AssertionError(reason)


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(8 * 1024 * 1024),b''):
            h.update(chunk)
    return h.hexdigest()


def load_original_step01(source):
    spec=importlib.util.spec_from_file_location('part4_original_reference', str(source))
    require(spec is not None and spec.loader is not None,'Cannot load the original Step01 source')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    needed=('load_registry','prepare_source_columns','feature_expressions',
            'add_outcome_and_status','RAW_REPORT_FIELDS','FEATURES')
    require(all(hasattr(module,x) for x in needed),'Original Step01 code missing required public functions')
    return module


def to_date(value):
    if isinstance(value,dt.datetime):return value.date()
    return value


def feature_equal(left: pl.DataFrame, right: pl.DataFrame, features: list[str], context: str):
    keys=['CERT','DECISION_DATE']
    require(left.select(keys).unique().height==left.height, f'{context}: duplicate left keys')
    require(right.select(keys).unique().height==right.height, f'{context}: duplicate right keys')
    a=left.select(keys+features).sort(keys)
    b=right.select(keys+features).sort(keys)
    require(a.height==b.height, f'{context}: row-count difference {a.height} vs {b.height}')
    require(a.select(keys).equals(b.select(keys)), f'{context}: key mismatch')
    differences={}
    for f in features:
        x=a[f].cast(pl.Float64).to_numpy()
        y=b[f].cast(pl.Float64).to_numpy()
        bad=~np.isclose(x,y,rtol=1e-9,atol=1e-10,equal_nan=True)
        if bad.any(): differences[f]=int(bad.sum())
    require(not differences, f'{context}: feature mismatches {differences}')
    return int(a.height * len(features))


def select_quarters_for_asof(result: pl.DataFrame, max_quarters: int):
    counts=(result.group_by('DECISION_DATE').agg(
        pl.len().alias('n'),
        (pl.col('LABEL_STATUS') == 'POSITIVE').sum().alias('p')
    ).sort('DECISION_DATE'))
    dates=counts['DECISION_DATE'].to_list()
    require(bool(dates),'No development decision quarters')
    # Spread across full history + include the highest-failure quarters.
    evenly=[dates[round(x)] for x in np.linspace(0,len(dates)-1,max_quarters).tolist()]
    hot=counts.sort('p',descending=True).head(min(4,max_quarters))['DECISION_DATE'].to_list()
    chosen=[]
    for d in hot+evenly:
        if d not in chosen:chosen.append(d)
    return sorted(chosen)


def adversarial_asof_check(args, module, dev_all: pl.DataFrame, features: list[str], out_dir: Path):
    if args.asof_quarters == 0:
        return {'status':'NOT_REQUESTED','quarters_checked':0,'comparisons':0}
    dates=select_quarters_for_asof(dev_all, args.asof_quarters)
    # Retain source of truth; input financial observations are never modified.
    clean=pl.read_parquet(args.clean,columns=['CERT','REPDTE','ASSET'])
    pit_scan=pl.scan_parquet(args.pit)
    audit=[]
    total=0
    for q in dates:
        q=to_date(q)
        pool=(dev_all.filter(pl.col('DECISION_DATE')==q)
              .select(['CERT','DECISION_DATE','LABEL_STATUS']+features))
        pos=pool.filter(pl.col('LABEL_STATUS')=='POSITIVE').head(200)
        neg=pool.filter(pl.col('LABEL_STATUS')=='NEGATIVE').head(150)
        other=pool.filter(~pl.col('LABEL_STATUS').is_in(['POSITIVE','NEGATIVE'])).head(50)
        chosen=pl.concat([pos,neg,other])
        if chosen.is_empty():continue
        certs=chosen['CERT'].to_list()
        # The PIT subset is exactly the decision cohort being challenged.
        pit=(pit_scan.filter(pl.col('DECISION_DATE')==pl.lit(q))
             .filter(pl.col('CERT').is_in(certs))
             .select(module.RAW_REPORT_FIELDS).collect())
        require(pit.height==chosen.height,f'{q}: source PIT subset cardinality changed')
        cut=to_date(pit['SOURCE_REPDTE'][0])
        require((pit['SOURCE_REPDTE']==cut).all(), f'{q}: inconsistent source cutoff')
        require(cut < q, f'{q}: source not earlier than decision')
        base=clean.filter(pl.col('CERT').is_in(certs))
        future=base.filter(pl.col('REPDTE')>pl.lit(cut)).height
        truncated=base.filter(pl.col('REPDTE')<=pl.lit(cut))
        poisoned=base.with_columns(
            pl.when(pl.col('REPDTE') > pl.lit(cut))
              .then(-11.0 * pl.col('ASSET').cast(pl.Float64).fill_null(0.0) + 37.0)
              .otherwise(pl.col('ASSET').cast(pl.Float64)).alias('ASSET')
        )
        with tempfile.TemporaryDirectory(prefix='bft65b_pit_',dir=str(out_dir)) as td:
            td=Path(td)
            pp=td/'PIT.parquet';pit.write_parquet(pp)
            outputs={}
            for name,frame in [('original',base),('truncated',truncated),('future_poisoned',poisoned)]:
                cp=td/f'{name}_clean.parquet';frame.write_parquet(cp)
                calc=(module.prepare_source_columns(pp,cp)
                      .with_columns(module.feature_expressions())
                      .select(['CERT','DECISION_DATE']+features).collect())
                outputs[name]=calc
            n_original=feature_equal(outputs['original'],chosen,features,f'{q} original vs recorded')
            n_trunc=feature_equal(outputs['original'],outputs['truncated'],features,f'{q} truncate')
            n_poison=feature_equal(outputs['original'],outputs['future_poisoned'],features,f'{q} poison')
            require(n_original==n_trunc==n_poison,f'{q}: comparison cardinality mismatch')
        audit.append({'decision_date':str(q),'source_cutoff':str(cut),
                      'sample_rows':int(chosen.height),'positive_sample_rows':int(pos.height),
                      'post_cutoff_clean_rows_poisoned':int(future),
                      'feature_cells_compared_per_variant':int(n_original),
                      'mismatches_after_truncation':0,'mismatches_after_poison':0})
        total+=2*n_original
        print(f'[PIT as-of] {q}: {chosen.height} rows, {future} future source rows poisoned; PASS',flush=True)
    pd.DataFrame(audit).to_csv(out_dir/'asof_future_poison_audit.csv',index=False)
    require(bool(audit),'No as-of quarters actually checked')
    require(sum(x['post_cutoff_clean_rows_poisoned'] for x in audit)>0,
            'Poison test did not alter any future financial source rows')
    return {'status':'PASS','quarters_checked':len(audit),'comparisons':total,
            'positive_samples_total':sum(x['positive_sample_rows'] for x in audit),
            'future_rows_poisoned':sum(x['post_cutoff_clean_rows_poisoned'] for x in audit)}


def full_pit_source_value_parity(clean_path:Path,pit_path:Path,module):
    """Recheck EVERY dev PIT raw financial field against its exact q−1 clean source.

    Unlike the future-poison test, this also catches fields already baked into
    the prepared PIT input from an incorrect reporting quarter. No outcome
    registry or final-test feature table is involved.
    """
    metadata={'CERT','SOURCE_REPDTE','DECISION_DATE'}
    fields=[x for x in module.RAW_REPORT_FIELDS if x not in metadata]
    clean=pl.scan_parquet(clean_path)
    missing=set(fields)-set(clean.collect_schema().names())
    require(not missing,f'Clean source is missing raw parity fields: {sorted(missing)}')
    observed=(clean.select('CERT',pl.col('REPDTE').alias('SOURCE_REPDTE'),*fields)
                 .with_columns(pl.lit(1,dtype=pl.Int8).alias('_EXACT_SOURCE_FOUND')))
    dev=(pl.scan_parquet(pit_path)
         .filter(pl.col('DECISION_DATE')<=pl.lit(DEV_END))
         .select(module.RAW_REPORT_FIELDS))
    joined=dev.join(observed,on=['CERT','SOURCE_REPDTE'],how='left',validate='m:1',suffix='_CLEAN')
    # Expression-based counts avoid exporting large raw bank rows.
    checks=[pl.len().alias('_DEV_ROWS'),
            pl.col('_EXACT_SOURCE_FOUND').is_null().sum().alias('_MISSING_SOURCE_KEY')]
    for f in fields:
        a=pl.col(f).cast(pl.Float64).fill_nan(None)
        b=pl.col(f+'_CLEAN').cast(pl.Float64).fill_nan(None)
        same=((a.is_null() & b.is_null()) |
              (a.is_not_null() & b.is_not_null() &
               ((a-b).abs() <= (1e-9 + 1e-8*b.abs()))))
        checks.append((~same.fill_null(False)).sum().alias(f+'_mismatch'))
    row=joined.select(checks).collect().to_dicts()[0]
    require(row['_MISSING_SOURCE_KEY']==0,
            f'PIT source join missing exact (CERT,SOURCE_REPDTE) keys: {row["_MISSING_SOURCE_KEY"]}')
    errors={f:int(row[f+'_mismatch']) for f in fields}
    require(not any(errors.values()),f'Prepared PIT raw values differ from clean q-1 source: {errors}')
    return {'status':'PASS','source_value_rows_checked':int(row['_DEV_ROWS']),
            'source_fields_checked':len(fields),'field_mismatch_counts':errors}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--clean',type=Path,required=True)
    ap.add_argument('--pit',type=Path,required=True)
    ap.add_argument('--registry-zip',type=Path,required=True)
    ap.add_argument('--step01-source',type=Path,required=True)
    ap.add_argument('--out-dir',type=Path,required=True)
    ap.add_argument('--pandas-oracle-source',type=Path,default=None,
                    help='Independent pandas Step03 oracle source, for full-v2 formula verification')
    ap.add_argument('--old-dev',type=Path,default=None,
                    help='Optional prior development features Parquet for unchanged-row parity')
    ap.add_argument('--asof-quarters',type=int,default=12,
                    help='Number of evenly spaced development quarters, plus four high-failure quarters')
    ap.add_argument('--assistance-events-csv',type=Path,default=None,
                    help='Optional verified CSV with CERT,ASSISTANCE_DATE, one or more events per CERT')
    ap.add_argument('--production-only', action='store_true',
                    help='Regenerate the development cohort only; do not repeat closed source/oracle/canary audits.')
    args=ap.parse_args()
    if args.production_only:
        require(args.asof_quarters == 0, '--production-only requires --asof-quarters 0; closed canary must not run.')
        require(args.pandas_oracle_source is None and args.old_dev is None and args.assistance_events_csv is None,
                '--production-only does not accept oracle, old-dev or assistance sensitivity inputs.')
    require(args.asof_quarters>=0, 'asof-quarters must be >=0')
    for file in [args.clean,args.pit,args.registry_zip,args.step01_source]:
        require(file.is_file(),f'Missing input file: {file}')
    args.out_dir = args.out_dir.expanduser().resolve()
    require(not args.out_dir.exists(), 'Output directory already exists; choose a NEW isolated --out-dir.')
    args.out_dir.mkdir(parents=True,exist_ok=False)
    module=load_original_step01(args.step01_source)
    registry,summary=module.load_registry(args.registry_zip)
    print('[1/4] Construct development-only financial features and original statuses...',flush=True)
    source=module.prepare_source_columns(args.pit,args.clean).filter(
        pl.col('DECISION_DATE') <= pl.lit(DEV_END))
    base=source.with_columns(module.feature_expressions())
    result=module.add_outcome_and_status(base,registry).collect()
    require(result.height>0,'Empty development cohort')
    require(result.select('CERT','DECISION_DATE').unique().height==result.height,'Duplicate keys')
    require(result['SPLIT'].eq('development').all(),'Non-development row entered audit')
    require((result['SOURCE_REPDTE'].dt.offset_by('3mo').dt.month_end()==result['DECISION_DATE']).all(),
            'Source reporting quarter not exactly 1Q before decision')
    features=list(module.FEATURES)
    assert len(features)==15
    require(not any(x in features for x in ['FIRST_FAILURE_DATE','RISK_STOP_DATE','EXIT_CLASS']),
            'Outcome variable in feature allowlist')
    if args.production_only:
        source_parity={'status':'CLOSED_PRIOR_NOT_RERUN'}
    else:
        print('[PIT] Independent full development q-1 source-value parity...',flush=True)
        source_parity=full_pit_source_value_parity(args.clean,args.pit,module)
    print('[2/4] Correct primary label policy without treating unknown exits as negatives...',flush=True)
    confirmed=(pl.col('LABEL_STATUS')=='COMPETING_EXIT_CENSORED') & (
        pl.col('EXIT_CLASS').is_in(CONFIRMED_NONFAILURE_EXIT_CLASSES))
    result=result.with_columns([
        pl.when(pl.col('LABEL_STATUS')=='POSITIVE').then(pl.lit(1,dtype=pl.Int8))
          .when((pl.col('LABEL_STATUS')=='NEGATIVE') | confirmed)
          .then(pl.lit(0,dtype=pl.Int8))
          .otherwise(pl.lit(None,dtype=pl.Int8)).alias('Y_PRIMARY_4Q'),
        pl.when(confirmed).then(pl.lit('CONFIRMED_NONFAILURE_EXIT_NEGATIVE'))
          .otherwise(pl.col('LABEL_STATUS')).alias('PRIMARY_LABEL_STATUS'),
    ])
    # No test labels or features are read or written.
    model_cols=['CERT','DECISION_DATE','SOURCE_REPDTE','SPLIT']+features
    primary=(result.filter(pl.col('Y_PRIMARY_4Q').is_not_null())
             .select(model_cols+[pl.col('Y_PRIMARY_4Q').alias('Y_4Q')]))
    old=(result.filter(pl.col('Y_4Q').is_not_null()).select(model_cols+['Y_4Q']))
    if args.old_dev and args.old_dev.exists():
        recorded=pl.read_parquet(args.old_dev)
        require(recorded.height==old.height, 'Recorded old development row count differs')
        require(int(recorded['Y_4Q'].sum())==int(old['Y_4Q'].sum()),'Recorded old label total differs')
        feature_equal(recorded,old,features,'existing Step01 development vs rerun')
        key=['CERT','DECISION_DATE']
        pair=(recorded.select(key+['Y_4Q'])
              .join(old.select(key+[pl.col('Y_4Q').alias('Y_OLD_RERUN')]),
                    on=key,how='full',coalesce=True,validate='1:1'))
        require(pair.height==old.height and
                pair.filter(pl.col('Y_4Q').is_null() | pl.col('Y_OLD_RERUN').is_null() |
                            (pl.col('Y_4Q')!=pl.col('Y_OLD_RERUN'))).height==0,
                'Recorded old positive/negative label differs at institution-quarter level')
    y_primary=primary['Y_4Q']
    require(primary.height>=old.height,'Primary policy unexpectedly discarded known original outcomes')
    require(int(y_primary.sum())==int(old['Y_4Q'].sum()),
            'Changing confirmed nonfailure exits unexpectedly changed failure positives')
    if args.production_only:
        policy_mismatch=None
        independent={'status':'CLOSED_PRIOR_NOT_RERUN'}
    else:
        # A separate pandas adjudicator must agree with the policy on EVERY dev row.
        label_pd=result.select('LABEL_STATUS','EXIT_CLASS','Y_PRIMARY_4Q').to_pandas()
        s_pd=label_pd['LABEL_STATUS'].astype('string')
        e_pd=label_pd['EXIT_CLASS'].astype('string')
        y_expected=np.select([
            s_pd.eq('POSITIVE').fillna(False).to_numpy(dtype=bool),
            (s_pd.eq('NEGATIVE') | (
               s_pd.eq('COMPETING_EXIT_CENSORED') &
               e_pd.isin(CONFIRMED_NONFAILURE_EXIT_CLASSES))).fillna(False).to_numpy(dtype=bool),
        ],[1.,0.],default=np.nan)
        y_actual=label_pd['Y_PRIMARY_4Q'].astype(float).to_numpy()
        policy_mismatch=int((~np.isclose(y_expected,y_actual,equal_nan=True)).sum())
        require(policy_mismatch==0, f'Pandas-vs-Polars primary label policy mismatches: {policy_mismatch}')
        # Formula-level oracle: independent pandas and quarter-ID joins on all NEW dev rows.
        independent={'status':'NOT_RUN_NO_ORACLE_SOURCE'}
        if args.pandas_oracle_source is not None:
            require(args.pandas_oracle_source.is_file(),'Missing independent pandas oracle source')
            spec=importlib.util.spec_from_file_location('independent_pandas_oracle',str(args.pandas_oracle_source))
            oracle=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(oracle)
            clean_pd=pd.read_parquet(args.clean,columns=['CERT','REPDTE','ASSET'])
            clean_pd=clean_pd.loc[pd.to_datetime(clean_pd['REPDTE']) <= pd.Timestamp(DEV_END)]
            raw_pd=result.select(module.RAW_REPORT_FIELDS).to_pandas()
            reference=oracle.independent_features(raw_pd,clean_pd)
            actual=result.select(features).to_pandas()
            mismatch={}
            for f in features:
                x=pd.to_numeric(actual[f],errors='coerce').to_numpy(dtype=float)
                y=pd.to_numeric(reference[f],errors='coerce').to_numpy(dtype=float)
                mismatch[f]=int((~np.isclose(x,y,rtol=1e-8,atol=1e-9,equal_nan=True)).sum())
            require(not any(mismatch.values()),f'Independent pandas-vs-Polars formula mismatch: {mismatch}')
            independent={'status':'PASS','rows':len(result),'compared_feature_cells':len(result)*len(features),
                         'feature_mismatches':mismatch,'pandas_oracle_code_sha256':sha256(args.pandas_oracle_source)}
            del clean_pd,raw_pd,reference,actual
    status=(result.group_by('LABEL_STATUS','EXIT_CLASS','PRIMARY_LABEL_STATUS')
           .agg(pl.len().alias('rows'),pl.col('CERT').n_unique().alias('distinct_certs'))
           .sort('LABEL_STATUS','EXIT_CLASS'))
    status.write_csv(args.out_dir/'dev_old_vs_primary_status.csv')
    by_quarter=(result.group_by('DECISION_DATE','PRIMARY_LABEL_STATUS').agg(pl.len().alias('rows'))
                .sort('DECISION_DATE','PRIMARY_LABEL_STATUS'))
    by_quarter.write_csv(args.out_dir/'dev_primary_by_quarter.csv')
    primary.write_parquet(args.out_dir/'development_primary_binary_v2.parquet',compression='zstd')
    old.write_parquet(args.out_dir/'development_legacy_censor_sensitivity_v2.parquet',compression='zstd')
    counts={
        'all_development_rows':result.height,
        'legacy_labelled_rows':old.height,
        'legacy_positive_rows':int(old['Y_4Q'].sum()),
        'primary_labelled_rows':primary.height,
        'primary_positive_rows':int(y_primary.sum()),
        'primary_negative_rows':int(primary.height-y_primary.sum()),
        'confirmed_nonfailure_exit_rows_relabelled_zero':int(result.filter(confirmed).height),
        'still_unknown_or_conflicted_rows':int(result.height-primary.height),
    }
    require(sum([counts['primary_labelled_rows'],counts['still_unknown_or_conflicted_rows']])==result.height,
            'Reconciliation fails')
    # Optional FAIL+ASSISTANCE sensitivity; requires a verified independent event crosswalk.
    assistance={'status':'NOT_RUN_NO_VERIFIED_ASSISTANCE_DATES'}
    if args.assistance_events_csv is not None:
        require(args.assistance_events_csv.is_file(),'Missing assistance events CSV')
        ass=pl.read_csv(args.assistance_events_csv,try_parse_dates=True)
        require({'CERT','ASSISTANCE_DATE'}.issubset(set(ass.columns)),
                'Assistance crosswalk requires CERT and ASSISTANCE_DATE')
        ass=ass.with_columns(pl.col('CERT').cast(pl.Int64),
                             pl.col('ASSISTANCE_DATE').cast(pl.Date))
        ass=ass.filter(pl.col('ASSISTANCE_DATE').is_not_null())
        # Keep ALL events, rather than only the earliest assistance per bank.
        ass=ass.select('CERT','ASSISTANCE_DATE').unique()
        aux=result.select('CERT','DECISION_DATE').join(ass,on='CERT',how='left')
        qend=pl.col('DECISION_DATE').dt.offset_by('1y').dt.month_end()
        help_flags=(aux.with_columns(((pl.col('ASSISTANCE_DATE') > pl.col('DECISION_DATE'))
                            & (pl.col('ASSISTANCE_DATE')<=qend)).fill_null(False).alias('_ASSIST_IN_4Q'))
                    .group_by('CERT','DECISION_DATE')
                    .agg(pl.col('_ASSIST_IN_4Q').any().alias('_ANY_ASSIST')))
        ad=result.join(help_flags,on=['CERT','DECISION_DATE'],how='left',validate='1:1')
        # Recognized failure OR verified assistance inside horizon => 1.
        # Do not invent negatives for unresolved events or incomplete follow-up.
        ad=ad.with_columns(
           pl.when((pl.col('Y_PRIMARY_4Q')==1) | pl.col('_ANY_ASSIST'))
             .then(pl.lit(1,dtype=pl.Int8))
             .when(pl.col('Y_PRIMARY_4Q')==0).then(pl.lit(0,dtype=pl.Int8))
             .otherwise(pl.lit(None,dtype=pl.Int8)).alias('Y_FAILURE_OR_ASSISTANCE_4Q'))
        data=(ad.filter(pl.col('Y_FAILURE_OR_ASSISTANCE_4Q').is_not_null())
              .select(model_cols+[pl.col('Y_FAILURE_OR_ASSISTANCE_4Q').alias('Y_4Q')]))
        data.write_parquet(args.out_dir/'development_failure_assistance_SENSITIVITY.parquet',compression='zstd')
        assistance={'status':'GENERATED_REQUIRES_EVENT_CROSSWALK_PROVENANCE',
                    'labelled_rows':data.height,'positive_rows':int(data['Y_4Q'].sum()),
                    'assistance_event_csv_sha256':sha256(args.assistance_events_csv)}
    if args.production_only:
        poison={'status':'CLOSED_PRIOR_NOT_RERUN','quarters_checked':0,'comparisons':0}
        print('[3/4] Production-only replay: closed source/oracle/canary audits are not repeated.',flush=True)
    else:
        print('[3/4] Adversarial as-of source truncation and future-poison tests...',flush=True)
        poison=adversarial_asof_check(args,module,result,features,args.out_dir)
    print('[4/4] Final evidence writeout...',flush=True)
    audit={
        'stage':'PART4_V2_DEV_LABEL_AND_INPUT_PIT_AUDIT',
        'status':('PRODUCER_REPLAY_COMPLETE_COMPARISON_REQUIRED' if args.production_only else
                  ('PASS' if (poison['status']=='PASS' and independent['status']=='PASS' and source_parity['status']=='PASS') else 'INCOMPLETE')),
        'execution_mode':'PRODUCTION_ONLY' if args.production_only else 'FULL_AUDIT',
        'scope':'DEVELOPMENT_ONLY_NO_TEST_FEATURE_FILE_OPENED',
        'counts':counts,
        'full_pit_source_parity':source_parity,
        'independent_pandas_primary_label_policy_mismatches':policy_mismatch,
        'independent_formula_oracle':independent,
        'asof_future_poison':poison,
        'assistance_sensitivity':assistance,
        'strictly_training_only_preprocessing_required_for_all_part5_folds':True,
        'code_and_source_sha256':{
          'original_step01':sha256(args.step01_source),
          'clean':sha256(args.clean),'pit':sha256(args.pit),
          'registry':sha256(args.registry_zip),'this_script':sha256(Path(__file__))},
        'limitations':[
            'Primary-v2 policy treats confirmed nonfailure exits as binary negatives, but unresolved adverse exits, insufficient follow-up and inconsistent dates remain unknown.',
            'Future failure/exit information is used for outcome ascertainment only; it is never appended to the predictor allowlist.',
            'Financial as-of poison tests assess code-level time gating, not retrospective FDIC historical-vintage revisions.',
            'All previously recorded Step02-04 labels, fold counts and imputation statistics refer to the OLD censored policy and must NOT be reused as measurements for primary-v2.',
            'No final test feature file or final test labels are opened, modelled or compared in this program.',
        ],
    }
    (args.out_dir/'part4_v2_development_audit.json').write_text(
        json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf8')
    with zipfile.ZipFile(args.out_dir/'SHARE_THIS_PART4_V2_DEV_EVIDENCE.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in ['part4_v2_development_audit.json','dev_old_vs_primary_status.csv',
                     'dev_primary_by_quarter.csv']+(['asof_future_poison_audit.csv'] if args.asof_quarters else []):
            z.write(args.out_dir/name,name)
    print('PART4 V2 DEV AUDIT '+audit['status']+'; summary:',args.out_dir/'part4_v2_development_audit.json',flush=True)
    print('SHARE_THIS_PART4_V2_DEV_EVIDENCE.zip',flush=True)
    if args.production_only:
        print('Compare the regenerated DEVELOPMENT cohort with its immutable archived reference; closed audits were not repeated.',flush=True)
    else:
        print('IMPORTANT: Step02/03 preprocessing audits must be repeated for the NEW primary-v2 development cohort.',flush=True)
        require(audit['status']=='PASS','Full as-of and independent formula checks must PASS to close the v2 gate')


if __name__=='__main__':
    main()
