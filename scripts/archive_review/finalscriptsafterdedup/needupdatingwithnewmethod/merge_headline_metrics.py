#!/usr/bin/env python3
r"""
merge_headline_metrics.py

Merges the outputs from the chunked headline-metric scripts into:

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
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path


REPORT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")

INPUT_TOTAL_VOLUME = REPORT_DIR / "chunked_total_cleaned_volume_final.json"
INPUT_BUSIEST_SITE = REPORT_DIR / "chunked_busiest_site_final.json"
INPUT_BUSIEST_DAY = REPORT_DIR / "chunked_busiest_day_final.json"
INPUT_BUSIEST_TIME_BIN = REPORT_DIR / "chunked_busiest_time_bin_final.json"
INPUT_PEAK_SHARES = REPORT_DIR / "chunked_peak_shares_final.json"

OUTPUT_JSON = REPORT_DIR / "headline_metrics.json"
OUTPUT_CSV = REPORT_DIR / "headline_metrics.csv"


PRECOMPUTED_SUMMARY = {
    "cleaned_rows": 37877397311,
    "date_range_start": "2014-01-01",
    "date_range_end": "2026-04-07",
}


def fmt_int(value):
    if value is None:
        return "N/A"
    return f"{int(value):,}"


def fmt_pct(value):
    if value is None:
        return "N/A"
    return f"{float(value):.2f}%"


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Required input file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def ensure_complete(name: str, payload: dict) -> None:
    is_complete = payload.get("is_complete")
    if is_complete is False:
        raise RuntimeError(f"Input file for {name} is not complete yet.")
    if is_complete is None:
        print(f"Warning: {name} has no explicit is_complete flag.")


def write_csv(flat_metrics: dict) -> None:
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric_name", "metric_value"])
        for key, value in flat_metrics.items():
            writer.writerow([key, value])


def main() -> None:
    print("=" * 90)
    print("MERGING HEADLINE METRICS")
    print("=" * 90)
    print(f"Report directory      : {REPORT_DIR}")
    print(f"Output JSON           : {OUTPUT_JSON}")
    print(f"Output CSV            : {OUTPUT_CSV}")
    print("=" * 90)

    total_volume = load_json(INPUT_TOTAL_VOLUME)
    busiest_site = load_json(INPUT_BUSIEST_SITE)
    busiest_day = load_json(INPUT_BUSIEST_DAY)
    busiest_time_bin = load_json(INPUT_BUSIEST_TIME_BIN)
    peak_shares = load_json(INPUT_PEAK_SHARES)

    ensure_complete("total_cleaned_volume", total_volume)
    ensure_complete("busiest_site", busiest_site)
    ensure_complete("busiest_day", busiest_day)
    ensure_complete("busiest_time_bin", busiest_time_bin)
    ensure_complete("peak_shares", peak_shares)

    merged = {
        "generated_at_epoch": round(time.time(), 3),
        "generated_at_readable": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_files": {
            "total_cleaned_volume": str(INPUT_TOTAL_VOLUME),
            "busiest_site": str(INPUT_BUSIEST_SITE),
            "busiest_day": str(INPUT_BUSIEST_DAY),
            "busiest_time_bin": str(INPUT_BUSIEST_TIME_BIN),
            "peak_shares": str(INPUT_PEAK_SHARES),
        },
        "headline_metrics": {
            "cleaned_rows": PRECOMPUTED_SUMMARY["cleaned_rows"],
            "distinct_sites": busiest_site.get("distinct_sites"),  # fallback if ever added there
            "date_range_start": PRECOMPUTED_SUMMARY["date_range_start"],
            "date_range_end": PRECOMPUTED_SUMMARY["date_range_end"],
            "total_cleaned_volume": total_volume.get("total_cleaned_volume"),
            "busiest_site_id": busiest_site.get("busiest_site_id"),
            "busiest_site_name": busiest_site.get("busiest_site_name"),
            "busiest_time_bin": busiest_time_bin.get("busiest_time_bin"),
            "busiest_day": busiest_day.get("busiest_day"),
            "am_peak_share": peak_shares.get("am_peak_share"),
            "pm_peak_share": peak_shares.get("pm_peak_share"),
        },
        "formatted": {
            "cleaned_rows": fmt_int(PRECOMPUTED_SUMMARY["cleaned_rows"]),
            "distinct_sites": fmt_int(busiest_site.get("distinct_sites")) if busiest_site.get("distinct_sites") is not None else "N/A",
            "date_range_start": PRECOMPUTED_SUMMARY["date_range_start"],
            "date_range_end": PRECOMPUTED_SUMMARY["date_range_end"],
            "total_cleaned_volume": fmt_int(total_volume.get("total_cleaned_volume")),
            "busiest_site_id": str(busiest_site.get("busiest_site_id")) if busiest_site.get("busiest_site_id") is not None else "N/A",
            "busiest_site_name": str(busiest_site.get("busiest_site_name")) if busiest_site.get("busiest_site_name") is not None else "N/A",
            "busiest_time_bin": str(busiest_time_bin.get("busiest_time_bin")) if busiest_time_bin.get("busiest_time_bin") is not None else "N/A",
            "busiest_day": str(busiest_day.get("busiest_day")) if busiest_day.get("busiest_day") is not None else "N/A",
            "am_peak_share": fmt_pct(peak_shares.get("am_peak_share")),
            "pm_peak_share": fmt_pct(peak_shares.get("pm_peak_share")),
        },
    }

    # Optional support for a standalone distinct-sites file later.
    distinct_sites_file = REPORT_DIR / "distinct_sites.json"
    if distinct_sites_file.exists():
        distinct_sites_payload = load_json(distinct_sites_file)
        value = distinct_sites_payload.get("distinct_sites")
        merged["headline_metrics"]["distinct_sites"] = value
        merged["formatted"]["distinct_sites"] = fmt_int(value)

    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)

    flat_csv = {
        "generated_at_readable": merged["generated_at_readable"],
        "cleaned_rows": merged["formatted"]["cleaned_rows"],
        "distinct_sites": merged["formatted"]["distinct_sites"],
        "date_range_start": merged["formatted"]["date_range_start"],
        "date_range_end": merged["formatted"]["date_range_end"],
        "total_cleaned_volume": merged["formatted"]["total_cleaned_volume"],
        "busiest_site_id": merged["formatted"]["busiest_site_id"],
        "busiest_site_name": merged["formatted"]["busiest_site_name"],
        "busiest_time_bin": merged["formatted"]["busiest_time_bin"],
        "busiest_day": merged["formatted"]["busiest_day"],
        "am_peak_share": merged["formatted"]["am_peak_share"],
        "pm_peak_share": merged["formatted"]["pm_peak_share"],
    }
    write_csv(flat_csv)

    print("Merge complete.")
    print(f"Cleaned rows         : {merged['formatted']['cleaned_rows']}")
    print(f"Distinct sites       : {merged['formatted']['distinct_sites']}")
    print(f"Date range start     : {merged['formatted']['date_range_start']}")
    print(f"Date range end       : {merged['formatted']['date_range_end']}")
    print(f"Total cleaned volume : {merged['formatted']['total_cleaned_volume']}")
    print(f"Busiest site ID      : {merged['formatted']['busiest_site_id']}")
    print(f"Busiest site name    : {merged['formatted']['busiest_site_name']}")
    print(f"Busiest time bin     : {merged['formatted']['busiest_time_bin']}")
    print(f"Busiest day          : {merged['formatted']['busiest_day']}")
    print(f"AM peak share        : {merged['formatted']['am_peak_share']}")
    print(f"PM peak share        : {merged['formatted']['pm_peak_share']}")
    print(f"Saved JSON           : {OUTPUT_JSON}")
    print(f"Saved CSV            : {OUTPUT_CSV}")
    print("=" * 90)


if __name__ == "__main__":
    main()