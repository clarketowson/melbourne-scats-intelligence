#!/usr/bin/env python3
r"""
generate_kepler_city_pulse_weekV1.py

Exports a Kepler.gl-ready animated "7 Day City Pulse of Melbourne" SCATS dataset.

V1 upgrade from generate_kepler_city_pulse_dayV2.py:
  - Exports 7 consecutive full days instead of one selected day.
  - Uses --start-date YYYY-MM-DD and automatically includes start date + 6 days.
  - Produces one combined Kepler-ready CSV for continuous animation.
  - Recognises volume_15m as the cleaned 15-minute volume column used by scats_clean.

Goal:
  Create one CSV with one row per SCATS site per 15-minute time bin for a selected 7-day period:
    timestamp, date_label, day_name, time_label, site_id, site_name, latitude, longitude,
    volume, scaled_volume, scaled_volume_0_100, intensity_band

This is designed for Kepler.gl animation:
  - Load CSV into Kepler.gl
  - Set timestamp as time field
  - Use latitude / longitude
  - Use volume or scaled_volume_0_100 for radius/weight
  - Animate continuously across the full week

Default selected period:
  2024-05-13 to 2024-05-19
A normal Monday-Sunday week candidate. Override with --start-date YYYY-MM-DD.

Inputs:
  DuckDB databases:
    A:\TrafficAnalytics\DATA\SCATS\scats.duckdb
    A:\TrafficAnalytics\DATA\SCATS\scats_continuation.duckdb
    A:\TrafficAnalytics\DATA\SCATS\scats_recovery.duckdb

  Site metadata:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\all_scats_sites_map_data_audit.csv

Output:
  A:\TrafficAnalytics\PROJECTS\reports\deduped\kepler_city_pulse\kepler_city_pulse_YYYY-MM-DD_to_YYYY-MM-DD.csv

Notes:
  - This queries the cleaned views directly.
  - It excludes sites without usable coordinates because Kepler needs lat/lon.
  - It keeps SCATS network nodes if they have coordinates.
  - A 7-day export is approximately 7x larger than the original one-day export.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import duckdb
import pandas as pd
import numpy as np


DEFAULT_MAIN_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats.duckdb"
DEFAULT_CONT_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats_continuation.duckdb"
DEFAULT_REC_DB = r"A:\TrafficAnalytics\DATA\SCATS\scats_recovery.duckdb"
DEFAULT_METADATA = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\all_scats_sites_map_data_audit.csv"
DEFAULT_OUTDIR = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\kepler_city_pulse"


def clean_label_text(text: str, max_len: int = 58) -> str:
    text = str(text or "").strip()
    if re.match(r"^\d{4}-\d{2}(-\d{2})?$", text):
        return ""
    if re.match(r"^\d+(\.0)?$", text):
        return ""
    if text.lower() in {"nan", "none", "null", "na", "n/a"}:
        return ""
    text = " ".join(text.replace("_", " ").split())
    if len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "…"
    return text


def load_metadata(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Metadata file not found: {path}")

    meta = pd.read_csv(path, low_memory=False)
    cols = {c.lower(): c for c in meta.columns}

    for required in ["site_id", "latitude", "longitude"]:
        if required not in cols:
            raise ValueError(f"Metadata missing required column {required}. Columns: {list(meta.columns)}")

    name_col = None
    for candidate in ["friendly_name", "site_name", "location", "description", "name"]:
        if candidate in cols:
            name_col = cols[candidate]
            break

    out = pd.DataFrame({
        "site_id": meta[cols["site_id"]].astype(str).str.strip(),
        "latitude": pd.to_numeric(meta[cols["latitude"]], errors="coerce"),
        "longitude": pd.to_numeric(meta[cols["longitude"]], errors="coerce"),
        "site_name": meta[name_col].fillna("").astype(str).map(clean_label_text) if name_col else "",
    })

    out = out.dropna(subset=["latitude", "longitude"])
    out = out[
        (out["latitude"].between(-39.5, -36.0)) &
        (out["longitude"].between(143.0, 146.5))
    ].copy()

    missing = out["site_name"].eq("")
    out.loc[missing, "site_name"] = "SCATS " + out.loc[missing, "site_id"] + " (network node)"
    return out.drop_duplicates(subset=["site_id"], keep="first")


def connect_duckdb(main_db: Path, cont_db: Path, rec_db: Path, temp_dir: Path, memory_limit: str, threads: int) -> duckdb.DuckDBPyConnection:
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
    else:
        print(f"WARNING: continuation DB not found, skipping: {cont_db}")

    if rec_db.exists():
        con.execute(f"ATTACH '{str(rec_db).replace(chr(92), '/')}' AS rec")
    else:
        print(f"WARNING: recovery DB not found, skipping: {rec_db}")

    return con


def table_exists(con: duckdb.DuckDBPyConnection, name: str) -> bool:
    try:
        con.execute(f"SELECT 1 FROM {name} LIMIT 1")
        return True
    except Exception:
        return False


def detect_columns(con: duckdb.DuckDBPyConnection, view_name: str) -> dict[str, str]:
    info = con.execute(f"DESCRIBE {view_name}").fetchdf()
    cols = {c.lower(): c for c in info["column_name"].tolist()}

    def pick(cands, label):
        for c in cands:
            if c.lower() in cols:
                return cols[c.lower()]
        raise ValueError(f"Could not find {label} column in {view_name}. Columns: {list(cols.values())}")

    return {
        "site": pick(["site_id", "nb_scats_site", "scats_site", "site"], "site"),
        "date": pick(["date", "count_date", "day", "traffic_date"], "date"),
        "time": pick(["time", "time_bin", "interval_time", "time_of_day"], "time"),
        "volume": pick(["volume", "volume_15m", "vehicles", "count", "vehicle_count", "veh_count", "sum_volume"], "volume"),
    }


def build_union_sql(con: duckdb.DuckDBPyConnection, start_date: str, end_date: str) -> str:
    sources = []
    for view_name in ["scats_clean", "cont.scats_clean", "rec.scats_clean"]:
        if table_exists(con, view_name):
            c = detect_columns(con, view_name)
            print(f"Detected columns in {view_name}: site={c['site']}, date={c['date']}, time={c['time']}, volume={c['volume']}")
            sources.append(f"""
                SELECT
                    CAST({c['site']} AS VARCHAR) AS site_id,
                    CAST({c['date']} AS DATE) AS count_date,
                    CAST({c['time']} AS VARCHAR) AS time_value,
                    TRY_CAST({c['volume']} AS DOUBLE) AS volume
                FROM {view_name}
                WHERE CAST({c['date']} AS DATE) BETWEEN DATE '{start_date}' AND DATE '{end_date}'
                  AND TRY_CAST({c['volume']} AS DOUBLE) IS NOT NULL
                  AND TRY_CAST({c['volume']} AS DOUBLE) >= 0
            """)
    if not sources:
        raise RuntimeError("No scats_clean views found in main/attached databases.")
    return "\nUNION ALL\n".join(sources)


def export_week(con: duckdb.DuckDBPyConnection, start_date: str, end_date: str) -> pd.DataFrame:
    union_sql = build_union_sql(con, start_date, end_date)
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
    ORDER BY count_date, time_bin, site_id
    """
    return con.execute(query).fetchdf()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", default="2024-05-13", help="Start date for 7-day export, YYYY-MM-DD")
    parser.add_argument("--main-db", default=DEFAULT_MAIN_DB)
    parser.add_argument("--cont-db", default=DEFAULT_CONT_DB)
    parser.add_argument("--rec-db", default=DEFAULT_REC_DB)
    parser.add_argument("--metadata", default=DEFAULT_METADATA)
    parser.add_argument("--outdir", default=DEFAULT_OUTDIR)
    parser.add_argument("--temp-dir", default=r"C:\DuckDBTemp")
    parser.add_argument("--memory-limit", default="50GB")
    parser.add_argument("--threads", type=int, default=10)
    parser.add_argument("--min-volume", type=float, default=1.0)
    args = parser.parse_args()

    start_dt = pd.to_datetime(args.start_date)
    end_dt = start_dt + pd.Timedelta(days=6)
    start_date = start_dt.strftime("%Y-%m-%d")
    end_date = end_dt.strftime("%Y-%m-%d")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    print("=" * 90)
    print("KEPLER CITY PULSE 7-DAY EXPORT V1")
    print("=" * 90)
    print(f"Start date    : {start_date}")
    print(f"End date      : {end_date}")
    print("Days exported : 7")
    print(f"Output dir    : {outdir}")
    print(f"Metadata      : {args.metadata}")
    print("=" * 90)

    meta = load_metadata(Path(args.metadata))
    print(f"Metadata sites with coordinates: {len(meta):,}")

    con = connect_duckdb(
        Path(args.main_db),
        Path(args.cont_db),
        Path(args.rec_db),
        Path(args.temp_dir),
        args.memory_limit,
        args.threads,
    )

    week = export_week(con, start_date, end_date)
    print(f"Raw site/time rows exported from DuckDB: {len(week):,}")

    if week.empty:
        print("ERROR: no rows for selected 7-day period.")
        return 2

    week["site_id"] = week["site_id"].astype(str).str.strip()
    week["volume"] = pd.to_numeric(week["volume"], errors="coerce").fillna(0)
    week = week[week["volume"] >= args.min_volume].copy()

    merged = week.merge(meta, on="site_id", how="inner")
    print(f"Rows after coordinate join: {len(merged):,}")
    print(f"Distinct mapped sites     : {merged['site_id'].nunique():,}")

    merged["timestamp"] = pd.to_datetime(
        merged["count_date"].astype(str) + " " + merged["time_bin"].astype(str),
        errors="coerce",
    )
    merged = merged.dropna(subset=["timestamp"]).copy()

    merged["date_label"] = merged["timestamp"].dt.strftime("%Y-%m-%d")
    merged["day_name"] = merged["timestamp"].dt.day_name()
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

    final = merged[[
        "timestamp",
        "date_label",
        "day_name",
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
    ]].sort_values(["timestamp", "volume"], ascending=[True, False])

    out_csv = outdir / f"kepler_city_pulse_{start_date}_to_{end_date}.csv"
    final.to_csv(out_csv, index=False)

    out_json = outdir / f"kepler_city_pulse_{start_date}_to_{end_date}_summary.json"
    summary = {
        "start_date": start_date,
        "end_date": end_date,
        "days": 7,
        "rows": int(len(final)),
        "distinct_sites": int(final["site_id"].nunique()),
        "unique_timestamps": int(final["timestamp"].nunique()),
        "expected_15min_bins_for_7_days": 672,
        "time_labels_per_day": int(final["time_label"].nunique()),
        "total_volume": float(final["volume"].sum()),
        "max_15min_site_volume": float(final["volume"].max()),
        "output_csv": str(out_csv),
    }
    pd.Series(summary).to_json(out_json, indent=2)

    print("-" * 90)
    print(f"Wrote CSV       : {out_csv}")
    print(f"Wrote summary   : {out_json}")
    print(f"Rows            : {len(final):,}")
    print(f"Distinct sites  : {final['site_id'].nunique():,}")
    print(f"Unique timestamps: {final['timestamp'].nunique():,}")
    print(f"Time labels/day : {final['time_label'].nunique():,}")
    print(f"Total volume    : {final['volume'].sum():,.0f}")
    print(f"Max point volume: {final['volume'].max():,.0f}")
    print("-" * 90)
    print("Kepler setup:")
    print("  Layer type     : Point")
    print("  Latitude field : latitude")
    print("  Longitude field: longitude")
    print("  Time field     : timestamp")
    print("  Size field     : scaled_volume_0_100 or volume")
    print("  Color field    : intensity_band or volume")
    print("=" * 90)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
