#!/usr/bin/env python3
r"""
generate_yearly_chart_ready.py

Builds chart-ready yearly output from the already-generated
yearly_totals.csv / yearly_totals_final.json.

Inputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\yearly_totals.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\yearly_totals_final.json

Outputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\yearly_chart_ready.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\yearly_chart_ready.json
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import duckdb


REPORT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")

INPUT_CSV = REPORT_DIR / "yearly_totals.csv"
INPUT_JSON = REPORT_DIR / "yearly_totals_final.json"

OUTPUT_CSV = REPORT_DIR / "yearly_chart_ready.csv"
OUTPUT_JSON = REPORT_DIR / "yearly_chart_ready.json"


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
        raise RuntimeError("yearly_totals_final.json indicates the build is not complete yet.")
    return payload


def build_rows() -> list[tuple]:
    con = duckdb.connect(database=":memory:")
    try:
        csv_path = str(INPUT_CSV).replace(chr(92), "/")
        sql = f"""
        WITH src AS (
            SELECT
                CAST(year AS INTEGER) AS year,
                CAST(month_total_volume AS DOUBLE) AS month_total_volume,
                CAST(days_loaded AS DOUBLE) AS days_loaded
            FROM read_csv_auto('{csv_path}', header=true)
        ),
        agg AS (
            SELECT
                year,
                SUM(month_total_volume) AS total_volume,
                SUM(days_loaded) AS days_loaded,
                CASE
                    WHEN SUM(days_loaded) IS NULL OR SUM(days_loaded) = 0 THEN NULL
                    ELSE SUM(month_total_volume) * 1.0 / SUM(days_loaded)
                END AS avg_daily_volume
            FROM src
            GROUP BY year
        )
        SELECT
            year,
            total_volume,
            days_loaded,
            avg_daily_volume
        FROM agg
        ORDER BY year
        """
        return con.execute(sql).fetchall()
    finally:
        con.close()


def write_csv(rows: list[tuple]) -> None:
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "year",
            "total_volume",
            "days_loaded",
            "avg_daily_volume",
            "formatted_total_volume",
            "formatted_avg_daily_volume",
        ])
        for year, total_volume, days_loaded, avg_daily_volume in rows:
            writer.writerow([
                year,
                total_volume,
                days_loaded,
                avg_daily_volume,
                fmt_int(total_volume),
                fmt_int(avg_daily_volume),
            ])


def write_json(rows: list[tuple], source_payload: dict) -> None:
    out_rows = []
    for year, total_volume, days_loaded, avg_daily_volume in rows:
        out_rows.append({
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
        "source_is_complete": source_payload.get("is_complete"),
        "date_range_start": source_payload.get("date_range_start"),
        "date_range_end": source_payload.get("date_range_end"),
        "rows": out_rows,
    }

    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main() -> None:
    print("=" * 90)
    print("GENERATING YEARLY CHART-READY OUTPUT")
    print("=" * 90)
    source_payload = ensure_input_ready()
    rows = build_rows()
    write_csv(rows)
    write_json(rows, source_payload)
    print(f"Rows written          : {len(rows)}")
    print("=" * 90)


if __name__ == "__main__":
    main()