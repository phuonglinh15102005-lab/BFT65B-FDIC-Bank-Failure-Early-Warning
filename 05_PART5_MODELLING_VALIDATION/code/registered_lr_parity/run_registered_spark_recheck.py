#!/usr/bin/env python3
"""Controlled replacement wrapper: explicit inputs and preflight ONLY.

The historical wrapper auto-discovered home folders, fitted classifiers and
replaced a result ZIP. This repaired wrapper never dispatches that operation.
The diagnostic source is retained next to it; no classifier is fitted here.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO_ROOT=ROOT.parents[2]
SRC=ROOT/'spark_registered_logistic_parity.py'
DEV_HASH='d365ce25204a3dcace715db4cea259c94b1b1abba4822c7bcf2b050a1c7f6a73'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dev',type=Path,required=True)
    p.add_argument('--reference-dir',type=Path,required=True,
                   help='Explicit directory containing archived registered_fold1_keys.npz and registered_fold1_LR_scores.npz; no private default.')
    p.add_argument('--out',type=Path,help='Optional NEW external preflight JSON; never a fit output')
    a=p.parse_args();issues=[]
    for file in [SRC,a.dev,a.reference_dir/'registered_fold1_keys.npz',a.reference_dir/'registered_fold1_LR_scores.npz']:
        if not file.is_file():issues.append('Not supplied locally: '+str(file))
    if a.dev.is_file() and sha(a.dev)!=DEV_HASH:issues.append('Development snapshot SHA mismatch')
    result={'status':'BLOCKED_INPUTS' if issues else 'PREFLIGHT_ONLY_NOT_EXECUTED',
            'source':str(SRC),'reference_dir':str(a.reference_dir),'issues':issues,
            'estimator_fits':0,'model_loads':0,'final_test_inference':0,
            'note':'Reference presence only; this is not numerical-parity verification.'}
    if a.out:
        out=a.out.resolve()
        if out.is_relative_to(REPO_ROOT):p.error('Output must be outside the submission source repository')
        if out.is_relative_to(a.reference_dir.expanduser().resolve()) or out.is_relative_to(a.dev.expanduser().resolve().parent):
            p.error('Output must be outside the source/reference input directories')
        if out.exists():p.error('Refusing to overwrite preflight output')
        out.parent.mkdir(parents=True,exist_ok=True)
        with out.open('x',encoding='utf-8') as stream:
            stream.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    return 3 if issues else 0

if __name__=='__main__':raise SystemExit(main())
