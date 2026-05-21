#!/usr/bin/env python3
r"""
generate_peak_shares_chunked.py

Computes AM and PM peak shares safely using monthly chunking.

Pipeline:
- build scats_all_clean_dedup in-session from the 3 scats_clean views
- for each month:
    compute total_volume, am_volume, pm_volume
    save monthly totals to CSV immediately
- after all months:
    combine monthly totals
    compute final AM and PM peak shares

Outputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\chunked_peak_shares_monthly.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\chunked_peak_shares_final.json
"""

from __future__ import annotations

import csv
import json
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
MONTHLY_CSV = REPORT_DIR / "chunked_peak_shares_monthly.csv"
FINAL_JSON = REPORT_DIR / "chunked_peak_shares_final.json"

DATE_RANGE_START = date(2014, 1, 1)
DATE_RANGE_END = date(2026, 4, 7)

AM_START = "07:00"
AM_END = "10:00"
PM_START = "16:00"
PM_END = "19:00"


@dataclass(frozen=True)
class MonthWindow:
    month_start: date
    next_month_start: date
    label: str


def fmt_int(value):
    if value is None:
        return "N/A"
    return f"{int(value):,}"


def fmt_pct(value):
    if value is None:
        return "N/A"
    return f"{float(value):.2f}%"


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

    con.execute(f"ATTACH '{CONT_DB.replace(chr(92), '/')}' AS cont")
    con.execute(f"ATTACH '{REC_DB.replace(chr(92), '/')}' AS rec")
    return con


def preflight_check(con: duckdb.DuckDBPyConnection) -> None:
    print("Running preflight checks...")
    for obj in ["scats_clean", "cont.scats_clean", "rec.scats_clean"]:
        con.execute(f"SELECT COUNT(*) FROM {obj} LIMIT 1").fetchone()
        print(f"  OK: {obj}")


def create_unified_view(con: duckdb.DuckDBPyConnection) -> None:
    print("Creating TEMP VIEW scats_all_clean_dedup...")
    sql = """
    CREATE OR REPLACE TEMP VIEW scats_all_clean_dedup AS
    WITH unified AS (
        SELECT scats_site, count_date, detector, region_code, source_file_id, interval_index, time_bin, volume_15m
        FROM scats_clean
        UNION ALL
        SELECT scats_site, count_date, detector, region_code, source_file_id, interval_index, time_bin, volume_15m
        FROM cont.scats_clean
        UNION ALL
        SELECT scats_site, count_date, detector, region_code, source_file_id, interval_index, time_bin, volume_15m
        FROM rec.scats_clean
    ),
    ranked AS (
        SELECT
            scats_site, count_date, detector, region_code, source_file_id, interval_index, time_bin, volume_15m,
            ROW_NUMBER() OVER (
                PARTITION BY scats_site, count_date, detector, interval_index
                ORDER BY source_file_id
            ) AS rn
        FROM unified
    )
    SELECT scats_site, count_date, detector, region_code, source_file_id, interval_index, time_bin, volume_15m
    FROM ranked
    WHERE rn = 1
    """
    con.execute(sql)
    print("TEMP VIEW ready.")


def ensure_monthly_csv() -> None:
    if not MONTHLY_CSV.exists():
        with MONTHLY_CSV.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "month_label",
                "month_start",
                "next_month_start",
                "month_total_volume",
                "month_am_volume",
                "month_pm_volume",
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
    month_total_volume,
    month_am_volume,
    month_pm_volume,
    month_elapsed_seconds: float,
) -> None:
    ensure_monthly_csv()
    with MONTHLY_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            month.label,
            month.month_start.isoformat(),
            month.next_month_start.isoformat(),
            int(month_total_volume) if month_total_volume is not None else "",
            int(month_am_volume) if month_am_volume is not None else "",
            int(month_pm_volume) if month_pm_volume is not None else "",
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


