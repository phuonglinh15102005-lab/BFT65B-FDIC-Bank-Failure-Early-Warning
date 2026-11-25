"""Verify supplied 2A/2B/2C review bundles without reading full financial values.

Requires polars plus the reviewed 02b/02c scripts beside this file.
Run with --step2a-zip, --step2b-zip, --step2c-zip and --out DIRECTORY.
Reconstructed keys do not establish equality of the underlying financial values.
AI assistance: ChatGPT, 9 November 2026.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import date
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PureWindowsPath
import zipfile
import polars as pl


def load_module():
    p=Path(__file__).with_name('02c_finalize_panel.py')
    spec=importlib.util.spec_from_file_location('stage2c',p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m


def rows(z,name):
    return list(csv.DictReader(io.StringIO(z.read(name).decode('utf-8-sig'))))


def json_member(z,name):
    return json.loads(z.read(name))


def frame(z,name):
    return pl.read_csv(io.BytesIO(z.read(name)),try_parse_dates=True,infer_schema_length=None)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--step2a-zip',type=Path,required=True)
    ap.add_argument('--step2b-zip',type=Path,required=True)
    ap.add_argument('--step2c-zip',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();args.out.mkdir(exist_ok=True,parents=True)
    m=load_module();checks=[]
    def check(name,ok):
        if not ok:raise AssertionError(name)
        checks.append({'check':name,'result':'PASS'})
    with zipfile.ZipFile(args.step2a_zip) as za,zipfile.ZipFile(args.step2b_zip) as zb,zipfile.ZipFile(args.step2c_zip) as zc:
        check('ZIP member integrity',all(z.testzip() is None for z in [za,zb,zc]))
        sa=json_member(za,'step2_summary.json');sb=json_member(zb,'step2b_summary.json');sc=json_member(zc,'step2c_summary.json');cfg=json_member(zc,'step2c_config.json')
        check('Reviewed producer script',cfg['script_sha256']==m.sha(Path(__file__).with_name('02c_finalize_panel.py')))
        for name,expected in cfg['step2b_inputs'].items():
            data=args.step2b_zip.read_bytes() if name=='part2_review_bundle.zip' else zb.read('/'.join(PureWindowsPath(name).parts))
            check('2B lineage '+name,hashlib.sha256(data).hexdigest()==expected)
        check('Common input panel identity',sa['panel_sha256']==sb['source_panel_sha256_recorded_in_step2A']==cfg['panel_sha256'])
        coverage=rows(za,'review_AUDIT_ONLY/bank_coverage_AUDIT_ONLY.csv')
        metadata=rows(zb,'review_AUDIT_ONLY/financial_metadata_AUDIT_ONLY.csv')
        history=rows(zb,'review_AUDIT_ONLY/history_events_AUDIT_ONLY.csv')
        failures=rows(za,'review_AUDIT_ONLY/failure_event_coverage.csv')
        by=defaultdict(list)
        for r in metadata:by[int(r['CERT'])].append(m.parse_date(r['REPDTE']))
        reconstructed=[]
        for r in coverage:
            cert=int(r['CERT']);first=m.parse_date(r['FIRST_REPDTE']);last=m.parse_date(r['LAST_REPDTE'])
            if int(r['INTERNAL_MISSING_QUARTERS'])>0:
                dates=sorted(by[cert])
            else:
                dates=[]
                for i in range(first.year*4+(first.month-1)//3,last.year*4+(last.month-1)//3+1):
                    y,q=divmod(i,4);mo,day=[(3,31),(6,30),(9,30),(12,31)][q];dates.append(date(y,mo,day))
            if len(dates)!=int(r['OBSERVED_QUARTERS']) or dates[0]!=first or dates[-1]!=last:
                raise AssertionError('Cannot reconstruct coverage '+str(cert))
            reconstructed.extend((cert,d) for d in dates)
        keys=pl.DataFrame(reconstructed,schema={'CERT':pl.Int64,'REPDTE':pl.Date},orient='row')
        check('Reconstructed source key count and uniqueness',keys.height==sa['rows_output']==keys.unique().height)
        reg=m.registry_frame(m.build_registry(coverage,history,failures)[0])
        actual_reg=frame(zc,'review_AUDIT_ONLY/bank_event_registry_AUDIT_ONLY.csv')
        check('Registry bank count and uniqueness',actual_reg.height==sa['banks']==actual_reg['CERT'].n_unique())
        cols=['CERT','EXIT_CLASS','EXIT_SOURCE','EXIT_DATE','RISK_STOP_DATE','FIRST_FAILURE_DATE','ELIGIBILITY_END']
        check('Event rules reproduced from 2A and 2B',reg.select(cols).sort('CERT').equals(actual_reg.select(cols).sort('CERT')))
        scope=frame(zc,'review_AUDIT_ONLY/insurance_scope_exceptions.csv')
        check('Scope exceptions present in source keys',scope.select('CERT','REPDTE').join(keys,on=['CERT','REPDTE'],how='anti').height==0)
        check('Scope exception evidence consistent',scope.height==11598 and scope.filter((pl.col('INSFDIC_OBSERVED')!=0)|(pl.col('INSAGNT1_OBSERVED')!='NONE')|(pl.col('BKCLASS_OBSERVED')!='NC')).height==0)
        decisions=m.row_decisions(keys,reg,scope)
        excluded=decisions.filter(pl.col('ROW_ACTION')!='RETAIN')
        actual_exc=frame(zc,'review_AUDIT_ONLY/excluded_rows_AUDIT_ONLY.csv')
        cols=['CERT','REPDTE','ROW_ACTION']
        check('Every exclusion key and reason reproduced',excluded.select(cols).sort('CERT','REPDTE').equals(actual_exc.select(cols).sort('CERT','REPDTE')))
        check('Exclusion keys unique',actual_exc.height==actual_exc.select('CERT','REPDTE').unique().height)
        actions=decisions.group_by('ROW_ACTION').agg(pl.len().alias('rows')).sort('ROW_ACTION')
        check('Exclusive row accounting',actions.to_dicts()==sc['row_accounting'])
        clean=decisions.filter(pl.col('ROW_ACTION')=='RETAIN').select('CERT','REPDTE')
        check('Clean panel dimensions',clean.height==sc['clean_rows'] and clean['CERT'].n_unique()==sc['clean_banks'] and clean['REPDTE'].n_unique()==sc['clean_quarters'])
        quarter_actions=decisions.group_by('REPDTE','ROW_ACTION').agg(pl.len().alias('rows')).sort('REPDTE','ROW_ACTION')
        actual_q=frame(zc,'review_AUDIT_ONLY/row_accounting_by_quarter.csv')
        check('Every quarter accounting reproduced',quarter_actions.equals(actual_q.sort('REPDTE','ROW_ACTION')))
        pit=m.decision_base(clean,reg,1);pit2=m.decision_base(clean,reg,2)
        check('Decision counts both calendar lags',pit.height==sc['decision_rows_lag1'] and pit2.height==sc['decision_rows_lag2'])
        check('Decision banks and bounds',pit['CERT'].n_unique()==sc['decision_banks_lag1'] and str(pit['DECISION_DATE'].min())==sc['decision_start'] and str(pit['DECISION_DATE'].max())==sc['decision_end'])
        pq=pit.group_by('DECISION_DATE').agg(pl.len().alias('rows')).sort('DECISION_DATE')
        check('Every decision quarter count reproduced',pq.equals(frame(zc,'review_AUDIT_ONLY/decision_rows_by_quarter.csv').sort('DECISION_DATE')))
        before={r['column']:r for r in rows(za,'review_AUDIT_ONLY/numeric_profile.csv')}
        after=rows(zc,'review_AUDIT_ONLY/numeric_profile_after.csv')
        miss=rows(zc,'review_AUDIT_ONLY/missingness_after_by_quarter.csv')
        check('Missingness quarterly denominators',sum(int(r['rows']) for r in miss)==sc['clean_rows'] and len(miss)==170)
        check('Numeric profiles reconcile with quarterly null counts',all(sum(int(q[r['column']]) for q in miss)==int(r['null']) and int(r['rows'])==sc['clean_rows'] for r in after))
        check('No nonfinite values recorded',all(int(r['nonfinite'])==0 for r in after))
        signs=frame(zc,'review_AUDIT_ONLY/negative_stock_values_REVIEW.csv')
        check('Flagged negative stock cells are retained keys',signs.select('CERT','REPDTE').join(clean,on=['CERT','REPDTE'],how='anti').height==0 and signs.filter(pl.col('value')>=0).height==0)
        count_signs=dict(signs.group_by('column').len().iter_rows())
        check('Negative cell counts reconcile',all(count_signs[c]==int(next(r['negative'] for r in after if r['column']==c)) for c in count_signs))
        gaps=clean.group_by('CERT').agg(pl.col('REPDTE').min().alias('first'),pl.col('REPDTE').max().alias('last'),pl.len().alias('observed'))
        gaps=gaps.with_columns(((pl.col('last').dt.year()-pl.col('first').dt.year())*4+pl.col('last').dt.quarter().cast(pl.Int32)-pl.col('first').dt.quarter().cast(pl.Int32)+1-pl.col('observed')).alias('internal_missing_quarters')).filter(pl.col('internal_missing_quarters')>0)
        cols=['CERT','first','last','observed','internal_missing_quarters']
        check('Internal gap report reproduced',gaps.select(cols).sort('CERT').equals(frame(zc,'review_AUDIT_ONLY/internal_gaps_after.csv').select(cols).sort('CERT')))
        pos=pit.join(reg.select('CERT','FIRST_FAILURE_DATE'),on='CERT',how='left').filter((pl.col('FIRST_FAILURE_DATE')>pl.col('DECISION_DATE'))&(pl.col('FIRST_FAILURE_DATE')<=pl.col('DECISION_DATE').dt.offset_by('1y').dt.month_end()))
        pos=pos.group_by('CERT','FIRST_FAILURE_DATE').agg(pl.len().alias('eligible_decisions_in_positive_window')).sort('FIRST_FAILURE_DATE','CERT')
        check('First failure coverage is diagnostic not test event count',pos.equals(frame(zc,'review_AUDIT_ONLY/first_failure_positive_window_coverage_AUDIT_ONLY.csv').sort('FIRST_FAILURE_DATE','CERT')) and pos.height==sc['first_failure_events_with_eligible_positive_window'])
        check('Corrected history date cases retained',clean.filter(pl.col('CERT').is_in([35054,35493])).height==66)
        sample_flow=clean.join(reg.select('CERT','RISK_STOP_DATE','ELIGIBILITY_END'),on='CERT').with_columns(pl.col('REPDTE').dt.offset_by('3mo').dt.month_end().alias('q'))
        sample_flow=sample_flow.with_columns(pl.when(pl.col('q')>pl.lit(m.MODEL_END)).then(pl.lit('Beyond 2025Q2 decision cutoff')).when(pl.col('RISK_STOP_DATE').is_not_null()&(pl.col('q')>=pl.col('RISK_STOP_DATE'))).then(pl.lit('At or after evidenced risk stop')).when(pl.col('q')>pl.col('ELIGIBILITY_END')).then(pl.lit('Beyond unresolved follow-up bound')).otherwise(pl.lit('Retained decision')).alias('decision_action'))
        flow=sample_flow.group_by('decision_action').len().sort('decision_action')
        flow.write_csv(args.out/'decision_flow_recomputed.csv')
        stats={'clean_rows':clean.height,'clean_banks':clean['CERT'].n_unique(),'decision_rows':pit.height,'decision_banks':pit['CERT'].n_unique(),
               'excluded_fraction_pct':100*excluded.height/keys.height,'gap_banks_after':gaps.height,'gap_quarters_after':int(gaps['internal_missing_quarters'].sum()),
               'negative_stock_cells_after':signs.height,'negative_stock_rows_after':signs.select('CERT','REPDTE').unique().height,
               'negative_stock_banks_after':signs['CERT'].n_unique(),'decision_quarters':pq.height,
               'first_failure_events_with_positive_window':pos.height,'decision_flow':flow.to_dicts(),
               'lag2_coverage_reduction_pct':100*(pit.height-pit2.height)/pit.height,
               'source_values_reexecuted':False,'full_output_parquet_hashes_independently_verified':False}
        compare=[]
        for r in after:
            prev=before[r['column']]
            compare.append({'column':r['column'],'before_rows':int(prev['rows']),'before_null':int(prev['missing_after']),
              'before_missing_pct':float(prev['missing_pct']),'after_rows':int(r['rows']),'after_null':int(r['null']),
              'after_missing_pct':100*int(r['null'])/int(r['rows']),'after_negative':int(r['negative'])})
        pl.DataFrame(compare).sort('after_missing_pct',descending=True).write_csv(args.out/'missingness_comparison.csv')
        result={'status':'PASS','checks':checks,'check_count':len(checks),'metrics':stats,
                'limitations':['Keyset reconstructed from coverage and gap-bank metadata; full financial values are not in review ZIPs.',
                               'Output Parquet hashes are recorded by producer, not independently recomputed here.',
                               'API raw cached responses are not in review ZIPs; count/manifest evidence is inspected, not all responses redownloaded.']}
        (args.out/'verification_results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({'status':result['status'],'checks':len(checks),'metrics':stats},indent=2))


if __name__=='__main__':main()
