"""Synthetic metadata and column-scanner tests; no frozen FDIC data."""
import pathlib,sys,types,unittest,tempfile
import numpy as np
import pandas as pd
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'engine'))
# Local test environment may not include pyarrow. Stub ParquetFile import only;
# tests use a small FakeParquet with same iter_batches contract.
try:
 import pyarrow.parquet
except ImportError:
 arrow=types.ModuleType('pyarrow');arrow.__version__='19.0.0'
 parquet=types.ModuleType('pyarrow.parquet');arrow.parquet=parquet
 sys.modules['pyarrow']=arrow;sys.modules['pyarrow.parquet']=parquet
import verify_fold_preprocessing_streaming as m
class Batch:
 def __init__(self,series):self.series=series
 def column(self,index):return self
 def to_pandas(self):return self.series
class FakeParquet:
 def __init__(self,df):
  self.df=df
  self.schema_arrow=types.SimpleNamespace(names=df.columns.tolist())
  self.metadata=types.SimpleNamespace(num_rows=len(df))
 def iter_batches(self,batch_size,columns,use_threads):
  series=self.df[columns[0]]
  for i in range(0,len(series),batch_size):
   yield Batch(series.iloc[i:i+batch_size])
class Tests(unittest.TestCase):
 def setup_data(self):
  dates=['1987-12-31','1989-03-31','1990-12-31','1992-03-31','2005-12-31','2007-03-31']
  vals={'CERT':[101,102,103,104,105,106], 'DECISION_DATE':pd.to_datetime(dates),
        'SOURCE_REPDTE':pd.to_datetime(dates)-pd.offsets.QuarterEnd(1),
        'SPLIT':['development']*6,'Y_4Q':[0,1,0,1,1,0]}
  for c in m.FEATURES:vals[c]=[1.0,np.nan,3.,4.,5.,6.]
  for c in m.BINARY:vals[c]=[1.,np.nan,0.,1.,0.,1.]
  return FakeParquet(pd.DataFrame(vals))
 def test_columns(self):
  p=self.setup_data()
  self.assertEqual(m.read_col(p,'CERT','int').tolist(),[101,102,103,104,105,106])
  self.assertEqual(m.read_col(p,'Y_4Q','binary').sum(),3)
  self.assertTrue(np.isnan(m.read_col(p,'log_assets','float')[1]))
  m.read_col(p,'SPLIT','str')
 def test_metadata_folds(self):
  p=self.setup_data()
  folds=[('early_bank_stress','1987-12-31','1989-03-31','1990-12-31'),
         ('post_stress_transition','1990-12-31','1992-03-31','1992-03-31'),
         ('global_financial_crisis','2005-12-31','2007-03-31','2007-03-31')]
  protocol={'validation':{'embargo_calendar_quarters':4,'folds':[
    {'id':name,'train_end':a,'validation_start':b,'validation_end':c} for name,a,b,c in folds]}}
  masks=m.make_masks(p,protocol,frozen=False)
  self.assertEqual(masks['early_bank_stress']['counts'][:2],(1,2))
  self.assertEqual(masks['post_stress_transition']['counts'][:2],(3,1))
  self.assertEqual(masks['global_financial_crisis']['counts'][:2],(5,1))
  self.assertTrue(all(x['gap']==4 for x in masks.values()))
 def test_original_equivalence_parameters(self):
  x=np.array([[1.],[2.],[np.nan],[4.],[5.]])
  valid=np.array([[1.],[np.nan],[8.]])
  for clip in [False,True]:
   p=m.continuous_parameters(x,valid,clip)[0]
   self.assertEqual(p['train_missing_count'],1)
   self.assertEqual(p['validation_missing_count'],1)
   self.assertTrue(np.isfinite(p['train_robust_scale']))
 def test_full_72_rows_504_statistics_synthetic(self):
  p=self.setup_data()
  folds=[('early_bank_stress','1987-12-31','1989-03-31','1990-12-31'),
         ('post_stress_transition','1990-12-31','1992-03-31','1992-03-31'),
         ('global_financial_crisis','2005-12-31','2007-03-31','2007-03-31')]
  protocol={'validation':{'embargo_calendar_quarters':4,'folds':[
    {'id':name,'train_end':a,'validation_start':b,'validation_end':c} for name,a,b,c in folds]},
    'feature_policy':{'tier1_features':m.FEATURES}}
  masks=m.make_masks(p,protocol,frozen=False)
  ref=[]
  for feat in m.CONTINUOUS:
   x=p.df[feat].to_numpy(dtype=np.float64)
   for fold,k in masks.items():
    for mode in (False,True):
     values=m.continuous_parameters(x[k['train']].reshape(-1,1),x[k['valid']].reshape(-1,1),mode)[0]
     ref.append({'fold':fold,'clip':mode,'feature':feat,**values})
  orig_make,orig_parquet=m.make_masks,getattr(m.pq,"ParquetFile",None)
  try:
   m.make_masks=lambda _p,_proto,_frozen:masks
   m.pq.ParquetFile=lambda _path:p
   with tempfile.TemporaryDirectory() as t:
    from pathlib import Path
    csv=Path(t)/'expected.csv';pd.DataFrame(ref).to_csv(csv,index=False)
    outcome=m.verify_fold_preprocessing_lowmem('fake.parquet',csv,protocol,Path(t)/'out')
    self.assertEqual(outcome['status'],'PASS')
    self.assertEqual(outcome['rows_compared'],72)
    self.assertEqual(outcome['statistics_compared'],504)
    self.assertEqual(outcome['mismatches'],0)
  finally:
   m.make_masks=orig_make
   if orig_parquet is None:delattr(m.pq,"ParquetFile")
   else:m.pq.ParquetFile=orig_parquet
 def test_duplicate_key_rejected(self):
  p=self.setup_data();p.df.loc[1,'CERT']=101;p.df.loc[1,'DECISION_DATE']=p.df.loc[0,'DECISION_DATE'];p.df.loc[1,'SOURCE_REPDTE']=p.df.loc[0,'SOURCE_REPDTE']
  folds=[{'id':x,'train_end':'1987-12-31','validation_start':'1989-03-31','validation_end':'1990-12-31'} for x in m.FROZEN_COUNTS]
  with self.assertRaisesRegex(ValueError,'Duplicate'):
   m.make_masks(p,{'validation':{'embargo_calendar_quarters':4,'folds':folds}},frozen=False)
if __name__=='__main__':unittest.main(verbosity=2)
