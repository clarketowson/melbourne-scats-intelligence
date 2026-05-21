#!/usr/bin/env python3
r"""
generate_daily_totals_chunkedV3.py

Builds daily total cleaned volume using the V3 one-month-per-execution method.

V3 improvements:
- Detects already-completed months from the daily CSV.
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

Critical V3 zero-row / NULL-month fix:
- If a month produces no daily rows, the script writes a numeric zero-volume
  placeholder row for that month instead of a blank / NULL value.
- Completion detection counts valid month labels from valid daily rows or from
  zero-month placeholder rows.
- Final statistics exclude placeholder rows from busiest / quietest day and
  daily row counts.
- This prevents the 2018-12-style bug where a NULL / blank N/A result was never
  counted as complete and the wrapper retried the same month forever.

Outputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\daily_totals.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\daily_totals_final.json
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
DAILY_CSV = REPORT_DIR / "daily_totals.csv"
FINAL_JSON = REPORT_DIR / "daily_totals_final.json"

DATE_RANGE_START = date(2014, 1, 1)
DATE_RANGE_END = date(2026, 4, 7)

CSV_HEADER = [
    "month_label",
    "month_start",
    "next_month_start",
    "count_date",
    "day_total_volume",
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


def parse_float(value) -> float | None:
    try:
        if value is None:
            return None
        text = str(value).strip()
        if text == "":
            return None
        return float(text)
    except ValueError:
        return None


def parse_int(value) -> int | None:
    parsed = parse_float(value)
    if parsed is None:
        return None
    return int(parsed)


def parse_date_string(value) -> date | None:
    try:
        text = str(value or "").strip()
        if not text:
            return None
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


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


def ensure_daily_csv() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    if not DAILY_CSV.exists():
        with DAILY_CSV.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(CSV_HEADER)
        return

    try:
        text = DAILY_CSV.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""

    if not text.strip():
        with DAILY_CSV.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(CSV_HEADER)


def is_zero_month_placeholder(row: dict) -> bool:
    """A deliberate completion marker for a month with no daily rows."""
    count_date = (row.get("count_date") or "").strip()
    total = parse_int(row.get("day_total_volume"))
    return count_date == "" and total == 0


def is_valid_daily_row(row: dict, valid_labels: set[str]) -> bool:
    label = (row.get("month_label") or "").strip()
    if label not in valid_labels:
        return False

    # Month completion requires a numeric elapsed/completed marker. This avoids
    # accepting corrupted rows with only a label.
    if parse_float(row.get("month_elapsed_seconds")) is None:
        return False
    if parse_float(row.get("completed_at_epoch")) is None:
        return False

    count_date = parse_date_string(row.get("count_date"))
    total = parse_int(row.get("day_total_volume"))

    # Normal daily row.
    if count_date is not None and total is not None:
        return True

    # Deliberate zero-row month marker. This is the key fix for NULL / blank
    # months such as 2018-12.
    if is_zero_month_placeholder(row):
        return True

    return False


def load_completed_months(months: list[MonthWindow]) -> set[str]:
    """
    V3 completion detection:
    - Reads existing CSV if present.
    - Counts only valid month labels from valid daily rows or zero-month markers.
    - Ignores malformed/blank rows instead of restarting the whole process.
    - Handles duplicate rows by using a set of labels.
    """
    ensure_daily_csv()
    valid_labels = {m.label for m in months}
    done: set[str] = set()

    try:
        with DAILY_CSV.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return done
            for row in reader:
                if is_valid_daily_row(row, valid_labels):
                    done.add((row.get("month_label") or "").strip())
    except FileNotFoundError:
        ensure_daily_csv()

    return done


def append_day_rows(rows: list[tuple], month: MonthWindow, month_elapsed_seconds: float) -> None:
    """
    Appends the daily rows for a completed month.

    If the query returns no rows, a deliberate numeric zero placeholder is
    written so completion detection can advance past the month.
    """
    ensure_daily_csv()
    with DAILY_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        now_epoch = round(time.time(), 3)

        if not rows:
            writer.writerow([
                month.label,
                month.month_start.isoformat(),
                month.next_month_start.isoformat(),
                "",
                0,
                round(month_elapsed_seconds, 3),
                now_epoch,
            ])
            return

        for count_date, day_total_volume in rows:
            writer.writerow([
                month.label,
                month.month_start.isoformat(),
                month.next_month_start.isoformat(),
                str(count_date),
                int(day_total_volume or 0),
                round(month_elapsed_seconds, 3),
                now_epoch,
            ])


def sanitize_daily_csv(months: list[MonthWindow]) -> None:
    """
    Removes malformed rows and duplicate month runs.

    For each month, this keeps the latest completed run by completed_at_epoch.
    It preserves all daily rows for that latest run, or preserves the deliberate
    zero-month placeholder if the month had no daily rows.
    """
    ensure_daily_csv()
    valid_labels = {m.label for m in months}
    month_order = {m.label: i for i, m in enumerate(months)}

    try:
        with DAILY_CSV.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except FileNotFoundError:
        return

    valid_rows: list[dict] = []
    changed = False

    for row in rows:
        if is_valid_daily_row(row, valid_labels):
            valid_rows.append(row)
        else:
            changed = True

    if not valid_rows:
        if changed and rows:
            backup = DAILY_CSV.with_suffix(DAILY_CSV.suffix + f".bak_{int(time.time())}")
            DAILY_CSV.replace(backup)
            with DAILY_CSV.open("w", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=CSV_HEADER).writeheader()
            print(f"Cleaned malformed daily CSV rows. Backup saved: {backup}")
        return

    latest_epoch_by_month: dict[str, float] = {}
    for row in valid_rows:
        label = (row.get("month_label") or "").strip()
        epoch = parse_float(row.get("completed_at_epoch")) or 0.0
        latest_epoch_by_month[label] = max(latest_epoch_by_month.get(label, -1.0), epoch)

    kept: list[dict] = []
    for row in valid_rows:
        label = (row.get("month_label") or "").strip()
        epoch = parse_float(row.get("completed_at_epoch")) or 0.0
        if epoch == latest_epoch_by_month[label]:
            kept.append(row)
        else:
            changed = True

    # Sort output back into month/date order for readability.
    kept.sort(key=lambda r: (
        month_order.get((r.get("month_label") or "").strip(), 9999),
        (r.get("count_date") or ""),
    ))

    if not changed and len(kept) == len(rows):
        return

    backup = DAILY_CSV.with_suffix(DAILY_CSV.suffix + f".bak_{int(time.time())}")
    DAILY_CSV.replace(backup)

    with DAILY_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writeheader()
        for row in kept:
            writer.writerow({k: row.get(k, "") for k in CSV_HEADER})

    print(f"Cleaned malformed/duplicate daily CSV rows. Backup saved: {backup}")


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


def query_month_daily_totals(con: duckdb.DuckDBPyConnection, month: MonthWindow) -> list[tuple]:
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
    SELECT
        count_date,
        COALESCE(SUM(volume_15m), 0) AS day_total_volume
    FROM ranked
    WHERE rn = 1
    GROUP BY count_date
    ORDER BY count_date
    """
    return con.execute(sql).fetchall()


