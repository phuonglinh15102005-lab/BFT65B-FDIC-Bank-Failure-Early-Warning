"""Continuous RAW/PREPARED -> native 2A -> NEW native 2B -> 2C/PIT -> DEV.

No frozen checkpoint fallback, downloads, modelling, tuning or test scoring.
"""
from pathlib import Path
import csv,hashlib,json,os,subprocess,sys,traceback,uuid,zipfile
from datetime import datetime
from workflow.common import ROOT,Blocked,require,read_json,save_json,sha,utc,load_config,resolve_profile,inputs_for,validate_output,verify_source_manifest,package_hashes
from workflow.engine import choose_python,stream_command,reference,safe_hash
from workflow.continuous_contract import SOURCES,stages,artifact,command_arguments,check_lineage

def plan(start='raw'):
    evidence=ROOT/'config/continuous_verification.json'
    return dict(mode='continuous-data-only',start=start,stages=stages(start),source=SOURCES,
        fresh_parent_required=True,frozen_checkpoint_fallback=False,
        exogenous_inputs='Frozen raw/prepared snapshot and frozen cached HTTP source evidence; original outputs are comparison-only',
        real_data_execution='NOT_EXECUTED_BY_PLAN_COMMAND',
        historical_execution_evidence=read_json(evidence) if evidence.is_file() else dict(status='NOT_EXECUTED'),
        full_clean_room_E2E='NOT_EXECUTED')

def preflight(config,inputs,start):
    """Hash original inputs only. Missing evidence is BLOCKED, changed evidence FAIL."""
    wanted={};missing=[];errors=[]
    def add(path,expected=None,role='reference'):
        path=Path(path).resolve();key=str(path)
        if not path.is_file():missing.append(dict(path=key,role=role));return
        actual=sha(path)
        if expected is not None and actual!=expected:errors.append(dict(path=key,reason='SHA-256 differs from frozen/archived identity',expected=expected,actual=actual))
        wanted[key]=dict(sha256=actual,role=role)
    # Existing prepared values are anchored by the previously delivered 174-file list.
    prepared=read_json(ROOT/'config/prepared_snapshot_manifest.json')
    for item in prepared:add(inputs['prepared_audit']/item['relative_path'],item['sha256'],'prepared-reference' if start=='raw' else 'prepared-source')
    for name,item in config['reference_files'].items():add(reference(config,inputs,name),item['sha256'],'frozen-output-comparison-only')
    for name,h in read_json(ROOT/'config/step2b_snapshot_hashes.json').items():add(inputs['step2b']/name,h,'frozen-Part2B-reference-only')
    body_manifest=inputs['step2b']/'sources_manifest.json'
    if body_manifest.is_file():
        try:
            for item in read_json(body_manifest)['requests']:
                key=hashlib.sha256(item['url'].encode()).hexdigest();cache=inputs['step2b']/'request_cache'
                add(cache/(key+'.body'),item['sha256'],'Part2B-cached-source-body')
                add(cache/(key+'.json'),role='Part2B-cached-source-metadata')
        except Exception as e:errors.append(dict(path=str(body_manifest),reason='Invalid archived cache manifest: '+str(e)))
    for item in read_json(ROOT/'config/frozen_scope_requests.json'):
        key=hashlib.sha256(item['url'].encode()).hexdigest();cache=inputs['step2c']/'request_cache'
        add(cache/(key+'.body'),item['sha256'],'Part2C-cached-scope-body');add(cache/(key+'.json'),role='Part2C-cached-scope-metadata')
    # Include every possible cached hit for before/after preservation; no network fallback.
    for folder in [inputs['step2b']/'request_cache',inputs['step2c']/'request_cache']:
        if not folder.is_dir():missing.append(dict(path=str(folder),role='required-offline-cache-directory'))
        else:
            for p in sorted(folder.iterdir()):
                if p.is_file() and p.suffix in {'.body','.json'}:
                    if str(p.resolve()) not in wanted:add(p,role='offline-cache')
            for meta in sorted(folder.glob('*.json')):
                try:
                    v=read_json(meta);key=hashlib.sha256(v['url'].encode()).hexdigest();body=folder/(key+'.body')
                    require(meta.stem==key,'Cache filename does not match URL')
                    require(body.is_file() and sha(body)==v['sha256'],'Cache body/metadata mismatch')
                except Exception as e:errors.append(dict(path=str(meta),reason=str(e)))
    raw_ledger_status='NOT_REQUIRED_PREPARED_START'
    if start=='raw':
        ledger=inputs['prepared_audit']/'file_checksums.csv';add(ledger,role='original-raw-checksum-ledger')
        raw_names=['manifest_financials.json','institutions.parquet','failures.parquet']
        raw_names += ['financials/'+Path(i['relative_path']).name for i in prepared if '/financials/' in i['relative_path']]
        expected={}
        if ledger.is_file():
            try:
                with ledger.open(encoding='utf-8-sig',newline='') as f:records=list(csv.DictReader(f))
                for row in records:
                    rel=Path(row['file'].replace('\\','/'))
                    require(not rel.is_absolute() and '..' not in rel.parts and ':' not in rel.as_posix(),'Unsafe archived raw-ledger path')
                    require(rel.as_posix() not in expected,'Duplicate raw-ledger filename')
                    expected[rel.as_posix()]=row['sha256']
                require(set(expected)==set(raw_names),'Archived raw-ledger scope must contain 170 quarter files, two small tables and manifest')
                raw_ledger_status='CHECKED_AGAINST_ARCHIVED_LEDGER_NOT_INDEPENDENTLY_PREPINNED'
            except Exception as e:
                errors.append(dict(path=str(ledger),reason='Invalid original raw ledger: '+str(e)))
                raw_ledger_status='INVALID_RAW_LEDGER'
        else:raw_ledger_status='MISSING_REQUIRED_ARCHIVED_RAW_LEDGER'
        for name in raw_names:add(inputs['raw_fdic_dir']/name,expected.get(name),'raw-source')
    return dict(status='FAIL' if errors else 'BLOCKED' if missing else 'PASS',inputs=wanted,
        missing=missing,errors=errors,raw_ledger_status=raw_ledger_status,
        note='Ledger hash recorded now; matching 172 prepared Parquet references independently anchors downstream numerical reproduction')

