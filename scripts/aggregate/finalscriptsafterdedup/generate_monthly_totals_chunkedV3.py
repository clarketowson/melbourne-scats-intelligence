#!/usr/bin/env python3
r"""
generate_monthly_totals_chunkedV3.py

Builds monthly total cleaned volume using the V3 one-month-per-execution method.

V3 improvements:
- Detects already-completed months from the monthly CSV.
- Resumes cleanly when the CSV already exists.
- Does not restart from month 1 when rows are missing or partial.
- Processes exactly ONE next incomplete month per execution.
- Rebuilds final JSON after every run.
- Final JSON includes:
    months_total
    months_completed
    is_complete
    total_elapsed_seconds
- Compatible with wrapper-style execution.
- Uses V3 DuckDB temp directory / memory / thread handling.
- Maintains the same output filenames as V2 unless required.

Outputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\monthly_totals.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\monthly_totals_final.json
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

# V3 standard temp handling.
# Prefer the fast local/NVMe temp drive used in the later V3 scripts.
TEMP_DIR = r"C:\DuckDBTemp"
MEMORY_LIMIT = "50GB"
MAX_TEMP_DIRECTORY_SIZE = "1000GiB"
THREADS = 10

REPORT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")
MONTHLY_CSV = REPORT_DIR / "monthly_totals.csv"
FINAL_JSON = REPORT_DIR / "monthly_totals_final.json"

DATE_RANGE_START = date(2014, 1, 1)
DATE_RANGE_END = date(2026, 4, 7)

CSV_HEADER = [
    "month_label",
    "month_start",
    "next_month_start",
    "month_total_volume",
    "month_elapsed_seconds",
    "completed_at_epoch",
]


@dataclass(frozen=True)
class MonthWindow:
    month_start: date
    next_month_start: date
    label: str


def fmt_int(value):
    if value is None or value == "":
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


def duck_path(path: str | Path) -> str:
    return str(path).replace("\\", "/")


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
    con.execute(f"SET temp_directory='{duck_path(TEMP_DIR)}'")
    con.execute(f"SET max_temp_directory_size='{MAX_TEMP_DIRECTORY_SIZE}'")
    con.execute(f"SET threads={THREADS}")
    con.execute("SET preserve_insertion_order=false")
    try:
        con.execute("SET enable_progress_bar=true")
    except Exception:
        pass

    con.execute(f"ATTACH '{duck_path(CONT_DB)}' AS cont")
    con.execute(f"ATTACH '{duck_path(REC_DB)}' AS rec")
    return con


def preflight_check(con: duckdb.DuckDBPyConnection) -> None:
    print("Running preflight checks...")
    for obj in ["main.scats_clean", "cont.scats_clean", "rec.scats_clean"]:
        con.execute(f"SELECT COUNT(*) FROM {obj} LIMIT 1").fetchone()
        print(f"  OK: {obj}")


def ensure_monthly_csv() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    if not MONTHLY_CSV.exists():
        with MONTHLY_CSV.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(CSV_HEADER)
        return

    # If the file exists but is empty/corrupt-header-only, make sure it has the expected header.
    try:
        text = MONTHLY_CSV.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""

    if not text.strip():
        with MONTHLY_CSV.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(CSV_HEADER)


def is_valid_month_row(row: dict, valid_labels: set[str]) -> bool:
    label = (row.get("month_label") or "").strip()
    if label not in valid_labels:
        return False

    total = (row.get("month_total_volume") or "").strip()
    if total == "":
        return False

    try:
        int(float(total))
    except ValueError:
        return False

    return True


def load_completed_months(months: list[MonthWindow]) -> set[str]:
    """
    V3 completion detection:
    - Reads existing CSV if present.
    - Only counts rows with valid month labels and numeric totals.
    - Ignores malformed/blank rows instead of restarting the whole process.
    - Handles duplicate rows by using a set of labels.
    """
    ensure_monthly_csv()
    valid_labels = {m.label for m in months}
    done: set[str] = set()

    try:
        with MONTHLY_CSV.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return done
            for row in reader:
                if is_valid_month_row(row, valid_labels):
                    done.add((row.get("month_label") or "").strip())
    except FileNotFoundError:
        ensure_monthly_csv()

    return done


def append_month_row(month: MonthWindow, month_total_volume, month_elapsed_seconds: float) -> None:
    ensure_monthly_csv()
    with MONTHLY_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            month.label,
            month.month_start.isoformat(),
            month.next_month_start.isoformat(),
            int(month_total_volume or 0),
            round(month_elapsed_seconds, 3),
            round(time.time(), 3),
        ])



def sanitize_monthly_csv(months: list[MonthWindow]) -> None:
    """
    Removes malformed/blank month rows and duplicate completed rows.
    This specifically prevents a zero-row month from being retried forever after
    blank month_total_volume rows have been appended.
    A backup is written before any cleanup.
    """
    ensure_monthly_csv()
    valid_labels = {m.label for m in months}
    month_order = {m.label: i for i, m in enumerate(months)}

    try:
        with MONTHLY_CSV.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except FileNotFoundError:
        return

    latest_valid: dict[str, dict] = {}
    changed = False

    for row in rows:
        label = (row.get("month_label") or "").strip()
        if not is_valid_month_row(row, valid_labels):
            changed = True
            continue

        prev = latest_valid.get(label)
        if prev is None:
            latest_valid[label] = row
            continue

        changed = True
        try:
            row_epoch = float(row.get("completed_at_epoch") or 0)
            prev_epoch = float(prev.get("completed_at_epoch") or 0)
        except ValueError:
            row_epoch = 0
            prev_epoch = 0
        if row_epoch >= prev_epoch:
            latest_valid[label] = row

    if not changed and len(latest_valid) == len(rows):
        return

    backup = MONTHLY_CSV.with_suffix(MONTHLY_CSV.suffix + f".bak_{int(time.time())}")
    MONTHLY_CSV.replace(backup)

    with MONTHLY_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writeheader()
        for label in sorted(latest_valid, key=lambda x: month_order.get(x, 9999)):
            writer.writerow({k: latest_valid[label].get(k, "") for k in CSV_HEADER})

    print(f"Cleaned malformed/duplicate monthly CSV rows. Backup saved: {backup}")

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


def query_month_total(con: duckdb.DuckDBPyConnection, month: MonthWindow):
    start_s = month.month_start.isoformat()
    end_s = month.next_month_start.isoformat()

    sql = f"""
    WITH unified AS (
        SELECT scats_site, count_date, detector, source_file_id, interval_index, volume_15m
        FROM main.scats_clean
        WHERE count_date >= DATE '{start_s}'
          AND count_date <  DATE '{end_s}'

        UNION ALL

        SELECT scats_site, count_date, detector, source_file_id, interval_index, volume_15m
        FROM cont.scats_clean
        WHERE count_date >= DATE '{start_s}'
          AND count_date <  DATE '{end_s}'

        UNION ALL

        SELECT scats_site, count_date, detector, source_file_id, interval_index, volume_15m
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
    SELECT COALESCE(SUM(volume_15m), 0) AS month_total_volume
    FROM ranked
    WHERE rn = 1
    """
    row = con.execute(sql).fetchone()
    return row[0] if row else None


def build_final_result(con: duckdb.DuckDBPyConnection, months: list[MonthWindow]) -> dict:
    """
    Builds final JSON from the existing monthly CSV.

    V3 behavior:
    - Completion is based on valid month labels, not raw CSV row count.
    - Duplicate month rows do not inflate months_completed.
    - For duplicate rows, the latest completed_at_epoch row is used for totals/elapsed.
    - Missing rows simply leave is_complete=false without forcing restart from month 1.
    """
    completed = load_completed_months(months)
    months_completed = len(completed)
    months_total = len(months)
    monthly_csv_path = duck_path(MONTHLY_CSV)

    if months_completed == 0:
        return {
            "metric_name": "monthly_totals",
            "date_range_start": DATE_RANGE_START.isoformat(),
            "date_range_end": DATE_RANGE_END.isoformat(),
            "months_total": months_total,
            "months_completed": 0,
            "is_complete": False,
            "rows_in_monthly_csv": 0,
            "grand_total_volume": None,
            "total_elapsed_seconds": 0.0,
            "generated_at_epoch": round(time.time(), 3),
            "monthly_csv": str(MONTHLY_CSV),
        }

    sql = f"""
    WITH raw_monthly AS (
        SELECT
            CAST(month_label AS VARCHAR) AS month_label,
            CAST(month_total_volume AS BIGINT) AS month_total_volume,
            CAST(month_elapsed_seconds AS DOUBLE) AS month_elapsed_seconds,
            CAST(completed_at_epoch AS DOUBLE) AS completed_at_epoch
        FROM read_csv_auto('{monthly_csv_path}', header=true)
        WHERE month_label IS NOT NULL
          AND month_total_volume IS NOT NULL
    ),
    latest AS (
        SELECT
            month_label,
            month_total_volume,
            month_elapsed_seconds,
            completed_at_epoch,
            ROW_NUMBER() OVER (
                PARTITION BY month_label
                ORDER BY completed_at_epoch DESC NULLS LAST
            ) AS rn
        FROM raw_monthly
    ),
    dedup AS (
        SELECT
            month_label,
            month_total_volume,
            month_elapsed_seconds
        FROM latest
        WHERE rn = 1
    )
    SELECT
        COUNT(*) AS rows_in_monthly_csv,
        SUM(month_total_volume) AS grand_total_volume,
        SUM(month_elapsed_seconds) AS total_elapsed_seconds
    FROM dedup
    """
    row = con.execute(sql).fetchone()

    return {
        "metric_name": "monthly_totals",
        "date_range_start": DATE_RANGE_START.isoformat(),
        "date_range_end": DATE_RANGE_END.isoformat(),
        "months_total": months_total,
        "months_completed": months_completed,
        "is_complete": months_completed == months_total,
        "rows_in_monthly_csv": int(row[0]) if row and row[0] is not None else 0,
        "grand_total_volume": int(row[1]) if row and row[1] is not None else None,
        "total_elapsed_seconds": round(float(row[2]), 3) if row and row[2] is not None else 0.0,
        "generated_at_epoch": round(time.time(), 3),
        "monthly_csv": str(MONTHLY_CSV),
    }


def save_final_json(payload: dict) -> None:
    with FINAL_JSON.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def print_final_summary(payload: dict) -> None:
    print("-" * 90)
    print("Final JSON status")
    print(f"Months completed     : {payload.get('months_completed')}/{payload.get('months_total')}")
    print(f"Is complete          : {payload.get('is_complete')}")
    print(f"Grand total volume   : {fmt_int(payload.get('grand_total_volume'))}")
    print(f"Total elapsed        : {fmt_seconds(float(payload.get('total_elapsed_seconds') or 0))}")
    print(f"Saved final JSON     : {FINAL_JSON}")
    print("-" * 90)


def main() -> None:
    overall_start = time.time()
    months = month_iter(DATE_RANGE_START, DATE_RANGE_END)
    total_months = len(months)

    sanitize_monthly_csv(months)
    completed_before = load_completed_months(months)
    next_month = find_next_incomplete_month(months, completed_before)

    print("=" * 90)
    print("MONTHLY TOTALS V3 - ONE MONTH PER EXECUTION")
    print("=" * 90)
    print(f"Date range           : {DATE_RANGE_START} to {DATE_RANGE_END}")
    print(f"Months total         : {total_months}")
    print(f"Already completed    : {len(completed_before)}/{total_months}")
    print(f"Monthly CSV output   : {MONTHLY_CSV}")
    print(f"Final JSON output    : {FINAL_JSON}")
    print(f"Memory limit         : {MEMORY_LIMIT}")
    print(f"Threads              : {THREADS}")
    print(f"Temp directory       : {TEMP_DIR}")
    print("=" * 90)

    con = connect_db()
    try:
        preflight_check(con)

        if next_month is None:
            final_payload = build_final_result(con, months)
            save_final_json(final_payload)
            print("All valid month rows are already complete. Nothing to do.")
            print_final_summary(final_payload)
            return

        next_idx = next(i for i, m in enumerate(months, start=1) if m.label == next_month.label)
        print(f"Next month to run    : {next_month.label} ({next_idx}/{total_months})")
        print(f"Date window          : {next_month.month_start.isoformat()} to < {next_month.next_month_start.isoformat()}")

        temp_before = current_temp_usage_bytes(TEMP_DIR)
        print(f"Temp usage before    : {fmt_gb(temp_before)}")

        month_start_ts = time.time()
        month_total = query_month_total(con, next_month)
        month_elapsed = time.time() - month_start_ts

        append_month_row(next_month, month_total, month_elapsed)

        temp_after = current_temp_usage_bytes(TEMP_DIR)
        temp_delta = temp_after - temp_before

        final_payload = build_final_result(con, months)
        save_final_json(final_payload)

        print("-" * 90)
        print(f"Finished month       : {next_month.label}")
        print(f"Month total volume   : {fmt_int(month_total)}")
        print(f"Month elapsed        : {fmt_seconds(month_elapsed)}")
        print(f"Temp usage after     : {fmt_gb(temp_after)}")
        print(f"Temp delta           : {fmt_gb(temp_delta)}")
        print(f"Months completed     : {final_payload['months_completed']}/{final_payload['months_total']}")
        print(f"Grand total so far   : {fmt_int(final_payload['grand_total_volume'])}")
        print(f"Overall elapsed      : {fmt_seconds(time.time() - overall_start)}")
        print("-" * 90)

        upcoming = find_next_incomplete_month(months, load_completed_months(months))
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
