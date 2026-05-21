#!/usr/bin/env python3
r"""
generate_day_of_week_profile_chunkedV3.py

V3 patched day-of-week traffic profile generator.

Based on generate_day_of_week_profile_chunkedV2.py, with the key safety fixes from
generate_site_month_totals_chunkedV3.py.

Fixes / improvements over V2:
- Uses C:\DuckDBTemp by default, matching the recent stable V3 scripts.
- Disables DuckDB Unicode progress bar to avoid PowerShell mojibake output.
- Uses defensive CSV parsing for existing day_of_week_profile.csv.
- Writes explicit zero-row month marker rows so months such as 2018-12 do not loop forever.
- Excludes zero-row marker rows from final aggregation.
- Uses all_varchar=true when reading output CSV back through DuckDB.
- Adds row_type column for new V3 rows while remaining compatible with older V2 CSVs.
- Adds detailed traceback printing if a month fails.
- Writes/refreshes final JSON after every successful month.
- Keeps one-month-per-run wrapper compatibility.

Outputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\day_of_week_profile.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\day_of_week_profile_final.json
"""

from __future__ import annotations

import csv
import json
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb


MAIN_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats.duckdb"
CONT_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats_continuation.duckdb"
REC_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats_recovery.duckdb"

TEMP_DIR = r"C:\DuckDBTemp"
MEMORY_LIMIT = "50GB"
MAX_TEMP_DIRECTORY_SIZE = "1000GiB"
THREADS = 10

REPORT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")
MONTHLY_CSV = REPORT_DIR / "day_of_week_profile.csv"
FINAL_JSON = REPORT_DIR / "day_of_week_profile_final.json"

DATE_RANGE_START = date(2014, 1, 1)
DATE_RANGE_END = date(2026, 4, 7)

ROW_TYPE_DAY_TOTAL = "day_of_week_month_day_total"
ROW_TYPE_ZERO_ROW_MONTH = "zero_row_month"

DAY_NAMES = {
    1: "Monday",
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday",
    7: "Sunday",
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

    # Disable progress bar because PowerShell can render DuckDB Unicode blocks as mojibake.
    try:
        con.execute("SET enable_progress_bar=false")
    except Exception:
        pass

    con.execute(f"ATTACH '{CONT_DB.replace(chr(92), '/')}' AS cont")
    con.execute(f"ATTACH '{REC_DB.replace(chr(92), '/')}' AS rec")
    return con


def preflight_check(con: duckdb.DuckDBPyConnection) -> None:
    print("Running preflight checks...", flush=True)
    for obj in ["scats_clean", "cont.scats_clean", "rec.scats_clean"]:
        con.execute(f"SELECT COUNT(*) FROM {obj} LIMIT 1").fetchone()
        print(f"  OK: {obj}", flush=True)


def ensure_monthly_csv() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    if not MONTHLY_CSV.exists():
        with MONTHLY_CSV.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "month_label",
                "month_start",
                "next_month_start",
                "iso_dow",
                "day_name",
                "day_total_volume",
                "days_loaded",
                "avg_daily_volume",
                "month_elapsed_seconds",
                "completed_at_epoch",
                "row_type",
            ])
        return

    # If an older V2 CSV exists without row_type, leave it alone.
    # DictReader handles missing row_type as None; final SQL handles both.
    # Do not rewrite the file while a process may be running.


def load_completed_months() -> set[str]:
    ensure_monthly_csv()
    done: set[str] = set()

    with MONTHLY_CSV.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        if not reader.fieldnames or "month_label" not in reader.fieldnames:
            raise RuntimeError(f"Invalid CSV header in {MONTHLY_CSV}: {reader.fieldnames}")

        for row in reader:
            label = (row.get("month_label") or "").strip()
            if not label:
                continue

            # A month is complete if at least one row exists for it,
            # including the explicit zero-row marker.
            done.add(label)

    return done


