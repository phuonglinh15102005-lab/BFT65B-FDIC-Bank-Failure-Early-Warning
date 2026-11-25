"""NEW posthoc paired CERT bootstrap using archived DEVELOPMENT scores only."""
from pathlib import Path
import argparse, csv, hashlib, json, platform, sys, time
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
FOLDS = ['early_bank_stress', 'post_stress_transition', 'global_financial_crisis']
CONFIGS = {'LR': ('02A_logistic', 'LR_C0p1_Wnone_CLq01_99'),
           'HGB': ('02B_hgb', 'HGB_L15_LR0p05_I150_L21_CLnone')}

def require(ok, message):
    if not ok:
        raise ValueError(message)

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def groups(y, score, bank):
    order = np.argsort(-score, kind='stable')
    starts = np.r_[0, np.flatnonzero(np.diff(score[order])) + 1]
    return y[order], bank[order], starts

def ap_grouped(group, multiplicity):
    y, bank, starts = group
    weights = multiplicity[bank]
    tp = np.add.reduceat(weights * y, starts).cumsum()
    n = np.add.reduceat(weights, starts).cumsum()
    if tp[-1] == 0:
        return np.nan
    precision = np.divide(tp, n, out=np.zeros_like(tp, dtype=float), where=n > 0)
    return float(np.sum(np.diff(np.r_[0, tp]) * precision) / tp[-1])

def selftest():
    rng = np.random.default_rng(631)
    for trial in range(100):
        bank = rng.integers(0, 12, size=100)
        y = rng.integers(0, 2, size=100)
        score = rng.integers(0, 8, size=100).astype(float) / 8
        multiplicity = rng.integers(0, 4, size=12)
        weight = multiplicity[bank]
        if (weight*y).sum() == 0:
            continue
        actual = ap_grouped(groups(y, score, bank), multiplicity)
        expected = average_precision_score(y, score, sample_weight=weight)
        expanded = average_precision_score(np.repeat(y, weight), np.repeat(score, weight))
        require(abs(actual-expected) < 2e-14 and abs(actual-expanded) < 2e-14,
                'Tie/zero-multiplicity AP mismatch')
    # Pairing must follow bank/date keys even when baseline rows are shuffled.
    a = pd.DataFrame({'CERT':[1,2], 'day':[10,10], 'y':[0,1]})
    b = pd.DataFrame({'CERT':[2,1], 'day':[10,10], 'score':[.9,.1]})
    joined = a.merge(b, on=['CERT','day'], validate='one_to_one')
    require(joined.score.tolist() == [.1,.9], 'Shuffled baseline pairing')
    try:
        a.merge(pd.concat([b,b]), on=['CERT','day'], validate='one_to_one')
    except pd.errors.MergeError:
        pass
    else:
        raise ValueError('Duplicate keys were accepted')
    return {'status':'PASS', 'weighted_AP_tie_zero_tests':100,
            'shuffled_baseline_join':'PASS', 'duplicate_key_rejection':'PASS'}

def load():
    hashes = json.loads((ROOT/'INPUT_HASHES.json').read_text())
    for name, digest in hashes.items():
        require(sha(ROOT/'INPUTS'/name) == digest, 'Changed archived input: '+name)
    baseline = pd.read_csv(ROOT/'INPUTS/01_baseline/baseline_development_oof.csv',
                           float_precision='round_trip')
    baseline['day'] = pd.to_datetime(baseline.DECISION_DATE).to_numpy(dtype='datetime64[D]').astype('int64')
    require(not baseline.duplicated(['fold','CERT','day']).any(), 'Duplicate baseline keys')
    frames=[]
    for fold in FOLDS:
        families=[]
        for family, (folder, config) in CONFIGS.items():
            with np.load(ROOT/'INPUTS'/folder/'fold_keys'/(fold+'.npz'), allow_pickle=False) as z:
                frame=pd.DataFrame({'CERT':z['cert'], 'day':z['decision_day'], 'y':z['y']})
            with np.load(ROOT/'INPUTS'/folder/'predictions'/(config+'__'+fold+'.npz'), allow_pickle=False) as z:
                frame[family]=z['score']
            require(not frame.duplicated(['CERT','day']).any(), 'Duplicate NPZ fold keys')
            families.append(frame)
        merged=families[0].merge(families[1],on=['CERT','day'],how='outer',
                                 validate='one_to_one',indicator=True,suffixes=('_LR','_HGB'))
        require(merged['_merge'].eq('both').all(), 'LR/HGB key mismatch')
        require(merged.y_LR.eq(merged.y_HGB).all(), 'LR/HGB label mismatch')
        merged=merged.drop(columns=['_merge','y_HGB']).rename(columns={'y_LR':'y'})
        b=baseline.loc[baseline.fold.eq(fold), ['CERT','day','Y_4Q','p_failure']]
        merged=merged.merge(b,on=['CERT','day'],how='outer',validate='one_to_one',indicator=True)
        require(merged['_merge'].eq('both').all() and merged.y.eq(merged.Y_4Q).all(), 'Equity keys/labels mismatch')
        merged=merged.rename(columns={'p_failure':'equity'}).drop(columns=['_merge','Y_4Q'])
        require(np.isfinite(merged[['LR','HGB','equity']]).all().all(), 'Nonfinite scores')
        require(merged.y.isin([0,1]).all(), 'Invalid labels')
        require((merged.day <= np.datetime64('2008-12-31','D').astype('int64')).all(), 'Non-development date')
        merged['fold']=fold;frames.append(merged)
    all_rows=pd.concat(frames,ignore_index=True)
    require(len(all_rows)==304598 and int(all_rows.y.sum())==3683, 'OOF census mismatch')
    require(all_rows.loc[all_rows.y.eq(1),'CERT'].nunique()==1290, 'Positive CERT count')
    return frames, all_rows, hashes

