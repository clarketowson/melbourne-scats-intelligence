#!/usr/bin/env python3
r"""
generate_top_10_sites_by_month_variability.py

Builds the top 10 sites by month-to-month variability from the already-generated
site_month_totals.csv / site_month_totals_final.json.

Inputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\site_month_totals.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\site_month_totals_final.json

Outputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\top_10_sites_by_month_variability.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\top_10_sites_by_month_variability.json
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

INPUT_CSV = REPORT_DIR / "site_month_totals.csv"
INPUT_JSON = REPORT_DIR / "site_month_totals_final.json"

OUTPUT_CSV = REPORT_DIR / "top_10_sites_by_month_variability.csv"
OUTPUT_JSON = REPORT_DIR / "top_10_sites_by_month_variability.json"

TOP_N = 10
MIN_MONTHS = 12


def fmt_int(value):
    if value is None:
        return "N/A"
    return f"{int(round(value)):,}"


def fmt_float(value):
    if value is None:
        return "N/A"
    return f"{float(value):.2f}"


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Required input file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def ensure_input_ready() -> dict:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Required input CSV not found: {INPUT_CSV}")
    return load_json(INPUT_JSON)


def connect_db() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(database=":memory:")
    con.execute(f"ATTACH '{MAIN_DB.replace(chr(92), '/')}' AS main_db")
    con.execute(f"ATTACH '{CONT_DB.replace(chr(92), '/')}' AS cont")
    con.execute(f"ATTACH '{REC_DB.replace(chr(92), '/')}' AS rec")
    return con


def build_rows(con: duckdb.DuckDBPyConnection) -> list[tuple]:
    csv_path = str(INPUT_CSV).replace(chr(92), "/")
    sql = f"""
    WITH src AS (
        SELECT
            CAST(scats_site AS INTEGER) AS scats_site,
            CAST(month_site_volume AS DOUBLE) AS month_site_volume
        FROM read_csv_auto('{csv_path}', header=true)
    ),
    agg AS (
        SELECT
            scats_site,
            COUNT(*) AS months_present,
            AVG(month_site_volume) AS avg_month_volume,
            STDDEV_SAMP(month_site_volume) AS stddev_month_volume,
            MIN(month_site_volume) AS min_month_volume,
            MAX(month_site_volume) AS max_month_volume
        FROM src
        GROUP BY scats_site
        HAVING COUNT(*) >= {MIN_MONTHS}
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
    enriched AS (
        SELECT
            a.scats_site,
            COALESCE(sn.site_name, CAST(a.scats_site AS VARCHAR)) AS site_name,
            a.months_present,
            a.avg_month_volume,
            a.stddev_month_volume,
            a.min_month_volume,
            a.max_month_volume,
            CASE
                WHEN a.avg_month_volume IS NULL OR a.avg_month_volume = 0 THEN NULL
                ELSE a.stddev_month_volume / a.avg_month_volume
            END AS coeff_variation
        FROM agg a
        LEFT JOIN site_names sn
          ON a.scats_site = sn.scats_site
    ),
    ranked AS (
        SELECT
            ROW_NUMBER() OVER (
                ORDER BY coeff_variation DESC, stddev_month_volume DESC, scats_site
            ) AS rank_position,
            scats_site,
            site_name,
            months_present,
            avg_month_volume,
            stddev_month_volume,
            min_month_volume,
            max_month_volume,
            coeff_variation
        FROM enriched
    )
    SELECT
        rank_position,
        scats_site,
        site_name,
        months_present,
        avg_month_volume,
        stddev_month_volume,
        min_month_volume,
        max_month_volume,
        coeff_variation
    FROM ranked
    WHERE rank_position <= {TOP_N}
    ORDER BY rank_position
    """
    return con.execute(sql).fetchall()


def write_csv(rows: list[tuple]) -> None:
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "rank",
            "scats_site",
            "site_name",
            "months_present",
            "avg_month_volume",
            "stddev_month_volume",
            "min_month_volume",
            "max_month_volume",
            "coeff_variation",
            "formatted_avg_month_volume",
            "formatted_stddev_month_volume",
            "formatted_min_month_volume",
            "formatted_max_month_volume",
            "formatted_coeff_variation",
        ])
        for row in rows:
            (
                rank_position,
                scats_site,
                site_name,
                months_present,
                avg_month_volume,
                stddev_month_volume,
                min_month_volume,
                max_month_volume,
                coeff_variation,
            ) = row

            writer.writerow([
                rank_position,
                scats_site,
                site_name,
                months_present,
                avg_month_volume,
                stddev_month_volume,
                min_month_volume,
                max_month_volume,
                coeff_variation,
                fmt_int(avg_month_volume),
                fmt_int(stddev_month_volume),
                fmt_int(min_month_volume),
                fmt_int(max_month_volume),
                fmt_float(coeff_variation),
            ])


def write_json(rows: list[tuple], source_payload: dict) -> None:
    out_rows = []
    for row in rows:
        (
            rank_position,
            scats_site,
            site_name,
            months_present,
            avg_month_volume,
            stddev_month_volume,
            min_month_volume,
            max_month_volume,
            coeff_variation,
        ) = row

        out_rows.append({
            "rank": rank_position,
            "scats_site": scats_site,
            "site_name": site_name,
            "months_present": months_present,
            "avg_month_volume": avg_month_volume,
            "stddev_month_volume": stddev_month_volume,
            "min_month_volume": min_month_volume,
            "max_month_volume": max_month_volume,
            "coeff_variation": coeff_variation,
            "formatted_avg_month_volume": fmt_int(avg_month_volume),
            "formatted_stddev_month_volume": fmt_int(stddev_month_volume),
            "formatted_min_month_volume": fmt_int(min_month_volume),
            "formatted_max_month_volume": fmt_int(max_month_volume),
            "formatted_coeff_variation": fmt_float(coeff_variation),
        })

    payload = {
        "generated_at_epoch": round(time.time(), 3),
        "generated_at_readable": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_csv": str(INPUT_CSV),
        "source_json": str(INPUT_JSON),
        "date_range_start": source_payload.get("date_range_start"),
        "date_range_end": source_payload.get("date_range_end"),
        "min_months": MIN_MONTHS,
        "top_n": TOP_N,
        "top_10_sites_by_month_variability": out_rows,
    }

    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main() -> None:
    print("=" * 90)
    print("GENERATING TOP 10 SITES BY MONTH VARIABILITY")
    print("=" * 90)

    source_payload = ensure_input_ready()
    con = connect_db()
    try:
        rows = build_rows(con)
    finally:
        con.close()

    write_csv(rows)
    write_json(rows, source_payload)

    print(f"Rows written          : {len(rows)}")
    if rows:
        print(f"Top variable site     : #{rows[0][0]} | {rows[0][1]} | {rows[0][2]}")
    print("=" * 90)


if __name__ == "__main__":
    main()