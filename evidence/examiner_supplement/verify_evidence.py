"""Read-only checks for the BFT65B examiner memo. Run via python verify_evidence.py."""
import argparse
import csv
from fractions import Fraction
from hashlib import sha256
import json
from math import isclose
from pathlib import Path
import random
from statistics import median

ROOT = Path(__file__).resolve().parent

def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))

def require(condition, message):
    if not condition:
        raise ValueError(message)

def interpolated_quantile(sample, probability):
    ordered = sorted(sample)
    index = (len(ordered) - 1) * probability
    left = int(index)
    right = min(left + 1, len(ordered) - 1)
    return ordered[left] + (index - left) * (ordered[right] - ordered[left])

def storage(inputs):
    setting = json.loads((inputs / "csv_writer_setting.json").read_text())
    fields = read_csv(inputs / "field_null_counts.csv")
    require(len(fields) == len({v["field"] for v in fields}) == setting["source_columns"], "Field coverage mismatch")
    require(all(int(v["benchmark_typed_nulls"]) == int(v["sum_of_170_quarters"]) for v in fields), "Null ledgers disagree")
    n = sum(int(v["benchmark_typed_nulls"]) for v in fields)
    b = {v["variant"]: int(v["bytes"]) for v in read_csv(inputs / "storage_sizes.csv")}
    observed, zstd = b["csv_uncompressed"], b["parquet_zstd"]
    length = len(setting["null_token"].encode("ascii"))
    one_byte = observed - n * (length - 1)
    return {"typed_null_cells": n, "token_bytes": length, "observed_csv_bytes": observed,
            "observed_zstd_bytes": zstd, "measured_saving_pct": 100 * (1-zstd/observed),
            "one_byte_csv_bytes_conditional": one_byte, "one_byte_csv_MiB_conditional": one_byte / 2**20,
            "one_byte_saving_pct_conditional": 100 * (1-zstd/one_byte),
            "note": "Byte arithmetic with other serialization bytes fixed. No alternative file was timed or round-tripped."}

def population(inputs):
    lag = {int(v["lag_calendar_quarters"]): v for v in read_csv(inputs / "lag_coverage.csv")}
    n1, n2 = [int(lag[k]["rows"]) for k in (1, 2)]
    observed = next(v for v in read_csv(inputs / "outcome_dev.csv") if v["scenario"] == "Primary FAILURE only")
    pos, neg, missing, labelled = [int(observed[k]) for k in ("positive", "negative", "unresolved", "labelled")]
    require(pos+neg == labelled, "Adjudicated denominator mismatch")
    n = labelled + missing
    stock = json.loads((inputs/"negative_stock_summary.json").read_text())
    stock["total_negative_cells"] = sum(stock["by_field"].values())
    return {"lag1_rows": n1, "lag2_rows": n2, "net_row_difference": n1 - n2,
            "relative_count_reduction_pct": 100 * (n1-n2)/n1,
            "lag1_banks": int(lag[1]["banks"]), "lag2_banks": int(lag[2]["banks"]),
            "negative_stock_audit": stock, "development_candidates": n, "unresolved": missing, "labelled_positives": pos,
            "observed_prevalence_pct": 100*pos/labelled, "lower_prevalence_pct": 100*pos/n,
            "upper_prevalence_pct": 100*(pos+missing)/n,
            "note": "Binary outcome envelope after initial risk-set construction; no claim about AP, selection bias size or feasible joint label patterns."}

