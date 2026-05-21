#!/usr/bin/env python3
r"""
generate_covid_24hour_heartbeat_animationV1.py

Animates the 24-hour traffic curves drawing across the day.

Output:
  A:\TrafficAnalytics\PROJECTS\reports\deduped\animations\covid\covid_24hour_heartbeat_animation.mp4
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt

from _common_covid_animation import *


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default=DEFAULT_COVID_CSV)
    p.add_argument("--outdir", default=DEFAULT_OUTDIR)
    p.add_argument("--frames", type=int, default=192)
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--ffmpeg", default=DEFAULT_FFMPEG)
    args = p.parse_args()

    outdir = Path(args.outdir)
    frames_dir = outdir / "frames_covid_24hour_heartbeat"
    ensure_clean_dir(frames_dir)

    print("=" * 90)
    print("COVID 24-HOUR HEARTBEAT ANIMATION V1")
    print("=" * 90)

    df = load_covid_csv(Path(args.input))
    tb = (
        df.groupby(["comparison_period", "time_minutes"], observed=True)
        .agg(total_volume=("volume", "sum"))
        .reset_index()
    )

    periods = order_periods(tb["comparison_period"].unique().tolist())
    y_max = tb["total_volume"].max() / 1_000_000 * 1.12

    for i in range(args.frames):
        progress_minutes = 24 * 60 * i / max(args.frames - 1, 1)

        fig, ax = plt.subplots(figsize=(16, 9))
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")
        fig.subplots_adjust(top=0.82, bottom=0.13, left=0.08, right=0.96)
        title_block(
            fig,
            "24-Hour Melbourne Traffic Shape Through COVID",
            "Curves draw across the day to show lockdown collapse, recovery, and 2025 overperformance."
        )

        for period in periods:
            sub = tb[tb["comparison_period"].eq(period)].sort_values("time_minutes")
            drawn = sub[sub["time_minutes"] <= progress_minutes]
            if drawn.empty:
                continue
            ax.plot(
                drawn["time_minutes"] / 60,
                drawn["total_volume"] / 1_000_000,
                linewidth=3.0 if period in ["Pre-COVID baseline", "Lockdown / COVID shock", "Busiest day detected"] else 2.2,
                color=PERIOD_COLORS.get(period, "#64748b"),
                label=PERIOD_SHORT.get(period, period),
            )

        ax.axvline(progress_minutes / 60, color="#64748b", linestyle="--", linewidth=1.2, alpha=0.6)
        ax.text(
            progress_minutes / 60,
            y_max * 0.96,
            f"{int(progress_minutes//60):02d}:{int(progress_minutes%60):02d}",
            ha="center",
            va="top",
            fontsize=12,
            fontweight="bold",
            color="#334155",
            bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="#dbe3ef", alpha=0.95),
        )

        ax.set_xlim(0, 24)
        ax.set_ylim(0, y_max)
        ax.set_xlabel("Hour of Day")
        ax.set_ylabel("Vehicle Movements per 15-Minute Bin (Millions)")
        ax.set_xticks(range(0, 25, 2))
        ax.grid(alpha=0.25)
        ax.legend(ncol=3, fontsize=10, loc="lower center", bbox_to_anchor=(0.5, 0.02), framealpha=0.95)

        fig.savefig(frames_dir / f"frame_{i:05d}.png", dpi=140, bbox_inches="tight")
        plt.close(fig)

        if (i + 1) % 24 == 0:
            print(f"Rendered frame {i + 1}/{args.frames}")

    out_mp4 = outdir / "covid_24hour_heartbeat_animation.mp4"
    run_ffmpeg(frames_dir, out_mp4, args.fps, args.ffmpeg)
    print(f"Wrote: {out_mp4}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
