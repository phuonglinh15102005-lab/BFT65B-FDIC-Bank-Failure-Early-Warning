#!/usr/bin/env python3
"""Reproducible NEW post-score CERT-cluster bootstrap on immutable locked scores.

NOT the historical 1,500-draw method. No model load/fit/predict, no threshold
selection, no writes to the original directory. Validates score/event hashes
against the frozen output manifest and recomputes point AP independently.
Run: python bootstrap_locked_scores.py --locked-dir PATH --out NEW_DIRECTORY
"""
from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss, log_loss

SEED=20261117
N_BOOTSTRAP=1500
EXPECTED_SHA={
 'final_test_scored_rows.csv.gz': '6ca6913f2770f98382be9a491afb8c68559739e5bc5a65c43c5b8aedf5d3bf09',
 'final_test_event_detection_by_cert.csv': 'b94d483423ba5f9637aecd818b85865bd5a9e39cdef953ad66a9719151d2ad04',
}

def sha256(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for x in iter(lambda:f.read(1024*1024),b''):h.update(x)
 return h.hexdigest()

def exact_weighted_ap(y_sorted, s_sorted, row_cert_sorted, sample_multiplicity):
 """AP with sample weights and one group per unique predicted score.

 Sorting is done ONCE, grouping tie scores at the same decision threshold.
 Matching sklearn's non-interpolated AP is checked on independent random
 weights prior to any bootstrap results being accepted.
 """
 w=sample_multiplicity[row_cert_sorted].astype('float64',copy=False)
 total_pos=np.dot(w,y_sorted)
 if total_pos <= 0:
  return float('nan')
 tp=np.cumsum(w*y_sorted)
 pred=np.cumsum(w)
 ends=np.r_[np.flatnonzero(s_sorted[:-1]!=s_sorted[1:]),len(s_sorted)-1]
 tp_end=tp[ends]
 pred_end=pred[ends]
 tp_increment=np.diff(np.r_[0.0,tp_end])
 prec=np.divide(tp_end,pred_end,out=np.zeros_like(tp_end),where=pred_end>0)
 return float(np.dot(prec,tp_increment)/total_pos)

def run(base,out):
 if out.exists():raise ValueError('Out directory already exists; refusing overwrite')
 base=base.resolve();files=base/'final_test_output_manifest.json'
 if not files.is_file():raise FileNotFoundError(files)
 manifest=json.loads(files.read_text(encoding='utf-8'))
 for name,expected in EXPECTED_SHA.items():
  p=base/name
  if not p.is_file():raise FileNotFoundError(p)
  if manifest['files'][name]['sha256'] != expected or sha256(p)!=expected:
   raise ValueError('Frozen hash mismatch: '+name)
 scores=pd.read_csv(base/'final_test_scored_rows.csv.gz',usecols=['CERT','DECISION_DATE','Y_4Q','score'])
 events=pd.read_csv(base/'final_test_event_detection_by_cert.csv',usecols=['CERT','detected'])
 if len(scores)!=364440 or int(scores.Y_4Q.sum())!=1112 or len(events)!=341 or int(events.detected.sum())!=326:
  raise ValueError('Frozen cohort/event counts disagree')
 if scores.duplicated(['CERT','DECISION_DATE']).any() or events.CERT.duplicated().any():
  raise ValueError('Duplicated CERT/quarter or event CERT')
 y=scores.Y_4Q.to_numpy(dtype=np.int8)
 s=scores.score.to_numpy(dtype=np.float64)
 if not np.isfinite(s).all() or not ((s>=0)&(s<=1)).all() or not np.isin(y,[0,1]).all():
  raise ValueError('Invalid predictions or binary labels')
 cert,bank=np.unique(scores.CERT.to_numpy(dtype=np.int64),return_inverse=True)
 n_banks=len(cert)
 event_bank=np.searchsorted(cert,events.CERT.to_numpy(dtype=np.int64))
 if np.any(event_bank>=len(cert)) or np.any(cert[event_bank]!=events.CERT.to_numpy(dtype=np.int64)):
  raise ValueError('Event missing from prediction bank universe')
 event_detected=events.detected.astype(bool).to_numpy()
 order=np.argsort(-s,kind='stable')
 ys=y[order].astype('float64')
 ss=s[order]
 bs=bank[order]
 unit_weights=np.ones(n_banks,dtype='int64')
 unit_ap=exact_weighted_ap(ys,ss,bs,unit_weights)
 sklearn_ap=average_precision_score(y,s)
 if not math.isclose(unit_ap,sklearn_ap,abs_tol=1e-12,rel_tol=1e-11):
  raise ValueError('Tie-safe AP fails sklearn sanity check')
 rng=np.random.default_rng(SEED)
 # Independent arbitrary weighted checks, including zero and >1 CERT weights.
 for i in range(5):
  testw=rng.integers(0,4,size=n_banks)
  if not math.isclose(exact_weighted_ap(ys,ss,bs,testw),
                      average_precision_score(y,s,sample_weight=testw[bank]),
                      abs_tol=2e-12,rel_tol=1e-11):
   raise ValueError('Tie-safe weighted AP fails sklearn weighted check '+str(i))
 # Use a separate RNG stream for reproducibility of final draws, independent
 # of the above algorithm verification draws.
 rng=np.random.default_rng(SEED)
 ap_out=np.empty(N_BOOTSTRAP,dtype=np.float64)
 event_recall_out=np.empty(N_BOOTSTRAP,dtype=np.float64)
 for i in range(N_BOOTSTRAP):
  draws=rng.integers(0,n_banks,size=n_banks)
  multiplicity=np.bincount(draws,minlength=n_banks)
  ap_out[i]=exact_weighted_ap(ys,ss,bs,multiplicity)
  num=multiplicity[event_bank]
  denom=num.sum()
  event_recall_out[i]=(num@event_detected)/denom if denom else float('nan')
 if not np.isfinite(ap_out).all() or not np.isfinite(event_recall_out).all():
  raise ValueError('Invalid bootstrap draws')
 point={
  'n_rows':len(scores),'n_positive_rows':int(y.sum()),'n_unique_cert':n_banks,
  'n_unique_failure_events':len(events),'n_detected_events':int(event_detected.sum()),
  'average_precision':sklearn_ap,'roc_auc':roc_auc_score(y,s),
  'brier':brier_score_loss(y,s),'log_loss':log_loss(y,s),
  'event_recall':float(event_detected.mean()),
 }
 summary={
  'status':'PASS_SAVED_SCORES_ONLY_NOT_HISTORICAL_BOOTSTRAP',
  'methods':'Post hoc CERT-cluster pairs bootstrap applied to frozen saved scores and archived event detection flags, with same CERT resampling multiplicities for AP and event recall',
  'independence_limit':'CERT resampling does not account for common calendar shocks or model selection uncertainty.',
  'not_performed':['model loading','training','prediction','final test scoring','threshold tuning','feature selection'],
  'source_hashes_sha256':EXPECTED_SHA,
  'seed':SEED,'num_replicates':N_BOOTSTRAP,'numpy_bit_generator':'PCG64 via numpy.random.default_rng',
  'point':point,
  'ap_ci_95_percentile':[float(x) for x in np.quantile(ap_out,[0.025,0.975])],
  'event_recall_ci_95_percentile':[float(x) for x in np.quantile(event_recall_out,[0.025,0.975])],
  'ap_draw_summary':{'min':float(ap_out.min()),'median':float(np.median(ap_out)),'max':float(ap_out.max())},
  'event_draw_summary':{'min':float(event_recall_out.min()),'median':float(np.median(event_recall_out)),'max':float(event_recall_out.max())},
  'warning':'NEW reproducible post hoc check, NOT reproduction or validation of archived original 1500-replicate CI.'
 }
 out.mkdir(parents=True,exist_ok=False)
 (out/'NEW_POSTHOC_BOOTSTRAP_RESULTS.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
 # Keep full draws for independent verification, without row-level predictions.
 pd.DataFrame({'replicate':np.arange(1,N_BOOTSTRAP+1),'AP':ap_out,'event_recall':event_recall_out}).to_csv(out/'NEW_POSTHOC_BOOTSTRAP_DRAWS.csv',index=False)
 print(json.dumps(summary,indent=2))
 return summary

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--locked-dir',type=Path,required=True)
 p.add_argument('--out',type=Path,required=True)
 a=p.parse_args();run(a.locked_dir,a.out)
