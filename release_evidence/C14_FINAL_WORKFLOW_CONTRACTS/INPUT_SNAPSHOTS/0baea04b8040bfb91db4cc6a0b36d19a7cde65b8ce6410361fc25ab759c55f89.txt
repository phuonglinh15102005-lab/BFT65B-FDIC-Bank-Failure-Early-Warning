"""Explicit stage policy and isolated-write guard; not an OS/native IO sandbox."""
from pathlib import Path
import os,sys
from workflow.common import ROOT,require

ALLOWED={
 'p2-base':'02_PART2_DATA_QUALITY_PANEL/code/02_build_panel_base.py',
 'p2-clean':'02_PART2_DATA_QUALITY_PANEL/code/02c_finalize_panel.py',
 'development-features':'04_PART4_FEATURE_PIPELINE/code/part4_v2_relabel_asof_gate.py',
}
CLOSED={'R23','R24','ablation','model-selection','test-metrics','posthoc-ci','part3-polars','part3-pandas','part3-spark'}
FORBIDDEN={'train','fit','refit','grid','logistic','hgb','baseline','spark-mllib','final-test','score','threshold-search','download'}

def permitted_stage(name):
    require(name in ALLOWED,'Stage is not in the new data-producer allowlist; no training/scoring or closed audit dispatch: '+name)
    return ALLOWED[name]

def validate_arguments(stage,args,out):
    permitted_stage(stage)
    require(not any(x in args for x in ['--self-test','--fit','--refit','--score','--download','--old-dev','--pandas-oracle-source','--assistance-events-csv']), 'Forbidden or closed-audit arguments')
    output_flag='--out-dir' if stage=='development-features' else '--out'
    require(args.count(output_flag)==1,'Exactly one explicit output required')
    target=Path(args[args.index(output_flag)+1]).resolve()
    require(target.is_relative_to(out) and target!=out,'Producer output must be a NEW child of its isolated job')
    if stage=='p2-clean':require('--offline' in args and '--cache-dir' in args,'Part2C is offline-only using read-only cache')
    if stage=='development-features':
        require('--production-only' in args and '--asof-quarters' in args,'Development producer-only mode required')
        require(args[args.index('--asof-quarters')+1]=='0','Do not repeat closed canary audits')

DENIED_READS=('final_test','test_primary_binary','06_test_locked','final_hgb_refit','final_model_lock','step06b','step06a')
class Guard:
    def __init__(self,out):self.out=Path(out).resolve()
    def write(self,path):
        if isinstance(path,int):return
        require(Path(path).resolve().is_relative_to(self.out),'Write outside isolated output forbidden: '+str(path))
    def hook(self,event,args):
        if event=='open':
            path,mode,flags=args[:3]
            if isinstance(path,(str,bytes,os.PathLike)):
                p=os.fsdecode(path).replace('\\','/').casefold()
                if any(token in p for token in DENIED_READS) or Path(p).suffix in {'.joblib','.pkl','.pickle'}:
                    raise PermissionError('Frozen model/final-test input is forbidden in producer replay: '+p)
            writing=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
            if writing:self.write(path)
        elif event in {'os.mkdir','os.remove','os.rmdir','os.truncate','os.chmod','os.utime'}:self.write(args[0])
        elif event in {'os.rename','os.replace','os.link','os.symlink'}:
            self.write(args[0]);self.write(args[1])
        elif event in {'subprocess.Popen','os.system','os.posix_spawn','socket.connect','socket.bind','socket.getaddrinfo'}:
            raise PermissionError('Data replay forbids subprocesses/network: '+event)
    def install(self):sys.addaudithook(self.hook)
