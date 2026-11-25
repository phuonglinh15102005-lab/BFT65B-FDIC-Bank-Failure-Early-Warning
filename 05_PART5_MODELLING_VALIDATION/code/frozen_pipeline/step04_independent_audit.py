#!/usr/bin/env python3
"""Repeatable review of the three submitted Step04 evidence members only."""
import argparse, hashlib, io, json, zipfile
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss
from pathlib import Path

def run(path):
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        a=json.loads(z.read('part5_step04_audit.json'))
        assert a['status']=='PASS_FOLD_PREPROCESSING_AND_RANKING_PARITY'
        assert a['protocol_sha256']=='994f72de6e2446916db8c2fcd36847c45cc68eb6fef5ef67f07acc0476c6d911'
        df=pd.read_csv(io.BytesIO(z.read('spark_vs_sklearn_dev_validation.csv')))
        summ=pd.read_csv(io.BytesIO(z.read('spark_mllib_fold_metrics.csv')))
        assert summ.shape==(1,18)
        assert len(df)==125962 and df.Y_4Q.sum()==2796
        assert df.loc[df.Y_4Q.eq(1),'CERT'].nunique()==932
        assert len(df[['CERT','DECISION_DATE']].drop_duplicates())==125962
        assert df['DECISION_DATE'].between('1989-03-31','1990-12-31').all()
        assert df['DECISION_DATE'].nunique()==8
        assert not df.isna().any().any() and df.Y_4Q.isin([0,1]).all()
        y=df.Y_4Q.to_numpy()
        checks={}
        for key,col in [('spark','spark_score'),('sklearn','sklearn_baseline_score')]:
            q=df[col].to_numpy()
            assert np.isfinite(q).all() and np.all((q>=0)&(q<=1))
            for metric,val in [('AP',average_precision_score(y,q)),('ROC_AUC',roc_auc_score(y,q)),('Brier',brier_score_loss(y,q))]:
                name=f'{key}_{metric}'
                assert abs(val-float(a['metrics'][name]))<1e-12
                checks[name]=float(val)
        assert abs(np.corrcoef(df.spark_score,df.sklearn_baseline_score)[0,1]-a['metrics']['score_pearson_correlation'])<1e-12
        for name,h in a['output_sha256'].items():
            assert hashlib.sha256(z.read(name)).hexdigest()==h
        report={'status':'PASS_INDEPENDENT_RECOMPUTATION','input_zip_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                'rows':125962,'positive_rows':2796,'positive_certs':932,
                'unique_quarters':8,'validation_range':'1989Q1-1990Q4',
                'csv_sha256_verified':2,'metrics':checks,'pearson_corr':float(np.corrcoef(df.spark_score,df.sklearn_baseline_score)[0,1]),
                'max_absolute_score_difference':float(np.max(np.abs(df.spark_score-df.sklearn_baseline_score))),
                'scope':'Evidence-level checks on submitted predictions; not a second Spark training run.'}
        return report

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--zip',type=Path,required=True);ap.add_argument('--out',type=Path)
    a=ap.parse_args();r=run(a.zip)
    print(json.dumps(r,indent=2))
    if a.out:a.out.write_text(json.dumps(r,indent=2)+'\n')
if __name__=='__main__':main()
