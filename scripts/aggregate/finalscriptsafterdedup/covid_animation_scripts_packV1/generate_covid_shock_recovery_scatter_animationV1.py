#!/usr/bin/env python3
r"""
generate_covid_shock_recovery_scatter_animationV1.py

Animates the site shock vs recovery scatter.

Output:
  A:\TrafficAnalytics\PROJECTS\reports\deduped\animations\covid\covid_shock_recovery_scatter_animation.mp4
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
    p.add_argument("--frames", type=int, default=180)
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--ffmpeg", default=DEFAULT_FFMPEG)
    args = p.parse_args()

    outdir = Path(args.outdir)
    frames_dir = outdir / "frames_covid_shock_recovery_scatter"
    ensure_clean_dir(frames_dir)

    print("=" * 90)
    print("COVID SHOCK VS RECOVERY SCATTER ANIMATION V1")
    print("=" * 90)

    df = load_covid_csv(Path(args.input))
    site = (
        df.groupby(["comparison_period", "site_id"], observed=True)
        .agg(site_volume=("volume", "sum"), site_name=("site_name", "first"))
        .reset_index()
    )
    pivot = site.pivot_table(index="site_id", columns="comparison_period", values="site_volume", aggfunc="sum").reset_index()
    names = site.groupby("site_id", as_index=False).agg(site_name=("site_name", "first"))
    pvt = names.merge(pivot, on="site_id", how="left")

    needed = ["Pre-COVID baseline", "Lockdown / COVID shock", "Busiest day detected"]
    for n in needed:
        if n not in pvt.columns:
            raise RuntimeError(f"Missing period: {n}")

    pvt["baseline_volume"] = pvt["Pre-COVID baseline"]
    baseline_min = max(1000.0, float(pvt["baseline_volume"].quantile(0.10)))
    pvt = pvt[pvt["baseline_volume"] >= baseline_min].copy()
    pvt["lockdown_index"] = pvt["Lockdown / COVID shock"] / pvt["baseline_volume"] * 100
    pvt["busiest_index"] = pvt["Busiest day detected"] / pvt["baseline_volume"] * 100
    pvt = pvt.replace([np.inf, -np.inf], np.nan).dropna(subset=["lockdown_index", "busiest_index"])
    pvt = pvt[(pvt["lockdown_index"] >= 0) & (pvt["busiest_index"] >= 0)].copy()
    pvt = pvt.sort_values("baseline_volume", ascending=False).reset_index(drop=True)

    x_max = max(120, min(250, float(pvt["lockdown_index"].quantile(0.995)) * 1.08))
    y_max = max(150, min(350, float(pvt["busiest_index"].quantile(0.995)) * 1.08))
    sizes = np.clip(np.sqrt(pvt["baseline_volume"]) / 5, 8, 90)

    for i in range(args.frames):
        t = i / max(args.frames - 1, 1)
        ease = 0.5 - 0.5 * math.cos(math.pi * t)
        reveal_n = int(max(1, len(pvt) * ease))
        sub = pvt.iloc[:reveal_n]
        sub_sizes = sizes.iloc[:reveal_n]

        fig, ax = plt.subplots(figsize=(13.5, 9))
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        fig.subplots_adjust(top=0.82, bottom=0.12, left=0.10, right=0.96)
        title_block(
            fig,
            "SCATS Site Shock vs Recovery",
            "X = 2020 lockdown index vs 2019; Y = 2025 busiest day index vs 2019."
        )

        ax.scatter(
            sub["lockdown_index"],
            sub["busiest_index"],
            s=sub_sizes,
            alpha=0.38,
            color="#007bff",
            edgecolors="none",
        )
        ax.axvline(100, linestyle="--", color="#64748b", linewidth=1.2)
        ax.axhline(100, linestyle="--", color="#64748b", linewidth=1.2)
        ax.set_xlim(0, x_max)
        ax.set_ylim(0, y_max)
        ax.set_xlabel("2020 Lockdown Index (2019 = 100)")
        ax.set_ylabel("2025 Busiest Day Index (2019 = 100)")
        ax.grid(alpha=0.25)

        ax.text(5, y_max * 0.94, "Collapsed hard,\nthen over-recovered", fontsize=10, color="#475569", va="top")
        ax.text(x_max * 0.60, y_max * 0.94, "Resilient through lockdown,\nthen over-recovered", fontsize=10, color="#475569", va="top")
        ax.text(5, y_max * 0.10, f"Sites revealed: {fmt_int(reveal_n)} / {fmt_int(len(pvt))}", fontsize=11, color="#64748b", va="bottom")

        fig.savefig(frames_dir / f"frame_{i:05d}.png", dpi=140, bbox_inches="tight")
        plt.close(fig)

        if (i + 1) % 30 == 0:
            print(f"Rendered frame {i + 1}/{args.frames}")

    out_mp4 = outdir / "covid_shock_recovery_scatter_animation.mp4"
    run_ffmpeg(frames_dir, out_mp4, args.fps, args.ffmpeg)
    print(f"Wrote: {out_mp4}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
