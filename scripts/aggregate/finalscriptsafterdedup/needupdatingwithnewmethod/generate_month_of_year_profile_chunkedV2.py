#!/usr/bin/env python3
r"""
generate_month_of_year_profile_chunkedV2.py

Builds month-of-year traffic profile using the improved one-month-per-execution method.

New design:
- Uses 50GB DuckDB memory limit
- Processes EXACTLY ONE next incomplete month per run
- Restricts each source to the target month BEFORE union/dedup
- Writes one monthly summary row immediately
- Rebuilds final JSON immediately
- Closes DuckDB and exits cleanly so wrapper can relaunch quickly

Outputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\month_of_year_profile.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\month_of_year_profile_final.json
"""

from __future__ import annotations

import csv
import json
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb


MAIN_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats.duckdb"
CONT_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats_continuation.duckdb"
REC_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats_recovery.duckdb"

TEMP_DIR = r"G:\DuckDBTemp"
MEMORY_LIMIT = "50GB"
MAX_TEMP_DIRECTORY_SIZE = "1000GiB"
THREADS = 10

REPORT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")
MONTHLY_CSV = REPORT_DIR / "month_of_year_profile.csv"
FINAL_JSON = REPORT_DIR / "month_of_year_profile_final.json"

DATE_RANGE_START = date(2014, 1, 1)
DATE_RANGE_END = date(2026, 4, 7)

MONTH_NAMES = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}


@dataclass(frozen=True)
class MonthWindow:
    month_start: date
    next_month_start: date
    label: str


def fmt_int(value):
    if value is None:
        return "N/A"
    return f"{int(value):,}"


def fmt_seconds(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def fmt_gb(num_bytes: int) -> str:
    return f"{num_bytes / (1024 ** 3):,.1f} GB"


def month_iter(start: date, end: date) -> list[MonthWindow]:
    months: list[MonthWindow] = []
    y, m = start.year, start.month
    while True:
        month_start = date(y, m, 1)
        next_month_start = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
        months.append(MonthWindow(month_start, next_month_start, f"{y:04d}-{m:02d}"))
        if y == end.year and m == end.month:
            break
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1
    return months


def connect_db() -> duckdb.DuckDBPyConnection:
    Path(TEMP_DIR).mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(MAIN_DB, read_only=False)
    con.execute(f"SET memory_limit='{MEMORY_LIMIT}'")
    con.execute(f"SET temp_directory='{TEMP_DIR.replace(chr(92), '/')}'")
    con.execute(f"SET max_temp_directory_size='{MAX_TEMP_DIRECTORY_SIZE}'")
    con.execute(f"SET threads={THREADS}")
    con.execute("SET preserve_insertion_order=false")
    try:
        con.execute("SET enable_progress_bar=true")
    except Exception:
        pass

    con.execute(f"ATTACH '{CONT_DB.replace(chr(92), '/')}' AS cont")
    con.execute(f"ATTACH '{REC_DB.replace(chr(92), '/')}' AS rec")
    return con


def preflight_check(con: duckdb.DuckDBPyConnection) -> None:
    print("Running preflight checks...")
    for obj in ["scats_clean", "cont.scats_clean", "rec.scats_clean"]:
        con.execute(f"SELECT COUNT(*) FROM {obj} LIMIT 1").fetchone()
        print(f"  OK: {obj}")


def ensure_monthly_csv() -> None:
    if not MONTHLY_CSV.exists():
        with MONTHLY_CSV.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "month_label",
                "month_start",
                "next_month_start",
                "month_of_year",
                "month_name",
                "month_total_volume",
                "days_loaded",
                "avg_daily_volume",
                "month_elapsed_seconds",
                "completed_at_epoch",
            ])


def load_completed_months() -> set[str]:
    ensure_monthly_csv()
    done: set[str] = set()
    with MONTHLY_CSV.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            done.add(row["month_label"])
    return done


def append_month_row(
    month: MonthWindow,
    month_of_year: int,
    month_name: str,
    month_total_volume,
    days_loaded,
    avg_daily_volume,
    month_elapsed_seconds: float,
) -> None:
    ensure_monthly_csv()
    with MONTHLY_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            month.label,
            month.month_start.isoformat(),
            month.next_month_start.isoformat(),
            month_of_year,
            month_name,
            int(month_total_volume) if month_total_volume is not None else "",
            int(days_loaded) if days_loaded is not None else "",
            float(avg_daily_volume) if avg_daily_volume is not None else "",
            round(month_elapsed_seconds, 3),
            round(time.time(), 3),
        ])


def current_temp_usage_bytes(temp_dir: str) -> int:
    total = 0
    root = Path(temp_dir)
    if not root.exists():
        return 0
    for p in root.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            pass
    return total


def find_next_incomplete_month(months: list[MonthWindow], completed: set[str]) -> MonthWindow | None:
    for month in months:
        if month.label not in completed:
            return month
    return None


