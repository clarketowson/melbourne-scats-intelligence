#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
generate_all_scats_sites_map_json_v1.py

Builds an all-SCATS-sites Google Maps JSON layer.

Reads:
  - chunked_busiest_site_monthly.csv
  - busiestSCATSsitesCOORDINATES.csv / busiestSCATSsitesCOORDINATES(1).csv
  - SCATSSiteListingSpreadsheet.xls / .xlsx

Writes:
  - all_scats_sites_map_data.json
  - all_scats_sites_map_data_audit.csv

Design:
  - Aggregates total cleaned volume by SCATS site across all completed months.
  - Joins coordinates and names from lookup sources.
  - Adds traffic bands based on percentile ranking.
  - Keeps only sites with valid coordinates in the JSON.
  - Writes an audit CSV including mapped and unmapped sites.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


DEFAULT_BASE_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")
DEFAULT_OUTPUT_JSON = DEFAULT_BASE_DIR / "all_scats_sites_map_data.json"
DEFAULT_OUTPUT_AUDIT = DEFAULT_BASE_DIR / "all_scats_sites_map_data_audit.csv"


SITE_NAME_OVERRIDES = {
    "2816": "DIAMOND CREEK RD/GREENSBOROUGH HWY/CIVIC",
    "3376": "HODDLE NR STUDLEY (NORTHBOUND)",
}

COORDINATE_OVERRIDES = {
    # Manual coordinate overrides from the Top 20 map workflow.
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
        c_l = c.lower()
        if any(x in c_l for x in candidates):
            return c
    return None


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
            f"Could not detect site/volume columns. Columns: {list(df.columns)}"
        )

    out = pd.DataFrame()
    out["site_id"] = df[site_col].map(clean_site_id)
    out["volume"] = pd.to_numeric(df[vol_col], errors="coerce").fillna(0)

    if name_col:
        out["site_name_from_data"] = df[name_col].astype(str).replace({"nan": ""})
    else:
        out["site_name_from_data"] = ""

    out = out.dropna(subset=["site_id"])

    grouped = (
        out.groupby("site_id", as_index=False)
        .agg(
            total_cleaned_volume=("volume", "sum"),
            site_name_from_data=("site_name_from_data", lambda x: max([str(v) for v in x if str(v).strip()], key=len, default="")),
        )
    )

    grouped["total_cleaned_volume"] = grouped["total_cleaned_volume"].round().astype("int64")
    grouped = grouped[grouped["total_cleaned_volume"] > 0].copy()

    print(f"Aggregated site totals: {len(grouped):,} sites with positive volume")
    return grouped


def load_coordinate_csv(base_dir: Path) -> pd.DataFrame:
    paths = [
        base_dir / "busiestSCATSsitesCOORDINATES.csv",
        base_dir / "busiestSCATSsitesCOORDINATES(1).csv",
    ]

    frames = []

    for p in paths:
        if not p.exists():
            continue

        df = normalize_columns(pd.read_csv(p))
        site_col = find_col(df, ["site", "site_id", "scats_site", "scats_id"])
        name_col = find_col(df, ["site_name", "name", "description", "label"])
        lat_col = find_col(df, ["latitude", "lat", "y"])
        lon_col = find_col(df, ["longitude", "lng", "lon", "x"])

        if not site_col:
            print(f"  Coordinate CSV skipped: {p.name} -> no site column")
            continue

        out = pd.DataFrame()
        out["site_id"] = df[site_col].map(clean_site_id)
        out["site_name"] = df[name_col].astype(str).replace({"nan": ""}) if name_col else ""
        out["latitude"] = pd.to_numeric(df[lat_col], errors="coerce") if lat_col else np.nan
        out["longitude"] = pd.to_numeric(df[lon_col], errors="coerce") if lon_col else np.nan
        out["lookup_source"] = p.name

        out = out.dropna(subset=["site_id"])
        frames.append(out)
        print(f"Loaded coordinate lookup: {p.name} ({len(out):,} valid/raw rows)")

    if frames:
        return pd.concat(frames, ignore_index=True)

    return pd.DataFrame(columns=["site_id", "site_name", "latitude", "longitude", "lookup_source"])


