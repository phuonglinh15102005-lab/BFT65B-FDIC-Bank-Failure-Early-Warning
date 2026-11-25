#!/usr/bin/env python3
"""Read-only R23 parameter verification, Windows x64, minimal memory.

Only reads frozen development Parquet and archived reference tables.
No model artifacts, final test cohorts/scores, network or installation.
Every invocation creates new outputs under LOCALAPPDATA (never overwrites).
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
import pathlib
import sys
import traceback
import uuid
import zipfile
from contextlib import redirect_stdout,redirect_stderr

HERE=pathlib.Path(__file__).resolve().parent
SOURCE_SHA='d365ce25204a3dcace715db4cea259c94b1b1abba4822c7bcf2b050a1c7f6a73'
PROTOCOL_SHA='994f72de6e2446916db8c2fcd36847c45cc68eb6fef5ef67f07acc0476c6d911'
REF_SHA='df26410b18c7f6900993bb5ee873ce00b8c6102949b351eff19da3c8f4af4651'


def file_hash(p):
    h=hashlib.sha256()
    with pathlib.Path(p).open('rb') as stream:
        for b in iter(lambda:stream.read(8*1024*1024),b''):
            h.update(b)
    return h.hexdigest()


def save_json(path,obj):
    with pathlib.Path(path).open('x',encoding='utf-8') as s:
        json.dump(obj,s,indent=2,ensure_ascii=False,allow_nan=False)


def run():
    folder=pathlib.Path(os.environ.get('LOCALAPPDATA',os.environ.get('TEMP',str(pathlib.Path.home()))))/'BFT65B_AUDIT_RUNS'
    folder.mkdir(parents=True,exist_ok=True)
    token=dt.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]
    out=folder/('R23_LOW_MEMORY_'+token)
    out.mkdir(exist_ok=False)
    logpath=out/'R23_CONSOLE.log'
    checks=[]
    source=pathlib.Path.home()/'BFT65B_outputs'/'part4_v2_dev_only_outputs'/'development_primary_binary_v2.parquet'
    protocol_file=HERE/'reference'/'part5_protocol_freeze.json'
    param_file=HERE/'reference'/'expected_fold_preprocessing.csv'
    def record(k,status,detail):
        item={'check':k,'status':status,'detail':detail}
        checks.append(item)
        print(f'[{status}] {k}: {detail}',flush=True)
    result=None
    f_before=None
    with logpath.open('x',encoding='utf-8') as logfile:
        class Output:
            def __init__(self,*streams):self.streams=streams
            def write(self,text):
                for stream in self.streams:stream.write(text);stream.flush()
            def flush(self):
                for stream in self.streams:stream.flush()
        with redirect_stdout(Output(sys.stdout,logfile)),redirect_stderr(Output(sys.stderr,logfile)):
            try:
                import numpy as np
                import pandas as pd
                import pyarrow
                record('ENVIRONMENT','PASS','Python '+sys.version.split()[0]+' NumPy '+np.__version__+' pandas '+pd.__version__+' pyarrow '+pyarrow.__version__)
                require_files=[(source,SOURCE_SHA,'FROZEN_DEVELOPMENT'),(protocol_file,PROTOCOL_SHA,'FROZEN_PROTOCOL'),(param_file,REF_SHA,'PARAMETER_REFERENCE')]
                for p,h,k in require_files:
                    if not p.is_file():
                        record(k,'BLOCKED','Missing file '+str(p));raise FileNotFoundError('Required original not found: '+str(p))
                    actual=file_hash(p)
                    record(k,'PASS' if actual==h else 'FAIL','SHA256 '+actual)
                    if actual!=h:raise ValueError('SHA mismatch for '+k)
                f_before=file_hash(source)
                from verify_fold_preprocessing_streaming import verify_fold_preprocessing_lowmem
                protocol=json.loads(protocol_file.read_text(encoding='utf-8-sig'))
                result=verify_fold_preprocessing_lowmem(source,param_file,protocol,out/'FOLD_PREPROCESSING')
                record('R23_504_PARAMETER_STATISTICS',result['status'],'Rows '+str(result['rows_compared'])+', statistics '+str(result['statistics_compared'])+', mismatches '+str(result['mismatches']))
            except MemoryError:
                record('R23_504_PARAMETER_STATISTICS','FAIL','MemoryError during low-memory scan; see traceback');(out/'R23_ERROR.txt').write_text(traceback.format_exc(),encoding='utf-8')
            except Exception as e:
                record('R23_504_PARAMETER_STATISTICS','FAIL',type(e).__name__+': '+str(e));(out/'R23_ERROR.txt').write_text(traceback.format_exc(),encoding='utf-8')
            finally:
                if source.is_file() and f_before:
                    after=file_hash(source)
                    record('FROZEN_SOURCE_UNCHANGED','PASS' if after==f_before else 'FAIL','Before: '+f_before+' After: '+after)
                else:
                    record('FROZEN_SOURCE_UNCHANGED','BLOCKED','Source initial hash unavailable')
    overall=('FAIL' if any(x['status']=='FAIL' for x in checks) else 'BLOCKED' if any(x['status']=='BLOCKED' for x in checks) else 'SCOPED_CHECKS_COMPLETED_REVIEW_REQUIRED')
    save_json(out/'R23_STATUS.json',{
      'overall':overall,'checks':checks,'source':str(source),'created_local':token,
      'R23_scope':'72 fold × clipping × continuous-feature rows; 7 metrics each = 504 comparisons',
      'not_performed':['train','fit','refit','test cohort reads','test predictions','model loading','network','software installation'],
      'scope_limitation':'Not a full end-to-end pipeline reproduction or historical filing-vintage validation'
    })
    zip_path=out.with_suffix('.zip')
    with zipfile.ZipFile(zip_path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for f in sorted(out.rglob('*')):
            if f.is_file():z.write(f, f.relative_to(out.parent))
    print('FINAL STATUS:',overall)
    print('SEND THIS ZIP:',zip_path)
    try:
        os.startfile(zip_path.parent)
    except Exception:pass
    return 0 if overall=='SCOPED_CHECKS_COMPLETED_REVIEW_REQUIRED' else 2

if __name__=='__main__':raise SystemExit(run())
