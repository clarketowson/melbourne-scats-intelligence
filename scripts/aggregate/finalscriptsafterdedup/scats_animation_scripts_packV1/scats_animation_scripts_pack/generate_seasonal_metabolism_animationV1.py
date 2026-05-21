#!/usr/bin/env python3
r"""
generate_seasonal_metabolism_animationV1.py

Creates a January-to-December seasonal metabolism animation from month_of_year_profile.csv.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess, shutil
import pandas as pd
import matplotlib.pyplot as plt

DEFAULT_BASE = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")
MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"]


def detect_col(df, candidates, label):
    lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower:
            return lower[cand.lower()]
    raise ValueError(f"Could not detect {label}. Columns: {list(df.columns)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(DEFAULT_BASE / "month_of_year_profile.csv"))
    ap.add_argument("--outdir", default=str(DEFAULT_BASE / "animations"))
    ap.add_argument("--fps", type=int, default=12)
    ap.add_argument("--hold", type=int, default=12, help="Frames to hold on each month")
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--keep-frames", action="store_true")
    args = ap.parse_args()

    df = pd.read_csv(args.input, low_memory=False)
    m_col = detect_col(df, ["month_of_year", "month_num", "month_number"], "month number")
    name_col = detect_col(df, ["month_name", "month"], "month name")
    val_col = detect_col(df, ["avg_daily_volume", "average_daily_volume", "month_avg_daily_volume", "month_total_volume"], "volume")
    df[m_col] = pd.to_numeric(df[m_col], errors="coerce")
    df[val_col] = pd.to_numeric(df[val_col], errors="coerce")
    df = df.dropna(subset=[m_col, val_col]).sort_values(m_col).reset_index(drop=True)
    df["seasonal_index"] = df[val_col] / df[val_col].mean() * 100

    outdir = Path(args.outdir); frames = outdir / "frames_seasonal_metabolism"
    outdir.mkdir(parents=True, exist_ok=True); frames.mkdir(parents=True, exist_ok=True)

    frame = 0
    ymax = df["seasonal_index"].max() * 1.12
    ymin = df["seasonal_index"].min() * 0.92
    for i in range(len(df)):
        for _ in range(args.hold):
            sub = df.iloc[:i+1]
            cur = df.iloc[i]
            fig, ax = plt.subplots(figsize=(16,9))
            colours = [plt.cm.RdYlGn_r((v-df["seasonal_index"].min())/(df["seasonal_index"].max()-df["seasonal_index"].min())) for v in df["seasonal_index"]]
            ax.bar(df[name_col], df["seasonal_index"], color=colours, alpha=0.25)
            ax.bar([cur[name_col]], [cur["seasonal_index"]], color=colours[i], alpha=1.0)
            ax.plot(sub[name_col], sub["seasonal_index"], linewidth=3, marker="o")
            ax.axhline(100, linestyle="--", linewidth=1.5)
            ax.set_ylim(ymin, ymax)
            ax.set_ylabel("Seasonal index: 100 = average month")
            ax.set_title("Melbourne Seasonal Traffic Metabolism", fontsize=24, fontweight="bold", pad=16)
            ax.text(0.02, 0.90, str(cur[name_col]), transform=ax.transAxes, fontsize=22, fontweight="bold")
            ax.text(0.02, 0.84, f"Avg daily volume: {cur[val_col]/1e6:.1f}M", transform=ax.transAxes, fontsize=15)
            ax.text(0.02, 0.78, f"Seasonal index: {cur['seasonal_index']:.1f}", transform=ax.transAxes, fontsize=15)
            ax.tick_params(axis="x", rotation=35)
            ax.grid(axis="y", alpha=0.25)
            fig.tight_layout()
            fig.savefig(frames / f"frame_{frame:05d}.png", dpi=args.dpi)
            plt.close(fig)
            frame += 1

    mp4 = outdir / "seasonal_metabolism_animation.mp4"
    subprocess.run(["ffmpeg", "-y", "-framerate", str(args.fps), "-i", str(frames / "frame_%05d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(mp4)], check=True)
    print(f"Wrote: {mp4}")
    if not args.keep_frames: shutil.rmtree(frames, ignore_errors=True)

if __name__ == "__main__":
    main()