def append_rows(rows: list[tuple], month: MonthWindow, month_elapsed_seconds: float) -> None:
    ensure_monthly_csv()
    now_epoch = round(time.time(), 3)

    with MONTHLY_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Explicit zero-row marker. This prevents a missing-data month such as 2018-12
        # from being retried forever by the wrapper.
        if not rows:
            writer.writerow([
                month.label,
                month.month_start.isoformat(),
                month.next_month_start.isoformat(),
                "",
                "",
                "",
                "",
                "",
                round(month_elapsed_seconds, 3),
                now_epoch,
                ROW_TYPE_ZERO_ROW_MONTH,
            ])
            return

        for iso_dow, day_name, day_total_volume, days_loaded, avg_daily_volume in rows:
            writer.writerow([
                month.label,
                month.month_start.isoformat(),
                month.next_month_start.isoformat(),
                iso_dow,
                day_name,
                int(day_total_volume) if day_total_volume is not None else "",
                int(days_loaded) if days_loaded is not None else "",
                float(avg_daily_volume) if avg_daily_volume is not None else "",
                round(month_elapsed_seconds, 3),
                now_epoch,
                ROW_TYPE_DAY_TOTAL,
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


def query_day_of_week_summary(con: duckdb.DuckDBPyConnection, month: MonthWindow) -> list[tuple]:
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
        WHERE scats_site IS NOT NULL
          AND count_date IS NOT NULL
          AND detector IS NOT NULL
          AND interval_index IS NOT NULL
    ),
    base AS (
        SELECT
            count_date,
            volume_15m,
            EXTRACT(ISODOW FROM count_date) AS iso_dow
        FROM ranked
        WHERE rn = 1
          AND volume_15m IS NOT NULL
    ),
    agg AS (
        SELECT
            iso_dow,
            SUM(volume_15m) AS day_total_volume,
            COUNT(DISTINCT count_date) AS days_loaded
        FROM base
        GROUP BY iso_dow
    )
    SELECT
        iso_dow,
        CASE iso_dow
            WHEN 1 THEN 'Monday'
            WHEN 2 THEN 'Tuesday'
            WHEN 3 THEN 'Wednesday'
            WHEN 4 THEN 'Thursday'
            WHEN 5 THEN 'Friday'
            WHEN 6 THEN 'Saturday'
            WHEN 7 THEN 'Sunday'
        END AS day_name,
        day_total_volume,
        days_loaded,
        CASE
            WHEN days_loaded IS NULL OR days_loaded = 0 THEN NULL
            ELSE day_total_volume * 1.0 / days_loaded
        END AS avg_daily_volume
    FROM agg
    WHERE iso_dow IS NOT NULL
      AND day_total_volume IS NOT NULL
    ORDER BY iso_dow
    """
    return con.execute(sql).fetchall()


def build_final_result(con: duckdb.DuckDBPyConnection, months: list[MonthWindow]) -> dict:
    completed = load_completed_months()
    done_labels = [m.label for m in months if m.label in completed]
    all_labels = {m.label for m in months}

    zero_row_months: list[str] = []
    physical_rows_in_csv = 0

    with MONTHLY_CSV.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            physical_rows_in_csv += 1
            label = (row.get("month_label") or "").strip()
            row_type = (row.get("row_type") or "").strip()
            day_total = (row.get("day_total_volume") or "").strip()

            if label in all_labels and (row_type == ROW_TYPE_ZERO_ROW_MONTH or day_total == ""):
                zero_row_months.append(label)

    zero_row_months = sorted(set(zero_row_months))

    base_payload = {
        "metric_name": "day_of_week_profile",
        "date_range_start": DATE_RANGE_START.isoformat(),
        "date_range_end": DATE_RANGE_END.isoformat(),
        "months_total": len(months),
        "months_completed": len(done_labels),
        "is_complete": len(done_labels) == len(months),
        "rows_in_day_of_week_profile_csv": 0,
        "physical_rows_in_csv": physical_rows_in_csv,
        "zero_row_months": zero_row_months,
        "best_day_of_week": None,
        "best_day_name": None,
        "best_day_avg_daily_volume": None,
        "lowest_day_of_week": None,
        "lowest_day_name": None,
        "lowest_day_avg_daily_volume": None,
        "total_elapsed_seconds": 0.0,
        "generated_at_epoch": round(time.time(), 3),
        "day_of_week_profile_csv": str(MONTHLY_CSV),
    }

    if not done_labels:
        return base_payload

    monthly_csv_path = str(MONTHLY_CSV).replace(chr(92), "/")

    sql = f"""
    WITH raw_csv AS (
        SELECT *
        FROM read_csv_auto('{monthly_csv_path}', header=true, all_varchar=true)
    ),
    daily AS (
        SELECT
            TRY_CAST(iso_dow AS INTEGER) AS iso_dow,
            CAST(day_name AS VARCHAR) AS day_name,
            TRY_CAST(day_total_volume AS BIGINT) AS day_total_volume,
            TRY_CAST(days_loaded AS BIGINT) AS days_loaded,
            TRY_CAST(month_elapsed_seconds AS DOUBLE) AS month_elapsed_seconds
        FROM raw_csv
        WHERE month_label IS NOT NULL
          AND month_label <> ''
          AND COALESCE(row_type, '{ROW_TYPE_DAY_TOTAL}') <> '{ROW_TYPE_ZERO_ROW_MONTH}'
          AND day_total_volume IS NOT NULL
          AND day_total_volume <> ''
    ),
    agg AS (
        SELECT
            iso_dow,
            MIN(day_name) AS day_name,
            SUM(day_total_volume) AS total_volume,
            SUM(days_loaded) AS total_days_loaded,
            CASE
                WHEN SUM(days_loaded) IS NULL OR SUM(days_loaded) = 0 THEN NULL
                ELSE SUM(day_total_volume) * 1.0 / SUM(days_loaded)
            END AS avg_daily_volume
        FROM daily
        WHERE iso_dow IS NOT NULL
          AND day_total_volume IS NOT NULL
        GROUP BY iso_dow
    ),
    best AS (
        SELECT
            iso_dow,
            day_name,
            avg_daily_volume
        FROM agg
        ORDER BY avg_daily_volume DESC, iso_dow
        LIMIT 1
    ),
    worst AS (
        SELECT
            iso_dow,
            day_name,
            avg_daily_volume
        FROM agg
        ORDER BY avg_daily_volume ASC, iso_dow
        LIMIT 1
    ),
    elapsed AS (
        SELECT SUM(month_elapsed_seconds) AS total_elapsed_seconds
        FROM (
            SELECT
                month_label,
                MAX(TRY_CAST(month_elapsed_seconds AS DOUBLE)) AS month_elapsed_seconds
            FROM raw_csv
            WHERE month_label IS NOT NULL
              AND month_label <> ''
            GROUP BY month_label
        )
    )
    SELECT
        (SELECT COUNT(*) FROM daily) AS rows_in_day_of_week_profile_csv,
        best.iso_dow,
        best.day_name,
        best.avg_daily_volume,
        worst.iso_dow,
        worst.day_name,
        worst.avg_daily_volume,
        elapsed.total_elapsed_seconds
    FROM best
    CROSS JOIN worst
    CROSS JOIN elapsed
    """
    row = con.execute(sql).fetchone()

    if row:
        base_payload.update({
            "rows_in_day_of_week_profile_csv": row[0] if row[0] is not None else 0,
            "best_day_of_week": row[1],
            "best_day_name": row[2],
            "best_day_avg_daily_volume": row[3],
            "lowest_day_of_week": row[4],
            "lowest_day_name": row[5],
            "lowest_day_avg_daily_volume": row[6],
            "total_elapsed_seconds": round(float(row[7]), 3) if row[7] is not None else 0.0,
        })

    return base_payload


def save_final_json(payload: dict) -> None:
    with FINAL_JSON.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def print_final_payload(payload: dict) -> None:
    print("-" * 90, flush=True)
    print(f"Months completed     : {payload['months_completed']}/{payload['months_total']}", flush=True)
    print(f"Is complete          : {payload['is_complete']}", flush=True)
    print(f"Zero-row months      : {', '.join(payload['zero_row_months']) if payload['zero_row_months'] else 'None'}", flush=True)
    print(f"Rows in profile CSV  : {fmt_int(payload['rows_in_day_of_week_profile_csv'])}", flush=True)
    print(f"Physical CSV rows    : {fmt_int(payload['physical_rows_in_csv'])}", flush=True)
    print(f"Best day so far      : {payload['best_day_name']} ({fmt_int(payload['best_day_avg_daily_volume'])} avg/day)", flush=True)
    print(f"Lowest day so far    : {payload['lowest_day_name']} ({fmt_int(payload['lowest_day_avg_daily_volume'])} avg/day)", flush=True)
    print(f"Total elapsed        : {fmt_seconds(payload['total_elapsed_seconds'])}", flush=True)
    print("-" * 90, flush=True)


def main() -> None:
    overall_start = time.time()
    months = month_iter(DATE_RANGE_START, DATE_RANGE_END)
    total_months = len(months)

    completed_before = load_completed_months()
    next_month = find_next_incomplete_month(months, completed_before)

    print("=" * 90, flush=True)
    print("DAY OF WEEK PROFILE V3 - ONE MONTH PER EXECUTION", flush=True)
    print("=" * 90, flush=True)
    print(f"Date range           : {DATE_RANGE_START} to {DATE_RANGE_END}", flush=True)
    print(f"Months total         : {total_months}", flush=True)
    print(f"Already completed    : {sum(1 for m in months if m.label in completed_before)}/{total_months}", flush=True)
    print(f"Monthly CSV output   : {MONTHLY_CSV}", flush=True)
    print(f"Final JSON output    : {FINAL_JSON}", flush=True)
    print(f"Temp directory       : {TEMP_DIR}", flush=True)
    print(f"Memory limit         : {MEMORY_LIMIT}", flush=True)
    print(f"Threads              : {THREADS}", flush=True)
    print("=" * 90, flush=True)

    con = connect_db()

    try:
        preflight_check(con)

        if next_month is None:
            final_payload = build_final_result(con, months)
            save_final_json(final_payload)
            print("All months are already complete. Nothing to do.", flush=True)
            print_final_payload(final_payload)
            return

        next_idx = next(i for i, m in enumerate(months, start=1) if m.label == next_month.label)
        print(f"Next month to run    : {next_month.label} ({next_idx}/{total_months})", flush=True)
        print(f"Date window          : {next_month.month_start.isoformat()} to < {next_month.next_month_start.isoformat()}", flush=True)

        temp_before = current_temp_usage_bytes(TEMP_DIR)
        print(f"Temp usage before    : {fmt_gb(temp_before)}", flush=True)

        month_start_ts = time.time()
        rows = query_day_of_week_summary(con, next_month)
        month_elapsed = time.time() - month_start_ts

        append_rows(rows, next_month, month_elapsed)

        temp_after = current_temp_usage_bytes(TEMP_DIR)
        temp_delta = temp_after - temp_before

        month_best_day = None
        month_best_avg = None
        if rows:
            month_best_day = max(
                rows,
                key=lambda x: (x[4] if x[4] is not None else -1, -int(x[0]) if x[0] is not None else 0)
            )
            month_best_avg = month_best_day[4]

        final_payload = build_final_result(con, months)
        save_final_json(final_payload)

        print("-" * 90, flush=True)
        print(f"Finished month       : {next_month.label}", flush=True)
        print(f"Rows written         : {fmt_int(len(rows))}", flush=True)
        print(f"Best day this month  : {month_best_day[1] if month_best_day else 'N/A'}", flush=True)
        print(f"Best avg/day         : {fmt_int(month_best_avg) if month_best_avg is not None else 'N/A'}", flush=True)
        print(f"Month elapsed        : {fmt_seconds(month_elapsed)}", flush=True)
        print(f"Temp usage after     : {fmt_gb(temp_after)}", flush=True)
        print(f"Temp delta           : {fmt_gb(temp_delta)}", flush=True)
        print(f"Overall elapsed      : {fmt_seconds(time.time() - overall_start)}", flush=True)

        print_final_payload(final_payload)

        upcoming = find_next_incomplete_month(months, load_completed_months())
        if upcoming is not None:
            print(f"Next launch will start at month: {upcoming.label}", flush=True)
        else:
            print("ARCHIVE COMPLETE.", flush=True)

    finally:
        try:
            con.close()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user.", flush=True)
        sys.exit(130)
    except Exception:
        print("\nERROR: generate_day_of_week_profile_chunkedV3.py failed.", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
