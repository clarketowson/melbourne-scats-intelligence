#!/usr/bin/env python3
r"""
generate_peak_hour_summary.py

Builds a peak-hour summary from the already-generated time_bin_profile.csv.

Inputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\time_bin_profile.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\time_bin_profile_final.json

Outputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\peak_hour_summary.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\peak_hour_summary.json
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import duckdb


REPORT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")

INPUT_CSV = REPORT_DIR / "time_bin_profile.csv"
INPUT_FINAL_JSON = REPORT_DIR / "time_bin_profile_final.json"

OUTPUT_CSV = REPORT_DIR / "peak_hour_summary.csv"
OUTPUT_JSON = REPORT_DIR / "peak_hour_summary.json"


def fmt_int(value):
    if value is None:
        return "N/A"
    return f"{int(round(value)):,}"


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
        raise RuntimeError("time_bin_profile_final.json indicates the build is not complete yet.")
    return payload


def build_peak_summary() -> dict:
    con = duckdb.connect(database=":memory:")
    try:
        csv_path = str(INPUT_CSV).replace(chr(92), "/")
        sql = f"""
        WITH tb AS (
            SELECT
                CAST(time_bin AS VARCHAR) AS time_bin,
                CAST(month_time_bin_volume AS BIGINT) AS month_time_bin_volume,
                CAST(days_in_month_loaded AS BIGINT) AS days_in_month_loaded
            FROM read_csv_auto('{csv_path}', header=true)
        ),
        agg AS (
            SELECT
                time_bin,
                SUM(month_time_bin_volume) AS total_volume
            FROM tb
            GROUP BY time_bin
        ),
        total_days AS (
            SELECT SUM(days_loaded) AS total_days_loaded
            FROM (
                SELECT month_label, MAX(days_in_month_loaded) AS days_loaded
                FROM read_csv_auto('{csv_path}', header=true)
                GROUP BY month_label
            )
        ),
        enriched AS (
            SELECT
                agg.time_bin,
                agg.total_volume,
                CASE
                    WHEN total_days.total_days_loaded IS NULL OR total_days.total_days_loaded = 0 THEN NULL
                    ELSE agg.total_volume * 1.0 / total_days.total_days_loaded
                END AS avg_daily_volume
            FROM agg
            CROSS JOIN total_days
        ),
        overall_best AS (
            SELECT *
            FROM enriched
            ORDER BY total_volume DESC, time_bin
            LIMIT 1
        ),
        am_best AS (
            SELECT *
            FROM enriched
            WHERE time_bin >= '07:00' AND time_bin < '10:00'
            ORDER BY total_volume DESC, time_bin
            LIMIT 1
        ),
        pm_best AS (
            SELECT *
            FROM enriched
            WHERE time_bin >= '16:00' AND time_bin < '19:00'
            ORDER BY total_volume DESC, time_bin
            LIMIT 1
        )
        SELECT
            overall_best.time_bin,
            overall_best.total_volume,
            overall_best.avg_daily_volume,
            am_best.time_bin,
            am_best.total_volume,
            am_best.avg_daily_volume,
            pm_best.time_bin,
            pm_best.total_volume,
            pm_best.avg_daily_volume
        FROM overall_best
        CROSS JOIN am_best
        CROSS JOIN pm_best
        """
        row = con.execute(sql).fetchone()
    finally:
        con.close()

    if not row:
        raise RuntimeError("Could not build peak hour summary.")

    return {
        "overall_peak_time_bin": row[0],
        "overall_peak_total_volume": row[1],
        "overall_peak_avg_daily_volume": row[2],
        "am_peak_time_bin": row[3],
        "am_peak_total_volume": row[4],
        "am_peak_avg_daily_volume": row[5],
        "pm_peak_time_bin": row[6],
        "pm_peak_total_volume": row[7],
        "pm_peak_avg_daily_volume": row[8],
    }


def write_csv(result: dict) -> None:
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric_name", "metric_value"])
        for k, v in result.items():
            writer.writerow([k, v])
        writer.writerow(["formatted_overall_peak_total_volume", fmt_int(result["overall_peak_total_volume"])])
        writer.writerow(["formatted_overall_peak_avg_daily_volume", fmt_int(result["overall_peak_avg_daily_volume"])])
        writer.writerow(["formatted_am_peak_total_volume", fmt_int(result["am_peak_total_volume"])])
        writer.writerow(["formatted_am_peak_avg_daily_volume", fmt_int(result["am_peak_avg_daily_volume"])])
        writer.writerow(["formatted_pm_peak_total_volume", fmt_int(result["pm_peak_total_volume"])])
        writer.writerow(["formatted_pm_peak_avg_daily_volume", fmt_int(result["pm_peak_avg_daily_volume"])])


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
            "overall_peak_total_volume": fmt_int(result["overall_peak_total_volume"]),
            "overall_peak_avg_daily_volume": fmt_int(result["overall_peak_avg_daily_volume"]),
            "am_peak_total_volume": fmt_int(result["am_peak_total_volume"]),
            "am_peak_avg_daily_volume": fmt_int(result["am_peak_avg_daily_volume"]),
            "pm_peak_total_volume": fmt_int(result["pm_peak_total_volume"]),
            "pm_peak_avg_daily_volume": fmt_int(result["pm_peak_avg_daily_volume"]),
        },
    }

    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main() -> None:
    print("=" * 90)
    print("GENERATING PEAK HOUR SUMMARY")
    print("=" * 90)
    print(f"Input CSV             : {INPUT_CSV}")
    print(f"Input final JSON      : {INPUT_FINAL_JSON}")
    print(f"Output CSV            : {OUTPUT_CSV}")
    print(f"Output JSON           : {OUTPUT_JSON}")
    print("=" * 90)

    source_payload = ensure_input_ready()
    result = build_peak_summary()
    write_csv(result)
    write_json(result, source_payload)

    print(f"Overall peak          : {result['overall_peak_time_bin']} | {fmt_int(result['overall_peak_avg_daily_volume'])}")
    print(f"AM peak               : {result['am_peak_time_bin']} | {fmt_int(result['am_peak_avg_daily_volume'])}")
    print(f"PM peak               : {result['pm_peak_time_bin']} | {fmt_int(result['pm_peak_avg_daily_volume'])}")
    print("=" * 90)


if __name__ == "__main__":
    main()