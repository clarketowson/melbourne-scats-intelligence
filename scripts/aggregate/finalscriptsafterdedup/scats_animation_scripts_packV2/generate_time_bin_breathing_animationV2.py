#!/usr/bin/env python3
r"""
generate_time_bin_breathing_animationV2.py

Creates a 24-hour breathing/radial traffic rhythm animation from time_bin_profile.csv.

V2 fix:
  - Supports the actual completed time_bin_profile.csv schema:
      month_label, month_start, next_month_start, time_bin,
      month_time_bin_volume, days_in_month_loaded,
      month_elapsed_seconds, completed_at_epoch, row_type
  - Aggregates month_time_bin_volume across all months by time_bin.
  - Divides by days_in_month_loaded to create an average daily volume per 15-minute bin.
  - Falls back to other volume-style columns if used on a different CSV variant.

Input default:
  A:\TrafficAnalytics\PROJECTS\reports\deduped\time_bin_profile.csv

Output default:
  A:\TrafficAnalytics\PROJECTS\reports\deduped\animations\time_bin_breathing_animation.mp4
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

DEFAULT_BASE = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")


def detect_col(df: pd.DataFrame, candidates: list[str], label: str) -> str:
    lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower:
            return lower[cand.lower()]
    raise ValueError(f"Could not detect {label}. Columns: {list(df.columns)}")


def normalise_time_bin(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip()
    # Handles HH:MM, HH:MM:SS, timestamps, and odd values reasonably.
    extracted = s.str.extract(r"(\d{1,2}:\d{2})", expand=False)
    s = extracted.fillna(s.str.slice(0, 5))
    # Pad 0:15 -> 00:15 if required.
    s = s.str.replace(r"^(\d):", r"0\1:", regex=True)
    return s


def load_and_aggregate_time_bins(input_csv: Path) -> pd.DataFrame:
    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    df = pd.read_csv(input_csv, low_memory=False)
    print(f"Loaded rows: {len(df):,}")
    print(f"Columns: {list(df.columns)}")

    time_col = detect_col(df, ["time_bin", "time_label", "time", "bin_time"], "time bin")
    df[time_col] = normalise_time_bin(df[time_col])

    # Prefer the completed time-bin profile schema.
    lower = {c.lower(): c for c in df.columns}
    has_month_time_bin = "month_time_bin_volume" in lower
    has_days_loaded = "days_in_month_loaded" in lower

    if has_month_time_bin:
        volume_col = lower["month_time_bin_volume"]
        df[volume_col] = pd.to_numeric(df[volume_col], errors="coerce")

        if has_days_loaded:
            days_col = lower["days_in_month_loaded"]
            df[days_col] = pd.to_numeric(df[days_col], errors="coerce")
            grouped = (
                df.dropna(subset=[time_col, volume_col, days_col])
                  .groupby(time_col, as_index=False)
                  .agg(
                      total_volume=(volume_col, "sum"),
                      total_days_loaded=(days_col, "sum"),
                      months_seen=(volume_col, "count"),
                  )
            )
            grouped["avg_daily_volume"] = grouped["total_volume"] / grouped["total_days_loaded"].replace({0: np.nan})
        else:
            grouped = (
                df.dropna(subset=[time_col, volume_col])
                  .groupby(time_col, as_index=False)
                  .agg(total_volume=(volume_col, "sum"), months_seen=(volume_col, "count"))
            )
            grouped["total_days_loaded"] = np.nan
            grouped["avg_daily_volume"] = grouped["total_volume"] / grouped["months_seen"].replace({0: np.nan})

    else:
        # Generic fallback for alternate CSV variants.
        volume_col = detect_col(
            df,
            [
                "average_daily_volume",
                "avg_daily_volume",
                "busiest_time_bin_average_daily_volume",
                "time_bin_average_daily_volume",
                "total_volume",
                "volume",
                "sum_volume",
            ],
            "volume",
        )
        df[volume_col] = pd.to_numeric(df[volume_col], errors="coerce")
        grouped = (
            df.dropna(subset=[time_col, volume_col])
              .groupby(time_col, as_index=False)
              .agg(avg_daily_volume=(volume_col, "mean"), total_volume=(volume_col, "sum"), months_seen=(volume_col, "count"))
        )
        grouped["total_days_loaded"] = np.nan

    grouped = grouped.dropna(subset=["avg_daily_volume"]).copy()
    grouped = grouped[grouped["avg_daily_volume"] >= 0].copy()
    grouped["sort_time"] = pd.to_datetime(grouped[time_col], format="%H:%M", errors="coerce")
    grouped = grouped.dropna(subset=["sort_time"]).sort_values("sort_time").reset_index(drop=True)
    grouped = grouped.rename(columns={time_col: "time_bin"})

    if len(grouped) != 96:
        print(f"WARNING: expected 96 x 15-minute bins, found {len(grouped):,}")
    else:
        print("Detected 96 x 15-minute bins.")

    busiest = grouped.loc[grouped["avg_daily_volume"].idxmax()]
    quietest = grouped.loc[grouped["avg_daily_volume"].idxmin()]
    print(f"Busiest time bin : {busiest['time_bin']} ({busiest['avg_daily_volume']:,.0f})")
    print(f"Quietest time bin: {quietest['time_bin']} ({quietest['avg_daily_volume']:,.0f})")

    return grouped


def run_ffmpeg(frames_dir: Path, mp4_path: Path, fps: int) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found in PATH. Install ffmpeg or add it to PATH.")

    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-framerate", str(fps),
            "-i", str(frames_dir / "frame_%05d.png"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(mp4_path),
        ],
        check=True,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(DEFAULT_BASE / "time_bin_profile.csv"))
    ap.add_argument("--outdir", default=str(DEFAULT_BASE / "animations"))
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--loops", type=int, default=3)
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--keep-frames", action="store_true")
    args = ap.parse_args()

    input_csv = Path(args.input)
    outdir = Path(args.outdir)
    frames = outdir / "frames_time_bin_breathing"
    outdir.mkdir(parents=True, exist_ok=True)
    frames.mkdir(parents=True, exist_ok=True)

    df = load_and_aggregate_time_bins(input_csv)

    n = len(df)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    vals = df["avg_daily_volume"].to_numpy(dtype=float)
    vmin, vmax = float(np.nanmin(vals)), float(np.nanmax(vals))
    norm = (vals - vmin) / (vmax - vmin) if vmax > vmin else np.zeros_like(vals)
    radii = 0.32 + norm * 0.68

    busiest_idx = int(np.argmax(vals))
    quietest_idx = int(np.argmin(vals))
    total_frames = n * max(1, args.loops)

    print(f"Rendering frames: {total_frames:,}")

    for frame in range(total_frames):
        i = frame % n
        current_time = df.loc[i, "time_bin"]
        current_val = vals[i]

        fig = plt.figure(figsize=(14, 14))
        ax = plt.subplot(111, projection="polar")
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.set_ylim(0, 1.20)
        ax.set_yticklabels([])
        ax.set_xticks(np.linspace(0, 2*np.pi, 8, endpoint=False))
        ax.set_xticklabels(["00:00", "03:00", "06:00", "09:00", "12:00", "15:00", "18:00", "21:00"], fontsize=10)
        ax.grid(alpha=0.20)

        # Whole day rhythm.
        bar_width = (2 * np.pi / n) * 0.92
        ax.bar(angles, radii, width=bar_width, alpha=0.42)
        ax.plot(angles, radii, linewidth=2.4, alpha=0.85)

        # Current pulse.
        ax.bar([angles[i]], [radii[i]], width=bar_width * 1.3, alpha=1.0)
        ax.scatter([angles[i]], [radii[i]], s=260, zorder=6)

        # Mark busiest and quietest bins subtly.
        ax.scatter([angles[busiest_idx]], [radii[busiest_idx]], s=90, marker="^", zorder=5)
        ax.scatter([angles[quietest_idx]], [radii[quietest_idx]], s=90, marker="v", zorder=5)

        ax.set_title(
            "Melbourne Breathes: 24-Hour SCATS Traffic Rhythm",
            fontsize=23,
            fontweight="bold",
            pad=30,
        )
        fig.text(
            0.5,
            0.515,
            current_time,
            ha="center",
            va="center",
            fontsize=54,
            fontweight="bold",
        )
        fig.text(
            0.5,
            0.465,
            f"Average daily movements in this 15-minute bin: {current_val:,.0f}",
            ha="center",
            va="center",
            fontsize=14,
        )
        fig.text(
            0.5,
            0.435,
            f"Busiest: {df.loc[busiest_idx, 'time_bin']}  |  Quietest: {df.loc[quietest_idx, 'time_bin']}",
            ha="center",
            va="center",
            fontsize=12,
        )
        fig.text(
            0.5,
            0.085,
            "Source: Melbourne SCATS cleaned 15-minute traffic profile, 2014-01-01 to 2026-04-07",
            ha="center",
            va="center",
            fontsize=10,
        )

        fig.tight_layout()
        fig.savefig(frames / f"frame_{frame:05d}.png", dpi=args.dpi, bbox_inches="tight")
        plt.close(fig)

    mp4 = outdir / "time_bin_breathing_animation.mp4"
    run_ffmpeg(frames, mp4, args.fps)
    print(f"Wrote: {mp4}")

    summary_csv = outdir / "time_bin_breathing_aggregated_profile.csv"
    df[["time_bin", "avg_daily_volume", "total_volume", "total_days_loaded", "months_seen"]].to_csv(summary_csv, index=False)
    print(f"Wrote aggregated profile: {summary_csv}")

    if not args.keep_frames:
        shutil.rmtree(frames, ignore_errors=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