def comparisons(stage,run,config,inputs):
    out=artifact(run,stage);items=[]
    def parquet(name,new,ref,keys,rtol=0.,atol=0.):
        items.append(dict(id=name,new=str(new),reference=str(ref),keys=keys,rtol=rtol,atol=atol))
    if stage=='prepare':
        for item in read_json(ROOT/'config/prepared_snapshot_manifest.json'):
            rel=item['relative_path']
            if not rel.endswith('.parquet'):continue
            if '/financials/' in rel:keys=['CERT','REPDTE'];label='prepared_'+Path(rel).stem.replace('=','_')
            elif Path(rel).name=='institutions.parquet':keys=['CERT'];label='prepared_institutions'
            else:keys=['SOURCE_ROW'];label='prepared_failures_all'
            parquet(label,out/rel,inputs['prepared_audit']/rel,keys)
    elif stage=='base':parquet('base',out/'panel_base.parquet',reference(config,inputs,'base'),['CERT','REPDTE'])
    elif stage=='exits':
        for filename in ['history_events_AUDIT_ONLY.csv','bank_exit_evidence_AUDIT_ONLY.csv']:
            items.append(dict(id='part2b_'+filename[:-4],kind='csv',new=str(out/'review_AUDIT_ONLY'/filename),reference=str(inputs['step2b']/'review_AUDIT_ONLY'/filename)))
    elif stage=='clean':
        parquet('clean',out/'panel_clean.parquet',reference(config,inputs,'clean'),['CERT','REPDTE'])
        parquet('pit',out/'panel_pit_base.parquet',reference(config,inputs,'pit'),['CERT','DECISION_DATE'])
        items.append(dict(id='event_registry',kind='csv',new=str(out/'review_AUDIT_ONLY/bank_event_registry_AUDIT_ONLY.csv'),
            reference=str(reference(config,inputs,'registry')),reference_member='review_AUDIT_ONLY/bank_event_registry_AUDIT_ONLY.csv'))
    else:parquet('development',out/'development_primary_binary_v2.parquet',reference(config,inputs,'development'),['CERT','DECISION_DATE'],1e-9,1e-10)
    return items

def parent_inputs(stage,run,inputs,start):
    folders=[];files=[]
    if stage=='base':folders=[artifact(run,'prepare')] if start=='raw' else []
    if stage=='exits':folders=[artifact(run,'base')]
    if stage=='clean':folders=[artifact(run,'base'),artifact(run,'exits')]
    if stage=='features':files=[artifact(run,'clean')/n for n in ['panel_clean.parquet','panel_pit_base.parquet','part2_clean_review_bundle.zip']]
    files += [p for folder in folders for p in folder.rglob('*') if p.is_file()]
    return {str(p.resolve()):sha(p) for p in files}

