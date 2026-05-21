#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd


DEFAULT_ORIGINAL_DB = Path(r"A:\TrafficAnalytics\DATA\SCATS\scats.duckdb")
DEFAULT_CONTINUATION_DB = Path(r"A:\TrafficAnalytics\DATA\SCATS\scats_continuation.duckdb")
DEFAULT_RECOVERY_DB = Path(r"A:\TrafficAnalytics\DATA\SCATS\scats_recovery.duckdb")
DEFAULT_TEMP_DIR = Path(r"C:\TrafficAnalyticsTemp")
DEFAULT_OUTDIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\scats_unified_summary_chunked")


def parse_args():
    p = argparse.ArgumentParser(description="Chunked unified SCATS clean summary with progress.")
    p.add_argument("--original-db", type=Path, default=DEFAULT_ORIGINAL_DB)
    p.add_argument("--continuation-db", type=Path, default=DEFAULT_CONTINUATION_DB)
    p.add_argument("--recovery-db", type=Path, default=DEFAULT_RECOVERY_DB)
    p.add_argument("--temp-dir", type=Path, default=DEFAULT_TEMP_DIR)
    p.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)

    p.add_argument("--threads", type=int, default=3)
    p.add_argument("--memory-limit", default="40GB")
    p.add_argument("--max-temp-directory-size", default="160GiB")

    return p.parse_args()


def ensure_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def configure_duckdb(con, args):
    temp_dir = str(args.temp_dir)
    con.execute(f"PRAGMA threads={args.threads}")
    con.execute(f"PRAGMA memory_limit='{args.memory_limit}'")
    con.execute(f"PRAGMA temp_directory='{temp_dir}'")
    con.execute("SET preserve_insertion_order=false")
    con.execute(f"SET max_temp_directory_size='{args.max_temp_directory_size}'")


def attach_databases(con, args):
    con.execute(f"ATTACH '{args.original_db}' AS orig")
    con.execute(f"ATTACH '{args.continuation_db}' AS cont")
    con.execute(f"ATTACH '{args.recovery_db}' AS rec")


def validate_required_objects(con) -> None:
    checks = [
        ("orig.scats_clean", "SELECT 1 FROM orig.scats_clean LIMIT 1"),
        ("cont.scats_clean", "SELECT 1 FROM cont.scats_clean LIMIT 1"),
        ("rec.scats_clean", "SELECT 1 FROM rec.scats_clean LIMIT 1"),
    ]
    for label, sql in checks:
        try:
            con.execute(sql)
        except Exception as e:
            raise RuntimeError(f"Required object missing or unreadable: {label}: {e}") from e


def create_unified_view(con):
    con.execute("""
    CREATE OR REPLACE TEMP VIEW scats_all_clean_union AS

    SELECT
        scats_site, count_date, detector, region_code, source_file_id,
        interval_index, time_bin, volume_15m,
        2 AS source_priority,
        'orig' AS source_db
    FROM orig.scats_clean

    UNION ALL

    SELECT
        scats_site, count_date, detector, region_code, source_file_id,
        interval_index, time_bin, volume_15m,
        3 AS source_priority,
        'cont' AS source_db
    FROM cont.scats_clean

    UNION ALL

    SELECT
        scats_site, count_date, detector, region_code, source_file_id,
        interval_index, time_bin, volume_15m,
        1 AS source_priority,
        'rec' AS source_db
    FROM rec.scats_clean
    """)


def get_global_date_range(con):
    row = con.execute("""
        SELECT
            MIN(count_date) AS min_date,
            MAX(count_date) AS max_date
        FROM (
            SELECT MIN(count_date) AS count_date FROM orig.scats_clean
            UNION ALL
            SELECT MIN(count_date) AS count_date FROM cont.scats_clean
            UNION ALL
            SELECT MIN(count_date) AS count_date FROM rec.scats_clean
        )
    """).fetchone()

    row2 = con.execute("""
        SELECT
            MIN(count_date) AS min_date,
            MAX(count_date) AS max_date
        FROM (
            SELECT MAX(count_date) AS count_date FROM orig.scats_clean
            UNION ALL
            SELECT MAX(count_date) AS count_date FROM cont.scats_clean
            UNION ALL
            SELECT MAX(count_date) AS count_date FROM rec.scats_clean
        )
    """).fetchone()

    min_date = row[0]
    max_date = row2[1]
    if min_date is None or max_date is None:
        raise RuntimeError("Could not determine global date range.")
    return min_date, max_date


