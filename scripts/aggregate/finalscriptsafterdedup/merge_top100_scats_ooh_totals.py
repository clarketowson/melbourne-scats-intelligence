#!/usr/bin/env python3
"""
merge_top100_scats_ooh_totals.py

Merges:
  1) Top 100 SCATS Vicmap/parcel enrichment CSV
  2) Busiest-site totals CSV containing total 12-year vehicle movements

Then calculates OOH advertising exposure fields:
  - 12-year vehicle movements
  - average annual movements
  - average daily movements
  - indicative peak-hour exposure estimate

Example:
  python .\merge_top100_scats_ooh_totals.py top100_scats_vicmap_ooh.csv busiest_sites_totals.csv top100_scats_vicmap_ooh_with_totals.csv

Common Windows example:
  python A:\TrafficAnalytics\PROJECTS\scripts\merge_top100_scats_ooh_totals.py A:\TrafficAnalytics\PROJECTS\reports\deduped\top100_scats_vicmap_ooh.csv A:\TrafficAnalytics\PROJECTS\reports\deduped\busiest_site_totals.csv A:\TrafficAnalytics\PROJECTS\reports\deduped\top100_scats_vicmap_ooh_with_totals.csv

If your column names differ, use:
  --left-site-col site_id
  --right-site-col site_id
  --right-total-col total
"""

import argparse
from pathlib import Path
import pandas as pd


DEFAULT_YEAR_SPAN = 12
DEFAULT_DATASET_LABEL = "2014-2026"


def clean_site_id(value):
    """Normalise SCATS site ids so 4415, 4415.0 and '4415' all join."""
    if pd.isna(value):
        return ""
    s = str(value).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def parse_number(value):
    """Parse numbers that may contain commas or blanks."""
    if pd.isna(value):
        return 0
    s = str(value).replace(",", "").strip()
    if not s:
        return 0
    try:
        return int(float(s))
    except Exception:
        return 0


