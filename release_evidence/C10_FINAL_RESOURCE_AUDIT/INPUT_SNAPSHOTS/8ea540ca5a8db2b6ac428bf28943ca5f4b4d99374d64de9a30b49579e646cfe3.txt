"""Non-executing source/resource/publication audit for this code release."""
from pathlib import Path
import argparse,ast,csv,json,os,sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workflow.common import ROOT,sha,read_json,save_json,validate_output,utc

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    out=validate_output(args.out,{});out.mkdir(parents=True)
    errors=[];sources=[];resources=[]
    science_roots={p.name for p in ROOT.iterdir() if p.is_dir() and p.name[:2].isdigit() and p.name!='00_ASSIGNMENT'}
    for path in sorted(ROOT.rglob('*.py')):
        try:tree=ast.parse(path.read_bytes())
        except SyntaxError as error:errors.append(dict(file=str(path.relative_to(ROOT)),error=str(error)));continue
        calls=[];imports=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):imports += [x.name for x in node.names]
            if isinstance(node,ast.ImportFrom):imports += [node.module or '']
            if isinstance(node,ast.Call):
                name=ast.unparse(node.func)
                if any(x in name for x in ['read_parquet','scan_parquet','write_parquet','to_parquet','fit','predict','load','urlopen','subprocess.']):calls.append(dict(line=node.lineno,call=ast.unparse(node)[:400]))
                if isinstance(node.func,ast.Attribute) and node.func.attr=='with_name' and node.args and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str):
                    sibling=path.with_name(node.args[0].value)
                    item=dict(source=path.relative_to(ROOT).as_posix(),line=node.lineno,resource=sibling.relative_to(ROOT).as_posix(),exists=sibling.is_file())
                    resources.append(item)
                    # A literal .py or protocol resource is code-required; dataset/output names are external by design.
                    if sibling.suffix in {'.py','.sha256'} and not sibling.is_file():errors.append(item)
        sources.append(dict(file=path.relative_to(ROOT).as_posix(),sha256=sha(path),imports=sorted(set(imports)),calls=calls,science_source=path.relative_to(ROOT).parts[0] in science_roots))
    for path in ROOT.rglob('part5_protocol_freeze.json'):
        if sha(path)!='994f72de6e2446916db8c2fcd36847c45cc68eb6fef5ef67f07acc0476c6d911':errors.append(dict(error='Protocol digest mismatch',file=str(path)))
    prohibited=[p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and p.suffix.lower() in {'.parquet','.joblib','.pkl','.pickle','.npz','.npy','.gz','.zip','.sqlite','.db'}]
    if prohibited:errors.append(dict(error='Prohibited publication payload',files=prohibited))
    input_required=['config/default.json','config/stages.json','config/environments.json','config/prepared_snapshot_manifest.json','config/step2b_snapshot_hashes.json','config/frozen_scope_requests.json','04_PART4_FEATURE_PIPELINE/part5_protocol_freeze.sha256']
    for name in input_required:
        if not (ROOT/name).is_file():errors.append(dict(error='Missing executable metadata',file=name))
    result=dict(status='FAIL' if errors else 'PASS_SOURCE_RESOURCE_AND_PUBLICATION_CONTENT',errors=errors,python_sources=len(sources),science_python_sources=sum(x['science_source'] for x in sources),sources=sources,literal_sibling_resources=resources,
                no_raw_model_prediction_archives=not prohibited,full_E2E='NOT_EXECUTED',new_real_data_producers='PENDING_WINDOWS',command=[sys.executable,'-B',str(Path(__file__)),*sys.argv[1:]],finished_utc=utc())
    save_json(out/'FINAL_SOURCE_RESOURCE_AUDIT.json',result)
    print(json.dumps({k:result[k] for k in ['status','python_sources','science_python_sources','errors']},indent=2))
    return 0 if not errors else 1

if __name__=='__main__':sys.exit(main())
