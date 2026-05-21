#!/usr/bin/env python3
r"""
generate_weekday_vs_weekend_chart_ready.py

Builds a chart-ready weekday vs weekend comparison from the already-generated
weekday_weekend_split.csv and weekday_weekend_split_final.json.

Inputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\weekday_weekend_split_final.json

Outputs:
    A:\TrafficAnalytics\PROJECTS\reports\deduped\weekday_vs_weekend_chart_ready.csv
    A:\TrafficAnalytics\PROJECTS\reports\deduped\weekday_vs_weekend_chart_ready.json
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path


REPORT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")

INPUT_FINAL_JSON = REPORT_DIR / "weekday_weekend_split_final.json"

OUTPUT_CSV = REPORT_DIR / "weekday_vs_weekend_chart_ready.csv"
OUTPUT_JSON = REPORT_DIR / "weekday_vs_weekend_chart_ready.json"


def fmt_int(value):
    if value is None:
        return "N/A"
    return f"{int(round(value)):,}"


def fmt_pct(value):
    if value is None:
        return "N/A"
    return f"{float(value):.2f}%"


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Required input file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    print("=" * 90)
    print("GENERATING WEEKDAY VS WEEKEND CHART-READY OUTPUT")
    print("=" * 90)
    print(f"Input final JSON      : {INPUT_FINAL_JSON}")
    print(f"Output CSV            : {OUTPUT_CSV}")
    print(f"Output JSON           : {OUTPUT_JSON}")
    print("=" * 90)

    payload = load_json(INPUT_FINAL_JSON)
    if payload.get("is_complete") is False:
        raise RuntimeError("weekday_weekend_split_final.json indicates the build is not complete yet.")

    rows = [
        {
            "category": "Weekday",
            "total_volume": payload.get("weekday_volume"),
            "share_pct": payload.get("weekday_share"),
            "avg_day_volume": payload.get("weekday_avg_day_volume"),
            "formatted_total_volume": fmt_int(payload.get("weekday_volume")),
            "formatted_share_pct": fmt_pct(payload.get("weekday_share")),
            "formatted_avg_day_volume": fmt_int(payload.get("weekday_avg_day_volume")),
        },
        {
            "category": "Weekend",
            "total_volume": payload.get("weekend_volume"),
            "share_pct": payload.get("weekend_share"),
            "avg_day_volume": payload.get("weekend_avg_day_volume"),
            "formatted_total_volume": fmt_int(payload.get("weekend_volume")),
            "formatted_share_pct": fmt_pct(payload.get("weekend_share")),
            "formatted_avg_day_volume": fmt_int(payload.get("weekend_avg_day_volume")),
        },
    ]

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "category",
            "total_volume",
            "share_pct",
            "avg_day_volume",
            "formatted_total_volume",
            "formatted_share_pct",
            "formatted_avg_day_volume",
        ])
        for row in rows:
            writer.writerow([
                row["category"],
                row["total_volume"],
                row["share_pct"],
                row["avg_day_volume"],
                row["formatted_total_volume"],
                row["formatted_share_pct"],
                row["formatted_avg_day_volume"],
            ])

    out_payload = {
        "generated_at_epoch": round(time.time(), 3),
        "generated_at_readable": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_final_json": str(INPUT_FINAL_JSON),
        "source_is_complete": payload.get("is_complete"),
        "date_range_start": payload.get("date_range_start"),
        "date_range_end": payload.get("date_range_end"),
        "rows": rows,
    }

    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(out_payload, f, indent=2)

    print("Chart-ready output written.")
    print("=" * 90)


if __name__ == "__main__":
    main()