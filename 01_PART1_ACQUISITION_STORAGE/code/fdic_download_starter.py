"""
BFT65B Final Report - Starter script: download FDIC BankFind data via the public API.

What it does
------------
1. /financials   : quarterly Call Report panel, one Parquet file per quarter
                   (resumable: quarters already downloaded and complete are skipped).
2. /failures     : list of failed banks (with COST to the deposit insurance fund).
3. /institutions : static bank information (state, charter class, why reporting ended).
4. Completeness check: rows per quarter == API total, no duplicate (CERT, REPDTE).

No account or API key is needed. Docs: https://api.fdic.gov/banks/docs/

Usage
-----
    pip install requests pandas pyarrow
    # quick test: 4 quarters (~20k rows, ~2-3 minutes)
    python fdic_download_starter.py --start 2023-03-31 --end 2023-12-31
    # full panel, course convention 1984Q1 -> 2026Q2 (~1.68M rows, roughly 1 hour)
    python fdic_download_starter.py

The script is a STARTING POINT. You are expected to understand it, adapt the field
list to your own design, and document your choices in the report.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd
from acquisition_validation import (atomic_json, atomic_parquet, sha256,
    frame_issues, manifest_issues, saved_table_issues)


BASE = "https://api.fdic.gov/banks"
PAGE_SIZE = 10_000  # maximum rows the API returns per call

# Core field set required by the exam: 3 keys + 30 Call Report fields
# (amounts in thousands of USD; ratios in %).
# Look up every code in the field dictionary before using it:
# https://api.fdic.gov/banks/docs/risview_properties.yaml
FIN_FIELDS = [
    "CERT", "REPDTE", "STNAME",
    "ASSET", "DEP", "DEPDOM", "EQ", "BRO", "CHBAL", "SC",          # balance sheet, liquidity
    "LNLSGR", "LNLSNET", "LNRE", "LNCI", "LNCON", "LNATRES",        # loans, reserves
    "NCLNLS", "P3ASSET", "P9ASSET", "NAASSET", "NTLNLS", "ORE",     # asset quality
    "NETINC", "INTINC", "EINTEXP", "NONII", "NONIX", "ELNATR",      # earnings
    "ROA", "ROE", "NIMY",                                           # earnings ratios
    "RBC1AAJ", "RBCRWAJ",                                           # capital ratios
]
FAIL_FIELDS = ["CERT", "NAME", "CITYST", "FAILDATE", "FAILYR", "COST", "QBFASSET", "QBFDEP", "RESTYPE"]
INST_FIELDS = ["CERT", "NAME", "STNAME", "BKCLASS", "ACTIVE", "ESTYMD", "ENDEFYMD", "CHANGEC1", "INSDATE"]


# ----------------------------------------------------------------------------
# HTTP helper: polite, with retry and exponential back-off
# ----------------------------------------------------------------------------
SESSION = None


def get_session():
    global SESSION
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError('Acquisition requires requests; no package was installed by the repair') from exc
    if SESSION is None:
        SESSION = requests.Session()
        SESSION.headers.update({"User-Agent": "BFT65B-course-starter/1.0"})
    return SESSION


def get_json(endpoint: str, params: dict, max_retries: int = 6, pause: float = 1.0) -> dict:
    """GET {BASE}/{endpoint} and return the decoded JSON, retrying on errors."""
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError('Network acquisition requires requests; CLI/help/local checks do not') from exc
    session = get_session()
    url = f"{BASE}/{endpoint}"
    for attempt in range(1, max_retries + 1):
        try:
            r = session.get(url, params=params, timeout=180)
            if r.status_code == 200:
                time.sleep(pause)  # be polite between calls
                return r.json()
            print(f"    HTTP {r.status_code} (attempt {attempt}) - retrying")
        except requests.RequestException as exc:
            print(f"    {type(exc).__name__} (attempt {attempt}) - retrying")
        time.sleep(min(60, 2 ** attempt))  # 2, 4, 8, ... seconds
    raise RuntimeError(f"Giving up on {url} with {params}")


def fetch_all(endpoint: str, fields: list[str], filters: str | None = None,
              sort_by: str = "CERT") -> tuple[pd.DataFrame, int]:
    """Page through an endpoint with limit/offset. Returns (DataFrame, total reported by API)."""
    rows, offset, total = [], 0, None
    first_total = None
    while True:
        params = {
            "fields": ",".join(fields),
            "limit": PAGE_SIZE,
            "offset": offset,
            "sort_by": sort_by,
            "sort_order": "ASC",
            "format": "json",
        }
        if filters:
            params["filters"] = filters
        js = get_json(endpoint, params)
        total = js["meta"]["total"]
        if isinstance(total, bool) or not isinstance(total, int) or total < 0:
            raise RuntimeError('Invalid FDIC API total')
        if first_total is None:
            first_total = total
        elif total != first_total:
            raise RuntimeError('FDIC API total changed during pagination; use a new snapshot')
        page = [rec["data"] for rec in js["data"]]
        if not page and offset < total:
            raise RuntimeError('Empty API page before saved total was reached')
        if offset + len(page) > total:
            raise RuntimeError('API page exceeds declared total')
        rows.extend(page)
        offset += len(page)
        if not page or offset >= total:
            break
    if len(rows) != total:
        raise RuntimeError('Incomplete paginated response')
    df = pd.DataFrame(rows)
    return df.drop(columns=["ID"], errors="ignore"), total


# ----------------------------------------------------------------------------
# Quarter helpers
# ----------------------------------------------------------------------------
def quarter_ends(start: date, end: date) -> list[str]:
    """All quarter-end dates (YYYYMMDD) between start and end, inclusive."""
    ends = []
    for y in range(start.year, end.year + 1):
        for m, d in ((3, 31), (6, 30), (9, 30), (12, 31)):
            q = date(y, m, d)
            if start <= q <= end:
                ends.append(q.strftime("%Y%m%d"))
    return ends


def normalize_repdte(value) -> date:
    """Parse API YYYYMMDD or ISO dates explicitly; numeric values are not epochs."""
    if isinstance(value, bool):
        raise ValueError('REPDTE must be YYYYMMDD or an ISO quarter-end date')
    if isinstance(value, int):
        text = str(value)
    elif isinstance(value, float) and value.is_integer():
        text = str(int(value))
    elif isinstance(value, str):
        text = value.strip()
    else:
        raise ValueError('REPDTE must be an integer YYYYMMDD or ISO date string')
    if len(text) == 8 and text.isascii() and text.isdecimal():
        parsed = date(int(text[:4]), int(text[4:6]), int(text[6:]))
    elif len(text) == 10 and text[4] == '-' and text[7] == '-':
        parsed = date.fromisoformat(text)
    else:
        raise ValueError('REPDTE must use YYYYMMDD or YYYY-MM-DD format')
    if (parsed.month, parsed.day) not in {(3, 31), (6, 30), (9, 30), (12, 31)}:
        raise ValueError('REPDTE is not a calendar quarter-end: ' + parsed.isoformat())
    return parsed


def latest_repdte() -> str:
    js = get_json("financials", {"fields": "REPDTE", "sort_by": "REPDTE",
                                 "sort_order": "DESC", "limit": 1, "format": "json"})
    return normalize_repdte(js["data"][0]["data"]["REPDTE"]).isoformat()


# ----------------------------------------------------------------------------
# Downloads
# ----------------------------------------------------------------------------
def download_financials(out: Path, quarters: list[str]) -> None:
    fin_dir = out / "financials"
    fin_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest_financials.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for i, q in enumerate(quarters, 1):
        target = fin_dir / f"REPDTE={q}.parquet"
        if target.exists():
            problems, _ = saved_table_issues(target, manifest.get(q), 'financials', q)
            if problems:
                raise RuntimeError('Existing snapshot not trusted; do not overwrite it: '+ '; '.join(problems))
            print(f"[{i}/{len(quarters)}] {q}: saved counts, keys and digest verified; skipped")
            continue
        df, total = fetch_all("financials", FIN_FIELDS, filters=f"REPDTE:{q}")
        if df.empty:
            raise RuntimeError(f'Required quarter {q} returned no observations')
        problems = frame_issues(df, 'financials', q)
        if len(df) != total: problems.append('Financial rows != API total')
        if problems: raise RuntimeError('; '.join(problems))
        atomic_parquet(df, target)
        manifest[q] = {"rows": len(df), "api_total": total, "complete": True,
                       "sha256": sha256(target), "bytes":target.stat().st_size}
        atomic_json(manifest_path, manifest)
        print(f"[{i}/{len(quarters)}] {q}: {len(df):,} rows, recorded API total {total:,}")


def download_small_tables(out: Path) -> None:
    manifest_path = out/'manifest_small_tables.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {'tables':{}}
    tables = manifest['tables']
    for name, fields, sort_by in (("failures", FAIL_FIELDS, "FAILDATE"),
                                  ("institutions", INST_FIELDS, "CERT")):
        target = out/f'{name}.parquet'
        if target.exists():
            problems, _ = saved_table_issues(target, tables.get(name), name)
            if problems:
                raise RuntimeError('Existing small-table snapshot not trusted; do not overwrite it: '+ '; '.join(problems))
            print(name+': saved API total, keys and digest verified; skipped')
            continue
        df, total = fetch_all(name, fields, sort_by=sort_by)
        problems = frame_issues(df, name)
        if len(df) != total: problems.append(name+': rows != API total')
        if problems: raise RuntimeError('; '.join(problems))
        atomic_parquet(df, target)
        tables[name] = {'rows':len(df),'api_total':total,'complete':True,
                        'sha256':sha256(target),'bytes':target.stat().st_size}
        atomic_json(manifest_path, manifest)
        print(f'{name}: {len(df):,} rows, recorded API total {total:,}')


def check(out: Path, requested_quarters: list[str] | None = None) -> bool:
    expected = requested_quarters or quarter_ends(date(1984,3,31),date(2026,6,30))
    manifest = json.loads((out/'manifest_financials.json').read_text())
    problems = manifest_issues(manifest, expected)
    for q in expected:
        issues, _ = saved_table_issues(out/'financials'/f'REPDTE={q}.parquet',
                                      manifest.get(q),'financials',q)
        problems += issues
    actual = {p.name for p in (out/'financials').glob('*.parquet')}
    problems += ['Unexpected Financials file: '+name for name in
                 sorted(actual-{f'REPDTE={q}.parquet' for q in expected})]
    small = json.loads((out/'manifest_small_tables.json').read_text())['tables']
    for name in ('failures','institutions'):
        issues, _ = saved_table_issues(out/f'{name}.parquet',small.get(name),name)
        problems += issues
    for issue in problems: print(issue)
    print('Local saved-total/key/digest validation:', 'FAIL' if problems else 'PASS')
    print('No historical release-vintage claim is made.')
    return not problems


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", default="1984-03-31", help="first quarter-end, YYYY-MM-DD")
    ap.add_argument("--end", default="2026-06-30",
                    help="last quarter-end, YYYY-MM-DD (course convention: 2026-06-30; 'latest' = newest available)")
    ap.add_argument("--out", default="data_raw/fdic", help="output folder (do NOT commit it to Git)")
    args = ap.parse_args()

    try:
        end = args.end if args.end != "latest" else latest_repdte()
        start_date, end_date = date.fromisoformat(args.start), date.fromisoformat(end)
        if start_date > end_date:
            raise ValueError('--start must not be later than --end')
        quarters = quarter_ends(start_date, end_date)
        if not quarters:
            raise ValueError('The requested interval contains no calendar quarter-end')
    except ValueError as exc:
        ap.error(str(exc))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {len(quarters)} quarters: {quarters[0]} -> {quarters[-1]} into {out.resolve()}\n")

    download_financials(out, quarters)
    print()
    download_small_tables(out)
    ok = check(out, quarters)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
