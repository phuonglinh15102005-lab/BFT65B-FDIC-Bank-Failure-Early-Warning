"""Small SYNTHETIC Parquet controls; no bank data, models or closed metric checks."""
from pathlib import Path
import argparse,os,sys,tempfile,traceback
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workflow.common import Blocked,save_json,sha,utc
from workflow.compare import compare_parquet

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    for key in ['TMP','TEMP','TMPDIR','POLARS_TEMP_DIR']:os.environ[key]=str(out)
    os.environ['POLARS_MAX_THREADS']='2';tempfile.tempdir=str(out)
    status='FAIL';cases=[];detail=None;start=utc()
    try:
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
            import polars as pl
        except ImportError as error:raise Blocked('Synthetic Parquet comparator check needs existing Polars/PyArrow: '+str(error))
        schema=pa.schema([('CERT',pa.int64()),('x',pa.float64()),('label',pa.int8())])
        original={'CERT':[1,2,3,4],'x':[None,float('nan'),1.,float('inf')],'label':[0,1,0,1]}
        reference=out/'reference.parquet';pq.write_table(pa.table(original,schema=schema),reference)
        def case(name,values,expected_pass,rtol=1e-9,atol=1e-10,variant_schema=None):
            new=out/(name+'.parquet');pq.write_table(pa.table(values,schema=variant_schema or schema),new)
            result=compare_parquet(new,reference,['CERT'],name,out/(name+'.json'),rtol,atol)
            passed=result['status'].startswith('PASS')
            if passed!=expected_pass:raise AssertionError('Comparator control behaved incorrectly: '+name)
            cases.append(dict(case=name,status='PASS_CONTROL',expected_numerical_equivalence=expected_pass,actual_comparison_status=result['status'],new_sha256=sha(new),reference_sha256=sha(reference)))
        case('identical',original,True)
        case('reordered',{k:list(reversed(v)) for k,v in original.items()},True)
        changed={k:list(v) for k,v in original.items()};changed['x'][3]=2.;case('finite_vs_infinite',changed,False)
        changed={k:list(v) for k,v in original.items()};changed['x'][3]=float('-inf');case('opposite_infinities',changed,False)
        changed={k:list(v) for k,v in original.items()};changed['x'][0]=float('nan');case('null_to_nan',changed,False)
        changed={k:list(v) for k,v in original.items()};changed['CERT'][1]=1;case('duplicate_keys',changed,False)
        changed={k:list(v) for k,v in original.items()};changed['label'][2]=1;case('label_mutation',changed,False)
        changed={k:list(v) for k,v in original.items()};changed['x'][2]+=1e-12;case('tolerated_float_roundoff',changed,True)
        case('strict_float_roundoff_rejected',changed,False,rtol=0.,atol=0.)
        case('wrong_schema',original,False,variant_schema=pa.schema([('CERT',pa.int64()),('x',pa.float64()),('label',pa.int64())]))
        status='PASS';detail='Ten synthetic Arrow/Polars controls;expected mismatches correctly fail. No bank data or estimators.'
    except Blocked as error:status='BLOCKED';detail=str(error)
    except Exception as error:detail=type(error).__name__+': '+str(error);(out/'ERROR_TRACEBACK.txt').write_text(traceback.format_exc())
    result=dict(status=status,detail=detail,started_utc=start,finished_utc=utc(),command=[sys.executable,'-B',str(Path(__file__)),*sys.argv[1:]],cases=cases)
    save_json(out/'SELFTEST_RESULT.json',result);print(status,detail,flush=True)
    return 0 if status=='PASS' else 2 if status=='BLOCKED' else 1

if __name__=='__main__':sys.exit(main())
