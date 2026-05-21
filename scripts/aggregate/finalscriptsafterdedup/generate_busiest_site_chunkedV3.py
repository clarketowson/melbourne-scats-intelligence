#!/usr/bin/env python3
r"""
generate_busiest_site_chunkedV3.py

Computes busiest SCATS site using the improved one-month-per-execution method.

Fixes in V3:
- Empty months are now explicitly recorded in the monthly CSV so progress advances.
- CSV writes use a small retry loop to reduce failures from temporary file locks.
- Final JSON is written atomically.
- Extra logging makes empty-month handling obvious.

Outputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\chunked_busiest_site_monthly.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\chunked_busiest_site_final.json
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

TEMP_DIR = r"G:\DuckDBTemp"
MEMORY_LIMIT = "50GB"
MAX_TEMP_DIRECTORY_SIZE = "1000GiB"
THREADS = 10

REPORT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")
MONTHLY_CSV = REPORT_DIR / "chunked_busiest_site_monthly.csv"
FINAL_JSON = REPORT_DIR / "chunked_busiest_site_final.json"

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
        if m == 12:
            next_month_start = date(y + 1, 1, 1)
        else:
            next_month_start = date(y, m + 1, 1)

        months.append(
            MonthWindow(
                month_start=month_start,
                next_month_start=next_month_start,
                label=f"{month_start.year:04d}-{month_start.month:02d}",
            )
        )

        if month_start.year == end.year and month_start.month == end.month:
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
    checks = [
        "scats_clean",
        "cont.scats_clean",
        "rec.scats_clean",
        "scats_site",
        "cont.scats_site",
        "rec.scats_site",
    ]
    print("Running preflight checks...")
    for obj in checks:
        con.execute(f"SELECT COUNT(*) FROM {obj} LIMIT 1").fetchone()
        print(f"  OK: {obj}")


def ensure_monthly_csv() -> None:
    if not MONTHLY_CSV.exists():
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        with MONTHLY_CSV.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "month_label",
                    "month_start",
                    "next_month_start",
                    "scats_site",
                    "month_site_volume",
                    "month_elapsed_seconds",
                    "completed_at_epoch",
                ]
            )


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

    rows_to_write: list[list] = []

    if not rows:
        rows_to_write.append(
            [
                month.label,
                month.month_start.isoformat(),
                month.next_month_start.isoformat(),
                "",
                "",
                round(month_elapsed_seconds, 3),
                now_epoch,
            ]
        )
        write_rows_with_retry(rows_to_write)
        return 1

    for scats_site, month_site_volume in rows:
        rows_to_write.append(
            [
                month.label,
                month.month_start.isoformat(),
                month.next_month_start.isoformat(),
                scats_site,
                int(month_site_volume) if month_site_volume is not None else "",
                round(month_elapsed_seconds, 3),
                now_epoch,
            ]
        )

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


def query_month_site_totals(con: duckdb.DuckDBPyConnection, month: MonthWindow) -> list[tuple]:
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
        scats_site,
        SUM(volume_15m) AS month_site_volume
    FROM ranked
    WHERE rn = 1
      AND scats_site IS NOT NULL
      AND volume_15m IS NOT NULL
    GROUP BY scats_site
    ORDER BY scats_site
    """
    return con.execute(sql).fetchall()


