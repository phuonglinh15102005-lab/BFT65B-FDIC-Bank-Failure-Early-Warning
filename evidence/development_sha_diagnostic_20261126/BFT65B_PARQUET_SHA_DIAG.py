"""Read-only diagnostic for the exact original and 25-Nov development Parquet.
No model, no test, no raw row exports, no changes to either Parquet. Needs pyarrow/numpy.
Usage: python -B BFT65B_PARQUET_SHA_DIAG.py --out D:/BFT_SHA_DIAG.json
Optional: --root PATH (repeatable) or --original FILE --replay FILE.
"""
import argparse, hashlib, json, math, os, platform, sys
from pathlib import Path
ORIG='d365ce25204a3dcace715db4cea259c94b1b1abba4822c7bcf2b050a1c7f6a73'
REPLAY='a7295637cc68f91bc02aa8c78e8d952b12abffda30fbb420e3c8a0d0d2662b61'
NAME='development_primary_binary_v2.parquet'
KEYS=['CERT','DECISION_DATE']; EXPECTED_ROWS=1231631

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()
def need(x,m):
    if not x: raise RuntimeError(m)
def default_roots():
    home=Path.home();roots=[home/'BFT65B_outputs',home/'Downloads',home/'Desktop',home/'Documents']
    for disk in (Path('C:/'),Path('D:/')):
        if disk.exists():
            roots.extend(p for p in disk.iterdir() if p.is_dir() and (p.name.upper().startswith(('BFT','S5','FINAL_EXECUTION'))))
    return [p for p in roots if p.exists()]
def locate(roots):
    found={};seen=set()
    for root in roots:
        if not root.exists():continue
        for d,dirs,files in os.walk(root,followlinks=False):
            dirs[:]=[x for x in dirs if x not in ('.git','__pycache__','node_modules','System Volume Information','$RECYCLE.BIN') and not x.startswith('.')]
            if NAME not in files:continue
            p=Path(d)/NAME
            try:
                key=str(p.resolve())
                if key in seen:continue
                seen.add(key); h=sha(p)
                if h in (ORIG,REPLAY):found[h]=p;print('Found exact', 'original' if h==ORIG else 'replay',flush=True)
                if len(found)==2:return found
            except (OSError,PermissionError):continue
    return found