def run_stage(stage,run,config,inputs,start,python,environment):
    job=run/stage;job.mkdir(exist_ok=False);before={};record=dict(stage=stage,status='FAIL',started_utc=utc(),environment=environment,
        new_model_fits=0,final_test_inference=False,comparison_results=[],lineage_checks=[])
    try:
        before=parent_inputs(stage,run,inputs,start)
        args=command_arguments(stage,run,inputs,start)
        spec=dict(stage=stage,run=str(run),start=start,inputs={k:str(v) for k,v in inputs.items()},arguments=args)
        save_json(job/'PRODUCER_SPEC.json',spec)
        cmd=[str(python),'-B',str(ROOT/'workflow/continuous_worker.py'),'--spec',str(job/'PRODUCER_SPEC.json')]
        record['command']=cmd;record['producer_arguments']=args
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1'}
        code=stream_command(cmd,job,env);worker=read_json(job/'WORKER_RESULT.json') if (job/'WORKER_RESULT.json').is_file() else {}
        if code:
            if worker.get('status')=='BLOCKED':raise Blocked(worker.get('error') or 'Producer prerequisite missing')
            raise ValueError('Native producer failed; inspect WORKER_RESULT/STDERR')
        record['lineage_checks']=check_lineage(stage,run,inputs,start)
        spec=dict(out=str(job/'comparison'),datasets=comparisons(stage,run,config,inputs));save_json(job/'COMPARISON_SPEC.json',spec)
        logs=job/'comparison_command';logs.mkdir()
        cmd=[str(python),'-B',str(ROOT/'workflow/continuous_compare.py'),'--spec',str(job/'COMPARISON_SPEC.json')]
        record['comparison_command']=cmd
        code=stream_command(cmd,logs,env)
        result=read_json(job/'comparison/COMPARISON_RESULT.json')
        if code==2:raise Blocked(result.get('error') or 'Comparison unavailable')
        require(code==0 and result['status']=='PASS','Schema/key/value/row-count/reference comparison failed')
        record.update(status='PASS',comparison_results=result['results'],artifact_directory=str(artifact(run,stage)))
    except Blocked as e:record.update(status='BLOCKED',reason=str(e))
    except Exception as e:record.update(status='FAIL',reason=type(e).__name__+': '+str(e),traceback=traceback.format_exc())
    after={n:sha(Path(n)) if Path(n).is_file() else None for n in before}
    if before!=after:record.update(status='FAIL',reason='A fresh parent file changed during child execution')
    record.update(input_sha256_before=before,input_sha256_after=after,finished_utc=utc(),output_sha256=package_hashes(job))
    save_json(job/'STAGE_RESULT.json',record);return record

