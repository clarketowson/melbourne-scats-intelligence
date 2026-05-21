#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
generate_all_scats_sites_map_json_v2.py

Builds a Melbourne-wide SCATS sites Google Maps JSON layer using the full
Victorian traffic signals / SCATS location file as the primary coordinate source.

Primary coordinate source:
  victorian_traffic_signals_all_SCATS_locations.csv

Traffic volume source:
  chunked_busiest_site_monthly.csv

Outputs:
  all_scats_sites_map_data.json
  all_scats_sites_map_data_audit.csv

Expected result:
  Thousands of mapped SCATS sites, not just the prior 99-site subset.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


DEFAULT_BASE_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")

SITE_NAME_OVERRIDES = {
    "2816": "DIAMOND CREEK RD/GREENSBOROUGH HWY/CIVIC",
    "3376": "HODDLE NR STUDLEY (NORTHBOUND)",
}

COORDINATE_OVERRIDES = {
    "2816": {
        "latitude": -37.68909,
        "longitude": 145.11328,
        "coordinate_source": "manual_override_roundabout_database",
    },
    "3376": {
        "latitude": -37.80240,
        "longitude": 144.99245,
        "coordinate_source": "manual_override_approx_hoddle_near_studley",
    },
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [
        str(c).strip().lower().replace(" ", "_").replace("-", "_")
        for c in df.columns
    ]
    return df


def clean_site_id(value) -> Optional[str]:
    if pd.isna(value):
        return None
    s = str(value).strip()
    if not s:
        return None
    m = re.search(r"\d+", s)
    if not m:
        return None
    try:
        return str(int(m.group(0)))
    except Exception:
        return None


def first_existing(base_dir: Path, names: list[str]) -> Optional[Path]:
    for name in names:
        p = base_dir / name
        if p.exists():
            return p
    return None


def find_col(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    cols = list(df.columns)
    for c in candidates:
        if c in cols:
            return c
    for c in cols:
        c_l = str(c).lower()
        if any(x in c_l for x in candidates):
            return c
    return None


def friendly_name(raw_name: str, site_id: str) -> str:
    name = str(raw_name or "").strip()
    if not name or name.lower() == "nan":
        return f"SCATS Site {site_id}"

    text = name.strip()
    text = text.replace(" NR ", " near ")
    text = text.replace(" BTW ", " between ")
    text = text.replace(" FWY ", " Freeway ")
    text = text.replace(" HWY", " Highway")
    text = text.replace("PHE", "Princes Highway East")
    text = text.replace("/", " / ")
    text = re.sub(r"\s+", " ", text).strip()

    # Title case if source is all-caps, with common acronyms restored.
    if text.upper() == text:
        text = text.title()
        replacements = {
            "Fwy": "Freeway",
            "Hwy": "Highway",
            "Mrr": "MRR",
            "Phe": "Princes Highway East",
            "Nr": "near",
            "Btw": "between",
            "Cbd": "CBD",
            "Rd": "Road",
            "St": "Street",
            "Ave": "Avenue",
        }
        for src, dst in replacements.items():
            text = text.replace(src, dst)

    return text


def traffic_band(percentile: float) -> str:
    # Busiest sites have percentile near 100.
    if percentile >= 95:
        return "red"
    if percentile >= 80:
        return "orange"
    if percentile >= 50:
        return "yellow"
    return "green"


def load_site_monthly(base_dir: Path) -> pd.DataFrame:
    p = first_existing(base_dir, [
        "chunked_busiest_site_monthly.csv",
        "chunked_busiest_site_monthly(6).csv",
        "busiest_site_monthly.csv",
    ])

    if not p:
        raise FileNotFoundError(
            f"Could not find chunked_busiest_site_monthly.csv in {base_dir}"
        )

    df = normalize_columns(pd.read_csv(p))
    print(f"Loaded site monthly CSV: {p.name} ({len(df):,} rows)")

    site_col = find_col(df, ["site", "site_id", "scats_site", "scats_id"])
    vol_col = find_col(df, [
        "volume",
        "total_volume",
        "total_cleaned_volume",
        "monthly_volume",
        "total_cleaned",
        "cleaned_vehicle_movements",
    ])
    name_col = find_col(df, ["site_name", "name", "description", "label"])

    if not site_col or not vol_col:
        raise RuntimeError(
            f"Could not detect site/volume columns in {p.name}. Columns: {list(df.columns)}"
        )

    out = pd.DataFrame()
    out["site_id"] = df[site_col].map(clean_site_id)
    out["volume"] = pd.to_numeric(df[vol_col], errors="coerce").fillna(0)

    if name_col:
        out["site_name_from_volume_csv"] = df[name_col].fillna("").astype(str)
    else:
        out["site_name_from_volume_csv"] = ""

    out = out.dropna(subset=["site_id"])

    grouped = (
        out.groupby("site_id", as_index=False)
        .agg(
            total_cleaned_volume=("volume", "sum"),
            site_name_from_volume_csv=(
                "site_name_from_volume_csv",
                lambda x: max([str(v).strip() for v in x if str(v).strip() and str(v).lower() != "nan"], key=len, default=""),
            ),
        )
    )

    grouped["total_cleaned_volume"] = grouped["total_cleaned_volume"].round().astype("int64")
    grouped = grouped[grouped["total_cleaned_volume"] > 0].copy()

    print(f"Aggregated positive-volume SCATS site totals: {len(grouped):,}")
    return grouped


def load_full_scats_locations(base_dir: Path) -> pd.DataFrame:
    p = first_existing(base_dir, [
        "victorian_traffic_signals_all_SCATS_locations.csv",
        "victorian_traffic_signals_all_SCATS_locations(1).csv",
    ])

    if not p:
        raise FileNotFoundError(
            "Could not find victorian_traffic_signals_all_SCATS_locations.csv "
            f"in {base_dir}. Copy it into the reports/deduped folder first."
        )

    df = normalize_columns(pd.read_csv(p))
    print(f"Loaded full SCATS location CSV: {p.name} ({len(df):,} rows)")

    site_col = find_col(df, ["site_no", "site_number", "site", "site_id", "scats_site", "scats_id"])
    name_col = find_col(df, ["site_name", "location", "description", "name"])
    type_col = find_col(df, ["type"])
    muni_col = find_col(df, ["municipality", "lga", "council"])
    lat_col = find_col(df, ["latitude", "lat"])
    lon_col = find_col(df, ["longitude", "lng", "lon"])

    if not site_col or not lat_col or not lon_col:
        raise RuntimeError(
            f"Could not detect required site/latitude/longitude columns. Columns: {list(df.columns)}"
        )

    out = pd.DataFrame()
    out["site_id"] = df[site_col].map(clean_site_id)
    out["site_name"] = df[name_col].fillna("").astype(str).str.strip() if name_col else ""
    out["signal_type"] = df[type_col].fillna("").astype(str).str.strip() if type_col else ""
    out["municipality"] = df[muni_col].fillna("").astype(str).str.strip() if muni_col else ""
    out["latitude"] = pd.to_numeric(df[lat_col], errors="coerce")
    out["longitude"] = pd.to_numeric(df[lon_col], errors="coerce")
    out["lookup_source"] = p.name

    out = out.dropna(subset=["site_id"])
    out = out[out["latitude"].between(-40, -33, inclusive="both")]
    out = out[out["longitude"].between(140, 150, inclusive="both")]

    # Prefer rows with names and coordinates; dedupe by site ID.
    out["name_quality"] = out["site_name"].str.len()
    out = out.sort_values(["site_id", "name_quality"], ascending=[True, False])
    out = out.drop_duplicates("site_id", keep="first").copy()

    print(f"Full SCATS locations with valid coordinates: {len(out):,}")
    return out[[
        "site_id",
        "site_name",
        "signal_type",
        "municipality",
        "latitude",
        "longitude",
        "lookup_source",
    ]]


def apply_overrides(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for site_id, name in SITE_NAME_OVERRIDES.items():
        mask = df["site_id"] == site_id
        if mask.any():
            df.loc[mask, "site_name"] = name

    for site_id, coords in COORDINATE_OVERRIDES.items():
        mask = df["site_id"] == site_id
        if mask.any():
            df.loc[mask, "latitude"] = coords["latitude"]
            df.loc[mask, "longitude"] = coords["longitude"]
            df.loc[mask, "lookup_source"] = coords["coordinate_source"]

    return df


def build_all_sites_map_data(base_dir: Path, output_json: Path, output_audit: Path) -> None:
    site_totals = load_site_monthly(base_dir)
    locations = load_full_scats_locations(base_dir)

    df = site_totals.merge(locations, on="site_id", how="left")
    df = apply_overrides(df)

    # Use location CSV name first, fall back to volume CSV name.
    df["site_name"] = df["site_name"].fillna("").astype(str).str.strip()
    df["site_name_from_volume_csv"] = df["site_name_from_volume_csv"].fillna("").astype(str).str.strip()
    df.loc[df["site_name"] == "", "site_name"] = df.loc[df["site_name"] == "", "site_name_from_volume_csv"]

    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["has_coordinates"] = df["latitude"].notna() & df["longitude"].notna()
    df["friendly_name"] = [
        friendly_name(row.site_name, row.site_id)
        for row in df.itertuples(index=False)
    ]

    df = df.sort_values("total_cleaned_volume", ascending=False).reset_index(drop=True)
    df["rank"] = np.arange(1, len(df) + 1)
    df["percentile_rank"] = df["total_cleaned_volume"].rank(pct=True) * 100.0
    df["traffic_band"] = df["percentile_rank"].map(traffic_band)

    max_volume = df["total_cleaned_volume"].max()
    df["volume_ratio"] = (df["total_cleaned_volume"] / max_volume).round(6)

    # URLs.
    df["google_maps_url"] = np.where(
        df["has_coordinates"],
        "https://www.google.com/maps/search/?api=1&query="
        + df["latitude"].astype(str)
        + ","
        + df["longitude"].astype(str),
        "https://www.google.com/maps/search/?api=1&query="
        + ("SCATS " + df["site_id"].astype(str) + " " + df["friendly_name"].astype(str) + " Victoria").str.replace(" ", "%20", regex=False),
    )

    audit_cols = [
        "rank",
        "site_id",
        "friendly_name",
        "site_name",
        "site_name_from_volume_csv",
        "signal_type",
        "municipality",
        "total_cleaned_volume",
        "latitude",
        "longitude",
        "has_coordinates",
        "percentile_rank",
        "traffic_band",
        "volume_ratio",
        "lookup_source",
        "google_maps_url",
    ]

    for c in audit_cols:
        if c not in df.columns:
            df[c] = ""

    df[audit_cols].to_csv(output_audit, index=False)
    print(f"Wrote audit CSV: {output_audit}")
    print(f"Audit rows: {len(df):,}")
    print(f"Rows with coordinates: {int(df['has_coordinates'].sum()):,}")
    print(f"Rows without coordinates: {int((~df['has_coordinates']).sum()):,}")

    mapped = df[df["has_coordinates"]].copy()

    records = []
    for row in mapped.itertuples(index=False):
        records.append({
            "rank": int(row.rank),
            "site_id": str(row.site_id),
            "friendly_name": str(row.friendly_name),
            "official_name": str(row.site_name) if str(row.site_name).strip() else f"SCATS Site {row.site_id}",
            "signal_type": str(row.signal_type) if hasattr(row, "signal_type") else "",
            "municipality": str(row.municipality) if hasattr(row, "municipality") else "",
            "lat": float(row.latitude),
            "lng": float(row.longitude),
            "total": int(row.total_cleaned_volume),
            "total_millions": round(int(row.total_cleaned_volume) / 1_000_000, 1),
            "percentile_rank": round(float(row.percentile_rank), 2),
            "traffic_band": str(row.traffic_band),
            "volume_ratio": float(row.volume_ratio),
            "lookup_source": str(row.lookup_source),
            "google_maps_url": str(row.google_maps_url),
        })

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"Wrote JSON: {output_json}")
    print(f"Map records created: {len(records):,}")

    print("\nTraffic band counts:")
    if records:
        band_counts = pd.Series([r["traffic_band"] for r in records]).value_counts()
        for band, count in band_counts.items():
            print(f"  {band}: {count:,}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-dir",
        default=str(DEFAULT_BASE_DIR),
        help="Directory containing input CSVs and where outputs are written.",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Output JSON path. Defaults to base-dir/all_scats_sites_map_data.json",
    )
    parser.add_argument(
        "--output-audit",
        default=None,
        help="Output audit CSV path. Defaults to base-dir/all_scats_sites_map_data_audit.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_dir = Path(args.base_dir)

    output_json = Path(args.output_json) if args.output_json else base_dir / "all_scats_sites_map_data.json"
    output_audit = Path(args.output_audit) if args.output_audit else base_dir / "all_scats_sites_map_data_audit.csv"

    build_all_sites_map_data(base_dir, output_json, output_audit)


if __name__ == "__main__":
    main()
