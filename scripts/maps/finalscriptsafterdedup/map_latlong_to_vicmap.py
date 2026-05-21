#!/usr/bin/env python3

import argparse
import time
import requests
import pandas as pd

# Vicmap PARCEL layer (not property)
VICMAP_PARCEL_LAYER = (
    "https://services-ap1.arcgis.com/P744lA0wf4LlBZ84/ArcGIS/rest/services/"
    "Vicmap_Parcel/FeatureServer/0/query"
)

def query_parcel(lat, lon):

    params = {
        "f": "json",

        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,

        "distance": 50,
        "units": "esriSRUnit_Meter",

        # Parcel-level identifiers
        "outFields": (
            "parcel_pfi,"
            "parcel_ufi,"
            "spi,"
            "lot,"
            "plan"
        ),

        "returnGeometry": "false"
    }

    r = requests.get(
        VICMAP_PARCEL_LAYER,
        params=params,
        timeout=30
    )

    r.raise_for_status()

    data = r.json()

    features = data.get("features", [])

    if not features:
        return {}

    return features[0]["attributes"]


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("input_csv")
    parser.add_argument("output_csv")

    parser.add_argument("--lat-col", default="lat")
    parser.add_argument("--lon-col", default="lng")

    args = parser.parse_args()

    df = pd.read_csv(args.input_csv)

    results = []

    for i, row in df.iterrows():

        lat = row[args.lat_col]
        lon = row[args.lon_col]

        print(f"[{i+1}/{len(df)}] {lat}, {lon}")

        try:

            attrs = query_parcel(lat, lon)

        except Exception as e:

            attrs = {
                "parcel_error": str(e)
            }

        results.append(attrs)

        time.sleep(0.15)

    parcel_df = pd.DataFrame(results)

    out = pd.concat(
        [df.reset_index(drop=True),
         parcel_df.reset_index(drop=True)],
        axis=1
    )

    out.to_csv(
        args.output_csv,
        index=False
    )

    print(f"\nDone → {args.output_csv}")


if __name__ == "__main__":
    main()