#!/usr/bin/env python3
r"""
generate_kepler_covid_comparison_daysV4_standalone_chunked.py

Standalone, chunked COVID collapse/recovery Kepler exporter.

This script intentionally does NOT import _common_scats_kepler.py.

It:
  1. Connects to the three SCATS DuckDB databases.
  2. Loads SCATS site metadata with latitude/longitude.
  3. Processes selected comparison dates ONE DAY AT A TIME.
  4. Writes one chunk CSV per selected date.
  5. Prints exactly where it is up to.
  6. Merges all chunks into one Kepler.gl-ready CSV.

Default selected days:
  2019-05-15 - Pre-COVID baseline
  2020-08-05 - Lockdown / COVID shock
  2021-08-05 - Extended disruption
  2022-05-18 - Recovery phase
  2024-05-15 - Recent normal
  2025-12-12 - Busiest day detected

Kepler.gl:
  Time field      : animation_timestamp
  Latitude field  : latitude
  Longitude field : longitude
  Size field      : scaled_volume_0_100
  Colour field    : comparison_period or intensity_band
"""

from __future__ import annotations

import argparse
import gc
import json
import shutil
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd


DEFAULT_MAIN_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats.duckdb"
DEFAULT_CONT_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats_continuation.duckdb"
DEFAULT_REC_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats_recovery.duckdb"
DEFAULT_METADATA = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\all_scats_sites_map_data_audit.csv"
DEFAULT_OUTDIR = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\kepler_animation_exports"

DEFAULT_DATES = [
    ("2019-05-15", "Pre-COVID baseline"),
    ("2020-08-05", "Lockdown / COVID shock"),
    ("2021-08-05", "Extended disruption"),
    ("2022-05-18", "Recovery phase"),
    ("2024-05-15", "Recent normal"),
    ("2025-12-12", "Busiest day detected"),
]


def fmt_int(x) -> str:
    try:
        return f"{int(x):,}"
    except Exception:
        return str(x)


def fmt_seconds(seconds: float) -> str:
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def parse_dates(value: str):
    if not value:
        return DEFAULT_DATES

    out = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            d, label = part.split(":", 1)
        else:
            d, label = part, part
        out.append((pd.to_datetime(d.strip()).strftime("%Y-%m-%d"), label.strip()))
    return out or DEFAULT_DATES


def detect_col(columns, candidates, label, required=True):
    lookup = {str(c).lower(): c for c in columns}
    for candidate in candidates:
        if candidate.lower() in lookup:
            return lookup[candidate.lower()]
    if required:
        raise RuntimeError(f"Could not detect {label}. Columns: {list(columns)}")
    return None


def load_metadata(path: Path) -> pd.DataFrame:
    print("")
    print("=" * 90)
    print("METADATA LOAD")
    print("=" * 90)
    print(f"Metadata path    : {path}")

    if not path.exists():
        raise FileNotFoundError(f"Metadata file not found: {path}")

    df = pd.read_csv(path, low_memory=False)
    print(f"Metadata raw rows: {fmt_int(len(df))}")
    print(f"Metadata columns : {list(df.columns)}")

    site_col = detect_col(df.columns, ["site_id", "scats_site", "nb_scats_site", "site"], "site")
    lat_col = detect_col(df.columns, ["latitude", "lat"], "latitude")
    lon_col = detect_col(df.columns, ["longitude", "lng", "lon"], "longitude")
    name_col = detect_col(df.columns, ["friendly_name", "site_name", "name", "location", "description"], "site name", required=False)

    out = pd.DataFrame({
        "site_id": df[site_col].astype(str).str.strip(),
        "latitude": pd.to_numeric(df[lat_col], errors="coerce"),
        "longitude": pd.to_numeric(df[lon_col], errors="coerce"),
    })

    if name_col:
        out["site_name"] = df[name_col].fillna("").astype(str).str.strip()
    else:
        out["site_name"] = ""

    out.loc[out["site_name"].isin(["", "nan", "None", "NULL"]), "site_name"] = (
        "SCATS " + out["site_id"] + " (network node)"
    )

    out = out.dropna(subset=["latitude", "longitude"])
    out = out[
        (out["latitude"].between(-39.5, -36.0)) &
        (out["longitude"].between(143.0, 146.5))
    ].copy()

    out = out.drop_duplicates(subset=["site_id"], keep="first")

    print(f"Site column      : {site_col}")
    print(f"Latitude column  : {lat_col}")
    print(f"Longitude column : {lon_col}")
    print(f"Name column      : {name_col}")
    print(f"Mapped sites     : {fmt_int(len(out))}")
    return out