def build_final_result(con: duckdb.DuckDBPyConnection, months: list[MonthWindow]) -> dict:
    """
    Builds final JSON from the existing daily CSV.

    V3 behavior:
    - Completion is based on valid month labels, not raw CSV row count.
    - Duplicate month runs do not inflate months_completed.
    - Zero-month placeholders count toward completion but are excluded from
      day-level totals, busiest day, quietest day, and rows_in_daily_csv.
    """
    completed = load_completed_months(months)
    months_completed = len(completed)
    months_total = len(months)
    daily_csv_path = duck_path(DAILY_CSV)

    base = {
        "metric_name": "daily_totals",
        "date_range_start": DATE_RANGE_START.isoformat(),
        "date_range_end": DATE_RANGE_END.isoformat(),
        "months_total": months_total,
        "months_completed": months_completed,
        "is_complete": months_completed == months_total,
        "rows_in_daily_csv": 0,
        "busiest_day": None,
        "busiest_day_total_volume": None,
        "quietest_day": None,
        "quietest_day_total_volume": None,
        "grand_total_volume": None,
        "zero_row_months": [],
        "total_elapsed_seconds": 0.0,
        "generated_at_epoch": round(time.time(), 3),
        "daily_csv": str(DAILY_CSV),
    }

    if months_completed == 0:
        return base

    sql = f"""
    WITH raw_daily AS (
        SELECT
            CAST(month_label AS VARCHAR) AS month_label,
            TRY_CAST(count_date AS DATE) AS count_date,
            TRY_CAST(day_total_volume AS BIGINT) AS day_total_volume,
            TRY_CAST(month_elapsed_seconds AS DOUBLE) AS month_elapsed_seconds,
            TRY_CAST(completed_at_epoch AS DOUBLE) AS completed_at_epoch
        FROM read_csv_auto('{daily_csv_path}', header=true)
        WHERE month_label IS NOT NULL
    ),
    latest_month AS (
        SELECT
            month_label,
            MAX(completed_at_epoch) AS latest_completed_at_epoch
        FROM raw_daily
        WHERE completed_at_epoch IS NOT NULL
        GROUP BY month_label
    ),
    latest_rows AS (
        SELECT r.*
        FROM raw_daily r
        JOIN latest_month m
          ON r.month_label = m.month_label
         AND r.completed_at_epoch = m.latest_completed_at_epoch
    ),
    valid_days AS (
        SELECT count_date, day_total_volume
        FROM latest_rows
        WHERE count_date IS NOT NULL
          AND day_total_volume IS NOT NULL
    ),
    agg AS (
        SELECT
            COUNT(*) AS rows_in_daily_csv,
            SUM(day_total_volume) AS grand_total_volume
        FROM valid_days
    ),
    best AS (
        SELECT count_date, day_total_volume
        FROM valid_days
        ORDER BY day_total_volume DESC, count_date
        LIMIT 1
    ),
    worst AS (
        SELECT count_date, day_total_volume
        FROM valid_days
        ORDER BY day_total_volume ASC, count_date
        LIMIT 1
    ),
    elapsed AS (
        SELECT SUM(month_elapsed_seconds) AS total_elapsed_seconds
        FROM (
            SELECT
                month_label,
                MAX(month_elapsed_seconds) AS month_elapsed_seconds
            FROM latest_rows
            GROUP BY month_label
        )
    ),
    zero_months AS (
        SELECT string_agg(month_label, ',' ORDER BY month_label) AS zero_row_months
        FROM latest_rows
        GROUP BY month_label
        HAVING SUM(CASE WHEN count_date IS NOT NULL THEN 1 ELSE 0 END) = 0
    )
    SELECT
        agg.rows_in_daily_csv,
        best.count_date,
        best.day_total_volume,
        worst.count_date,
        worst.day_total_volume,
        agg.grand_total_volume,
        elapsed.total_elapsed_seconds,
        (SELECT string_agg(zero_row_months, ',') FROM zero_months) AS zero_row_months
    FROM agg
    LEFT JOIN best ON true
    LEFT JOIN worst ON true
    CROSS JOIN elapsed
    """
    row = con.execute(sql).fetchone()

    if not row:
        return base

    zero_row_months = []
    if row[7]:
        zero_row_months = [m for m in str(row[7]).split(",") if m]

    base.update({
        "rows_in_daily_csv": int(row[0]) if row[0] is not None else 0,
        "busiest_day": str(row[1]) if row[1] is not None else None,
        "busiest_day_total_volume": int(row[2]) if row[2] is not None else None,
        "quietest_day": str(row[3]) if row[3] is not None else None,
        "quietest_day_total_volume": int(row[4]) if row[4] is not None else None,
        "grand_total_volume": int(row[5]) if row[5] is not None else None,
        "zero_row_months": zero_row_months,
        "total_elapsed_seconds": round(float(row[6]), 3) if row[6] is not None else 0.0,
        "generated_at_epoch": round(time.time(), 3),
    })
    return base