def find_column(df, preferred, fallbacks):
    if preferred and preferred in df.columns:
        return preferred
    for col in fallbacks:
        if col in df.columns:
            return col
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Merge Top 100 SCATS Vicmap parcel enrichment with 12-year traffic totals."
    )

    parser.add_argument("vicmap_csv", help="Top 100 Vicmap/parcel enriched CSV")
    parser.add_argument("totals_csv", help="Busiest-site totals CSV")
    parser.add_argument("output_csv", help="Merged OOH-ready output CSV")

    parser.add_argument("--left-site-col", default="site_id", help="SCATS site id column in Vicmap CSV")
    parser.add_argument("--right-site-col", default=None, help="SCATS site id column in totals CSV")
    parser.add_argument("--right-total-col", default=None, help="Traffic total column in totals CSV")
    parser.add_argument("--right-name-col", default=None, help="Optional name column in totals CSV")
    parser.add_argument("--years", type=float, default=DEFAULT_YEAR_SPAN, help="Dataset span in years")
    parser.add_argument("--dataset-label", default=DEFAULT_DATASET_LABEL, help="Dataset period label")
    parser.add_argument("--peak-hour-factor", type=float, default=0.10, help="Indicative peak-hour factor of daily average")
    parser.add_argument("--keep-all-left", action="store_true", default=True, help="Keep all rows from Vicmap CSV")

    args = parser.parse_args()

    vicmap_path = Path(args.vicmap_csv)
    totals_path = Path(args.totals_csv)
    output_path = Path(args.output_csv)

    left = pd.read_csv(vicmap_path)
    right = pd.read_csv(totals_path)

    print("\nVicmap/enriched CSV columns:")
    print(", ".join(left.columns))

    print("\nTotals CSV columns:")
    print(", ".join(right.columns))

    if args.left_site_col not in left.columns:
        raise SystemExit(
            f"\nERROR: left site column '{args.left_site_col}' not found in {vicmap_path}.\n"
            "Use --left-site-col to specify the correct column."
        )

    right_site_col = find_column(
        right,
        args.right_site_col,
        [
            "site_id",
            "SCATS Site",
            "SCATS_SITE",
            "scats_site",
            "site",
            "site_no",
            "site_number",
            "Site",
        ],
    )

    if not right_site_col:
        raise SystemExit(
            "\nERROR: Could not auto-detect SCATS site id column in totals CSV.\n"
            "Use --right-site-col, for example: --right-site-col site_id"
        )

    right_total_col = find_column(
        right,
        args.right_total_col,
        [
            "total",
            "Total",
            "TOTAL",
            "total_cleaned",
            "total_cleaned_volume",
            "total_movements",
            "vehicle_movements",
            "movements",
            "total_volume",
            "sum_cleaned_value",
        ],
    )

    if not right_total_col:
        raise SystemExit(
            "\nERROR: Could not auto-detect traffic total column in totals CSV.\n"
            "Use --right-total-col, for example: --right-total-col total"
        )

    right_name_col = find_column(
        right,
        args.right_name_col,
        [
            "name",
            "Name",
            "site_name",
            "Site Name",
            "lookup_name",
            "Location",
        ],
    )

    print(f"\nJoin columns:")
    print(f"  Left  site column: {args.left_site_col}")
    print(f"  Right site column: {right_site_col}")
    print(f"  Right total column: {right_total_col}")
    if right_name_col:
        print(f"  Right name column: {right_name_col}")

    left["_join_site_id"] = left[args.left_site_col].map(clean_site_id)
    right["_join_site_id"] = right[right_site_col].map(clean_site_id)

    right_small_cols = ["_join_site_id", right_total_col]
    if right_name_col:
        right_small_cols.append(right_name_col)

    right_small = right[right_small_cols].copy()
    right_small = right_small.rename(columns={right_total_col: "_merged_total_12yr"})
    if right_name_col:
        right_small = right_small.rename(columns={right_name_col: "_merged_total_name"})

    # Drop duplicate site IDs in totals if present, keeping the largest total.
    right_small["_merged_total_12yr_num"] = right_small["_merged_total_12yr"].map(parse_number)
    right_small = (
        right_small.sort_values("_merged_total_12yr_num", ascending=False)
        .drop_duplicates("_join_site_id", keep="first")
        .drop(columns=["_merged_total_12yr_num"])
    )

    merged = left.merge(right_small, on="_join_site_id", how="left")

    merged["ooh_total_12yr_movements"] = merged["_merged_total_12yr"].map(parse_number)

    # If some rows already had totals in the left CSV, preserve them when merge missed.
    if "total" in merged.columns:
        left_total = merged["total"].map(parse_number)
        merged["ooh_total_12yr_movements"] = merged["ooh_total_12yr_movements"].where(
            merged["ooh_total_12yr_movements"] > 0,
            left_total,
        )

    years = float(args.years)
    days = years * 365.25

    merged["ooh_annual_avg_movements"] = (
        merged["ooh_total_12yr_movements"] / years
    ).round().astype("Int64")

    merged["ooh_daily_avg_movements"] = (
        merged["ooh_total_12yr_movements"] / days
    ).round().astype("Int64")

    merged["ooh_peak_hour_estimate"] = (
        merged["ooh_daily_avg_movements"].astype("float") * float(args.peak_hour_factor)
    ).round().astype("Int64")

    merged["ooh_dataset_period"] = args.dataset_label

    merged["ooh_exposure_summary"] = merged.apply(
        lambda r: (
            f"{int(r['ooh_total_12yr_movements']):,} vehicle movements over {args.dataset_label}; "
            f"approximately {int(r['ooh_annual_avg_movements']):,} per year, "
            f"{int(r['ooh_daily_avg_movements']):,} per day, "
            f"and an indicative {int(r['ooh_peak_hour_estimate']):,} vehicles in a major peak hour."
        )
        if parse_number(r["ooh_total_12yr_movements"]) > 0
        else "Traffic total not matched; parcel enrichment available but exposure metrics require a matching totals row.",
        axis=1,
    )

    merged["ooh_advertising_context"] = merged.apply(
        lambda r: (
            "Long-term SCATS volume plus nearby Vicmap parcel identifiers supports OOH screening: "
            "traffic exposure, cadastral due diligence, VicPlan lookup, and Street View feasibility review."
        ),
        axis=1,
    )

    # Add a convenience VicPlan URL. Due to VicPlan disclaimer, this opens VicPlan;
    # users copy SPI/PFI from the page and paste into search.
    merged["vicplan_url"] = "https://mapshare.vic.gov.au/vicplan/"

    # Add Google Street View URL if lat/lng are present.
    lat_col = "lat" if "lat" in merged.columns else None
    lng_col = "lng" if "lng" in merged.columns else None
    if lat_col and lng_col:
        merged["google_street_view_url"] = merged.apply(
            lambda r: (
                f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={r[lat_col]},{r[lng_col]}"
                if pd.notna(r[lat_col]) and pd.notna(r[lng_col])
                else ""
            ),
            axis=1,
        )

    matched = int((merged["ooh_total_12yr_movements"] > 0).sum())
    total_rows = len(merged)

    # Put key columns first.
    preferred_order = [
        "site_id",
        "name",
        "lat",
        "lng",
        "ooh_total_12yr_movements",
        "ooh_annual_avg_movements",
        "ooh_daily_avg_movements",
        "ooh_peak_hour_estimate",
        "ooh_dataset_period",
        "ooh_exposure_summary",
        "parcel_parcel_spi",
        "parcel_parcel_pfi",
        "parcel_plan_number",
        "parcel_lot_number",
        "prop_prop_pfi",
        "prop_prop_ufi",
        "vicplan_url",
        "google_street_view_url",
    ]

    ordered_cols = [c for c in preferred_order if c in merged.columns]
    remaining_cols = [c for c in merged.columns if c not in ordered_cols and not c.startswith("_")]
    merged = merged[ordered_cols + remaining_cols]

    merged.to_csv(output_path, index=False)

    print(f"\nDone: {output_path}")
    print(f"Rows written: {total_rows}")
    print(f"Rows with matched traffic totals: {matched}/{total_rows}")

    if matched < total_rows:
        print("\nWARNING: Some rows did not match totals.")
        print("Check whether SCATS site ids have different formats between the two CSV files.")
        print("You can inspect the unmatched rows by filtering ooh_total_12yr_movements = 0.")


if __name__ == "__main__":
    main()
