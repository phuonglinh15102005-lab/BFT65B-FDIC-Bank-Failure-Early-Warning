"""Exactly three authorized DEVELOPMENT HGB fits; no final-test file access."""
from pathlib import Path
import argparse, csv, gc, hashlib, importlib.metadata as metadata, json, os
import platform, sys, tempfile, time, traceback
from datetime import datetime,timezone,timedelta
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score,roc_auc_score
from threadpoolctl import threadpool_limits
from original.part4_v2_train_only_pipeline import FEATURES,CONTINUOUS,BINARY,make_preprocessor
from original.part5_step01_baseline_dev_only import audit_dev,FOLD_EXPECTED,verify_protocol
from safety import Blocked,require,sha,validate_output,AccessPolicy,create_claim,update_claim,reserve_fit_attempt

HERE=Path(__file__).resolve().parent
FOLDS=['early_bank_stress','post_stress_transition','global_financial_crisis']
FIELDS=['fold','status','train_rows','validation_rows','full_AP','ablated_AP','delta_AP_ablated_minus_full',
        'full_ROC_AUC','ablated_ROC_AUC','delta_ROC_AUC_ablated_minus_full','transformed_width','fit_attempt']

class PreflightComplete(Exception):
    """Internal no-fit control flow; final hash checks still determine exit status."""
    pass