def query_month_of_year_summary(con: duckdb.DuckDBPyConnection, month: MonthWindow) -> tuple:
    start_s = month.month_start.isoformat()
    end_s = month.next_month_start.isoformat()

    sql = f"""
    WITH unified AS (
        SELECT scats_site, count_date, detector, region_code, source_file_id, interval_index, time_bin, volume_15m
        FROM scats_clean
        WHERE count_date >= DATE '{start_s}'
          AND count_date <  DATE '{end_s}'

        UNION ALL

        SELECT scats_site, count_date, detector, region_code, source_file_id, interval_index, time_bin, volume_15m
        FROM cont.scats_clean
        WHERE count_date >= DATE '{start_s}'
          AND count_date <  DATE '{end_s}'

        UNION ALL

        SELECT scats_site, count_date, detector, region_code, source_file_id, interval_index, time_bin, volume_15m
        FROM rec.scats_clean
        WHERE count_date >= DATE '{start_s}'
          AND count_date <  DATE '{end_s}'
    ),
    ranked AS (
        SELECT
            scats_site,
            count_date,
            detector,
            interval_index,
            source_file_id,
            volume_15m,
            ROW_NUMBER() OVER (
                PARTITION BY scats_site, count_date, detector, interval_index
                ORDER BY source_file_id
            ) AS rn
        FROM unified
    ),
    base AS (
        SELECT count_date, volume_15m
        FROM ranked
        WHERE rn = 1
    )
    SELECT
        SUM(volume_15m) AS month_total_volume,
        COUNT(DISTINCT count_date) AS days_loaded
    FROM base
    """
    row = con.execute(sql).fetchone()
    if not row:
        return (None, None, None)

    month_total_volume = row[0]
    days_loaded = row[1]
    avg_daily_volume = None
    if month_total_volume is not None and days_loaded not in (None, 0):
        avg_daily_volume = month_total_volume * 1.0 / days_loaded

    return month_total_volume, days_loaded, avg_daily_volume


def build_final_result(con: duckdb.DuckDBPyConnection, months: list[MonthWindow]) -> dict:
    completed = load_completed_months()
    done_labels = [m.label for m in months if m.label in completed]

    if not done_labels:
        return {
            "metric_name": "month_of_year_profile",
            "date_range_start": DATE_RANGE_START.isoformat(),
            "date_range_end": DATE_RANGE_END.isoformat(),
            "months_total": len(months),
            "months_completed": 0,
            "is_complete": False,
            "rows_in_month_of_year_profile_csv": 0,
            "best_month_of_year": None,
            "best_month_name": None,
            "best_month_avg_daily_volume": None,
            "lowest_month_of_year": None,
            "lowest_month_name": None,
            "lowest_month_avg_daily_volume": None,
            "total_elapsed_seconds": 0.0,
            "generated_at_epoch": round(time.time(), 3),
            "month_of_year_profile_csv": str(MONTHLY_CSV),
        }

    monthly_csv_path = str(MONTHLY_CSV).replace(chr(92), "/")

    sql = f"""
    WITH monthly AS (
        SELECT
            CAST(month_of_year AS INTEGER) AS month_of_year,
            CAST(month_name AS VARCHAR) AS month_name,
            CAST(month_total_volume AS BIGINT) AS month_total_volume,
            CAST(days_loaded AS BIGINT) AS days_loaded
        FROM read_csv_auto('{monthly_csv_path}', header=true)
    ),
    agg AS (
        SELECT
            month_of_year,
            MIN(month_name) AS month_name,
            SUM(month_total_volume) AS total_volume,
            SUM(days_loaded) AS total_days_loaded,
            CASE
                WHEN SUM(days_loaded) IS NULL OR SUM(days_loaded) = 0 THEN NULL
                ELSE SUM(month_total_volume) * 1.0 / SUM(days_loaded)
            END AS avg_daily_volume
        FROM monthly
        GROUP BY month_of_year
    ),
    best AS (
        SELECT
            month_of_year,
            month_name,
            avg_daily_volume
        FROM agg
        ORDER BY avg_daily_volume DESC, month_of_year
        LIMIT 1
    ),
    worst AS (
        SELECT
            month_of_year,
            month_name,
            avg_daily_volume
        FROM agg
        ORDER BY avg_daily_volume ASC, month_of_year
        LIMIT 1
    ),
    elapsed AS (
        SELECT SUM(month_elapsed_seconds) AS total_elapsed_seconds
        FROM (
            SELECT
                month_label,
                MAX(CAST(month_elapsed_seconds AS DOUBLE)) AS month_elapsed_seconds
            FROM read_csv_auto('{monthly_csv_path}', header=true)
            GROUP BY month_label
        )
    )
    SELECT
        (SELECT COUNT(*) FROM monthly) AS rows_in_month_of_year_profile_csv,
        best.month_of_year,
        best.month_name,
        best.avg_daily_volume,
        worst.month_of_year,
        worst.month_name,
        worst.avg_daily_volume,
        elapsed.total_elapsed_seconds
    FROM best
    CROSS JOIN worst
    CROSS JOIN elapsed
    """
    row = con.execute(sql).fetchone()

    return {
        "metric_name": "month_of_year_profile",
        "date_range_start": DATE_RANGE_START.isoformat(),
        "date_range_end": DATE_RANGE_END.isoformat(),
        "months_total": len(months),
        "months_completed": len(done_labels),
        "is_complete": len(done_labels) == len(months),
        "rows_in_month_of_year_profile_csv": row[0] if row else 0,
        "best_month_of_year": row[1] if row else None,
        "best_month_name": row[2] if row else None,
        "best_month_avg_daily_volume": row[3] if row else None,
        "lowest_month_of_year": row[4] if row else None,
        "lowest_month_name": row[5] if row else None,
        "lowest_month_avg_daily_volume": row[6] if row else None,
        "total_elapsed_seconds": round(float(row[7]), 3) if row and row[7] is not None else 0.0,
        "generated_at_epoch": round(time.time(), 3),
        "month_of_year_profile_csv": str(MONTHLY_CSV),
    }