def month_starts(start_date: date, end_date: date):
    months = []
    y, m = start_date.year, start_date.month
    cur = date(y, m, 1)
    while cur <= end_date:
        months.append(cur)
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)
    return months


def month_end(month_start: date) -> date:
    if month_start.month == 12:
        next_month = date(month_start.year + 1, 1, 1)
    else:
        next_month = date(month_start.year, month_start.month + 1, 1)
    return pd.Timestamp(next_month) - pd.Timedelta(days=1)


def query_month_summary(con, start_d: date, end_d: date):
    sql = f"""
    WITH month_union AS (
        SELECT *
        FROM scats_all_clean_union
        WHERE count_date BETWEEN DATE '{start_d}' AND DATE '{end_d}'
    ),
    month_dedup AS (
        SELECT *
        EXCLUDE (rn)
        FROM (
            SELECT *,
                   ROW_NUMBER() OVER (
                       PARTITION BY scats_site, count_date, detector, interval_index
                       ORDER BY source_priority, source_db
                   ) AS rn
            FROM month_union
        )
        WHERE rn = 1
    )
    SELECT
        COUNT(*) AS rows,
        COUNT(*) FILTER (WHERE volume_15m IS NULL) AS null_rows,
        COUNT(*) FILTER (WHERE volume_15m < 0) AS negative_rows,
        MIN(count_date) AS min_date,
        MAX(count_date) AS max_date
    FROM month_dedup
    """
    return con.execute(sql).fetchone()


def main():
    args = parse_args()

    for path, label in [
        (args.original_db, "Original DB"),
        (args.continuation_db, "Continuation DB"),
        (args.recovery_db, "Recovery DB"),
    ]:
        ensure_exists(path, label)

    args.temp_dir.mkdir(parents=True, exist_ok=True)
    args.outdir.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(":memory:")

    try:
        configure_duckdb(con, args)
        attach_databases(con, args)
        validate_required_objects(con)
        create_unified_view(con)

        min_date, max_date = get_global_date_range(con)
        months = month_starts(min_date, max_date)
        total_months = len(months)

        monthly_rows = []
        total_rows = 0
        total_null_rows = 0
        total_negative_rows = 0
        global_min = None
        global_max = None

        started = time.time()

        print(f"Global date range: {min_date} to {max_date}")
        print(f"Months to process: {total_months}")

        for i, m in enumerate(months, start=1):
            mend = month_end(m)
            if mend.date() > max_date:
                mend = pd.Timestamp(max_date)

            row = query_month_summary(con, m, mend.date())

            rows = int(row[0] or 0)
            null_rows = int(row[1] or 0)
            negative_rows = int(row[2] or 0)
            min_d = row[3]
            max_d = row[4]

            total_rows += rows
            total_null_rows += null_rows
            total_negative_rows += negative_rows

            if min_d is not None:
                global_min = min_d if global_min is None else min(global_min, min_d)
            if max_d is not None:
                global_max = max_d if global_max is None else max(global_max, max_d)

            monthly_rows.append({
                "month_start": m,
                "month_end": mend.date(),
                "rows": rows,
                "null_rows": null_rows,
                "negative_rows": negative_rows,
                "min_date": min_d,
                "max_date": max_d,
            })

            elapsed = time.time() - started
            pct = i / total_months * 100.0
            avg_sec = elapsed / i
            eta_sec = avg_sec * (total_months - i)

            print(
                f"[{i}/{total_months}] {pct:5.1f}%  "
                f"{m} to {mend.date()}  "
                f"rows={rows:,}  nulls={null_rows:,}  neg={negative_rows:,}  "
                f"elapsed={elapsed/60:.1f} min  eta={eta_sec/60:.1f} min"
            )

        monthly_df = pd.DataFrame(monthly_rows)
        monthly_csv = args.outdir / "monthly_unified_clean_summary.csv"
        monthly_df.to_csv(monthly_csv, index=False)

        final_summary = pd.DataFrame([{
            "rows": total_rows,
            "null_rows": total_null_rows,
            "negative_rows": total_negative_rows,
            "min_date": global_min,
            "max_date": global_max,
        }])
        summary_csv = args.outdir / "unified_clean_summary.csv"
        final_summary.to_csv(summary_csv, index=False)

        print("\n=== Unified Clean Summary ===")
        print(f"rows          = {total_rows:,}")
        print(f"null_rows     = {total_null_rows:,}")
        print(f"negative_rows = {total_negative_rows:,}")
        print(f"min_date      = {global_min}")
        print(f"max_date      = {global_max}")

        print(f"\nSaved: {monthly_csv}")
        print(f"Saved: {summary_csv}")

        return 0

    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())