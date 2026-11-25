"""Parquet value checks plus exact CSV row-multiset checks, aggregate output only."""
from pathlib import Path
from collections import Counter
import argparse,csv,hashlib,io,json,os,sys,tempfile,traceback,zipfile
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workflow.common import Blocked,require,read_json,save_json,sha,utc
from workflow.compare import compare_parquet
from workflow.policy import Guard

def csv_payload(path,member=None):
    if member:
        with zipfile.ZipFile(path) as z:return z.read(member)
    return Path(path).read_bytes()

def csv_signature(payload):
    reader=csv.DictReader(io.StringIO(payload.decode('utf-8-sig'),newline=''))
    fields=reader.fieldnames or [];require(len(fields)==len(set(fields)),'Duplicate CSV headers')
    counter=Counter()
    for row in reader:
        require(None not in row and all(x is not None for x in row.values()),'CSV row/header mismatch')
        counter[json.dumps(row,sort_keys=True,ensure_ascii=False,separators=(',',':'))]+=1
    canonical=json.dumps(sorted(counter.items()),ensure_ascii=False,separators=(',',':')).encode()
    return fields,counter,hashlib.sha256(canonical).hexdigest()

def compare_csv(spec):
    left=csv_payload(spec['new'],spec.get('new_member'));right=csv_payload(spec['reference'],spec.get('reference_member'))
    lf,lc,lh=csv_signature(left);rf,rc,rh=csv_signature(right)
    missing=sum((rc-lc).values());extra=sum((lc-rc).values())
    return dict(dataset=spec['id'],kind='csv_row_multiset',status='PASS_CSV_EQUIVALENCE' if lf==rf and not missing and not extra else 'FAIL',
        schema_equal=lf==rf,new_rows=sum(lc.values()),reference_rows=sum(rc.values()),new_columns=lf,reference_columns=rf,
        missing_rows=missing,extra_rows=extra,new_canonical_sha256=lh,reference_canonical_sha256=rh,
        new_sha256=hashlib.sha256(left).hexdigest(),reference_sha256=hashlib.sha256(right).hexdigest(),byte_identical=left==right)

def main():
    p=argparse.ArgumentParser();p.add_argument('--spec',type=Path,required=True);args=p.parse_args();spec=read_json(args.spec)
    out=Path(spec['out']).resolve();out.mkdir(exist_ok=False);scratch=out/'scratch';scratch.mkdir()
    for k in ['TMP','TEMP','TMPDIR','POLARS_TEMP_DIR']:os.environ[k]=str(scratch)
    os.environ['POLARS_MAX_THREADS']='2';tempfile.tempdir=str(scratch)
    status='FAIL';results=[];started=utc();error=None
    try:
        Guard(out).install()
        for ds in spec['datasets']:
            target=out/(ds['id']+'.json')
            if ds.get('kind')=='csv':result=compare_csv(ds);save_json(target,result)
            else:result=compare_parquet(Path(ds['new']),Path(ds['reference']),ds['keys'],ds['id'],target,ds['rtol'],ds['atol'])
            results.append(result)
        status='PASS' if all(r['status'].startswith('PASS') for r in results) else 'FAIL'
    except Exception as e:
        error=type(e).__name__+': '+str(e);status='BLOCKED' if isinstance(e,(Blocked,FileNotFoundError,ModuleNotFoundError)) else 'FAIL'
        (out/'ERROR_TRACEBACK.txt').write_text(traceback.format_exc(),encoding='utf-8')
    save_json(out/'COMPARISON_RESULT.json',dict(status=status,error=error,started_utc=started,finished_utc=utc(),
        command=[sys.executable,'-B',str(Path(__file__)),*sys.argv[1:]],spec_sha256=sha(args.spec),results=results))
    print(status,flush=True);return 0 if status=='PASS' else 2 if status=='BLOCKED' else 1
if __name__=='__main__':sys.exit(main())