def query_month_peak_shares(con: duckdb.DuckDBPyConnection, month: MonthWindow) -> tuple:
    sql = f"""
    SELECT
        SUM(volume_15m) AS month_total_volume,
        SUM(
            CASE
                WHEN time_bin >= '{AM_START}' AND time_bin < '{AM_END}'
                THEN volume_15m
                ELSE 0
            END
        ) AS month_am_volume,
        SUM(
            CASE
                WHEN time_bin >= '{PM_START}' AND time_bin < '{PM_END}'
                THEN volume_15m
                ELSE 0
            END
        ) AS month_pm_volume
    FROM scats_all_clean_dedup
    WHERE count_date >= DATE '{month.month_start.isoformat()}'
      AND count_date <  DATE '{month.next_month_start.isoformat()}'
    """
    row = con.execute(sql).fetchone()
    if not row:
        return (None, None, None)
    return row[0], row[1], row[2]


def build_final_result(con: duckdb.DuckDBPyConnection) -> dict:
    sql = f"""
    WITH monthly AS (
        SELECT
            CAST(month_total_volume AS BIGINT) AS month_total_volume,
            CAST(month_am_volume AS BIGINT) AS month_am_volume,
            CAST(month_pm_volume AS BIGINT) AS month_pm_volume
        FROM read_csv_auto('{str(MONTHLY_CSV).replace(chr(92), "/")}', header=true)
    ),
    totals AS (
        SELECT
            SUM(month_total_volume) AS total_volume,
            SUM(month_am_volume) AS am_volume,
            SUM(month_pm_volume) AS pm_volume
        FROM monthly
    )
    SELECT
        total_volume,
        am_volume,
        pm_volume,
        CASE
            WHEN total_volume IS NULL OR total_volume = 0 THEN NULL
            ELSE am_volume * 100.0 / total_volume
        END AS am_peak_share,
        CASE
            WHEN total_volume IS NULL OR total_volume = 0 THEN NULL
            ELSE pm_volume * 100.0 / total_volume
        END AS pm_peak_share
    FROM totals
    """
    row = con.execute(sql).fetchone()
    return {
        "total_volume": row[0] if row else None,
        "am_volume": row[1] if row else None,
        "pm_volume": row[2] if row else None,
        "am_peak_share": row[3] if row else None,
        "pm_peak_share": row[4] if row else None,
    }