def load_excel_site_listing(base_dir: Path) -> pd.DataFrame:
    paths = [
        base_dir / "SCATSSiteListingSpreadsheet.xls",
        base_dir / "SCATSSiteListingSpreadsheet.xlsx",
        base_dir / "SCATSSiteListingSpreadsheet(2).xls",
        base_dir / "SCATSSiteListingSpreadsheet(2).xlsx",
    ]

    best = None
    best_info = None

    for p in paths:
        if not p.exists():
            continue

        try:
            sheets = pd.read_excel(p, sheet_name=None, header=None)
        except Exception as e:
            print(f"WARNING: could not read Excel lookup {p}: {e}")
            continue

        for sheet_name, raw in sheets.items():
            raw = raw.dropna(how="all").dropna(axis=1, how="all")

            if raw.empty:
                continue

            # Try each of the first 15 rows as a header row.
            for header_row in range(min(15, len(raw))):
                temp = raw.iloc[header_row + 1:].copy()
                header = raw.iloc[header_row].astype(str).str.strip().tolist()
                temp.columns = header
                temp = normalize_columns(temp)

                site_col = find_col(temp, ["site_no", "site_number", "scats_site", "site_id", "site"])
                name_col = find_col(temp, ["location", "site_name", "description", "name", "site_description"])
                lat_col = find_col(temp, ["latitude", "lat"])
                lon_col = find_col(temp, ["longitude", "lng", "lon"])

                if not site_col:
                    continue

                out = pd.DataFrame()
                out["site_id"] = temp[site_col].map(clean_site_id)
                out["site_name"] = temp[name_col].astype(str).replace({"nan": ""}) if name_col else ""
                out["latitude"] = pd.to_numeric(temp[lat_col], errors="coerce") if lat_col else np.nan
                out["longitude"] = pd.to_numeric(temp[lon_col], errors="coerce") if lon_col else np.nan
                out["lookup_source"] = f"{p.name}:{sheet_name}"

                out = out.dropna(subset=["site_id"])
                out = out[out["site_id"].str.len() > 0]

                valid_count = len(out)
                if valid_count > 100:
                    print(
                        f"  Excel sheet candidate: {p.name} / {sheet_name!r} -> "
                        f"{valid_count:,} valid site rows (header row {header_row})"
                    )

                if best is None or valid_count > len(best):
                    best = out
                    best_info = (p.name, sheet_name, header_row, valid_count)

    if best is None:
        print("WARNING: no useful Excel site listing found")
        return pd.DataFrame(columns=["site_id", "site_name", "latitude", "longitude", "lookup_source"])

    print(
        f"Selected Excel site table from {best_info[0]} / {best_info[1]!r}: "
        f"{best_info[3]:,} valid site rows"
    )
    return best


def build_lookup(base_dir: Path) -> pd.DataFrame:
    frames = [
        load_coordinate_csv(base_dir),
        load_excel_site_listing(base_dir),
    ]

    lookup = pd.concat([f for f in frames if f is not None and not f.empty], ignore_index=True)

    if lookup.empty:
        return pd.DataFrame(columns=["site_id", "site_name", "latitude", "longitude", "lookup_source"])

    lookup["site_id"] = lookup["site_id"].map(clean_site_id)
    lookup["site_name"] = lookup["site_name"].fillna("").astype(str).str.strip()
    lookup["latitude"] = pd.to_numeric(lookup["latitude"], errors="coerce")
    lookup["longitude"] = pd.to_numeric(lookup["longitude"], errors="coerce")
    lookup["has_coords"] = lookup["latitude"].notna() & lookup["longitude"].notna()
    lookup["name_quality"] = lookup["site_name"].str.len()

    # Prefer rows with coordinates, then longer names.
    lookup = lookup.sort_values(
        ["site_id", "has_coords", "name_quality"],
        ascending=[True, False, False],
    )
    lookup = lookup.drop_duplicates("site_id", keep="first").copy()

    # Apply name overrides and coordinate overrides.
    for site_id, name in SITE_NAME_OVERRIDES.items():
        if site_id in set(lookup["site_id"]):
            lookup.loc[lookup["site_id"] == site_id, "site_name"] = name
        else:
            lookup = pd.concat([
                lookup,
                pd.DataFrame([{
                    "site_id": site_id,
                    "site_name": name,
                    "latitude": np.nan,
                    "longitude": np.nan,
                    "lookup_source": "manual_name_override",
                    "has_coords": False,
                    "name_quality": len(name),
                }])
            ], ignore_index=True)

    for site_id, coords in COORDINATE_OVERRIDES.items():
        if site_id in set(lookup["site_id"]):
            mask = lookup["site_id"] == site_id
            lookup.loc[mask, "latitude"] = coords["latitude"]
            lookup.loc[mask, "longitude"] = coords["longitude"]
            lookup.loc[mask, "lookup_source"] = coords["coordinate_source"]
        else:
            lookup = pd.concat([
                lookup,
                pd.DataFrame([{
                    "site_id": site_id,
                    "site_name": SITE_NAME_OVERRIDES.get(site_id, f"SCATS Site {site_id}"),
                    "latitude": coords["latitude"],
                    "longitude": coords["longitude"],
                    "lookup_source": coords["coordinate_source"],
                    "has_coords": True,
                    "name_quality": 20,
                }])
            ], ignore_index=True)

    lookup["has_coords"] = lookup["latitude"].notna() & lookup["longitude"].notna()

    print(f"Merged site lookup: {len(lookup):,} unique SCATS site IDs")
    print(f"Sites with coordinates in lookup: {lookup['has_coords'].sum():,}")
    return lookup[["site_id", "site_name", "latitude", "longitude", "lookup_source"]]


