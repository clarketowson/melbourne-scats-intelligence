#!/usr/bin/env python3
r"""
generate_top_20_quietest_days_from_daily_totals.py

Builds the top 20 quietest days from the already-generated daily_totals.csv.

Inputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\daily_totals.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\daily_totals_final.json

Outputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\top_20_quietest_days.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\top_20_quietest_days.json
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import duckdb


REPORT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")

INPUT_CSV = REPORT_DIR / "daily_totals.csv"
INPUT_FINAL_JSON = REPORT_DIR / "daily_totals_final.json"

OUTPUT_CSV = REPORT_DIR / "top_20_quietest_days.csv"
OUTPUT_JSON = REPORT_DIR / "top_20_quietest_days.json"

TOP_N = 20


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
        raise RuntimeError("daily_totals_final.json indicates the build is not complete yet.")
    return payload


def build_quietest_days() -> list[tuple]:
    con = duckdb.connect(database=":memory:")
    try:
        csv_path = str(INPUT_CSV).replace(chr(92), "/")
        sql = f"""
        WITH daily AS (
            SELECT
                CAST(count_date AS DATE) AS count_date,
                CAST(day_total_volume AS BIGINT) AS day_total_volume
            FROM read_csv_auto('{csv_path}', header=true)
        ),
        ranked AS (
            SELECT
                ROW_NUMBER() OVER (
                    ORDER BY day_total_volume ASC, count_date
                ) AS rank_position,
                count_date,
                day_total_volume
            FROM daily
        )
        SELECT
            rank_position,
            count_date,
            day_total_volume
        FROM ranked
        WHERE rank_position <= {TOP_N}
        ORDER BY rank_position
        """
        rows = con.execute(sql).fetchall()
    finally:
        con.close()
    return rows


def write_csv(rows: list[tuple]) -> None:
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["rank", "count_date", "day_total_volume", "formatted_day_total_volume"])
        for rank_position, count_date, day_total_volume in rows:
            writer.writerow([
                rank_position,
                count_date,
                day_total_volume,
                fmt_int(day_total_volume),
            ])


def write_json(rows: list[tuple], source_payload: dict) -> None:
    quiet_days = []
    for rank_position, count_date, day_total_volume in rows:
        quiet_days.append({
            "rank": rank_position,
            "count_date": str(count_date),
            "day_total_volume": day_total_volume,
            "formatted_day_total_volume": fmt_int(day_total_volume),
        })

    payload = {
        "generated_at_epoch": round(time.time(), 3),
        "generated_at_readable": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_csv": str(INPUT_CSV),
        "source_final_json": str(INPUT_FINAL_JSON),
        "source_is_complete": source_payload.get("is_complete"),
        "date_range_start": source_payload.get("date_range_start"),
        "date_range_end": source_payload.get("date_range_end"),
        "top_n": TOP_N,
        "top_20_quietest_days": quiet_days,
    }

    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main() -> None:
    print("=" * 90)
    print("GENERATING TOP 20 QUIETEST DAYS FROM DAILY TOTALS")
    print("=" * 90)
    print(f"Input CSV             : {INPUT_CSV}")
    print(f"Input final JSON      : {INPUT_FINAL_JSON}")
    print(f"Output CSV            : {OUTPUT_CSV}")
    print(f"Output JSON           : {OUTPUT_JSON}")
    print(f"Top N                 : {TOP_N}")
    print("=" * 90)

    source_payload = ensure_input_ready()
    rows = build_quietest_days()
    write_csv(rows)
    write_json(rows, source_payload)

    print(f"Rows written          : {len(rows)}")
    if rows:
        print(f"Quietest day          : #{rows[0][0]} | {rows[0][1]} | {fmt_int(rows[0][2])}")
    print("=" * 90)


if __name__ == "__main__":
    main()