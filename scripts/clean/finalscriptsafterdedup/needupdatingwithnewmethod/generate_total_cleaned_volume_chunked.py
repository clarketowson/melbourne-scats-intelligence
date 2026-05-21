#!/usr/bin/env python3
r"""
generate_total_cleaned_volume_chunked.py

Safely computes total cleaned volume from scats_all_clean_dedup by processing
the archive one month at a time.

Key design:
- Uses scats_clean from:
    scats.duckdb
    scats_continuation.duckdb
    scats_recovery.duckdb
- Builds scats_all_clean_dedup as a TEMP VIEW in-session
- Processes monthly date windows
- Writes monthly subtotals immediately
- Can resume after interruption
- Prints detailed progress and ETA information

Outputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\chunked_total_cleaned_volume_monthly.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\chunked_total_cleaned_volume_final.json
"""

from __future__ import annotations

import csv
import json
import math
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb


MAIN_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats.duckdb"
CONT_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats_continuation.duckdb"
REC_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats_recovery.duckdb"

TEMP_DIR = r"G:\DuckDBTemp"
MEMORY_LIMIT = "30GB"
MAX_TEMP_DIRECTORY_SIZE = "1000GiB"
THREADS = 10

REPORT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")
MONTHLY_CSV = REPORT_DIR / "chunked_total_cleaned_volume_monthly.csv"
FINAL_JSON = REPORT_DIR / "chunked_total_cleaned_volume_final.json"

DATE_RANGE_START = date(2014, 1, 1)
DATE_RANGE_END = date(2026, 4, 7)


@dataclass(frozen=True)
class MonthWindow:
    month_start: date
    next_month_start: date
    label: str


def fmt_int(value) -> str:
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


def safe_float(value: float | None) -> float:
    if value is None:
        return 0.0
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return 0.0
    return float(value)


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

    con.execute(f"ATTACH '{CONT_DB.replace(chr(92), '/')}' AS cont")
    con.execute(f"ATTACH '{REC_DB.replace(chr(92), '/')}' AS rec")
    return con


def preflight_check(con: duckdb.DuckDBPyConnection) -> None:
    checks = [
        "scats_clean",
        "cont.scats_clean",
        "rec.scats_clean",
    ]
    print("Running preflight checks...")
    for obj in checks:
        con.execute(f"SELECT COUNT(*) FROM {obj} LIMIT 1").fetchone()
        print(f"  OK: {obj}")


def create_unified_view(con: duckdb.DuckDBPyConnection) -> None:
    print("Creating TEMP VIEW scats_all_clean_dedup...")
    sql = """
    CREATE OR REPLACE TEMP VIEW scats_all_clean_dedup AS
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
    ),
    ranked AS (
        SELECT
            scats_site,
            count_date,
            detector,
            region_code,
            source_file_id,
            interval_index,
            time_bin,
            volume_15m,
            ROW_NUMBER() OVER (
                PARTITION BY scats_site, count_date, detector, interval_index
                ORDER BY source_file_id
            ) AS rn
        FROM unified
    )
    SELECT
        scats_site,
        count_date,
        detector,
        region_code,
        source_file_id,
        interval_index,
        time_bin,
        volume_15m
    FROM ranked
    WHERE rn = 1
    """
    con.execute(sql)
    print("TEMP VIEW ready.")


def ensure_monthly_csv() -> None:
    if not MONTHLY_CSV.exists():
        with MONTHLY_CSV.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "month_label",
                    "month_start",
                    "next_month_start",
                    "month_total_cleaned_volume",
                    "month_elapsed_seconds",
                    "completed_at_epoch",
                ]
            )


def load_completed_months() -> dict[str, dict]:
    ensure_monthly_csv()
    completed: dict[str, dict] = {}

    with MONTHLY_CSV.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            completed[row["month_label"]] = row

    return completed


def append_month_result(
    month: MonthWindow,
    month_total: float | int | None,
    month_elapsed_seconds: float,
) -> None:
    ensure_monthly_csv()
    with MONTHLY_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                month.label,
                month.month_start.isoformat(),
                month.next_month_start.isoformat(),
                int(month_total) if month_total is not None else "",
                round(month_elapsed_seconds, 3),
                round(time.time(), 3),
            ]
        )


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


def fmt_gb(num_bytes: int) -> str:
    return f"{num_bytes / (1024 ** 3):,.1f} GB"


def query_month_total(con: duckdb.DuckDBPyConnection, month: MonthWindow) -> float | None:
    sql = f"""
    SELECT SUM(volume_15m)
    FROM scats_all_clean_dedup
    WHERE count_date >= DATE '{month.month_start.isoformat()}'
      AND count_date <  DATE '{month.next_month_start.isoformat()}'
    """
    row = con.execute(sql).fetchone()
    return row[0] if row else None