def dump(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf-8')

def environment():
    packages={}
    for distribution in metadata.distributions():
        name=distribution.metadata.get('Name')
        if name:packages[name.casefold()]=distribution.version
    return dict(python=platform.python_version(),platform=platform.platform(),
                executable=sys.executable,packages=packages)

def environment_blockers(config,observed):
    issues=[]
    for key,want in {**config['expected_core'],**config['additional_current_observed_runtime_pins']}.items():
        actual=observed['python'] if key=='python' else observed['packages'].get(key.casefold())
        if actual!=want:issues.append(f'{key}: required {want}, observed {actual}')
    return issues

def output_names():
    return ['continuous__'+x for x in CONTINUOUS]+['binary__'+x for x in BINARY]+['missing__'+x for x in FEATURES]

def feature_contract(config):
    names=output_names();drop=config['drop_transformed_indices']
    require(len(FEATURES)==15 and len(names)==30 and drop==[17,18],'Feature width/drop specification changed')
    require([names[i] for i in drop]==config['drop_transformed_names'],'Removed feature names mismatch')
    keep=[i for i in range(30) if i not in drop]
    require(len(keep)==28 and keep[2:4]==[2,3],'Continuous growth features must remain')
    return dict(raw_input_order=FEATURES,full_output_order=names,removed_indices=drop,
                removed_names=[names[i] for i in drop],retained_indices=keep,
                ablated_output_order=[names[i] for i in keep],original_width=30,ablated_width=28)

def remove_indicators(matrix,contract):
    require(matrix.ndim==2 and matrix.shape[1]==30,'Expected original 30-column transformation')
    return matrix[:,contract['retained_indices']]

def preprocess_state(prep):
    cont=prep.named_transformers_['continuous']
    return dict(median=cont.named_steps['training_median'].statistics_.tolist(),
                robust_center=cont.named_steps['training_robust_scale'].center_.tolist(),
                robust_scale=cont.named_steps['training_robust_scale'].scale_.tolist(),
                missing_flag_input_width=int(prep.named_transformers_['missing'].n_features_in_),
                continuous_features=list(prep.transformers_[0][2]),
                binary_features=list(prep.transformers_[1][2]),
                missing_features=list(prep.transformers_[2][2]))

def fold_contract(dev,fold):
    start=pd.Timestamp(fold['validation_start']);end=pd.Timestamp(fold['validation_end']);last=pd.Timestamp(fold['train_end'])
    require(start.to_period('Q').ordinal-last.to_period('Q').ordinal-1==4,'Four complete embargo quarters required')
    require(last+pd.offsets.QuarterEnd(4)<start,'Training labels overlap validation window')
    tr=dev.loc[dev.DECISION_DATE.le(last)]
    va=dev.loc[dev.DECISION_DATE.between(start,end)]
    actual=dict(train=len(tr),valid=len(va),train_pos=int(tr.Y_4Q.sum()),valid_pos=int(va.Y_4Q.sum()),
                valid_certs=int(va.loc[va.Y_4Q.eq(1),'CERT'].nunique()))
    require(actual==FOLD_EXPECTED[fold['id']],'Fold census differs from original: '+fold['id'])
    return tr,va,actual

def load_reference(fold,va,metrics,config):
    with np.load(HERE/'REF/fold_keys'/(fold+'.npz'),allow_pickle=False) as z:
        require(np.array_equal(z['cert'],va.CERT.to_numpy(dtype=np.int64)),'Validation CERT order differs')
        require(np.array_equal(z['decision_day'],va.DECISION_DATE.to_numpy(dtype='datetime64[D]').astype(np.int64)),'Validation date order differs')
        require(np.array_equal(z['y'],va.Y_4Q.to_numpy(dtype=np.uint8)),'Validation labels differ')
    with np.load(HERE/'REF/predictions'/(config['full_config_id']+'__'+fold+'.npz'),allow_pickle=False) as z:score=z['score'].copy()
    require(score.shape==(len(va),) and np.isfinite(score).all(),'Archived development scores invalid')
    row=metrics.loc[metrics.fold.eq(fold)&metrics.config_id.eq(config['full_config_id'])]
    require(len(row)==1,'Archived fold metric missing/duplicated')
    ap=float(average_precision_score(va.Y_4Q,score));auc=float(roc_auc_score(va.Y_4Q,score))
    require(abs(ap-float(row.iloc[0].average_precision))<1e-12 and abs(auc-float(row.iloc[0].roc_auc))<1e-12,'Archived score/metric mismatch for ablation comparison')
    return score,ap,auc

def write_metrics(out,rows):
    with (out/'ABLATION_FOLD_METRICS.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)

def render(out,status,rows,detail):
    lines=['# Newly executed development-only ablation', '', 'Status: '+status,'',
           'Execution date UTC: '+datetime.now(timezone.utc).isoformat(),
           'Execution date Vietnam: '+datetime.now(timezone(timedelta(hours=7))).isoformat(),'',
           'Late robustness analysis after original final-test lock; not evidence of pre-lock execution.',
           'Primary HGB, threshold, model selection and final-test results remain unchanged.','',detail,'',
           '| Fold | Status | Full AP | Ablated AP | Delta AP (ablated-full) | Full AUC | Ablated AUC |',
           '|---|---|---:|---:|---:|---:|---:|']
    for row in rows:lines.append('| '+' | '.join(str(row.get(k,'')) for k in ['fold','status','full_AP','ablated_AP','delta_AP_ablated_minus_full','full_ROC_AUC','ablated_ROC_AUC'])+' |')
    (out/'ABLATION_RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

def run(profile,out,claimfile,preflight_only=False):
    config=json.loads((HERE/'CONFIG.json').read_text());devpath=(profile/config['development_profile_relative_path']).resolve()
    validate_output(out,HERE.parent,devpath);out.mkdir(parents=True,exist_ok=False)
    observed=environment();dump(out/'ENVIRONMENT.json',observed)
    command=[sys.executable,'-B',str(Path(__file__).resolve()),*sys.argv[1:]]
    dump(out/'COMMAND.json',command);dump(out/'CONFIG_USED.json',config)
    rows=[];claim=None;dev_digest=None;policy=None;before={};status='FAIL';detail=''
    started=datetime.now(timezone.utc).isoformat()
    def event(phase,**values):
        with (out/'EVENTS.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(dict(time_utc=datetime.now(timezone.utc).isoformat(),phase=phase,**values))+'\n')
        print(phase,values,flush=True)
    try:
        require(not any(x in config['development_filename'].lower() for x in ['test','final']),'Development filename changed')
        integrity=json.loads((HERE/'RUNTIME_HASHES.json').read_text())
        for name,h in integrity.items():require(sha(HERE/name)==h,'Runtime package changed: '+name)
        for name,h in json.loads((HERE/'REFERENCE_HASHES.json').read_text()).items():
            before[name]=sha(HERE/name);require(before[name]==h,'Original reference changed: '+name)
        protocol,ph=verify_protocol(HERE/'REF/part5_protocol_freeze.json')
        require(ph==config['protocol_sha256'],'Protocol SHA differs')
        require([f['id'] for f in protocol['validation']['folds']]==FOLDS,'Fold order differs')
        require(config['HGB']==dict(max_leaf_nodes=15,learning_rate=.05,max_iter=150,l2_regularization=1.,random_state=20261114,early_stopping=False),'Selected HGB config changed')
        contract=feature_contract(config);dump(out/'FEATURE_ORDER_CONTRACT.json',contract)
        issues=environment_blockers(config,observed)
        if not devpath.is_file():issues.append('Development Parquet missing at known exact path: '+str(devpath))
        if issues:raise Blocked('; '.join(issues))
        require(devpath.name==config['development_filename'],'Wrong development filename')
        dev_digest=sha(devpath);require(dev_digest==config['development_sha256'],'Development SHA mismatch; no fallback to latest file')
        event('PREFLIGHT_INPUT_AND_ENVIRONMENT_PASS',development_sha256=dev_digest)
        if preflight_only:
            status='PREFLIGHT_PASS_NO_FIT';detail='Inputs/environment verified. No preprocessing/model fit.'
            raise PreflightComplete()
        scratch=out/'scratch';scratch.mkdir()
        for key in ['TMP','TEMP','TMPDIR','JOBLIB_TEMP_FOLDER']:os.environ[key]=str(scratch)
        tempfile.tempdir=str(scratch)
        policy=AccessPolicy(out,devpath,claimfile);sys.addaudithook(policy.audit)
        dev=pd.read_parquet(devpath)
        for name in ['DECISION_DATE','SOURCE_REPDTE']:dev[name]=pd.to_datetime(dev[name],errors='raise')
        observed_dev=audit_dev(dev,expected=True);dump(out/'DEVELOPMENT_INPUT_CONTRACT.json',observed_dev)
        metrics=pd.read_csv(HERE/'REF/hgb_candidate_fold_metrics.csv',float_precision='round_trip')
        # Validate every fold and reference before the first new HGB fit.
        for fold in protocol['validation']['folds']:
            tr,va,count=fold_contract(dev,fold);load_reference(fold['id'],va,metrics,config);del tr,va
        require(claimfile.parent==out.parent.parent and claimfile.name=='THREE_FITS_EXECUTION_CLAIM.json','Unexpected execution-claim location')
        claim=create_claim(claimfile,out,command)
        with threadpool_limits(limits=1):
            for fold in protocol['validation']['folds']:
                name=fold['id'];job=out/name;job.mkdir();tr,va,count=fold_contract(dev,fold)
                full,full_ap,full_auc=load_reference(name,va,metrics,config)
                event('FOLD_TRAINING_PREPROCESSOR_START',fold=name,counts=count)
                prep=make_preprocessor(clip=False)
                ztr=prep.fit_transform(tr[FEATURES]);state=preprocess_state(prep)
                require(list(prep.output_indices_['continuous'].indices(30))==[0,12,1] and list(prep.output_indices_['binary'].indices(30))==[12,15,1] and list(prep.output_indices_['missing'].indices(30))==[15,30,1],'Actual transformer block order differs')
                zva=prep.transform(va[FEATURES]);require(preprocess_state(prep)==state,'Validation altered fitted preprocessing')
                for index,feature in [(17,'asset_log_growth_1q'),(18,'asset_log_growth_4q')]:
                    require(np.array_equal(zva[:,index],va[feature].isna().to_numpy(dtype=float)),'Missing-indicator positions do not match financial features')
                xtr=remove_indicators(ztr,contract);xva=remove_indicators(zva,contract)
                require(xtr.shape[1]==xva.shape[1]==28 and np.isfinite(xtr).all() and np.isfinite(xva).all(),'Invalid ablated transformation')
                require(np.array_equal(xva[:,2:4],zva[:,2:4]),'Continuous asset-growth values were altered')
                dump(job/'PREPROCESSING_STATE.json',dict(state=state,train_shape=list(xtr.shape),validation_shape=list(xva.shape),feature_contract=contract))
                # Save a bounded diagnostic transform sample, not a new data cohort.
                np.savez_compressed(job/'TRANSFORM_SAMPLE.npz',full30=zva[:128],ablated28=xva[:128])
                del ztr,zva;gc.collect()
                model=HistGradientBoostingClassifier(**config['HGB'])
                reserve_fit_attempt(claimfile,claim,name)
                event('AUTHORIZED_HGB_FIT_START',fold=name,fit_attempt=claim['fit_attempts'],width=28)
                tick=time.perf_counter();model.fit(xtr,tr.Y_4Q.to_numpy(dtype=np.int8));fit_seconds=time.perf_counter()-tick
                require(int(model.n_iter_)==150 and int(model.n_features_in_)==28,'Estimator iteration/feature contract')
                score=model.predict_proba(xva)[:,1]
                require(score.shape==(len(va),) and np.isfinite(score).all() and ((score>=0)&(score<=1)).all(),'Invalid development predictions')
                require(preprocess_state(prep)==state,'Prediction changed preprocessing state')
                ap=float(average_precision_score(va.Y_4Q,score));auc=float(roc_auc_score(va.Y_4Q,score))
                np.savez_compressed(job/'DEVELOPMENT_VALIDATION_PREDICTIONS.npz',cert=va.CERT.to_numpy(dtype=np.int64),decision_day=va.DECISION_DATE.to_numpy(dtype='datetime64[D]').astype(np.int64),y=va.Y_4Q.to_numpy(dtype=np.uint8),score_ablated=score,score_full_archived=full)
                row=dict(fold=name,status='COMPLETED_REVIEW_REQUIRED',train_rows=count['train'],validation_rows=count['valid'],full_AP=full_ap,ablated_AP=ap,delta_AP_ablated_minus_full=ap-full_ap,full_ROC_AUC=full_auc,ablated_ROC_AUC=auc,delta_ROC_AUC_ablated_minus_full=auc-full_auc,transformed_width=28,fit_attempt=claim['fit_attempts'])
                rows.append(row);write_metrics(out,rows)
                outputs={p.name:sha(p) for p in job.iterdir() if p.is_file()}
                dump(job/'FOLD_EXECUTION_RECORD.json',dict(command=command,environment_sha256=sha(out/'ENVIRONMENT.json'),input_development_sha256=dev_digest,input_reference_hashes=before,model_parameters=model.get_params(),fold_definition=fold,counts=count,metrics=row,fit_seconds=fit_seconds,output_sha256=outputs,status='PASS_FOLD_NUMERICAL_CONTRACT__INDEPENDENT_REVIEW_REQUIRED'))
                event('FOLD_COMPLETE',fold=name,AP=ap,ROC_AUC=auc,delta_AP=ap-full_ap)
                del prep,model,xtr,xva,tr,va,score,full;gc.collect()
        require(claim['fit_attempts']==3 and len(rows)==3,'Exactly three fits required')
        mean={k:float(np.mean([row[k] for row in rows])) for k in ['full_AP','ablated_AP','delta_AP_ablated_minus_full','full_ROC_AUC','ablated_ROC_AUC','delta_ROC_AUC_ablated_minus_full']}
        rows.append(dict(fold='UNWEIGHTED_MEAN',status='COMPLETED_REVIEW_REQUIRED',**mean,transformed_width=28))
        status='COMPLETED_3_FITS_REVIEW_REQUIRED'
        detail='Three development fold fits completed. Delta = ablated minus full. Report either sign without changing the selected primary model/threshold. Independent output inspection still required.'
        claim['state']=status;update_claim(claimfile,claim)
    except PreflightComplete:
        pass
    except Blocked as error:
        status='BLOCKED';detail=str(error);event('BLOCKED',reason=detail)
    except Exception as error:
        status='FAIL';detail=type(error).__name__+': '+str(error)
        (out/'ERROR_TRACEBACK.txt').write_text(traceback.format_exc(),encoding='utf-8');event('FAIL',reason=detail)
    finally:
        if dev_digest is not None:
            after_dev=sha(devpath)
            if after_dev!=dev_digest:status='FAIL';detail+='; DEVELOPMENT INPUT CHANGED'
        else:after_dev=None
        after={name:sha(HERE/name) for name in before}
        if after!=before:status='FAIL';detail+='; REFERENCE INPUT CHANGED'
        if not rows:
            rows=[dict(fold=f,status=status) for f in FOLDS]
        write_metrics(out,rows);render(out,status,rows,detail)
        artifacts={p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file()}
        record=dict(status=status,detail=detail,started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),command=command,environment=observed,
                    inputs_sha256_before=dict(development=dev_digest,references=before),inputs_sha256_after=dict(development=after_dev,references=after),output_sha256=artifacts,
                    HGB_fit_attempts=claim['fit_attempts'] if claim else 0,final_test_access_permitted=False,scope='Development-only late robustness analysis; NOT historical pre-lock execution or full E2E',
                    guard_limit='Python audit hook plus exact explicit input paths and hashes; not an OS/native-Arrow sandbox')
        dump(out/'RUN_RECORD.json',record)
        print('FINAL_STATUS',status,detail,flush=True)
    return status

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',type=Path,default=Path(os.environ.get('USERPROFILE',str(Path.home()))))
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--claim-file',type=Path,required=True)
    parser.add_argument('--preflight-only',action='store_true')
    args=parser.parse_args()
    status=run(args.profile,args.out.resolve(),args.claim_file.resolve(),args.preflight_only)
    return 0 if status in {'COMPLETED_3_FITS_REVIEW_REQUIRED','PREFLIGHT_PASS_NO_FIT'} else 2 if status=='BLOCKED' else 1

if __name__=='__main__':sys.exit(main())