def friendly_name(raw_name: str, site_id: str) -> str:
    name = str(raw_name or "").strip()
    if not name:
        return f"SCATS Site {site_id}"

    # Make short SCATS abbreviations a bit more readable without over-claiming.
    text = name
    text = text.replace(" NR ", " near ")
    text = text.replace(" FWY ", " Freeway ")
    text = text.replace(" HWY", " Highway")
    text = text.replace(" PHE", " Princes Highway East")
    text = text.replace("PHE/", "Princes Highway East / ")
    text = text.replace("/", " / ")
    text = re.sub(r"\s+", " ", text).strip()

    # Title case only if it is mostly uppercase, but preserve acronyms reasonably.
    if text.upper() == text:
        text = text.title()
        replacements = {
            "Fwy": "Freeway",
            "Hwy": "Highway",
            "Mrr": "MRR",
            "Phe": "Princes Highway East",
            "Nr": "near",
        }
        for a, b in replacements.items():
            text = text.replace(a, b)

    return text


def traffic_band(percentile: float) -> str:
    if percentile >= 95:
        return "red"
    if percentile >= 80:
        return "orange"
    if percentile >= 50:
        return "yellow"
    return "green"


def main() -> None:
    base_dir = DEFAULT_BASE_DIR

    site_totals = load_site_monthly(base_dir)
    lookup = build_lookup(base_dir)

    df = site_totals.merge(lookup, on="site_id", how="left")
    df["site_name"] = df["site_name"].fillna(df["site_name_from_data"]).fillna("")
    df["friendly_name"] = [
        friendly_name(row.site_name, row.site_id)
        for row in df.itertuples(index=False)
    ]

    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["has_coordinates"] = df["latitude"].notna() & df["longitude"].notna()

    df = df.sort_values("total_cleaned_volume", ascending=False).reset_index(drop=True)
    df["rank"] = np.arange(1, len(df) + 1)

    # Percentile: busiest sites near 100.
    df["percentile_rank"] = df["total_cleaned_volume"].rank(pct=True) * 100.0
    df["traffic_band"] = df["percentile_rank"].map(traffic_band)
    max_volume = df["total_cleaned_volume"].max()
    df["volume_ratio"] = (df["total_cleaned_volume"] / max_volume).round(6)

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
        "total_cleaned_volume",
        "latitude",
        "longitude",
        "has_coordinates",
        "percentile_rank",
        "traffic_band",
        "lookup_source",
        "google_maps_url",
    ]
    df[audit_cols].to_csv(DEFAULT_OUTPUT_AUDIT, index=False)
    print(f"Wrote audit CSV: {DEFAULT_OUTPUT_AUDIT}")
    print(f"Audit rows: {len(df):,}")
    print(f"Rows with coordinates: {df['has_coordinates'].sum():,}")
    print(f"Rows without coordinates: {(~df['has_coordinates']).sum():,}")

    mapped = df[df["has_coordinates"]].copy()

    records = []
    for row in mapped.itertuples(index=False):
        records.append({
            "rank": int(row.rank),
            "site_id": str(row.site_id),
            "friendly_name": str(row.friendly_name),
            "official_name": str(row.site_name) if str(row.site_name).strip() else f"SCATS Site {row.site_id}",
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

    with open(DEFAULT_OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"Wrote JSON: {DEFAULT_OUTPUT_JSON}")
    print(f"Map records created: {len(records):,}")


if __name__ == "__main__":
    main()