def build_final_json(completed_months: dict[str, dict], months: list[MonthWindow]) -> dict:
    month_labels = [m.label for m in months]
    done_labels = [label for label in month_labels if label in completed_months]

    running_total = 0
    total_elapsed = 0.0

    for label in done_labels:
        row = completed_months[label]
        value = row.get("month_total_cleaned_volume", "")
        if value not in ("", None):
            running_total += int(value)
        elapsed = row.get("month_elapsed_seconds", "")
        if elapsed not in ("", None):
            total_elapsed += float(elapsed)

    final = {
        "metric_name": "total_cleaned_volume",
        "date_range_start": DATE_RANGE_START.isoformat(),
        "date_range_end": DATE_RANGE_END.isoformat(),
        "months_total": len(months),
        "months_completed": len(done_labels),
        "is_complete": len(done_labels) == len(months),
        "total_cleaned_volume": running_total if len(done_labels) == len(months) else None,
        "partial_total_cleaned_volume": running_total,
        "total_elapsed_seconds": round(total_elapsed, 3),
        "generated_at_epoch": round(time.time(), 3),
        "monthly_csv": str(MONTHLY_CSV),
    }
    return final


def save_final_json(payload: dict) -> None:
    with FINAL_JSON.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main() -> None:
    overall_start = time.time()
    months = month_iter(DATE_RANGE_START, DATE_RANGE_END)
    total_months = len(months)

    print("=" * 90)
    print("CHUNKED TOTAL CLEANED VOLUME RUN")
    print("=" * 90)
    print(f"Date range           : {DATE_RANGE_START} to {DATE_RANGE_END}")
    print(f"Months to process    : {total_months}")
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

    completed_before = load_completed_months()
    completed_count_before = sum(1 for m in months if m.label in completed_before)

    print(f"Already completed    : {completed_count_before}/{total_months}")
    if completed_count_before:
        partial = build_final_json(completed_before, months)
        print(f"Existing partial sum : {fmt_int(partial['partial_total_cleaned_volume'])}")

    con = connect_db()
    try:
        preflight_check(con)
        create_unified_view(con)

        completed = load_completed_months()
        processed_this_run = 0
        month_times: list[float] = []

        for idx, month in enumerate(months, start=1):
            if month.label in completed:
                print(
                    f"[SKIP] {month.label} already completed "
                    f"({idx}/{total_months}, {idx / total_months * 100:6.2f}%)"
                )
                continue

            current_done = sum(1 for m in months if m.label in completed)
            pct_complete_before = (current_done / total_months) * 100.0

            print("-" * 90)
            print(
                f"Starting month {month.label} "
                f"({idx}/{total_months}, {pct_complete_before:6.2f}% complete before this month)"
            )
            print(
                f"Date window          : {month.month_start.isoformat()} "
                f"to < {month.next_month_start.isoformat()}"
            )

            temp_before = current_temp_usage_bytes(TEMP_DIR)
            print(f"Temp usage before    : {fmt_gb(temp_before)}")

            month_start_ts = time.time()
            month_total = query_month_total(con, month)
            month_elapsed = time.time() - month_start_ts

            append_month_result(month, month_total, month_elapsed)
            completed = load_completed_months()

            processed_this_run += 1
            month_times.append(month_elapsed)

            current_done = sum(1 for m in months if m.label in completed)
            pct_complete_after = (current_done / total_months) * 100.0

            temp_after = current_temp_usage_bytes(TEMP_DIR)
            temp_delta = temp_after - temp_before

            overall_elapsed = time.time() - overall_start

            avg_month_time_this_run = sum(month_times) / len(month_times)
            remaining_months = total_months - current_done
            eta_remaining = remaining_months * avg_month_time_this_run

            partial = build_final_json(completed, months)
            running_total = partial["partial_total_cleaned_volume"]

            print(f"Finished month       : {month.label}")
            print(f"Month subtotal       : {fmt_int(month_total)}")
            print(f"Month elapsed        : {fmt_seconds(month_elapsed)}")
            print(f"Temp usage after     : {fmt_gb(temp_after)}")
            print(f"Temp delta           : {fmt_gb(temp_delta)}")
            print(f"Months completed     : {current_done}/{total_months}")
            print(f"Overall progress     : {pct_complete_after:6.2f}%")
            print(f"Running total volume : {fmt_int(running_total)}")
            print(f"Overall elapsed      : {fmt_seconds(overall_elapsed)}")
            print(f"Avg month time (run) : {fmt_seconds(avg_month_time_this_run)}")
            print(f"ETA remaining        : {fmt_seconds(eta_remaining)}")

            save_final_json(partial)

        final = build_final_json(load_completed_months(), months)
        save_final_json(final)

        print("=" * 90)
        print("RUN COMPLETE")
        print("=" * 90)
        print(f"Months completed     : {final['months_completed']}/{final['months_total']}")
        print(f"Is complete          : {final['is_complete']}")
        print(f"Final total volume   : {fmt_int(final['total_cleaned_volume'] or final['partial_total_cleaned_volume'])}")
        print(f"Total elapsed        : {fmt_seconds(time.time() - overall_start)}")
        print(f"Monthly CSV          : {MONTHLY_CSV}")
        print(f"Final JSON           : {FINAL_JSON}")
        print("=" * 90)

    finally:
        con.close()


if __name__ == "__main__":
    main()