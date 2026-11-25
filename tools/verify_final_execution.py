#!/usr/bin/env python3
"""Verify S5 published aggregate evidence. No data download, training or scoring."""
import ast,csv,hashlib,json,math,statistics as st
from pathlib import Path
R=Path(__file__).resolve().parents[1];N=R/'evidence/final_execution';S=N/'storage';P=N/'policy';X=N/'replay';E=N/'install'
def csvrows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def j(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(x,m):
 if not x:raise ValueError(m)
def close(a,b):return math.isclose(float(a),float(b),rel_tol=1e-12,abs_tol=1e-12)
a=j(S/'storage_summary.json');require(a['script_sha256']==sha(R/'tools/storage_sensitivity.py'),'Storage producer digest')
require(a['rows']==1682616 and a['quarters']==170 and a['all_equivalence_checks_passed'] and a['empty_text_encoding']['synthetic_roundtrip_passed'],'Storage status')
m=csvrows(S/'measurements.csv');b=csvrows(S/'benchmark_summary.csv');ref=j(S/'reference_fingerprints.json');require(len(m)==144 and len({r['run_order'] for r in m})==144 and len(b)==16 and len({(r['variant'],r['query']) for r in b})==16,'Storage counts')
for r in m:
 q=j(S/'runs'/f"{int(r['run_order']):03d}.json");require(q['fingerprint']==ref[r['query']] and q['variant']==r['variant'] and q['query']==r['query'] and r['equivalence_pass']=='True','Fingerprint')
 for k in ['seconds','peak_rss_mib','peak_rss_increase_mib','baseline_rss_mib']:require(close(q[k],r[k]),'Run measurement')
for r in b:
 g=[x for x in m if (x['variant'],x['query'])==(r['variant'],r['query'])];t=[x for x in g if x['warmup']=='False'];require(len(g)==9 and len(t)==7,'Repeat count')
 for k,l,f in [('median_seconds','seconds',st.median),('min_seconds','seconds',min),('max_seconds','seconds',max),('stdev_seconds','seconds',st.stdev),('median_peak_rss_mib','peak_rss_mib',st.median),('max_peak_rss_mib','peak_rss_mib',max),('median_peak_rss_increase_mib','peak_rss_increase_mib',st.median)]:require(close(r[k],f([float(x[l]) for x in t])),'Summary mismatch '+k)
 base=next(x for x in b if x['variant']=='csv_uncompressed' and x['query']==r['query']);require(close(r['speedup_vs_csv'],float(base['median_seconds'])/float(r['median_seconds'])),'Speedup')
sz=csvrows(S/'storage_sizes.csv');require(len(sz)==4 and all(close(r['mib'],int(r['bytes'])/2**20) for r in sz),'Sizes')
sc=csvrows(S/'source_checksums.csv');old=csvrows(R/'evidence/final_review/part1/recovered_manifest/quarter_reconciliation.csv');require(len(sc)==170 and {r['quarter']:r['sha256'] for r in sc}=={r['quarter']:r['prepared_sha256'] for r in old},'Prepared identities')
for q in ref:
 z=next(r for r in b if r['variant']=='parquet_zstd' and r['query']==q);require(all(float(z['max_seconds'])<float(r['min_seconds']) for r in b if r['query']==q and r['variant']!='parquet_zstd'),'Observed range separation')
policy=j(P/'REPRODUCTION_STATUS.json');tree=ast.parse((R/'tools/reproduce_development.py').read_text());expected=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='EXPECTED' for t in n.targets));require(policy['input_hashes']==expected and policy['mode']=='policy' and policy['stages']==[{'stage':'policy','exit_code':0}],'Frozen policy provenance')
for new,old,count in [('development_model_ranking_rechecked.csv','candidate_grid_21.csv',21),('development_threshold_scenarios.csv','threshold_cost_scenarios_4.csv',4)]:
 r=csvrows(P/new);require(len(r)==count and r==csvrows(R/'evidence/verified_archive_aggregates'/old),'Policy archive mismatch')
for r in csvrows(P/'development_threshold_scenarios.csv'):
 loss=int(r['fp_cert_years'])+int(r['ratio'])*int(r['missed_failure_certs']);require(close(loss,r['cost_units']) and close(loss*float(r['COST_median_thousand_USD'])/int(r['ratio']),r['scenario_cost_thousand_USD']),'Policy loss')
d=j(X/'RETURNED_EXECUTION_SUMMARY.json');require(d['source_manifest_sha256']==sha(R/'config/source_manifest.json') and d['fresh_parent_required'] and not d['frozen_checkpoint_fallback'] and d['new_model_fits']==0 and not d['final_test_inference'] and d['full_clean_room_E2E']=='NOT_EXECUTED','Replay scope')
require(len(d['stages'])==5 and all(x['status']=='PASS' and x['all_stage_inputs_preserved'] and all(y['status']=='PASS' for y in x['lineage_checks']) for x in d['stages']),'Stage lineage')
rows=csvrows(X/'DATASET_COMPARISON.csv');num=csvrows(X/'NUMERICAL_COMPARISON.csv');require(len(rows)==179 and len({r['dataset'] for r in rows})==179 and sum(r['byte_identical']=='True' for r in rows)==178 and all(r['new_rows']==r['reference_rows'] and r['schema_equal']=='True' and r['status'].startswith('PASS') for r in rows),'Dataset parity')
require(len(num)==5401 and sum(int(r['rows']) for r in num)==230664115 and all(r['status']=='PASS' and all(int(r[k])==0 for k in ['null_mismatches','nan_mismatches','value_mismatches']) for r in num),'Column parity')
require({r['dataset']:r['reference_sha256'] for r in rows}=={r['dataset']:r['reference_sha256'] for r in csvrows(R/'outputs/verification/CONTINUOUS_DATASET_VERIFICATION.csv')},'Reference identities')
dig=csvrows(X/'INPUT_DIGESTS.csv');require(len(dig)==506 and all(r['before']==r['after'] for r in dig),'Input preservation')
require(len(j(X/'EXPORTED_FILE_MANIFEST.json'))==256,'Private returned manifest count (not public tree)')
def pins(p):
 for line in p.read_text().splitlines():
  line=line.strip()
  if line.startswith('-r '):yield from pins(p.parent/line[3:].strip())
  elif '==' in line and not line.startswith('#'):yield line.lower().split('==',1)
for name,recipe,version,count in [('engineering','engineering-recorded.txt','3.13.9',24),('model','model-and-spark-observed.txt','3.13.7',16)]:
 z=j(E/name/'STATUS.json');require(z['status']=='PASS_CLEAN_INSTALL_IMPORTS_ONLY' and z['python']==version and {x['name'] for x in z['steps']}=={'install','freeze','pip_check','imports'} and all(x['exit_code']==0 for x in z['steps']),'Install status')
 f=E/name/'freeze.log';freeze=dict(line.lower().split('==',1) for line in f.read_text().splitlines() if '==' in line);require(len(freeze)==count and all(freeze[k]==v for k,v in pins(R/'requirements'/recipe)) and f.read_bytes()==(R/'requirements'/f'{name}-clean-freeze-20261125.txt').read_bytes() and (E/name/'pip_check.log').read_text().strip()=='No broken requirements found.','Install pins')
print('PASS S5: 144 fingerprints; 112 timed observations; 170 prepared digests; 21 rankings + 4 policies; 179 datasets, 5,401 columns / 230,664,115 cells; 506 input digests; two clean installs. Returned aggregates only; private 256-member manifest was verified during release construction, not rehashed here.')
