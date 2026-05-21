#!/usr/bin/env python3
"""
generate_kepler_covid_comparison_daysV2_chunked.py

Chunked rewrite of generate_kepler_covid_comparison_daysV1.py.

Why V2 exists:
  V1 queried the full min_date..max_date range, then filtered selected dates in pandas.
  For widely separated comparison days this can scan/hold a huge amount of data.

V2 strategy:
  - Load metadata once.
  - Connect to DuckDB once.
  - Process one selected comparison date at a time.
  - Write each enriched day to a temporary CSV chunk.
  - Print detailed command-line progress at every stage.
  - Merge chunks at the end into one Kepler-ready CSV.

Output:
  A:\TrafficAnalytics\PROJECTS\reports\deduped\kepler_animation_exports\kepler_covid_collapse_recovery_comparison_days.csv

Kepler:
  Use animation_timestamp as the time field.
  Colour by comparison_period.
"""

from __future__ import annotations

import argparse
import gc
import json
import shutil
import time
from pathlib import Path

import pandas as pd
import numpy as np

from _common_scats_kepler import *


DEFAULT_DATES = [
    ("2019-05-15", "Pre-COVID baseline"),
    ("2020-08-05", "Lockdown / COVID shock"),
    ("2021-08-05", "Extended disruption"),
    ("2022-05-18", "Recovery phase"),
    ("2024-05-15", "Recent normal"),
    ("2025-12-12", "Busiest day detected"),
]


def fmt_int(value) -> str:
    try:
        return f"{int(value):,}"
    except Exception:
        return str(value)


def fmt_seconds(seconds: float) -> str:
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def parse_dates(value: str):
    """
    Format:
      YYYY-MM-DD:Label,YYYY-MM-DD:Label

    Example:
      2019-05-15:Pre-COVID,2020-08-05:Lockdown
    """
    out = []
    if not value:
        return DEFAULT_DATES

    for part in value.split(","):
        part = part.strip()
        if not part:
            continue

        if ":" in part:
            d, label = part.split(":", 1)
        else:
            d, label = part, part

        out.append((pd.to_datetime(d.strip()).strftime("%Y-%m-%d"), label.strip()))

    if not out:
        return DEFAULT_DATES

    return out


