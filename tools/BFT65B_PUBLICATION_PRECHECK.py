#!/usr/bin/env python3
"""Read-only GitHub publication preflight for a BFT65B source folder or ZIP.

Exit nonzero if candidate appears to contain raw/fitted binary data, local-user
absolute paths, or possible secrets. This does not establish that a repo is
public, that a full data pipeline can run from scratch, or that results are right.
"""
from __future__ import annotations
import argparse, os, zipfile, re, json, sys, pathlib, collections
from pathlib import Path

BLOCKED_EXTS={'.parquet','.arrow','.feather','.npz','.npy','.joblib','.pkl','.pickle','.sqlite','.db','.gz'}
LOCAL=re.compile(rb'(?i)(?:[A-Z]:[\\/]+users[\\/]+(?:admin|[^\\/\s,:\"\'{}]+)[\\/]|/(?:users)/[^/\s]+/|/(?:home)/[^/\s]+/)')
POSSIBLE_SECRET=re.compile(rb'(?i)(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{24,}|AKIA[0-9A-Z]{16})')
LIMIT=20*1024*1024

def from_zip(path):
 with zipfile.ZipFile(path) as z:
  for ent in z.infolist():
   if ent.is_dir():continue
   yield ent.filename,z.read(ent) if ent.file_size <= LIMIT else None

def from_dir(path):
 for f in sorted(path.rglob('*')):
  if not f.is_file() or '.git' in f.parts:continue
  yield str(f.relative_to(path)),f.read_bytes() if f.stat().st_size <= LIMIT else None

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('input',type=Path,help='repo root directory or source ZIP')
 ap.add_argument('--json',type=Path,help='optional JSON report path OUTSIDE source folder')
 x=ap.parse_args()
 assert x.input.exists(), 'Input must exist'
 files=list(from_zip(x.input) if x.input.is_file() else from_dir(x.input))
 issues=[]; large=[]
 for name,data in files:
  n=Path(name)
  if n.suffix.lower() in BLOCKED_EXTS:issues.append({'file':name,'flag':'BINARY_DATA_OR_FITTED_ARTIFACT'})
  if data is None:
   large.append(name);continue
  if b'\x00' in data[:4096]:continue
  if LOCAL.search(data):issues.append({'file':name,'flag':'EMBEDDED_ABSOLUTE_LOCAL_USER_PATH'})
  if POSSIBLE_SECRET.search(data):issues.append({'file':name,'flag':'POSSIBLE_CREDENTIAL__DO_NOT_PRINT'} )
  if re.search(rb'(?i)C:[\\/]+Users[\\/]+admin',data):
   # retained for simple detection even when path JSON-escaped, without showing it
   if not any(v['file']==name and v['flag']=='EMBEDDED_ABSOLUTE_LOCAL_USER_PATH' for v in issues):
    issues.append({'file':name,'flag':'EMBEDDED_ABSOLUTE_LOCAL_USER_PATH'})
 report={'candidate':str(x.input),'files_scanned':len(files),'files_over_text_scan_limit':len(large),
         'flags_by_type':dict(collections.Counter(k['flag'] for k in issues)),
         'issues':issues,
         'interpretation':'Read-only candidate checks; outputs are not publication clearance, hash verification or E2E rerun'}
 print(json.dumps({k:v for k,v in report.items() if k!='issues'},indent=2))
 for v in issues[:30]: print(f"{v['flag']}: {v['file']}")
 if len(issues)>30: print(f'... {len(issues)-30} additional flags (use --json for full list).')
 if x.json:x.json.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
 return 0 if not issues else 3
if __name__=='__main__':sys.exit(main())
