#!/usr/bin/env python3
r"""
generate_daily_totals_animationV1.py

Creates an animated daily total traffic line chart from daily_totals.csv.

Default input:
  A:\TrafficAnalytics\PROJECTS\reports\deduped\daily_totals.csv

Default output:
  A:\TrafficAnalytics\PROJECTS\reports\deduped\animations\daily_total_traffic_animation.mp4

Requires:
  pip install pandas matplotlib numpy
  ffmpeg available on PATH
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import shutil

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

DEFAULT_BASE = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")


def detect_col(df: pd.DataFrame, candidates: list[str], label: str) -> str:
    lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower:
            return lower[cand.lower()]
    raise ValueError(f"Could not detect {label} column. Columns: {list(df.columns)}")


def fmt_millions(x: float) -> str:
    return f"{x/1e6:.1f}M"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(DEFAULT_BASE / "daily_totals.csv"))
    ap.add_argument("--outdir", default=str(DEFAULT_BASE / "animations"))
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--step", type=int, default=7, help="Days revealed per rendered frame")
    ap.add_argument("--dpi", type=int, default=140)
    ap.add_argument("--keep-frames", action="store_true")
    args = ap.parse_args()

    csv_path = Path(args.input)
    outdir = Path(args.outdir)
    frames = outdir / "frames_daily_totals"
    outdir.mkdir(parents=True, exist_ok=True)
    frames.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path, low_memory=False)
    date_col = detect_col(df, ["date", "count_date", "day", "traffic_date"], "date")
    vol_col = detect_col(df, ["total_volume", "day_total_volume", "volume", "daily_total", "month_total_volume"], "volume")

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df[vol_col] = pd.to_numeric(df[vol_col], errors="coerce")
    df = df.dropna(subset=[date_col, vol_col]).sort_values(date_col).reset_index(drop=True)
    df["rolling_30"] = df[vol_col].rolling(30, min_periods=1).mean()

    ymax = df[vol_col].quantile(0.995) * 1.12
    ymin = max(0, df[vol_col].quantile(0.005) * 0.70)

    frame_no = 0
    for end in range(args.step, len(df) + args.step, args.step):
        sub = df.iloc[:min(end, len(df))]
        current = sub.iloc[-1]
        fig, ax = plt.subplots(figsize=(16, 9))
        ax.plot(sub[date_col], sub[vol_col] / 1e6, linewidth=1.0, alpha=0.35, label="Daily total")
        ax.plot(sub[date_col], sub["rolling_30"] / 1e6, linewidth=2.6, label="30-day rolling average")
        ax.scatter([current[date_col]], [current[vol_col] / 1e6], s=70, zorder=5)
        ax.set_title("Melbourne SCATS Daily Traffic Pulse", fontsize=24, fontweight="bold", pad=16)
        ax.set_xlabel("Date")
        ax.set_ylabel("Daily vehicle movements (millions)")
        ax.set_xlim(df[date_col].min(), df[date_col].max())
        ax.set_ylim(ymin / 1e6, ymax / 1e6)
        ax.grid(alpha=0.25)
        ax.legend(loc="upper left")
        ax.text(0.02, 0.92, current[date_col].strftime("%A %d %B %Y"), transform=ax.transAxes, fontsize=16, fontweight="bold")
        ax.text(0.02, 0.86, f"Daily volume: {fmt_millions(current[vol_col])}", transform=ax.transAxes, fontsize=14)
        ax.text(0.02, 0.80, f"30-day average: {fmt_millions(current['rolling_30'])}", transform=ax.transAxes, fontsize=14)
        fig.tight_layout()
        fig.savefig(frames / f"frame_{frame_no:05d}.png", dpi=args.dpi)
        plt.close(fig)
        frame_no += 1

    mp4 = outdir / "daily_total_traffic_animation.mp4"
    cmd = ["ffmpeg", "-y", "-framerate", str(args.fps), "-i", str(frames / "frame_%05d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(mp4)]
    subprocess.run(cmd, check=True)
    print(f"Wrote: {mp4}")

    if not args.keep_frames:
        shutil.rmtree(frames, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
