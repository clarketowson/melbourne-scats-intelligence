#!/usr/bin/env python3
r"""
generate_headline_metrics.py

Builds the unified clean deduplicated view in-session from:
- scats.duckdb
- scats_continuation.duckdb
- scats_recovery.duckdb

Source of truth:
    scats_clean (from each database)

Then computes headline metrics for the HTML template.

Safety settings:
- memory_limit = 30GB
- temp_directory = G:/DuckDBTemp
- max_temp_directory_size = 1000GiB
- threads = 10
- preserve_insertion_order = false
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import duckdb


MAIN_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats.duckdb"
CONT_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats_continuation.duckdb"
REC_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats_recovery.duckdb"

OUTPUT_JSON = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\headline_metrics.json"
TEMP_DIR = r"G:\DuckDBTemp"

MEMORY_LIMIT = "30GB"
MAX_TEMP_DIRECTORY_SIZE = "1000GiB"
THREADS = 10

AM_START = "07:00"
AM_END = "10:00"
PM_START = "16:00"
PM_END = "19:00"

# From completed unified clean summary
PRECOMPUTED_SUMMARY = {
    "cleaned_rows": 37877397311,
    "date_range_start": "2014-01-01",
    "date_range_end": "2026-04-07",
}


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


class ProgressTracker:
    def __init__(self, steps):
        self.steps = steps
        self.total_weight = sum(weight for _, weight in steps)
        self.completed_weight = 0.0
        self.start_time = time.time()
        self.step_start = None
        self.step_name = ""

    def start_step(self, step_name: str):
        self.step_name = step_name
        self.step_start = time.time()
        pct = (self.completed_weight / self.total_weight) * 100
        elapsed = time.time() - self.start_time
        eta = self._estimate_eta()
        print(
            f"[{pct:6.2f}%] Starting: {step_name} | "
            f"elapsed={fmt_seconds(elapsed)} | eta={fmt_seconds(eta)}"
        )

    def finish_step(self, weight: float):
        step_elapsed = time.time() - self.step_start
        self.completed_weight += weight
        pct = (self.completed_weight / self.total_weight) * 100
        elapsed = time.time() - self.start_time
        eta = self._estimate_eta()
        print(
            f"[{pct:6.2f}%] Finished: {self.step_name} | "
            f"step_time={fmt_seconds(step_elapsed)} | "
            f"elapsed={fmt_seconds(elapsed)} | eta={fmt_seconds(eta)}"
        )

    def _estimate_eta(self) -> float:
        elapsed = time.time() - self.start_time
        if self.completed_weight <= 0:
            return 0.0
        rate = elapsed / self.completed_weight
        remaining_weight = self.total_weight - self.completed_weight
        return remaining_weight * rate


def connect_db() -> duckdb.DuckDBPyConnection:
    Path(TEMP_DIR).mkdir(parents=True, exist_ok=True)

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
        "scats_site",
        "cont.scats_site",
        "rec.scats_site",
    ]

    for obj in checks:
        try:
            con.execute(f"SELECT COUNT(*) FROM {obj} LIMIT 1").fetchone()
            print(f"  OK: {obj}")
        except Exception as e:
            raise RuntimeError(f"Preflight failed for {obj}: {e}") from e


def create_unified_view(con: duckdb.DuckDBPyConnection) -> None:
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


def q_distinct_sites(con: duckdb.DuckDBPyConnection) -> dict:
    sql = """
    SELECT COUNT(*) AS distinct_sites
    FROM (
        SELECT scats_site FROM scats_site
        UNION
        SELECT scats_site FROM cont.scats_site
        UNION
        SELECT scats_site FROM rec.scats_site
    ) t
    """
    row = con.execute(sql).fetchone()
    return {"distinct_sites": row[0] if row else None}


def q_total_cleaned_volume(con: duckdb.DuckDBPyConnection) -> dict:
    sql = """
    SELECT SUM(volume_15m)
    FROM scats_all_clean_dedup
    """
    row = con.execute(sql).fetchone()
    return {"total_cleaned_volume": row[0] if row else None}


def q_busiest_site(con: duckdb.DuckDBPyConnection) -> dict:
    sql = """
    SELECT
        d.scats_site,
        COALESCE(s.site_name, CAST(d.scats_site AS VARCHAR)) AS site_name
    FROM (
        SELECT
            scats_site,
            SUM(volume_15m) AS site_volume
        FROM scats_all_clean_dedup
        GROUP BY scats_site
        ORDER BY site_volume DESC, scats_site
        LIMIT 1
    ) d
    LEFT JOIN (
        SELECT scats_site, site_name FROM scats_site
        UNION ALL
        SELECT scats_site, site_name FROM cont.scats_site
        UNION ALL
        SELECT scats_site, site_name FROM rec.scats_site
    ) s
      ON d.scats_site = s.scats_site
    LIMIT 1
    """
    row = con.execute(sql).fetchone()
    return {
        "busiest_site_id": row[0] if row else None,
        "busiest_site_name": row[1] if row else None,
    }


def q_busiest_time_bin(con: duckdb.DuckDBPyConnection) -> dict:
    sql = """
    SELECT
        time_bin
    FROM scats_all_clean_dedup
    GROUP BY time_bin
    ORDER BY SUM(volume_15m) DESC, time_bin
    LIMIT 1
    """
    row = con.execute(sql).fetchone()
    return {"busiest_time_bin": row[0] if row else None}


def q_busiest_day(con: duckdb.DuckDBPyConnection) -> dict:
    sql = """
    SELECT
        count_date
    FROM scats_all_clean_dedup
    GROUP BY count_date
    ORDER BY SUM(volume_15m) DESC, count_date
    LIMIT 1
    """
    row = con.execute(sql).fetchone()
    return {"busiest_day": row[0] if row else None}


def q_peak_shares(con: duckdb.DuckDBPyConnection) -> dict:
    sql = f"""
    WITH totals AS (
        SELECT
            SUM(volume_15m) AS total_volume,
            SUM(
                CASE
                    WHEN time_bin >= '{AM_START}' AND time_bin < '{AM_END}'
                    THEN volume_15m ELSE 0
                END
            ) AS am_volume,
            SUM(
                CASE
                    WHEN time_bin >= '{PM_START}' AND time_bin < '{PM_END}'
                    THEN volume_15m ELSE 0
                END
            ) AS pm_volume
        FROM scats_all_clean_dedup
    )
    SELECT
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
        "am_peak_share": row[0] if row else None,
        "pm_peak_share": row[1] if row else None,
    }


