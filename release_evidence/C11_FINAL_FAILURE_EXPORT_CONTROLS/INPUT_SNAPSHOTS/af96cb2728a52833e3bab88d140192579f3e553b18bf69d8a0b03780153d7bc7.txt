"""Fault-injection test: a source-integrity failure must still export FAIL evidence."""
from pathlib import Path
import argparse,json,tempfile,unittest
from unittest.mock import patch
from workflow import engine
from workflow.common import ROOT

class FailureExport(unittest.TestCase):
    def test_source_drift_after_preflight_still_exports_fail_zip(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);out=base/'new_output'
            args=argparse.Namespace(config=ROOT/'config/default.json',profile=base/'missing_profile',out=out,
                                    python_engineering=None,stages='unverified',reveal=False)
            with patch.object(engine,'choose_python',return_value=(None,None,[])),patch.object(engine,'verify_source_manifest',side_effect=[{'source':'same'}, {'source':'same'}, ValueError('SYNTHETIC_SOURCE_DRIFT')]):
                # First call is the initial source check,second is source_before,third is source_after.
                code=engine.replay(args)
            self.assertEqual(code,1)
            result=json.loads((out/'REPLAY_RESULT.json').read_text())
            self.assertEqual(result['status'],'FAIL')
            self.assertIn('SYNTHETIC_SOURCE_DRIFT',result['source_integrity_error'])
            self.assertTrue(out.with_name(out.name+'_GUI_LAI_CHO_CODEX.zip').is_file())
            self.assertEqual(result['new_model_fits'],0)
            self.assertEqual(result['full_clean_room_E2E'],'NOT_EXECUTED')

    def test_missing_final_source_manifest_digest_still_exports_fail_zip(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);out=base/'new_output'
            args=argparse.Namespace(config=ROOT/'config/default.json',profile=base/'missing_profile',out=out,
                                    python_engineering=None,stages='unverified',reveal=False)
            original_hash=engine.sha
            def missing_manifest(path):
                if Path(path).name=='source_manifest.json':raise FileNotFoundError('SYNTHETIC_MISSING_MANIFEST')
                return original_hash(path)
            with patch.object(engine,'choose_python',return_value=(None,None,[])),patch.object(engine,'verify_source_manifest',side_effect=[{'source':'same'}, {'source':'same'}, FileNotFoundError('SYNTHETIC_MISSING_MANIFEST')]),patch.object(engine,'sha',side_effect=missing_manifest):
                code=engine.replay(args)
            self.assertEqual(code,1)
            result=json.loads((out/'REPLAY_RESULT.json').read_text())
            self.assertEqual(result['status'],'FAIL');self.assertIsNone(result['source_manifest_sha256'])
            self.assertTrue(out.with_name(out.name+'_GUI_LAI_CHO_CODEX.zip').is_file())

if __name__=='__main__':unittest.main(verbosity=2)
