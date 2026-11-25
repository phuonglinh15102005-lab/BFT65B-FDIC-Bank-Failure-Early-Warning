from pathlib import Path
import hashlib
import json

folder=Path(__file__).resolve().parents[1]
config=folder/'part5_protocol_freeze.json'
expected=(folder/'part5_protocol_freeze.sha256').read_text().split()[0]
actual=hashlib.sha256(config.read_bytes()).hexdigest()
if expected!=actual:
    raise SystemExit('FAIL: protocol file differs from the frozen SHA-256 digest')
rule=json.loads(config.read_text(encoding='utf-8'))
assert rule['stage']=='FROZEN_PRESELECTION_RULES_BEFORE_ANY_MODEL_COMPARISON'
assert len(rule['validation']['folds'])==3
assert len(rule['feature_policy']['tier1_features'])==15
assert rule['test_policy']['observed_test_results_present_in_protocol'] is False
print('PASS protocol byte SHA-256',actual)
