"""Data-free verification of returned S6 aggregate evidence, not a scientific replay."""
from pathlib import Path
import json, hashlib, statistics as st, math
P=Path(__file__).resolve().parent

def req(ok,msg):
    if not ok: raise RuntimeError(msg)
def rd(name): return json.loads((P/name).read_text(encoding='utf-8'))
def eq(a,b):return math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-12)
def main():
    for ln in (P/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        h,n=ln.split(maxsplit=1); n=n.lstrip('*');req(Path(n).name==n,'Unsafe checksum path');req(hashlib.sha256((P/n).read_bytes()).hexdigest()==h,'Digest mismatch: '+n)
    a,s,b=[rd(n) for n in ('feature_audit_result.json','feature_scaling_result.json','feature_benchmark_result.json')]
    req(a['status']==s['status']==b['status']=='PASS','Returned status')
    req(a['source_commit']==s['source_commit']=='050889604e449efa26c7bb44943c58cef8477e54','Source commit mismatch')
    req(a['panel_sha256']==s['panel_sha256']=={'panel_clean.parquet':'0d1837815820e93eb71508dabd6f48143e2b596b09453606ccf0070c3717e107','panel_pit_base.parquet':'3fce669406ff1898ac85d9c41c6385b7f8c6b27e29ecd041bb0a3c59f6337421'},'Panel hash mismatch')
    req(a['comparison']=={'atol':1e-9,'rtol':1e-8,'exact_null_mask':True},'Unexpected tolerance contract')
    repo=P.parents[1]
    if (repo/'config/source_manifest.json').is_file():
        req(len(a['source_sha256'])==3,'Source count')
        for rel,expected in a['source_sha256'].items():
            f=repo/rel;req(f.is_file() and hashlib.sha256(f.read_bytes()).hexdigest()==expected,'Distributed scientific source mismatch: '+rel)
    req(a['validated_output_sha256']==s['reference_output_sha256']==b['validated_output_sha256'],'Output digest mismatch')
    req(a['rows']==1232375 and a['features']==15 and a['cells_compared']==a['rows']*15 and a['source_cells_compared']==a['rows']*11,'Audit dimensions')
    req(len(a['per_feature'])==15 and all(v['null_mask_mismatches']==v['value_mismatches']==0 for v in a['per_feature'].values()),'Feature mismatches')
    req(a['source_parity']['status']=='PASS' and len(a['source_parity']['field_mismatch_counts'])==11 and not any(a['source_parity']['field_mismatch_counts'].values()),'Source parity')
    req(len(s['warmups'])==3 and len(s['measured'])==9 and len(b['warmups'])==2 and len(b['measured'])==12,'Trial count')
    for k in (1,2,3):
        rr=[r for r in s['measured'] if r['scale']==k];ss=s['summary'][str(k)];req(len(rr)==3 and {r['block'] for r in rr}=={1,2,3},'Scale blocks')
        req(all(r['output_rows']==k*a['rows'] and r['verified_replicas']==k and r['rss_samples']>0 and r['elapsed_s']>0 for r in rr),'Scale checks')
        t=[r['elapsed_s'] for r in rr]; m=[r['sampled_peak_RSS_MiB'] for r in rr];req(eq(st.median(t),ss['seconds_median']) and all(eq(v,w) for v,w in zip([min(t),max(t)],ss['seconds_range'])) and eq(st.median(m),ss['peak_RSS_MiB_median']) and eq(max(m),ss['peak_RSS_MiB_max']),'Scale summaries')
    for k in (1,2):
        rr=[r for r in b['measured'] if r['jobs']==k]; ss=b['summary'][str(k)];req(len(rr)==6 and {r['block'] for r in rr}==set(range(1,7)),'Concurrency blocks')
        req(all(r['verified_outputs']==k and len(r['job_seconds'])==k and r['rss_samples']>0 and r['batch_seconds']>0 for r in rr),'Concurrent outputs')
        t=[r['batch_seconds'] for r in rr];m=[r['peak_sum_RSS_MiB'] for r in rr];req(eq(st.median(t),ss['batch_seconds_median']) and all(eq(v,w) for v,w in zip([min(t),max(t)],ss['batch_seconds_range'])) and eq(st.median(m),ss['sampled_sum_RSS_MiB_median']) and eq(max(m),ss['sampled_sum_RSS_MiB_max']),'Concurrency summaries')
    print('PASS_S6_ARCHIVED_AGGREGATES_ONLY: 15 features; 11 source fields; 9 scaling trials; 12 concurrency trials')
if __name__=='__main__':main()
