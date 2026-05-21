#!/usr/bin/env python3
r"""
generate_site_totals_chunkedV3.py

Builds SCATS site total cleaned volume using the safer V3 one-month-per-execution method.

V3 behaviour:
- Processes EXACTLY ONE next incomplete month per run.
- Detects already-completed months from site_totals.csv.
- Treats zero-row months as complete using an explicit ZERO_ROW_MONTH marker row.
- Does not loop forever on months such as 2018-12 where no rows are returned.
- Resumes cleanly if the CSV already exists.
- Rebuilds site_totals_final.json after every run.
- Final JSON includes months_total, months_completed, is_complete, zero_row_months,
  rows_in_site_totals_csv, distinct_sites, top site fields, grand_total_volume,
  total_elapsed_seconds, and generated_at_epoch.
- Uses V3 DuckDB temp/memory settings suitable for wrapper-style execution.

Outputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\site_totals.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\site_totals_final.json
"""

from __future__ import annotations

import csv
import json
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import duckdb


MAIN_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats.duckdb"
CONT_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats_continuation.duckdb"
REC_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats_recovery.duckdb"

# V3 standard: prefer the fast local NVMe temp directory.
# Change this if you intentionally want another DuckDB spill location.
TEMP_DIR = r"C:\DuckDBTemp"
MEMORY_LIMIT = "50GB"
MAX_TEMP_DIRECTORY_SIZE = "1000GiB"
THREADS = 10

REPORT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")
SITE_TOTALS_CSV = REPORT_DIR / "site_totals.csv"
FINAL_JSON = REPORT_DIR / "site_totals_final.json"

DATE_RANGE_START = date(2014, 1, 1)
DATE_RANGE_END = date(2026, 4, 7)

ZERO_ROW_MARKER = "__ZERO_ROW_MONTH__"
CSV_COLUMNS = [
    "month_label",
    "month_start",
    "next_month_start",
    "scats_site",
    "month_site_volume",
    "month_elapsed_seconds",
    "completed_at_epoch",
    "row_type",
]


@dataclass(frozen=True)
class MonthWindow:
    month_start: date
    next_month_start: date
    label: str


def fmt_int(value: Any) -> str:
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


def win_path_for_duckdb(path: str | Path) -> str:
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
    con.execute(f"SET temp_directory='{win_path_for_duckdb(TEMP_DIR)}'")
    con.execute(f"SET max_temp_directory_size='{MAX_TEMP_DIRECTORY_SIZE}'")
    con.execute(f"SET threads={THREADS}")
    con.execute("SET preserve_insertion_order=false")
    try:
        con.execute("SET enable_progress_bar=true")
    except Exception:
        pass

    con.execute(f"ATTACH '{win_path_for_duckdb(CONT_DB)}' AS cont")
    con.execute(f"ATTACH '{win_path_for_duckdb(REC_DB)}' AS rec")
    return con


def preflight_check(con: duckdb.DuckDBPyConnection) -> None:
    print("Running preflight checks...")
    for obj in [
        "scats_clean",
        "cont.scats_clean",
        "rec.scats_clean",
        "scats_site",
        "cont.scats_site",
        "rec.scats_site",
    ]:
        con.execute(f"SELECT COUNT(*) FROM {obj} LIMIT 1").fetchone()
        print(f"  OK: {obj}")


def ensure_site_totals_csv() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    if not SITE_TOTALS_CSV.exists():
        with SITE_TOTALS_CSV.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(CSV_COLUMNS)


def read_existing_rows() -> list[dict[str, str]]:
    ensure_site_totals_csv()
    with SITE_TOTALS_CSV.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows: list[dict[str, str]] = []
        for row in reader:
            # Backward compatibility for old V2 CSVs without row_type.
            if "row_type" not in row or row.get("row_type") in (None, ""):
                row["row_type"] = "data"
            rows.append(row)
        return rows


def load_completed_months() -> set[str]:
    done: set[str] = set()
    for row in read_existing_rows():
        label = (row.get("month_label") or "").strip()
        site = (row.get("scats_site") or "").strip()
        row_type = (row.get("row_type") or "data").strip()
        volume = (row.get("month_site_volume") or "").strip()

        # A month is complete if it has any normal site row, or an explicit zero-row marker.
        if label and (row_type == "zero_row_month" or site == ZERO_ROW_MARKER or volume != ""):
            done.add(label)
    return done


def load_zero_row_months() -> list[str]:
    zero_months: set[str] = set()
    for row in read_existing_rows():
        label = (row.get("month_label") or "").strip()
        site = (row.get("scats_site") or "").strip()
        row_type = (row.get("row_type") or "").strip()
        if label and (row_type == "zero_row_month" or site == ZERO_ROW_MARKER):
            zero_months.add(label)
    return sorted(zero_months)