def write_exports(out,result):
    save_json(out/'CONTINUOUS_RESULT.json',result)
    with (out/'STAGE_STATUS.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['stage','status','reason'])
        for name,r in result['stages'].items():w.writerow([name,r['status'],r.get('reason','')])
        w.writerow(['full-clean-room-E2E','NOT_EXECUTED','Live acquisition/models/final-test inference excluded'])
    columns=[];datasets=[]
    for s in result['stages'].values():
        for d in s.get('comparison_results',[]):
            columns+=d.get('columns',[])
            datasets.append(dict(dataset=d['dataset'],status=d['status'],new_rows=d['new_rows'],reference_rows=d['reference_rows'],
                schema_equal=d['schema_equal'],byte_identical=d['byte_identical'],new_sha256=d['new_sha256'],reference_sha256=d['reference_sha256']))
    for name,records in [('NUMERICAL_COMPARISON.csv',columns),('DATASET_COMPARISON.csv',datasets)]:
        if records:
            with (out/name).open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    keep=[]
    for p in out.rglob('*'):
        rel=p.relative_to(out)
        if not p.is_file() or 'artifacts' in rel.parts or 'scratch' in rel.parts:continue
        if p.suffix in {'.json','.txt'} or p.name in {'STAGE_STATUS.csv','NUMERICAL_COMPARISON.csv','DATASET_COMPARISON.csv'}:keep.append(p)
    # Exported-file manifest is independent of unavailable bank-row output payloads.
    save_json(out/'EXPORTED_FILE_MANIFEST.json',{p.relative_to(out).as_posix():sha(p) for p in keep})
    keep.append(out/'EXPORTED_FILE_MANIFEST.json')
    target=out.with_name(out.name+'_GUI_LAI_CHO_CODEX.zip')
    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(keep):z.write(p,p.relative_to(out).as_posix())
    print('SEND_THIS_ZIP',target,flush=True);return target

def execute(args):
    config=load_config(args.config);profile=resolve_profile(config,args.profile);inputs=inputs_for(config,profile)
    before_source=verify_source_manifest()
    default=Path(os.environ.get('LOCALAPPDATA',os.environ.get('TEMP',str(Path.home()))))/'BFT65B_CONTINUOUS_REPRO'/(datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8])
    out=validate_output(args.out or default,inputs);out.mkdir(parents=True,exist_ok=False)
    started=utc();records={};prep=dict(status='FAIL',inputs={},missing=[],errors=[]);python=None;observed=None;error=None;units=None
    try:
        print('Continuous preflight: checking original snapshot/cache/reference identities...',flush=True)
        prep=preflight(config,inputs,args.start);save_json(out/'PREFLIGHT.json',prep)
        python,observed,attempts=choose_python(profile,args.python_engineering);save_json(out/'EXISTING_ENVIRONMENTS.json',attempts)
        if prep['status']=='FAIL':raise ValueError('Original input/reference/cache integrity failed')
        if prep['status']=='BLOCKED':raise Blocked('Required original inputs/cache are unavailable; see PREFLIGHT missing list')
        if python is None:raise Blocked('Exact engineering interpreter unavailable; no installation/version relaxation')
        # Newly changed QA contracts, not any closed scientific check.
        job=out/'unit_tests';job.mkdir()
        cmd=[str(python),'-B','-m','unittest','discover','-s',str(ROOT/'tests'),'-v']
        units=dict(command=cmd,status='FAIL')
        code=stream_command(cmd,job,{**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1'},cwd=ROOT)
        units['status']='PASS' if code==0 else 'FAIL';save_json(job/'RESULT.json',units)
        require(code==0,'Updated unit suite failed; no real producers executed')
        for stage in stages(args.start):
            print('CONTINUOUS_STAGE',stage,flush=True)
            records[stage]=run_stage(stage,out,config,inputs,args.start,python,observed)
            print('CONTINUOUS_STAGE_RESULT',stage,records[stage]['status'],flush=True)
            if records[stage]['status']=='BLOCKED':raise Blocked('Parent stage blocked: '+stage)
            require(records[stage]['status']=='PASS','Parent stage failed: '+stage)
    except Blocked as e:error=dict(status='BLOCKED',reason=str(e))
    except Exception as e:error=dict(status='FAIL',reason=type(e).__name__+': '+str(e),traceback=traceback.format_exc())
    finally:
        for stage in stages(args.start):
            if stage not in records:records[stage]=dict(stage=stage,status='NOT_EXECUTED',reason='Preflight or earlier stage did not pass; no frozen checkpoint fallback',new_model_fits=0)
        input_after={p:sha(Path(p)) if Path(p).is_file() else None for p in prep.get('inputs',{})}
        input_before={p:v['sha256'] for p,v in prep.get('inputs',{}).items()}
        if input_after!=input_before:error=dict(status='FAIL',reason='An original source/reference/cache changed')
        try:require(verify_source_manifest()==before_source,'Source changed during execution')
        except Exception as e:error=dict(status='FAIL',reason='Source integrity error: '+str(e))
        status=error['status'] if error else 'PASS_CONTINUOUS_'+args.start.upper()+'_TO_DEVELOPMENT_REPLAY_REVIEW_REQUIRED'
        result=dict(status=status,start=args.start,started_utc=started,finished_utc=utc(),
            command=[sys.executable,'-B',str(ROOT/'run.py'),*sys.argv[1:]],environment=observed,unit_tests=units,error=error,
            config_sha256=safe_hash(args.config),source_manifest_sha256=safe_hash(ROOT/'config/source_manifest.json'),stages=records,
            preflight_status=prep['status'],input_sha256_before=input_before,input_sha256_after=input_after,
            continuous_data_replay='NOT_EXECUTED' if not any('command' in v for v in records.values()) else 'COMPLETED' if not error else 'INCOMPLETE',
            fresh_parent_required=True,frozen_checkpoint_fallback=False,new_model_fits=0,final_test_inference=False,
            full_clean_room_E2E='NOT_EXECUTED',live_acquisition='NOT_EXECUTED',model_selection_refit_scoring='NOT_EXECUTED',
            claim_boundary='PASS only for the declared raw/prepared-to-development chain, not full Parts1–5/model E2E')
        export=write_exports(out,result)
        if args.reveal and os.name=='nt':subprocess.Popen(['explorer.exe','/select,'+str(export)])
    return 0 if status.startswith('PASS') else 2 if status=='BLOCKED' else 1
