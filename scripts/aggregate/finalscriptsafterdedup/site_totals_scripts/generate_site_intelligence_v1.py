#!/usr/bin/env python3
"""
generate_site_intelligence_v1.py

Post-processes SCATS site_totals.csv into template-ready intelligence outputs.

Input expected columns from Site Totals V3.1:
  month_label, month_start, next_month_start, scats_site, month_site_volume,
  month_elapsed_seconds, completed_at_epoch, row_type

Key safety behaviours:
  - Ignores zero_row_month marker rows.
  - Drops blank / NaN site IDs and NaN volumes.
  - Deduplicates repeated month+site rows by keeping the latest completed_at_epoch.
  - Works on partial or final site_totals.csv.
  - Optional enrichment from a site lookup CSV.

Example:
  python generate_site_intelligence_v1.py ^
    --input A:\TrafficAnalytics\PROJECTS\reports\deduped\site_totals.csv ^
    --output-dir A:\TrafficAnalytics\PROJECTS\reports\deduped\site_intelligence

Optional site lookup:
  python generate_site_intelligence_v1.py --input ... --site-lookup A:\TrafficAnalytics\DATA\SCATS\victorian_traffic_signals.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

EXPECTED_MONTHS = 148
TOP_N_EXPORTS = [10, 25, 50, 100, 500, 1000]


def pick_col(columns: List[str], candidates: List[str]) -> Optional[str]:
    lower_map = {c.lower().strip(): c for c in columns}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    return None


def load_site_lookup(path: Optional[Path]) -> Optional[pd.DataFrame]:
    if not path:
        return None
    if not path.exists():
        raise FileNotFoundError(f"Site lookup file not found: {path}")

    lookup = pd.read_csv(path, low_memory=False)
    site_col = pick_col(
        list(lookup.columns),
        ["scats_site", "site_id", "site", "site_no", "site_number", "SCATS_SITE", "NB_SCATS_SITE"],
    )
    if not site_col:
        raise ValueError(
            "Could not find a site id column in lookup file. Expected one of: "
            "scats_site, site_id, site, site_no, site_number, NB_SCATS_SITE"
        )

    lookup = lookup.rename(columns={site_col: "scats_site"})
    lookup["scats_site"] = pd.to_numeric(lookup["scats_site"], errors="coerce")
    lookup = lookup.dropna(subset=["scats_site"])
    lookup["scats_site"] = lookup["scats_site"].astype("int64")
    lookup = lookup.drop_duplicates(subset=["scats_site"], keep="last")

    # Normalize common descriptive columns when present.
    rename_candidates = {
        "site_name": ["site_name", "name", "location", "site_description", "description", "SITE_NAME"],
        "suburb": ["suburb", "SUBURB"],
        "road_name": ["road_name", "road", "ROAD_NAME"],
        "latitude": ["latitude", "lat", "LATITUDE", "Lat"],
        "longitude": ["longitude", "lon", "lng", "LONGITUDE", "Long"],
    }
    for standard, candidates in rename_candidates.items():
        col = pick_col(list(lookup.columns), candidates)
        if col and col != standard:
            lookup = lookup.rename(columns={col: standard})

    keep = ["scats_site"] + [c for c in ["site_name", "suburb", "road_name", "latitude", "longitude"] if c in lookup.columns]
    return lookup[keep]


def load_and_clean_site_totals(input_path: Path) -> pd.DataFrame:
    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    df = pd.read_csv(
        input_path,
        dtype={
            "month_label": "string",
            "month_start": "string",
            "next_month_start": "string",
            "scats_site": "string",
            "row_type": "string",
        },
        low_memory=True,
    )
    required = {"month_label", "scats_site", "month_site_volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Input CSV missing required columns: {sorted(missing)}")

    if "row_type" in df.columns:
        df = df[df["row_type"].astype(str).str.lower().isin(["data", "site_total"])]

    df["scats_site"] = pd.to_numeric(df["scats_site"], errors="coerce")
    df["month_site_volume"] = pd.to_numeric(df["month_site_volume"], errors="coerce")
    df["completed_at_epoch"] = pd.to_numeric(df.get("completed_at_epoch", 0), errors="coerce").fillna(0)

    df = df.dropna(subset=["scats_site", "month_label", "month_site_volume"])
    df["scats_site"] = df["scats_site"].astype("int64")
    df["month_label"] = df["month_label"].astype(str)

    # Keep the latest row for any month/site pair. This prevents accidental double counting
    # if a month was rerun and appended again.
    df = df.sort_values(["month_label", "scats_site", "completed_at_epoch"])
    df = df.drop_duplicates(subset=["month_label", "scats_site"], keep="last")

    return df


def percentile_band(rank: int, total_sites: int) -> str:
    pct = rank / total_sites
    if pct <= 0.01:
        return "Top 1%"
    if pct <= 0.05:
        return "Top 5%"
    if pct <= 0.10:
        return "Top 10%"
    if pct <= 0.25:
        return "Top 25%"
    if pct <= 0.50:
        return "Top 50%"
    return "Bottom 50%"


def build_rankings(df: pd.DataFrame, lookup: Optional[pd.DataFrame]) -> pd.DataFrame:
    grouped = (
        df.groupby("scats_site", as_index=False)
        .agg(
            total_volume=("month_site_volume", "sum"),
            months_present=("month_label", "nunique"),
            first_month=("month_label", "min"),
            last_month=("month_label", "max"),
            avg_monthly_volume=("month_site_volume", "mean"),
            max_monthly_volume=("month_site_volume", "max"),
        )
    )

    best_month = (
        df.sort_values(["scats_site", "month_site_volume"], ascending=[True, False])
        .drop_duplicates(subset=["scats_site"], keep="first")
        [["scats_site", "month_label", "month_site_volume"]]
        .rename(columns={"month_label": "best_month", "month_site_volume": "best_month_volume"})
    )
    grouped = grouped.merge(best_month, on="scats_site", how="left")

    if lookup is not None:
        grouped = grouped.merge(lookup, on="scats_site", how="left")

    grouped = grouped.sort_values("total_volume", ascending=False).reset_index(drop=True)
    grouped.insert(0, "rank", grouped.index + 1)

    grand_total = grouped["total_volume"].sum()
    grouped["percent_of_network"] = grouped["total_volume"] / grand_total * 100 if grand_total else 0
    grouped["cumulative_volume"] = grouped["total_volume"].cumsum()
    grouped["cumulative_percent"] = grouped["cumulative_volume"] / grand_total * 100 if grand_total else 0
    total_sites = len(grouped)
    grouped["percentile_band"] = grouped["rank"].apply(lambda r: percentile_band(int(r), total_sites))

    # Nice integer fields for CSV/JSON readability.
    for col in ["total_volume", "months_present", "max_monthly_volume", "best_month_volume", "cumulative_volume"]:
        if col in grouped.columns:
            grouped[col] = grouped[col].round(0).astype("int64")
    grouped["avg_monthly_volume"] = grouped["avg_monthly_volume"].round(2)
    grouped["percent_of_network"] = grouped["percent_of_network"].round(6)
    grouped["cumulative_percent"] = grouped["cumulative_percent"].round(6)

    return grouped


def build_summary(df: pd.DataFrame, rankings: pd.DataFrame) -> Dict:
    months = sorted(df["month_label"].unique().tolist())
    grand_total = int(rankings["total_volume"].sum())
    top_site = rankings.iloc[0].to_dict() if not rankings.empty else {}

    def share_for_top(n: int) -> float:
        if grand_total == 0:
            return 0.0
        return round(float(rankings.head(n)["total_volume"].sum() / grand_total * 100), 4)

    return {
        "input_months_completed": len(months),
        "expected_months": EXPECTED_MONTHS,
        "is_final_expected_complete": len(months) >= EXPECTED_MONTHS,
        "first_month": months[0] if months else None,
        "last_month": months[-1] if months else None,
        "total_sites": int(rankings["scats_site"].nunique()),
        "grand_total_volume": grand_total,
        "top_site": {
            "rank": int(top_site.get("rank", 0)) if top_site else None,
            "scats_site": int(top_site.get("scats_site", 0)) if top_site else None,
            "site_name": top_site.get("site_name") if "site_name" in top_site else None,
            "total_volume": int(top_site.get("total_volume", 0)) if top_site else None,
            "percent_of_network": float(top_site.get("percent_of_network", 0)) if top_site else None,
        },
        "traffic_concentration": {
            "top_10_share_percent": share_for_top(10),
            "top_25_share_percent": share_for_top(25),
            "top_50_share_percent": share_for_top(50),
            "top_100_share_percent": share_for_top(100),
            "top_500_share_percent": share_for_top(500),
        },
        "generated_outputs": [],
    }


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SCATS site intelligence outputs from site_totals.csv")
    parser.add_argument("--input", required=True, help="Path to site_totals.csv")
    parser.add_argument("--output-dir", required=True, help="Directory for generated outputs")
    parser.add_argument("--site-lookup", default=None, help="Optional CSV with site names / locations")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    lookup = load_site_lookup(Path(args.site_lookup)) if args.site_lookup else None
    df = load_and_clean_site_totals(input_path)
    rankings = build_rankings(df, lookup)
    summary = build_summary(df, rankings)

    outputs = []

    rankings_csv = output_dir / "site_rankings.csv"
    rankings_json = output_dir / "site_rankings.json"
    rankings.to_csv(rankings_csv, index=False)
    write_json(rankings_json, rankings.to_dict(orient="records"))
    outputs.extend([rankings_csv.name, rankings_json.name])

    for n in TOP_N_EXPORTS:
        top = rankings.head(n)
        csv_path = output_dir / f"top_{n}_sites.csv"
        json_path = output_dir / f"top_{n}_sites.json"
        top.to_csv(csv_path, index=False)
        write_json(json_path, top.to_dict(orient="records"))
        outputs.extend([csv_path.name, json_path.name])

    # Monthly total trend from the same source.
    monthly = (
        df.groupby("month_label", as_index=False)
        .agg(
            total_volume=("month_site_volume", "sum"),
            active_sites=("scats_site", "nunique"),
        )
        .sort_values("month_label")
    )
    monthly["total_volume"] = monthly["total_volume"].round(0).astype("int64")
    monthly_csv = output_dir / "site_totals_monthly_network_trend.csv"
    monthly_json = output_dir / "site_totals_monthly_network_trend.json"
    monthly.to_csv(monthly_csv, index=False)
    write_json(monthly_json, monthly.to_dict(orient="records"))
    outputs.extend([monthly_csv.name, monthly_json.name])

    # Percentile / concentration summary.
    bands = (
        rankings.groupby("percentile_band", as_index=False)
        .agg(
            sites=("scats_site", "count"),
            total_volume=("total_volume", "sum"),
        )
    )
    grand_total = rankings["total_volume"].sum()
    bands["share_percent"] = (bands["total_volume"] / grand_total * 100).round(4) if grand_total else 0
    bands_csv = output_dir / "site_volume_percentile_bands.csv"
    bands_json = output_dir / "site_volume_percentile_bands.json"
    bands.to_csv(bands_csv, index=False)
    write_json(bands_json, bands.to_dict(orient="records"))
    outputs.extend([bands_csv.name, bands_json.name])

    summary["generated_outputs"] = outputs
    summary_json = output_dir / "site_network_summary.json"
    write_json(summary_json, summary)
    outputs.append(summary_json.name)

    print("=" * 80)
    print("SCATS SITE INTELLIGENCE V1 COMPLETE")
    print("=" * 80)
    print(f"Input file             : {input_path}")
    print(f"Output directory       : {output_dir}")
    print(f"Months completed       : {summary['input_months_completed']} / {summary['expected_months']}")
    print(f"First month / last     : {summary['first_month']} / {summary['last_month']}")
    print(f"Total sites            : {summary['total_sites']:,}")
    print(f"Grand total volume     : {summary['grand_total_volume']:,}")
    print(f"Top site               : {summary['top_site']['scats_site']}")
    if summary['top_site'].get('site_name'):
        print(f"Top site name          : {summary['top_site']['site_name']}")
    print(f"Top site volume        : {summary['top_site']['total_volume']:,}")
    print(f"Top 100 share          : {summary['traffic_concentration']['top_100_share_percent']}%")
    print("=" * 80)
    print("Generated files:")
    for name in outputs:
        print(f"  - {name}")


if __name__ == "__main__":
    main()
