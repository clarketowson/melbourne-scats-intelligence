#!/usr/bin/env python3
r"""
generate_monday_vs_friday_comparison.py

Builds a Monday vs Friday comparison from the already-generated
day_of_week_profile.csv.

Inputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\day_of_week_profile.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\day_of_week_profile_final.json

Outputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\monday_vs_friday_comparison.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\monday_vs_friday_comparison.json
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import duckdb


REPORT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")

INPUT_CSV = REPORT_DIR / "day_of_week_profile.csv"
INPUT_FINAL_JSON = REPORT_DIR / "day_of_week_profile_final.json"

OUTPUT_CSV = REPORT_DIR / "monday_vs_friday_comparison.csv"
OUTPUT_JSON = REPORT_DIR / "monday_vs_friday_comparison.json"


def fmt_int(value):
    if value is None:
        return "N/A"
    return f"{int(round(value)):,}"


def fmt_pct(value):
    if value is None:
        return "N/A"
    return f"{float(value):.2f}%"


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Required input file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def ensure_input_ready() -> dict:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Required input CSV not found: {INPUT_CSV}")

    payload = load_json(INPUT_FINAL_JSON)
    if payload.get("is_complete") is False:
        raise RuntimeError("day_of_week_profile_final.json indicates the build is not complete yet.")
    return payload


def build_comparison() -> dict:
    con = duckdb.connect(database=":memory:")
    try:
        csv_path = str(INPUT_CSV).replace(chr(92), "/")
        sql = f"""
        WITH daily AS (
            SELECT
                CAST(iso_dow AS INTEGER) AS iso_dow,
                CAST(day_name AS VARCHAR) AS day_name,
                CAST(day_total_volume AS BIGINT) AS day_total_volume,
                CAST(days_loaded AS BIGINT) AS days_loaded
            FROM read_csv_auto('{csv_path}', header=true)
        ),
        agg AS (
            SELECT
                iso_dow,
                MIN(day_name) AS day_name,
                SUM(day_total_volume) AS total_volume,
                SUM(days_loaded) AS total_days_loaded,
                CASE
                    WHEN SUM(days_loaded) IS NULL OR SUM(days_loaded) = 0 THEN NULL
                    ELSE SUM(day_total_volume) * 1.0 / SUM(days_loaded)
                END AS avg_daily_volume
            FROM daily
            GROUP BY iso_dow
        ),
        mon AS (
            SELECT * FROM agg WHERE iso_dow = 1
        ),
        fri AS (
            SELECT * FROM agg WHERE iso_dow = 5
        )
        SELECT
            mon.day_name,
            mon.total_volume,
            mon.total_days_loaded,
            mon.avg_daily_volume,
            fri.day_name,
            fri.total_volume,
            fri.total_days_loaded,
            fri.avg_daily_volume,
            (fri.avg_daily_volume - mon.avg_daily_volume) AS abs_diff,
            CASE
                WHEN mon.avg_daily_volume IS NULL OR mon.avg_daily_volume = 0 THEN NULL
                ELSE (fri.avg_daily_volume - mon.avg_daily_volume) * 100.0 / mon.avg_daily_volume
            END AS pct_diff_vs_monday
        FROM mon
        CROSS JOIN fri
        """
        row = con.execute(sql).fetchone()
    finally:
        con.close()

    if not row:
        raise RuntimeError("Could not build Monday vs Friday comparison.")

    return {
        "monday_day_name": row[0],
        "monday_total_volume": row[1],
        "monday_total_days": row[2],
        "monday_avg_daily_volume": row[3],
        "friday_day_name": row[4],
        "friday_total_volume": row[5],
        "friday_total_days": row[6],
        "friday_avg_daily_volume": row[7],
        "abs_diff": row[8],
        "pct_diff_vs_monday": row[9],
    }


def write_csv(result: dict) -> None:
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric_name", "metric_value"])
        for k, v in result.items():
            writer.writerow([k, v])
        writer.writerow(["formatted_monday_avg_daily_volume", fmt_int(result["monday_avg_daily_volume"])])
        writer.writerow(["formatted_friday_avg_daily_volume", fmt_int(result["friday_avg_daily_volume"])])
        writer.writerow(["formatted_abs_diff", fmt_int(result["abs_diff"])])
        writer.writerow(["formatted_pct_diff_vs_monday", fmt_pct(result["pct_diff_vs_monday"])])


def write_json(result: dict, source_payload: dict) -> None:
    payload = {
        "generated_at_epoch": round(time.time(), 3),
        "generated_at_readable": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_csv": str(INPUT_CSV),
        "source_final_json": str(INPUT_FINAL_JSON),
        "source_is_complete": source_payload.get("is_complete"),
        "date_range_start": source_payload.get("date_range_start"),
        "date_range_end": source_payload.get("date_range_end"),
        **result,
        "formatted": {
            "monday_avg_daily_volume": fmt_int(result["monday_avg_daily_volume"]),
            "friday_avg_daily_volume": fmt_int(result["friday_avg_daily_volume"]),
            "abs_diff": fmt_int(result["abs_diff"]),
            "pct_diff_vs_monday": fmt_pct(result["pct_diff_vs_monday"]),
        },
    }

    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main() -> None:
    print("=" * 90)
    print("GENERATING MONDAY VS FRIDAY COMPARISON")
    print("=" * 90)
    print(f"Input CSV             : {INPUT_CSV}")
    print(f"Input final JSON      : {INPUT_FINAL_JSON}")
    print(f"Output CSV            : {OUTPUT_CSV}")
    print(f"Output JSON           : {OUTPUT_JSON}")
    print("=" * 90)

    source_payload = ensure_input_ready()
    result = build_comparison()
    write_csv(result)
    write_json(result, source_payload)

    print(f"Monday avg/day        : {fmt_int(result['monday_avg_daily_volume'])}")
    print(f"Friday avg/day        : {fmt_int(result['friday_avg_daily_volume'])}")
    print(f"Difference            : {fmt_int(result['abs_diff'])}")
    print(f"% vs Monday           : {fmt_pct(result['pct_diff_vs_monday'])}")
    print("=" * 90)


if __name__ == "__main__":
    main()