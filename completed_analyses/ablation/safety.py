"""Read-only source / isolated-output checks for the authorized ablation."""
from pathlib import Path
import hashlib, json, os, sys

class Blocked(RuntimeError):
    pass

def require(ok, message):
    if not bool(ok):
        raise ValueError(message)

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()

def inside(path, parent):
    return Path(path).resolve().is_relative_to(Path(parent).resolve())

def validate_output(out, package, dev):
    require(not inside(out,package), 'Output must be outside the package')
    require(not inside(out,dev.parent) and not inside(dev,out), 'Output overlaps original data')
    require(not out.exists(), 'Output directory already exists; never resume or overwrite')

DENIED_PARTS=('final_test','test_primary_binary','06_test_locked','step06',
              'final_hgb_refit','final_model_lock')

def denied(path):
    name=str(path).replace('\\','/').casefold()
    return any(part in name for part in DENIED_PARTS)

class AccessPolicy:
    """Python audit hook, defense in depth; not an OS/native-Arrow sandbox."""
    def __init__(self, out, dev, claim):
        self.out=Path(out).resolve();self.dev=Path(dev).resolve();self.claim=Path(claim).resolve()
        self.parquet_open_events=0

    def audit(self,event,args):
        if event in {'socket.connect','socket.getaddrinfo','subprocess.Popen'}:
            raise PermissionError('Ablation forbids network and subprocesses')
        if event!='open' or not args or not isinstance(args[0],(str,bytes,os.PathLike)):
            return
        p=Path(os.fsdecode(args[0])).absolute()
        if denied(p):raise PermissionError('Final-test/frozen-model path forbidden: '+p.name)
        if p.suffix.casefold() in {'.joblib','.pkl','.pickle'}:
            raise PermissionError('Serialized models are not allowed')
        if p.suffix.casefold()=='.parquet':
            if p.resolve()!=self.dev:raise PermissionError('Only exact development Parquet may be read')
            self.parquet_open_events+=1
        mode=args[1] if len(args)>1 else None
        flags=args[2] if len(args)>2 and isinstance(args[2],int) else 0
        writes=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
        if writes and not (p.resolve().is_relative_to(self.out) or p.resolve()==self.claim):
            raise PermissionError('Write outside isolated output/own claim forbidden: '+str(p))

def create_claim(path, out, command):
    value=dict(state='STARTED_NO_FIT_YET',out=str(out),command=command,fit_attempts=0,
               policy='At most three additional HGB fits; no automatic retry/resume')
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2)
    except FileExistsError:
        raise Blocked('A previous execution claim exists. Do not repeat training; send previous output for review: '+str(path))
    return value

def update_claim(path,value):
    # This is the NEW runner's own mutable progress ledger, never an original artifact.
    with path.open('w',encoding='utf-8') as stream:json.dump(value,stream,indent=2)

def reserve_fit_attempt(path,value,fold):
    require(value['fit_attempts']<3,'Fit budget exhausted: never attempt a fourth HGB fit')
    value['fit_attempts']+=1
    value['state']='FIT_ATTEMPT_STARTED';value['fold']=fold
    update_claim(path,value)
    return value['fit_attempts']