def append_site_rows(rows: list[tuple], month: MonthWindow, month_elapsed_seconds: float) -> None:
    ensure_site_totals_csv()
    now_epoch = round(time.time(), 3)
    with SITE_TOTALS_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not rows:
            # Critical V3 fix: mark empty months as complete so the wrapper does not loop forever.
            writer.writerow([
                month.label,
                month.month_start.isoformat(),
                month.next_month_start.isoformat(),
                ZERO_ROW_MARKER,
                "",
                round(month_elapsed_seconds, 3),
                now_epoch,
                "zero_row_month",
            ])
            return

        for scats_site, month_site_volume in rows:
            writer.writerow([
                month.label,
                month.month_start.isoformat(),
                month.next_month_start.isoformat(),
                scats_site,
                int(month_site_volume) if month_site_volume is not None else "",
                round(month_elapsed_seconds, 3),
                now_epoch,
                "data",
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


def query_month_site_totals(con: duckdb.DuckDBPyConnection, month: MonthWindow) -> list[tuple]:
    start_s = month.month_start.isoformat()
    end_s = month.next_month_start.isoformat()

    sql = f"""
    WITH unified AS (
        SELECT scats_site, count_date, detector, source_file_id, interval_index, volume_15m
        FROM scats_clean
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
        scats_site,
        SUM(volume_15m) AS month_site_volume
    FROM ranked
    WHERE rn = 1
    GROUP BY scats_site
    ORDER BY scats_site
    """
    return con.execute(sql).fetchall()


def build_final_result(con: duckdb.DuckDBPyConnection, months: list[MonthWindow]) -> dict[str, Any]:
    completed = load_completed_months()
    done_labels = [m.label for m in months if m.label in completed]
    zero_row_months = load_zero_row_months()

    base_payload: dict[str, Any] = {
        "metric_name": "site_totals",
        "date_range_start": DATE_RANGE_START.isoformat(),
        "date_range_end": DATE_RANGE_END.isoformat(),
        "months_total": len(months),
        "months_completed": len(done_labels),
        "is_complete": len(done_labels) == len(months),
        "zero_row_months": zero_row_months,
        "rows_in_site_totals_csv": 0,
        "distinct_sites": None,
        "top_site_id": None,
        "top_site_name": None,
        "top_site_total_volume": None,
        "grand_total_volume": None,
        "total_elapsed_seconds": 0.0,
        "generated_at_epoch": round(time.time(), 3),
        "site_totals_csv": str(SITE_TOTALS_CSV),
    }

    if not done_labels:
        return base_payload

    site_csv_path = win_path_for_duckdb(SITE_TOTALS_CSV)

    sql = f"""
    WITH raw_csv AS (
        SELECT *
        FROM read_csv_auto('{site_csv_path}', header=true, all_varchar=true)
    ),
    site_monthly AS (
        SELECT
            TRY_CAST(scats_site AS INTEGER) AS scats_site,
            TRY_CAST(month_site_volume AS BIGINT) AS month_site_volume,
            month_label,
            TRY_CAST(month_elapsed_seconds AS DOUBLE) AS month_elapsed_seconds
        FROM raw_csv
        WHERE COALESCE(row_type, 'data') <> 'zero_row_month'
          AND scats_site <> '{ZERO_ROW_MARKER}'
          AND TRY_CAST(scats_site AS INTEGER) IS NOT NULL
          AND TRY_CAST(month_site_volume AS BIGINT) IS NOT NULL
    ),
    site_totals AS (
        SELECT
            scats_site,
            SUM(month_site_volume) AS total_site_volume
        FROM site_monthly
        GROUP BY scats_site
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
    best AS (
        SELECT
            st.scats_site,
            st.total_site_volume,
            sn.site_name
        FROM site_totals st
        LEFT JOIN site_names sn
          ON st.scats_site = sn.scats_site
        ORDER BY st.total_site_volume DESC, st.scats_site
        LIMIT 1
    ),
    agg AS (
        SELECT
            COUNT(*) AS distinct_sites,
            SUM(total_site_volume) AS grand_total_volume
        FROM site_totals
    ),
    elapsed AS (
        SELECT SUM(month_elapsed_seconds) AS total_elapsed_seconds
        FROM (
            SELECT
                month_label,
                MAX(TRY_CAST(month_elapsed_seconds AS DOUBLE)) AS month_elapsed_seconds
            FROM raw_csv
            WHERE month_label IS NOT NULL
            GROUP BY month_label
        )
    )
    SELECT
        (SELECT COUNT(*) FROM site_monthly) AS rows_in_site_totals_csv,
        agg.distinct_sites,
        best.scats_site,
        COALESCE(best.site_name, CAST(best.scats_site AS VARCHAR)) AS top_site_name,
        best.total_site_volume,
        agg.grand_total_volume,
        elapsed.total_elapsed_seconds
    FROM agg
    LEFT JOIN best ON TRUE
    CROSS JOIN elapsed
    """
    row = con.execute(sql).fetchone()

    if row:
        base_payload.update({
            "rows_in_site_totals_csv": int(row[0] or 0),
            "distinct_sites": int(row[1]) if row[1] is not None else None,
            "top_site_id": int(row[2]) if row[2] is not None else None,
            "top_site_name": row[3] if row[3] is not None else None,
            "top_site_total_volume": int(row[4]) if row[4] is not None else None,
            "grand_total_volume": int(row[5]) if row[5] is not None else None,
            "total_elapsed_seconds": round(float(row[6]), 3) if row[6] is not None else 0.0,
        })

    return base_payload


def save_final_json(payload: dict[str, Any]) -> None:
    with FINAL_JSON.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def print_final_summary(payload: dict[str, Any]) -> None:
    print("-" * 90)
    print(f"Months completed     : {payload['months_completed']}/{payload['months_total']}")
    print(f"Is complete          : {payload['is_complete']}")
    print(f"Zero-row months      : {', '.join(payload['zero_row_months']) if payload['zero_row_months'] else 'None'}")
    print(f"Rows in site CSV     : {fmt_int(payload['rows_in_site_totals_csv'])}")
    print(f"Distinct sites       : {fmt_int(payload['distinct_sites'])}")
    print(f"Top site             : {payload['top_site_id']} - {payload['top_site_name']}")
    print(f"Top site volume      : {fmt_int(payload['top_site_total_volume'])}")
    print(f"Grand total volume   : {fmt_int(payload['grand_total_volume'])}")
    print(f"Total elapsed        : {fmt_seconds(float(payload['total_elapsed_seconds'] or 0))}")
    print("-" * 90)


def main() -> None:
    overall_start = time.time()
    months = month_iter(DATE_RANGE_START, DATE_RANGE_END)
    total_months = len(months)

    completed_before = load_completed_months()
    next_month = find_next_incomplete_month(months, completed_before)

    print("=" * 90)
    print("SITE TOTALS V3 - ONE MONTH PER EXECUTION")
    print("=" * 90)
    print(f"Date range           : {DATE_RANGE_START} to {DATE_RANGE_END}")
    print(f"Months total         : {total_months}")
    print(f"Already completed    : {sum(1 for m in months if m.label in completed_before)}/{total_months}")
    print(f"Site totals CSV      : {SITE_TOTALS_CSV}")
    print(f"Final JSON output    : {FINAL_JSON}")
    print(f"Temp directory       : {TEMP_DIR}")
    print(f"Memory limit         : {MEMORY_LIMIT}")
    print(f"Threads              : {THREADS}")
    print("=" * 90)

    con = connect_db()
    try:
        preflight_check(con)

        if next_month is None:
            final_payload = build_final_result(con, months)
            save_final_json(final_payload)
            print("All months are already complete. Nothing to do.")
            print_final_summary(final_payload)
            return

        next_idx = next(i for i, m in enumerate(months, start=1) if m.label == next_month.label)
        print(f"Next month to run    : {next_month.label} ({next_idx}/{total_months})")
        print(f"Date window          : {next_month.month_start.isoformat()} to < {next_month.next_month_start.isoformat()}")

        temp_before = current_temp_usage_bytes(TEMP_DIR)
        print(f"Temp usage before    : {fmt_gb(temp_before)}")

        month_start_ts = time.time()
        rows = query_month_site_totals(con, next_month)
        month_elapsed = time.time() - month_start_ts

        append_site_rows(rows, next_month, month_elapsed)

        temp_after = current_temp_usage_bytes(TEMP_DIR)
        temp_delta = temp_after - temp_before

        month_best_site = None
        month_best_volume = None
        if rows:
            month_best_site, month_best_volume = max(rows, key=lambda x: (x[1], -int(x[0])))

        final_payload = build_final_result(con, months)
        save_final_json(final_payload)

        print("-" * 90)
        print(f"Finished month       : {next_month.label}")
        print(f"Rows written         : {fmt_int(len(rows))}")
        if not rows:
            print("Zero-row marker      : written; month will not be retried")
        print(f"Month best site      : {month_best_site if month_best_site is not None else 'N/A'}")
        print(f"Month best volume    : {fmt_int(month_best_volume) if month_best_volume is not None else 'N/A'}")
        print(f"Month elapsed        : {fmt_seconds(month_elapsed)}")
        print(f"Temp usage after     : {fmt_gb(temp_after)}")
        print(f"Temp delta           : {fmt_gb(temp_delta)}")
        print(f"Overall elapsed      : {fmt_seconds(time.time() - overall_start)}")
        print_final_summary(final_payload)

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