def summarize_metadata(pf):
    m=pf.metadata
    rows=[m.row_group(i).num_rows for i in range(m.num_row_groups)]
    # No raw min/max values, key values, file paths or serialized metadata contents exported.
    props=[]
    for j in range(m.num_columns):
        cs=[m.row_group(i).column(j) for i in range(m.num_row_groups)]
        props.append({'field':cs[0].path_in_schema,'physical_type':cs[0].physical_type,'compression':sorted({str(c.compression) for c in cs}),'encodings':sorted({str(e) for c in cs for e in c.encodings}),'stats_presence':[bool(c.is_stats_set) for c in cs],'compressed_bytes':sum(c.total_compressed_size for c in cs),'uncompressed_bytes':sum(c.total_uncompressed_size for c in cs)})
    md=m.metadata or {}; mdhash={k.decode('utf-8',errors='replace'):hashlib.sha256(v).hexdigest() for k,v in md.items()}
    return {'created_by':m.created_by,'format_version':str(m.format_version),'row_groups':m.num_row_groups,'rows_per_group':rows,'footer_serialized_size':m.serialized_size,'kv_metadata_value_hashes':mdhash,'columns':props}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--original',type=Path);p.add_argument('--replay',type=Path);p.add_argument('--root',type=Path,action='append');p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    need(not a.out.exists(),'Output file already exists; choose new output');need(a.out.parent.is_dir(),'Output directory does not exist')
    if a.original and a.replay: orig,rep=a.original,a.replay
    else:
        need(not a.original and not a.replay,'Supply both --original and --replay or neither');found=locate(a.root or default_roots());need(ORIG in found and REPLAY in found,'Could not find both exact SHA files. Supply --root or exact --original and --replay paths. No data modified.');orig,rep=found[ORIG],found[REPLAY]
    need(sha(orig)==ORIG and sha(rep)==REPLAY,'Wrong snapshot; required exact original and 25-Nov replay SHA')
    import numpy as np
    import pyarrow as pa, pyarrow.compute as pc, pyarrow.parquet as pq
    pf1,pf2=pq.ParquetFile(orig),pq.ParquetFile(rep)
    need(pf1.metadata.num_rows==pf2.metadata.num_rows==EXPECTED_ROWS,'Unexpected row count')
    need(pf1.schema_arrow.equals(pf2.schema_arrow,check_metadata=False),'Arrow schema differs; stop exact comparison')
    def boolarr(x):return x.to_numpy(zero_copy_only=False)
    k1,k2=pf1.read(columns=KEYS),pf2.read(columns=KEYS)
    for k in KEYS:need(k1[k].null_count==k2[k].null_count==0,'Null key')
    order_equal=all(k1[k].combine_chunks().equals(k2[k].combine_chunks()) for k in KEYS)
    ix1=pc.sort_indices(k1,sort_keys=[(k,'ascending') for k in KEYS]);ix2=pc.sort_indices(k2,sort_keys=[(k,'ascending') for k in KEYS]);s1,s2=k1.take(ix1),k2.take(ix2)
    for k in KEYS:need(s1[k].combine_chunks().equals(s2[k].combine_chunks()),'Key set differs')
    adj=np.ones(EXPECTED_ROWS-1,dtype=bool)
    for k in KEYS:
        col=s1[k].combine_chunks();adj &= boolarr(pc.equal(col.slice(0,len(col)-1),col.slice(1)))
    need(not np.any(adj),'Duplicate sorted key')
    del k1,k2,s1,s2,adj
    columns=[]
    for field in pf1.schema_arrow:
        if field.name in KEYS:continue
        print('Comparing',field.name,flush=True)
        x=pf1.read(columns=[field.name])[field.name].take(ix1).combine_chunks();y=pf2.read(columns=[field.name])[field.name].take(ix2).combine_chunks()
        nx=boolarr(pc.is_null(x));ny=boolarr(pc.is_null(y));valid=~(nx|ny);nm=int(np.count_nonzero(nx!=ny))
        row={'column':field.name,'type':str(field.type),'null_mismatches':nm}
        if pa.types.is_floating(field.type):
            xx=x.to_numpy(zero_copy_only=False);yy=y.to_numpy(zero_copy_only=False);both_nan=np.isnan(xx)&np.isnan(yy); exact=(xx==yy)|both_nan
            row['numeric_exact_mismatches']=int(np.count_nonzero(valid&~exact));row['nan_mask_mismatches']=int(np.count_nonzero(valid&(np.isnan(xx)!=np.isnan(yy))))
            uint={2:np.uint16,4:np.uint32,8:np.uint64}[xx.dtype.itemsize];need(xx.dtype==yy.dtype,'Float dtype mismatch')
            row['float_bit_mismatches']=int(np.count_nonzero(valid&(xx.view(uint)!=yy.view(uint))))
            finite=valid&np.isfinite(xx)&np.isfinite(yy);delta=np.abs(xx[finite].astype(np.float64)-yy[finite].astype(np.float64));row['max_abs_finite_difference']=float(delta.max()) if delta.size else 0.0
        else:
            eq=boolarr(pc.fill_null(pc.equal(x,y),False));row['numeric_exact_mismatches']=int(np.count_nonzero(valid&~eq));row['float_bit_mismatches']=0;row['nan_mask_mismatches']=0
        columns.append(row)
        del x,y
    md1,md2=summarize_metadata(pf1),summarize_metadata(pf2)
    num=sum(x['numeric_exact_mismatches']+x['null_mismatches'] for x in columns);bits=sum(x['float_bit_mismatches'] for x in columns)
    conclusion=('EXACT_VALUE_DIFFERENCES_PRESENT' if num else 'FLOAT_REPRESENTATION_DIFFERENCES_PRESENT' if bits else 'EXACT_DECODED_VALUES_MATCH_ROW_ORDER_DIFFERS' if not order_equal else 'EXACT_DECODED_VALUES_AND_ORDER_MATCH_SERIALIZATION_DIFFERENCE_REMAINS')
    need(sha(orig)==ORIG and sha(rep)==REPLAY,'Input bytes changed during diagnostic')
    report={'scope':'read-only development files, aggregate diagnostics only; no model or test inference; not E2E','original_sha256':ORIG,'replay_sha256':REPLAY,'rows':EXPECTED_ROWS,'keys':KEYS,'key_set_equal':True,'key_order_equal':order_equal,'unique_keys':True,'schema_equal_excluding_metadata':True,'arrow_schema_metadata_equal':pf1.schema_arrow.equals(pf2.schema_arrow,check_metadata=True),'value_or_null_mismatches':num,'float_bit_mismatches':bits,'columns':columns,'original_parquet_metadata':md1,'replay_parquet_metadata':md2,'metadata_fields_differing':[k for k in md1 if md1[k]!=md2[k]],'conclusion':conclusion,'inputs_preserved':True,'python':platform.python_version(),'pyarrow':pa.__version__,'numpy':np.__version__,'warning':'Matching decoded values do not prove the exact cause of byte differences. Never substitute the replay for the frozen original or bypass SHA guards.'}
    a.out.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8');print('DIAGNOSTIC_COMPLETE:',conclusion,'\nJSON:',a.out)
if __name__=='__main__':
    try:main()
    except Exception as e:print('STOP:',e,file=sys.stderr);sys.exit(1)