def save_final_json(payload: dict) -> None:
    with FINAL_JSON.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main() -> None:
    overall_start = time.time()
    months = month_iter(DATE_RANGE_START, DATE_RANGE_END)
    total_months = len(months)

    print("=" * 90)
    print("CHUNKED PEAK SHARES RUN")
    print("=" * 90)
    print(f"Date range           : {DATE_RANGE_START} to {DATE_RANGE_END}")
    print(f"Months to process    : {total_months}")
    print(f"Temp directory       : {TEMP_DIR}")
    print(f"Monthly CSV output   : {MONTHLY_CSV}")
    print(f"Final JSON output    : {FINAL_JSON}")
    print(f"AM window            : {AM_START} to < {AM_END}")
    print(f"PM window            : {PM_START} to < {PM_END}")
    print(f"Memory limit         : {MEMORY_LIMIT}")
    print(f"Temp max             : {MAX_TEMP_DIRECTORY_SIZE}")
    print(f"Threads              : {THREADS}")
    print("=" * 90)

    completed_before = load_completed_months()
    print(f"Already completed    : {sum(1 for m in months if m.label in completed_before)}/{total_months}")

    con = connect_db()
    try:
        preflight_check(con)
        create_unified_view(con)

        completed = load_completed_months()
        month_times: list[float] = []

        for idx, month in enumerate(months, start=1):
            if month.label in completed:
                print(f"[SKIP] {month.label} already completed ({idx}/{total_months}, {idx / total_months * 100:6.2f}%)")
                continue

            current_done = sum(1 for m in months if m.label in completed)
            pct_before = (current_done / total_months) * 100.0

            print("-" * 90)
            print(f"Starting month {month.label} ({idx}/{total_months}, {pct_before:6.2f}% complete before this month)")
            print(f"Date window          : {month.month_start.isoformat()} to < {month.next_month_start.isoformat()}")

            temp_before = current_temp_usage_bytes(TEMP_DIR)
            print(f"Temp usage before    : {fmt_gb(temp_before)}")

            month_start_ts = time.time()
            month_total, month_am, month_pm = query_month_peak_shares(con, month)
            month_elapsed = time.time() - month_start_ts

            append_month_row(month, month_total, month_am, month_pm, month_elapsed)
            completed = load_completed_months()
            month_times.append(month_elapsed)

            current_done = sum(1 for m in months if m.label in completed)
            pct_after = (current_done / total_months) * 100.0

            temp_after = current_temp_usage_bytes(TEMP_DIR)
            temp_delta = temp_after - temp_before

            overall_elapsed = time.time() - overall_start
            avg_month_time = sum(month_times) / len(month_times)
            remaining_months = total_months - current_done
            eta_remaining = remaining_months * avg_month_time

            am_pct = (month_am * 100.0 / month_total) if month_total not in (None, 0) and month_am is not None else None
            pm_pct = (month_pm * 100.0 / month_total) if month_total not in (None, 0) and month_pm is not None else None

            print(f"Finished month       : {month.label}")
            print(f"Month total volume   : {fmt_int(month_total)}")
            print(f"Month AM volume      : {fmt_int(month_am)}")
            print(f"Month PM volume      : {fmt_int(month_pm)}")
            print(f"Month AM share       : {fmt_pct(am_pct)}")
            print(f"Month PM share       : {fmt_pct(pm_pct)}")
            print(f"Month elapsed        : {fmt_seconds(month_elapsed)}")
            print(f"Temp usage after     : {fmt_gb(temp_after)}")
            print(f"Temp delta           : {fmt_gb(temp_delta)}")
            print(f"Months completed     : {current_done}/{total_months}")
            print(f"Overall progress     : {pct_after:6.2f}%")
            print(f"Overall elapsed      : {fmt_seconds(overall_elapsed)}")
            print(f"Avg month time (run) : {fmt_seconds(avg_month_time)}")
            print(f"ETA remaining        : {fmt_seconds(eta_remaining)}")

        final = build_final_result(con)
        final_payload = {
            "metric_name": "peak_shares",
            "date_range_start": DATE_RANGE_START.isoformat(),
            "date_range_end": DATE_RANGE_END.isoformat(),
            "months_total": total_months,
            "months_completed": len(load_completed_months()),
            "is_complete": len(load_completed_months()) == total_months,
            "total_volume": final["total_volume"],
            "am_volume": final["am_volume"],
            "pm_volume": final["pm_volume"],
            "am_peak_share": final["am_peak_share"],
            "pm_peak_share": final["pm_peak_share"],
            "am_peak_share_formatted": fmt_pct(final["am_peak_share"]),
            "pm_peak_share_formatted": fmt_pct(final["pm_peak_share"]),
            "total_elapsed_seconds": round(time.time() - overall_start, 3),
            "generated_at_epoch": round(time.time(), 3),
            "monthly_csv": str(MONTHLY_CSV),
        }
        save_final_json(final_payload)

        print("=" * 90)
        print("RUN COMPLETE")
        print("=" * 90)
        print(f"Total volume         : {fmt_int(final_payload['total_volume'])}")
        print(f"AM volume            : {fmt_int(final_payload['am_volume'])}")
        print(f"PM volume            : {fmt_int(final_payload['pm_volume'])}")
        print(f"AM peak share        : {final_payload['am_peak_share_formatted']}")
        print(f"PM peak share        : {final_payload['pm_peak_share_formatted']}")
        print(f"Total elapsed        : {fmt_seconds(final_payload['total_elapsed_seconds'])}")
        print(f"Monthly CSV          : {MONTHLY_CSV}")
        print(f"Final JSON           : {FINAL_JSON}")
        print("=" * 90)

    finally:
        con.close()


if __name__ == "__main__":
    main()