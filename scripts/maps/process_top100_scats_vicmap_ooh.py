#!/usr/bin/env python3
"""
process_top100_scats_vicmap_ooh.py

Enriches the busiest SCATS site coordinate CSV with nearby Vicmap/VicPlan parcel data
for OOH advertising opportunity mapping.

Expected input columns by default:
  SCATS Site, Name, Latitude, Longitude

Example:
  python .\process_top100_scats_vicmap_ooh.py busiestSCATSsitesCOORDINATES.csv top100_scats_vicmap_ooh.csv

Optional custom columns:
  python .\process_top100_scats_vicmap_ooh.py input.csv output.csv --site-col "site_id" --name-col "name" --lat-col "lat" --lon-col "lng"
"""

import argparse
import json
import math
import time
from pathlib import Path

import pandas as pd
import requests


VICMAP_PROPERTY_LAYER = (
    "https://services-ap1.arcgis.com/P744lA0wf4LlBZ84/ArcGIS/rest/services/"
    "Vicmap_Property/FeatureServer/0/query"
)

VICMAP_PARCEL_LAYER = (
    "https://services-ap1.arcgis.com/P744lA0wf4LlBZ84/ArcGIS/rest/services/"
    "Vicmap_Parcel/FeatureServer/0/query"
)


def safe_int(value, default=0):
    try:
        if pd.isna(value):
            return default
        return int(float(str(value).replace(",", "").strip()))
    except Exception:
        return default


def safe_float(value):
    try:
        if pd.isna(value):
            return None
        return float(str(value).strip())
    except Exception:
        return None


def query_arcgis(layer_url, lat, lon, distance_m=50, out_fields="*", return_geometry=False):
    params = {
        "f": "json",
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "distance": distance_m,
        "units": "esriSRUnit_Meter",
        "outFields": out_fields,
        "returnGeometry": str(return_geometry).lower(),
        "outSR": 4326,
    }

    r = requests.get(layer_url, params=params, timeout=45)
    r.raise_for_status()
    data = r.json()

    if "error" in data:
        raise RuntimeError(json.dumps(data["error"], ensure_ascii=False))

    features = data.get("features", [])
    return features


def first_attributes(features):
    if not features:
        return {}
    return features[0].get("attributes", {}) or {}


def make_ooh_fields(row, total_col=None):
    total = safe_int(row.get(total_col), 0) if total_col else 0

    # Dataset period used in your SCATS reporting page.
    years = 12
    annual_avg = round(total / years) if total else ""
    daily_avg = round(total / (years * 365.25)) if total else ""
    peak_hour_est = round(daily_avg * 0.10) if daily_avg else ""

    return {
        "ooh_total_12yr_movements": total if total else "",
        "ooh_annual_avg_movements": annual_avg,
        "ooh_daily_avg_movements": daily_avg,
        "ooh_peak_hour_estimate": peak_hour_est,
        "ooh_dataset_period": "2014-2026",
        "ooh_advertising_context": (
            "Verified high-exposure advertising corridor. Long-term SCATS traffic "
            "volume can indicate sustained roadside visibility and potential suitability "
            "for premium billboard or digital signage investigation near the closest "
            "cadastral parcels."
        ),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Process Top 100 busiest SCATS sites into OOH + Vicmap/VicPlan parcel enrichment CSV."
    )
    parser.add_argument("input_csv", help="Input busiest SCATS coordinate CSV")
    parser.add_argument("output_csv", help="Output enriched CSV")
    parser.add_argument("--site-col", default="SCATS Site")
    parser.add_argument("--name-col", default="Name")
    parser.add_argument("--lat-col", default="Latitude")
    parser.add_argument("--lon-col", default="Longitude")
    parser.add_argument("--total-col", default=None, help="Optional total movements column, e.g. total or Total")
    parser.add_argument("--distance", type=int, default=50, help="Vicmap search radius in metres")
    parser.add_argument("--sleep", type=float, default=0.20, help="Delay between API calls")
    parser.add_argument("--limit", type=int, default=100, help="Maximum rows to process")
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    output_path = Path(args.output_csv)

    df = pd.read_csv(input_path)

    print("Input columns:")
    print(", ".join(df.columns))

    required = [args.site_col, args.name_col, args.lat_col, args.lon_col]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(
            "Missing required columns: "
            + ", ".join(missing)
            + "\nUse --site-col, --name-col, --lat-col and --lon-col to match your CSV."
        )

    # Auto-detect total column if not supplied.
    total_col = args.total_col
    if total_col is None:
        candidates = ["total", "Total", "TOTAL", "total_cleaned", "total_movements", "movements"]
        total_col = next((c for c in candidates if c in df.columns), None)

    work = df.head(args.limit).copy()
    output_rows = []

    for i, row in work.iterrows():
        site = row[args.site_col]
        name = row[args.name_col]
        lat = safe_float(row[args.lat_col])
        lon = safe_float(row[args.lon_col])

        print(f"[{len(output_rows)+1}/{len(work)}] Site {site} - {name} @ {lat},{lon}")

        base = {
            "site_id": site,
            "name": name,
            "lat": lat,
            "lng": lon,
        }

        # Preserve original total if present.
        if total_col:
            base["total"] = safe_int(row.get(total_col), 0)

        base.update(make_ooh_fields(row, total_col=total_col))

        if lat is None or lon is None or math.isnan(lat) or math.isnan(lon):
            base["vicmap_error"] = "Invalid latitude/longitude"
            output_rows.append(base)
            continue

        try:
            prop_features = query_arcgis(
                VICMAP_PROPERTY_LAYER,
                lat,
                lon,
                distance_m=args.distance,
                out_fields="*",
                return_geometry=False,
            )
            prop = first_attributes(prop_features)

            for k, v in prop.items():
                base[f"prop_{str(k).lower()}"] = v

        except Exception as e:
            base["property_error"] = str(e)

        time.sleep(args.sleep)

        try:
            parcel_features = query_arcgis(
                VICMAP_PARCEL_LAYER,
                lat,
                lon,
                distance_m=args.distance,
                out_fields="*",
                return_geometry=False,
            )
            parcel = first_attributes(parcel_features)

            for k, v in parcel.items():
                base[f"parcel_{str(k).lower()}"] = v

        except Exception as e:
            base["parcel_error"] = str(e)

        output_rows.append(base)
        time.sleep(args.sleep)

    out_df = pd.DataFrame(output_rows)
    out_df.to_csv(output_path, index=False)

    print(f"\nDone: {output_path}")
    print(f"Rows written: {len(out_df)}")
    print("\nUseful output fields should include:")
    print("  site_id, name, lat, lng")
    print("  ooh_total_12yr_movements, ooh_annual_avg_movements, ooh_daily_avg_movements")
    print("  prop_* fields")
    print("  parcel_* fields such as parcel_parcel_pfi, parcel_parcel_spi, parcel_plan_number, parcel_lot_number")


if __name__ == "__main__":
    main()