def save_final_json(payload: dict) -> None:
    with FINAL_JSON.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def print_final_summary(payload: dict) -> None:
    print("-" * 90)
    print("Final JSON status")
    print(f"Months completed     : {payload.get('months_completed')}/{payload.get('months_total')}")
    print(f"Is complete          : {payload.get('is_complete')}")
    print(f"Rows in daily CSV    : {fmt_int(payload.get('rows_in_daily_csv'))}")
    print(f"Grand total volume   : {fmt_int(payload.get('grand_total_volume'))}")
    print(f"Busiest day          : {payload.get('busiest_day')}")
    print(f"Quietest day         : {payload.get('quietest_day')}")
    print(f"Zero-row months      : {payload.get('zero_row_months')}")
    print(f"Total elapsed        : {fmt_seconds(float(payload.get('total_elapsed_seconds') or 0))}")
    print(f"Saved final JSON     : {FINAL_JSON}")
    print("-" * 90)


def main() -> None:
    overall_start = time.time()
    months = month_iter(DATE_RANGE_START, DATE_RANGE_END)
    total_months = len(months)

    sanitize_daily_csv(months)
    completed_before = load_completed_months(months)
    next_month = find_next_incomplete_month(months, completed_before)

    print("=" * 90)
    print("DAILY TOTALS V3 - ONE MONTH PER EXECUTION")
    print("=" * 90)
    print(f"Date range           : {DATE_RANGE_START} to {DATE_RANGE_END}")
    print(f"Months total         : {total_months}")
    print(f"Already completed    : {len(completed_before)}/{total_months}")
    print(f"Daily CSV output     : {DAILY_CSV}")
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
        rows = query_month_daily_totals(con, next_month)
        month_elapsed = time.time() - month_start_ts

        append_day_rows(rows, next_month, month_elapsed)

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
        print(f"Rows written         : {fmt_int(len(rows))}")
        if not rows:
            print("Zero-row marker      : written with numeric volume 0 so the month is complete")
        print(f"Month best day       : {month_best_day if month_best_day is not None else 'N/A'}")
        print(f"Month best volume    : {fmt_int(month_best_volume) if month_best_volume is not None else 'N/A'}")
        print(f"Month elapsed        : {fmt_seconds(month_elapsed)}")
        print(f"Temp usage after     : {fmt_gb(temp_after)}")
        print(f"Temp delta           : {fmt_gb(temp_delta)}")
        print(f"Months completed     : {final_payload['months_completed']}/{final_payload['months_total']}")
        print(f"Grand total so far   : {fmt_int(final_payload['grand_total_volume'])}")
        print(f"Busiest day so far   : {final_payload['busiest_day']}")
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
