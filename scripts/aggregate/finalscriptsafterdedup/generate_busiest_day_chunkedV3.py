#!/usr/bin/env python3
r"""
generate_busiest_day_chunkedV3.py

Computes busiest day using the improved one-month-per-execution method.

V3 carries across the reliability fixes from generate_peak_shares_chunkedV3.py:
- Empty months are explicitly recorded in the monthly CSV so progress always advances.
- CSV writes use a small retry loop to reduce failures from temporary file locks.
- Final JSON is written atomically.
- Completed-month loading ignores blank labels and treats placeholder rows as complete.
- Extra logging makes empty-month handling obvious.

Outputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\chunked_busiest_day_monthly.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\chunked_busiest_day_final.json
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
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
MONTHLY_CSV = REPORT_DIR / "chunked_busiest_day_monthly.csv"
FINAL_JSON = REPORT_DIR / "chunked_busiest_day_final.json"

DATE_RANGE_START = date(2014, 1, 1)
DATE_RANGE_END = date(2026, 4, 7)

CSV_WRITE_RETRIES = 10
CSV_WRITE_RETRY_SECONDS = 2


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
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        with MONTHLY_CSV.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "month_label",
                "month_start",
                "next_month_start",
                "count_date",
                "day_total_volume",
                "month_elapsed_seconds",
                "completed_at_epoch",
            ])


def load_completed_months() -> set[str]:
    ensure_monthly_csv()
    done: set[str] = set()
    with MONTHLY_CSV.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            label = (row.get("month_label") or "").strip()
            if label:
                done.add(label)
    return done


def write_rows_with_retry(rows_to_write: list[list]) -> None:
    last_exc: Exception | None = None

    for attempt in range(1, CSV_WRITE_RETRIES + 1):
        try:
            with MONTHLY_CSV.open("a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(rows_to_write)
                f.flush()
                os.fsync(f.fileno())
            return
        except PermissionError as exc:
            last_exc = exc
            print(
                f"Monthly CSV is locked/unavailable (attempt {attempt}/{CSV_WRITE_RETRIES}). "
                f"Retrying in {CSV_WRITE_RETRY_SECONDS}s..."
            )
            time.sleep(CSV_WRITE_RETRY_SECONDS)

    if last_exc is not None:
        raise last_exc


def append_month_rows(rows: list[tuple], month: MonthWindow, month_elapsed_seconds: float) -> int:
    ensure_monthly_csv()
    now_epoch = round(time.time(), 3)

    if not rows:
        rows_to_write = [[
            month.label,
            month.month_start.isoformat(),
            month.next_month_start.isoformat(),
            "",
            "",
            round(month_elapsed_seconds, 3),
            now_epoch,
        ]]
    else:
        rows_to_write = []
        for count_date, day_total_volume in rows:
            rows_to_write.append([
                month.label,
                month.month_start.isoformat(),
                month.next_month_start.isoformat(),
                count_date,
                int(day_total_volume) if day_total_volume is not None else "",
                round(month_elapsed_seconds, 3),
                now_epoch,
            ])

    write_rows_with_retry(rows_to_write)
    return len(rows_to_write)


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


def query_month_day_totals(con: duckdb.DuckDBPyConnection, month: MonthWindow) -> list[tuple]:
    start_s = month.month_start.isoformat()
    end_s = month.next_month_start.isoformat()

    sql = f"""
    WITH unified AS (
        SELECT
            scats_site,
            count_date,
            detector,
            region_code,
            source_file_id,
            interval_index,
            time_bin,
            volume_15m
        FROM scats_clean
        WHERE count_date >= DATE '{start_s}'
          AND count_date <  DATE '{end_s}'

        UNION ALL

        SELECT
            scats_site,
            count_date,
            detector,
            region_code,
            source_file_id,
            interval_index,
            time_bin,
            volume_15m
        FROM cont.scats_clean
        WHERE count_date >= DATE '{start_s}'
          AND count_date <  DATE '{end_s}'

        UNION ALL

        SELECT
            scats_site,
            count_date,
            detector,
            region_code,
            source_file_id,
            interval_index,
            time_bin,
            volume_15m
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
    )
    SELECT
        count_date,
        SUM(volume_15m) AS day_total_volume
    FROM ranked
    WHERE rn = 1
      AND volume_15m IS NOT NULL
    GROUP BY count_date
    ORDER BY count_date
    """
    return con.execute(sql).fetchall()


def build_final_result(con: duckdb.DuckDBPyConnection, months: list[MonthWindow]) -> dict:
    completed = load_completed_months()
    month_labels = [m.label for m in months]
    done_labels = [label for label in month_labels if label in completed]

    if not done_labels:
        return {
            "metric_name": "busiest_day",
            "date_range_start": DATE_RANGE_START.isoformat(),
            "date_range_end": DATE_RANGE_END.isoformat(),
            "months_total": len(months),
            "months_completed": 0,
            "is_complete": False,
            "busiest_day": None,
            "busiest_day_total_volume": None,
            "total_elapsed_seconds": 0.0,
            "generated_at_epoch": round(time.time(), 3),
            "monthly_csv": str(MONTHLY_CSV),
        }

    monthly_csv_path = str(MONTHLY_CSV).replace(chr(92), "/")

    sql = f"""
    WITH daily AS (
        SELECT
            CAST(count_date AS DATE) AS count_date,
            CAST(day_total_volume AS BIGINT) AS day_total_volume
        FROM read_csv_auto('{monthly_csv_path}', header=true)
        WHERE month_label IS NOT NULL
          AND count_date IS NOT NULL
          AND day_total_volume IS NOT NULL
    ),
    best AS (
        SELECT
            count_date,
            day_total_volume
        FROM daily
        ORDER BY day_total_volume DESC, count_date
        LIMIT 1
    ),
    elapsed AS (
        SELECT SUM(month_elapsed_seconds) AS total_elapsed_seconds
        FROM (
            SELECT
                month_label,
                MAX(CAST(month_elapsed_seconds AS DOUBLE)) AS month_elapsed_seconds
            FROM read_csv_auto('{monthly_csv_path}', header=true)
            WHERE month_label IS NOT NULL
            GROUP BY month_label
        )
    )
    SELECT
        best.count_date,
        best.day_total_volume,
        elapsed.total_elapsed_seconds
    FROM best
    CROSS JOIN elapsed
    LIMIT 1
    """
    row = con.execute(sql).fetchone()

    return {
        "metric_name": "busiest_day",
        "date_range_start": DATE_RANGE_START.isoformat(),
        "date_range_end": DATE_RANGE_END.isoformat(),
        "months_total": len(months),
        "months_completed": len(done_labels),
        "is_complete": len(done_labels) == len(months),
        "busiest_day": str(row[0]) if row and row[0] is not None else None,
        "busiest_day_total_volume": row[1] if row else None,
        "total_elapsed_seconds": round(float(row[2]), 3) if row and row[2] is not None else 0.0,
        "generated_at_epoch": round(time.time(), 3),
        "monthly_csv": str(MONTHLY_CSV),
    }


def save_final_json(payload: dict) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = FINAL_JSON.with_suffix(FINAL_JSON.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    temp_path.replace(FINAL_JSON)


def main() -> None:
    overall_start = time.time()
    months = month_iter(DATE_RANGE_START, DATE_RANGE_END)
    total_months = len(months)

    completed_before = load_completed_months()
    completed_count_before = sum(1 for m in months if m.label in completed_before)
    next_month = find_next_incomplete_month(months, completed_before)

    print("=" * 90)
    print("CHUNKED BUSIEST DAY RUN V3 - ONE MONTH PER EXECUTION")
    print("=" * 90)
    print(f"Date range           : {DATE_RANGE_START} to {DATE_RANGE_END}")
    print(f"Months total         : {total_months}")
    print(f"Already completed    : {completed_count_before}/{total_months}")
    print(f"Main DB              : {MAIN_DB}")
    print(f"Continuation DB      : {CONT_DB}")
    print(f"Recovery DB          : {REC_DB}")
    print(f"Temp directory       : {TEMP_DIR}")
    print(f"Monthly CSV output   : {MONTHLY_CSV}")
    print(f"Final JSON output    : {FINAL_JSON}")
    print(f"Memory limit         : {MEMORY_LIMIT}")
    print(f"Temp max             : {MAX_TEMP_DIRECTORY_SIZE}")
    print(f"Threads              : {THREADS}")
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
    print(
        f"Date window          : {next_month.month_start.isoformat()} "
        f"to < {next_month.next_month_start.isoformat()}"
    )

    con = connect_db()
    try:
        preflight_check(con)

        temp_before = current_temp_usage_bytes(TEMP_DIR)
        print(f"Temp usage before    : {fmt_gb(temp_before)}")

        month_start_ts = time.time()
        rows = query_month_day_totals(con, next_month)
        month_elapsed = time.time() - month_start_ts

        csv_rows_written = append_month_rows(rows, next_month, month_elapsed)

        temp_after = current_temp_usage_bytes(TEMP_DIR)
        temp_delta = temp_after - temp_before

        month_best_day = None
        month_best_volume = None
        if rows:
            month_best_day, month_best_volume = max(rows, key=lambda x: (x[1], x[0]))

        final_payload = build_final_result(con, months)
        save_final_json(final_payload)

        print("-" * 90)
        print(f"Finished month       : {next_month.label}")
        print(f"CSV rows written     : {fmt_int(csv_rows_written)}")
        print(f"Daily rows returned  : {fmt_int(len(rows))}")
        print(f"Month best day       : {month_best_day if month_best_day is not None else 'N/A'}")
        print(f"Month best volume    : {fmt_int(month_best_volume) if month_best_volume is not None else 'N/A'}")
        print(f"Month elapsed        : {fmt_seconds(month_elapsed)}")
        if not rows:
            print("Empty month handled  : yes (placeholder progress row written)")
        print(f"Temp usage after     : {fmt_gb(temp_after)}")
        print(f"Temp delta           : {fmt_gb(temp_delta)}")
        print(f"Months completed     : {final_payload['months_completed']}/{final_payload['months_total']}")
        print(f"Running busiest day  : {final_payload['busiest_day']}")
        print(f"Running day volume   : {fmt_int(final_payload['busiest_day_total_volume'])}")
        print(f"Overall elapsed      : {fmt_seconds(time.time() - overall_start)}")
        print(f"Monthly CSV          : {MONTHLY_CSV}")
        print(f"Final JSON           : {FINAL_JSON}")
        print("-" * 90)

        if final_payload["is_complete"]:
            print("ARCHIVE COMPLETE.")
        else:
            upcoming = find_next_incomplete_month(months, load_completed_months())
            if upcoming is not None:
                print(f"Next launch will start at month: {upcoming.label}")

    finally:
        con.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(130)