def connect_duckdb(main_db: Path, cont_db: Path, rec_db: Path, temp_dir: Path, memory_limit: str, threads: int):
    print("")
    print("=" * 90)
    print("DUCKDB CONNECTION")
    print("=" * 90)
    print(f"Main DB          : {main_db}")
    print(f"Continuation DB  : {cont_db}")
    print(f"Recovery DB      : {rec_db}")
    print(f"Temp dir         : {temp_dir}")
    print(f"Memory limit     : {memory_limit}")
    print(f"Threads          : {threads}")

    if not main_db.exists():
        raise FileNotFoundError(f"Main DuckDB not found: {main_db}")

    temp_dir.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(main_db))
    con.execute(f"SET memory_limit='{memory_limit}'")
    con.execute(f"SET threads={threads}")
    con.execute("SET preserve_insertion_order=false")
    con.execute(f"SET temp_directory='{str(temp_dir).replace(chr(92), '/')}'")

    if cont_db.exists():
        con.execute(f"ATTACH '{str(cont_db).replace(chr(92), '/')}' AS cont")
        print("Attached         : cont")
    else:
        print(f"WARNING          : continuation DB not found: {cont_db}")

    if rec_db.exists():
        con.execute(f"ATTACH '{str(rec_db).replace(chr(92), '/')}' AS rec")
        print("Attached         : rec")
    else:
        print(f"WARNING          : recovery DB not found: {rec_db}")

    return con


def table_exists(con, name: str) -> bool:
    try:
        con.execute(f"SELECT 1 FROM {name} LIMIT 1")
        return True
    except Exception:
        return False


def detect_scats_columns(con, view_name: str) -> dict[str, str]:
    info = con.execute(f"DESCRIBE {view_name}").fetchdf()
    cols = info["column_name"].tolist()

    site_col = detect_col(cols, ["site_id", "nb_scats_site", "scats_site", "site"], "site")
    date_col = detect_col(cols, ["date", "count_date", "day", "traffic_date"], "date")
    time_col = detect_col(cols, ["time", "time_bin", "interval_time", "time_of_day"], "time")
    vol_col = detect_col(cols, ["volume", "volume_15m", "vehicles", "count", "vehicle_count", "veh_count", "sum_volume"], "volume")

    return {
        "site": site_col,
        "date": date_col,
        "time": time_col,
        "volume": vol_col,
    }


def query_one_day(con, selected_date: str) -> pd.DataFrame:
    print("")
    print("Detecting available SCATS views and columns...")

    sources = []
    for view_name in ["scats_clean", "cont.scats_clean", "rec.scats_clean"]:
        if not table_exists(con, view_name):
            print(f"  missing/skipped : {view_name}")
            continue

        c = detect_scats_columns(con, view_name)
        print(
            f"  {view_name}: site={c['site']}, date={c['date']}, "
            f"time={c['time']}, volume={c['volume']}"
        )

        # The date equality is still cast-safe but only for one day per chunk.
        sources.append(f"""
            SELECT
                CAST({c['site']} AS VARCHAR) AS site_id,
                CAST({c['date']} AS DATE) AS count_date,
                CAST({c['time']} AS VARCHAR) AS time_value,
                TRY_CAST({c['volume']} AS DOUBLE) AS volume
            FROM {view_name}
            WHERE CAST({c['date']} AS DATE) = DATE '{selected_date}'
              AND TRY_CAST({c['volume']} AS DOUBLE) IS NOT NULL
              AND TRY_CAST({c['volume']} AS DOUBLE) >= 0
        """)

    if not sources:
        raise RuntimeError("No usable scats_clean views found.")

    union_sql = "\nUNION ALL\n".join(sources)

    query = f"""
    WITH raw AS (
        {union_sql}
    ),
    cleaned AS (
        SELECT
            site_id,
            count_date,
            CASE
                WHEN LENGTH(time_value) >= 5 THEN SUBSTR(time_value, 1, 5)
                ELSE time_value
            END AS time_bin,
            volume
        FROM raw
    )
    SELECT
        site_id,
        count_date,
        time_bin,
        SUM(volume) AS volume
    FROM cleaned
    GROUP BY site_id, count_date, time_bin
    ORDER BY time_bin, site_id
    """

    return con.execute(query).fetchdf()


