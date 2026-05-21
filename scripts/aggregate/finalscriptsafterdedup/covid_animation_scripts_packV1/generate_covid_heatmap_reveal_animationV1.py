#!/usr/bin/env python3
r"""
generate_covid_heatmap_reveal_animationV1.py

Creates a row-by-row reveal of the COVID traffic heartbeat heatmap.
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
    p.add_argument("--frames", type=int, default=144)
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--ffmpeg", default=DEFAULT_FFMPEG)
    args = p.parse_args()

    outdir = Path(args.outdir)
    frames_dir = outdir / "frames_covid_heatmap_reveal"
    ensure_clean_dir(frames_dir)

    df = load_covid_csv(Path(args.input))
    tb = (
        df.groupby(["comparison_period", "time_minutes"], observed=True)
        .agg(total_volume=("volume", "sum"))
        .reset_index()
    )
    pivot = tb.pivot_table(index="comparison_period", columns="time_minutes", values="total_volume", aggfunc="sum")
    ordered = [p for p in PERIOD_ORDER if p in pivot.index] + [p for p in pivot.index if p not in PERIOD_ORDER]
    pivot = pivot.loc[ordered]
    values = pivot.values / 1_000_000

    labels = [PERIOD_SHORT.get(str(p), str(p)) for p in pivot.index]
    xcols = pivot.columns.tolist()
    xtick_positions = [i for i, m in enumerate(xcols) if m % 120 == 0]
    xtick_labels = [f"{int(xcols[i] // 60):02d}:00" for i in xtick_positions]

    for i in range(args.frames):
        t = i / max(args.frames - 1, 1)
        rows_float = t * len(labels)
        reveal_rows = int(np.ceil(rows_float))
        reveal_rows = max(1, min(len(labels), reveal_rows))

        masked = np.full_like(values, np.nan)
        masked[:reveal_rows, :] = values[:reveal_rows, :]

        fig, ax = plt.subplots(figsize=(16, 7.5))
        fig.patch.set_facecolor("white")
        fig.subplots_adjust(top=0.80, bottom=0.18, left=0.12, right=0.90)
        title_block(
            fig,
            "Melbourne COVID Traffic Heartbeat",
            "Historical comparison days revealed row-by-row across 15-minute time bins."
        )

        im = ax.imshow(masked, aspect="auto", cmap="YlOrRd", vmin=np.nanmin(values), vmax=np.nanmax(values))
        cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.035)
        cbar.set_label("Vehicle Movements per 15-Minute Bin (Millions)")

        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels)
        ax.set_xticks(xtick_positions)
        ax.set_xticklabels(xtick_labels, rotation=45, ha="right")
        ax.set_xlabel("Time of Day")
        ax.set_ylabel("Comparison Period")

        fig.savefig(frames_dir / f"frame_{i:05d}.png", dpi=140, bbox_inches="tight")
        plt.close(fig)

        if (i + 1) % 24 == 0:
            print(f"Rendered frame {i + 1}/{args.frames}")

    out_mp4 = outdir / "covid_heatmap_reveal_animation.mp4"
    run_ffmpeg(frames_dir, out_mp4, args.fps, args.ffmpeg)
    print(f"Wrote: {out_mp4}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
