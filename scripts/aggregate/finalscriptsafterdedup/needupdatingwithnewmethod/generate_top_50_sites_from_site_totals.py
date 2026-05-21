#!/usr/bin/env python3
r"""
generate_top_50_sites_from_site_totals.py

Builds a Top 50 SCATS site ranking from the already-generated site_totals.csv.

This script does NOT scan raw SCATS interval data.
It reads the precomputed site_totals.csv, aggregates total volume by site,
joins site names from the SCATS databases, and writes ranked outputs.

Inputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\site_totals.csv

Outputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\top_50_sites.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\top_50_sites.json
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import duckdb


MAIN_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats.duckdb"
CONT_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats_continuation.duckdb"
REC_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats_recovery.duckdb"

REPORT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")

INPUT_SITE_TOTALS_CSV = REPORT_DIR / "site_totals.csv"
INPUT_SITE_TOTALS_FINAL_JSON = REPORT_DIR / "site_totals_final.json"

OUTPUT_CSV = REPORT_DIR / "top_50_sites.csv"
OUTPUT_JSON = REPORT_DIR / "top_50_sites.json"


def fmt_int(value):
    if value is None:
        return "N/A"
    return f"{int(value):,}"


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Required input file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def ensure_input_ready() -> dict:
    if not INPUT_SITE_TOTALS_CSV.exists():
        raise FileNotFoundError(f"Required input CSV not found: {INPUT_SITE_TOTALS_CSV}")

    payload = load_json(INPUT_SITE_TOTALS_FINAL_JSON)
    if payload.get("is_complete") is False:
        raise RuntimeError("site_totals_final.json indicates the site totals build is not complete yet.")
    return payload


def connect_db() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(database=":memory:")
    con.execute(f"ATTACH '{MAIN_DB.replace(chr(92), '/')}' AS main_db")
    con.execute(f"ATTACH '{CONT_DB.replace(chr(92), '/')}' AS cont")
    con.execute(f"ATTACH '{REC_DB.replace(chr(92), '/')}' AS rec")
    return con


def build_top_50(con: duckdb.DuckDBPyConnection) -> list[tuple]:
    site_totals_csv_path = str(INPUT_SITE_TOTALS_CSV).replace(chr(92), "/")

    sql = f"""
    WITH site_monthly AS (
        SELECT
            CAST(scats_site AS INTEGER) AS scats_site,
            CAST(month_site_volume AS BIGINT) AS month_site_volume
        FROM read_csv_auto('{site_totals_csv_path}', header=true)
    ),
    site_totals AS (
        SELECT
            scats_site,
            SUM(month_site_volume) AS total_site_volume
        FROM site_monthly
        GROUP BY scats_site
    ),
    site_names_raw AS (
        SELECT scats_site, site_name FROM main_db.scats_site
        UNION ALL
        SELECT scats_site, site_name FROM cont.scats_site
        UNION ALL
        SELECT scats_site, site_name FROM rec.scats_site
    ),
    site_names AS (
        SELECT
            scats_site,
            MIN(site_name) AS site_name
        FROM site_names_raw
        GROUP BY scats_site
    ),
    ranked AS (
        SELECT
            st.scats_site,
            COALESCE(sn.site_name, CAST(st.scats_site AS VARCHAR)) AS site_name,
            st.total_site_volume,
            ROW_NUMBER() OVER (
                ORDER BY st.total_site_volume DESC, st.scats_site
            ) AS rank_position
        FROM site_totals st
        LEFT JOIN site_names sn
          ON st.scats_site = sn.scats_site
    )
    SELECT
        rank_position,
        scats_site,
        site_name,
        total_site_volume
    FROM ranked
    WHERE rank_position <= 50
    ORDER BY rank_position
    """
    return con.execute(sql).fetchall()


def write_csv(rows: list[tuple]) -> None:
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["rank", "scats_site", "site_name", "total_site_volume", "formatted_total_site_volume"])
        for rank_position, scats_site, site_name, total_site_volume in rows:
            writer.writerow([
                rank_position,
                scats_site,
                site_name,
                total_site_volume,
                fmt_int(total_site_volume),
            ])


def write_json(rows: list[tuple], source_payload: dict) -> None:
    top_50 = []
    for rank_position, scats_site, site_name, total_site_volume in rows:
        top_50.append({
            "rank": rank_position,
            "scats_site": scats_site,
            "site_name": site_name,
            "total_site_volume": total_site_volume,
            "formatted_total_site_volume": fmt_int(total_site_volume),
        })

    payload = {
        "generated_at_epoch": round(time.time(), 3),
        "generated_at_readable": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_csv": str(INPUT_SITE_TOTALS_CSV),
        "source_final_json": str(INPUT_SITE_TOTALS_FINAL_JSON),
        "source_is_complete": source_payload.get("is_complete"),
        "date_range_start": source_payload.get("date_range_start"),
        "date_range_end": source_payload.get("date_range_end"),
        "distinct_sites": source_payload.get("distinct_sites"),
        "top_50_count": len(top_50),
        "top_50_sites": top_50,
    }

    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main() -> None:
    print("=" * 90)
    print("GENERATING TOP 50 SITES FROM SITE TOTALS")
    print("=" * 90)
    print(f"Input CSV             : {INPUT_SITE_TOTALS_CSV}")
    print(f"Input final JSON      : {INPUT_SITE_TOTALS_FINAL_JSON}")
    print(f"Output CSV            : {OUTPUT_CSV}")
    print(f"Output JSON           : {OUTPUT_JSON}")
    print("=" * 90)

    source_payload = ensure_input_ready()

    con = connect_db()
    try:
        rows = build_top_50(con)
    finally:
        con.close()

    write_csv(rows)
    write_json(rows, source_payload)

    print(f"Top 50 rows written   : {len(rows)}")
    if rows:
        rank_position, scats_site, site_name, total_site_volume = rows[0]
        print(f"Top ranked site       : #{rank_position} | {scats_site} | {site_name} | {fmt_int(total_site_volume)}")
    print(f"Saved CSV             : {OUTPUT_CSV}")
    print(f"Saved JSON            : {OUTPUT_JSON}")
    print("=" * 90)


if __name__ == "__main__":
    main()