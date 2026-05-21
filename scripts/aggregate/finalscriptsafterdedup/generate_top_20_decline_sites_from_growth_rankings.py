#!/usr/bin/env python3
r"""
generate_top_20_decline_sites_from_growth_rankings.py

Builds the top 20 declining sites from the already-generated
site_growth_rankings.csv / site_growth_rankings.json.

Inputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\site_growth_rankings.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\site_growth_rankings.json

Outputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\top_20_decline_sites.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\top_20_decline_sites.json
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import duckdb


REPORT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")

INPUT_CSV = REPORT_DIR / "site_growth_rankings.csv"
INPUT_JSON = REPORT_DIR / "site_growth_rankings.json"

OUTPUT_CSV = REPORT_DIR / "top_20_decline_sites.csv"
OUTPUT_JSON = REPORT_DIR / "top_20_decline_sites.json"

TOP_N = 20


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Required input file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def ensure_input_ready() -> dict:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Required input CSV not found: {INPUT_CSV}")
    return load_json(INPUT_JSON)


def build_top_declines() -> list[tuple]:
    con = duckdb.connect(database=":memory:")
    try:
        csv_path = str(INPUT_CSV).replace(chr(92), "/")
        sql = f"""
        WITH src AS (
            SELECT
                CAST(group_name AS VARCHAR) AS group_name,
                CAST(rank AS INTEGER) AS src_rank,
                CAST(scats_site AS INTEGER) AS scats_site,
                CAST(site_name AS VARCHAR) AS site_name,
                CAST(first_period_avg AS DOUBLE) AS first_period_avg,
                CAST(last_period_avg AS DOUBLE) AS last_period_avg,
                CAST(abs_change AS DOUBLE) AS abs_change,
                CAST(pct_change AS DOUBLE) AS pct_change
            FROM read_csv_auto('{csv_path}', header=true)
        ),
        decline AS (
            SELECT *
            FROM src
            WHERE group_name = 'biggest_decline'
        ),
        ranked AS (
            SELECT
                ROW_NUMBER() OVER (
                    ORDER BY pct_change ASC, abs_change ASC, scats_site
                ) AS rank_position,
                scats_site,
                site_name,
                first_period_avg,
                last_period_avg,
                abs_change,
                pct_change
            FROM decline
        )
        SELECT
            rank_position,
            scats_site,
            site_name,
            first_period_avg,
            last_period_avg,
            abs_change,
            pct_change
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
            "scats_site",
            "site_name",
            "first_period_avg",
            "last_period_avg",
            "abs_change",
            "pct_change",
            "formatted_first_period_avg",
            "formatted_last_period_avg",
            "formatted_abs_change",
            "formatted_pct_change",
        ])
        for rank_position, scats_site, site_name, first_avg, last_avg, abs_change, pct_change in rows:
            writer.writerow([
                rank_position,
                scats_site,
                site_name,
                first_avg,
                last_avg,
                abs_change,
                pct_change,
                f"{int(round(first_avg)):,}" if first_avg is not None else "N/A",
                f"{int(round(last_avg)):,}" if last_avg is not None else "N/A",
                f"{int(round(abs_change)):,}" if abs_change is not None else "N/A",
                f"{float(pct_change):.2f}%" if pct_change is not None else "N/A",
            ])


def write_json(rows: list[tuple], source_payload: dict) -> None:
    out_rows = []
    for rank_position, scats_site, site_name, first_avg, last_avg, abs_change, pct_change in rows:
        out_rows.append({
            "rank": rank_position,
            "scats_site": scats_site,
            "site_name": site_name,
            "first_period_avg": first_avg,
            "last_period_avg": last_avg,
            "abs_change": abs_change,
            "pct_change": pct_change,
            "formatted_first_period_avg": f"{int(round(first_avg)):,}" if first_avg is not None else "N/A",
            "formatted_last_period_avg": f"{int(round(last_avg)):,}" if last_avg is not None else "N/A",
            "formatted_abs_change": f"{int(round(abs_change)):,}" if abs_change is not None else "N/A",
            "formatted_pct_change": f"{float(pct_change):.2f}%" if pct_change is not None else "N/A",
        })

    payload = {
        "generated_at_epoch": round(time.time(), 3),
        "generated_at_readable": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_csv": str(INPUT_CSV),
        "source_json": str(INPUT_JSON),
        "top_n": TOP_N,
        "date_range_start": source_payload.get("date_range_start"),
        "date_range_end": source_payload.get("date_range_end"),
        "top_20_decline_sites": out_rows,
    }

    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main() -> None:
    print("=" * 90)
    print("GENERATING TOP 20 DECLINE SITES")
    print("=" * 90)
    source_payload = ensure_input_ready()
    rows = build_top_declines()
    write_csv(rows)
    write_json(rows, source_payload)
    print(f"Rows written          : {len(rows)}")
    if rows:
        print(f"Top decline site      : #{rows[0][0]} | {rows[0][1]} | {rows[0][2]}")
    print("=" * 90)


if __name__ == "__main__":
    main()