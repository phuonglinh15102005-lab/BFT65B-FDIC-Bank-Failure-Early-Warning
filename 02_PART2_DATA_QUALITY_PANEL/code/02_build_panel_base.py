#!/usr/bin/env python3
"""BFT65B step 2A: base panel and evidence for data-quality/exit decisions.

Run: python 02_build_panel_base.py
Optional: --audit-dir PATH --out NEW_DIRECTORY
Requires polars and pyarrow from the existing project environment.

Reads an audit v2 prepared snapshot; never downloads or alters input files.
Writes a NEW output directory. No imputation, row deletion, labels, model,
final exit classification or point-in-time certification is performed here.
All snapshot/event metadata are kept in audit-only tables, outside panel_base.

Sources: course final_report_bft65b.pdf; audit_fdic.py v2;
https://api.fdic.gov/banks/docs/ ; https://docs.pola.rs/api/python/stable/ .
AI assistance: prepared with ChatGPT on 2026-11-08. Disclose in report/README.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
import zipfile

try:
    import polars as pl
    import pyarrow.parquet as pq
except ImportError as exc:
    raise SystemExit(f"Missing dependency: {exc}. Use the Python environment used for check_prepared.py.")

VERSION = "1.0"
DEFAULT_AUDIT = Path.home() / "data_raw/fdic/audit_results/20261108T032158_540721Z"
FORBIDDEN = {"FAILDATE", "RESTYPE", "COST", "ACTIVE", "ENDEFYMD", "CHANGEC1", "QBFASSET", "QBFDEP"}


def say(message):
    print(message, flush=True)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str, allow_nan=False), encoding="utf-8")


def clean_text(frame):
    """Preserve case; whitespace-only strings become null. Numeric values unchanged."""
    schema = frame.collect_schema() if isinstance(frame, pl.LazyFrame) else frame.schema
    exprs = []
    for c, dtype in schema.items():
        if dtype == pl.String:
            s = pl.col(c).str.strip_chars()
            exprs.append(pl.when(s == "").then(None).otherwise(s).alias(c))
    return frame.with_columns(exprs)


def text_profile(frame, table):
    lf = frame if isinstance(frame, pl.LazyFrame) else frame.lazy()
    cols = [c for c, t in lf.collect_schema().items() if t == pl.String]
    if not cols:
        return []
    exprs = []
    for j, c in enumerate(cols):
        s = pl.col(c)
        exprs.extend([
            s.is_null().sum().alias(f"null_{j}"),
            (s.str.strip_chars() == "").sum().alias(f"blank_{j}"),
            (s != s.str.strip_chars()).sum().alias(f"trim_{j}"),
        ])
    counts = lf.select(exprs).collect().row(0, named=True)
    return [{"table": table, "column": c, "null_before": counts[f"null_{j}"],
             "blank_to_null": counts[f"blank_{j}"], "trimmed_strings": counts[f"trim_{j}"]}
            for j, c in enumerate(cols)]


def require_typed(frame, columns, table):
    for c, dtype in columns.items():
        require(c in frame.columns and frame.schema[c] == dtype,
                f"{table}.{c} must be {dtype}. Select the prepared folder from audit v2.")


def make_panel(audit_dir: Path, out: Path):
    started = time.perf_counter()
    prepared = audit_dir / "prepared"
    old = json.loads((audit_dir / "summary.json").read_text(encoding="utf-8-sig"))
    marker_path = audit_dir / "STANDARDIZATION_COMPLETE.json"
    require(marker_path.is_file(), "Missing STANDARDIZATION_COMPLETE.json in the selected audit directory.")
    require(old.get("status") == "ACQUISITION_STRUCTURE_PASS", "Selected audit did not pass acquisition checks.")
    require(old.get("prepared_state") == "STANDARDIZED_FOR_REVIEW", "Selected audit has no complete prepared data.")
    start, end = date.fromisoformat(old["start"]), date.fromisoformat(old["end"])
    expected = [date(y, m, d).strftime("%Y%m%d") for y in range(start.year, end.year + 1)
                for m, d in [(3, 31), (6, 30), (9, 30), (12, 31)] if start <= date(y, m, d) <= end]
    files = sorted((prepared / "financials").glob("*.parquet"))
    require({p.name for p in files} == {f"REPDTE={q}.parquet" for q in expected},
            "Prepared financial files do not match the audit's quarter range.")
    require(not out.exists(), f"Output directory already exists: {out}. Choose a new directory.")
    require(not out.is_relative_to(prepared) and not prepared.is_relative_to(out),
            "Output must be separate from prepared inputs.")
    out.mkdir(parents=True)
    evidence = out / "review_AUDIT_ONLY"
    evidence.mkdir()

    def csv(frame, name):
        frame.write_csv(evidence / name, include_bom=True)

    say(f"[1/5] Reading {len(files)} prepared quarters...")
    source = pl.scan_parquet([str(p) for p in files])
    schema = source.collect_schema()
    require(schema.get("CERT") == pl.Int64 and schema.get("REPDTE") == pl.Date,
            "Use prepared financials with CERT Int64 and REPDTE Date.")
    require(not FORBIDDEN.intersection(schema), "Event or current-status columns found inside financial inputs.")
    keys = source.select("CERT", "REPDTE").collect()
    require(keys.height == old["total_financial_rows"], "Prepared row count differs from prior audit.")
    require(keys.filter(pl.col("CERT").is_null() | (pl.col("CERT") <= 0) | pl.col("REPDTE").is_null()).height == 0,
            "Invalid keys: resolve before building a panel.")
    require(keys.unique().height == keys.height, "Duplicate bank-quarter keys: no automatic deduplication.")
    require(keys["REPDTE"].n_unique() == len(expected), "Unexpected number of observed quarters.")
    require(set(keys["REPDTE"].unique().to_list()) == {datetime.strptime(q, "%Y%m%d").date() for q in expected},
            "Report dates do not match the requested quarter range.")
    require(keys["CERT"].n_unique() == old["distinct_valid_panel_CERT"], "Bank count differs from prior audit.")

    inst = pl.read_parquet(prepared / "institutions.parquet")
    events = pl.read_parquet(prepared / "failures_all.parquet")
    require_typed(inst, {"CERT": pl.Int64, "ENDEFYMD": pl.Date, "ACTIVE": pl.Int64}, "institutions")
    require_typed(events, {"CERT": pl.Int64, "FAILDATE": pl.Date}, "failures_all")
    require("RESTYPE" in events.columns, "Missing RESTYPE.")
    require(inst["CERT"].null_count() == 0 and inst["CERT"].n_unique() == inst.height, "Institution keys are not unique.")
    require(inst.filter(pl.col("CERT") <= 0).height == 0, "Invalid institution identifier.")
    for table, df in [("institutions", inst), ("failures", events)]:
        require(df.height == old["small_tables"][table]["rows"], f"{table} row count differs from selected audit.")
    text_changes = text_profile(source, "financials") + text_profile(inst, "institutions") + text_profile(events, "failures")
    csv(pl.DataFrame(text_changes), "text_cleanup.csv")
    inst, events = clean_text(inst), clean_text(events)
    events = events.with_columns(pl.col("RESTYPE").str.to_uppercase())
    if "SOURCE_ROW" not in events.columns:
        events = events.with_row_index("SOURCE_ROW", offset=1)

    say("[2/5] Building the base panel; keeping all financial rows...")
    clean = clean_text(source)
    numeric = [c for c, dtype in schema.items() if dtype.is_numeric() and c != "CERT"]
    # Non-finite values cannot be used as financial amounts; preserve originals in source.
    clean = clean.with_columns([
        pl.when(pl.col(c).is_finite()).then(pl.col(c)).otherwise(None).alias(c) for c in numeric
    ])
    (evidence / "polars_panel_plan.txt").write_text(clean.explain(optimized=True), encoding="utf-8")
    target = out / "panel_base.parquet"
    clean.sink_parquet(target, compression="zstd", row_group_size=100_000)
    require(pq.ParquetFile(target).metadata.num_rows == keys.height, "Output row count changed.")
    panel = pl.scan_parquet(target)
    output_keys = panel.select("CERT", "REPDTE").collect()
    require(keys.sort("CERT", "REPDTE").equals(output_keys.sort("CERT", "REPDTE")), "Output keys changed.")

    # Missingness by quarter, plus numerical profiles; no data-dependent fit here.
    agg = source.group_by("REPDTE").agg(pl.len().alias("rows"), *[
        (~pl.col(c).is_finite().fill_null(False)).sum().alias(c) for c in numeric
    ]).sort("REPDTE").collect()
    missing = agg.unpivot(on=numeric, index=["REPDTE", "rows"], variable_name="column", value_name="missing_after")
    missing = missing.with_columns((100 * pl.col("missing_after") / pl.col("rows")).alias("missing_pct"))
    csv(missing, "missingness_by_quarter.csv")
    profiles = []
    exprs = []
    for j, c in enumerate(numeric):
        v = pl.col(c)
        exprs.extend([v.is_null().sum().alias(f"null_{j}"), v.is_nan().sum().alias(f"nan_{j}"),
                      v.is_infinite().sum().alias(f"inf_{j}"),
                      (v.is_finite() & (v < 0)).sum().alias(f"neg_{j}"),
                      (v == 0).sum().alias(f"zero_{j}"),
                      v.filter(v.is_finite()).min().alias(f"min_{j}"),
                      v.filter(v.is_finite()).max().alias(f"max_{j}")])
    stats = source.select(exprs).collect().row(0, named=True)
    for j, c in enumerate(numeric):
        n = stats[f"null_{j}"] + stats[f"nan_{j}"] + stats[f"inf_{j}"]
        profiles.append({"column": c, "dtype": str(schema[c]), "rows": keys.height,
                         "null_before": stats[f"null_{j}"], "nan_to_null": stats[f"nan_{j}"],
                         "infinity_to_null": stats[f"inf_{j}"], "missing_after": n,
                         "missing_pct": 100 * n / keys.height, "negative_count": stats[f"neg_{j}"],
                         "zero_count": stats[f"zero_{j}"], "min_finite": stats[f"min_{j}"], "max_finite": stats[f"max_{j}"]})
    csv(pl.DataFrame(profiles).sort("missing_pct", descending=True), "numeric_profile.csv")
    observed = missing.filter(pl.col("missing_after") < pl.col("rows")).group_by("column").agg(
        pl.col("REPDTE").min().alias("FIRST_VALUE_QUARTER"), pl.col("REPDTE").max().alias("LAST_VALUE_QUARTER"),
        pl.len().alias("QUARTERS_WITH_VALUES"))
    csv(pl.DataFrame({"column": numeric}).join(observed, on="column", how="left"), "column_availability.csv")

    say("[3/5] Reviewing gaps, institution links and failure events...")
    key_index = keys.with_columns((pl.col("REPDTE").dt.year().cast(pl.Int32) * 4 + pl.col("REPDTE").dt.quarter().cast(pl.Int32)).alias("Q_INDEX"))
    coverage = key_index.group_by("CERT").agg(
        pl.col("REPDTE").min().alias("FIRST_REPDTE"), pl.col("REPDTE").max().alias("LAST_REPDTE"),
        pl.len().alias("OBSERVED_QUARTERS"),
        (pl.col("Q_INDEX").max() - pl.col("Q_INDEX").min() + 1).alias("CALENDAR_QUARTERS"),
    ).with_columns((pl.col("CALENDAR_QUARTERS") - pl.col("OBSERVED_QUARTERS")).alias("INTERNAL_MISSING_QUARTERS"))
    csv(coverage.filter(pl.col("INTERNAL_MISSING_QUARTERS") > 0).sort("CERT"), "banks_with_internal_gaps.csv")
    inst_meta = inst.select("CERT", *[pl.col(c).alias("SNAPSHOT_" + c) for c in inst.columns if c != "CERT"])
    inst_meta = inst_meta.with_columns(pl.lit(True).alias("HAS_INSTITUTION_METADATA"))
    coverage = coverage.join(inst_meta, on="CERT", how="left", validate="1:1").with_columns(
        pl.col("HAS_INSTITUTION_METADATA").fill_null(False))
    valid = events.filter((pl.col("CERT") > 0) & pl.col("FAILDATE").is_not_null())
    unlinked = events.filter(~((pl.col("CERT") > 0) & pl.col("FAILDATE").is_not_null()).fill_null(False))
    failures = valid.filter(pl.col("RESTYPE") == "FAILURE")
    assistance = valid.filter(pl.col("RESTYPE") == "ASSISTANCE")
    failure_counts = failures.group_by("CERT").agg(pl.len().alias("FAILURE_EVENT_COUNT"))
    coverage = coverage.join(failure_counts, on="CERT", how="left", validate="1:1").with_columns(
        pl.col("FAILURE_EVENT_COUNT").fill_null(0))
    # These are review groups, NOT final outcome/exit labels.
    coverage = coverage.with_columns(
        pl.when(pl.col("FAILURE_EVENT_COUNT") > 1).then(pl.lit("MULTIPLE_FAILURE_EVENTS_REVIEW"))
        .when(pl.col("FAILURE_EVENT_COUNT") == 1).then(pl.lit("FAILURE_HISTORY_REVIEW_TIMING"))
        .when(~pl.col("HAS_INSTITUTION_METADATA")).then(pl.lit("MISSING_INSTITUTION_METADATA"))
        .when(pl.col("SNAPSHOT_ACTIVE") == 0).then(pl.lit("INACTIVE_NO_FAILURE_VERIFY_REASON"))
        .when(pl.col("SNAPSHOT_ACTIVE") == 1).then(pl.lit("ACTIVE_SNAPSHOT_VERIFY_COVERAGE"))
        .otherwise(pl.lit("UNKNOWN_STATUS_REVIEW")).alias("REVIEW_GROUP")
    ).sort("CERT")
    require(coverage.height == keys["CERT"].n_unique(), "Institution join changed bank count.")
    csv(coverage, "bank_coverage_AUDIT_ONLY.csv")
    unmatched = coverage.filter(~pl.col("HAS_INSTITUTION_METADATA"))
    csv(unmatched, "unmatched_institutions.csv")
    inactive_no_failure = coverage.filter((pl.col("SNAPSHOT_ACTIVE") == 0) & (pl.col("FAILURE_EVENT_COUNT") == 0))
    csv(inactive_no_failure.group_by("SNAPSHOT_CHANGEC1").agg(pl.len().alias("banks")), "inactive_change_codes.csv")
    missing_failures = failures.filter(pl.col("FAILDATE").is_between(start, end, closed="both")).join(
        coverage.select("CERT"), on="CERT", how="anti")
    csv(missing_failures, "failures_without_financials.csv")
    multiple = failures.join(failure_counts.filter(pl.col("FAILURE_EVENT_COUNT") > 1), on="CERT", how="inner")
    csv(multiple.sort("CERT", "FAILDATE"), "multiple_failure_events.csv")
    multi_rows = panel.join(multiple.select("CERT").unique().lazy(), on="CERT", how="inner").collect()
    csv(multi_rows.sort("CERT", "REPDTE"), "financials_for_multiple_failure_CERTs.csv")
    duplicates = valid.filter(pl.struct("CERT", "FAILDATE", "RESTYPE").is_duplicated())
    csv(duplicates, "duplicate_event_keys.csv")
    csv(unlinked, "unlinked_events.csv")
    unknown = events.filter(pl.col("RESTYPE").is_null() | ~pl.col("RESTYPE").is_in(["FAILURE", "ASSISTANCE"]))
    csv(unknown, "unknown_event_types.csv")
    # Future/current metadata can be used for audit here, but never as predictors.
    event_coverage = failures.join(coverage.select("CERT", "FIRST_REPDTE", "LAST_REPDTE"), on="CERT", how="left", validate="m:1")
    event_coverage = event_coverage.with_columns((pl.col("LAST_REPDTE") >= pl.col("FAILDATE")).fill_null(False).alias("REPORT_ON_OR_AFTER_EVENT_REVIEW"))
    csv(event_coverage, "failure_event_coverage.csv")
    ends = coverage.filter(pl.col("HAS_INSTITUTION_METADATA") & (pl.col("SNAPSHOT_ACTIVE") == 0) &
                           pl.col("SNAPSHOT_ENDEFYMD").is_not_null() & (pl.col("LAST_REPDTE") > pl.col("SNAPSHOT_ENDEFYMD")))
    csv(ends, "reports_after_inactive_date_REVIEW.csv")
    csv(events.group_by("RESTYPE").len().rename({"len": "events"}), "event_type_counts.csv")
    csv(failures.with_columns(pl.col("FAILDATE").dt.year().alias("year")).group_by("year").agg(
        pl.len().alias("failure_event_rows"), pl.col("CERT").n_unique().alias("distinct_CERT")), "failures_by_year.csv")
    # Store normalized event/institution tables away from the predictor input.
    inst.write_parquet(evidence / "institutions_AUDIT_ONLY.parquet", compression="zstd")
    events.write_parquet(evidence / "events_AUDIT_ONLY.parquet", compression="zstd")

    say("[4/5] Saving provenance and quality evidence...")
    input_paths = [*files, prepared / "institutions.parquet", prepared / "failures_all.parquet", audit_dir / "summary.json", marker_path]
    checksums = [{"path": str(p), "bytes": p.stat().st_size, "sha256": sha256(p)} for p in input_paths]
    csv(pl.DataFrame(checksums), "input_checksums.csv")
    quarters = keys.group_by("REPDTE").len().rename({"len": "financial_rows"}).sort("REPDTE")
    csv(quarters, "rows_by_quarter.csv")
    review_counts = {
        "banks_without_institution_metadata": unmatched.height,
        "rows_without_institution_metadata": int(unmatched["OBSERVED_QUARTERS"].sum()),
        "failure_events_in_scope_without_financials": missing_failures.height,
        "CERTs_with_multiple_failure_events": multiple["CERT"].n_unique(),
        "unlinked_event_rows_preserved": unlinked.height,
        "duplicate_event_rows_for_review": duplicates.height,
        "unknown_event_type_rows": unknown.height,
        "banks_with_internal_quarter_gaps": coverage.filter(pl.col("INTERNAL_MISSING_QUARTERS") > 0).height,
        "failure_events_with_reports_on_or_after_event": event_coverage.filter(pl.col("REPORT_ON_OR_AFTER_EVENT_REVIEW")).height,
        "banks_with_reports_after_inactive_date": ends.height,
        "financial_blank_strings_to_null": sum(r["blank_to_null"] for r in text_changes if r["table"] == "financials"),
    }
    summary = {
        "status": "BASE_PANEL_READY_FOR_REVIEW", "step": "2A", "version": VERSION,
        "run_time_utc": datetime.now(timezone.utc).isoformat(), "audit_dir": str(audit_dir), "output_dir": str(out),
        "quarters": len(files), "rows_input": keys.height, "rows_output": pq.ParquetFile(target).metadata.num_rows,
        "banks": coverage.height, "first_quarter": start, "last_quarter": end,
        "rows_dropped": 0, "labels_created": False, "model_ready": False,
        "panel_bytes": target.stat().st_size, "panel_sha256": sha256(target),
        "script_sha256": sha256(Path(__file__)), "review_counts": review_counts,
        "review_groups": coverage.group_by("REVIEW_GROUP").len().sort("REVIEW_GROUP").to_dicts(),
        "python": platform.python_version(), "polars": pl.__version__, "platform": platform.platform(),
        "elapsed_seconds_not_a_benchmark": round(time.perf_counter() - started, 3),
        "rules": ["Trim strings; blank strings become null.", "NaN/infinity become null with counts; finite numeric values retained.",
                  "Keep all bank-quarter rows, zeros and finite negative values.", "No imputation, winsorization, labels or final exit decisions.",
                  "Current institution status, failure events and audit flags are excluded from panel_base."],
        "limitations": ["Base panel is not model-ready or verified point-in-time data.",
                        "Exit reasons, repeated events, observation eligibility and availability lag still require decisions.",
                        "Review summaries use future events and current metadata; never use review tables as predictors.",
                        "Storage layout is provisional; no CSV/pandas/Spark benchmark was performed in this step."]
    }
    save_json(out / "step2_summary.json", summary)
    readme = """BFT65B STEP 2A - BASE PANEL, NOT MODEL-READY

