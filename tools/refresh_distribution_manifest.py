#!/usr/bin/env python3
"""Regenerate distribution manifest after an intentional documentation update; never changes scientific pins."""
from pathlib import Path
import hashlib,csv
R=Path(__file__).resolve().parents[1]
rows=[]
for p in sorted(R.rglob('*')):
    if not p.is_file() or '.git' in p.relative_to(R).parts or '__pycache__' in p.parts or p.suffix=='.pyc' or p.name=='FILE_MANIFEST_SHA256.csv':continue
    rows.append((p.relative_to(R).as_posix(),p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest()))
with (R/'FILE_MANIFEST_SHA256.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(['relative_path','bytes','sha256']);w.writerows(rows)
print('Manifest entries:',len(rows))
