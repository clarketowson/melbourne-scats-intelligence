#!/usr/bin/env python3
r"""
generate_local_7day_pulse_animationV1.py

Local Python/ffmpeg renderer for the 7-day Melbourne SCATS pulse animation.

This bypasses Kepler.gl entirely.

Input:
  A:\TrafficAnalytics\PROJECTS\reports\deduped\kepler_animation_exports\kepler_city_pulse_7days_2024-05-13_to_2024-05-19.csv

Output:
  A:\TrafficAnalytics\PROJECTS\reports\deduped\animations\local_7day_pulse_animation.mp4
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


DEFAULT_INPUT = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\kepler_animation_exports\kepler_city_pulse_7days_2024-05-13_to_2024-05-19.csv"
DEFAULT_OUTDIR = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\animations"
DEFAULT_FFMPEG = r"E:\Program Files\ImageMagick-7.0.8-Q16\ffmpeg.EXE"

DAY_COLORS = {
    "Monday": "#16395f",
    "Tuesday": "#007bff",
    "Wednesday": "#0f766e",
    "Thursday": "#16a34a",
    "Friday": "#d97706",
    "Saturday": "#b00020",
    "Sunday": "#7c3aed",
}


def fmt_int(x) -> str:
    try:
        return f"{int(round(float(x))):,}"
    except Exception:
        return str(x)


def fmt_millions(x) -> str:
    return f"{float(x) / 1_000_000:.2f}M"


def detect_col(cols, candidates, label, required=True):
    lookup = {str(c).lower(): c for c in cols}
    for cand in candidates:
        if cand.lower() in lookup:
            return lookup[cand.lower()]
    if required:
        raise RuntimeError(f"Could not detect {label}. Columns: {list(cols)}")
    return None


def load_pulse_csv(path: Path) -> pd.DataFrame:
    print("=" * 90)
    print("LOCAL 7-DAY SCATS PULSE ANIMATION V1")
    print("=" * 90)
    print(f"Input CSV: {path}")

    if not path.exists():
        raise FileNotFoundError(f"Input CSV not found: {path}")

    df = pd.read_csv(path, low_memory=False)
    print(f"Loaded rows: {fmt_int(len(df))}")
    print(f"Columns: {list(df.columns)}")

    lat_col = detect_col(df.columns, ["latitude", "lat"], "latitude")
    lon_col = detect_col(df.columns, ["longitude", "lng", "lon"], "longitude")
    vol_col = detect_col(df.columns, ["volume", "volume_15m", "scaled_volume_0_100", "scaled_volume"], "volume")
    site_col = detect_col(df.columns, ["site_id", "scats_site", "site"], "site")
    name_col = detect_col(df.columns, ["site_name", "friendly_name", "name"], "site name", required=False)
    ts_col = detect_col(df.columns, ["timestamp", "animation_timestamp", "datetime", "date_time"], "timestamp")

    out = pd.DataFrame({
        "site_id": df[site_col].astype(str),
        "latitude": pd.to_numeric(df[lat_col], errors="coerce"),
        "longitude": pd.to_numeric(df[lon_col], errors="coerce"),
        "volume": pd.to_numeric(df[vol_col], errors="coerce").fillna(0),
        "timestamp": pd.to_datetime(df[ts_col], errors="coerce"),
    })

    if name_col:
        out["site_name"] = df[name_col].fillna("").astype(str)
    else:
        out["site_name"] = out["site_id"]

    out = out.dropna(subset=["latitude", "longitude", "timestamp"])
    out = out[
        (out["latitude"].between(-39.5, -36.0)) &
        (out["longitude"].between(143.0, 146.5))
    ].copy()

    out["day_name"] = out["timestamp"].dt.day_name()
    out["time_label"] = out["timestamp"].dt.strftime("%H:%M")
    out["date_label"] = out["timestamp"].dt.strftime("%Y-%m-%d")
    out["frame_key"] = out["timestamp"].dt.strftime("%Y-%m-%d %H:%M")

    print(f"Rows after cleaning: {fmt_int(len(out))}")
    print(f"Distinct sites     : {fmt_int(out['site_id'].nunique())}")
    print(f"Distinct frames    : {fmt_int(out['frame_key'].nunique())}")
    print(f"Total volume       : {fmt_int(out['volume'].sum())}")
    print("=" * 90)

    return out


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


def add_title(fig, title: str, subtitle: str):
    fig.suptitle(title, fontsize=26, fontweight="bold", color="#16395f", y=0.965)
    fig.text(0.5, 0.918, subtitle, ha="center", va="top", fontsize=12.5, color="#475569")


def render_frame(
    sub: pd.DataFrame,
    all_sites: pd.DataFrame,
    frame_idx: int,
    total_frames: int,
    out_path: Path,
    lon_min: float,
    lon_max: float,
    lat_min: float,
    lat_max: float,
    max_volume: float,
    weekly_total: float,
):
    day_name = sub["day_name"].iloc[0]
    date_label = sub["date_label"].iloc[0]
    time_label = sub["time_label"].iloc[0]
    frame_volume = sub["volume"].sum()
    active_sites = sub[sub["volume"] > 0]["site_id"].nunique()
    progress = frame_idx / max(total_frames - 1, 1)
    day_color = DAY_COLORS.get(day_name, "#007bff")

    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#f8fafc")
    fig.subplots_adjust(top=0.82, bottom=0.08, left=0.04, right=0.97)

    add_title(
        fig,
        "Melbourne 7-Day SCATS Traffic Pulse",
        "One frame per 15-minute bin. Point size and colour intensity reflect local SCATS traffic volume."
    )

    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)
    ax.grid(color="#94a3b8", alpha=0.16, linewidth=0.7)
    ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.scatter(
        all_sites["longitude"],
        all_sites["latitude"],
        s=8,
        color="#cbd5e1",
        alpha=0.28,
        linewidths=0,
        zorder=1,
    )

    scaled = np.clip(sub["volume"] / max_volume, 0, 1)
    sizes = 8 + (np.sqrt(scaled) * 95)
    alpha = 0.28 + scaled * 0.55

    ax.scatter(
        sub["longitude"],
        sub["latitude"],
        s=sizes * 2.7,
        c=sub["volume"],
        cmap="turbo",
        alpha=0.10,
        linewidths=0,
        zorder=2,
    )
    ax.scatter(
        sub["longitude"],
        sub["latitude"],
        s=sizes,
        c=sub["volume"],
        cmap="turbo",
        alpha=alpha,
        linewidths=0,
        zorder=3,
    )

    top = sub.sort_values("volume", ascending=False).head(40)
    top_scaled = np.clip(top["volume"] / max_volume, 0, 1)
    ax.scatter(
        top["longitude"],
        top["latitude"],
        s=(8 + np.sqrt(top_scaled) * 95) * 1.35,
        facecolors="none",
        edgecolors="#16395f",
        alpha=0.30,
        linewidths=0.8,
        zorder=4,
    )

    panel_text = (
        f"{day_name}\n"
        f"{date_label}  {time_label}\n\n"
        f"15-minute volume: {fmt_int(frame_volume)}\n"
        f"Active mapped sites: {fmt_int(active_sites)}\n"
        f"7-day total: {fmt_millions(weekly_total)}"
    )
    ax.text(
        0.045,
        0.88,
        panel_text,
        transform=ax.transAxes,
        fontsize=15,
        color="#111827",
        ha="left",
        va="top",
        linespacing=1.35,
        bbox=dict(boxstyle="round,pad=0.7", facecolor="#ffffff", edgecolor="#dbe3ef", alpha=0.96),
        zorder=5,
    )

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for i, d in enumerate(days):
        x = 0.18 + i * 0.095
        is_active = d == day_name
        ax.text(
            x,
            0.075,
            d[:3],
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=10,
            fontweight="bold",
            color="#ffffff" if is_active else "#64748b",
            bbox=dict(
                boxstyle="round,pad=0.35",
                facecolor=DAY_COLORS.get(d, "#64748b") if is_active else "#e2e8f0",
                edgecolor="none",
                alpha=0.98,
            ),
            zorder=6,
        )

    ax.add_patch(plt.Rectangle((0.05, 0.035), 0.90, 0.012, transform=ax.transAxes, color="#dbe3ef", lw=0, zorder=5))
    ax.add_patch(plt.Rectangle((0.05, 0.035), 0.90 * progress, 0.012, transform=ax.transAxes, color=day_color, lw=0, zorder=6))

    ax.text(
        0.955,
        0.055,
        f"Frame {frame_idx + 1:,} / {total_frames:,}",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=10,
        color="#475569",
        zorder=6,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render local 7-day SCATS pulse animation without Kepler.gl.")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--outdir", default=DEFAULT_OUTDIR)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--ffmpeg", default=DEFAULT_FFMPEG)
    parser.add_argument("--keep-frames", action="store_true")
    parser.add_argument("--max-frames", type=int, default=0, help="Debug limit. 0 = all frames.")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    frames_dir = outdir / "frames_local_7day_pulse"
    out_mp4 = outdir / "local_7day_pulse_animation.mp4"

    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)
    outdir.mkdir(parents=True, exist_ok=True)

    df = load_pulse_csv(Path(args.input))

    lon_min, lon_max = df["longitude"].min(), df["longitude"].max()
    lat_min, lat_max = df["latitude"].min(), df["latitude"].max()
    lon_pad = (lon_max - lon_min) * 0.07
    lat_pad = (lat_max - lat_min) * 0.10
    lon_min -= lon_pad
    lon_max += lon_pad
    lat_min -= lat_pad
    lat_max += lat_pad

    all_sites = df[["site_id", "longitude", "latitude"]].drop_duplicates("site_id")
    frame_keys = sorted(df["frame_key"].unique().tolist())
    if args.max_frames and args.max_frames > 0:
        frame_keys = frame_keys[:args.max_frames]

    total_frames = len(frame_keys)
    max_volume = max(1.0, float(df["volume"].quantile(0.995)))
    weekly_total = float(df["volume"].sum())

    print("")
    print("Rendering frames...")
    print(f"Frame count      : {fmt_int(total_frames)}")
    print(f"Max volume scale : {max_volume:,.0f}")
    print(f"Output frames    : {frames_dir}")
    print("")

    for idx, key in enumerate(frame_keys):
        sub = df[df["frame_key"].eq(key)].copy()
        render_frame(
            sub=sub,
            all_sites=all_sites,
            frame_idx=idx,
            total_frames=total_frames,
            out_path=frames_dir / f"frame_{idx:05d}.png",
            lon_min=lon_min,
            lon_max=lon_max,
            lat_min=lat_min,
            lat_max=lat_max,
            max_volume=max_volume,
            weekly_total=weekly_total,
        )

        if (idx + 1) % 25 == 0 or idx == total_frames - 1:
            print(f"Rendered frame {idx + 1:,}/{total_frames:,} ({key})")

    print("")
    print("Encoding MP4 with ffmpeg...")
    run_ffmpeg(frames_dir, out_mp4, args.fps, args.ffmpeg)

    if not args.keep_frames:
        shutil.rmtree(frames_dir, ignore_errors=True)

    print("")
    print("=" * 90)
    print("DONE")
    print("=" * 90)
    print(f"Wrote: {out_mp4}")
    print(f"Duration at {args.fps} fps: {total_frames / args.fps:.1f} seconds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
