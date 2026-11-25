#!/usr/bin/env python3
"""Verify archived aggregate acquisition evidence, not live HTTP or raw file bytes."""
import calendar, hashlib, json, csv
from pathlib import Path
R=Path(__file__).resolve().parents[1]
D=R/'evidence/final_review/part1/recovered_manifest'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def require(b,m):
    if not b: raise ValueError(m)
def check():
    p=D/'manifest_financials.json'; m=load(p)
    require(sha(p)=='d0e3b531bd3ca0802b943cb94a073444be52d619dc625efe8448bb8c140d76d5','original manifest digest')
    expected={f'{y:04}{mo:02}{calendar.monthrange(y,mo)[1]:02}' for y in range(1984,2027) for mo in (3,6,9,12) if (y,mo)<=(2026,6)}
    require(set(m)==expected,'quarter scope')
    require(all(x['complete'] is True and isinstance(x['rows'],int) and x['rows']>0 and x['rows']==x['api_total'] for x in m.values()),'quarter totals/completion')
    require(sum(x['rows'] for x in m.values())==1682616,'total Financials')
    pins=[x for x in load(R/'config/prepared_snapshot_manifest.json') if '/financials/' in x['relative_path']]
    pin={Path(x['relative_path']).stem.split('=')[-1]:x for x in pins}
    require(len(pins)==len(pin)==170 and set(pin)==expected,'prepared pin scope')
    root=R/'release_evidence/continuous_windows_20261119/prepare/comparison'
    out=[]
    for q,x in sorted(m.items()):
        d=load(root/f'prepared_REPDTE_{q}.json')
        require(d['new_rows']==d['reference_rows']==x['rows'],'quarter row count '+q)
        require(d['byte_identical'] is True and d['reference_sha256']==d['new_sha256']==pin[q]['sha256'],'quarter prepared digest '+q)
        out.append({'quarter':q,'recorded_api_total':x['api_total'],'manifest_rows':x['rows'],'replay_rows':d['new_rows'],'prepared_sha256':pin[q]['sha256'],'status':'PASS'})
    for q,n in [('institutions',27835),('failures_all',4117)]:
        d=load(root/f'prepared_{q}.json');require(d['new_rows']==d['reference_rows']==n and d['byte_identical'] is True,'small table '+q)
    with (D/'quarter_reconciliation.csv').open(encoding='utf-8-sig',newline='') as f: saved=list(csv.DictReader(f))
    require(len(saved)==len(out) and all({k:str(v) for k,v in a.items()}==b for a,b in zip(out,saved)),'saved reconciliation differs')
    return {'status':'PASS','quarters':170,'financial_rows':1682616,'complete_quarters':170,'quarter_count_matches':170,'prepared_digest_ledger_matches':170,'institutions_rows':27835,'failures_assistance_rows':4117,'manifest_sha256':sha(p),'scope':'Recovered original manifest counts and archived replay ledger; no HTTP body or raw data verification here.'}
if __name__=='__main__':print(json.dumps(check(),indent=2))
