#!/usr/bin/env python3
r"""
generate_time_bin_breathing_animationV1.py

Creates a 24-hour breathing/radial traffic rhythm animation from time_bin_profile.csv.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess, shutil
import numpy as np
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
    ap.add_argument("--input", default=str(DEFAULT_BASE / "time_bin_profile.csv"))
    ap.add_argument("--outdir", default=str(DEFAULT_BASE / "animations"))
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--loops", type=int, default=3)
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--keep-frames", action="store_true")
    args = ap.parse_args()

    df = pd.read_csv(args.input, low_memory=False)
    time_col = detect_col(df, ["time_bin", "time_label", "time", "bin_time"], "time bin")
    val_col = detect_col(df, ["average_daily_volume", "avg_daily_volume", "busiest_time_bin_average_daily_volume", "total_volume", "volume"], "volume")
    df[time_col] = df[time_col].astype(str).str.slice(0,5)
    df[val_col] = pd.to_numeric(df[val_col], errors="coerce")
    df = df.dropna(subset=[val_col]).drop_duplicates(subset=[time_col]).sort_values(time_col).reset_index(drop=True)

    # If file has multiple years/months per time bin, aggregate to 96 bins.
    df = df.groupby(time_col, as_index=False)[val_col].mean().sort_values(time_col).reset_index(drop=True)
    n = len(df)
    angles = np.linspace(0, 2*np.pi, n, endpoint=False)
    vals = df[val_col].to_numpy()
    norm = (vals - vals.min()) / (vals.max() - vals.min())
    radii = 0.35 + norm * 0.65

    outdir = Path(args.outdir); frames = outdir / "frames_time_bin_breathing"
    outdir.mkdir(parents=True, exist_ok=True); frames.mkdir(parents=True, exist_ok=True)

    total_frames = n * args.loops
    for frame in range(total_frames):
        i = frame % n
        fig = plt.figure(figsize=(10,10))
        ax = plt.subplot(111, projection="polar")
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.set_ylim(0, 1.15)
        ax.set_yticklabels([]); ax.set_xticklabels([])
        ax.grid(alpha=0.18)
        ax.bar(angles, radii, width=(2*np.pi/n)*0.9, alpha=0.45)
        ax.bar([angles[i]], [radii[i]], width=(2*np.pi/n)*1.15, alpha=1.0)
        ax.plot(angles, radii, linewidth=2)
        ax.scatter([angles[i]], [radii[i]], s=180, zorder=5)
        ax.set_title("Melbourne Breathes: 24-Hour Traffic Rhythm", fontsize=21, fontweight="bold", pad=24)
        fig.text(0.5, 0.47, df.loc[i, time_col], ha="center", va="center", fontsize=44, fontweight="bold")
        fig.text(0.5, 0.405, f"Avg daily volume in bin: {vals[i]:,.0f}", ha="center", va="center", fontsize=13)
        fig.tight_layout()
        fig.savefig(frames / f"frame_{frame:05d}.png", dpi=args.dpi)
        plt.close(fig)

    mp4 = outdir / "time_bin_breathing_animation.mp4"
    subprocess.run(["ffmpeg", "-y", "-framerate", str(args.fps), "-i", str(frames / "frame_%05d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(mp4)], check=True)
    print(f"Wrote: {mp4}")
    if not args.keep_frames: shutil.rmtree(frames, ignore_errors=True)

if __name__ == "__main__":
    main()
