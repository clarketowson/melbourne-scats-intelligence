#!/usr/bin/env python3
r"""
generate_time_bin_breathing_animationV3.py

Fixed V3 of the SCATS time-bin breathing animation.

Fixes:
  - Handles the actual time_bin_profile.csv schema:
      month_label, month_start, next_month_start, time_bin,
      month_time_bin_volume, days_in_month_loaded, ...
  - Aggregates month x time-bin rows into one 24-hour 96-bin profile.
  - Calculates average daily time-bin volume correctly:
      SUM(month_time_bin_volume) / SUM(days_in_month_loaded)
  - Fixes ffmpeg H.264 failure caused by odd image dimensions:
      width not divisible by 2
    by:
      1. rendering frames at a fixed even 16:9 canvas size
      2. adding an ffmpeg scale filter that truncates to even dimensions

Output:
  A:\TrafficAnalytics\PROJECTS\reports\deduped\animations\time_bin_breathing_animation.mp4
"""

from __future__ import annotations

import argparse
import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


DEFAULT_BASE_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")
DEFAULT_INPUT_CSV = DEFAULT_BASE_DIR / "time_bin_profile.csv"
DEFAULT_OUTDIR = DEFAULT_BASE_DIR / "animations"
DEFAULT_FFMPEG = "ffmpeg"


def find_ffmpeg(user_value: str | None) -> str:
    if user_value:
        return user_value

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg

    known = [
        r"E:\Program Files\ImageMagick-7.0.8-Q16\ffmpeg.EXE",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    ]

    for path in known:
        if Path(path).exists():
            return path

    return DEFAULT_FFMPEG


def normalise_time_bin(value: object) -> str:
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return ""

    # Handles HH:MM:SS
    if len(s) >= 5 and s[2:3] == ":":
        return s[:5]

    # Handles pandas-ish / Excel-ish variants if they appear
    try:
        dt = pd.to_datetime(s, errors="coerce")
        if pd.notna(dt):
            return dt.strftime("%H:%M")
    except Exception:
        pass

    return s[:5]


def load_time_bin_profile(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Input CSV not found: {path}")

    df = pd.read_csv(path, low_memory=False)
    print(f"Loaded rows: {len(df):,}")
    print(f"Columns: {list(df.columns)}")

    if "time_bin" not in df.columns:
        raise ValueError("Could not find required column: time_bin")

    df["time_bin"] = df["time_bin"].map(normalise_time_bin)
    df = df[df["time_bin"].str.match(r"^\d{2}:\d{2}$", na=False)].copy()

    # Prefer actual schema from your run.
    if {"month_time_bin_volume", "days_in_month_loaded"}.issubset(df.columns):
        df["month_time_bin_volume"] = pd.to_numeric(df["month_time_bin_volume"], errors="coerce").fillna(0)
        df["days_in_month_loaded"] = pd.to_numeric(df["days_in_month_loaded"], errors="coerce").fillna(0)

        grouped = (
            df.groupby("time_bin", as_index=False)
              .agg(
                  total_volume=("month_time_bin_volume", "sum"),
                  total_days_loaded=("days_in_month_loaded", "sum"),
                  months_seen=("month_label", "nunique") if "month_label" in df.columns else ("time_bin", "size"),
              )
        )

        grouped["avg_daily_volume"] = np.where(
            grouped["total_days_loaded"] > 0,
            grouped["total_volume"] / grouped["total_days_loaded"],
            0,
        )

    else:
        # Fallback support for earlier/simple schemas.
        volume_candidates = [
            "avg_daily_volume",
            "average_daily_volume",
            "busiest_time_bin_average_daily_volume",
            "total_volume",
            "volume",
            "time_bin_total_volume",
        ]
        val_col = next((c for c in volume_candidates if c in df.columns), None)
        if not val_col:
            raise ValueError(
                "Could not detect a usable volume column. "
                f"Columns found: {list(df.columns)}"
            )

        df[val_col] = pd.to_numeric(df[val_col], errors="coerce").fillna(0)
        grouped = (
            df.groupby("time_bin", as_index=False)
              .agg(avg_daily_volume=(val_col, "mean"))
        )
        grouped["total_volume"] = grouped["avg_daily_volume"]
        grouped["total_days_loaded"] = np.nan
        grouped["months_seen"] = np.nan

    grouped["sort_minutes"] = grouped["time_bin"].str.slice(0, 2).astype(int) * 60 + grouped["time_bin"].str.slice(3, 5).astype(int)
    grouped = grouped.sort_values("sort_minutes").reset_index(drop=True)

    if len(grouped) != 96:
        print(f"WARNING: Expected 96 time bins, found {len(grouped):,}.")

    print(f"Detected {len(grouped):,} x 15-minute bins.")
    busiest = grouped.loc[grouped["avg_daily_volume"].idxmax()]
    quietest = grouped.loc[grouped["avg_daily_volume"].idxmin()]
    print(f"Busiest time bin : {busiest['time_bin']} ({busiest['avg_daily_volume']:,.0f})")
    print(f"Quietest time bin: {quietest['time_bin']} ({quietest['avg_daily_volume']:,.0f})")

    return grouped


def render_frame(
    profile: pd.DataFrame,
    frame_idx: int,
    output_path: Path,
    loops: int,
    width_px: int,
    height_px: int,
    dpi: int,
) -> None:
    n = len(profile)
    idx = frame_idx % n

    current = profile.iloc[idx]
    time_label = current["time_bin"]
    current_value = float(current["avg_daily_volume"])
    max_value = float(profile["avg_daily_volume"].max())
    min_value = float(profile["avg_daily_volume"].min())
    mean_value = float(profile["avg_daily_volume"].mean())

    # Pulse size 0..1
    if max_value > min_value:
        intensity = (current_value - min_value) / (max_value - min_value)
    else:
        intensity = 0.5

    theta = np.linspace(0, 2 * np.pi, n, endpoint=False)
    values = profile["avg_daily_volume"].to_numpy(dtype=float)
    values_norm = (values - min_value) / (max_value - min_value) if max_value > min_value else np.ones_like(values) * 0.5

    # Canvas is fixed and even. Avoid bbox_inches="tight" to prevent odd dimensions.
    fig_w = width_px / dpi
    fig_h = height_px / dpi
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=dpi)
    ax = fig.add_subplot(111, projection="polar")
    fig.patch.set_facecolor("#07111f")
    ax.set_facecolor("#07111f")

    # Completed arc / full rhythm
    ax.plot(theta, values_norm, linewidth=2.0, alpha=0.45)
    ax.fill(theta, values_norm, alpha=0.12)

    # Highlight current time-bin
    ax.scatter(
        [theta[idx]],
        [values_norm[idx]],
        s=650 + intensity * 2600,
        alpha=0.85,
        edgecolors="white",
        linewidths=2,
    )

    # Add a soft central pulse using normal axes coordinates.
    pulse_radius = 0.13 + 0.20 * intensity
    circle = plt.Circle(
        (0.5, 0.5),
        pulse_radius,
        transform=ax.transAxes,
        color="white",
        alpha=0.045 + 0.10 * intensity,
        zorder=0,
    )
    ax.add_artist(circle)

    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 1.08)
    ax.set_yticks([])
    ax.set_xticks(np.linspace(0, 2 * np.pi, 8, endpoint=False))
    ax.set_xticklabels(["00:00", "03:00", "06:00", "09:00", "12:00", "15:00", "18:00", "21:00"], color="#dbeafe", fontsize=11)
    ax.grid(color="#24415f", alpha=0.45)
    ax.spines["polar"].set_color("#34506f")
    ax.spines["polar"].set_alpha(0.65)

    # Text overlay
    fig.text(
        0.5,
        0.935,
        "MELBOURNE BREATHES",
        ha="center",
        va="center",
        color="white",
        fontsize=34,
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.895,
        "Average citywide SCATS traffic intensity by 15-minute time bin, 2014–2026",
        ha="center",
        va="center",
        color="#a7bdd6",
        fontsize=14,
    )
    fig.text(
        0.5,
        0.49,
        time_label,
        ha="center",
        va="center",
        color="white",
        fontsize=48,
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.43,
        f"{current_value:,.0f} avg vehicle movements",
        ha="center",
        va="center",
        color="#dbeafe",
        fontsize=15,
    )
    fig.text(
        0.5,
        0.075,
        f"Quietest: {profile.loc[profile['avg_daily_volume'].idxmin(), 'time_bin']}  |  "
        f"Busiest: {profile.loc[profile['avg_daily_volume'].idxmax(), 'time_bin']}  |  "
        f"Mean: {mean_value:,.0f}",
        ha="center",
        va="center",
        color="#9fb4cc",
        fontsize=12,
    )

    # Keep fixed canvas dimensions.
    fig.subplots_adjust(left=0.08, right=0.92, top=0.84, bottom=0.11)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, facecolor=fig.get_facecolor())
    plt.close(fig)


