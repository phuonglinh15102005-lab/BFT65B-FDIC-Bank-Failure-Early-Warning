"""Second implementation of key/date reconciliation from the three review ZIPs.

Standard library only. Does not import the 2A/2B/2C producer functions, read all
financial values, query FDIC or change the inputs. This is independent code,
not an independent data source or proof of historical vintage availability.
AI assistance: ChatGPT, 9 November 2026. Sources: course brief and saved FDIC evidence.
"""
import argparse
import calendar
from collections import Counter, defaultdict
import csv
from datetime import date, datetime
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import zipfile


def dt(s):
    if not s or str(s).startswith('9999'):
        return None
    s = str(s)
    for form in ('%Y-%m-%d', '%Y%m%d'):
        try:
            return datetime.strptime(s, form).date()
        except ValueError:
            pass
    raise ValueError('Unrecognised date: '+s)


def quarter_after(d, n):
    k = d.year*4 + (d.month-1)//3 + n
    y, q = divmod(k, 4)
    mo = 3*(q+1)
    return date(y, mo, calendar.monthrange(y, mo)[1])


def read_csv(z, name):
    return list(csv.DictReader(io.StringIO(z.read(name).decode('utf-8-sig'))))


def emit_csv(path, values, columns=None):
    columns = columns or list(values[0])
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(values)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('step2a', 'step2b', 'step2c'):
        ap.add_argument('--'+name+'-zip', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    passed = []
    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        passed.append(name)
    with zipfile.ZipFile(a.step2a_zip) as za, zipfile.ZipFile(a.step2b_zip) as zb, zipfile.ZipFile(a.step2c_zip) as zc:
        check('ZIP CRC', all(z.testzip() is None for z in (za, zb, zc)))
        sa = json.loads(za.read('step2_summary.json'))
        sb = json.loads(zb.read('step2b_summary.json'))
        sc = json.loads(zc.read('step2c_summary.json'))
        for script, summary in [('02_build_panel_base.py', sa), ('02b_collect_exit_evidence.py', sb), ('02c_finalize_panel.py', sc)]:
            if script == '02c_finalize_panel.py':
                expected = json.loads(zc.read('step2c_config.json'))['script_sha256']
            else:
                expected = summary['script_sha256']
            check('Producer identity '+script, hashlib.sha256(Path(__file__).with_name(script).read_bytes()).hexdigest()==expected)
        cov = read_csv(za, 'review_AUDIT_ONLY/bank_coverage_AUDIT_ONLY.csv')
        meta = read_csv(zb, 'review_AUDIT_ONLY/financial_metadata_AUDIT_ONLY.csv')
        hist = read_csv(zb, 'review_AUDIT_ONLY/history_events_AUDIT_ONLY.csv')
        fail = read_csv(za, 'review_AUDIT_ONLY/failure_event_coverage.csv')
        registry = read_csv(zc, 'review_AUDIT_ONLY/bank_event_registry_AUDIT_ONLY.csv')
        reg = {int(r['CERT']): r for r in registry}
        check('Registry one row per source bank', len(reg)==len(registry)==len(cov))
        dates_by_cert = defaultdict(list)
        for r in meta:
            dates_by_cert[int(r['CERT'])].append(dt(r['REPDTE']))
        failure_dates = defaultdict(set)
        for r in fail:
            if r['CERT'] and r['FAILDATE']:
                check_type = r['RESTYPE']=='FAILURE'
                if not check_type: raise AssertionError('Nonfailure in failure evidence')
                failure_dates[int(r['CERT'])].add(dt(r['FAILDATE']))
        terminal = {211,213,215,216,217,221,222,223,224,230,235,240,260}
        merger = {221,222,223,224}
        adverse = {211,215,230,235,260}
        resolution = {213,216,217}
        hh = defaultdict(list)
        for r in hist:
            code = int(r['CHANGECODE']) if r['CHANGECODE'] else None
            if code not in terminal or r['ORG_ROLE_CDE']!='FI': continue
            owner = int(r['CERT']) if r['CERT'] else None
            outgoing = int(r['OUT_CERT']) if r['OUT_CERT'] else None
            if owner and outgoing and owner!=outgoing: raise AssertionError('Role conflict')
            hh[outgoing or owner].append((dt(r['EFFDATE']), code))
        def kind(codes):
            if codes <= merger: return 'MERGER_OR_REORGANIZATION_NONFAILURE'
            if codes == {240}: return 'VOLUNTARY_CLOSURE_NONFAILURE'
            if codes & adverse: return 'ADVERSE_EXIT_WITHOUT_MATCHED_FAILURE'
            if codes <= resolution: return 'ASSISTED_OR_RESOLUTION_EXIT'
            return 'UNRESOLVED_EXIT_TYPE'
        expected_reg = {}
        end = date(2026,6,30)
        for c in cov:
            cert = int(c['CERT']); first=dt(c['FIRST_REPDTE']); last=dt(c['LAST_REPDTE'])
            fd=min(failure_dates[cert]) if failure_dates[cert] else None
            hd=min(x[0] for x in hh[cert]) if hh[cert] else None
            active=c['SNAPSHOT_ACTIVE']; snap=dt(c['SNAPSHOT_ENDEFYMD'])
            rawcode=Decimal(c['SNAPSHOT_CHANGEC1']) if c['SNAPSHOT_CHANGEC1'] else None
            if rawcode is not None and rawcode!=rawcode.to_integral_value():
                raise AssertionError('Nonintegral change code')
            code=int(rawcode) if rawcode is not None else None
            exitdate=stop=None
            if fd:
                klass='FIRST_REGISTER_FAILURE'; src='FAILURES_RESTYPE_FAILURE'
                exitdate=fd; stop=min(fd,hd) if hd else fd
            elif hd:
                klass=kind({x[1] for x in hh[cert] if x[0]==hd})
                src='HISTORY_TERMINAL_EVENT'; exitdate=stop=hd
            elif active=='0' and code in terminal and snap and first<snap<=end:
                klass=kind({code}); src='INSTITUTIONS_REASON_CODED_FALLBACK'; exitdate=stop=snap
            elif active=='1':
                klass='NO_REGISTERED_EXIT_AT_SNAPSHOT'; src='CURRENT_STATUS_OUTCOME_AUDIT_ONLY'
            else:
                klass='UNRESOLVED_OR_UNOBSERVED_EXIT'; src='LAST_REPORT_IS_CENSORING_BOUND_NOT_EXIT'
            bound=min(end,stop) if stop else (end if klass=='NO_REGISTERED_EXIT_AT_SNAPSHOT' else last)
            vals={'EXIT_CLASS':klass,'EXIT_SOURCE':src,'EXIT_DATE':exitdate,'RISK_STOP_DATE':stop,'FIRST_FAILURE_DATE':fd,'ELIGIBILITY_END':bound}
            for key,value in vals.items():
                actual=dt(reg[cert][key]) if key.endswith('DATE') or key=='ELIGIBILITY_END' else reg[cert][key]
                if actual!=value: raise AssertionError(f'Registry mismatch {cert} {key}')
            expected_reg[cert]=vals
        check('Registry recomputed without producer imports', True)
        scope=read_csv(zc,'review_AUDIT_ONLY/insurance_scope_exceptions.csv')
        uninsured={(int(r['CERT']),dt(r['REPDTE'])) for r in scope if r['INSFDIC_OBSERVED']=='0' and r['INSAGNT1_OBSERVED']=='NONE' and r['BKCLASS_OBSERVED']=='NC'}
        check('Scope rule supported for all exception rows',len(uninsured)==len(scope)==sc['confirmed_uninsured_rows'])
        exclusions={}; actions=Counter(); by_quarter=Counter(); dcounts={1:Counter(),2:Counter()}; dbanks={1:set(),2:set()}; positive=Counter(); gaps=[]
        source_count=0; clean_banks=set(); flow=Counter(); encountered_scope=set()
        for c in cov:
            cert=int(c['CERT']); first=dt(c['FIRST_REPDTE']); last=dt(c['LAST_REPDTE'])
            if int(c['INTERNAL_MISSING_QUARTERS']):
                dates=sorted(dates_by_cert[cert])
            else:
                dates=[]; d=first
                while d<=last:
                    dates.append(d); d=quarter_after(d,1)
            if len(dates)!=int(c['OBSERVED_QUARTERS']) or len(dates)!=len(set(dates)) or dates[0]!=first or dates[-1]!=last:
                raise AssertionError('Coverage reconstruction mismatch '+str(cert))
            e=expected_reg[cert]; retained=[]
            for d in dates:
                source_count+=1; key=(cert,d)
                if key in uninsured:
                    action='CONFIRMED_UNINSURED_NC'; encountered_scope.add(key)
                elif e['RISK_STOP_DATE'] and d>=e['RISK_STOP_DATE']:
                    action='AT_OR_AFTER_FAILURE_RISK_STOP' if e['FIRST_FAILURE_DATE'] else 'AT_OR_AFTER_OTHER_EXIT'
                else: action='RETAIN'
                actions[action]+=1;by_quarter[(d,action)]+=1
                if action!='RETAIN':exclusions[key]=action;continue
                retained.append(d);clean_banks.add(cert)
                q=quarter_after(d,1)
                if q>date(2025,6,30):flow['Beyond 2025Q2']+=1
                elif e['RISK_STOP_DATE'] and q>=e['RISK_STOP_DATE']:flow['At/after risk stop']+=1
                elif q>e['ELIGIBILITY_END']:flow['Beyond unresolved follow-up']+=1
                else:flow['Retained']+=1
                for lag in (1,2):
                    q=quarter_after(d,lag)
                    if q>date(2025,6,30) or q>e['ELIGIBILITY_END'] or (e['RISK_STOP_DATE'] and q>=e['RISK_STOP_DATE']):continue
                    dcounts[lag][q]+=1;dbanks[lag].add(cert)
                    if lag==1 and e['FIRST_FAILURE_DATE'] and q<e['FIRST_FAILURE_DATE']<=quarter_after(q,4):positive[cert]+=1
            if retained:
                expected=(retained[-1].year-retained[0].year)*4+(retained[-1].month-retained[0].month)//3+1
                if expected>len(retained):gaps.append((cert,expected-len(retained)))
        check('Source key count and insurance coverage',source_count==sa['rows_output'] and encountered_scope==uninsured)
        actual_exc={(int(r['CERT']),dt(r['REPDTE'])):r['ROW_ACTION'] for r in read_csv(zc,'review_AUDIT_ONLY/excluded_rows_AUDIT_ONLY.csv')}
        check('Every excluded key and reason',actual_exc==exclusions)
        check('Exclusive row accounting',dict(actions)=={r['ROW_ACTION']:int(r['rows']) for r in sc['row_accounting']})
        aq={(dt(r['REPDTE']),r['ROW_ACTION']):int(r['rows']) for r in read_csv(zc,'review_AUDIT_ONLY/row_accounting_by_quarter.csv')}
        check('Every reporting quarter',dict(by_quarter)==aq)
        check('Clean bank count',len(clean_banks)==sc['clean_banks'])
        check('Lag one and two counts',all(sum(dcounts[k].values())==sc['decision_rows_lag'+str(k)] for k in (1,2)))
        check('Decision bank count',len(dbanks[1])==sc['decision_banks_lag1'])
        aq={dt(r['DECISION_DATE']):int(r['rows']) for r in read_csv(zc,'review_AUDIT_ONLY/decision_rows_by_quarter.csv')}
        check('Every decision quarter',dict(dcounts[1])==aq)
        ag={int(r['CERT']):int(r['internal_missing_quarters']) for r in read_csv(zc,'review_AUDIT_ONLY/internal_gaps_after.csv')}
        check('Internal gaps',dict(gaps)==ag)
        ap={int(r['CERT']):int(r['eligible_decisions_in_positive_window']) for r in read_csv(zc,'review_AUDIT_ONLY/first_failure_positive_window_coverage_AUDIT_ONLY.csv')}
        check('Every first-failure positive window count',dict(positive)==ap)
        early=[]; no_window=[]
        for r in registry:
            cert=int(r['CERT']); fd=dt(r['FIRST_FAILURE_DATE']); stop=dt(r['RISK_STOP_DATE'])
            if fd and stop<fd:
                early.append({'CERT':cert,'history_stop':stop,'register_failure':fd,'difference_days':(fd-stop).days,'history_codes':r['HISTORY_TERMINAL_CODES']})
            if fd and cert not in positive:
                if fd<date(1984,1,1): reason='Registered failure before acquisition period'
                elif fd<=date(1984,6,30):reason='Failure before first eligible 1984Q2 decision'
                elif fd>end:reason='Failure after maximum label horizon 2026Q2'
                else:reason='No lagged decision before failure (CERT 32630)'
                no_window.append({'CERT':cert,'first_report':r['FIRST_REPDTE'],'last_report':r['LAST_REPDTE'],'first_failure':fd,'reason':reason})
        emit_csv(a.out/'history_failure_date_exceptions.csv',early)
        emit_csv(a.out/'failure_window_exclusions.csv',no_window)
        fall=Counter(r['EXIT_CLASS'] for r in registry if r['EXIT_SOURCE']=='INSTITUTIONS_REASON_CODED_FALLBACK')
        emit_csv(a.out/'fallback_breakdown.csv',[{'exit_class':k,'banks':v} for k,v in sorted(fall.items())])
        nreason=Counter(r['reason'] for r in no_window)
        emit_csv(a.out/'failure_window_exclusion_summary.csv',[{'reason':k,'banks':v} for k,v in sorted(nreason.items())])
        signs=Counter(r['column'] for r in read_csv(zc,'review_AUDIT_ONLY/negative_stock_values_REVIEW.csv'))
        emit_csv(a.out/'negative_stock_counts.csv',[{'field':k,'negative_cells':v} for k,v in sorted(signs.items())])
        profiles=read_csv(zc,'review_AUDIT_ONLY/numeric_profile_after.csv')
        ratios=[{k:r[k] for k in ('column','min','q01','median','q99','max','zero','null')} for r in profiles if r['column'] in {'ROA','ROE','RBC1AAJ','RBCRWAJ'}]
        emit_csv(a.out/'ratio_extremes.csv',ratios)
        check('Reviewer exception counts',len(early)==19 and min(r['difference_days'] for r in early)==1 and max(r['difference_days'] for r in early)==22 and sum(fall.values())==354 and len(no_window)==30)
        check('Reviewer failure-window explanation', sorted(nreason.values())==[1,2,2,25] and len(positive)==2811)
        check('Negative stock cell total',sum(signs.values())==822)
    result={'status':'PASS','check_count':len(passed),'checks':passed,'implementation':'standard library; no imports from producer scripts','independent_source':False,'full_financial_values_read':False,'metrics':{'history_date_exceptions':len(early),'fallback_breakdown':dict(fall),'positive_window_exclusions':dict(nreason),'negative_stock_cells':sum(signs.values()),'decision_flow':dict(flow)},'limits':['Shares supplied review evidence; not independent source validation.','No complete output Parquet bytes available in this review.','Economic validity of every retained value and original-vintage availability not established.']}
    (a.out/'independent_review_results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
