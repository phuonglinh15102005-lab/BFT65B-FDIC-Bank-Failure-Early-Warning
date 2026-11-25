#!/usr/bin/env python3
"""Rehash only shipped post-lock aggregate CSV files (no Parquet, models or scoring)."""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
issues=[]
checks=0
for e,manifest_file,key in [('E11','E11_MANIFEST.json','outputs_sha256'),('E12','E12_MANIFEST.json','output_sha256')]:
    base=root/'supplementary_diagnostics'/e/'verified_aggregate_results'/'outputs'
    manifest=json.loads((base/manifest_file).read_text(encoding='utf8'))
    for name,expected in manifest[key].items():
        path=base/name
        observed=hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        checks+=1
        if observed!=expected:issues.append(f'{e}/{name}: expected {expected}, observed {observed}')
print(json.dumps({'status':'PASS_AGGREGATE_HASHES' if not issues else 'FAIL','files_checked':checks,'issues':issues,
'interpretation':'This does not independently rerun model refits on original FDIC Parquet.'},indent=2))
sys.exit(1 if issues else 0)
