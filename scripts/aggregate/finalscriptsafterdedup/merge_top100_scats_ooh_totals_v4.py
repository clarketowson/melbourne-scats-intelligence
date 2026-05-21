#!/usr/bin/env python3
"""
merge_top100_scats_ooh_totals_v4.py

V4 fix:
- Sums ALL rows in site_totals.csv by scats_site.
- Does NOT filter row_type.
- This matches the PowerShell check:
    Import-Csv site_totals.csv | Where-Object {$_.scats_site -eq "4415"} | Measure-Object -Property month_site_volume -Sum

Input 1:
  top100_scats_vicmap_ooh.csv

Input 2:
  site_totals.csv with columns:
    month_label, month_start, next_month_start, scats_site, month_site_volume, ...

Output:
  top100_scats_vicmap_ooh_with_totals.csv

Run:
  python A:\\TrafficAnalytics\\PROJECTS\\scripts\\finalscriptsafterdedup\\merge_top100_scats_ooh_totals_v4.py A:\\TrafficAnalytics\\PROJECTS\\reports\\deduped\\top100_scats_vicmap_ooh.csv A:\\TrafficAnalytics\\PROJECTS\\reports\\deduped\\site_totals.csv A:\\TrafficAnalytics\\PROJECTS\\reports\\deduped\\top100_scats_vicmap_ooh_with_totals.csv
"""

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_YEAR_SPAN = 12.27
DEFAULT_DATASET_LABEL = "2014-01-01 to 2026-04-07"

STALE_OOH_COLUMNS = [
    "ooh_total_12yr_movements",
    "ooh_annual_avg_movements",
    "ooh_daily_avg_movements",
    "ooh_peak_hour_estimate",
    "ooh_dataset_period",
    "ooh_exposure_summary",
    "ooh_advertising_context",
]


