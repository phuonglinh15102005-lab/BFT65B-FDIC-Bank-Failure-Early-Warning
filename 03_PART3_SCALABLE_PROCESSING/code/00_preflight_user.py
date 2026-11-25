#!/usr/bin/env python3
"""BFT65B Part 3 - STEP 1: read-only source/environment preflight.

Usage from the folder containing the two source Parquets:
  python 00_preflight_user.py

Or pass explicit Windows file paths:
  python 00_preflight_user.py --clean "C:\\data\\panel_clean.parquet" --pit "C:\\data\\panel_pit_base.parquet"

Or point to the folder containing both files:
  python 00_preflight_user.py --data-dir "%USERPROFILE%\\Documents\\BFT65B"

This script never edits either input and never sends data to the internet.
It writes only aggregate metadata to part3_preflight.json.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


EXPECTED = {
    "clean": {
        "filename": "panel_clean.parquet",
        "rows": 1_669_802,
        "sha256": "0d1837815820e93eb71508dabd6f48143e2b596b09453606ccf0070c3717e107",
        "required": ("CERT", "REPDTE", "ASSET", "DEP", "EQ", "ROA", "LNLSGR", "NCLNLS"),
        "date_fields": ("REPDTE",),
    },
    "pit": {
        "filename": "panel_pit_base.parquet",
        "rows": 1_629_398,
        "sha256": "3fce669406ff1898ac85d9c41c6385b7f8c6b27e29ecd041bb0a3c59f6337421",
        "required": ("CERT", "DECISION_DATE", "SOURCE_REPDTE", "ASSET", "EQ", "ROA", "P3ASSET"),
        "date_fields": ("DECISION_DATE", "SOURCE_REPDTE"),
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def installed_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def java_version() -> dict:
    executable = shutil.which("java")
    source = "PATH" if executable else None
    if not executable and os.environ.get("JAVA_HOME"):
        candidate = Path(os.environ["JAVA_HOME"]) / "bin" / (
            "java.exe" if os.name == "nt" else "java"
        )
        if candidate.is_file():
            executable = str(candidate)
            source = "JAVA_HOME"
    if not executable:
        return {"available": False, "version": None, "source": None}
    try:
        result = subprocess.run(
            [executable, "-version"], capture_output=True, text=True,
            check=False, timeout=10,
        )
        lines = (result.stderr or result.stdout).splitlines()
        return {
            "available": result.returncode == 0,
            "version": lines[0][:160] if lines else None,
            "source": source,
        }
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"available": False, "version": type(error).__name__, "source": source}


def inspect_parquet(label: str, path: Path, pyarrow_parquet) -> dict:
    expected = EXPECTED[label]
    record = {"file_name": path.name, "attempted_path": str(path.resolve()),
              "exists": path.is_file(), "checks": {}}
    if not path.is_file():
        record["checks"]["file_exists"] = False
        record["status"] = "FAIL"
        return record

    record["checks"]["file_exists"] = True
    record["bytes"] = path.stat().st_size
    parquet = pyarrow_parquet.ParquetFile(path)
    schema = parquet.schema_arrow
    actual_fields = {field.name: str(field.type) for field in schema}
    record["metadata_rows"] = parquet.metadata.num_rows
    record["row_groups"] = parquet.metadata.num_row_groups
    record["column_count"] = len(schema)
    record["required_fields"] = {name: actual_fields.get(name) for name in expected["required"]}

    record["checks"]["row_count_matches"] = record["metadata_rows"] == expected["rows"]
    record["checks"]["required_fields_present"] = all(
        name in actual_fields for name in expected["required"]
    )
    record["checks"]["CERT_is_int64"] = actual_fields.get("CERT") == "int64"
    record["checks"]["date_types"] = all(
        actual_fields.get(name) == "date32[day]" for name in expected["date_fields"]
    )
    record["sha256"] = sha256(path)
    record["checks"]["exact_source_sha256"] = record["sha256"] == expected["sha256"]
    record["status"] = "PASS" if all(record["checks"].values()) else "FAIL"
    return record


def main() -> int:
    folder = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=folder,
                        help="Folder containing both Parquet files; defaults to script folder")
    parser.add_argument("--clean", type=Path, default=None,
                        help="Exact panel_clean.parquet path; overrides --data-dir")
    parser.add_argument("--pit", type=Path, default=None,
                        help="Exact panel_pit_base.parquet path; overrides --data-dir")
    parser.add_argument("--out", type=Path, default=folder / "part3_preflight.json")
    args = parser.parse_args()
    if args.clean is None:
        args.clean = args.data_dir / EXPECTED["clean"]["filename"]
    if args.pit is None:
        args.pit = args.data_dir / EXPECTED["pit"]["filename"]
    if args.out.suffix.lower() != ".json":
        parser.error("--out must end with .json; source Parquet files must never be overwritten")
    if args.out.resolve() in {args.clean.resolve(), args.pit.resolve()}:
        parser.error("--out must not point to an input Parquet")

    packages = ["python", "pandas", "polars", "pyarrow", "pyspark", "py4j", "psutil", "numpy"]
    installed = {name: (platform.python_version() if name == "python" else installed_version(name))
                 for name in packages}
    system = {
        "os": platform.system(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "python_executable": Path(sys.executable).name,
        "logical_cpus": os.cpu_count(),
        "libraries": installed,
        "java": java_version(),
    }
    try:
        import psutil

        system["ram_total_gib"] = round(psutil.virtual_memory().total / 1024**3, 2)
    except ImportError:
        system["ram_total_gib"] = None

    payload = {
        "project": "BFT65B FDIC Part 3",
        "step": "00 read-only data/environment preflight",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "environment": system,
        "files": {},
        "warnings": [],
        "preflight_status": "NOT_RUN",
    }
    try:
        import pyarrow.parquet as pq
    except ImportError:
        payload["warnings"].append("PyArrow is missing. Install the existing course requirements before rerunning.")
        payload["preflight_status"] = "FAIL_MISSING_PYARROW"
    else:
        for label, path in (("clean", args.clean), ("pit", args.pit)):
            try:
                payload["files"][label] = inspect_parquet(label, path, pq)
            except Exception as error:
                payload["files"][label] = {
                    "file_name": path.name,
                    "status": "FAIL",
                    "error": f"{type(error).__name__}: {error}",
                }
        payload["preflight_status"] = (
            "PASS" if len(payload["files"]) == 2
            and all(info.get("status") == "PASS" for info in payload["files"].values())
            else "FAIL"
        )

    if not system["java"]["available"]:
        payload["warnings"].append("Java is not ready. Polars/pandas can run, but Spark will need Java.")
    for library in ("polars", "pandas", "pyspark", "psutil"):
        if installed[library] is None:
            payload["warnings"].append(f"{library} is missing; it is needed at a later Part 3 step.")
    if platform.python_version_tuple()[:2] != ("3", "12"):
        payload["warnings"].append("The reviewed environment used Python 3.12; please report your version.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PART3 STEP 00: {payload['preflight_status']}")
    for label in ("clean", "pit"):
        file = payload["files"].get(label, {})
        print(f"  {label}: {file.get('status', 'NOT_CHECKED')} "
              f"rows={file.get('metadata_rows')} sha256_verified={file.get('checks', {}).get('exact_source_sha256')}")
    print(f"  Python: {installed['python']} | Polars: {installed['polars']} | "
          f"pandas: {installed['pandas']} | PySpark: {installed['pyspark']}")
    print(f"  Java available: {system['java']['available']} | RAM: {system['ram_total_gib']} GiB")
    for label, path in (("clean", args.clean), ("pit", args.pit)):
        if not path.is_file():
            print(f"  MISSING {label}: {path.resolve()}")
    if payload["preflight_status"] == "FAIL" and any(
        not path.is_file() for path in (args.clean, args.pit)
    ):
        print('  ACTION: Use --data-dir "C:\\FULL\\FOLDER\\WITH\\PARQUETS" '
              'or specify --clean and --pit separately.')
    if payload["warnings"]:
        print("  WARNINGS:")
        for item in payload["warnings"]:
            print(f"   - {item}")
    print(f"OUTPUT JSON: {args.out.resolve()}")
    return 0 if payload["preflight_status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
