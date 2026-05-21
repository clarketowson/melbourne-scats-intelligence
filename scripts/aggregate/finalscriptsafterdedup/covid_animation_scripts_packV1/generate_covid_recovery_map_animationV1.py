#!/usr/bin/env python3
r"""
generate_covid_recovery_map_animationV1.py

Creates a cinematic static-map style COVID recovery animation from the COVID comparison CSV.

Output:
  A:\TrafficAnalytics\PROJECTS\reports\deduped\animations\covid\covid_recovery_map_animation.mp4
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

from _common_covid_animation import *


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default=DEFAULT_COVID_CSV)
    p.add_argument("--outdir", default=DEFAULT_OUTDIR)
    p.add_argument("--frames-per-period", type=int, default=48)
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--ffmpeg", default=DEFAULT_FFMPEG)
    args = p.parse_args()

    outdir = Path(args.outdir)
    frames_dir = outdir / "frames_covid_recovery_map"
    ensure_clean_dir(frames_dir)

    print("=" * 90)
    print("COVID RECOVERY MAP ANIMATION V1")
    print("=" * 90)

    df = load_covid_csv(Path(args.input))
    print(f"Rows loaded: {fmt_int(len(df))}")

    site_period = (
        df.groupby(["comparison_period", "site_id", "site_name"], observed=True)
        .agg(volume=("volume", "sum"), latitude=("latitude", "first"), longitude=("longitude", "first"))
        .reset_index()
    )

    periods = order_periods(site_period["comparison_period"].unique().tolist())
    max_volume = site_period["volume"].quantile(0.995)

    lon_min, lon_max = site_period["longitude"].min(), site_period["longitude"].max()
    lat_min, lat_max = site_period["latitude"].min(), site_period["latitude"].max()
    lon_pad = (lon_max - lon_min) * 0.07
    lat_pad = (lat_max - lat_min) * 0.10

    frame_idx = 0
    total_frames = len(periods) * args.frames_per_period

    for pi, period in enumerate(periods):
        sub = site_period[site_period["comparison_period"].eq(period)].copy()
        total = sub["volume"].sum()
        active_sites = sub["site_id"].nunique()
        color = PERIOD_COLORS.get(period, "#007bff")

        scaled = np.clip(sub["volume"] / max_volume, 0, 1)
        sizes = 8 + scaled * 90

        for j in range(args.frames_per_period):
            t = j / max(args.frames_per_period - 1, 1)
            ease = 0.5 - 0.5 * math.cos(math.pi * t)
            pulse = 1.0 + 0.18 * math.sin(t * math.pi * 4)

            fig, ax = plt.subplots(figsize=(16, 9))
            fig.patch.set_facecolor("#ffffff")
            ax.set_facecolor("#f8fafc")
            fig.subplots_adjust(top=0.82, bottom=0.08, left=0.04, right=0.97)
            title_block(
                fig,
                "Melbourne COVID Traffic Collapse and Recovery",
                "SCATS sites coloured by historical comparison period; point size reflects daily site volume."
            )

            ax.set_xlim(lon_min - lon_pad, lon_max + lon_pad)
            ax.set_ylim(lat_min - lat_pad, lat_max + lat_pad)
            ax.grid(color="#94a3b8", alpha=0.16, linewidth=0.7)
            ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)

            reveal_n = int(max(1, len(sub) * ease))
            visible = sub.iloc[:reveal_n]
            visible_sizes = sizes.iloc[:reveal_n] * pulse

            ax.scatter(
                visible["longitude"],
                visible["latitude"],
                s=visible_sizes * 2.6,
                color=color,
                alpha=0.10,
                linewidths=0,
            )
            ax.scatter(
                visible["longitude"],
                visible["latitude"],
                s=visible_sizes,
                color=color,
                alpha=0.45,
                linewidths=0,
            )

            ax.text(
                0.045, 0.88,
                PERIOD_SHORT.get(period, period),
                transform=ax.transAxes,
                fontsize=24,
                fontweight="bold",
                color=color,
                ha="left",
                va="top",
                bbox=dict(boxstyle="round,pad=0.45", facecolor="white", edgecolor="#dbe3ef", alpha=0.95),
            )
            ax.text(
                0.047, 0.765,
                f"Total daily volume: {fmt_millions(total)}\nActive mapped sites: {fmt_int(active_sites)}",
                transform=ax.transAxes,
                fontsize=14,
                color="#111827",
                ha="left",
                va="top",
                bbox=dict(boxstyle="round,pad=0.55", facecolor="#f8fafc", edgecolor="#dbe3ef", alpha=0.95),
            )

            progress = frame_idx / max(total_frames - 1, 1)
            ax.add_patch(plt.Rectangle((0.05, 0.045), 0.90, 0.012, transform=ax.transAxes, color="#dbe3ef", lw=0))
            ax.add_patch(plt.Rectangle((0.05, 0.045), 0.90 * progress, 0.012, transform=ax.transAxes, color="#007bff", lw=0))

            fig.savefig(frames_dir / f"frame_{frame_idx:05d}.png", dpi=140, bbox_inches="tight")
            plt.close(fig)

            if frame_idx % 25 == 0:
                print(f"Rendered frame {frame_idx + 1}/{total_frames}")
            frame_idx += 1

    out_mp4 = outdir / "covid_recovery_map_animation.mp4"
    run_ffmpeg(frames_dir, out_mp4, args.fps, args.ffmpeg)
    print(f"Wrote: {out_mp4}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