def clean_site_id(value):
    if pd.isna(value):
        return ""
    s = str(value).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def parse_number(value):
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
        description="Merge Top 100 SCATS Vicmap parcel enrichment with true summed site_totals.csv traffic totals."
    )

    parser.add_argument("vicmap_csv")
    parser.add_argument("site_totals_csv")
    parser.add_argument("output_csv")

    parser.add_argument("--left-site-col", default="site_id")
    parser.add_argument("--totals-site-col", default=None)
    parser.add_argument("--monthly-volume-col", default=None)
    parser.add_argument("--years", type=float, default=DEFAULT_YEAR_SPAN)
    parser.add_argument("--dataset-label", default=DEFAULT_DATASET_LABEL)
    parser.add_argument("--peak-hour-factor", type=float, default=0.10)

    args = parser.parse_args()

    vicmap_path = Path(args.vicmap_csv)
    totals_path = Path(args.site_totals_csv)
    output_path = Path(args.output_csv)

    left = pd.read_csv(vicmap_path, low_memory=False)
    totals = pd.read_csv(totals_path, low_memory=False)

    print("\nVicmap/enriched CSV columns:")
    print(", ".join(left.columns))

    print("\nSite totals CSV columns:")
    print(", ".join(totals.columns))

    if args.left_site_col not in left.columns:
        raise SystemExit(
            f"\nERROR: left site column '{args.left_site_col}' not found. "
            "Use --left-site-col to specify the correct column."
        )

    totals_site_col = find_column(
        totals,
        args.totals_site_col,
        ["scats_site", "site_id", "SCATS Site", "SCATS_SITE", "site", "Site"],
    )

    if not totals_site_col:
        raise SystemExit(
            "\nERROR: Could not find site ID column in site_totals CSV. "
            "Use --totals-site-col scats_site"
        )

    monthly_volume_col = find_column(
        totals,
        args.monthly_volume_col,
        [
            "month_site_volume",
            "monthly_site_volume",
            "site_month_volume",
            "total",
            "Total",
            "volume",
            "movements",
        ],
    )

    if not monthly_volume_col:
        raise SystemExit(
            "\nERROR: Could not find monthly volume column in site_totals CSV. "
            "Use --monthly-volume-col month_site_volume"
        )

    stale_present = [c for c in STALE_OOH_COLUMNS if c in left.columns]
    if stale_present:
        print("\nDropping stale OOH metric columns from Vicmap file before recalculation:")
        print(", ".join(stale_present))
        left = left.drop(columns=stale_present)

    print("\nUsing:")
    print(f"  Left site column:       {args.left_site_col}")
    print(f"  Totals site column:     {totals_site_col}")
    print(f"  Monthly volume column:  {monthly_volume_col}")
    print(f"  Dataset period:         {args.dataset_label}")
    print(f"  Year divisor:           {args.years}")
    print("  Row filtering:          OFF — summing all rows")

    left["_join_site_id"] = left[args.left_site_col].map(clean_site_id)
    totals["_join_site_id"] = totals[totals_site_col].map(clean_site_id)
    totals["_month_volume_num"] = totals[monthly_volume_col].map(parse_number)

    site_sums = (
        totals
        .groupby("_join_site_id", as_index=False)["_month_volume_num"]
        .sum()
        .rename(columns={"_month_volume_num": "ooh_total_12yr_movements"})
    )

    print(f"\nSummed totals for {len(site_sums):,} distinct SCATS sites.")

    merged = left.merge(site_sums, on="_join_site_id", how="left")

    merged["ooh_total_12yr_movements"] = (
        merged["ooh_total_12yr_movements"]
        .fillna(0)
        .map(parse_number)
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

    def exposure_summary(row):
        total = parse_number(row["ooh_total_12yr_movements"])
        if total <= 0:
            return (
                "Traffic total not matched; parcel enrichment is available but exposure "
                "metrics require a matching site total."
            )

        return (
            f"{total:,} vehicle movements across {args.dataset_label}; "
            f"approximately {int(row['ooh_annual_avg_movements']):,} per year, "
            f"{int(row['ooh_daily_avg_movements']):,} per day, "
            f"and an indicative {int(row['ooh_peak_hour_estimate']):,} vehicles in a major peak hour."
        )

    merged["ooh_exposure_summary"] = merged.apply(exposure_summary, axis=1)

    merged["ooh_advertising_context"] = (
        "Long-term SCATS traffic volume combined with nearby Vicmap parcel identifiers "
        "supports OOH screening: exposure strength, cadastral due diligence, VicPlan lookup, "
        "and Google Street View feasibility review."
    )

    merged["vicplan_url"] = "https://mapshare.vic.gov.au/vicplan/"

    if "lat" in merged.columns and "lng" in merged.columns:
        merged["google_street_view_url"] = merged.apply(
            lambda r: (
                f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={r['lat']},{r['lng']}"
                if pd.notna(r["lat"]) and pd.notna(r["lng"])
                else ""
            ),
            axis=1,
        )

    matched = int((merged["ooh_total_12yr_movements"] > 0).sum())
    total_rows = len(merged)

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
        "parcel_parcel_plan_number",
        "parcel_parcel_lot_number",
        "parcel_parcel_road",
        "parcel_parcel_crown_status",
        "parcel_parcel_status",
        "prop_prop_pfi",
        "prop_prop_ufi",
        "prop_prop_property_type",
        "prop_prop_status",
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
        print("\nWARNING: Some Top 100 rows did not match site totals.")
        cols = [c for c in ["site_id", "name"] if c in merged.columns]
        unmatched = merged.loc[merged["ooh_total_12yr_movements"] <= 0, cols].head(20)
        print(unmatched.to_string(index=False))

    print("\nTop 10 by merged multi-year movements:")
    preview_cols = [
        c for c in [
            "site_id",
            "name",
            "ooh_total_12yr_movements",
            "ooh_daily_avg_movements",
            "parcel_parcel_spi",
        ]
        if c in merged.columns
    ]

    print(
        merged.sort_values("ooh_total_12yr_movements", ascending=False)
        .head(10)[preview_cols]
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
