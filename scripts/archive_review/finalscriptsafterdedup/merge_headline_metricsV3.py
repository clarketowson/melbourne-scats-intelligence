#!/usr/bin/env python3
r"""
merge_headline_metricsV3.py

Merges the outputs from the headline-metric scripts into:

    A:\TrafficAnalytics\PROJECTS\reports\deduped\headline_metrics.json
    A:\TrafficAnalytics\PROJECTS\reports\deduped\headline_metrics.csv

Expected inputs:
    chunked_total_cleaned_volume_final.json
    chunked_busiest_site_final.json
    chunked_busiest_day_final.json
    chunked_busiest_time_bin_final.json
    chunked_peak_shares_final.json

This script does NOT query DuckDB.
It only merges already-generated result files.

V3 behavior:
- Designed to work cleanly after generate_peak_shares_chunkedV3.py.
- Never loops internally.
- Always writes a diagnostic JSON/CSV when possible, even if sources are missing.
- In strict mode, exits with code 2 if any required final JSON is missing or incomplete.
- In partial mode, merges whatever is available and marks missing/incomplete sources clearly.
- Treats missing source files as a terminal condition for wrappers, not as something to retry forever.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


REPORT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")

INPUTS = {
    "total_cleaned_volume": REPORT_DIR / "chunked_total_cleaned_volume_final.json",
    "busiest_site": REPORT_DIR / "chunked_busiest_site_final.json",
    "busiest_day": REPORT_DIR / "chunked_busiest_day_final.json",
    "busiest_time_bin": REPORT_DIR / "chunked_busiest_time_bin_final.json",
    "peak_shares": REPORT_DIR / "chunked_peak_shares_final.json",
}

OUTPUT_JSON = REPORT_DIR / "headline_metrics.json"
OUTPUT_CSV = REPORT_DIR / "headline_metrics.csv"
DIAGNOSTIC_JSON = REPORT_DIR / "headline_metrics_merge_status.json"

# Default is strict because the public headline file should only be considered final
# when every upstream metric script has completed.
STRICT_COMPLETE_DEFAULT = True

PRECOMPUTED_SUMMARY = {
    "cleaned_rows": 37877397311,
    "date_range_start": "2014-01-01",
    "date_range_end": "2026-04-07",
}


class InputProblem(Exception):
    pass


def fmt_int(value: Any) -> str:
    if value is None or value == "":
        return "N/A"
    return f"{int(value):,}"


def fmt_pct(value: Any) -> str:
    if value is None or value == "":
        return "N/A"
    return f"{float(value):.2f}%"


def fmt_text(value: Any) -> str:
    if value is None or value == "":
        return "N/A"
    return str(value)


def read_json(path: Path) -> tuple[dict | None, str | None]:
    if not path.exists():
        return None, "missing"
    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            return None, "not_a_json_object"
        return payload, None
    except json.JSONDecodeError as exc:
        return None, f"json_decode_error: {exc}"
    except OSError as exc:
        return None, f"read_error: {exc}"


def source_status(name: str, path: Path, payload: dict | None, problem: str | None) -> dict:
    exists = path.exists()
    is_complete = payload.get("is_complete") if payload else False
    months_total = payload.get("months_total") if payload else None
    months_completed = payload.get("months_completed") if payload else None

    if problem is not None:
        state = problem
    elif is_complete is True:
        state = "complete"
    elif is_complete is False:
        state = "incomplete"
    else:
        # Older files may not include is_complete. Do not fail purely for that,
        # but make it visible in the diagnostic output.
        state = "unknown_completion_flag"

    return {
        "name": name,
        "path": str(path),
        "exists": exists,
        "is_complete": is_complete,
        "months_total": months_total,
        "months_completed": months_completed,
        "state": state,
        "problem": problem,
    }


def load_all_inputs() -> tuple[dict[str, dict | None], dict[str, dict]]:
    payloads: dict[str, dict | None] = {}
    statuses: dict[str, dict] = {}

    for name, path in INPUTS.items():
        payload, problem = read_json(path)
        payloads[name] = payload
        statuses[name] = source_status(name, path, payload, problem)

    return payloads, statuses


def is_source_ok_for_strict(status: dict) -> bool:
    # Missing/unreadable JSON is always not OK.
    if status["problem"] is not None:
        return False
    if status["exists"] is not True:
        return False
    # Known incomplete files are not OK.
    if status["is_complete"] is False:
        return False
    # None is allowed for backwards-compatible older final JSONs, but reported.
    return True


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


def write_csv(path: Path, flat_metrics: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric_name", "metric_value"])
        for key, value in flat_metrics.items():
            writer.writerow([key, value])
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


def get(payloads: dict[str, dict | None], source: str, key: str) -> Any:
    payload = payloads.get(source)
    if not payload:
        return None
    return payload.get(key)


def build_merged(payloads: dict[str, dict | None], statuses: dict[str, dict], strict_complete: bool) -> dict:
    all_sources_present = all(item["exists"] for item in statuses.values())
    all_sources_complete = all(is_source_ok_for_strict(item) for item in statuses.values())
    missing_sources = [name for name, item in statuses.items() if not item["exists"]]
    incomplete_sources = [
        name for name, item in statuses.items()
        if item["exists"] and item["problem"] is None and item["is_complete"] is False
    ]
    unreadable_sources = [name for name, item in statuses.items() if item["problem"] not in (None, "missing")]

    merged = {
        "generated_at_epoch": round(time.time(), 3),
        "generated_at_readable": time.strftime("%Y-%m-%d %H:%M:%S"),
        "merge_script_version": "V3",
        "strict_complete_mode": strict_complete,
        "all_sources_present": all_sources_present,
        "all_sources_complete": all_sources_complete,
        "missing_sources": missing_sources,
        "incomplete_sources": incomplete_sources,
        "unreadable_sources": unreadable_sources,
        "source_status": statuses,
        "headline_metrics": {
            "cleaned_rows": PRECOMPUTED_SUMMARY["cleaned_rows"],
            "distinct_sites": None,
            "date_range_start": PRECOMPUTED_SUMMARY["date_range_start"],
            "date_range_end": PRECOMPUTED_SUMMARY["date_range_end"],
            "total_cleaned_volume": get(payloads, "total_cleaned_volume", "total_cleaned_volume"),
            "busiest_site_id": get(payloads, "busiest_site", "busiest_site_id"),
            "busiest_site_name": get(payloads, "busiest_site", "busiest_site_name"),
            "busiest_time_bin": get(payloads, "busiest_time_bin", "busiest_time_bin"),
            "busiest_day": get(payloads, "busiest_day", "busiest_day"),
            "am_peak_share": get(payloads, "peak_shares", "am_peak_share"),
            "pm_peak_share": get(payloads, "peak_shares", "pm_peak_share"),
        },
        "formatted": {},
    }

    distinct_sites_file = REPORT_DIR / "distinct_sites.json"
    distinct_sites_value = None
    if distinct_sites_file.exists():
        distinct_payload, distinct_problem = read_json(distinct_sites_file)
        if distinct_payload and distinct_problem is None:
            distinct_sites_value = distinct_payload.get("distinct_sites")
    elif get(payloads, "busiest_site", "distinct_sites") is not None:
        distinct_sites_value = get(payloads, "busiest_site", "distinct_sites")

    merged["headline_metrics"]["distinct_sites"] = distinct_sites_value

    hm = merged["headline_metrics"]
    merged["formatted"] = {
        "cleaned_rows": fmt_int(hm["cleaned_rows"]),
        "distinct_sites": fmt_int(hm["distinct_sites"]),
        "date_range_start": fmt_text(hm["date_range_start"]),
        "date_range_end": fmt_text(hm["date_range_end"]),
        "total_cleaned_volume": fmt_int(hm["total_cleaned_volume"]),
        "busiest_site_id": fmt_text(hm["busiest_site_id"]),
        "busiest_site_name": fmt_text(hm["busiest_site_name"]),
        "busiest_time_bin": fmt_text(hm["busiest_time_bin"]),
        "busiest_day": fmt_text(hm["busiest_day"]),
        "am_peak_share": fmt_pct(hm["am_peak_share"]),
        "pm_peak_share": fmt_pct(hm["pm_peak_share"]),
    }

    return merged


def build_flat_csv(merged: dict) -> dict:
    formatted = merged["formatted"]
    return {
        "generated_at_readable": merged["generated_at_readable"],
        "merge_script_version": merged["merge_script_version"],
        "strict_complete_mode": merged["strict_complete_mode"],
        "all_sources_present": merged["all_sources_present"],
        "all_sources_complete": merged["all_sources_complete"],
        "missing_sources": ",".join(merged["missing_sources"]),
        "incomplete_sources": ",".join(merged["incomplete_sources"]),
        "unreadable_sources": ",".join(merged["unreadable_sources"]),
        "cleaned_rows": formatted["cleaned_rows"],
        "distinct_sites": formatted["distinct_sites"],
        "date_range_start": formatted["date_range_start"],
        "date_range_end": formatted["date_range_end"],
        "total_cleaned_volume": formatted["total_cleaned_volume"],
        "busiest_site_id": formatted["busiest_site_id"],
        "busiest_site_name": formatted["busiest_site_name"],
        "busiest_time_bin": formatted["busiest_time_bin"],
        "busiest_day": formatted["busiest_day"],
        "am_peak_share": formatted["am_peak_share"],
        "pm_peak_share": formatted["pm_peak_share"],
    }


def print_source_report(statuses: dict[str, dict]) -> None:
    print("SOURCE STATUS")
    print("-" * 90)
    for name, item in statuses.items():
        print(f"{name:22s} state={item['state']}")
        print(f"{'':22s} path={item['path']}")
        if item["months_total"] is not None or item["months_completed"] is not None:
            print(f"{'':22s} months={item['months_completed']}/{item['months_total']}")
    print("-" * 90)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge headline metric final JSON files into headline_metrics outputs.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--strict", action="store_true", help="Fail unless all required sources are present and complete.")
    mode.add_argument("--partial", action="store_true", help="Merge available sources even if some are missing or incomplete.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    strict_complete = STRICT_COMPLETE_DEFAULT
    if args.strict:
        strict_complete = True
    if args.partial:
        strict_complete = False

    print("=" * 90)
    print("MERGING HEADLINE METRICS V3")
    print("=" * 90)
    print(f"Report directory      : {REPORT_DIR}")
    print(f"Output JSON           : {OUTPUT_JSON}")
    print(f"Output CSV            : {OUTPUT_CSV}")
    print(f"Diagnostic JSON       : {DIAGNOSTIC_JSON}")
    print(f"Strict complete mode  : {strict_complete}")
    print("=" * 90)

    payloads, statuses = load_all_inputs()
    print_source_report(statuses)

    merged = build_merged(payloads, statuses, strict_complete)

    # Always write diagnostic output so a wrapper/user can see exactly why it stopped.
    atomic_write_json(DIAGNOSTIC_JSON, merged)

    # In partial mode, write headline outputs even with missing values.
    # In strict mode, write headline outputs only when everything is complete enough.
    if (not strict_complete) or merged["all_sources_complete"]:
        atomic_write_json(OUTPUT_JSON, merged)
        write_csv(OUTPUT_CSV, build_flat_csv(merged))
        wrote_headline_outputs = True
    else:
        wrote_headline_outputs = False

    print("Merge status.")
    print(f"All sources present   : {merged['all_sources_present']}")
    print(f"All sources complete  : {merged['all_sources_complete']}")
    print(f"Missing sources       : {', '.join(merged['missing_sources']) if merged['missing_sources'] else 'none'}")
    print(f"Incomplete sources    : {', '.join(merged['incomplete_sources']) if merged['incomplete_sources'] else 'none'}")
    print(f"Unreadable sources    : {', '.join(merged['unreadable_sources']) if merged['unreadable_sources'] else 'none'}")
    print(f"Wrote headline files  : {wrote_headline_outputs}")
    print(f"Wrote diagnostic JSON : {DIAGNOSTIC_JSON}")

    if wrote_headline_outputs:
        print(f"Saved JSON            : {OUTPUT_JSON}")
        print(f"Saved CSV             : {OUTPUT_CSV}")
        print(f"Cleaned rows          : {merged['formatted']['cleaned_rows']}")
        print(f"Distinct sites        : {merged['formatted']['distinct_sites']}")
        print(f"Date range start      : {merged['formatted']['date_range_start']}")
        print(f"Date range end        : {merged['formatted']['date_range_end']}")
        print(f"Total cleaned volume  : {merged['formatted']['total_cleaned_volume']}")
        print(f"Busiest site ID       : {merged['formatted']['busiest_site_id']}")
        print(f"Busiest site name     : {merged['formatted']['busiest_site_name']}")
        print(f"Busiest time bin      : {merged['formatted']['busiest_time_bin']}")
        print(f"Busiest day           : {merged['formatted']['busiest_day']}")
        print(f"AM peak share         : {merged['formatted']['am_peak_share']}")
        print(f"PM peak share         : {merged['formatted']['pm_peak_share']}")

    print("=" * 90)

    if strict_complete and not merged["all_sources_complete"]:
        print("Strict merge stopped because one or more required inputs are missing or incomplete.")
        print("This is intentional: wrappers should stop here instead of relaunching forever.")
        return 2

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        raise SystemExit(130)
