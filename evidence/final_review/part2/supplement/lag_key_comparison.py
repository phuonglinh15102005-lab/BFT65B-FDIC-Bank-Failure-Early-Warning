"""Compare reporting-lag key sets from historical audit ledgers (not financial values or scored labels)."""
import csv, json, hashlib
from pathlib import Path
from collections import Counter, defaultdict
import sys
root=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).parent
out=root/'lag_key_comparison.json'
def rows(p):
    with (root/p).open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def q(d):
    if not d or d.startswith('9999'): return None
    d=d.replace('-',''); return int(d[:4])*4+(int(d[4:6])-1)//3
from datetime import date
import calendar
def day(d): return date.fromisoformat(d) if d and not d.startswith('9999') else None
def end(i):
    y,k=divmod(i,4); m=(k+1)*3; return date(y,m,calendar.monthrange(y,m)[1])
cov=rows('review_bundle/review_AUDIT_ONLY/bank_coverage_AUDIT_ONLY.csv')
reg={r['CERT']:r for r in rows('part2_clean_review_bundle/review_AUDIT_ONLY/bank_event_registry_AUDIT_ONLY.csv')}
meta=defaultdict(set)
for r in rows('part2_review_bundle/review_AUDIT_ONLY/financial_metadata_AUDIT_ONLY.csv'): meta[r['CERT']].add(q(r['REPDTE']))
exc=defaultdict(set)
for r in rows('part2_clean_review_bundle/review_AUDIT_ONLY/excluded_rows_AUDIT_ONLY.csv'): exc[r['CERT']].add(q(r['REPDTE']))
counts=Counter(); eras=defaultdict(Counter); source_flow=defaultdict(Counter); exit_classes=defaultdict(Counter); posbanks={1:set(),2:set()}; bp=defaultdict(lambda:{1:set(),2:set()}); certs={1:set(),2:set()}; positive_key_overlap=Counter(); loss_reason=Counter(); gain_reason=Counter()
cut=q('20250630'); dev=q('20081231'); test=q('20100101'); cache={i:end(i) for i in range(q('19840331'),q('20260630')+9)}
for r in cov:
    c=r['CERT']; a,b=q(r['FIRST_REPDTE']),q(r['LAST_REPDTE']); observed=meta[c] if int(r['INTERNAL_MISSING_QUARTERS']) else set(range(a,b+1)); assert len(observed)==int(r['OBSERVED_QUARTERS']) and min(observed)==a and max(observed)==b
    clean=observed-exc[c]; counts['source']+=len(observed);counts['clean']+=len(clean)
    e=reg[c]; stop=day(e['RISK_STOP_DATE']); bound=day(e['ELIGIBILITY_END']); fail=day(e['FIRST_FAILURE_DATE']); decisions={}; p={}
    for lag in (1,2):
        good=set()
        for s in clean:
            t=s+lag; d=cache[t]
            if t>cut: reason='beyond cutoff'
            elif stop and d>=stop: reason='at/after risk stop'
            elif d>bound: reason='beyond eligibility end'
            else: reason='retained'; good.add(t)
            source_flow[lag][reason]+=1
        decisions[lag]=good; counts[f'lag{lag}']+=len(good)
        if good: certs[lag].add(c)
        p[lag]={t for t in good if fail and cache[t]<fail<=cache[t+4]}
        counts[f'positive_lag{lag}']+=len(p[lag]);
        if p[lag]: posbanks[lag].add(c)
        for t in good:
            era='development' if t<=dev else ('embargo' if t<test else 'test-era candidate')
            eras[era][f'lag{lag}']+=1
            exit_classes[(era,e['EXIT_CLASS'])][f'lag{lag}_candidate_decisions']+=1
            if t in p[lag]: eras[era][f'positive_lag{lag}']+=1; bp[era][lag].add(c)
    shared=decisions[1]&decisions[2]; lost=decisions[1]-decisions[2]; gained=decisions[2]-decisions[1]
    counts['shared']+=len(shared);counts['lag1_only']+=len(lost);counts['lag2_only']+=len(gained)
    for t in lost:
        s=t-2; loss_reason['pre-first-source-report' if s<a else 'excluded source report' if s in observed else 'internal missing report']+=1
    for t in gained:
        s=t-1; gain_reason['after-last-source-report' if s>b else 'excluded source report' if s in observed else 'internal missing report']+=1
    positive_key_overlap['shared']+=len(p[1]&p[2]);positive_key_overlap['lag1_only']+=len(p[1]-p[2]);positive_key_overlap['lag2_only']+=len(p[2]-p[1]);
    for t in lost|gained:
        era='development' if t<=dev else ('embargo' if t<test else 'test-era candidate'); eras[era]['lag1_only' if t in lost else 'lag2_only']+=1
assert counts['source']==1682616 and counts['clean']==1669802 and counts['lag1']==1629398 and counts['lag2']==1605882 and len(certs[1])==23651 and len(certs[2])==23394 and len(posbanks[1])==2811
assert counts['lag1']-counts['lag2']==counts['lag1_only']-counts['lag2_only']
res={'scope':'Reconstructed keys from archived coverage, targeted gap metadata, exclusion ledger and reconciled event registry. No financial values, model fitting, test scores or final labels read. Positive-window counts are registry-based pre-adjudication opportunities, not the model cohort labels.', 'counts':dict(counts),'distinct_CERTs':{str(k):len(v) for k,v in certs.items()},'positive_window_CERTs':{str(k):len(v) for k,v in posbanks.items()},'positive_window_CERTs_overlap':{'shared':len(posbanks[1]&posbanks[2]),'lag1_only':len(posbanks[1]-posbanks[2]),'lag2_only':len(posbanks[2]-posbanks[1])},'positive_key_overlap':dict(positive_key_overlap),'lost_decision_keys_by_lag2_source_absence':dict(loss_reason),'gained_decision_keys_by_lag1_source_absence':dict(gain_reason),'source_row_flow':{str(k):dict(v) for k,v in source_flow.items()},'era_counts':{k:{**v,**{f'positive_window_CERTs_lag{n}':len(bp[k][n]) for n in (1,2)}} for k,v in eras.items()},'exit_class_candidate_counts':[{'era':era,'class':klass,**v} for (era,klass),v in sorted(exit_classes.items())]}
out.write_text(json.dumps(res,indent=2)+'\n'); print(json.dumps({k:v for k,v in res.items() if k!='exit_class_candidate_counts'},indent=2))
