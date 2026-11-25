from pathlib import Path
import hashlib,json,os,sys
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
class Blocked(RuntimeError):pass
def require(ok,msg):
    if not bool(ok):raise ValueError(msg)
def read_json(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def save_json(path,value):Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(4*1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()
def resolve_profile(config,override=None):
    return Path(override or os.environ.get('USERPROFILE') or Path.home()).expanduser().resolve()
def inputs_for(config,profile):
    return {name:(profile/item).resolve() if not Path(item).is_absolute() else Path(item).resolve() for name,item in config['inputs'].items()}
def load_config(path):
    value=read_json(path);canonical=read_json(ROOT/'config/default.json')
    for key in ['release_id','reference_files','default_new_replay_stages','read_only_cache']:
        require(value.get(key)==canonical[key],'Configuration may override input paths only, not frozen contracts: '+key)
    require(set(value['inputs'])==set(canonical['inputs']),'Input configuration keys differ')
    require(all(isinstance(p,str) and p for p in value['inputs'].values()),'Every input path must be an explicit nonempty string')
    return value
def validate_output(out,inputs):
    out=Path(out).resolve();require(not out.exists(),'Output already exists; do not overwrite/resume')
    require(not out.is_relative_to(ROOT) and not ROOT.is_relative_to(out),'Output overlaps repository')
    for path in inputs.values():
        parent=path if path.is_dir() or path.suffix=='' else path.parent
        require(not out.is_relative_to(parent) and not path.is_relative_to(out),'Output overlaps a source/input directory: '+str(path))
    return out
def verify_source_manifest():
    expected=read_json(ROOT/'config/source_manifest.json')
    for name,digest in expected.items():
        p=(ROOT/name).resolve();require(p.is_relative_to(ROOT),'Manifest path escape')
        require(p.is_file() and sha(p)==digest,'Source/config/reference metadata changed: '+name)
    return expected
def input_digest(path,expected=None):
    if not path.is_file():raise Blocked('Required external file is missing: '+str(path))
    actual=sha(path)
    if expected is not None:require(actual==expected,'Existing input SHA mismatch; do not select another/latest dataset: '+str(path))
    return actual
def package_hashes(folder):
    return {p.relative_to(folder).as_posix():sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}
