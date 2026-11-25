"""Schema/key/null/value comparisons of new Parquet outputs, no model metrics."""
from pathlib import Path
import json,math
from workflow.common import Blocked,require,sha,save_json

def scalar_equal(left,right,*,rtol=0.,atol=0.):
    """Reference contract used by synthetic tests, including distinct null/NaN masks."""
    if left is None or right is None:return left is None and right is None
    if isinstance(left,float) and math.isnan(left):return isinstance(right,float) and math.isnan(right)
    if isinstance(right,float) and math.isnan(right):return False
    if isinstance(left,float) or isinstance(right,float):
        return left==right or (math.isfinite(left) and math.isfinite(right) and abs(left-right)<=atol+rtol*abs(right))
    return type(left)==type(right) and left==right

def compare_parquet(new,reference,keys,dataset,out,rtol=0.,atol=0.):
    try:
        import polars as pl
        import pyarrow.parquet as pq
    except ImportError as error:raise Blocked('Parquet comparison dependency missing: '+str(error))
    ns=pq.ParquetFile(new).schema_arrow;rs=pq.ParquetFile(reference).schema_arrow
    schema_ok=ns.equals(rs,check_metadata=False)
    nl=pl.scan_parquet(new);rl=pl.scan_parquet(reference)
    nrows=nl.select(pl.len()).collect().item();rrows=rl.select(pl.len()).collect().item()
    new_digest=sha(new);reference_digest=sha(reference)
    report=dict(dataset=dataset,new_sha256=new_digest,reference_sha256=reference_digest,byte_identical=new_digest==reference_digest,
                schema_equal=schema_ok,new_schema=str(ns),reference_schema=str(rs),new_rows=nrows,reference_rows=rrows,
                keys=keys,rtol=rtol,atol=atol,columns=[],status='FAIL')
    if not schema_ok or nrows!=rrows:
        report['reason']='Schema/row-count mismatch';save_json(out,report);return report
    duplicate_new=nl.group_by(keys).len().filter(pl.col('len')!=1).select(pl.len()).collect().item()
    duplicate_ref=rl.group_by(keys).len().filter(pl.col('len')!=1).select(pl.len()).collect().item()
    nullnew=nl.select(pl.any_horizontal([pl.col(k).is_null() for k in keys]).sum()).collect().item()
    nullref=rl.select(pl.any_horizontal([pl.col(k).is_null() for k in keys]).sum()).collect().item()
    missingnew=rl.select(keys).join(nl.select(keys),on=keys,how='anti').select(pl.len()).collect().item()
    missingref=nl.select(keys).join(rl.select(keys),on=keys,how='anti').select(pl.len()).collect().item()
    report['key_checks']=dict(duplicate_new=duplicate_new,duplicate_reference=duplicate_ref,null_new=nullnew,null_reference=nullref,
                              missing_in_new=missingnew,unexpected_in_new=missingref)
    if any(report['key_checks'].values()):
        report['reason']='Key uniqueness/null/set mismatch';save_json(out,report);return report
    columns=[c for c in ns.names if c not in keys];schema=nl.collect_schema()
    # Six-column groups bound join memory and preserve exact comparisons for integer/date/string fields.
    for start in range(0,len(columns),6):
        batch=columns[start:start+6]
        joined=nl.select(keys+batch).join(rl.select(keys+batch),on=keys,how='left',suffix='__reference',validate='1:1')
        expressions=[]
        for j,col in enumerate(batch):
            left=pl.col(col);right=pl.col(col+'__reference')
            nullbad=left.is_null()!=right.is_null()
            if schema[col].is_float():
                ln=left.is_nan().fill_null(False);rn=right.is_nan().fill_null(False)
                nanbad=ln!=rn
                finite=left.is_finite() & right.is_finite()
                same=(left==right)|(finite & ((left-right).abs()<=atol+rtol*right.abs()))
                bad=(~same.fill_null(False)) & left.is_not_null() & right.is_not_null() & ~ln & ~rn
                maxdelta=(left-right).abs().fill_nan(None).max().fill_null(0.)
            else:
                nanbad=pl.lit(False)
                bad=(left!=right).fill_null(False)
                maxdelta=(left.cast(pl.Float64)-right.cast(pl.Float64)).abs().max().fill_null(0.) if schema[col].is_numeric() else pl.lit(0.)
            expressions += [nullbad.sum().alias(f'n{j}'),nanbad.sum().alias(f'a{j}'),bad.sum().alias(f'b{j}'),maxdelta.alias(f'd{j}')]
        values=joined.select(expressions).collect().row(0,named=True)
        for j,col in enumerate(batch):
            delta=float(values[f'd{j}'])
            item=dict(dataset=dataset,column=col,rows=nrows,null_mismatches=int(values[f'n{j}']),nan_mismatches=int(values[f'a{j}']),
                      value_mismatches=int(values[f'b{j}']),max_abs_difference=delta if math.isfinite(delta) else None,
                      nonfinite_difference=not math.isfinite(delta),rtol=rtol if schema[col].is_float() else 0.,atol=atol if schema[col].is_float() else 0.)
            item['status']='FAIL' if item['null_mismatches']+item['nan_mismatches']+item['value_mismatches'] else 'PASS'
            report['columns'].append(item)
    report['status']='PASS_NUMERICAL_SCHEMA_EQUIVALENCE' if all(c['status']=='PASS' for c in report['columns']) else 'FAIL'
    report['scope']='All keys/null masks/non-key columns checked; Parquet byte identity recorded separately, not forced by tolerant numerical comparison.'
    save_json(out,report);return report
