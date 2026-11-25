"""Strict continuous data-producer DAG; model and test stages are excluded."""
from pathlib import Path
from workflow.common import ROOT,require,read_json,sha

SOURCES={
 'prepare':'01_PART1_ACQUISITION_STORAGE/code/audit_fdic.py',
 'base':'02_PART2_DATA_QUALITY_PANEL/code/02_build_panel_base.py',
 'exits':'02_PART2_DATA_QUALITY_PANEL/code/02b_collect_exit_evidence.py',
 'clean':'02_PART2_DATA_QUALITY_PANEL/code/02c_finalize_panel.py',
 'features':'04_PART4_FEATURE_PIPELINE/code/part4_v2_relabel_asof_gate.py',
}
REPORTS=['bank_coverage_AUDIT_ONLY.csv','failure_event_coverage.csv','unmatched_institutions.csv',
 'banks_with_internal_gaps.csv','multiple_failure_events.csv','reports_after_inactive_date_REVIEW.csv',
 'numeric_profile.csv','missingness_by_quarter.csv','column_availability.csv','text_cleanup.csv','rows_by_quarter.csv']

def stages(start):
    require(start in {'raw','prepared'},'Start must be raw or prepared')
    return list(SOURCES) if start=='raw' else list(SOURCES)[1:]

def artifact(run,stage):return Path(run)/stage/'artifacts'

def command_arguments(stage,run,inputs,start):
    require(stage in stages(start),'Stage not in selected continuous chain')
    out=artifact(run,stage)
    prepared=artifact(run,'prepare') if start=='raw' else inputs['prepared_audit']
    base=artifact(run,'base');exits=artifact(run,'exits');clean=artifact(run,'clean')
    if stage=='prepare':return ['--data-dir',str(inputs['raw_fdic_dir']),'--out',str(out),'--prepare',
        '--start','1984-03-31','--end','2026-06-30','--expected-failures','4117','--expected-institutions','27835']
    if stage=='base':return ['--audit-dir',str(prepared),'--out',str(out)]
    if stage=='exits':return ['--step2-dir',str(base),'--out',str(out),'--offline','--cache-dir',str(inputs['step2b']/'request_cache')]
    if stage=='clean':return ['--step2-dir',str(base),'--step2b-dir',str(exits),'--out',str(out),'--offline','--cache-dir',str(inputs['step2c']/'request_cache')]
    return ['--clean',str(clean/'panel_clean.parquet'),'--pit',str(clean/'panel_pit_base.parquet'),
        '--registry-zip',str(clean/'part2_clean_review_bundle.zip'),'--step01-source',str(ROOT/'04_PART4_FEATURE_PIPELINE/code/part4_step01_reference_UNCHANGED.py'),
        '--out-dir',str(out),'--production-only','--asof-quarters','0']

def assert_arguments(stage,args,run,inputs,start):
    # Equal to the complete generated vector: cannot silently use a frozen parent.
    require(args==command_arguments(stage,run,inputs,start),'Continuous producer arguments differ from registered fresh-parent DAG')
    target=artifact(run,stage).resolve();require(not target.exists(),'Producer output already exists')
    require(target.is_relative_to(Path(run).resolve()),'Producer output escapes run')

def signature(base):
    return {p.name:sha(p) for p in [base/'step2_summary.json',*[base/'review_AUDIT_ONLY'/n for n in REPORTS]]}

def check_lineage(stage,run,inputs,start):
    """Validate actual native metadata; never edit it to make an edge pass."""
    out=artifact(run,stage);evidence=[]
    def same(actual,expected,label):
        require(Path(actual).resolve()==Path(expected).resolve(),label+' parent path mismatch')
        evidence.append(dict(check=label,status='PASS',actual=str(actual),expected=str(expected)))
    if stage=='prepare':
        v=read_json(out/'summary.json');same(v['data_dir'],inputs['raw_fdic_dir'],'raw_to_preparation')
        require(v['errors']==0 and v['prepared_state']=='STANDARDIZED_FOR_REVIEW','Native preparation did not complete')
    elif stage=='base':
        v=read_json(out/'step2_summary.json')
        same(v['audit_dir'],artifact(run,'prepare') if start=='raw' else inputs['prepared_audit'],'preparation_to_base')
        require(v['panel_sha256']==sha(out/'panel_base.parquet'),'Native base identity mismatch')
    elif stage=='exits':
        base=artifact(run,'base');v=read_json(out/'step2b_summary.json');cfg=read_json(out/'step2b_config.json')
        same(v['step2_dir'],base,'base_to_new_part2b');same(cfg['step2_dir'],base,'part2b_signature_parent')
        require(cfg['source_sha256']==signature(base),'Fresh Part2B signature does not bind fresh Part2A')
        require(v['source_panel_sha256_recorded_in_step2A']==sha(base/'panel_base.parquet'),'Part2B bound a different base panel')
        require(v['source_csv_inputs_verified_unchanged'] and v['supplemental_count_or_date_bound_mismatches']==0,'Native Part2B validation failed')
        for name in REPORTS:require(sha(out/'review_AUDIT_ONLY'/('step2A_'+name))==cfg['source_sha256'][name],'Part2B copied report differs from its fresh parent')
        evidence.append(dict(check='native_new_signature_and_copied_reports',status='PASS',files=len(REPORTS)+1))
    elif stage=='clean':
        v=read_json(out/'step2c_config.json');base=artifact(run,'base');exits=artifact(run,'exits')
        same(v['step2_dir'],base,'fresh_base_to_part2c');same(v['step2b_dir'],exits,'fresh_part2b_to_part2c')
        require(v['panel_sha256']==sha(base/'panel_base.parquet'),'Part2C used a different base')
        for name,h in v['step2b_inputs'].items():require(sha(exits/name)==h,'Part2C fresh Part2B digest mismatch')
        require(bool(v['step2b_inputs']),'Missing Part2C source signature')
    else:
        # Worker argv/input hashes prove feature reads; no historical cohort fallback.
        for flag,name in [('--clean','panel_clean.parquet'),('--pit','panel_pit_base.parquet'),('--registry-zip','part2_clean_review_bundle.zip')]:
            path=artifact(run,'clean')/name;require(path.is_file(),'Missing fresh feature parent '+name)
            evidence.append(dict(check=flag,status='PASS',path=str(path),sha256=sha(path)))
    return evidence
