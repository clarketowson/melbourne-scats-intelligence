#!/usr/bin/env python3
"""
generate_kepler_seasonal_top100_monthly_pulseV2.py

Fixed V2 of generate_kepler_seasonal_top100_monthly_pulseV1.py.

V1 failed because site_month_totals.csv uses:
  month_site_volume

instead of:
  month_total_volume / site_month_total_volume / total_volume / volume

V2 supports:
  - month_site_volume
  - scats_site
  - month_start
  - month_label
  - row_type filtering
  - joins to all_scats_sites_map_data_audit.csv for lat/lon/site_name
  - top-N filtering by cumulative volume
  - Kepler-ready monthly animation timestamp

Inputs:
  A:\TrafficAnalytics\PROJECTS\reports\deduped\site_month_totals.csv
  A:\TrafficAnalytics\PROJECTS\reports\deduped\all_scats_sites_map_data_audit.csv

Output:
  A:\TrafficAnalytics\PROJECTS\reports\deduped\kepler_animation_exports\kepler_seasonal_top100_monthly_pulse.csv

Kepler:
  latitude field: latitude
  longitude field: longitude
  time field: animation_timestamp
  size field: scaled_volume_0_100
  colour field: seasonal_band / month_name / volume
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_SITE_MONTH_CSV = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\site_month_totals.csv"
DEFAULT_METADATA = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\all_scats_sites_map_data_audit.csv"
DEFAULT_OUTDIR = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\kepler_animation_exports"


MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}


def fmt_int(x) -> str:
    try:
        return f"{int(x):,}"
    except Exception:
        return str(x)


def find_col(cols, candidates, label, required=True):
    lookup = {c.lower(): c for c in cols}
    for c in candidates:
        if c.lower() in lookup:
            return lookup[c.lower()]
    if required:
        raise ValueError(f"Could not find {label}. Columns: {list(cols)}")
    return None


def load_metadata(path: Path) -> pd.DataFrame:
    print("")
    print("Loading metadata...")
    print(f"Metadata file: {path}")

    if not path.exists():
        raise FileNotFoundError(f"Metadata file not found: {path}")

    df = pd.read_csv(path, low_memory=False)

    site_col = find_col(df.columns, ["site_id", "scats_site", "nb_scats_site", "site"], "site")
    lat_col = find_col(df.columns, ["latitude", "lat"], "latitude")
    lon_col = find_col(df.columns, ["longitude", "lng", "lon"], "longitude")
    name_col = find_col(df.columns, ["friendly_name", "site_name", "name", "location", "description"], "site name", required=False)

    meta = pd.DataFrame({
        "site_id": df[site_col].astype(str).str.strip(),
        "latitude": pd.to_numeric(df[lat_col], errors="coerce"),
        "longitude": pd.to_numeric(df[lon_col], errors="coerce"),
    })

    if name_col:
        meta["site_name"] = df[name_col].fillna("").astype(str)
    else:
        meta["site_name"] = "SCATS " + meta["site_id"]

    meta = meta.dropna(subset=["latitude", "longitude"])
    meta = meta[
        (meta["latitude"].between(-39.5, -36.0)) &
        (meta["longitude"].between(143.0, 146.5))
    ].copy()

    meta = meta.drop_duplicates(subset=["site_id"], keep="first")
    print(f"Metadata mapped sites: {fmt_int(len(meta))}")
    return meta


def seasonal_band(month: int) -> str:
    if month in (12, 1, 2):
        return "summer"
    if month in (3, 4, 5):
        return "autumn"
    if month in (6, 7, 8):
        return "winter"
    return "spring"


def main() -> int:
    p = argparse.ArgumentParser(description="Export seasonal Top 100 monthly SCATS pulse dataset for Kepler.gl.")
    p.add_argument("--site-month-csv", default=DEFAULT_SITE_MONTH_CSV)
    p.add_argument("--metadata", default=DEFAULT_METADATA)
    p.add_argument("--outdir", default=DEFAULT_OUTDIR)
    p.add_argument("--top-n", type=int, default=100)
    p.add_argument("--min-volume", type=float, default=1.0)
    p.add_argument("--output-name", default="kepler_seasonal_top100_monthly_pulse.csv")
    args = p.parse_args()

    site_month_path = Path(args.site_month_csv)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    out_csv = outdir / args.output_name
    out_summary = out_csv.with_name(out_csv.stem + "_summary.json")

    print("=" * 90)
    print("KEPLER SEASONAL TOP 100 MONTHLY PULSE EXPORT V2")
    print("=" * 90)
    print(f"Input site-month CSV : {site_month_path}")
    print(f"Metadata             : {args.metadata}")
    print(f"Output CSV           : {out_csv}")
    print(f"Top N sites          : {args.top_n}")
    print(f"Min volume           : {args.min_volume}")
    print("=" * 90)

    if not site_month_path.exists():
        raise FileNotFoundError(f"Site-month CSV not found: {site_month_path}")

    meta = load_metadata(Path(args.metadata))

    print("")
    print("Loading site-month totals...")
    df = pd.read_csv(site_month_path, low_memory=False)
    print(f"Loaded rows: {fmt_int(len(df))}")
    print(f"Columns: {list(df.columns)}")

    site_col = find_col(df.columns, ["site_id", "scats_site", "nb_scats_site", "site"], "site")
    vol_col = find_col(
        df.columns,
        [
            "month_site_volume",
            "site_month_total_volume",
            "month_total_volume",
            "total_volume",
            "volume",
        ],
        "volume",
    )
    month_start_col = find_col(df.columns, ["month_start", "month", "date", "month_date"], "month start")
    month_label_col = find_col(df.columns, ["month_label", "month_name"], "month label", required=False)
    row_type_col = find_col(df.columns, ["row_type"], "row type", required=False)

    print("")
    print("Detected columns:")
    print(f"  site column       : {site_col}")
    print(f"  volume column     : {vol_col}")
    print(f"  month_start column: {month_start_col}")
    print(f"  month_label column: {month_label_col}")
    print(f"  row_type column   : {row_type_col}")

    if row_type_col:
        before = len(df)
        df = df[df[row_type_col].fillna("").astype(str).str.lower().isin(["", "data", "normal", "complete"]) | df[row_type_col].isna()].copy()
        # If this accidentally filters everything due unknown labels, fall back to original.
        if df.empty:
            print("WARNING: row_type filtering removed all rows; reloading without row_type filter.")
            df = pd.read_csv(site_month_path, low_memory=False)
        else:
            print(f"Rows after row_type filter: {fmt_int(len(df))} / {fmt_int(before)}")

    print("")
    print("Cleaning fields...")
    df["site_id"] = df[site_col].astype(str).str.strip()
    df["volume"] = pd.to_numeric(df[vol_col], errors="coerce").fillna(0)
    df["month_start"] = pd.to_datetime(df[month_start_col], errors="coerce")

    df = df.dropna(subset=["month_start"])
    df = df[df["volume"] >= args.min_volume].copy()

    if month_label_col:
        df["month_label"] = df[month_label_col].astype(str)
    else:
        df["month_label"] = df["month_start"].dt.strftime("%Y-%m")

    print(f"Rows after cleaning/min-volume: {fmt_int(len(df))}")
    print(f"Distinct sites before top-N   : {fmt_int(df['site_id'].nunique())}")
    print(f"Month range                   : {df['month_start'].min().date()} to {df['month_start'].max().date()}")

    print("")
    print("Selecting Top N sites by cumulative monthly volume...")
    site_totals = (
        df.groupby("site_id", as_index=False)["volume"]
        .sum()
        .rename(columns={"volume": "site_total_volume"})
        .sort_values("site_total_volume", ascending=False)
    )
    top_sites = site_totals.head(args.top_n).copy()
    top_sites["site_rank"] = range(1, len(top_sites) + 1)
    print(f"Top sites selected: {fmt_int(len(top_sites))}")
    print("Top 10 preview:")
    print(top_sites.head(10).to_string(index=False))

    print("")
    print("Filtering to Top N and joining coordinates...")
    top = df.merge(top_sites, on="site_id", how="inner")
    top = top.merge(meta, on="site_id", how="inner")
    print(f"Rows after top-N + coordinate join: {fmt_int(len(top))}")
    print(f"Distinct mapped top sites         : {fmt_int(top['site_id'].nunique())}")

    if top.empty:
        raise RuntimeError("No rows remain after top-N coordinate join. Check metadata site IDs.")

    print("")
    print("Adding Kepler animation fields...")
    top["year"] = top["month_start"].dt.year
    top["month_of_year"] = top["month_start"].dt.month
    top["month_name"] = top["month_of_year"].map(MONTH_NAMES)
    top["seasonal_band"] = top["month_of_year"].map(seasonal_band)

    # Use the real month_start as animation timestamp.
    top["animation_timestamp"] = top["month_start"]

    # Scaling fields
    top["scaled_volume"] = np.log1p(top["volume"])
    max_scaled = top["scaled_volume"].max()
    top["scaled_volume_0_100"] = top["scaled_volume"] / max_scaled * 100 if max_scaled > 0 else 0

    q50, q75, q90, q98 = top["volume"].quantile([0.50, 0.75, 0.90, 0.98])

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

    top["intensity_band"] = top["volume"].map(band)

    final_cols = [
        "animation_timestamp",
        "month_start",
        "month_label",
        "year",
        "month_of_year",
        "month_name",
        "seasonal_band",
        "site_rank",
        "site_id",
        "site_name",
        "latitude",
        "longitude",
        "volume",
        "site_total_volume",
        "scaled_volume",
        "scaled_volume_0_100",
        "intensity_band",
    ]

    final = top[final_cols].sort_values(["animation_timestamp", "site_rank"]).copy()

    print("")
    print("Writing output...")
    final.to_csv(out_csv, index=False)

    summary = {
        "animation": "seasonal_top100_monthly_pulse",
        "script_version": "V2",
        "input_csv": str(site_month_path),
        "metadata": str(args.metadata),
        "output_csv": str(out_csv),
        "rows": int(len(final)),
        "top_n": int(args.top_n),
        "distinct_sites": int(final["site_id"].nunique()),
        "months": int(final["month_start"].nunique()),
        "date_range_start": str(final["month_start"].min().date()),
        "date_range_end": str(final["month_start"].max().date()),
        "total_volume": float(final["volume"].sum()),
        "max_month_site_volume": float(final["volume"].max()),
        "volume_column_used": vol_col,
    }

    out_summary.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("-" * 90)
    print(f"Wrote CSV       : {out_csv}")
    print(f"Wrote summary   : {out_summary}")
    print(f"Rows            : {fmt_int(len(final))}")
    print(f"Distinct sites  : {fmt_int(final['site_id'].nunique())}")
    print(f"Months          : {fmt_int(final['month_start'].nunique())}")
    print(f"Total volume    : {final['volume'].sum():,.0f}")
    print("-" * 90)
    print("Kepler setup:")
    print("  Layer type      : Point")
    print("  Latitude field  : latitude")
    print("  Longitude field : longitude")
    print("  Time field      : animation_timestamp")
    print("  Size field      : scaled_volume_0_100 or volume")
    print("  Colour field    : seasonal_band, month_name, intensity_band or volume")
    print("=" * 90)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
