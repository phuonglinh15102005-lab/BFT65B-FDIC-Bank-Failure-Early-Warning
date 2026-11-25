"""New lineage/offline/CSV/error contracts. Synthetic metadata only, no models."""
from pathlib import Path
import argparse,csv,hashlib,json,os,sys,tempfile,unittest
from unittest.mock import patch
from workflow import continuous as c
from workflow.common import ROOT,read_json,save_json,sha,inputs_for
from workflow.continuous_contract import SOURCES,REPORTS,artifact,stages,command_arguments,assert_arguments,signature,check_lineage
from workflow.continuous_compare import csv_signature,compare_csv
from workflow.offline_part2b import load_native,install_cache_adapter,NATIVE_SHA,SOURCE

class ContinuousGraph(unittest.TestCase):
    def paths(self,root):
        return {k:root/'original'/k for k in read_json(ROOT/'config/default.json')['inputs']}
    def test_raw_and_prepared_stage_order(self):
        self.assertEqual(stages('raw'),['prepare','base','exits','clean','features'])
        self.assertEqual(stages('prepared'),['base','exits','clean','features'])
        for bad in ['test','fit','ablation','final-test','download']:
            with self.assertRaises(ValueError):stages(bad)
    def test_native_sources_do_not_include_any_model_or_scorer(self):
        self.assertEqual(len(SOURCES),5)
        self.assertTrue(all('05_PART5' not in p and (ROOT/p).is_file() for p in SOURCES.values()))
    def test_unit_subprocess_records_and_uses_explicit_cwd(self):
        from workflow.engine import stream_command
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);logs=root/'logs';logs.mkdir();cwd=root/'working';cwd.mkdir()
            code=stream_command([sys.executable,'-B','-c','import os; print(os.getcwd())'],logs,{**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},cwd=cwd)
            self.assertEqual(code,0)
            self.assertEqual(Path((logs/'STDOUT.txt').read_text().strip()).resolve(),cwd.resolve())
            self.assertEqual(read_json(logs/'EXECUTION_CONTEXT.json')['working_directory'],str(cwd.resolve()))
    def test_every_child_binds_fresh_parent_and_rejects_frozen_path(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);run=root/'new';inputs=self.paths(root)
            for stage,flag,frozen in [('base','--audit-dir',inputs['prepared_audit']),('exits','--step2-dir',inputs['step2']),('clean','--step2b-dir',inputs['step2b']),('features','--clean',inputs['step2c']/'panel_clean.parquet')]:
                good=command_arguments(stage,run,inputs,'raw');assert_arguments(stage,good,run,inputs,'raw')
                bad=list(good);bad[bad.index(flag)+1]=str(frozen)
                with self.subTest(stage=stage),self.assertRaises(ValueError):assert_arguments(stage,bad,run,inputs,'raw')
    def test_existing_producer_output_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as t:
            run=Path(t)/'run';inputs=self.paths(Path(t));artifact(run,'base').mkdir(parents=True)
            with self.assertRaises(ValueError):assert_arguments('base',command_arguments('base',run,inputs,'raw'),run,inputs,'raw')
    def test_offline_and_production_only_flags_cannot_be_removed(self):
        with tempfile.TemporaryDirectory() as t:
            run=Path(t)/'run';inputs=self.paths(Path(t))
            for stage,flag in [('exits','--offline'),('clean','--offline'),('features','--production-only')]:
                args=command_arguments(stage,run,inputs,'raw');args.remove(flag)
                with self.subTest(stage=stage),self.assertRaises(ValueError):assert_arguments(stage,args,run,inputs,'raw')
    def make_new_b(self,run):
        base=artifact(run,'base');out=artifact(run,'exits');(base/'review_AUDIT_ONLY').mkdir(parents=True);(out/'review_AUDIT_ONLY').mkdir(parents=True)
        (base/'panel_base.parquet').write_bytes(b'SYNTHETIC_METADATA_FIXTURE_NOT_BANK_DATA')
        save_json(base/'step2_summary.json',dict(synthetic=True))
        for name in REPORTS:(base/'review_AUDIT_ONLY'/name).write_text('synthetic_column\nfixture\n')
        sig=signature(base);save_json(out/'step2b_config.json',dict(step2_dir=str(base),source_sha256=sig))
        save_json(out/'step2b_summary.json',dict(step2_dir=str(base),source_panel_sha256_recorded_in_step2A=sha(base/'panel_base.parquet'),source_csv_inputs_verified_unchanged=True,supplemental_count_or_date_bound_mismatches=0))
        for name in REPORTS:(out/'review_AUDIT_ONLY'/('step2A_'+name)).write_bytes((base/'review_AUDIT_ONLY'/name).read_bytes())
        return base,out
    def test_actual_new_b_signature_and_copies_bind_new_base(self):
        with tempfile.TemporaryDirectory() as t:
            run=Path(t)/'run';base,out=self.make_new_b(run)
            result=check_lineage('exits',run,self.paths(Path(t)),'raw')
            self.assertTrue(all(x['status']=='PASS' for x in result))
            self.assertEqual(signature(base),load_native().input_signature(base))
    def test_reusing_old_b_signature_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            run=Path(t)/'run';base,out=self.make_new_b(run);cfg=read_json(out/'step2b_config.json');cfg['source_sha256']['step2_summary.json']='0'*64;save_json(out/'step2b_config.json',cfg)
            with self.assertRaises(ValueError):check_lineage('exits',run,self.paths(Path(t)),'raw')
    def test_changed_copied_report_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            run=Path(t)/'run';base,out=self.make_new_b(run)
            (out/'review_AUDIT_ONLY'/('step2A_'+REPORTS[0])).write_text('changed')
            with self.assertRaises(ValueError):check_lineage('exits',run,self.paths(Path(t)),'raw')
    def test_preflight_missing_raw_and_cache_is_blocked(self):
        with tempfile.TemporaryDirectory() as t:
            inputs=self.paths(Path(t));v=c.preflight(read_json(ROOT/'config/default.json'),inputs,'raw')
            self.assertEqual(v['status'],'BLOCKED')
            self.assertTrue(any(x['role']=='original-raw-checksum-ledger' for x in v['missing']))
            self.assertTrue(any(x['role']=='required-offline-cache-directory' for x in v['missing']))
    def test_malformed_raw_ledger_fails_instead_of_relaxing_scope(self):
        with tempfile.TemporaryDirectory() as t:
            inputs=self.paths(Path(t));inputs['prepared_audit'].mkdir(parents=True)
            (inputs['prepared_audit']/'file_checksums.csv').write_text('file,sha256\n../escape,0000\n')
            v=c.preflight(read_json(ROOT/'config/default.json'),inputs,'raw')
            self.assertEqual(v['status'],'FAIL');self.assertEqual(v['raw_ledger_status'],'INVALID_RAW_LEDGER')
    def test_parent_failure_prevents_all_descendants_and_still_exports(self):
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)/'new';args=argparse.Namespace(config=ROOT/'config/default.json',profile=Path(t)/'missing',out=out,start='prepared',python_engineering=None,reveal=False)
            with patch.object(c,'verify_source_manifest',return_value={}),patch.object(c,'preflight',return_value=dict(status='PASS',inputs={},missing=[],errors=[])),patch.object(c,'choose_python',return_value=(Path(sys.executable),{'synthetic':True},[])),patch.object(c,'stream_command',return_value=0),patch.object(c,'run_stage',return_value=dict(stage='base',status='FAIL',reason='SYNTHETIC_PARENT_FAILURE')) as runner:
                code=c.execute(args)
            self.assertEqual(code,1);self.assertEqual(runner.call_count,1)
            v=read_json(out/'CONTINUOUS_RESULT.json')
            for stage in ['exits','clean','features']:self.assertEqual(v['stages'][stage]['status'],'NOT_EXECUTED')
            self.assertFalse(v['frozen_checkpoint_fallback']);self.assertTrue(out.with_name(out.name+'_GUI_LAI_CHO_CODEX.zip').is_file())
    def test_lost_final_manifest_still_exports_fail_without_any_producer(self):
        from workflow import engine
        original=engine.sha
        def absent(path):
            if Path(path).name=='source_manifest.json':raise FileNotFoundError('SYNTHETIC_LOST_MANIFEST')
            return original(path)
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)/'new';args=argparse.Namespace(config=ROOT/'config/default.json',profile=Path(t)/'missing',out=out,start='raw',python_engineering=None,reveal=False)
            with patch.object(c,'verify_source_manifest',side_effect=[{},FileNotFoundError('SYNTHETIC_LOST_MANIFEST')]),patch.object(c,'preflight',return_value=dict(status='BLOCKED',inputs={},missing=[],errors=[])),patch.object(c,'choose_python',return_value=(None,None,[])),patch.object(engine,'sha',side_effect=absent):
                code=c.execute(args)
            self.assertEqual(code,1);v=read_json(out/'CONTINUOUS_RESULT.json')
            self.assertEqual(v['status'],'FAIL');self.assertIsNone(v['source_manifest_sha256'])
            self.assertEqual(v['continuous_data_replay'],'NOT_EXECUTED');self.assertTrue(out.with_name(out.name+'_GUI_LAI_CHO_CODEX.zip').is_file())

