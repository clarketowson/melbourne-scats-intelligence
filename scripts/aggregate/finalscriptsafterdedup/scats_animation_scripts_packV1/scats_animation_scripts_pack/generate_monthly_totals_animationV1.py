#!/usr/bin/env python3
r"""
generate_monthly_totals_animationV1.py

Creates an animated monthly cumulative/growth chart from monthly_totals.csv.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess, shutil
import pandas as pd
import matplotlib.pyplot as plt

DEFAULT_BASE = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")


def detect_col(df, candidates, label):
    lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lower:
            return lower[cand.lower()]
    raise ValueError(f"Could not detect {label}. Columns: {list(df.columns)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(DEFAULT_BASE / "monthly_totals.csv"))
    ap.add_argument("--outdir", default=str(DEFAULT_BASE / "animations"))
    ap.add_argument("--fps", type=int, default=18)
    ap.add_argument("--dpi", type=int, default=140)
    ap.add_argument("--keep-frames", action="store_true")
    args = ap.parse_args()

    df = pd.read_csv(args.input, low_memory=False)
    date_col = detect_col(df, ["month_start", "month", "month_date", "date"], "month date")
    vol_col = detect_col(df, ["month_total_volume", "total_volume", "volume", "monthly_total"], "volume")
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df[vol_col] = pd.to_numeric(df[vol_col], errors="coerce")
    df = df.dropna(subset=[date_col, vol_col]).sort_values(date_col).reset_index(drop=True)
    df["cumulative"] = df[vol_col].cumsum()

    outdir = Path(args.outdir); frames = outdir / "frames_monthly_totals"
    outdir.mkdir(parents=True, exist_ok=True); frames.mkdir(parents=True, exist_ok=True)

    ymax_month = df[vol_col].max() / 1e9 * 1.15
    ymax_cum = df["cumulative"].max() / 1e9 * 1.08

    for i in range(1, len(df) + 1):
        sub = df.iloc[:i]
        cur = sub.iloc[-1]
        fig, ax1 = plt.subplots(figsize=(16, 9))
        ax1.bar(sub[date_col], sub[vol_col] / 1e9, width=24, alpha=0.75, label="Monthly volume")
        ax1.set_ylabel("Monthly vehicle movements (billions)")
        ax1.set_ylim(0, ymax_month)
        ax1.grid(axis="y", alpha=0.25)

        ax2 = ax1.twinx()
        ax2.plot(sub[date_col], sub["cumulative"] / 1e9, linewidth=3, label="Cumulative volume")
        ax2.set_ylabel("Cumulative movements (billions)")
        ax2.set_ylim(0, ymax_cum)

        ax1.set_xlim(df[date_col].min(), df[date_col].max())
        ax1.set_title("Melbourne SCATS 12-Year Growth Animation", fontsize=24, fontweight="bold", pad=16)
        ax1.text(0.02, 0.92, cur[date_col].strftime("%B %Y"), transform=ax1.transAxes, fontsize=18, fontweight="bold")
        ax1.text(0.02, 0.86, f"Monthly volume: {cur[vol_col]/1e9:.2f}B", transform=ax1.transAxes, fontsize=14)
        ax1.text(0.02, 0.80, f"Cumulative volume: {cur['cumulative']/1e9:.1f}B", transform=ax1.transAxes, fontsize=14)
        fig.tight_layout()
        fig.savefig(frames / f"frame_{i-1:05d}.png", dpi=args.dpi)
        plt.close(fig)

    mp4 = outdir / "monthly_total_growth_animation.mp4"
    subprocess.run(["ffmpeg", "-y", "-framerate", str(args.fps), "-i", str(frames / "frame_%05d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(mp4)], check=True)
    print(f"Wrote: {mp4}")
    if not args.keep_frames: shutil.rmtree(frames, ignore_errors=True)

if __name__ == "__main__":
    main()