def safe_unlink(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


def process_one_date(
    con,
    meta: pd.DataFrame,
    selected_date: str,
    label: str,
    sequence: int,
    total_dates: int,
    out_chunk: Path,
    min_volume: float,
) -> dict:
    """
    Query, enrich and write one comparison date.
    """
    started = time.time()

    print("")
    print("-" * 90)
    print(f"[{sequence + 1}/{total_dates}] START DATE CHUNK")
    print("-" * 90)
    print(f"Date             : {selected_date}")
    print(f"Label            : {label}")
    print(f"Chunk output     : {out_chunk}")
    print("Stage 1/5        : querying DuckDB for exactly this one day...")
    print("")

    raw = query_site_time(con, selected_date, selected_date)

    print("")
    print("Stage 1/5 done   : DuckDB query complete")
    print(f"Raw rows         : {fmt_int(len(raw))}")

    if raw.empty:
        print("WARNING          : no raw rows returned for this date")
        empty = pd.DataFrame()
        empty.to_csv(out_chunk, index=False)
        return {
            "date": selected_date,
            "label": label,
            "rows_raw": 0,
            "rows_final": 0,
            "distinct_sites": 0,
            "total_volume": 0.0,
            "elapsed_seconds": round(time.time() - started, 3),
            "chunk_csv": str(out_chunk),
            "status": "empty",
        }

    print("Stage 2/5        : enriching rows with site coordinates and Kepler fields...")
    final = enrich_for_kepler(raw, meta, min_volume=min_volume)

    print("Stage 2/5 done   : enrichment complete")
    print(f"Rows after enrich: {fmt_int(len(final))}")

    del raw
    gc.collect()

    if final.empty:
        print("WARNING          : all rows dropped after coordinate/min-volume filtering")
        final.to_csv(out_chunk, index=False)
        return {
            "date": selected_date,
            "label": label,
            "rows_raw": None,
            "rows_final": 0,
            "distinct_sites": 0,
            "total_volume": 0.0,
            "elapsed_seconds": round(time.time() - started, 3),
            "chunk_csv": str(out_chunk),
            "status": "filtered_empty",
        }

    print("Stage 3/5        : adding comparison labels and synthetic animation timestamps...")

    final["comparison_period"] = label
    final["comparison_sequence"] = sequence

    # Give each comparison day a synthetic date so Kepler animates each comparison evenly.
    base = pd.Timestamp("2030-01-01")
    final["animation_timestamp"] = [
        base + pd.Timedelta(days=int(sequence)) + pd.Timedelta(hours=int(h), minutes=int(m))
        for h, m in zip(final["hour"], final["minute"])
    ]

    keep_cols = [
        "animation_timestamp",
        "timestamp",
        "date_label",
        "comparison_sequence",
        "comparison_period",
        "time_label",
        "hour",
        "minute",
        "site_id",
        "site_name",
        "latitude",
        "longitude",
        "volume",
        "scaled_volume",
        "scaled_volume_0_100",
        "intensity_band",
    ]

    missing = [c for c in keep_cols if c not in final.columns]
    if missing:
        raise RuntimeError(f"Missing expected columns after enrich_for_kepler(): {missing}. Columns: {list(final.columns)}")

    final = final[keep_cols].sort_values(["animation_timestamp", "volume"], ascending=[True, False])

    print("Stage 3/5 done   : timestamp fields added")
    print(f"Distinct sites   : {fmt_int(final['site_id'].nunique())}")
    print(f"Time bins        : {fmt_int(final['time_label'].nunique())}")
    print(f"Total volume     : {final['volume'].sum():,.0f}")
    print(f"Max point volume : {final['volume'].max():,.0f}")

    print("Stage 4/5        : writing chunk CSV...")
    out_chunk.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(out_chunk, index=False)

    rows_final = len(final)
    distinct_sites = final["site_id"].nunique()
    total_volume = float(final["volume"].sum())
    max_volume = float(final["volume"].max())

    del final
    gc.collect()

    elapsed = time.time() - started

    print("Stage 4/5 done   : chunk written")
    print(f"Chunk rows       : {fmt_int(rows_final)}")
    print(f"Elapsed chunk    : {fmt_seconds(elapsed)}")
    print("-" * 90)

    return {
        "date": selected_date,
        "label": label,
        "rows_final": int(rows_final),
        "distinct_sites": int(distinct_sites),
        "total_volume": total_volume,
        "max_point_volume": max_volume,
        "elapsed_seconds": round(elapsed, 3),
        "chunk_csv": str(out_chunk),
        "status": "complete",
    }


def merge_chunks(chunk_files: list[Path], out_csv: Path) -> pd.DataFrame:
    print("")
    print("=" * 90)
    print("MERGE STAGE")
    print("=" * 90)
    print(f"Chunks to merge  : {len(chunk_files):,}")
    print(f"Final output CSV : {out_csv}")
    print("")

    frames = []
    total_rows_seen = 0

    for i, chunk in enumerate(chunk_files, start=1):
        print(f"[merge {i}/{len(chunk_files)}] reading {chunk.name}")
        if not chunk.exists():
            print(f"  WARNING: chunk missing, skipping: {chunk}")
            continue

        df = pd.read_csv(chunk, low_memory=False)
        print(f"  rows: {fmt_int(len(df))}")
        total_rows_seen += len(df)

        if len(df):
            frames.append(df)

    if frames:
        final = pd.concat(frames, ignore_index=True)
        final["animation_timestamp"] = pd.to_datetime(final["animation_timestamp"], errors="coerce")
        final = final.sort_values(["animation_timestamp", "volume"], ascending=[True, False])
    else:
        final = pd.DataFrame()

    print("")
    print("Writing final merged CSV...")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(out_csv, index=False)

    print(f"Final rows       : {fmt_int(len(final))}")
    print(f"Input rows seen  : {fmt_int(total_rows_seen)}")

    return final


def write_summary(summary_path: Path, summary: dict) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(
        description="Chunked export of selected comparison days for Kepler.gl COVID collapse/recovery animation."
    )
    p.add_argument("--dates", default="", help="Comma list: YYYY-MM-DD:Label,YYYY-MM-DD:Label")
    p.add_argument("--main-db", default=DEFAULT_MAIN_DB)
    p.add_argument("--cont-db", default=DEFAULT_CONT_DB)
    p.add_argument("--rec-db", default=DEFAULT_REC_DB)
    p.add_argument("--metadata", default=DEFAULT_METADATA)
    p.add_argument("--outdir", default=DEFAULT_OUTDIR)
    p.add_argument("--temp-dir", default=r"C:\DuckDBTemp")
    p.add_argument("--memory-limit", default="20GB", help="Lower default than V1 because this runs date-by-date")
    p.add_argument("--threads", type=int, default=6)
    p.add_argument("--min-volume", type=float, default=1.0)
    p.add_argument("--keep-chunks", action="store_true", help="Keep temporary per-day chunk CSVs")
    p.add_argument("--resume", action="store_true", help="Reuse existing chunk CSVs if present")
    args = p.parse_args()

    overall_started = time.time()

    dates = parse_dates(args.dates)
    total_dates = len(dates)

    outdir = Path(args.outdir)
    chunks_dir = outdir / "_chunks_covid_comparison_days"
    out_csv = outdir / "kepler_covid_collapse_recovery_comparison_days.csv"
    out_summary = outdir / "kepler_covid_collapse_recovery_comparison_days_summary.json"

    print("=" * 90)
    print("KEPLER COVID COLLAPSE / RECOVERY COMPARISON DAYS EXPORT V2 - CHUNKED")
    print("=" * 90)
    print("Selected days:")
    for i, (d, label) in enumerate(dates, start=1):
        print(f"  {i}. {d} - {label}")
    print("")
    print(f"Main DB          : {args.main_db}")
    print(f"Continuation DB  : {args.cont_db}")
    print(f"Recovery DB      : {args.rec_db}")
    print(f"Metadata         : {args.metadata}")
    print(f"Output dir       : {outdir}")
    print(f"Chunks dir       : {chunks_dir}")
    print(f"Temp dir         : {args.temp_dir}")
    print(f"Memory limit     : {args.memory_limit}")
    print(f"Threads          : {args.threads}")
    print(f"Min volume       : {args.min_volume}")
    print(f"Resume           : {args.resume}")
    print("=" * 90)

    outdir.mkdir(parents=True, exist_ok=True)

    if chunks_dir.exists() and not args.resume:
        print("")
        print("Removing old chunks directory because --resume was not specified...")
        shutil.rmtree(chunks_dir, ignore_errors=True)

    chunks_dir.mkdir(parents=True, exist_ok=True)

    print("")
    print("Loading metadata...")
    meta_started = time.time()
    meta = load_metadata(Path(args.metadata))
    print(f"Metadata rows with coordinates: {fmt_int(len(meta))}")
    print(f"Metadata load elapsed         : {fmt_seconds(time.time() - meta_started)}")

    print("")
    print("Connecting to DuckDB...")
    connect_started = time.time()
    con = connect_duckdb(
        Path(args.main_db),
        Path(args.cont_db),
        Path(args.rec_db),
        Path(args.temp_dir),
        args.memory_limit,
        args.threads,
    )
    print(f"DuckDB connection elapsed     : {fmt_seconds(time.time() - connect_started)}")

    chunk_summaries = []
    chunk_files = []

    for sequence, (selected_date, label) in enumerate(dates):
        safe_label = "".join(ch if ch.isalnum() else "_" for ch in label).strip("_").lower()
        chunk_file = chunks_dir / f"covid_comparison_{sequence:02d}_{selected_date}_{safe_label}.csv"
        chunk_files.append(chunk_file)

        if args.resume and chunk_file.exists():
            print("")
            print("-" * 90)
            print(f"[{sequence + 1}/{total_dates}] RESUME: chunk already exists, skipping query")
            print(f"Date             : {selected_date}")
            print(f"Chunk            : {chunk_file}")
            try:
                existing = pd.read_csv(chunk_file, usecols=["site_id", "volume"])
                chunk_summaries.append({
                    "date": selected_date,
                    "label": label,
                    "rows_final": int(len(existing)),
                    "distinct_sites": int(existing["site_id"].nunique()) if len(existing) else 0,
                    "total_volume": float(existing["volume"].sum()) if len(existing) else 0.0,
                    "chunk_csv": str(chunk_file),
                    "status": "resumed",
                })
                del existing
                gc.collect()
            except Exception as e:
                print(f"WARNING: could not read existing chunk summary: {e}")
            continue

        safe_unlink(chunk_file)

        summary = process_one_date(
            con=con,
            meta=meta,
            selected_date=selected_date,
            label=label,
            sequence=sequence,
            total_dates=total_dates,
            out_chunk=chunk_file,
            min_volume=args.min_volume,
        )
        chunk_summaries.append(summary)

        elapsed_total = time.time() - overall_started
        completed = sequence + 1
        avg_per_chunk = elapsed_total / completed
        remaining = avg_per_chunk * (total_dates - completed)

        print("")
        print("OVERALL PROGRESS")
        print(f"Completed        : {completed}/{total_dates}")
        print(f"Overall elapsed  : {fmt_seconds(elapsed_total)}")
        print(f"Estimated remain : {fmt_seconds(remaining)}")
        print("=" * 90)

    final = merge_chunks(chunk_files, out_csv)

    if not final.empty:
        total_rows = int(len(final))
        distinct_sites = int(final["site_id"].nunique())
        total_volume = float(final["volume"].sum())
        comparison_periods = sorted(final["comparison_period"].dropna().unique().tolist())
        time_min = str(final["animation_timestamp"].min())
        time_max = str(final["animation_timestamp"].max())
    else:
        total_rows = 0
        distinct_sites = 0
        total_volume = 0.0
        comparison_periods = []
        time_min = None
        time_max = None

    summary = {
        "animation": "covid_collapse_recovery_comparison",
        "script_version": "V2_chunked",
        "selected_dates": [{"date": d, "label": label} for d, label in dates],
        "rows": total_rows,
        "distinct_sites": distinct_sites,
        "total_volume": total_volume,
        "comparison_periods": comparison_periods,
        "animation_timestamp_start": time_min,
        "animation_timestamp_end": time_max,
        "output_csv": str(out_csv),
        "chunk_summaries": chunk_summaries,
        "total_elapsed_seconds": round(time.time() - overall_started, 3),
        "total_elapsed_formatted": fmt_seconds(time.time() - overall_started),
    }

    write_summary(out_summary, summary)

    print("")
    print("=" * 90)
    print("FINAL SUMMARY")
    print("=" * 90)
    print(f"Output CSV       : {out_csv}")
    print(f"Summary JSON     : {out_summary}")
    print(f"Rows             : {fmt_int(total_rows)}")
    print(f"Distinct sites   : {fmt_int(distinct_sites)}")
    print(f"Total volume     : {total_volume:,.0f}")
    print(f"Elapsed total    : {summary['total_elapsed_formatted']}")
    print("")
    print("Kepler setup:")
    print("  Time field      : animation_timestamp")
    print("  Latitude field  : latitude")
    print("  Longitude field : longitude")
    print("  Size field      : scaled_volume_0_100 or volume")
    print("  Colour field    : comparison_period or intensity_band")
    print("=" * 90)

    if not args.keep_chunks:
        print("")
        print("Cleaning up chunk CSVs because --keep-chunks was not specified...")
        shutil.rmtree(chunks_dir, ignore_errors=True)
        print("Chunk cleanup complete.")
    else:
        print("")
        print(f"Chunks kept at: {chunks_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
