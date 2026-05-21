#!/usr/bin/env python3
"""
generate_all_scats_sites_animationV1.py

Creates a cinematic "All SCATS Sites" animation from the mapped SCATS site metadata.

Input:
  A:\TrafficAnalytics\PROJECTS\reports\deduped\all_scats_sites_map_data_audit.csv

Output:
  A:\TrafficAnalytics\PROJECTS\reports\deduped\animations\all_scats_sites_animation.mp4

This is a full-network reveal animation:
  - all mapped SCATS sites appear across Melbourne
  - sites are colour/size coded by available traffic heat / volume fields when present
  - ffmpeg assembles PNG frames into MP4
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


DEFAULT_INPUT = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\all_scats_sites_map_data_audit.csv"
DEFAULT_OUTDIR = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\animations"
DEFAULT_FFMPEG = r"E:\Program Files\ImageMagick-7.0.8-Q16\ffmpeg.EXE"


def detect_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    cols = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in cols:
            return cols[c.lower()]
    return None


def clean_sites(df: pd.DataFrame) -> pd.DataFrame:
    site_col = detect_col(df, ["site_id", "scats_site", "nb_scats_site", "site"])
    lat_col = detect_col(df, ["latitude", "lat"])
    lon_col = detect_col(df, ["longitude", "lng", "lon"])
    name_col = detect_col(df, ["friendly_name", "site_name", "name", "location", "description"])
    volume_col = detect_col(df, ["total", "total_volume", "site_total_volume", "volume", "total_millions", "ooh_total_12yr_movements"])

    if not site_col or not lat_col or not lon_col:
        raise SystemExit(f"Could not detect site/latitude/longitude columns. Columns: {list(df.columns)}")

    out = pd.DataFrame({
        "site_id": df[site_col].astype(str).str.strip(),
        "latitude": pd.to_numeric(df[lat_col], errors="coerce"),
        "longitude": pd.to_numeric(df[lon_col], errors="coerce"),
    })

    out["site_name"] = df[name_col].fillna("").astype(str) if name_col else out["site_id"]

    if volume_col:
        out["volume"] = pd.to_numeric(df[volume_col], errors="coerce")
        if volume_col.lower() == "total_millions":
            out["volume"] = out["volume"] * 1_000_000
    else:
        out["volume"] = 1.0

    out = out.dropna(subset=["latitude", "longitude"])
    out = out[
        (out["latitude"].between(-39.5, -36.0)) &
        (out["longitude"].between(143.0, 146.5))
    ].copy()

    out = out.drop_duplicates(subset=["site_id"], keep="first")
    out["volume"] = out["volume"].fillna(out["volume"].median() if out["volume"].notna().any() else 1.0)
    out["rank"] = out["volume"].rank(ascending=False, method="first").astype(int)
    out = out.sort_values("rank").reset_index(drop=True)

    # Visual scaling
    v = out["volume"].to_numpy(dtype=float)
    if np.nanmax(v) > np.nanmin(v):
        scaled = (np.log1p(v) - np.log1p(np.nanmin(v))) / (np.log1p(np.nanmax(v)) - np.log1p(np.nanmin(v)))
    else:
        scaled = np.ones(len(out)) * 0.5
    out["size"] = 8 + scaled * 42
    out["alpha"] = 0.35 + scaled * 0.55

    return out


def frame_plot(sites: pd.DataFrame, frame_idx: int, total_frames: int, out_path: Path, dpi: int = 140):
    # Reveal progress: ease-in-out
    t = frame_idx / max(total_frames - 1, 1)
    ease = 0.5 - 0.5 * math.cos(math.pi * t)

    # Reveal all sites progressively, then pulse the full network near the end
    n = len(sites)
    reveal_count = int(max(1, min(n, ease * n * 1.08)))
    visible = sites.iloc[:reveal_count].copy()

    # Pulse after 70%
    pulse = 1.0
    if t > 0.70:
        pulse = 1.0 + 0.20 * math.sin((t - 0.70) / 0.30 * math.pi * 6)

    fig = plt.figure(figsize=(16, 9), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor("#07111f")
    fig.patch.set_facecolor("#07111f")

    # Melbourne-ish bounds from actual data with padding
    lon_min, lon_max = sites["longitude"].min(), sites["longitude"].max()
    lat_min, lat_max = sites["latitude"].min(), sites["latitude"].max()
    lon_pad = (lon_max - lon_min) * 0.07
    lat_pad = (lat_max - lat_min) * 0.10
    ax.set_xlim(lon_min - lon_pad, lon_max + lon_pad)
    ax.set_ylim(lat_min - lat_pad, lat_max + lat_pad)

    # subtle grid
    ax.grid(color="white", alpha=0.06, linewidth=0.7)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)

    if len(visible):
        c = visible["volume"].to_numpy()
        ax.scatter(
            visible["longitude"],
            visible["latitude"],
            s=visible["size"] * pulse,
            c=c,
            cmap="turbo",
            alpha=visible["alpha"],
            linewidths=0,
        )
        # bright top sites overlay
        top_visible = visible.head(min(100, len(visible)))
        ax.scatter(
            top_visible["longitude"],
            top_visible["latitude"],
            s=top_visible["size"] * 1.4 * pulse,
            facecolors="none",
            edgecolors="white",
            alpha=0.35,
            linewidths=0.8,
        )

    title = "All Melbourne SCATS Sites"
    subtitle = f"{reveal_count:,} of {n:,} mapped SCATS sites revealed"
    if t > 0.82:
        subtitle = f"Full mapped SCATS network: {n:,} sites"

    ax.text(
        0.045, 0.925, title,
        transform=ax.transAxes,
        color="white",
        fontsize=30,
        fontweight="bold",
        ha="left",
        va="top",
    )
    ax.text(
        0.047, 0.865, subtitle,
        transform=ax.transAxes,
        color="#dbeafe",
        fontsize=15,
        ha="left",
        va="top",
    )
    ax.text(
        0.047, 0.815,
        "Independent city-scale traffic intelligence from cleaned SCATS data",
        transform=ax.transAxes,
        color="#93c5fd",
        fontsize=12,
        ha="left",
        va="top",
    )

    # progress bar
    ax.add_patch(plt.Rectangle((0.045, 0.055), 0.91, 0.012, transform=ax.transAxes, color="white", alpha=0.12, lw=0))
    ax.add_patch(plt.Rectangle((0.045, 0.055), 0.91 * t, 0.012, transform=ax.transAxes, color="#38bdf8", alpha=0.95, lw=0))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0)
    plt.close(fig)


def run_ffmpeg(frames_dir: Path, out_mp4: Path, fps: int, ffmpeg_path: str):
    ffmpeg = ffmpeg_path if Path(ffmpeg_path).exists() else "ffmpeg"
    cmd = [
        ffmpeg, "-y",
        "-framerate", str(fps),
        "-i", str(frames_dir / "frame_%05d.png"),
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "slow",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(out_mp4),
    ]
    subprocess.run(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--outdir", default=DEFAULT_OUTDIR)
    parser.add_argument("--frames", type=int, default=240)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--ffmpeg", default=DEFAULT_FFMPEG)
    parser.add_argument("--keep-frames", action="store_true")
    args = parser.parse_args()

    input_path = Path(args.input)
    outdir = Path(args.outdir)
    frames_dir = outdir / "frames_all_scats_sites"
    out_mp4 = outdir / "all_scats_sites_animation.mp4"

    print("=" * 90)
    print("ALL SCATS SITES CINEMATIC ANIMATION V1")
    print("=" * 90)
    print(f"Input     : {input_path}")
    print(f"Output    : {out_mp4}")
    print(f"Frames    : {args.frames}")
    print(f"FPS       : {args.fps}")
    print("=" * 90)

    if not input_path.exists():
        raise SystemExit(f"Input not found: {input_path}")

    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)
    outdir.mkdir(parents=True, exist_ok=True)

    raw = pd.read_csv(input_path, low_memory=False)
    sites = clean_sites(raw)

    print(f"Mapped sites detected: {len(sites):,}")
    print("Rendering frames...")

    for i in range(args.frames):
        frame_plot(sites, i, args.frames, frames_dir / f"frame_{i:05d}.png")
        if (i + 1) % 25 == 0 or i == args.frames - 1:
            print(f"  frame {i + 1:,}/{args.frames:,}")

    print("Encoding MP4...")
    run_ffmpeg(frames_dir, out_mp4, args.fps, args.ffmpeg)

    if not args.keep_frames:
        shutil.rmtree(frames_dir, ignore_errors=True)

    print(f"Wrote: {out_mp4}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
