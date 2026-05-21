#!/usr/bin/env python3
r"""
generate_covid_leaderboard_animationsV1.py

Creates two animated leaderboards:
  - Top 30 traffic collapse sites
  - Top 30 post-COVID growth sites
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt

from _common_covid_animation import *


def build_site_pivot(df):
    site = (
        df.groupby(["comparison_period", "site_id"], observed=True)
        .agg(site_volume=("volume", "sum"), site_name=("site_name", "first"))
        .reset_index()
    )
    pivot = site.pivot_table(index="site_id", columns="comparison_period", values="site_volume", aggfunc="sum").reset_index()
    names = site.groupby("site_id", as_index=False).agg(site_name=("site_name", "first"))
    return names.merge(pivot, on="site_id", how="left")


def render_leaderboard(data, value_col, title, subtitle, color, xlabel, frames_dir, mp4_name, outdir, fps, ffmpeg):
    frames = 150
    max_val = data[value_col].max() / 1_000_000 * 1.08

    for i in range(frames):
        t = i / max(frames - 1, 1)
        ease = 0.5 - 0.5 * math.cos(math.pi * t)
        vals = data[value_col] / 1_000_000 * ease

        fig, ax = plt.subplots(figsize=(15, 12))
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        fig.subplots_adjust(top=0.86, bottom=0.08, left=0.30, right=0.96)
        title_block(fig, title, subtitle)

        labels = data["label"]
        ax.barh(labels[::-1], vals[::-1], color=color)
        ax.set_xlim(0, max_val)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("SCATS Site")
        ax.grid(axis="x", alpha=0.25)

        if i == frames - 1:
            for y, val in enumerate(vals[::-1]):
                ax.text(val, y, f" {val:.2f}M", va="center", fontsize=8)

        fig.savefig(frames_dir / f"frame_{i:05d}.png", dpi=140, bbox_inches="tight")
        plt.close(fig)

        if (i + 1) % 30 == 0:
            print(f"Rendered {mp4_name}: frame {i + 1}/{frames}")

    run_ffmpeg(frames_dir, outdir / mp4_name, fps, ffmpeg)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default=DEFAULT_COVID_CSV)
    p.add_argument("--outdir", default=DEFAULT_OUTDIR)
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--ffmpeg", default=DEFAULT_FFMPEG)
    args = p.parse_args()

    outdir = Path(args.outdir)
    df = load_covid_csv(Path(args.input))
    pivot = build_site_pivot(df)

    collapse = pivot.copy()
    collapse["absolute_collapse"] = collapse["Pre-COVID baseline"].fillna(0) - collapse["Lockdown / COVID shock"].fillna(0)
    collapse = collapse[collapse["absolute_collapse"] > 0].sort_values("absolute_collapse", ascending=False).head(30).copy()
    collapse["label"] = collapse["site_name"].fillna(collapse["site_id"]).astype(str).str.slice(0, 38)

    growth = pivot.copy()
    growth["growth_vs_baseline"] = growth["Busiest day detected"].fillna(0) - growth["Pre-COVID baseline"].fillna(0)
    growth = growth[growth["growth_vs_baseline"] > 0].sort_values("growth_vs_baseline", ascending=False).head(30).copy()
    growth["label"] = growth["site_name"].fillna(growth["site_id"]).astype(str).str.slice(0, 38)

    collapse_frames = outdir / "frames_covid_top30_collapse"
    growth_frames = outdir / "frames_covid_top30_growth"
    ensure_clean_dir(collapse_frames)
    ensure_clean_dir(growth_frames)

    render_leaderboard(
        collapse,
        "absolute_collapse",
        "Top 30 SCATS Sites by COVID Traffic Collapse",
        "2020 lockdown comparison day vs 2019 baseline day.",
        "#b00020",
        "Absolute Volume Loss (Millions)",
        collapse_frames,
        "covid_top30_collapse_leaderboard_animation.mp4",
        outdir,
        args.fps,
        args.ffmpeg,
    )

    render_leaderboard(
        growth,
        "growth_vs_baseline",
        "Top 30 SCATS Sites by Post-COVID Growth",
        "2025 busiest detected day vs 2019 baseline day.",
        "#16a34a",
        "Growth Above 2019 Baseline (Millions)",
        growth_frames,
        "covid_top30_growth_leaderboard_animation.mp4",
        outdir,
        args.fps,
        args.ffmpeg,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