def build_final_result(con: duckdb.DuckDBPyConnection, months: list[MonthWindow]) -> dict:
    completed = load_completed_months()
    month_labels = [m.label for m in months]
    done_labels = [label for label in month_labels if label in completed]

    if not done_labels:
        return {
            "metric_name": "busiest_site",
            "date_range_start": DATE_RANGE_START.isoformat(),
            "date_range_end": DATE_RANGE_END.isoformat(),
            "months_total": len(months),
            "months_completed": 0,
            "is_complete": False,
            "busiest_site_id": None,
            "busiest_site_name": None,
            "busiest_site_total_volume": None,
            "total_elapsed_seconds": 0.0,
            "generated_at_epoch": round(time.time(), 3),
            "monthly_csv": str(MONTHLY_CSV),
        }

    csv_path_sql = str(MONTHLY_CSV).replace(chr(92), "/")

    sql = f"""
    WITH monthly AS (
        SELECT
            CAST(scats_site AS INTEGER) AS scats_site,
            CAST(month_site_volume AS BIGINT) AS month_site_volume,
            CAST(month_elapsed_seconds AS DOUBLE) AS month_elapsed_seconds
        FROM read_csv_auto('{csv_path_sql}', header=true)
        WHERE scats_site IS NOT NULL
          AND month_site_volume IS NOT NULL
    ),
    site_totals AS (
        SELECT
            scats_site,
            SUM(month_site_volume) AS total_site_volume
        FROM monthly
        GROUP BY scats_site
    ),
    best AS (
        SELECT
            scats_site,
            total_site_volume
        FROM site_totals
        ORDER BY total_site_volume DESC, scats_site
        LIMIT 1
    ),
    site_names_raw AS (
        SELECT scats_site, site_name FROM scats_site
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
    elapsed AS (
        SELECT SUM(month_elapsed_seconds) AS total_elapsed_seconds
        FROM (
            SELECT month_label, MAX(month_elapsed_seconds) AS month_elapsed_seconds
            FROM read_csv_auto('{csv_path_sql}', header=true)
            GROUP BY month_label
        )
    )
    SELECT
        best.scats_site,
        COALESCE(site_names.site_name, CAST(best.scats_site AS VARCHAR)) AS site_name,
        best.total_site_volume,
        elapsed.total_elapsed_seconds
    FROM best
    LEFT JOIN site_names
      ON best.scats_site = site_names.scats_site
    CROSS JOIN elapsed
    LIMIT 1
    """
    row = con.execute(sql).fetchone()

    return {
        "metric_name": "busiest_site",
        "date_range_start": DATE_RANGE_START.isoformat(),
        "date_range_end": DATE_RANGE_END.isoformat(),
        "months_total": len(months),
        "months_completed": len(done_labels),
        "is_complete": len(done_labels) == len(months),
        "busiest_site_id": row[0] if row else None,
        "busiest_site_name": row[1] if row else None,
        "busiest_site_total_volume": row[2] if row else None,
        "total_elapsed_seconds": round(float(row[3]), 3) if row and row[3] is not None else 0.0,
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
    print("CHUNKED BUSIEST SITE RUN - ONE MONTH PER EXECUTION")
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
        rows = query_month_site_totals(con, next_month)
        month_elapsed = time.time() - month_start_ts

        csv_rows_written = append_month_rows(rows, next_month, month_elapsed)

        temp_after = current_temp_usage_bytes(TEMP_DIR)
        temp_delta = temp_after - temp_before

        month_best_site = None
        month_best_volume = None

        valid_rows = [
            (scats_site, month_site_volume)
            for scats_site, month_site_volume in rows
            if scats_site is not None and month_site_volume is not None
        ]

        if valid_rows:
            month_best_site, month_best_volume = max(
                valid_rows,
                key=lambda x: (x[1], -int(x[0]))
            )

        final_payload = build_final_result(con, months)
        save_final_json(final_payload)

        print("-" * 90)
        print(f"Finished month       : {next_month.label}")
        print(f"Rows returned        : {fmt_int(len(rows))}")
        print(f"CSV rows written     : {fmt_int(csv_rows_written)}")
        print(f"Month best site      : {month_best_site if month_best_site is not None else 'N/A'}")
        print(f"Month best volume    : {fmt_int(month_best_volume) if month_best_volume is not None else 'N/A'}")
        print(f"Month elapsed        : {fmt_seconds(month_elapsed)}")
        if not rows:
            print("Empty month handled  : yes (placeholder progress row written)")
        print(f"Temp usage after     : {fmt_gb(temp_after)}")
        print(f"Temp delta           : {fmt_gb(temp_delta)}")
        print(f"Months completed     : {final_payload['months_completed']}/{final_payload['months_total']}")
        print(f"Running busiest site : {final_payload['busiest_site_id']}")
        print(f"Running site name    : {final_payload['busiest_site_name']}")
        print(f"Running site volume  : {fmt_int(final_payload['busiest_site_total_volume'])}")
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