def enrich_for_kepler(raw: pd.DataFrame, meta: pd.DataFrame, min_volume: float) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()

    df = raw.copy()
    df["site_id"] = df["site_id"].astype(str).str.strip()
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    df = df[df["volume"] >= min_volume].copy()

    if df.empty:
        return pd.DataFrame()

    merged = df.merge(meta, on="site_id", how="inner")
    if merged.empty:
        return pd.DataFrame()

    merged["timestamp"] = pd.to_datetime(
        merged["count_date"].astype(str) + " " + merged["time_bin"].astype(str),
        errors="coerce",
    )
    merged = merged.dropna(subset=["timestamp"]).copy()

    merged["date_label"] = merged["timestamp"].dt.strftime("%Y-%m-%d")
    merged["hour"] = merged["timestamp"].dt.hour
    merged["minute"] = merged["timestamp"].dt.minute
    merged["time_label"] = merged["timestamp"].dt.strftime("%H:%M")

    merged["scaled_volume"] = np.log1p(merged["volume"])
    max_scaled = merged["scaled_volume"].max()
    merged["scaled_volume_0_100"] = merged["scaled_volume"] / max_scaled * 100 if max_scaled > 0 else 0

    q50, q75, q90, q98 = merged["volume"].quantile([0.50, 0.75, 0.90, 0.98])

    def band(v):
        if v >= q98:
            return "extreme"
        if v >= q90:
            return "very high"
        if v >= q75:
            return "high"
        if v >= q50:
            return "medium"
        return "low"

    merged["intensity_band"] = merged["volume"].map(band)
    return merged


def process_date(con, meta, selected_date, label, sequence, total_dates, chunk_path, min_volume):
    started = time.time()

    print("")
    print("=" * 90)
    print(f"DATE CHUNK {sequence + 1}/{total_dates}")
    print("=" * 90)
    print(f"Date             : {selected_date}")
    print(f"Label            : {label}")
    print(f"Chunk path       : {chunk_path}")
    print("Step 1           : Querying one selected day from DuckDB")

    raw = query_one_day(con, selected_date)

    print("")
    print("Step 1 complete  : DuckDB query returned")
    print(f"Raw rows         : {fmt_int(len(raw))}")

    if raw.empty:
        print("WARNING          : no rows found for this date")
        pd.DataFrame().to_csv(chunk_path, index=False)
        return {
            "date": selected_date,
            "label": label,
            "rows": 0,
            "distinct_sites": 0,
            "total_volume": 0.0,
            "elapsed_seconds": round(time.time() - started, 3),
            "status": "empty",
        }

    print("Step 2           : Joining metadata and calculating Kepler fields")
    final = enrich_for_kepler(raw, meta, min_volume=min_volume)

    del raw
    gc.collect()

    print("Step 2 complete  : Enrichment complete")
    print(f"Final rows       : {fmt_int(len(final))}")

    if final.empty:
        print("WARNING          : no rows after metadata join / min-volume filter")
        final.to_csv(chunk_path, index=False)
        return {
            "date": selected_date,
            "label": label,
            "rows": 0,
            "distinct_sites": 0,
            "total_volume": 0.0,
            "elapsed_seconds": round(time.time() - started, 3),
            "status": "filtered_empty",
        }

    print("Step 3           : Adding comparison labels and synthetic animation timestamp")
    final["comparison_period"] = label
    final["comparison_sequence"] = sequence

    base = pd.Timestamp("2030-01-01")
    final["animation_timestamp"] = [
        base + pd.Timedelta(days=int(sequence)) + pd.Timedelta(hours=int(h), minutes=int(m))
        for h, m in zip(final["hour"], final["minute"])
    ]

    keep_cols = [
        "animation_timestamp",
        "timestamp",
        "date_label",
        "comparison_sequence",
        "comparison_period",
        "time_label",
        "hour",
        "minute",
        "site_id",
        "site_name",
        "latitude",
        "longitude",
        "volume",
        "scaled_volume",
        "scaled_volume_0_100",
        "intensity_band",
    ]

    final = final[keep_cols].sort_values(["animation_timestamp", "volume"], ascending=[True, False])

    print("Step 4           : Writing chunk CSV")
    chunk_path.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(chunk_path, index=False)

    rows = int(len(final))
    sites = int(final["site_id"].nunique())
    total_volume = float(final["volume"].sum())
    max_volume = float(final["volume"].max())

    elapsed = time.time() - started

    print("")
    print("CHUNK COMPLETE")
    print(f"Rows             : {fmt_int(rows)}")
    print(f"Distinct sites   : {fmt_int(sites)}")
    print(f"Total volume     : {total_volume:,.0f}")
    print(f"Max 15m volume   : {max_volume:,.0f}")
    print(f"Elapsed          : {fmt_seconds(elapsed)}")

    del final
    gc.collect()

    return {
        "date": selected_date,
        "label": label,
        "rows": rows,
        "distinct_sites": sites,
        "total_volume": total_volume,
        "max_15m_volume": max_volume,
        "elapsed_seconds": round(elapsed, 3),
        "chunk_csv": str(chunk_path),
        "status": "complete",
    }


