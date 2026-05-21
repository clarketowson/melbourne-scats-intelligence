#!/usr/bin/env python3
r"""
generate_top_10_peak_time_bins.py

Builds the top 10 peak time bins from the already-generated
time_bin_profile.csv / time_bin_profile_final.json.

Inputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\time_bin_profile.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\time_bin_profile_final.json

Outputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\top_10_peak_time_bins.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\top_10_peak_time_bins.json
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import duckdb


REPORT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")

INPUT_CSV = REPORT_DIR / "time_bin_profile.csv"
INPUT_JSON = REPORT_DIR / "time_bin_profile_final.json"

OUTPUT_CSV = REPORT_DIR / "top_10_peak_time_bins.csv"
OUTPUT_JSON = REPORT_DIR / "top_10_peak_time_bins.json"

TOP_N = 10


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
    payload = load_json(INPUT_JSON)
    if payload.get("is_complete") is False:
        raise RuntimeError("time_bin_profile_final.json indicates the build is not complete yet.")
    return payload


def build_rows() -> list[tuple]:
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
        day_totals AS (
            SELECT SUM(days_loaded) AS total_days_loaded
            FROM (
                SELECT month_label, MAX(days_in_month_loaded) AS days_loaded
                FROM read_csv_auto('{csv_path}', header=true)
                GROUP BY month_label
            )
        ),
        agg AS (
            SELECT
                time_bin,
                SUM(month_time_bin_volume) AS total_volume
            FROM tb
            GROUP BY time_bin
        ),
        enriched AS (
            SELECT
                a.time_bin,
                a.total_volume,
                CASE
                    WHEN d.total_days_loaded IS NULL OR d.total_days_loaded = 0 THEN NULL
                    ELSE a.total_volume * 1.0 / d.total_days_loaded
                END AS avg_daily_volume
            FROM agg a
            CROSS JOIN day_totals d
        ),
        ranked AS (
            SELECT
                ROW_NUMBER() OVER (
                    ORDER BY avg_daily_volume DESC, time_bin
                ) AS rank_position,
                time_bin,
                total_volume,
                avg_daily_volume
            FROM enriched
        )
        SELECT
            rank_position,
            time_bin,
            total_volume,
            avg_daily_volume
        FROM ranked
        WHERE rank_position <= {TOP_N}
        ORDER BY rank_position
        """
        return con.execute(sql).fetchall()
    finally:
        con.close()


def write_csv(rows: list[tuple]) -> None:
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "rank",
            "time_bin",
            "total_volume",
            "avg_daily_volume",
            "formatted_total_volume",
            "formatted_avg_daily_volume",
        ])
        for rank_position, time_bin, total_volume, avg_daily_volume in rows:
            writer.writerow([
                rank_position,
                time_bin,
                total_volume,
                avg_daily_volume,
                fmt_int(total_volume),
                fmt_int(avg_daily_volume),
            ])


def write_json(rows: list[tuple], source_payload: dict) -> None:
    out_rows = []
    for rank_position, time_bin, total_volume, avg_daily_volume in rows:
        out_rows.append({
            "rank": rank_position,
            "time_bin": time_bin,
            "total_volume": total_volume,
            "avg_daily_volume": avg_daily_volume,
            "formatted_total_volume": fmt_int(total_volume),
            "formatted_avg_daily_volume": fmt_int(avg_daily_volume),
        })

    payload = {
        "generated_at_epoch": round(time.time(), 3),
        "generated_at_readable": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_csv": str(INPUT_CSV),
        "source_json": str(INPUT_JSON),
        "source_is_complete": source_payload.get("is_complete"),
        "date_range_start": source_payload.get("date_range_start"),
        "date_range_end": source_payload.get("date_range_end"),
        "top_n": TOP_N,
        "top_10_peak_time_bins": out_rows,
    }

    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main() -> None:
    print("=" * 90)
    print("GENERATING TOP 10 PEAK TIME BINS")
    print("=" * 90)
    source_payload = ensure_input_ready()
    rows = build_rows()
    write_csv(rows)
    write_json(rows, source_payload)
    print(f"Rows written          : {len(rows)}")
    if rows:
        print(f"Top peak bin          : #{rows[0][0]} | {rows[0][1]} | {fmt_int(rows[0][3])}")
    print("=" * 90)


if __name__ == "__main__":
    main()