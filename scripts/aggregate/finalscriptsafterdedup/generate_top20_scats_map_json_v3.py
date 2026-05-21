#!/usr/bin/env python3
"""
generate_top20_scats_map_json_v3.py

Creates top_20_scats_map_data.json for the SCATS Top 20 Google Map.

Why this version exists:
- The chart CSV may contain site_name but blank latitude/longitude.
- This script rebuilds coordinates by joining the Top 20 list to the SCATS coordinate lookup CSV.
- It also applies known manual overrides for sites that are not present in the coordinate CSV.

Expected inputs, by default:
  A:\TrafficAnalytics\PROJECTS\reports\deduped\charts\top_20_busiest_scats_sites_named.csv
  A:\TrafficAnalytics\PROJECTS\reports\deduped\busiestSCATSsitesCOORDINATES.csv

Output:
  A:\TrafficAnalytics\PROJECTS\reports\deduped\top_20_scats_map_data.json
  A:\TrafficAnalytics\PROJECTS\reports\deduped\top_20_scats_map_data_unresolved.csv
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Optional

import pandas as pd


# Known corrections / fallbacks.
# Note: 2816 coordinates come from the Greensborough Hwy / Diamond Creek Rd / Civic Dr roundabout location.
# 3376 is a manual approximate point on Hoddle St near Studley; verify/refine if you later obtain official coordinates.
SITE_OVERRIDES = {
    "2816": {
        "name": "DIAMOND CREEK RD/GREENSBOROUGH HWY/CIVIC",
        "lat": -37.68909,
        "lng": 145.11328,
        "coordinate_source": "manual_override_roundabout_database",
    },
    "3376": {
        "name": "HODDLE NR STUDLEY (NORTHBOUND)",
        "lat": -37.80240,
        "lng": 144.99245,
        "coordinate_source": "manual_override_approx_hoddle_near_studley",
    },
}


DEFAULT_REPORTS_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")
DEFAULT_CHARTS_DIR = DEFAULT_REPORTS_DIR / "charts"


def clean_site_id(value) -> Optional[str]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return None
    # Accept values like 4415, 4415.0, "Site 4415".
    m = re.search(r"\d+", s)
    if not m:
        return None
    return str(int(m.group(0)))


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def pick_first_existing(df: pd.DataFrame, names: list[str]) -> Optional[str]:
    for n in names:
        if n in df.columns:
            return n
    return None


def load_top20(top20_path: Path) -> pd.DataFrame:
    if not top20_path.exists():
        raise FileNotFoundError(f"Top 20 CSV not found: {top20_path}")

    df = normalise_columns(pd.read_csv(top20_path))
    print(f"Loaded Top 20 CSV: {top20_path} ({len(df):,} rows)")
    print("Top 20 columns:", list(df.columns))

    site_col = pick_first_existing(df, ["site", "site_id", "scats_site", "scats_site_id", "scats_site_number"])
    name_col = pick_first_existing(df, ["site_name", "name", "location", "description"])
    volume_col = pick_first_existing(df, ["volume", "total_cleaned_volume", "total_volume", "total", "month_site_volume"])
    lat_col = pick_first_existing(df, ["latitude", "lat"])
    lng_col = pick_first_existing(df, ["longitude", "lng", "lon"])

    if not site_col:
        raise RuntimeError(f"Could not detect site column. Columns: {list(df.columns)}")
    if not volume_col:
        raise RuntimeError(f"Could not detect volume column. Columns: {list(df.columns)}")

    out = pd.DataFrame()
    out["site_id"] = df[site_col].apply(clean_site_id)
    out["name"] = df[name_col].astype(str).str.strip() if name_col else ""
    out["total"] = pd.to_numeric(df[volume_col], errors="coerce").fillna(0).astype("int64")
    out["lat"] = pd.to_numeric(df[lat_col], errors="coerce") if lat_col else pd.NA
    out["lng"] = pd.to_numeric(df[lng_col], errors="coerce") if lng_col else pd.NA
    out["source_top20_csv"] = top20_path.name

    out = out.dropna(subset=["site_id"])
    out = out.sort_values("total", ascending=False).head(20).reset_index(drop=True)
    return out


def load_coordinate_lookup(reports_dir: Path, extra_lookup: Optional[Path] = None) -> pd.DataFrame:
    candidates = []
    if extra_lookup:
        candidates.append(extra_lookup)

    candidates.extend([
        reports_dir / "busiestSCATSsitesCOORDINATES.csv",
        reports_dir / "busiestSCATSsitesCOORDINATES(1).csv",
        Path.cwd() / "busiestSCATSsitesCOORDINATES.csv",
        Path.cwd() / "busiestSCATSsitesCOORDINATES(1).csv",
    ])

    frames = []
    seen = set()

    for path in candidates:
        if not path or str(path) in seen:
            continue
        seen.add(str(path))
        if not path.exists():
            continue
        try:
            raw = normalise_columns(pd.read_csv(path))
            print(f"Loaded coordinate lookup: {path} ({len(raw):,} rows)")
            print("Coordinate columns:", list(raw.columns))

            site_col = pick_first_existing(raw, ["scats_site", "scats_site_id", "site", "site_id", "scats_site_number"])
            name_col = pick_first_existing(raw, ["name", "site_name", "location", "description"])
            lat_col = pick_first_existing(raw, ["latitude", "lat"])
            lng_col = pick_first_existing(raw, ["longitude", "lng", "lon"])

            if not site_col or not lat_col or not lng_col:
                print(f"  Skipping {path.name}: could not detect site/lat/lng columns")
                continue

            df = pd.DataFrame()
            df["site_id"] = raw[site_col].apply(clean_site_id)
            df["lookup_name"] = raw[name_col].astype(str).str.strip() if name_col else ""
            df["lookup_lat"] = pd.to_numeric(raw[lat_col], errors="coerce")
            df["lookup_lng"] = pd.to_numeric(raw[lng_col], errors="coerce")
            df["coordinate_source"] = path.name
            df = df.dropna(subset=["site_id", "lookup_lat", "lookup_lng"])
            frames.append(df)
        except Exception as e:
            print(f"WARNING: failed to read coordinate lookup {path}: {e}")

    if not frames:
        print("WARNING: no usable coordinate lookup files found")
        return pd.DataFrame(columns=["site_id", "lookup_name", "lookup_lat", "lookup_lng", "coordinate_source"])

    lookup = pd.concat(frames, ignore_index=True)
    # Prefer rows with coordinates and longer names.
    lookup["name_quality"] = lookup["lookup_name"].fillna("").astype(str).str.len()
    lookup = lookup.sort_values(["site_id", "name_quality"], ascending=[True, False])
    lookup = lookup.drop_duplicates("site_id", keep="first").drop(columns=["name_quality"])
    print(f"Merged coordinate lookup: {len(lookup):,} unique sites with coordinates")
    return lookup


def apply_overrides(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for site_id, info in SITE_OVERRIDES.items():
        mask = df["site_id"].astype(str) == site_id
        if not mask.any():
            continue
        if info.get("name"):
            df.loc[mask, "name"] = info["name"]
        df.loc[mask, "lat"] = info["lat"]
        df.loc[mask, "lng"] = info["lng"]
        df.loc[mask, "coordinate_source"] = info.get("coordinate_source", "manual_override")
    return df


def build_json_records(df: pd.DataFrame) -> list[dict]:
    records = []
    max_total = float(df["total"].max()) if len(df) else 0.0

    for rank, row in enumerate(df.itertuples(index=False), start=1):
        total = int(row.total)
        ratio = total / max_total if max_total else 0
        if ratio >= 0.85:
            heat = "red"
        elif ratio >= 0.70:
            heat = "orange"
        elif ratio >= 0.55:
            heat = "amber"
        else:
            heat = "green"

        records.append({
            "rank": rank,
            "site_id": str(row.site_id),
            "name": str(row.name),
            "lat": float(row.lat),
            "lng": float(row.lng),
            "total": total,
            "total_millions": round(total / 1_000_000, 1),
            "traffic_heat": heat,
            "volume_ratio": round(ratio, 4),
            "coordinate_source": str(getattr(row, "coordinate_source", "")),
            "google_maps_url": f"https://www.google.com/maps/search/?api=1&query={float(row.lat)},{float(row.lng)}",
        })
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Top 20 SCATS Google Map JSON")
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORTS_DIR), help="Reports/deduped directory")
    parser.add_argument("--top20-csv", default=None, help="Top 20 named CSV path")
    parser.add_argument("--coord-csv", default=None, help="Optional coordinate lookup CSV path")
    parser.add_argument("--output", default=None, help="Output JSON path")
    args = parser.parse_args()

    reports_dir = Path(args.reports_dir)
    charts_dir = reports_dir / "charts"
    top20_path = Path(args.top20_csv) if args.top20_csv else charts_dir / "top_20_busiest_scats_sites_named.csv"
    coord_path = Path(args.coord_csv) if args.coord_csv else None
    output_path = Path(args.output) if args.output else reports_dir / "top_20_scats_map_data.json"
    unresolved_path = reports_dir / "top_20_scats_map_data_unresolved.csv"
    audit_path = reports_dir / "top_20_scats_map_data_audit.csv"

    top20 = load_top20(top20_path)
    lookup = load_coordinate_lookup(reports_dir, coord_path)

    merged = top20.merge(lookup, on="site_id", how="left")

    # Fill missing chart coordinates from lookup coordinates.
    merged["lat"] = pd.to_numeric(merged["lat"], errors="coerce")
    merged["lng"] = pd.to_numeric(merged["lng"], errors="coerce")
    merged["lat"] = merged["lat"].fillna(merged["lookup_lat"])
    merged["lng"] = merged["lng"].fillna(merged["lookup_lng"])

    # Fill names from lookup where chart name is blank/invalid.
    blank_name = merged["name"].isna() | merged["name"].astype(str).str.strip().isin(["", "nan", "None"])
    merged.loc[blank_name, "name"] = merged.loc[blank_name, "lookup_name"]

    merged["coordinate_source"] = merged["coordinate_source"].fillna("top20_csv_or_unresolved")

    # Apply known manual corrections last.
    merged = apply_overrides(merged)

    unresolved = merged[merged["lat"].isna() | merged["lng"].isna()].copy()
    if len(unresolved):
        unresolved.to_csv(unresolved_path, index=False)
        print(f"WARNING: {len(unresolved)} Top 20 sites still missing coordinates")
        print(f"Wrote unresolved report: {unresolved_path}")
        print(unresolved[["site_id", "name", "total"]].to_string(index=False))

    ready = merged.dropna(subset=["lat", "lng"]).copy()
    ready = ready.sort_values("total", ascending=False).head(20).reset_index(drop=True)

    records = build_json_records(ready)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    ready.to_csv(audit_path, index=False)

    print("\nDONE")
    print(f"Wrote JSON: {output_path}")
    print(f"Wrote audit CSV: {audit_path}")
    print(f"Records created: {len(records)}")
    if records:
        print("First record:")
        print(json.dumps(records[0], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