class NativeOfflineAdapter(unittest.TestCase):
    def test_native_source_is_original_bytes(self):self.assertEqual(sha(SOURCE),NATIVE_SHA)
    def cache_fixture(self,root):
        cache=root/'cache';cache.mkdir();url='https://example.invalid/synthetic-evidence';body=b'{"synthetic": true}';key=hashlib.sha256(url.encode()).hexdigest()
        (cache/(key+'.body')).write_bytes(body);save_json(cache/(key+'.json'),dict(url=url,sha256=hashlib.sha256(body).hexdigest()))
        return cache,url,body
    def test_offline_cache_hit_preserves_original_and_records_url(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);cache,url,body=self.cache_fixture(root);out=root/'new';out.mkdir();native=load_native();original=install_cache_adapter(native,cache)
            try:
                with patch.object(native,'urlopen',side_effect=AssertionError('NO NETWORK')):
                    collector=native.Collector(out,offline=True);self.assertEqual(collector.get(url),body);self.assertTrue(collector.records[0]['reused_cache'])
                self.assertEqual((cache/(hashlib.sha256(url.encode()).hexdigest()+'.body')).read_bytes(),body)
            finally:native.Collector.__init__=original
    def test_offline_miss_does_not_download(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);cache,url,body=self.cache_fixture(root);out=root/'new';out.mkdir();native=load_native();original=install_cache_adapter(native,cache)
            try:
                with patch.object(native,'urlopen') as network:
                    with self.assertRaises(ValueError):native.Collector(out,offline=True).get(url+'/missing')
                    network.assert_not_called()
            finally:native.Collector.__init__=original
    def test_cached_body_corruption_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);cache,url,body=self.cache_fixture(root);(cache/(hashlib.sha256(url.encode()).hexdigest()+'.body')).write_bytes(b'CORRUPTED')
            out=root/'new';out.mkdir();native=load_native();original=install_cache_adapter(native,cache)
            try:
                with self.assertRaises(ValueError):native.Collector(out,offline=True).get(url)
            finally:native.Collector.__init__=original
    def test_online_mode_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);cache,url,body=self.cache_fixture(root);out=root/'new';out.mkdir();native=load_native();original=install_cache_adapter(native,cache)
            try:
                with self.assertRaises(ValueError):native.Collector(out,offline=False)
            finally:native.Collector.__init__=original

