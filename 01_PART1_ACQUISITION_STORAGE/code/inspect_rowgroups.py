#!/usr/bin/env python3
"""Inspect Parquet reporting-date row-group statistics WITHOUT reading data pages.

Usage:
    python tools/inspect_rowgroups.py panel_clean.parquet --out evidence/rowgroups.csv
    python tools/inspect_rowgroups.py panel_clean.parquet panel_clean_by_date.parquet --out evidence/layout_rowgroups.csv

Dependencies: pyarrow, OR thrift>=0.20 for metadata-only fallback.
No parquet data are changed. Row-group overlap is necessary, not sufficient,
for physical pruning; runtime engine behavior should be checked separately.
"""
from __future__ import annotations
import argparse
import csv
from datetime import date, timedelta
from pathlib import Path

CRISIS_LO, CRISIS_HI = date(2008, 3, 31), date(2014, 12, 31)


def _date(x):
    if x is None:
        return None
    if isinstance(x,date):
        return x
    if isinstance(x,(bytes,bytearray)) and len(x)==4:
        return date(1970,1,1)+timedelta(days=int.from_bytes(x,'little',signed=True))
    if isinstance(x,int):
        return date(1970,1,1)+timedelta(days=x)
    return date.fromisoformat(str(x)[:10])


def _from_pyarrow(path:Path):
    import pyarrow.parquet as pq
    pf=pq.ParquetFile(path)
    cols=pf.schema_arrow.names
    date_col = 'REPDTE' if 'REPDTE' in cols else 'DECISION_DATE'
    if date_col not in cols:
        raise ValueError(f'No reporting or decision date in Parquet schema: {path}')
    idx=cols.index(date_col)
    return [(i,pf.metadata.row_group(i).num_rows,
             _date(pf.metadata.row_group(i).column(idx).statistics.min),
             _date(pf.metadata.row_group(i).column(idx).statistics.max))
            for i in range(pf.metadata.num_row_groups)]


def _from_thrift(path:Path):
    from thrift.protocol import TCompactProtocol
    from thrift.transport import TTransport
    from thrift.Thrift import TType
    def read(p,t):
        if t==TType.BOOL:return p.readBool()
        if t==TType.BYTE:return p.readByte()
        if t==TType.I16:return p.readI16()
        if t==TType.I32:return p.readI32()
        if t==TType.I64:return p.readI64()
        if t==TType.DOUBLE:return p.readDouble()
        if t==TType.STRING:return p.readBinary()
        if t==TType.STRUCT:
            p.readStructBegin();out={}
            while True:
                _,ft,fid=p.readFieldBegin()
                if ft==TType.STOP:break
                out[fid]=read(p,ft);p.readFieldEnd()
            p.readStructEnd();return out
        if t in (TType.LIST,TType.SET):
            et,n=p.readListBegin() if t==TType.LIST else p.readSetBegin()
            out=[read(p,et) for _ in range(n)]
            p.readListEnd() if t==TType.LIST else p.readSetEnd();return out
        if t==TType.MAP:
            kt,vt,n=p.readMapBegin();out=[(read(p,kt),read(p,vt)) for _ in range(n)]
            p.readMapEnd();return out
        raise ValueError(f'Unsupported metadata Thrift type: {t}')
    with path.open('rb') as f:
        f.seek(-8,2);footer=f.read(8)
        if len(footer)!=8 or footer[4:]!=b'PAR1':
            raise ValueError(f'Not a Parquet file: {path}')
        n=int.from_bytes(footer[:4],'little');f.seek(-8-n,2);content=f.read(n)
    parsed=read(TCompactProtocol.TCompactProtocol(TTransport.TMemoryBuffer(content)),TType.STRUCT)
    schema=parsed[2]
    names=[x.get(4,b'').decode('utf-8',errors='replace') for x in schema]
    date_col = 'REPDTE' if 'REPDTE' in names else 'DECISION_DATE'
    if date_col not in names:raise ValueError(f'No reporting or decision date in metadata: {path}')
    # This project's FDIC dataset is flat; root is the only non-leaf element.
    col_idx=names.index(date_col)-1
    answer=[]
    for i,g in enumerate(parsed[4]):
        cm=g[1][col_idx][3]
        stat=cm[12]
        lo=stat.get(6,stat.get(2));hi=stat.get(5,stat.get(1))
        answer.append((i,g[3],_date(lo),_date(hi)))
    return answer


def inspect(path:Path):
    try:
        return _from_pyarrow(path)
    except ImportError:
        return _from_thrift(path)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('parquets',type=Path,nargs='+')
    p.add_argument('--out',type=Path,default=Path('rowgroups.csv'))
    p.add_argument('--start',default=CRISIS_LO.isoformat())
    p.add_argument('--end',default=CRISIS_HI.isoformat())
    a=p.parse_args();start=date.fromisoformat(a.start);end=date.fromisoformat(a.end)
    if end<start:raise ValueError('End before start')
    rows=[]
    for path in a.parquets:
        pth=path.resolve()
        if not pth.is_file():raise FileNotFoundError(pth)
        groups=inspect(pth)
        possible=0;pruned=0
        for i,n,lo,hi in groups:
            overlaps=None if lo is None or hi is None else not (hi<start or lo>end)
            if overlaps is True:possible+=1
            if overlaps is False:pruned+=1
            rows.append({'file':pth.name,'group':i,'rows':n,
                         'min_date':str(lo) if lo else '',
                         'max_date':str(hi) if hi else '',
                         'overlaps_filter':overlaps,'window_start':str(start),'window_end':str(end)})
        print(f'{pth.name}: groups={len(groups)}, rows={sum(r[1] for r in groups):,}, '
              f'overlap={possible}, metadata-prunable={pruned} (others lack statistics).')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print('AUDIT CSV:',a.out)

if __name__=='__main__':main()