def run_ffmpeg(frames_dir: Path, output_mp4: Path, fps: int, ffmpeg_bin: str) -> None:
    output_mp4.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg_bin,
        "-y",
        "-framerate", str(fps),
        "-i", str(frames_dir / "frame_%05d.png"),
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_mp4),
    ]

    print("Running ffmpeg:")
    print(" ".join(f'"{x}"' if " " in x else x for x in cmd))

    subprocess.run(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", default=str(DEFAULT_INPUT_CSV))
    parser.add_argument("--outdir", default=str(DEFAULT_OUTDIR))
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--loops", type=int, default=3, help="How many 24-hour loops to render")
    parser.add_argument("--width", type=int, default=2240, help="Output frame width in pixels. Must be even.")
    parser.add_argument("--height", type=int, default=1260, help="Output frame height in pixels. Must be even.")
    parser.add_argument("--dpi", type=int, default=140)
    parser.add_argument("--ffmpeg", default=None)
    parser.add_argument("--keep-frames", action="store_true")
    args = parser.parse_args()

    width = int(args.width)
    height = int(args.height)

    # Force even dimensions.
    if width % 2:
        width += 1
    if height % 2:
        height += 1

    input_csv = Path(args.input_csv)
    outdir = Path(args.outdir)
    frames_dir = outdir / "frames_time_bin_breathing"
    mp4 = outdir / "time_bin_breathing_animation.mp4"
    ffmpeg_bin = find_ffmpeg(args.ffmpeg)

    if frames_dir.exists() and not args.keep_frames:
        for p in frames_dir.glob("frame_*.png"):
            p.unlink()
    frames_dir.mkdir(parents=True, exist_ok=True)

    profile = load_time_bin_profile(input_csv)

    total_frames = len(profile) * int(args.loops)
    print(f"Rendering frames: {total_frames:,}")
    print(f"Frame size      : {width}x{height}")
    print(f"FPS             : {args.fps}")
    print(f"Output MP4      : {mp4}")

    for i in range(total_frames):
        if i % 24 == 0 or i == total_frames - 1:
            print(f"  frame {i + 1:,}/{total_frames:,}")
        render_frame(
            profile=profile,
            frame_idx=i,
            output_path=frames_dir / f"frame_{i:05d}.png",
            loops=args.loops,
            width_px=width,
            height_px=height,
            dpi=args.dpi,
        )

    run_ffmpeg(frames_dir, mp4, args.fps, ffmpeg_bin)
    print(f"Wrote: {mp4}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
