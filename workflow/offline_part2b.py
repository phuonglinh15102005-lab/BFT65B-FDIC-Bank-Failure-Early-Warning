"""Transport-only adapter for the byte-unchanged native Part2B producer.

Native main generates a NEW config/signature from the NEW Part2A reports. Only
the Collector cache directory is redirected; no output/report/signature is copied.
"""
from pathlib import Path
import importlib.util,sys
from workflow.common import ROOT,require,sha,save_json

SOURCE=ROOT/'02_PART2_DATA_QUALITY_PANEL/code/02b_collect_exit_evidence.py'
NATIVE_SHA='9935d369667b4b5ff17dc5853bc81ccc7ee0af9f87792d2fb62f30c9f021f3ec'

def load_native():
    require(sha(SOURCE)==NATIVE_SHA,'Native Part2B source changed')
    spec=importlib.util.spec_from_file_location('bft_continuous_native_2b',SOURCE)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def install_cache_adapter(module,cache):
    cache=Path(cache).resolve();require(cache.is_dir(),'Original Part2B cache missing')
    original=module.Collector.__init__
    def init(collector,root,offline=False):
        require(offline,'Continuous Part2B must be offline')
        original(collector,root,offline=True)
        collector.cache=cache
    module.Collector.__init__=init
    return original

def run(arguments,out):
    require('--offline' in arguments and arguments.count('--cache-dir')==1,'Offline cache required')
    i=arguments.index('--cache-dir');cache=Path(arguments[i+1]).resolve()
    require(not out.is_relative_to(cache) and not cache.is_relative_to(out),'Cache/output overlap')
    native_args=arguments[:i]+arguments[i+2:]
    module=load_native();original=install_cache_adapter(module,cache)
    sys.argv=[str(SOURCE),*native_args]
    try:
        result=module.main()
    finally:
        module.Collector.__init__=original
    save_json(out.parent/'OFFLINE_ADAPTER.json',dict(native_source=str(SOURCE),native_sha256=sha(SOURCE),
        adapter_sha256=sha(Path(__file__)),native_arguments=native_args,read_only_cache=str(cache),
        fresh_part2b_generated=True,old_part2b_reports_copied=False,signatures_rewritten=False))
    return result
