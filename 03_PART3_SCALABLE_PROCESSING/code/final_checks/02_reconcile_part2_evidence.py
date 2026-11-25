#!/usr/bin/env python3
"""Read-only reconciliation of archived Part 2 and Part 3 CSV evidence.

Does not claim to re-run the original FDIC download or prove historical filing vintages.
Produces a small JSON to support exact report wording.
"""
from __future__ import annotations
import argparse, csv, io, json, statistics, zipfile
from pathlib import Path


def read_csv(z: zipfile.ZipFile, name: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(z.read(name).decode('utf-8-sig'))))


def main():
    a=argparse.ArgumentParser()
    a.add_argument('--part2',type=Path,required=True)
    a.add_argument('--part3',type=Path,required=True)
    a.add_argument('--out',type=Path,required=True)
    v=a.parse_args(); v.out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(v.part2) as z:
        if z.testzip() is not None:raise RuntimeError('Part 2 ZIP failed CRC check')
        summary=json.loads(z.read('step2c_summary.json'))
        accounting=read_csv(z,'review_AUDIT_ONLY/row_accounting.csv')
        numeric=read_csv(z,'review_AUDIT_ONLY/numeric_profile_after.csv')
    with zipfile.ZipFile(v.part3) as z:
        if z.testzip() is not None:raise RuntimeError('Part 3 ZIP failed CRC check')
        lag=read_csv(z,'calendar_lag.csv')
    counts={x['ROW_ACTION']:int(x['rows']) for x in accounting}
    assert sum(counts.values())==summary['source_rows']
    assert counts['RETAIN']==summary['clean_rows']
    assert summary['source_rows']-summary['clean_rows']==summary['excluded_rows']
    fields={x['column']:x for x in numeric}
    assert all(int(fields[k]['rows'])==summary['clean_rows'] for k in ['ROE','P3ASSET','NETINC','EQ','RBCRWAJ'])
    assert len(lag)==summary['clean_quarters']==170
    assert sum(int(r['REPORTS']) for r in lag)==summary['clean_rows']
    means=[float(r['MEAN_ASSET_GROWTH']) for r in lag if r['MEAN_ASSET_GROWTH']!='']
    assert len(means)==169
    out={'status':'PASS_ARCHIVED_CSV_RECONCILIATION_NOT_SOURCE_RERUN',
         'source_financial_rows':summary['source_rows'],
         'clean_rows':summary['clean_rows'],
         'exclusion_categories':counts,
         'decision_rows':summary['decision_rows_lag1'],
         'decision_quarters':len(lag)-5,
         'growth_measure':'MEDIAN_OF_169_QUARTERLY_CROSS_SECTIONAL_MEAN_ASSET_GROWTH',
         'median_quarterly_mean_growth_pct':100*statistics.median(means),
         'quarters_mean_growth_gt_5pct':sum(x>.05 for x in means),
         'quarters_mean_growth_gt_10pct':sum(x>.10 for x in means),
         'mean_growth_1997Q3_pct':100*next(float(r['MEAN_ASSET_GROWTH']) for r in lag if r['REPDTE']=='1997-09-30'),
         'roe_null':int(fields['ROE']['null']),
         'p3asset_null':int(fields['P3ASSET']['null']),
         'negative_netinc':int(fields['NETINC']['negative']),
         'negative_equity':int(fields['EQ']['negative']),
         'rbcrwaj_zero':int(fields['RBCRWAJ']['zero']),
         'notes':['Aggregates are reproduced from existing evidence CSV, NOT newly recomputed from 1.67M source records.',
                  'The growth median is not a bank-level cross-sectional median.',
                  'Do not construct quarter NETINC as a simple difference before verifying FDIC reporting convention and institution type.',
                  'Current snapshot plus one-quarter lag does not prove historical-vintage point-in-time integrity.']}
    v.out.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(out,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