panel_base.parquet contains only the original financial columns, with whitespace
trimmed, blank strings and non-finite numeric values changed to null. No financial
row was deleted, no value imputed, no label assigned, and no exit finally classified.

review_AUDIT_ONLY contains future/current metadata. NEVER use these columns as
historical predictors. LAST_REPDTE is a last observed report, not a verified exit.
REVIEW_GROUP is only a work queue, not failure/merger/other-exit classification.
Dates after an event require investigation; rows are preserved until resolved.

Next: verify event/exit cases and field definitions; define prediction timing,
calendar-based lags, observation eligibility and labels. Do not fit imputation or
outlier thresholds on the full panel. Training-only preprocessing comes later.

Use step2_summary.json and the CSVs as evidence for Part 2. The optimized Polars
plan is preliminary evidence for Part 3, not a performance benchmark or Spark demo.

Send review_bundle.zip for review. It contains the summary, CSV reports and plan;
it does not contain the large panel or the full source data. Some CSVs contain
selected public financial rows for investigating repeated failure events.
Do not commit this data-containing ZIP to GitHub. Raw and prepared inputs are unchanged.

Sources: instructor PDF and starter/audit code; https://api.fdic.gov/banks/docs/;
https://docs.pola.rs/api/python/stable/. AI assistance: ChatGPT, 2026-11-08.
"""
    (out / "READ_ME.txt").write_text(readme, encoding="utf-8")
    bundle = out / "review_bundle.zip"
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in [out / "step2_summary.json", out / "READ_ME.txt", *sorted(evidence.glob("*.csv")), evidence / "polars_panel_plan.txt"]:
            z.write(p, p.relative_to(out))
    save_json(out / "STEP2_COMPLETE.json", {"status": summary["status"], "panel_sha256": summary["panel_sha256"]})
    say("[5/5] DONE - BASE_PANEL_READY_FOR_REVIEW")
    say(f"Rows: {keys.height:,}; banks: {coverage.height:,}; quarters: {len(files)}; dropped: 0")
    say(f"Output: {out}")
    say(f"SEND THIS FILE: {bundle}")
    say("No model or labels created. Next: review exit cases and define labels.")
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    out = (args.out or (Path(__file__).resolve().parent / "BFT65B_outputs" / ("step2_" + stamp))).resolve()
    say("BFT65B - Step 2A starts. Input data will not be changed.")
    say(f"Audit input: {args.audit_dir.resolve()}")
    try:
        make_panel(args.audit_dir.resolve(), out)
    except Exception as exc:
        say(f"STOPPED: {type(exc).__name__}: {exc}")
        say("Do not use partial output. Send this message for help; no re-download is needed.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
