#!/usr/bin/env python3
r"""
generate_top_10_years_by_avg_daily_volume.py

Builds the top 10 years by average daily volume from the already-generated
yearly_chart_ready.csv / yearly_chart_ready.json.

Inputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\yearly_chart_ready.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\yearly_chart_ready.json

Outputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\top_10_years_by_avg_daily_volume.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\top_10_years_by_avg_daily_volume.json
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import duckdb


REPORT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")

INPUT_CSV = REPORT_DIR / "yearly_chart_ready.csv"
INPUT_JSON = REPORT_DIR / "yearly_chart_ready.json"

OUTPUT_CSV = REPORT_DIR / "top_10_years_by_avg_daily_volume.csv"
OUTPUT_JSON = REPORT_DIR / "top_10_years_by_avg_daily_volume.json"

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
    return load_json(INPUT_JSON)


def build_rows() -> list[tuple]:
    con = duckdb.connect(database=":memory:")
    try:
        csv_path = str(INPUT_CSV).replace(chr(92), "/")
        sql = f"""
        WITH src AS (
            SELECT
                CAST(year AS INTEGER) AS year,
                CAST(total_volume AS DOUBLE) AS total_volume,
                CAST(days_loaded AS DOUBLE) AS days_loaded,
                CAST(avg_daily_volume AS DOUBLE) AS avg_daily_volume
            FROM read_csv_auto('{csv_path}', header=true)
        ),
        ranked AS (
            SELECT
                ROW_NUMBER() OVER (
                    ORDER BY avg_daily_volume DESC, year
                ) AS rank_position,
                year,
                total_volume,
                days_loaded,
                avg_daily_volume
            FROM src
        )
        SELECT
            rank_position,
            year,
            total_volume,
            days_loaded,
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
            "year",
            "total_volume",
            "days_loaded",
            "avg_daily_volume",
            "formatted_total_volume",
            "formatted_avg_daily_volume",
        ])
        for rank_position, year, total_volume, days_loaded, avg_daily_volume in rows:
            writer.writerow([
                rank_position,
                year,
                total_volume,
                days_loaded,
                avg_daily_volume,
                fmt_int(total_volume),
                fmt_int(avg_daily_volume),
            ])


def write_json(rows: list[tuple], source_payload: dict) -> None:
    out_rows = []
    for rank_position, year, total_volume, days_loaded, avg_daily_volume in rows:
        out_rows.append({
            "rank": rank_position,
            "year": year,
            "total_volume": total_volume,
            "days_loaded": days_loaded,
            "avg_daily_volume": avg_daily_volume,
            "formatted_total_volume": fmt_int(total_volume),
            "formatted_avg_daily_volume": fmt_int(avg_daily_volume),
        })

    payload = {
        "generated_at_epoch": round(time.time(), 3),
        "generated_at_readable": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_csv": str(INPUT_CSV),
        "source_json": str(INPUT_JSON),
        "top_n": TOP_N,
        "rows": out_rows,
        "date_range_start": source_payload.get("date_range_start"),
        "date_range_end": source_payload.get("date_range_end"),
    }

    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main() -> None:
    print("=" * 90)
    print("GENERATING TOP 10 YEARS BY AVG DAILY VOLUME")
    print("=" * 90)
    source_payload = ensure_input_ready()
    rows = build_rows()
    write_csv(rows)
    write_json(rows, source_payload)
    print(f"Rows written          : {len(rows)}")
    if rows:
        print(f"Top year              : #{rows[0][0]} | {rows[0][1]} | {fmt_int(rows[0][4])}")
    print("=" * 90)


if __name__ == "__main__":
    main()