def save_final_json(payload: dict) -> None:
    with FINAL_JSON.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main() -> None:
    overall_start = time.time()
    months = month_iter(DATE_RANGE_START, DATE_RANGE_END)
    total_months = len(months)

    completed_before = load_completed_months()
    next_month = find_next_incomplete_month(months, completed_before)

    print("=" * 90)
    print("MONTH OF YEAR PROFILE RUN - ONE MONTH PER EXECUTION")
    print("=" * 90)
    print(f"Date range           : {DATE_RANGE_START} to {DATE_RANGE_END}")
    print(f"Months total         : {total_months}")
    print(f"Already completed    : {sum(1 for m in months if m.label in completed_before)}/{total_months}")
    print(f"Monthly CSV output   : {MONTHLY_CSV}")
    print(f"Final JSON output    : {FINAL_JSON}")
    print(f"Memory limit         : {MEMORY_LIMIT}")
    print("=" * 90)

    if next_month is None:
        con = connect_db()
        try:
            preflight_check(con)
            final_payload = build_final_result(con, months)
            save_final_json(final_payload)
        finally:
            con.close()
        print("All months are already complete. Nothing to do.")
        return

    next_idx = next(i for i, m in enumerate(months, start=1) if m.label == next_month.label)
    print(f"Next month to run    : {next_month.label} ({next_idx}/{total_months})")
    print(f"Date window          : {next_month.month_start.isoformat()} to < {next_month.next_month_start.isoformat()}")

    con = connect_db()
    try:
        preflight_check(con)

        temp_before = current_temp_usage_bytes(TEMP_DIR)
        print(f"Temp usage before    : {fmt_gb(temp_before)}")

        month_start_ts = time.time()
        month_total_volume, days_loaded, avg_daily_volume = query_month_of_year_summary(con, next_month)
        month_elapsed = time.time() - month_start_ts

        month_of_year = next_month.month_start.month
        month_name = MONTH_NAMES[month_of_year]

        append_month_row(
            next_month,
            month_of_year,
            month_name,
            month_total_volume,
            days_loaded,
            avg_daily_volume,
            month_elapsed,
        )

        temp_after = current_temp_usage_bytes(TEMP_DIR)
        temp_delta = temp_after - temp_before

        final_payload = build_final_result(con, months)
        save_final_json(final_payload)

        print("-" * 90)
        print(f"Finished month       : {next_month.label}")
        print(f"Month name           : {month_name}")
        print(f"Month total volume   : {fmt_int(month_total_volume)}")
        print(f"Days loaded          : {fmt_int(days_loaded)}")
        print(f"Avg daily volume     : {fmt_int(avg_daily_volume) if avg_daily_volume is not None else 'N/A'}")
        print(f"Month elapsed        : {fmt_seconds(month_elapsed)}")
        print(f"Temp usage after     : {fmt_gb(temp_after)}")
        print(f"Temp delta           : {fmt_gb(temp_delta)}")
        print(f"Months completed     : {final_payload['months_completed']}/{final_payload['months_total']}")
        print(f"Best month so far    : {final_payload['best_month_name']}")
        print(f"Lowest month so far  : {final_payload['lowest_month_name']}")
        print(f"Overall elapsed      : {fmt_seconds(time.time() - overall_start)}")
        print("-" * 90)

        upcoming = find_next_incomplete_month(months, load_completed_months())
        if upcoming is not None:
            print(f"Next launch will start at month: {upcoming.label}")
        else:
            print("ARCHIVE COMPLETE.")

    finally:
        con.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(130)