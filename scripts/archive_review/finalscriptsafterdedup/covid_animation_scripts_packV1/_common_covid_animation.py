#!/usr/bin/env python3
r"""
_common_covid_animation.py

Shared helpers for COVID SCATS animation scripts.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


DEFAULT_COVID_CSV = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\kepler_animation_exports\kepler_covid_collapse_recovery_comparison_days.csv"
DEFAULT_OUTDIR = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\animations\covid"
DEFAULT_CHART_DIR = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\charts\covid_comparison_v2"
DEFAULT_FFMPEG = r"E:\Program Files\ImageMagick-7.0.8-Q16\ffmpeg.EXE"

PERIOD_ORDER = [
    "Pre-COVID baseline",
    "Lockdown / COVID shock",
    "Extended disruption",
    "Recovery phase",
    "Recent normal",
    "Busiest day detected",
]

PERIOD_SHORT = {
    "Pre-COVID baseline": "2019 baseline",
    "Lockdown / COVID shock": "2020 lockdown",
    "Extended disruption": "2021 disruption",
    "Recovery phase": "2022 recovery",
    "Recent normal": "2024 normal",
    "Busiest day detected": "2025 busiest",
}

PERIOD_COLORS = {
    "Pre-COVID baseline": "#16395f",
    "Lockdown / COVID shock": "#b00020",
    "Extended disruption": "#d97706",
    "Recovery phase": "#007bff",
    "Recent normal": "#0f766e",
    "Busiest day detected": "#16a34a",
}


def fmt_int(x):
    try:
        return f"{int(round(float(x))):,}"
    except Exception:
        return str(x)


def fmt_millions(x):
    return f"{float(x) / 1_000_000:.1f}M"


def ensure_clean_dir(path: Path):
    import shutil
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def run_ffmpeg(frames_dir: Path, out_mp4: Path, fps: int = 24, ffmpeg_path: str = DEFAULT_FFMPEG):
    ffmpeg = ffmpeg_path if Path(ffmpeg_path).exists() else "ffmpeg"
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
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


def add_music(video: Path, music: Path, output: Path, ffmpeg_path: str = DEFAULT_FFMPEG):
    ffmpeg = ffmpeg_path if Path(ffmpeg_path).exists() else "ffmpeg"
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg, "-y",
        "-i", str(video),
        "-i", str(music),
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "slow",
        "-c:a", "aac",
        "-b:a", "320k",
        "-shortest",
        str(output),
    ]
    subprocess.run(cmd, check=True)


def load_covid_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"COVID CSV not found: {path}")
    df = pd.read_csv(path, low_memory=False)
    df["comparison_period"] = df["comparison_period"].astype(str)
    df["site_id"] = df["site_id"].astype(str)
    df["site_name"] = df["site_name"].fillna("").astype(str)
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    df["hour"] = pd.to_numeric(df["hour"], errors="coerce").fillna(0).astype(int)
    df["minute"] = pd.to_numeric(df["minute"], errors="coerce").fillna(0).astype(int)
    df["time_minutes"] = df["hour"] * 60 + df["minute"]
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"]).copy()
    return df


def title_block(fig, title, subtitle=None):
    fig.suptitle(title, fontsize=26, fontweight="bold", color="#16395f", y=0.965)
    if subtitle:
        fig.text(0.5, 0.918, subtitle, ha="center", va="top", fontsize=12.5, color="#475569")


def order_periods(items):
    return [p for p in PERIOD_ORDER if p in set(items)] + [p for p in items if p not in PERIOD_ORDER]