def generate_headline_metrics() -> dict[str, str]:
    steps = [
        ("Connect and apply safety settings", 1),
        ("Preflight checks", 1),
        ("Create unified deduplicated view", 4),
        ("Load precomputed summary values", 1),
        ("Compute distinct sites", 1),
        ("Compute total cleaned volume", 2),
        ("Compute busiest site", 2),
        ("Compute busiest time bin", 2),
        ("Compute busiest day", 2),
        ("Compute AM/PM peak shares", 3),
        ("Save output", 1),
    ]
    tracker = ProgressTracker(steps)
    metrics: dict = {}

    tracker.start_step("Connect and apply safety settings")
    con = connect_db()
    tracker.finish_step(1)

    try:
        tracker.start_step("Preflight checks")
        preflight_check(con)
        tracker.finish_step(1)

        tracker.start_step("Create unified deduplicated view")
        create_unified_view(con)
        tracker.finish_step(4)

        tracker.start_step("Load precomputed summary values")
        metrics["cleaned_rows"] = PRECOMPUTED_SUMMARY["cleaned_rows"]
        metrics["date_range_start"] = PRECOMPUTED_SUMMARY["date_range_start"]
        metrics["date_range_end"] = PRECOMPUTED_SUMMARY["date_range_end"]
        tracker.finish_step(1)

        tracker.start_step("Compute distinct sites")
        metrics.update(q_distinct_sites(con))
        tracker.finish_step(1)

        tracker.start_step("Compute total cleaned volume")
        metrics.update(q_total_cleaned_volume(con))
        tracker.finish_step(2)

        tracker.start_step("Compute busiest site")
        metrics.update(q_busiest_site(con))
        tracker.finish_step(2)

        tracker.start_step("Compute busiest time bin")
        metrics.update(q_busiest_time_bin(con))
        tracker.finish_step(2)

        tracker.start_step("Compute busiest day")
        metrics.update(q_busiest_day(con))
        tracker.finish_step(2)

        tracker.start_step("Compute AM/PM peak shares")
        metrics.update(q_peak_shares(con))
        tracker.finish_step(3)

    finally:
        con.close()

    tracker.start_step("Save output")

    formatted = {
        "cleaned_rows": fmt_int(metrics.get("cleaned_rows")),
        "distinct_sites": fmt_int(metrics.get("distinct_sites")),
        "date_range_start": str(metrics.get("date_range_start")) if metrics.get("date_range_start") is not None else "N/A",
        "date_range_end": str(metrics.get("date_range_end")) if metrics.get("date_range_end") is not None else "N/A",
        "total_cleaned_volume": fmt_int(metrics.get("total_cleaned_volume")) if metrics.get("total_cleaned_volume") is not None else "N/A",
        "busiest_site_id": str(metrics.get("busiest_site_id")) if metrics.get("busiest_site_id") is not None else "N/A",
        "busiest_site_name": str(metrics.get("busiest_site_name")) if metrics.get("busiest_site_name") is not None else "N/A",
        "busiest_time_bin": str(metrics.get("busiest_time_bin")) if metrics.get("busiest_time_bin") is not None else "N/A",
        "busiest_day": str(metrics.get("busiest_day")) if metrics.get("busiest_day") is not None else "N/A",
        "am_peak_share": fmt_pct(metrics.get("am_peak_share")),
        "pm_peak_share": fmt_pct(metrics.get("pm_peak_share")),
    }

    output_path = Path(OUTPUT_JSON)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(formatted, f, indent=2)

    tracker.finish_step(1)
    return formatted


if __name__ == "__main__":
    print("Generating headline metrics...")
    result = generate_headline_metrics()
    print(json.dumps(result, indent=2))
    print(f"Saved: {OUTPUT_JSON}")