def merge_chunks(chunk_paths, output_csv):
    print("")
    print("=" * 90)
    print("MERGING CHUNKS")
    print("=" * 90)

    frames = []

    for i, path in enumerate(chunk_paths, start=1):
        print(f"[{i}/{len(chunk_paths)}] Reading {path.name}")
        if not path.exists():
            print("  WARNING: missing; skipped")
            continue

        df = pd.read_csv(path, low_memory=False)
        print(f"  Rows: {fmt_int(len(df))}")
        if len(df):
            frames.append(df)

    if not frames:
        final = pd.DataFrame()
    else:
        final = pd.concat(frames, ignore_index=True)
        final["animation_timestamp"] = pd.to_datetime(final["animation_timestamp"], errors="coerce")
        final = final.sort_values(["animation_timestamp", "volume"], ascending=[True, False])

    print("")
    print("Writing merged output...")
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(output_csv, index=False)

    print(f"Merged rows      : {fmt_int(len(final))}")
    return final


def main():
    p = argparse.ArgumentParser(description="Standalone chunked COVID comparison Kepler export V4.")
    p.add_argument("--dates", default="", help="Comma list: YYYY-MM-DD:Label,YYYY-MM-DD:Label")
    p.add_argument("--main-db", default=DEFAULT_MAIN_DB)
    p.add_argument("--cont-db", default=DEFAULT_CONT_DB)
    p.add_argument("--rec-db", default=DEFAULT_REC_DB)
    p.add_argument("--metadata", default=DEFAULT_METADATA)
    p.add_argument("--outdir", default=DEFAULT_OUTDIR)
    p.add_argument("--temp-dir", default=r"C:\DuckDBTemp")
    p.add_argument("--memory-limit", default="20GB")
    p.add_argument("--threads", type=int, default=6)
    p.add_argument("--min-volume", type=float, default=1.0)
    p.add_argument("--keep-chunks", action="store_true")
    p.add_argument("--resume", action="store_true")
    args = p.parse_args()

    overall_start = time.time()
    dates = parse_dates(args.dates)

    outdir = Path(args.outdir)
    chunks_dir = outdir / "_chunks_covid_comparison_days_v4"
    output_csv = outdir / "kepler_covid_collapse_recovery_comparison_days.csv"
    summary_json = outdir / "kepler_covid_collapse_recovery_comparison_days_summary.json"

    print("=" * 90)
    print("COVID COLLAPSE / RECOVERY KEPLER EXPORT V4 - STANDALONE CHUNKED")
    print("=" * 90)
    print("Selected comparison dates:")
    for i, (d, label) in enumerate(dates, start=1):
        print(f"  {i}. {d} - {label}")
    print("")
    print(f"Output CSV       : {output_csv}")
    print(f"Summary JSON     : {summary_json}")
    print(f"Chunks dir       : {chunks_dir}")
    print(f"Keep chunks      : {args.keep_chunks}")
    print(f"Resume           : {args.resume}")
    print("=" * 90)

    outdir.mkdir(parents=True, exist_ok=True)

    if chunks_dir.exists() and not args.resume:
        print("")
        print("Removing previous V4 chunk directory...")
        shutil.rmtree(chunks_dir, ignore_errors=True)

    chunks_dir.mkdir(parents=True, exist_ok=True)

    meta = load_metadata(Path(args.metadata))
    con = connect_duckdb(
        Path(args.main_db),
        Path(args.cont_db),
        Path(args.rec_db),
        Path(args.temp_dir),
        args.memory_limit,
        args.threads,
    )

    chunk_paths = []
    chunk_summaries = []

    for sequence, (selected_date, label) in enumerate(dates):
        safe_label = "".join(ch if ch.isalnum() else "_" for ch in label).strip("_").lower()
        chunk_path = chunks_dir / f"chunk_{sequence:02d}_{selected_date}_{safe_label}.csv"
        chunk_paths.append(chunk_path)

        if args.resume and chunk_path.exists():
            print("")
            print("=" * 90)
            print(f"RESUME: chunk {sequence + 1}/{len(dates)} already exists")
            print(f"Using: {chunk_path}")
            try:
                existing = pd.read_csv(chunk_path, usecols=["site_id", "volume"])
                chunk_summaries.append({
                    "date": selected_date,
                    "label": label,
                    "rows": int(len(existing)),
                    "distinct_sites": int(existing["site_id"].nunique()) if len(existing) else 0,
                    "total_volume": float(existing["volume"].sum()) if len(existing) else 0.0,
                    "chunk_csv": str(chunk_path),
                    "status": "resumed",
                })
                del existing
                gc.collect()
            except Exception as e:
                print(f"WARNING: could not summarize existing chunk: {e}")
            continue

        if chunk_path.exists():
            chunk_path.unlink()

        summary = process_date(
            con=con,
            meta=meta,
            selected_date=selected_date,
            label=label,
            sequence=sequence,
            total_dates=len(dates),
            chunk_path=chunk_path,
            min_volume=args.min_volume,
        )
        chunk_summaries.append(summary)

        completed = sequence + 1
        elapsed = time.time() - overall_start
        avg = elapsed / completed
        remaining = avg * (len(dates) - completed)

        print("")
        print("=" * 90)
        print("OVERALL PROGRESS")
        print("=" * 90)
        print(f"Completed        : {completed}/{len(dates)}")
        print(f"Elapsed          : {fmt_seconds(elapsed)}")
        print(f"Estimated remain : {fmt_seconds(remaining)}")
        print("=" * 90)

    final = merge_chunks(chunk_paths, output_csv)

    if final.empty:
        rows = 0
        distinct_sites = 0
        total_volume = 0.0
        periods = []
        t_min = None
        t_max = None
    else:
        rows = int(len(final))
        distinct_sites = int(final["site_id"].nunique())
        total_volume = float(final["volume"].sum())
        periods = sorted(final["comparison_period"].dropna().unique().tolist())
        t_min = str(final["animation_timestamp"].min())
        t_max = str(final["animation_timestamp"].max())

    summary = {
        "script_version": "V4_standalone_chunked",
        "animation": "covid_collapse_recovery_comparison",
        "rows": rows,
        "distinct_sites": distinct_sites,
        "total_volume": total_volume,
        "comparison_periods": periods,
        "animation_timestamp_start": t_min,
        "animation_timestamp_end": t_max,
        "selected_dates": [{"date": d, "label": label} for d, label in dates],
        "chunk_summaries": chunk_summaries,
        "output_csv": str(output_csv),
        "total_elapsed_seconds": round(time.time() - overall_start, 3),
        "total_elapsed_formatted": fmt_seconds(time.time() - overall_start),
    }

    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("")
    print("=" * 90)
    print("FINAL SUMMARY")
    print("=" * 90)
    print(f"Output CSV       : {output_csv}")
    print(f"Summary JSON     : {summary_json}")
    print(f"Rows             : {fmt_int(rows)}")
    print(f"Distinct sites   : {fmt_int(distinct_sites)}")
    print(f"Total volume     : {total_volume:,.0f}")
    print(f"Elapsed          : {summary['total_elapsed_formatted']}")
    print("")
    print("Kepler setup:")
    print("  Time field      : animation_timestamp")
    print("  Latitude field  : latitude")
    print("  Longitude field : longitude")
    print("  Size field      : scaled_volume_0_100")
    print("  Colour field    : comparison_period")
    print("=" * 90)

    if not args.keep_chunks:
        print("")
        print("Cleaning chunk directory...")
        shutil.rmtree(chunks_dir, ignore_errors=True)
    else:
        print("")
        print(f"Chunks kept at: {chunks_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
