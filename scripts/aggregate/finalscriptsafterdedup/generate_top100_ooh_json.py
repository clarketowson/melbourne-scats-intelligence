#!/usr/bin/env python3

import pandas as pd
import json
import argparse
from pathlib import Path

def safe_int(val):
    try:
        if pd.isna(val):
            return 0
        return int(float(val))
    except:
        return 0

def main():

    parser = argparse.ArgumentParser(
        description="Convert Top100 SCATS OOH CSV into map-ready JSON."
    )

    parser.add_argument("input_csv")
    parser.add_argument("output_json")

    args = parser.parse_args()

    input_path = Path(args.input_csv)
    output_path = Path(args.output_json)

    print("Reading CSV...")
    df = pd.read_csv(input_path, low_memory=False)

    print("Rows loaded:", len(df))

    records = []

    for _, row in df.iterrows():

        site = {
            "site_id": str(row.get("site_id", "")),
            "name": str(row.get("name", "")),

            "lat": float(row.get("lat", 0)),
            "lng": float(row.get("lng", 0)),

            "traffic": {
                "total_12yr": safe_int(
                    row.get("ooh_total_12yr_movements", 0)
                ),

                "annual_avg": safe_int(
                    row.get("ooh_annual_avg_movements", 0)
                ),

                "daily_avg": safe_int(
                    row.get("ooh_daily_avg_movements", 0)
                ),

                "peak_hour": safe_int(
                    row.get("ooh_peak_hour_estimate", 0)
                )
            },

            "parcel": {
                "spi": str(
                    row.get("parcel_parcel_spi", "")
                ),

                "pfi": str(
                    row.get("parcel_parcel_pfi", "")
                ),

                "lot": str(
                    row.get("parcel_parcel_lot_number", "")
                ),

                "plan": str(
                    row.get("parcel_parcel_plan_number", "")
                ),

                "road": str(
                    row.get("parcel_parcel_road", "")
                )
            },

            "links": {
                "vicplan":
                    row.get("vicplan_url", ""),

                "street_view":
                    row.get("google_street_view_url", "")
            }
        }

        records.append(site)

    print("Writing JSON...")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

    print("\nDone.")
    print("Sites exported:", len(records))
    print("Output:", output_path)


if __name__ == "__main__":
    main()