def run(out):
    out.mkdir(parents=True, exist_ok=False)
    tests=selftest();(out/'SELFTEST.json').write_text(json.dumps(tests,indent=2))
    spec=json.loads((ROOT/'METHOD_FIXED_BEFORE_RUN.json').read_text())
    require(spec['seed']==20261117 and spec['draws']==1500, 'Analysis specification changed')
    frames, all_rows, hashes=load()
    universe=np.unique(all_rows.CERT.to_numpy()); prepared={}; points=[]
    for frame,fold in zip(frames,FOLDS):
        bank=np.searchsorted(universe,frame.CERT.to_numpy());y=frame.y.to_numpy()
        for family in ['HGB','LR','equity']:
            score=frame[family].to_numpy(); g=groups(y,score,bank);prepared[fold,family]=g
            point=ap_grouped(g,np.ones(len(universe),dtype=np.int64))
            require(abs(point-average_precision_score(y,score)) < 1e-12, 'Point AP formula check')
            points.append(dict(fold=fold,family=family,rows=len(frame),positives=int(y.sum()),AP=point))
    point_means={family:float(np.mean([p['AP'] for p in points if p['family']==family])) for family in ['HGB','LR','equity']}
    for family, expected in [('HGB',.29576629263614845),('LR',.24976137930453154),('equity',.1814676655250236)]:
        require(abs(point_means[family]-expected) < 2e-12, 'Archived mean AP mismatch: '+family)
    rng=np.random.Generator(np.random.PCG64(spec['seed']));draws=[];start=time.monotonic()
    with threadpool_limits(limits=1):
        for i in range(spec['draws']):
            multiplicity=np.bincount(rng.integers(0,len(universe),size=len(universe)),minlength=len(universe))
            values={f:[ap_grouped(prepared[fold,f],multiplicity) for fold in FOLDS] for f in ['HGB','LR','equity']}
            valid=all(np.isfinite(v).all() for v in values.values())
            means={f:float(np.mean(v)) for f,v in values.items()}
            draws.append(dict(replicate=i,valid=valid,**means,
                              HGB_minus_LR=means['HGB']-means['LR'],
                              HGB_minus_equity=means['HGB']-means['equity']))
            if (i+1)%250==0:print(f'Development paired draws: {i+1}/1500',flush=True)
    valid=[d for d in draws if d['valid']];require(len(valid)>=1400,'Too many undefined replicates')
    intervals={}
    for column in ['HGB_minus_LR','HGB_minus_equity']:
        intervals[column]=np.quantile([d[column] for d in valid],[.025,.975],method='linear').tolist()
    after={name:sha(ROOT/'INPUTS'/name) for name in hashes};require(after==hashes,'Input changed during execution')
    for name,records in [('PAIRED_DRAWS.csv',draws),('FOLD_POINT_AP.csv',points)]:
        with (out/name).open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    result=dict(status='PASS_POSTHOC_NUMERICAL_CHECK_ONLY',method=spec,
                universe_CERTs=len(universe),rows=len(all_rows),valid_draws=len(valid),
                invalid_draws=len(draws)-len(valid),point_mean_AP=point_means,
                point_difference=dict(HGB_minus_LR=point_means['HGB']-point_means['LR'],HGB_minus_equity=point_means['HGB']-point_means['equity']),
                percentile95_CI=intervals,input_sha256_before=hashes,input_sha256_after=after,
                code_sha256=sha(Path(__file__)),elapsed_seconds=time.monotonic()-start,
                environment=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__),
                not_established=['original historical bootstrap reproduction','selection-adjusted confidence','registered ablation execution','historical filing vintage','full E2E'],
                no_model_training_or_test_access=True)
    (out/'RESULT.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:result[k] for k in ['status','valid_draws','point_difference','percentile95_CI']},indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--self-test',action='store_true')
    args=parser.parse_args()
    if args.self_test:print(json.dumps(selftest(),indent=2))
    else:
        if args.out is None:parser.error('--out required')
        run(args.out)
