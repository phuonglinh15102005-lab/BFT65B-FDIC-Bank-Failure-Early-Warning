import zipfile,csv,io,json,hashlib,collections,calendar
from datetime import date
from pathlib import Path
root=Path('/mnt/data/p2check'); p=Path('/mnt/data/p4review'); r=next((p/'repo').iterdir()); o=p/'original'
def readzip(z,n):
 with zipfile.ZipFile(z) as f:return f.read(n)
def table(z,n):return list(csv.DictReader(io.StringIO(readzip(z,n).decode('utf-8-sig'))))
def sha(x):return hashlib.sha256(x).hexdigest()
a=readzip(o/'SHARE_THIS_PART4_V2_DEV_EVIDENCE.zip','part4_v2_development_audit.json'); b=readzip(o/'SHARE_THIS_PART4_V2_FOLD_AUDIT.zip','v2_train_only_audit.json'); aa=json.loads(a);bb=json.loads(b); can=json.loads((r/'evidence/verified_archive_aggregates/part4_step05_canary_audit.json').read_text()); assert sha(a)==can['sha256']['v2_audit_json']==bb['input_sha256']['part4_v2_development_audit_json'];assert sha(b)==can['sha256']['v2_fold_audit_json']; assert sha(readzip(o/'BFT65B_Part4_V2_Fold_Audit_Windows.zip','check_v2_folds_train_only.py'))==bb['input_sha256']['this_script'];assert sha(readzip(o/'BFT65B_Part4_Step05_Canary_Tier2_Windows.zip','part4_step05_canary_coverage.py'))==can['sha256']['this_script']; assert sha(readzip(o/'BFT65B_Part4_Step03_Independent_Leakage_Gate.zip','part4_step03_independent_full_gate.py'))==aa['independent_formula_oracle']['pandas_oracle_code_sha256']; assert sha((r/'04_PART4_FEATURE_PIPELINE/code/part4_v2_train_only_pipeline.py').read_bytes())==bb['input_sha256']['preprocessor_factory'];
params=table(o/'SHARE_THIS_PART4_V2_FOLD_AUDIT.zip','v2_preprocessing_params.csv'); assert len(params)==72; nonempty=sum(bool(v) for row in params for k,v in row.items() if k not in ('fold','clip','feature')); assert nonempty==432
qrows=table(o/'SHARE_THIS_PART4_V2_DEV_EVIDENCE.zip','dev_primary_by_quarter.csv'); days=sorted({x['DECISION_DATE'] for x in qrows})[:4]; start=sum(int(x['rows']) for x in qrows if x['DECISION_DATE'] in days and x['PRIMARY_LABEL_STATUS'] in ('POSITIVE','NEGATIVE','CONFIRMED_NONFAILURE_EXIT_NEGATIVE')); assert start==71150
failure=table(root/'review_bundle.zip','review_AUDIT_ONLY/failure_event_coverage.csv'); reg=table(root/'part2_clean_review_bundle.zip','review_AUDIT_ONLY/bank_event_registry_AUDIT_ONLY.csv'); first={}; invalid=[]
for x in failure:
 if x['RESTYPE']!='FAILURE':continue
 try:d=date.fromisoformat(x['FAILDATE']);c=str(int(x['CERT']))
 except (ValueError,TypeError):invalid.append(x['SOURCE_ROW']);continue
 first[c]=min(d,first.get(c,d))
mis=[]; reg_pos=0; coverage=0
for x in reg:
 c=x['CERT'];d=date.fromisoformat(x['FIRST_FAILURE_DATE']) if x['FIRST_FAILURE_DATE'] else None
 if d:reg_pos+=1
 if first.get(c)!=d:mis.append((c,str(first.get(c)),str(d)))
 if c in first:coverage+=1
print('failure rows',len(failure),'first cert',len(first),'bad',len(invalid),'reg',len(reg),'reg date',reg_pos,'matched',coverage,'mis',len(mis),mis[:4])
# Bounded coverage check: only internal absent original report quarters, inside observed raw span.
# No entry date assumptions; count candidate next-quarter keys that satisfy recorded stop/eligibility, dev dates only.
def q(s):
 s=s.replace('-','');return int(s[:4])*4+(int(s[4:6])-1)//3
def end(i):
 y,k=divmod(i,4);m=(k+1)*3;return date(y,m,calendar.monthrange(y,m)[1])
cov=table(root/'review_bundle.zip','review_AUDIT_ONLY/bank_coverage_AUDIT_ONLY.csv'); meta=collections.defaultdict(set)
for x in table(root/'part2_review_bundle.zip','review_AUDIT_ONLY/financial_metadata_AUDIT_ONLY.csv'):meta[x['CERT']].add(q(x['REPDTE']))
regmap={x['CERT']:x for x in reg}; gap=collections.Counter(); gap_banks=set()
for x in cov:
 if not int(x['INTERNAL_MISSING_QUARTERS']):continue
 c=x['CERT'];lo,hi=q(x['FIRST_REPDTE']),q(x['LAST_REPDTE']); obs=meta[c];assert len(obs)==int(x['OBSERVED_QUARTERS']) and min(obs)==lo and max(obs)==hi
 e=regmap[c];stop=date.fromisoformat(e['RISK_STOP_DATE']) if e['RISK_STOP_DATE'] else None;bound=date.fromisoformat(e['ELIGIBILITY_END']); fail=first.get(c)
 for s in set(range(lo,hi+1))-obs:
  t=s+1;d=end(t)
  if d>date(2008,12,31) or (stop and d>=stop) or d>bound:continue
  gap['eligible_internal_missing_source_keys']+=1;gap_banks.add(c)
  if fail and d<fail<=end(t+4):gap['failure_within_4q']+=1
  elif fail:gap['failure_outside_4q']+=1
  else:gap['no_register_FAILURE']+=1
print('gaps',gap,'banks',len(gap_banks))
result={'scope':'Recomputed from archived aggregate ledgers and original Part2 event/coverage review files; no Parquet reads or model scoring. Missing-source diagnostic is bounded to absent internal raw-report quarters within observed raw spans, eligible under retrospective registry, with decision <=2008Q4; not all historical live roster gaps or final labels. First failure reconciliation uses exported event-coverage ledger exported from source, not a reread of failures.parquet.', 'hash_links_checked':6,'dev_candidate_rows':aa['counts']['all_development_rows'],'dev_formula_cells':aa['independent_formula_oracle']['compared_feature_cells'],'PIT_source_cells':aa['full_pit_source_parity']['source_value_rows_checked']*aa['full_pit_source_parity']['source_fields_checked'],'ledger_cells':504,'populated_cells':nonempty,'first_four_decision_quarters':days,'structural_4q_missing_minimum':start,'first_fold_4q_missing':76781,'structural_share_of_first_fold_missing':start/76781,'failure_event_coverage_rows':len(failure),'valid_failure_certs_in_event_ledger':len(first),'invalid_FAILURE_rows':len(invalid),'registry_rows':len(reg),'registry_first_failure_dates':reg_pos,'registry_FIRST_FAILURE_date_mismatches':len(mis),'failure_CERTs_outside_registry':len(set(first)-set(regmap)),'internal_gap_diagnostic':dict(gap),'internal_gap_CERTs':len(gap_banks)}
(p/'recheck_results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
