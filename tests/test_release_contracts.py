"""Release CLI/safety contracts only: stdlib, no scientific imports or execution."""
from pathlib import Path
import copy
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from workflow import common
from workflow.compare import scalar_equal
from workflow.engine import environment_matches
from workflow.policy import ALLOWED, CLOSED, FORBIDDEN, Guard, permitted_stage, validate_arguments


class ConfigurationContracts(unittest.TestCase):
    def test_contract_suite_does_not_import_scientific_stack(self):
        # Host sitecustomize may preload packages. Test workflow-caused imports,
        # including cached imports, in a fresh normally-started child instead.
        program = '''
import builtins, importlib, json, sys
scientific = {'numpy','pandas','polars','pyarrow','sklearn','joblib','pyspark'}
before = set(sys.modules)
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in scientific:
        raise AssertionError('workflow attempted scientific import: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
for name in ['workflow.common','workflow.compare','workflow.engine','workflow.policy',
             'workflow.continuous','workflow.continuous_contract',
             'workflow.continuous_compare','workflow.continuous_worker','workflow.offline_part2b']:
    importlib.import_module(name)
added = sorted(n for n in set(sys.modules)-before if n.split('.')[0] in scientific)
assert not added, added
print(json.dumps({'new_scientific_modules': added}))
'''
        child = subprocess.run([sys.executable, '-B', '-c', program], cwd=common.ROOT,
                               capture_output=True, text=True)
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertEqual(json.loads(child.stdout)['new_scientific_modules'], [])

    def canonical(self):
        return json.loads((common.ROOT / 'config/default.json').read_text(encoding='utf-8'))

    def read_custom(self, value):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'custom.json'
            path.write_text(json.dumps(value), encoding='utf-8')
            return common.load_config(path)

    def test_explicit_input_path_overrides_are_allowed(self):
        original = self.canonical()
        custom = copy.deepcopy(original)
        for key in custom['inputs']:
            custom['inputs'][key] = '/external/read-only inputs/' + key
        loaded = self.read_custom(custom)
        self.assertEqual(loaded['inputs'], custom['inputs'])
        self.assertEqual(loaded['reference_files'], original['reference_files'])
        self.assertEqual(self.canonical(), original)

    def test_frozen_reference_hash_cannot_be_overridden(self):
        custom = self.canonical()
        key = next(iter(custom['reference_files']))
        custom['reference_files'][key]['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            self.read_custom(custom)

    def test_immutable_stage_cache_release_contracts(self):
        for key, changed in [('release_id', 'different-release'),
                             ('read_only_cache', 'new-network-cache'),
                             ('default_new_replay_stages', ['ablation'])]:
            custom = self.canonical()
            custom[key] = changed
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.read_custom(custom)

    def test_missing_extra_empty_or_nonstring_input_is_rejected(self):
        original = self.canonical()
        name = next(iter(original['inputs']))
        for action in ['missing', 'extra', 'empty', 'none']:
            custom = copy.deepcopy(original)
            if action == 'missing':
                del custom['inputs'][name]
            elif action == 'extra':
                custom['inputs']['unregistered_input'] = 'unexpected'
            elif action == 'empty':
                custom['inputs'][name] = ''
            else:
                custom['inputs'][name] = None
            with self.subTest(action=action), self.assertRaises(ValueError):
                self.read_custom(custom)

    def test_environment_matching_requires_exact_python_and_versions(self):
        expected = {'python': '3.13.9', 'packages': {'numpy': '2.5.4', 'polars': '2.1.0'}}
        correct = {'python': '3.13.9', 'packages': {'numpy': '2.5.4', 'polars': '2.1.0', 'extra': '1'}}
        self.assertTrue(environment_matches(correct, expected))
        for mutation in ['python', 'wrong_version', 'missing_version']:
            bad = copy.deepcopy(correct)
            if mutation == 'python':
                bad['python'] = '3.13.7'
            elif mutation == 'wrong_version':
                bad['packages']['numpy'] = '2.3.3'
            else:
                del bad['packages']['polars']
            with self.subTest(mutation=mutation):
                self.assertFalse(environment_matches(bad, expected))


class StageAndArgumentContracts(unittest.TestCase):
    def test_only_three_data_producers_can_be_dispatched(self):
        self.assertEqual(set(ALLOWED), {'p2-base', 'p2-clean', 'development-features'})
        for stage, source in ALLOWED.items():
            self.assertEqual(permitted_stage(stage), source)
        for stage in CLOSED | FORBIDDEN | {'selected-HGB-refit', 'model-lock', 'spark-registered', 'unknown'}:
            with self.subTest(stage=stage), self.assertRaises(ValueError):
                permitted_stage(stage)

    def test_base_requires_one_explicit_child_output(self):
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory).resolve()
            good = ['--audit-dir', '/external/audit', '--out', str(job / 'artifacts')]
            validate_arguments('p2-base', good, job)
            bad_arguments = [[], ['--out', str(job)], ['--out', str(job.parent / 'outside')],
                             good + ['--out', str(job / 'second')]]
            for bad in bad_arguments:
                with self.subTest(arguments=bad), self.assertRaises(ValueError):
                    validate_arguments('p2-base', bad, job)

    def test_clean_requires_offline_and_readonly_cache_argument(self):
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory).resolve()
            good = ['--out', str(job / 'artifacts'), '--offline', '--cache-dir', '/external/request_cache']
            validate_arguments('p2-clean', good, job)
            for bad in [good[:2], good[:2] + good[3:], good[:3]]:
                with self.subTest(arguments=bad), self.assertRaises(ValueError):
                    validate_arguments('p2-clean', bad, job)

    def test_development_production_only_requires_zero_canary_quarters(self):
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory).resolve()
            base = ['--out-dir', str(job / 'artifacts')]
            good = base + ['--production-only', '--asof-quarters', '0']
            validate_arguments('development-features', good, job)
            for bad in [base, base + ['--asof-quarters', '0'],
                        base + ['--production-only'],
                        base + ['--production-only', '--asof-quarters', '12']]:
                with self.subTest(arguments=bad), self.assertRaises(ValueError):
                    validate_arguments('development-features', bad, job)

    def test_closed_or_fitting_flags_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory).resolve()
            for option in ['--self-test', '--fit', '--refit', '--score', '--download',
                           '--old-dev', '--pandas-oracle-source', '--assistance-events-csv']:
                with self.subTest(option=option), self.assertRaises(ValueError):
                    validate_arguments('p2-base', ['--out', str(job / 'artifacts'), option], job)


