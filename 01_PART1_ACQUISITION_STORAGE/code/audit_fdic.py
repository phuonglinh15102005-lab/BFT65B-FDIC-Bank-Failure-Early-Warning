#!/usr/bin/env python3
"""BFT65B audit v2: scope-aware validation and optional schema standardization.

Run in the fdic directory containing financials/, failures.parquet,
institutions.parquet and manifest_financials.json:

    python audit_fdic.py --data-dir . --expected-failures 4117 --expected-institutions 27835 --prepare

Requires polars and pyarrow. Optional: --requirements path/to/requirements.txt.
The expected small-table counts must come from YOUR download log/snapshot.
This script reads input files only. It creates a new timestamped report directory.
It makes no network requests, imputations, feature selection or model fitting.
With --prepare it writes new typed Parquet copies and review tables. Raw files
remain unchanged. All financial rows and all source event rows are preserved.
Legacy events without CERT before the panel start are retained for provenance
and excluded from linkable event tables. Unknown exits remain unresolved.
Prepared data are standardized inputs, not a labelled or model-ready panel.

Output: summary.txt/json, issues.csv, quarters.csv, missingness_by_quarter.csv,
numeric_profile.csv, schema_by_quarter.csv, failure_types.csv, file_checksums.csv,
environment.csv, and optional requirement_versions.csv.
With --prepare: prepared/financials/, prepared/failures_all.parquet,
prepared/failure_events.parquet, prepared/assistance_events.parquet,
prepared/institutions.parquet, and review/*.csv. Financial values remain in
their original units. NaN becomes null, never zero. No rows are deduplicated.
STANDARDIZATION_COMPLETE.json is written only if all structural checks pass.

Sources: instructor-provided fdic_download_starter.py and final_report_bft65b.pdf;
https://api.fdic.gov/banks/docs/ (Financial, Failure and Institution dictionaries);
https://docs.pola.rs/api/python/stable/ ; https://arrow.apache.org/docs/python/ .
AI assistance: initial implementation prepared with ChatGPT, 2026-11-08.
If used in the project, disclose/adapt/validate it and cite it in report and README.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import date, datetime, timezone
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import re
import sys

try:
    import polars as pl
    import pyarrow.parquet as pq
except ImportError as exc:
    raise SystemExit(
        f"Missing audit dependency: {exc}. Activate the project environment, then "
        "install the project's requirements with python -m pip install -r requirements.txt."
    ) from exc


PACKAGE_NAMES = (
    "polars", "pyarrow", "pandas", "numpy", "scipy", "scikit-learn", "pyspark",
    "py4j", "matplotlib", "pyyaml", "psutil", "pytest", "requests", "python-docx",
    "jupyter", "nbconvert", "nbformat", "ipykernel",
)
AUDIT_VERSION = "2.0"
FINANCIAL_NUMERIC = {
    "ASSET", "DEP", "DEPDOM", "EQ", "BRO", "CHBAL", "SC", "LNLSGR", "LNLSNET",
    "LNRE", "LNCI", "LNCON", "LNATRES", "NCLNLS", "P3ASSET", "P9ASSET", "NAASSET",
    "NTLNLS", "ORE", "NETINC", "INTINC", "EINTEXP", "NONII", "NONIX", "ELNATR",
    "ROA", "ROE", "NIMY", "RBC1AAJ", "RBCRWAJ",
}


def typed_financials(frame: pl.DataFrame) -> pl.DataFrame:
    expressions = [cert_expression().alias("CERT"), date_expression(frame, "REPDTE").alias("REPDTE")]
    for name, dtype in frame.schema.items():
        if name in {"CERT", "REPDTE"}:
            continue
        if name == "STNAME":
            expressions.append(pl.col(name).cast(pl.String))
        elif name in FINANCIAL_NUMERIC or dtype.is_numeric():
            expressions.append(pl.col(name).cast(pl.Float64, strict=True).fill_nan(None))
    return frame.with_columns(expressions)


def save_prepared(frame: pl.DataFrame, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(target, compression="zstd")
    if pq.ParquetFile(target).metadata.num_rows != frame.height:
        raise ValueError(f"Prepared row count failed verification: {target}")


def quarter_ends(start: date, end: date) -> list[str]:
    return [
        date(y, m, d).strftime("%Y%m%d")
        for y in range(start.year, end.year + 1)
        for m, d in ((3, 31), (6, 30), (9, 30), (12, 31))
        if start <= date(y, m, d) <= end
    ]


def date_expression(frame: pl.DataFrame, column: str) -> pl.Expr:
    dtype = frame.schema[column]
    if dtype == pl.Date:
        return pl.col(column)
    if dtype.base_type() == pl.Datetime:
        return pl.col(column).dt.date()
    raw = pl.col(column).cast(pl.String).str.strip_chars().str.replace(r"\.0$", "")
    return pl.coalesce([
        raw.str.strptime(pl.Date, fmt, strict=False)
        for fmt in ("%Y%m%d", "%Y-%m-%d", "%m/%d/%Y")
    ])


def cert_expression() -> pl.Expr:
    raw = pl.col("CERT").cast(pl.String).str.strip_chars().str.replace(r"\.0$", "")
    return raw.cast(pl.Int64, strict=False)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_csv(path: Path, records: list[dict], empty_headers: tuple[str, ...] = ("status",)) -> None:
    headers = list(dict.fromkeys(k for row in records for k in row)) or list(empty_headers)
    # utf-8-sig lets Windows Excel open the report without damaging Unicode.
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        writer.writerows(records)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, help="New or empty report directory; default audit_results/<UTC timestamp>.")
    parser.add_argument("--start", default="1984-03-31")
    parser.add_argument("--end", default="2026-06-30")
    parser.add_argument("--expected-failures", type=int, help="Total from your download log; includes all RESTYPE values.")
    parser.add_argument("--expected-institutions", type=int, help="Total from your download log.")
    parser.add_argument("--requirements", type=Path, help="Optional file containing simple package==version pins.")
    parser.add_argument("--prepare", action="store_true", help="Also write typed copies and review extracts under the new report directory.")
    args = parser.parse_args()
    try:
        start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    except ValueError:
        parser.error("Use YYYY-MM-DD for --start and --end.")
    expected = quarter_ends(start, end)
    if not expected:
        parser.error("The requested range contains no quarter-end dates.")
    root = args.data_dir.resolve()
    if not root.is_dir() or not (root / "financials").is_dir():
        parser.error(f"{root} must contain the financials directory. Set --data-dir to the fdic directory.")
    if args.requirements and not args.requirements.is_file():
        parser.error(f"Requirements file not found: {args.requirements}")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    out = (args.out or (Path.cwd() / "audit_results" / timestamp)).resolve()
    if out == root or out == root / "financials" or (root / "financials") in out.parents:
        parser.error("Choose a report directory outside financials/ and different from the input directory.")
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        parser.error(f"Report directory is not empty: {out}. Choose a new directory.")
    out.mkdir(parents=True, exist_ok=True)

    issues: list[dict] = []
    quarters: list[dict] = []
    missingness: list[dict] = []
    numeric: list[dict] = []
    schemas: list[dict] = []
    checksums: list[dict] = []
    key_frames: list[pl.DataFrame] = []
    financial_columns: dict[str, set[str]] = {}
    rows_per_quarter: dict[str, int] = {}
    type_sets: dict[str, set[str]] = {}
    prepared_rows = 0
    prepared_schema = None

    def issue(severity: str, rule: str, table: str, detail: str, count: int | None = None) -> None:
        issues.append({"severity": severity, "rule": rule, "table": table, "count": count, "detail": detail})

    def remember_file(path: Path) -> None:
        checksums.append({"file": str(path.relative_to(root)), "bytes": path.stat().st_size, "sha256": sha256(path)})

    def profile(frame: pl.DataFrame, table: str, quarter: str = "") -> None:
        for name, dtype in frame.schema.items():
            values = frame[name]
            nulls = values.null_count()
            nans = int(values.is_nan().sum()) if dtype.is_float() else 0
            missingness.append({
                "table": table, "quarter": quarter, "column": name, "dtype": str(dtype),
                "rows": frame.height, "column_absent": False, "nulls": nulls, "nans": nans,
                "missing": nulls + nans,
                "missing_pct": round(100 * (nulls + nans) / frame.height, 4) if frame.height else None,
            })
            schemas.append({"table": table, "quarter": quarter, "column": name, "dtype": str(dtype)})
            if table == "financials":
                type_sets.setdefault(name, set()).add(str(dtype))
            if dtype.is_numeric() and name not in {"CERT", "REPDTE", "ID"}:
                numbers = values.cast(pl.Float64, strict=False)
                finite = numbers.filter(numbers.is_finite())
                infinite = int(numbers.is_infinite().sum())
                numeric.append({
                    "table": table, "quarter": quarter, "column": name,
                    "finite_count": len(finite), "infinite_count": infinite,
                    "zero_count": int((finite == 0).sum()), "negative_count": int((finite < 0).sum()),
                    "min": finite.min(), "median": finite.median(), "max": finite.max(),
                })
                if infinite:
                    issue("REVIEW", "infinite_numeric_value", table, f"{quarter} {name}: review before modelling", infinite)
                if name == "ASSET":
                    nonpositive = int((finite <= 0).sum())
                    if nonpositive:
                        issue("REVIEW", "nonpositive_assets", table, f"{quarter}: inspect source and denominator policy", nonpositive)

    manifest_path = root / "manifest_financials.json"
    manifest: dict = {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if not isinstance(manifest, dict):
            raise ValueError("Manifest must be an object indexed by quarter.")
        remember_file(manifest_path)
    except (OSError, ValueError) as exc:
        issue("ERROR", "manifest_unreadable", "financials", str(exc))
        manifest = {}

    expected_set = set(expected)
    paths = sorted((root / "financials").glob("*.parquet"))
    quarter_files: dict[str, Path] = {}
    for path in paths:
        match = re.fullmatch(r"REPDTE=(\d{8})\.parquet", path.name)
        if not match:
            issue("ERROR", "unexpected_parquet_filename", "financials", path.name)
        else:
            quarter_files[match.group(1)] = path
    for rule, values in (
        ("missing_quarter_files", expected_set - quarter_files.keys()),
        ("unexpected_quarter_files", quarter_files.keys() - expected_set),
        ("missing_manifest_quarters", expected_set - manifest.keys()),
        ("unexpected_manifest_quarters", manifest.keys() - expected_set),
    ):
        if values:
            issue("ERROR", rule, "financials", ", ".join(sorted(values)), len(values))

    for index, q in enumerate(expected, 1):
        path = quarter_files.get(q)
        if path is None:
            continue
        try:
            file_meta = pq.ParquetFile(path).metadata
            frame = pl.read_parquet(path)
            remember_file(path)
        except Exception as exc:
            issue("ERROR", "quarter_file_unreadable", "financials", f"{q}: {type(exc).__name__}: {exc}")
            continue
        n = frame.height
        rows_per_quarter[q] = n
        financial_columns[q] = set(frame.columns)
        profile(frame, "financials", q)
        record = manifest.get(q, {})
        if not isinstance(record, dict):
            issue("ERROR", "manifest_entry_invalid", "financials", q)
            record = {}
        m_rows, api_total = record.get("rows"), record.get("api_total")
        count_match = n == m_rows == api_total == file_meta.num_rows
        if not count_match or record.get("complete") is not True or n == 0:
            issue("ERROR", "quarter_count_or_complete_mismatch", "financials",
                  f"{q}: disk={n}, parquet_metadata={file_meta.num_rows}, manifest={m_rows}, API={api_total}, complete={record.get('complete')}")
        invalid_keys = wrong_dates = duplicate_extra = None
        if {"CERT", "REPDTE"}.issubset(frame.columns):
            keys = frame.select(cert_expression().alias("CERT"), date_expression(frame, "REPDTE").alias("REPDTE"))
            invalid_keys = keys.filter(pl.col("CERT").is_null() | (pl.col("CERT") <= 0) | pl.col("REPDTE").is_null()).height
            target = datetime.strptime(q, "%Y%m%d").date()
            wrong_dates = keys.filter(pl.col("REPDTE").is_not_null() & (pl.col("REPDTE") != target)).height
            valid_keys = keys.filter(pl.col("CERT").is_not_null() & (pl.col("CERT") > 0) & pl.col("REPDTE").is_not_null())
            duplicate_extra = valid_keys.height - valid_keys.unique().height
            key_frames.append(valid_keys)
            for rule, count in (("invalid_bank_quarter_keys", invalid_keys), ("report_date_wrong_file", wrong_dates), ("duplicate_keys_in_quarter", duplicate_extra)):
                if count:
                    issue("ERROR", rule, "financials", q, count)
        else:
            issue("ERROR", "missing_key_columns", "financials", f"{q}: {sorted({'CERT', 'REPDTE'} - set(frame.columns))}")
        if args.prepare and {"CERT", "REPDTE"}.issubset(frame.columns):
            try:
                typed = typed_financials(frame)
                signature = sorted((name, str(dtype)) for name, dtype in typed.schema.items())
                if prepared_schema is None:
                    prepared_schema = signature
                elif signature != prepared_schema:
                    issue("ERROR", "prepared_schema_mismatch", "financials", q)
                save_prepared(typed, out / "prepared" / "financials" / path.name)
                prepared_rows += typed.height
            except Exception as exc:
                issue("ERROR", "financial_standardization_failed", "financials", f"{q}: {type(exc).__name__}: {exc}")
        quarters.append({
            "quarter": q, "rows": n, "manifest_rows": m_rows, "manifest_api_total": api_total,
            "manifest_complete": record.get("complete"), "counts_match": count_match,
            "invalid_keys": invalid_keys, "wrong_report_dates": wrong_dates,
            "duplicate_extra_rows": duplicate_extra, "columns": frame.width, "bytes": path.stat().st_size,
        })
        if index % 20 == 0 or index == len(expected):
            print(f"Read {index}/{len(expected)} quarters", flush=True)

    all_columns = set().union(*financial_columns.values()) if financial_columns else set()
    for q, columns in financial_columns.items():
        absent = all_columns - columns
        if absent:
            issue("REVIEW", "columns_absent_in_quarter", "financials", f"{q}: {', '.join(sorted(absent))}", len(absent))
        for column in sorted(absent):
            n = rows_per_quarter[q]
            missingness.append({"table": "financials", "quarter": q, "column": column, "dtype": "ABSENT",
                                "rows": n, "column_absent": True, "nulls": None, "nans": None,
                                "missing": n, "missing_pct": 100.0 if n else None})
    for column, types in sorted(type_sets.items()):
        if len(types) > 1:
            issue("REVIEW", "schema_type_varies", "financials", f"{column}: {', '.join(sorted(types))}", len(types))

    panel_keys = pl.concat(key_frames) if key_frames else pl.DataFrame(schema={"CERT": pl.Int64, "REPDTE": pl.Date})
    panel_certs = set(panel_keys["CERT"].unique().to_list())
    duplicate_total = panel_keys.height - panel_keys.unique().height
    if duplicate_total:
        issue("ERROR", "duplicate_keys_entire_panel", "financials", "Extra valid-key rows beyond the first occurrence", duplicate_total)

    small: dict[str, pl.DataFrame] = {}
    small_summaries: dict[str, dict] = {}
    for name, expected_total in (("failures", args.expected_failures), ("institutions", args.expected_institutions)):
        path = root / f"{name}.parquet"
        try:
            frame = pl.read_parquet(path)
            remember_file(path)
            small[name] = frame
            profile(frame, name)
            small_summaries[name] = {"rows": frame.height, "expected_from_user_download_log": expected_total,
                                   "count_matches_provided_log": frame.height == expected_total if expected_total is not None else None}
            if not frame.height:
                issue("ERROR", "empty_table", name, path.name)
            if expected_total is not None and frame.height != expected_total:
                issue("ERROR", "small_table_count_mismatch", name, f"disk={frame.height}, provided_log={expected_total}")
            if expected_total is None:
                issue("REVIEW", "small_table_total_not_supplied", name, "No expected API total from the original download log was supplied.")
            required = {"CERT", "FAILDATE", "RESTYPE"} if name == "failures" else {"CERT", "ACTIVE", "ENDEFYMD", "CHANGEC1"}
            for column in sorted(required - set(frame.columns)):
                issue("ERROR", "missing_required_column", name, column)
            if "CERT" in frame.columns:
                certs = frame.select(cert_expression().alias("CERT"))["CERT"]
                invalid = int((certs.is_null() | (certs <= 0)).sum())
                if invalid:
                    legacy_count = 0
                    if name == "failures" and "FAILDATE" in frame.columns:
                        key_dates = frame.select(cert_expression().alias("CERT"), date_expression(frame, "FAILDATE").alias("FAILDATE"))
                        legacy = key_dates.filter((pl.col("CERT").is_null() | (pl.col("CERT") <= 0)) & (pl.col("FAILDATE") < start))
                        legacy_count = legacy.height
                        if legacy_count:
                            issue("REVIEW", "legacy_unlinkable_event_before_scope", name,
                                  f"{legacy['FAILDATE'].min()} to {legacy['FAILDATE'].max()}: retain raw records; exclude from CERT joins for this panel", legacy_count)
                        small_summaries[name]["legacy_unlinkable_events_before_scope"] = legacy_count
                    if invalid > legacy_count:
                        issue("ERROR", "invalid_cert", name, "Unusable CERT within/after scope or with unknown event date", invalid - legacy_count)
                    small_summaries[name]["all_invalid_CERT"] = invalid
                valid = certs.filter(certs.is_not_null() & (certs > 0))
                small_summaries[name]["distinct_valid_CERT"] = valid.n_unique()
                if name == "institutions":
                    duplicates = len(valid) - valid.n_unique()
                    if duplicates:
                        issue("ERROR", "duplicate_institution_cert", name, "Review before joining to panel", duplicates)
                    unmatched = panel_certs - set(valid.to_list())
                    small_summaries[name]["panel_CERT_not_in_institutions"] = len(unmatched)
                    if unmatched:
                        issue("REVIEW", "panel_cert_without_institution", name, f"First 20 examples: {sorted(unmatched)[:20]}", len(unmatched))
        except Exception as exc:
            issue("ERROR", "small_table_unreadable_or_invalid", name, f"{type(exc).__name__}: {exc}")

    failure_types: list[dict] = []
    if "failures" in small and {"CERT", "FAILDATE", "RESTYPE"}.issubset(small["failures"].columns):
        frame = small["failures"]
        events = frame.select(cert_expression().alias("CERT"), date_expression(frame, "FAILDATE").alias("FAILDATE"),
                              pl.col("RESTYPE").cast(pl.String).str.strip_chars().str.to_uppercase().fill_null("(MISSING)").alias("RESTYPE"))
        failure_types = events.group_by("RESTYPE").len().rename({"len": "rows"}).sort("RESTYPE").to_dicts()
        invalid_dates = events["FAILDATE"].null_count()
        if invalid_dates:
            issue("ERROR", "invalid_failure_date", "failures", "Missing or unparseable FAILDATE", invalid_dates)
        unknown = events.filter(~pl.col("RESTYPE").is_in(["FAILURE", "ASSISTANCE"]))
        if unknown.height:
            issue("REVIEW", "unknown_resolution_type", "failures", "Review failure_types.csv before defining outcomes", unknown.height)
        usable_mask = pl.col("CERT").is_not_null() & (pl.col("CERT") > 0) & pl.col("FAILDATE").is_not_null()
        usable_events = events.filter(usable_mask)
        duplicate_events = usable_events.height - usable_events.unique().height
        unusable_events = events.filter(~usable_mask.fill_null(False))
        unusable_collisions = unusable_events.height - unusable_events.unique().height
        if duplicate_events:
            issue("REVIEW", "duplicate_valid_event_keys", "failures", "Same valid CERT, FAILDATE, RESTYPE; investigate before labelling", duplicate_events)
        if unusable_collisions:
            issue("REVIEW", "unlinked_event_key_collisions", "failures",
                  "Unusable identifiers share date/type. These are not evidence of duplicate real events; preserve every source row", unusable_collisions)
        failure_rows = events.filter(pl.col("RESTYPE") == "FAILURE")
        small_summaries["failures"].update({"resolution_type_counts": failure_types, "invalid_FAILDATE": invalid_dates,
                                           "failure_rows": failure_rows.height,
                                           "linkable_failure_event_rows": usable_events.filter(pl.col("RESTYPE") == "FAILURE").height,
                                           "duplicate_valid_event_extra_rows": duplicate_events,
                                           "unlinked_event_key_collisions": unusable_collisions})
        recent_failures = failure_rows.filter(pl.col("FAILDATE").is_between(start, end, closed="both"))
        missing_certs = set(recent_failures["CERT"].drop_nulls().to_list()) - panel_certs
        small_summaries["failures"]["failure_CERT_in_date_scope_without_financials"] = len(missing_certs)
        if missing_certs:
            issue("REVIEW", "failure_without_financials_in_scope", "failures", f"First 20 examples: {sorted(missing_certs)[:20]}; investigate coverage/history", len(missing_certs))

    if "institutions" in small:
        frame = small["institutions"]
        if {"ACTIVE", "ENDEFYMD"}.issubset(frame.columns):
            state = frame.select(pl.col("ACTIVE").cast(pl.Int64, strict=False).alias("ACTIVE"), date_expression(frame, "ENDEFYMD").alias("END_DATE"))
            inactive = state.filter(pl.col("ACTIVE") == 0)
            missing_end = inactive["END_DATE"].null_count()
            small_summaries["institutions"]["inactive_rows"] = inactive.height
            small_summaries["institutions"]["inactive_missing_or_invalid_end_date"] = missing_end
            if missing_end:
                issue("REVIEW", "inactive_without_end_date", "institutions", "Investigate exits; do not equate inactive with failed", missing_end)

    # Separate audit-only metadata from financial inputs to avoid accidental use
    # of current status, exit dates or failure information as historical features.
    if args.prepare:
        review_dir = out / "review"
        review_dir.mkdir(exist_ok=True)
        try:
            frame = small["failures"]
            full_events = frame.with_row_index("SOURCE_ROW", offset=1).with_columns(
                pl.col("CERT").cast(pl.String).alias("CERT_RAW"),
                cert_expression().alias("CERT"), date_expression(frame, "FAILDATE").alias("FAILDATE"),
                pl.col("RESTYPE").cast(pl.String).str.strip_chars().str.to_uppercase().alias("RESTYPE"),
            )
            for column in ("COST", "QBFASSET", "QBFDEP"):
                if column in full_events.columns:
                    full_events = full_events.with_columns(pl.col(column).cast(pl.Float64, strict=True).fill_nan(None))
            linkable = (pl.col("CERT").is_not_null() & (pl.col("CERT") > 0) & pl.col("FAILDATE").is_not_null()).fill_null(False)
            full_events = full_events.with_columns(linkable.alias("LINKABLE_BY_CERT_DATE"))
            linked = full_events.filter(pl.col("LINKABLE_BY_CERT_DATE"))
            unlinked = full_events.filter(~pl.col("LINKABLE_BY_CERT_DATE"))
            failures = linked.filter(pl.col("RESTYPE") == "FAILURE")
            assistance = linked.filter(pl.col("RESTYPE") == "ASSISTANCE")
            save_prepared(full_events, out / "prepared" / "failures_all.parquet")
            save_prepared(failures, out / "prepared" / "failure_events.parquet")
            save_prepared(assistance, out / "prepared" / "assistance_events.parquet")
            unlinked.write_csv(review_dir / "unlinked_events.csv")
            duplicate_rows = linked.filter(pl.struct("CERT", "FAILDATE", "RESTYPE").is_duplicated())
            duplicate_rows.write_csv(review_dir / "duplicate_valid_events.csv")
            failures.filter(pl.col("FAILDATE").is_between(start, end, closed="both") & ~pl.col("CERT").is_in(sorted(panel_certs))).write_csv(review_dir / "failures_without_financials.csv")
            multiple = failures.group_by("CERT").agg(pl.len().alias("EVENT_COUNT")).filter(pl.col("EVENT_COUNT") > 1)
            failures.join(multiple, on="CERT", how="inner").sort("CERT", "FAILDATE").write_csv(review_dir / "multiple_failures_per_cert.csv")
            small_summaries["failures"]["CERT_with_multiple_failure_events"] = multiple.height

            frame = small["institutions"]
            expressions = [cert_expression().alias("CERT")]
            for column in ("ESTYMD", "ENDEFYMD", "INSDATE"):
                if column in frame.columns:
                    expressions.append(date_expression(frame, column).alias(column))
            for column in ("NAME", "STNAME", "BKCLASS", "CHANGEC1"):
                if column in frame.columns:
                    expressions.append(pl.col(column).cast(pl.String))
            if "ACTIVE" in frame.columns:
                expressions.append(pl.col("ACTIVE").cast(pl.Int64, strict=True))
            institutions = frame.with_columns(expressions)
            save_prepared(institutions, out / "prepared" / "institutions.parquet")
            institution_certs = institutions.filter(pl.col("CERT").is_not_null() & (pl.col("CERT") > 0))["CERT"].unique().to_list()
            coverage = panel_keys.group_by("CERT").agg(
                pl.col("REPDTE").min().alias("FIRST_REPDTE"), pl.col("REPDTE").max().alias("LAST_REPDTE"),
                pl.len().alias("OBSERVED_QUARTERS"),
            ).with_columns(
                pl.col("CERT").is_in(institution_certs).alias("HAS_INSTITUTION_METADATA"),
                pl.col("CERT").is_in(failures["CERT"].unique().to_list()).alias("HAS_FAILURE_EVENT_AUDIT_ONLY"),
            ).sort("CERT")
            coverage.write_csv(review_dir / "bank_coverage_AUDIT_ONLY.csv")
            coverage.filter(~pl.col("HAS_INSTITUTION_METADATA")).write_csv(review_dir / "unmatched_institutions.csv")
            (review_dir / "READ_ME.txt").write_text(
                "All files in review/ are for audit only, not predictor input.\n"
                "Missing institution metadata does not prove failure or merger. Retain those financial rows.\n"
                "LAST_REPDTE is the last observed report, not a verified exit date.\n"
                "Multiple failure events for one CERT require event-aware label construction; do not take the first event blindly.\n"
                "Unlinked events are preserved separately and in failures_all.parquet. They are never given artificial CERTs.\n"
                "Missing financial values remain null; any imputation must later be fitted on training data only.\n",
                encoding="utf-8",
            )
        except Exception as exc:
            issue("ERROR", "small_table_standardization_failed", "prepared", f"{type(exc).__name__}: {exc}")

    environment = []
    for name in PACKAGE_NAMES:
        try:
            installed = metadata.version(name)
        except metadata.PackageNotFoundError:
            installed = "NOT_INSTALLED"
        environment.append({"package": name, "installed_version": installed})
    requirement_rows = []
    if args.requirements:
        for number, line in enumerate(args.requirements.read_text(encoding="utf-8-sig").splitlines(), 1):
            content = line.split("#", 1)[0].strip()
            if not content:
                continue
            match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s;]+)", content)
            if not match:
                requirement_rows.append({"line": number, "requirement": content, "status": "NOT_CHECKED_COMPLEX_SPEC"})
                continue
            package, requested = match.groups()
            try:
                installed = metadata.version(package)
            except metadata.PackageNotFoundError:
                installed = "NOT_INSTALLED"
            requirement_rows.append({"line": number, "requirement": content, "installed": installed,
                                     "status": "MATCH" if installed == requested else "MISMATCH"})
        write_csv(out / "requirement_versions.csv", requirement_rows)

    missing_totals: dict[str, Counter] = {}
    for row in missingness:
        if row["table"] == "financials":
            item = missing_totals.setdefault(row["column"], Counter())
            item["rows"] += row["rows"]
            item["missing"] += row["missing"]
    top_missing = sorted([
        {"column": name, "missing": c["missing"], "rows": c["rows"],
         "missing_pct": round(100 * c["missing"] / c["rows"], 4) if c["rows"] else None}
        for name, c in missing_totals.items() if c["missing"]
    ], key=lambda row: row["missing_pct"] or 0, reverse=True)[:15]
    observation_ranges = []
    for column in sorted(all_columns):
        records = [row for row in missingness if row["table"] == "financials" and row["column"] == column]
        observed = sorted(row["quarter"] for row in records if row["rows"] > row["missing"])
        observation_ranges.append({"column": column, "first_quarter_with_value": observed[0] if observed else None,
                                   "last_quarter_with_value": observed[-1] if observed else None,
                                   "quarters_with_values": len(observed),
                                   "quarters_entirely_missing": sum(row["rows"] > 0 and row["rows"] == row["missing"] for row in records)})
    if args.prepare and prepared_rows != sum(rows_per_quarter.values()):
        issue("ERROR", "prepared_financial_row_count_mismatch", "prepared", f"raw={sum(rows_per_quarter.values())}, prepared={prepared_rows}")
    error_count = sum(row["severity"] == "ERROR" for row in issues)
    review_count = sum(row["severity"] == "REVIEW" for row in issues)
    status = "ACQUISITION_STRUCTURE_PASS" if error_count == 0 else "ACQUISITION_STRUCTURE_FAIL"
    summary = {
        "status": status, "audit_version": AUDIT_VERSION, "audit_time_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Initial acquisition/quality audit only; not complete Part 1, Part 2, or a model-ready certification.",
        "data_dir": str(root), "report_dir": str(out), "start": str(start), "end": str(end),
        "expected_quarters": len(expected), "quarter_files_found": len(quarter_files),
        "quarters_read_in_requested_scope": len(rows_per_quarter), "total_financial_rows": sum(rows_per_quarter.values()),
        "distinct_valid_panel_CERT": len(panel_certs), "duplicate_valid_panel_key_extra_rows": duplicate_total,
        "minimum_valid_REPDTE": str(panel_keys["REPDTE"].min()) if panel_keys.height else None,
        "maximum_valid_REPDTE": str(panel_keys["REPDTE"].max()) if panel_keys.height else None,
        "small_tables": small_summaries, "errors": error_count, "review_items": review_count,
        "top_missing_financial_columns": top_missing, "schema_columns_with_multiple_types": {k: sorted(v) for k, v in type_sets.items() if len(v) > 1},
        "financial_column_observation_ranges": observation_ranges,
        "preparation_requested": args.prepare, "financial_rows_standardized": prepared_rows if args.prepare else None,
        "prepared_state": ("STANDARDIZED_FOR_REVIEW" if error_count == 0 else "INCOMPLETE_NOT_FOR_USE") if args.prepare else "NOT_REQUESTED",
        "input_bytes": sum(item["bytes"] for item in checksums),
        "python_version": platform.python_version(), "python_executable": sys.executable, "platform": platform.platform(),
        "limitations": [
            "API totals are compared to the supplied manifest/download log; API was not queried again.",
            "Missingness and numeric profiles identify issues; no missing-value or outlier treatment was applied.",
            "Snapshot timing, historical publication dates/revisions, exit rules and leak-free labels remain to be designed.",
            "No CSV/Parquet benchmark, Spark parity, JVM test, full dependency resolver or model evaluation was performed.",
            "Package metadata versions are recorded; run python -m pip check and runtime smoke tests separately.",
            "Legacy unlinkable events before the first panel quarter are preserved but cannot be joined by CERT; they are not an in-scope acquisition failure.",
        ],
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    for filename, records, empty in (
        ("issues.csv", issues, ("severity", "rule", "table", "count", "detail")),
        ("quarters.csv", quarters, ("quarter", "rows")),
        ("missingness_by_quarter.csv", missingness, ("table", "quarter", "column")),
        ("numeric_profile.csv", numeric, ("table", "quarter", "column")),
        ("schema_by_quarter.csv", schemas, ("table", "quarter", "column", "dtype")),
        ("failure_types.csv", failure_types, ("RESTYPE", "rows")),
        ("file_checksums.csv", checksums, ("file", "bytes", "sha256")),
        ("environment.csv", environment, ("package", "installed_version")),
        ("column_observation_ranges.csv", observation_ranges, ("column", "first_quarter_with_value")),
    ):
        write_csv(out / filename, records, empty)
    lines = [
        f"BFT65B INITIAL AUDIT v{AUDIT_VERSION}", f"Status: {status}",
        f"Quarters read: {len(rows_per_quarter)}/{len(expected)}", f"Financial rows: {sum(rows_per_quarter.values()):,}",
        f"Distinct valid banks: {len(panel_certs):,}", f"Duplicate valid-key extra rows: {duplicate_total:,}",
        f"Errors: {error_count}; review items: {review_count}",
        f"Failure resolution types: {failure_types}", "", "Top financial missingness:",
        *[f"  {r['column']}: {r['missing_pct']}% ({r['missing']:,}/{r['rows']:,})" for r in top_missing],
        "", "Status concerns acquisition structure only. Review issues.csv and missingness before modelling.",
        "Read summary.json for scope and limitations. Keep the original data unchanged.", f"Reports: {out}",
    ]
    if args.prepare:
        lines.extend([f"Standardization: {summary['prepared_state']}", f"Financial rows standardized: {prepared_rows:,}",
                      "Typed copies: prepared/. Audit-only extracts: review/. No labels or imputation created."])
        if error_count == 0:
            (out / "STANDARDIZATION_COMPLETE.json").write_text(json.dumps({
                "audit_version": AUDIT_VERSION, "financial_rows": prepared_rows,
                "financial_schema": prepared_schema, "all_events_preserved": small_summaries.get("failures", {}).get("rows"),
                "scope": "Type standardization and review extracts only; exit/label decisions are still required.",
            }, indent=2), encoding="utf-8")
    text = "\n".join(lines) + "\n"
    (out / "summary.txt").write_text(text, encoding="utf-8")
    print("\n" + text)
    return 1 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
