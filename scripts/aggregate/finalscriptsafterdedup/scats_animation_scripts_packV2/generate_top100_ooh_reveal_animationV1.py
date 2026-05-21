#!/usr/bin/env python3
r"""
generate_top100_ooh_reveal_animationV1.py

Creates a Top 100 SCATS / OOH opportunity reveal animation from top100_scats_ooh_map.json.
This is a static map-style scatter reveal, not a basemap render.
"""
from __future__ import annotations

import argparse, json, subprocess, shutil
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

DEFAULT_BASE = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")


def flatten_item(item):
    traffic = item.get("traffic", {}) if isinstance(item.get("traffic"), dict) else {}
    return {
        "site_id": item.get("site_id"),
        "name": item.get("name"),
        "lat": item.get("lat"),
        "lng": item.get("lng"),
        "total": traffic.get("total_12yr", item.get("total", item.get("total_millions", 0))),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(DEFAULT_BASE / "top100_scats_ooh_map.json"))
    ap.add_argument("--outdir", default=str(DEFAULT_BASE / "animations"))
    ap.add_argument("--fps", type=int, default=12)
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--keep-frames", action="store_true")
    args = ap.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    df = pd.DataFrame([flatten_item(x) for x in data])
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lng"] = pd.to_numeric(df["lng"], errors="coerce")
    df["total"] = pd.to_numeric(df["total"], errors="coerce")
    df = df.dropna(subset=["lat", "lng", "total"]).sort_values("total", ascending=False).reset_index(drop=True)
    df["rank"] = range(1, len(df)+1)
    df["size"] = 80 + (df["total"] / df["total"].max()) * 900

    outdir = Path(args.outdir); frames = outdir / "frames_top100_ooh"
    outdir.mkdir(parents=True, exist_ok=True); frames.mkdir(parents=True, exist_ok=True)

    pad_lng = (df["lng"].max() - df["lng"].min()) * 0.08
    pad_lat = (df["lat"].max() - df["lat"].min()) * 0.08
    xlim = (df["lng"].min()-pad_lng, df["lng"].max()+pad_lng)
    ylim = (df["lat"].min()-pad_lat, df["lat"].max()+pad_lat)

    for i in range(1, len(df)+1):
        sub = df.iloc[:i]
        cur = df.iloc[i-1]
        fig, ax = plt.subplots(figsize=(16,9))
        ax.scatter(df["lng"], df["lat"], s=25, alpha=0.10)
        ax.scatter(sub["lng"], sub["lat"], s=sub["size"], alpha=0.68)
        ax.scatter([cur["lng"]], [cur["lat"]], s=cur["size"]*1.35, alpha=0.95, edgecolors="black", linewidths=1.0)
        ax.set_xlim(*xlim); ax.set_ylim(*ylim)
        ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
        ax.grid(alpha=0.20)
        ax.set_title("Top 100 Melbourne SCATS / OOH Opportunity Reveal", fontsize=23, fontweight="bold", pad=16)
        ax.text(0.02, 0.92, f"#{int(cur['rank'])} {cur['name']}", transform=ax.transAxes, fontsize=17, fontweight="bold")
        ax.text(0.02, 0.86, f"12-year traffic: {cur['total']/1e6:.1f}M movements", transform=ax.transAxes, fontsize=14)
        ax.text(0.02, 0.80, f"Sites revealed: {i}/{len(df)}", transform=ax.transAxes, fontsize=14)
        fig.tight_layout()
        fig.savefig(frames / f"frame_{i-1:05d}.png", dpi=args.dpi)
        plt.close(fig)

    mp4 = outdir / "top100_ooh_reveal_animation.mp4"
    subprocess.run(["ffmpeg", "-y", "-framerate", str(args.fps), "-i", str(frames / "frame_%05d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(mp4)], check=True)
    print(f"Wrote: {mp4}")
    if not args.keep_frames: shutil.rmtree(frames, ignore_errors=True)

if __name__ == "__main__":
    main()