class CSVContracts(unittest.TestCase):
    def compare(self,left,right):
        with tempfile.TemporaryDirectory() as t:
            a=Path(t)/'new.csv';b=Path(t)/'reference.csv';a.write_text(left);b.write_text(right)
            return compare_csv(dict(id='synthetic',new=str(a),reference=str(b)))
    def test_reordering_with_duplicates_preserves_multiset(self):
        r=self.compare('key,x\na,1\na,1\nb,2\n','key,x\nb,2\na,1\na,1\n');self.assertEqual(r['status'],'PASS_CSV_EQUIVALENCE');self.assertFalse(r['byte_identical'])
    def test_omitted_duplicate_is_not_deduplicated(self):self.assertEqual(self.compare('key,x\na,1\n','key,x\na,1\na,1\n')['status'],'FAIL')
    def test_label_or_date_value_change_fails(self):self.assertEqual(self.compare('key,date\na,2001-03-31\n','key,date\na,2001-06-30\n')['status'],'FAIL')
    def test_header_change_fails(self):self.assertEqual(self.compare('key,x\na,1\n','key,y\na,1\n')['status'],'FAIL')
    def test_malformed_row_and_duplicate_header_fail(self):
        for text in [b'key,x\na\n',b'key,key\na,b\n']:
            with self.assertRaises(ValueError):csv_signature(text)

if __name__=='__main__':unittest.main(verbosity=2)