class OutputAndGuardContracts(unittest.TestCase):
    def test_output_rejects_repository_overlap_existing_and_source_overlap(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            data = base / 'original'; data.mkdir()
            original = data / 'panel.parquet'
            original.write_bytes(b'SYNTHETIC_PATH_FIXTURE_NOT_PARQUET_DATA')
            valid = base / 'new-result'
            self.assertEqual(common.validate_output(valid, {'source': original}), valid.resolve())
            for bad in [data / 'new-output', data, base]:
                with self.subTest(output=bad), self.assertRaises(ValueError):
                    common.validate_output(bad, {'source': original})
            with self.assertRaises(ValueError):
                common.validate_output(common.ROOT / 'new-output', {})
            valid.mkdir()
            with self.assertRaises(ValueError):
                common.validate_output(valid, {})

    def test_raw_read_and_inside_write_events_allowed_without_actual_io(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve(); out = base / 'out'
            guard = Guard(out)
            guard.hook('open', (str(base / 'original/panel_base.parquet'), 'r', os.O_RDONLY))
            guard.hook('open', (str(out / 'new.parquet'), 'wb', os.O_WRONLY | os.O_CREAT))
            guard.hook('open', (1, 'w', os.O_WRONLY))
            guard.hook('os.mkdir', (str(out / 'new'), 0o755, -1))

    def test_outside_write_create_rename_remove_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve(); out = base / 'out'; guard = Guard(out)
            with self.assertRaises(ValueError):
                guard.hook('open', (str(base / 'original/file'), 'wb', os.O_WRONLY | os.O_CREAT))
            for event, args in [('os.mkdir', (str(base / 'outside'), 0o755, -1)),
                                ('os.remove', (str(base / 'outside'), -1)),
                                ('os.rename', (str(out / 'a'), str(base / 'outside'), -1, -1))]:
                with self.subTest(event=event), self.assertRaises(ValueError):
                    guard.hook(event, args)

    def test_model_and_frozen_test_reads_rejected_without_opening_files(self):
        guard = Guard(Path(tempfile.gettempdir()) / 'release-guard-test')
        for name in ['/external/06_test_locked/scores.csv', '/external/FINAL_TEST_scores.csv.gz',
                     '/external/final_hgb_refit.joblib', '/external/FINAL_MODEL_LOCK.json',
                     '/external/test_primary_binary_v2.parquet', '/external/model.pkl',
                     '/external/model.pickle', r'C:\external\step06b\cohort.parquet']:
            with self.subTest(name=name), self.assertRaises(PermissionError):
                guard.hook('open', (name, 'r', os.O_RDONLY))

    def test_network_process_and_shell_events_are_rejected(self):
        guard = Guard(Path(tempfile.gettempdir()) / 'release-guard-test')
        for event in ['socket.connect', 'socket.bind', 'socket.getaddrinfo', 'subprocess.Popen',
                      'os.system', 'os.posix_spawn']:
            with self.subTest(event=event), self.assertRaises(PermissionError):
                guard.hook(event, ())


class ScalarComparatorContracts(unittest.TestCase):
    def test_null_and_nan_masks_are_distinct(self):
        self.assertTrue(scalar_equal(None, None))
        self.assertTrue(scalar_equal(float('nan'), float('nan')))
        for left, right in [(None, float('nan')), (None, 0.), (float('nan'), 0.), (0., float('nan'))]:
            with self.subTest(left=left, right=right):
                self.assertFalse(scalar_equal(left, right))

    def test_same_infinity_is_equal_opposite_or_finite_is_not(self):
        self.assertTrue(scalar_equal(float('inf'), float('inf')))
        self.assertTrue(scalar_equal(-float('inf'), -float('inf')))
        for left, right in [(1., float('inf')), (float('inf'), 1.),
                            (-float('inf'), float('inf')), (float('inf'), -float('inf'))]:
            for relative in [0., 1e-9, 1.]:
                with self.subTest(left=left, right=right, rtol=relative):
                    self.assertFalse(scalar_equal(left, right, rtol=relative, atol=1.))

    def test_float_tolerance_and_exact_mode(self):
        self.assertTrue(scalar_equal(1.000001, 1., rtol=1e-5))
        self.assertTrue(scalar_equal(0.000001, 0., atol=1e-5))
        self.assertFalse(scalar_equal(1.000001, 1., rtol=0., atol=0.))
        self.assertFalse(scalar_equal(1.1, 1., rtol=1e-4, atol=1e-4))

    def test_integers_are_exact_even_beyond_float_precision(self):
        large = 2 ** 60
        self.assertTrue(scalar_equal(large, large))
        self.assertFalse(scalar_equal(large, large + 1, rtol=1., atol=1.))
        self.assertFalse(scalar_equal(True, 1))
        self.assertFalse(scalar_equal('1', 1))


if __name__ == '__main__':
    unittest.main(verbosity=2)
