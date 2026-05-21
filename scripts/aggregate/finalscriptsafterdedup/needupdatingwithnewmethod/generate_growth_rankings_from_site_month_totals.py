#!/usr/bin/env python3
r"""
generate_growth_rankings_from_site_month_totals.py

Builds growth and decline rankings from the already-generated site_month_totals.csv.

This script does NOT scan raw SCATS interval data.
It reads the precomputed site_month_totals.csv, compares early vs late periods,
joins site names from the SCATS databases, and writes ranked outputs.

Inputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\site_month_totals.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\site_month_totals_final.json

Outputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\site_growth_rankings.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\site_growth_rankings.json
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

INPUT_SITE_MONTH_TOTALS_CSV = REPORT_DIR / "site_month_totals.csv"
INPUT_SITE_MONTH_TOTALS_FINAL_JSON = REPORT_DIR / "site_month_totals_final.json"

OUTPUT_CSV = REPORT_DIR / "site_growth_rankings.csv"
OUTPUT_JSON = REPORT_DIR / "site_growth_rankings.json"

MIN_BASELINE_VOLUME = 100000  # avoids silly percentage jumps from tiny baselines
TOP_N = 50


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
    if not INPUT_SITE_MONTH_TOTALS_CSV.exists():
        raise FileNotFoundError(f"Required input CSV not found: {INPUT_SITE_MONTH_TOTALS_CSV}")

    payload = load_json(INPUT_SITE_MONTH_TOTALS_FINAL_JSON)
    if payload.get("is_complete") is False:
        raise RuntimeError("site_month_totals_final.json indicates the site-month totals build is not complete yet.")
    return payload


def connect_db() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(database=":memory:")
    con.execute(f"ATTACH '{MAIN_DB.replace(chr(92), '/')}' AS main_db")
    con.execute(f"ATTACH '{CONT_DB.replace(chr(92), '/')}' AS cont")
    con.execute(f"ATTACH '{REC_DB.replace(chr(92), '/')}' AS rec")
    return con


def build_growth_rankings(con: duckdb.DuckDBPyConnection) -> tuple[list[tuple], list[tuple]]:
    csv_path = str(INPUT_SITE_MONTH_TOTALS_CSV).replace(chr(92), "/")

    sql = f"""
    WITH monthly AS (
        SELECT
            CAST(month_label AS VARCHAR) AS month_label,
            CAST(scats_site AS INTEGER) AS scats_site,
            CAST(month_site_volume AS BIGINT) AS month_site_volume
        FROM read_csv_auto('{csv_path}', header=true)
    ),
    month_bounds AS (
        SELECT
            MIN(month_label) AS first_month,
            MAX(month_label) AS last_month
        FROM monthly
    ),
    first_period AS (
        SELECT
            scats_site,
            AVG(month_site_volume) AS first_period_avg
        FROM monthly
        WHERE month_label IN (
            SELECT month_label
            FROM (
                SELECT DISTINCT month_label
                FROM monthly
                ORDER BY month_label
                LIMIT 12
            )
        )
        GROUP BY scats_site
    ),
    last_period AS (
        SELECT
            scats_site,
            AVG(month_site_volume) AS last_period_avg
        FROM monthly
        WHERE month_label IN (
            SELECT month_label
            FROM (
                SELECT DISTINCT month_label
                FROM monthly
                ORDER BY month_label DESC
                LIMIT 12
            )
        )
        GROUP BY scats_site
    ),
    joined AS (
        SELECT
            COALESCE(f.scats_site, l.scats_site) AS scats_site,
            f.first_period_avg,
            l.last_period_avg,
            (l.last_period_avg - f.first_period_avg) AS abs_change,
            CASE
                WHEN f.first_period_avg IS NULL OR f.first_period_avg = 0 THEN NULL
                ELSE (l.last_period_avg - f.first_period_avg) * 100.0 / f.first_period_avg
            END AS pct_change
        FROM first_period f
        FULL OUTER JOIN last_period l
          ON f.scats_site = l.scats_site
    ),
    filtered AS (
        SELECT *
        FROM joined
        WHERE first_period_avg IS NOT NULL
          AND last_period_avg IS NOT NULL
          AND first_period_avg >= {MIN_BASELINE_VOLUME}
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
            f.scats_site,
            COALESCE(sn.site_name, CAST(f.scats_site AS VARCHAR)) AS site_name,
            f.first_period_avg,
            f.last_period_avg,
            f.abs_change,
            f.pct_change
        FROM filtered f
        LEFT JOIN site_names sn
          ON f.scats_site = sn.scats_site
    )
    SELECT
        scats_site,
        site_name,
        first_period_avg,
        last_period_avg,
        abs_change,
        pct_change
    FROM enriched
    ORDER BY pct_change DESC, abs_change DESC, scats_site
    LIMIT {TOP_N}
    """
    fastest_growth = con.execute(sql).fetchall()

    decline_sql = f"""
    WITH monthly AS (
        SELECT
            CAST(month_label AS VARCHAR) AS month_label,
            CAST(scats_site AS INTEGER) AS scats_site,
            CAST(month_site_volume AS BIGINT) AS month_site_volume
        FROM read_csv_auto('{csv_path}', header=true)
    ),
    first_period AS (
        SELECT
            scats_site,
            AVG(month_site_volume) AS first_period_avg
        FROM monthly
        WHERE month_label IN (
            SELECT month_label
            FROM (
                SELECT DISTINCT month_label
                FROM monthly
                ORDER BY month_label
                LIMIT 12
            )
        )
        GROUP BY scats_site
    ),
    last_period AS (
        SELECT
            scats_site,
            AVG(month_site_volume) AS last_period_avg
        FROM monthly
        WHERE month_label IN (
            SELECT month_label
            FROM (
                SELECT DISTINCT month_label
                FROM monthly
                ORDER BY month_label DESC
                LIMIT 12
            )
        )
        GROUP BY scats_site
    ),
    joined AS (
        SELECT
            COALESCE(f.scats_site, l.scats_site) AS scats_site,
            f.first_period_avg,
            l.last_period_avg,
            (l.last_period_avg - f.first_period_avg) AS abs_change,
            CASE
                WHEN f.first_period_avg IS NULL OR f.first_period_avg = 0 THEN NULL
                ELSE (l.last_period_avg - f.first_period_avg) * 100.0 / f.first_period_avg
            END AS pct_change
        FROM first_period f
        FULL OUTER JOIN last_period l
          ON f.scats_site = l.scats_site
    ),
    filtered AS (
        SELECT *
        FROM joined
        WHERE first_period_avg IS NOT NULL
          AND last_period_avg IS NOT NULL
          AND first_period_avg >= {MIN_BASELINE_VOLUME}
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
            f.scats_site,
            COALESCE(sn.site_name, CAST(f.scats_site AS VARCHAR)) AS site_name,
            f.first_period_avg,
            f.last_period_avg,
            f.abs_change,
            f.pct_change
        FROM filtered f
        LEFT JOIN site_names sn
          ON f.scats_site = sn.scats_site
    )
    SELECT
        scats_site,
        site_name,
        first_period_avg,
        last_period_avg,
        abs_change,
        pct_change
    FROM enriched
    ORDER BY pct_change ASC, abs_change ASC, scats_site
    LIMIT {TOP_N}
    """
    biggest_declines = con.execute(decline_sql).fetchall()

    return fastest_growth, biggest_declines


def write_csv(fastest_growth: list[tuple], biggest_declines: list[tuple]) -> None:
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "group_name",
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

        for idx, row in enumerate(fastest_growth, start=1):
            scats_site, site_name, first_avg, last_avg, abs_change, pct_change = row
            writer.writerow([
                "fastest_growth",
                idx,
                scats_site,
                site_name,
                first_avg,
                last_avg,
                abs_change,
                pct_change,
                fmt_int(first_avg),
                fmt_int(last_avg),
                fmt_int(abs_change),
                fmt_pct(pct_change),
            ])

        for idx, row in enumerate(biggest_declines, start=1):
            scats_site, site_name, first_avg, last_avg, abs_change, pct_change = row
            writer.writerow([
                "biggest_decline",
                idx,
                scats_site,
                site_name,
                first_avg,
                last_avg,
                abs_change,
                pct_change,
                fmt_int(first_avg),
                fmt_int(last_avg),
                fmt_int(abs_change),
                fmt_pct(pct_change),
            ])


def write_json(fastest_growth: list[tuple], biggest_declines: list[tuple], source_payload: dict) -> None:
    growth_list = []
    for idx, row in enumerate(fastest_growth, start=1):
        scats_site, site_name, first_avg, last_avg, abs_change, pct_change = row
        growth_list.append({
            "rank": idx,
            "scats_site": scats_site,
            "site_name": site_name,
            "first_period_avg": first_avg,
            "last_period_avg": last_avg,
            "abs_change": abs_change,
            "pct_change": pct_change,
            "formatted_first_period_avg": fmt_int(first_avg),
            "formatted_last_period_avg": fmt_int(last_avg),
            "formatted_abs_change": fmt_int(abs_change),
            "formatted_pct_change": fmt_pct(pct_change),
        })

    decline_list = []
    for idx, row in enumerate(biggest_declines, start=1):
        scats_site, site_name, first_avg, last_avg, abs_change, pct_change = row
        decline_list.append({
            "rank": idx,
            "scats_site": scats_site,
            "site_name": site_name,
            "first_period_avg": first_avg,
            "last_period_avg": last_avg,
            "abs_change": abs_change,
            "pct_change": pct_change,
            "formatted_first_period_avg": fmt_int(first_avg),
            "formatted_last_period_avg": fmt_int(last_avg),
            "formatted_abs_change": fmt_int(abs_change),
            "formatted_pct_change": fmt_pct(pct_change),
        })

    payload = {
        "generated_at_epoch": round(time.time(), 3),
        "generated_at_readable": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_csv": str(INPUT_SITE_MONTH_TOTALS_CSV),
        "source_final_json": str(INPUT_SITE_MONTH_TOTALS_FINAL_JSON),
        "source_is_complete": source_payload.get("is_complete"),
        "date_range_start": source_payload.get("date_range_start"),
        "date_range_end": source_payload.get("date_range_end"),
        "min_baseline_volume": MIN_BASELINE_VOLUME,
        "top_n": TOP_N,
        "fastest_growth": growth_list,
        "biggest_declines": decline_list,
    }

    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main() -> None:
    print("=" * 90)
    print("GENERATING GROWTH RANKINGS FROM SITE-MONTH TOTALS")
    print("=" * 90)
    print(f"Input CSV             : {INPUT_SITE_MONTH_TOTALS_CSV}")
    print(f"Input final JSON      : {INPUT_SITE_MONTH_TOTALS_FINAL_JSON}")
    print(f"Output CSV            : {OUTPUT_CSV}")
    print(f"Output JSON           : {OUTPUT_JSON}")
    print(f"Minimum baseline      : {fmt_int(MIN_BASELINE_VOLUME)}")
    print(f"Top N                 : {TOP_N}")
    print("=" * 90)

    source_payload = ensure_input_ready()

    con = connect_db()
    try:
        fastest_growth, biggest_declines = build_growth_rankings(con)
    finally:
        con.close()

    write_csv(fastest_growth, biggest_declines)
    write_json(fastest_growth, biggest_declines, source_payload)

    print(f"Fastest growth rows   : {len(fastest_growth)}")
    print(f"Biggest decline rows  : {len(biggest_declines)}")

    if fastest_growth:
        row = fastest_growth[0]
        print(f"Top growth site       : {row[0]} | {row[1]} | {fmt_pct(row[5])}")

    if biggest_declines:
        row = biggest_declines[0]
        print(f"Top decline site      : {row[0]} | {row[1]} | {fmt_pct(row[5])}")

    print(f"Saved CSV             : {OUTPUT_CSV}")
    print(f"Saved JSON            : {OUTPUT_JSON}")
    print("=" * 90)


if __name__ == "__main__":
    main()