def paired_timings(inputs):
    trials = read_csv(inputs / "paired_trials.csv")
    ref = {r["task"]: r for r in read_csv(inputs / "paired_reference.csv") if r["pandas_baseline"] == "pandas_optimized"}
    result = {}
    for task, output in ref.items():
        by_round = {}
        for obs in trials:
            if obs["warmup"].lower() == "true" or obs["task"] != task:
                continue
            same = by_round.setdefault(int(obs["round"]), {})
            require(obs["engine"] not in same, "Duplicate task, round and engine")
            same[obs["engine"]] = float(obs["seconds"])
        require(len(by_round) == int(output["n_paired_rounds"]), "Missing experimental round")
        ratios = [g["pandas_optimized"]/g["polars"] for k, g in sorted(by_round.items())]
        seed = 20261112 + 2026 + sum(map(ord, task + "pandas_optimized"))
        rng = random.Random(seed)
        boot = [median([ratios[rng.randrange(len(ratios))] for _ in ratios]) for _ in range(2500)]
        lo, hi = (interpolated_quantile(boot, p) for p in (0.025, 0.975))
        for calc, column in [(median(ratios),"median_paired_speedup"), (lo,"bootstrap_95_low"), (hi,"bootstrap_95_high")]:
            require(isclose(calc, float(output[column]), rel_tol=1e-10), "Archived paired summary disagrees")
        result[task] = {"rounds": len(ratios), "polars_faster": sum(r>1 for r in ratios), "median_ratio": median(ratios),
                         "archived_paired_bootstrap_95":[lo, hi]}
    return result

def fixed_policy_comparisons(inputs):
    policies = {int(p["ratio"]): p for p in read_csv(inputs/"policy_dev.csv")}
    require(set(policies) == {5, 10, 20, 50}, "Expected exactly the registered scenarios")
    for r, p in policies.items():
        require(int(p["fp_cert_years"]) + r*int(p["missed_failure_certs"]) == float(p["cost_units"]), "Loss mismatch")
        require(int(p["missed_failure_certs"]) + int(p["detected_failure_certs"]) == 1290, "Event registry mismatch")
    changes = {}
    for s, t in [(5,20), (10,20), (20,50)]:
        a, b = policies[s], policies[t]
        delta = {k: int(b[k])-int(a[k]) for k in ("cert_year_alerts","fp_cert_years","detected_failure_certs")}
        additional_events = delta["detected_failure_certs"]
        require(additional_events>0, "Invalid marginal denominator")
        delta["extra_false_first_reviews_per_extra_event"] = float(Fraction(delta["fp_cert_years"],additional_events))
        delta["extra_total_first_reviews_per_extra_event"] = float(Fraction(delta["cert_year_alerts"],additional_events))
        changes[f"{s}_to_{t}"] = delta
    lo = max(changes[k]["extra_false_first_reviews_per_extra_event"] for k in ("5_to_20", "10_to_20"))
    hi = changes["20_to_50"]["extra_false_first_reviews_per_extra_event"]
    require(lo < 20 < hi, "The archived policy comparison does not bracket 20")
    return {"adjacent_and_reference_differences": changes, "pairwise_cost_ratio_interval_for_locked_among_four":[lo,hi],
            "note":"Comparison of four already-reported fixed OOF policies only; no score thresholds were searched."}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional new result file. Existing files are protected.")
    args = parser.parse_args()
    for name, expected in json.loads((ROOT/"input_sha256.json").read_text()).items():
        require(sha256((ROOT/name).read_bytes()).hexdigest()==expected, f"SHA-256 mismatch in {name}")
    e10 = ROOT/"repository_addition"/"supplementary_diagnostics"/"E10"
    acceptance = json.loads((e10/"RUN_ACCEPTANCE.json").read_text())
    for name, expected in acceptance["result_hashes"].items():
        require(sha256((e10/name).read_bytes()).hexdigest()==expected, f"E10 historical digest mismatch in {name}")
    inp = ROOT/"inputs"
    result = {"storage":storage(inp), "population":population(inp), "paired_timings":paired_timings(inp),
              "fixed_development_policies":fixed_policy_comparisons(inp), "e10_historical_hash_matches":len(acceptance["result_hashes"])}
    text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as out:
            out.write(text)
    else:
        print(text, end="")

if __name__ == "__main__":
    main()
