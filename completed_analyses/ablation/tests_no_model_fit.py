"""Synthetic contract tests. No HGB/other estimator is fitted by these tests."""
from pathlib import Path
import json,tempfile,unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
import ablation_runner as a
from safety import AccessPolicy,Blocked,create_claim,validate_output,denied,reserve_fit_attempt

CONFIG=json.loads((a.HERE/'CONFIG.json').read_text())

class Tests(unittest.TestCase):
    def sample(self):
        frame=pd.DataFrame({name:np.arange(12,dtype=float)+j for j,name in enumerate(a.CONTINUOUS)})
        for name in a.BINARY:frame[name]=[0.,1.]*6
        frame.loc[[0,3,8],'asset_log_growth_1q']=np.nan
        frame.loc[[1,4],'asset_log_growth_4q']=np.nan
        return frame

    def test_exact_two_flags_only_and_growth_values_retained(self):
        data=self.sample();prep=a.make_preprocessor(clip=False)
        full=prep.fit_transform(data);contract=a.feature_contract(CONFIG)
        reduced=a.remove_indicators(full,contract)
        self.assertEqual(full.shape,(12,30));self.assertEqual(reduced.shape,(12,28))
        self.assertTrue(np.array_equal(full[:,17],data.asset_log_growth_1q.isna().astype(float)))
        self.assertTrue(np.array_equal(full[:,18],data.asset_log_growth_4q.isna().astype(float)))
        self.assertTrue(np.array_equal(full[:,2:4],reduced[:,2:4]))
        for j,i in enumerate(contract['retained_indices']):self.assertTrue(np.array_equal(reduced[:,j],full[:,i]))

    def test_validation_values_and_missingness_never_refit(self):
        train=self.sample();prep=a.make_preprocessor(clip=False);prep.fit(train)
        before=a.preprocess_state(prep);validation=train.copy()
        validation.loc[:,'log_assets']=1e25;validation.loc[:,'asset_log_growth_1q']=np.nan
        prep.transform(validation);self.assertEqual(before,a.preprocess_state(prep))

    def test_transformation_rejects_width_and_wrong_indicator_names(self):
        with self.assertRaises(ValueError):a.remove_indicators(np.zeros((2,29)),a.feature_contract(CONFIG))
        invalid=dict(CONFIG,drop_transformed_names=['continuous__asset_log_growth_1q','continuous__asset_log_growth_4q'])
        with self.assertRaises(ValueError):a.feature_contract(invalid)

    def test_version_drift_is_blocked(self):
        observed={'python':'3.13.7','packages':{k:v for k,v in {**CONFIG['expected_core'],**CONFIG['additional_current_observed_runtime_pins']}.items() if k!='python'}}
        self.assertEqual(a.environment_blockers(CONFIG,observed),[])
        observed['packages']['scikit-learn']='wrong'
        self.assertTrue(any('scikit-learn' in x for x in a.environment_blockers(CONFIG,observed)))

    def test_no_final_or_other_parquet_or_source_writes(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);dev=base/'data/development_primary_binary_v2.parquet';out=base/'out'
            policy=AccessPolicy(out,dev,base/'THREE_FITS_EXECUTION_CLAIM.json')
            for p in [base/'06_test_locked/scores.csv.gz',base/'final_hgb_refit.joblib',base/'unrelated.parquet']:
                with self.assertRaises(PermissionError):policy.audit('open',(str(p),'r',0))
            with self.assertRaises(PermissionError):policy.audit('open',(str(dev),'w',0))
            policy.audit('open',(str(dev),'r',0));policy.audit('open',(str(out/'new.json'),'w',0))
            with self.assertRaises(PermissionError):policy.audit('socket.connect',())
            with self.assertRaises(PermissionError):policy.audit('subprocess.Popen',())

    def test_output_overlap_and_claim_never_resume(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);dev=base/'data/dev.parquet';package=base/'package'
            with self.assertRaises(ValueError):validate_output(package/'new',package,dev)
            with self.assertRaises(ValueError):validate_output(dev.parent/'new',package,dev)
            out=base/'new';validate_output(out,package,dev)
            claim=base/'THREE_FITS_EXECUTION_CLAIM.json';create_claim(claim,out,['synthetic-no-fit'])
            with self.assertRaises(Blocked):create_claim(claim,out,['synthetic-no-fit'])

    def test_fixed_hyperparameters_and_no_estimator_fit(self):
        model=HistGradientBoostingClassifier(**CONFIG['HGB'])
        self.assertEqual(model.max_leaf_nodes,15);self.assertEqual(model.max_iter,150)
        self.assertFalse(model.early_stopping);self.assertEqual(model.random_state,20261114)
        with patch.object(HistGradientBoostingClassifier,'fit',side_effect=AssertionError('Any estimator fit in synthetic tests is forbidden')):
            prep=a.make_preprocessor(clip=False);prep.fit_transform(self.sample())

    def test_hard_three_fit_budget_without_fitting_a_model(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'THREE_FITS_EXECUTION_CLAIM.json'
            value=create_claim(path,Path(d)/'newrun',['SYNTHETIC_NO_MODEL_FIT'])
            for i,fold in enumerate(a.FOLDS,1):self.assertEqual(reserve_fit_attempt(path,value,fold),i)
            with self.assertRaises(ValueError):reserve_fit_attempt(path,value,'fourth_forbidden')
            self.assertEqual(json.loads(path.read_text())['fit_attempts'],3)

    def test_four_quarter_boundary_and_original_fold_counts(self):
        protocol=json.loads((a.HERE/'REF/part5_protocol_freeze.json').read_text())
        self.assertEqual([x['id'] for x in protocol['validation']['folds']],a.FOLDS)
        for f in protocol['validation']['folds']:
            start=pd.Timestamp(f['validation_start']);last=pd.Timestamp(f['train_end'])
            self.assertEqual(start.to_period('Q').ordinal-last.to_period('Q').ordinal-1,4)
            self.assertLess(last+pd.offsets.QuarterEnd(4),start)
        self.assertEqual(sum(a.FOLD_EXPECTED[x]['valid'] for x in a.FOLDS),304598)

if __name__=='__main__':unittest.main(verbosity=2)
