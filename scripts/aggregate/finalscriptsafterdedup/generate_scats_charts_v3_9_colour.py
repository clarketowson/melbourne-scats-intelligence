#!/usr/bin/env python3
"""
generate_scats_charts_v3_9_colour.py

CSV-only chart generator for the Melbourne SCATS unified reporting workflow.
It reads completed V3 CSV outputs and writes publication-ready PNG charts plus
CSV summaries and a chart_manifest.json file.

V3.9 colour improvements:
  - Extends traffic-light semantic colour coding across the chart pack.
  - Uses green/amber/red heat scales so low/clearer traffic reads green, medium traffic amber, and busiest/heaviest traffic red.
  - Applies heat colouring to monthly, yearly, seasonality, time-bin, busiest-day, weekday, site, and trend charts while preserving existing data-gap handling and SCATS site overrides.

V3.8 improvements:
  - Hard-codes verified SCATS site-name overrides for Site 2816 and Site 3376 after lookup merge.
  - Keeps the V3.7 heat-coded Top 20 busiest SCATS sites chart.

V3.7 improvements:
  - Improves merged SCATS site-name lookup quality by preferring non-blank, longer descriptive names over blank/short duplicate rows.
  - Adds row-level fallback name extraction from the Excel site listing, so sites missed by the selected name column can still be labelled.
  - Colour-codes the Top 20 busiest SCATS sites chart using a heat scale: busiest sites are hotter/redder, lower-ranked sites are lighter.

V3.6 improvements:
  - Fixes Excel lookup parsing when duplicate/ambiguous column headers make pandas return a DataFrame instead of a Series.
  - Makes generated headers unique and reports selected sheet/table diagnostics more clearly.

V3.5 improvements:
  - Robustly scans all sheets in SCATSSiteListingSpreadsheet.xls / .xlsx instead of reading only the first sheet.
  - Detects the real SCATS site table by valid site-ID count, so the 4,525-row listing is selected over the 27-row caution sheet.
  - Builds a standardized lookup from site ID, readable site name, and optional lat/long coordinates, with clear diagnostics.

V3.4 improvements:
  - Integrates a second SCATS site listing spreadsheet as a fallback lookup source.
  - Merges multiple site lookup files so missing names are filled without losing coordinates.
  - Improves Top 20 SCATS site readability with names, integer IDs, and lookup-source reporting.

V3.3 improvements:
  - Integrates optional SCATS site lookup CSV with site names and coordinates.
  - Labels Top 20 sites using readable names plus integer SCATS IDs.
  - Writes a named Top 20 site summary CSV including latitude/longitude when available.
  - Improves the busiest-site monthly trend title using the site name when available.

V3.2 improvements:
  - Forces SCATS site IDs to integer-only string labels with no decimals.
  - Improves Top 20 SCATS Sites bar labels and x-axis readability.

V3.1 improvements:
  - Fixes horizontal bar chart axes so category labels are never formatted as millions.
  - Makes Top 20 SCATS Sites x-axis meaningful with million-unit ticks and end labels.

V3 improvements:
  - Keeps the V2 2018-12 broken-line data-gap handling and annotation.
  - Applies a semantic, publication-friendly colour scheme so charts are easier
    to scan and do not all appear as default matplotlib blue.
  - Uses consistent colours for total traffic, rolling averages, growth,
    disruption, AM peak, PM peak, off-peak, seasonality, rankings, and quiet periods.

Default input directory:
  A:\\TrafficAnalytics\\PROJECTS\\reports\\deduped

Default output directory:
  A:\\TrafficAnalytics\\PROJECTS\\reports\\deduped\\charts
"""

from __future__ import annotations

import argparse
import json
import re
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.collections import LineCollection
import pandas as pd
import numpy as np


DEFAULT_INPUT_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")
DEFAULT_OUTPUT_DIR = DEFAULT_INPUT_DIR / "charts"

CSV_CANDIDATES = {
    "monthly_totals": ["monthly_totals.csv", "chunked_total_cleaned_volume_monthly.csv"],
    "total_cleaned_volume": ["chunked_total_cleaned_volume_monthly.csv", "monthly_totals.csv"],
    "busiest_day_monthly": ["chunked_busiest_day_monthly.csv"],
    "busiest_site_monthly": ["chunked_busiest_site_monthly.csv"],
    "busiest_time_bin_monthly": ["chunked_busiest_time_bin_monthly.csv"],
    "peak_shares_monthly": ["chunked_peak_shares_monthly.csv"],
    "headline_metrics": ["headline_metrics.csv"],
    "distinct_sites": ["distinct_sites.csv"],
    "site_lookup": [
        "busiestSCATSsitesCOORDINATES.csv",
        "busiestSCATSsitesCOORDINATES(1).csv",
        "scats_sites_coordinates.csv",
        "victorian_traffic_signals.csv",
        "SCATSSiteListingSpreadsheet.xls",
        "SCATSSiteListingSpreadsheet.xlsx",
    ],
}

MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
KNOWN_DATA_GAP_MONTHS = {"2018-12"}


# Semantic chart palette. Keep these stable so colours have consistent meaning
# across the public-facing chart set.
PALETTE = {
    "traffic": "#1f4e79",
    "traffic_light": "#5b9bd5",
    "rolling": "#f28e2b",
    "growth_pos": "#2ca02c",
    "growth_neg": "#d62728",
    "disruption": "#c44e52",
    "am_peak": "#7b5fc9",
    "pm_peak": "#17a2a8",
    "off_peak": "#9aa0a6",
    "seasonality": "#d4a017",
    "ranking": "#4e79a7",
    "quiet": "#9e9e9e",
    "processing": "#6f4e7c",
    "gap": "#555555",
}


# Traffic-light colour logic used by V3.9.
# Low/light traffic = green, middle = amber, heavy/busy = red.
TRAFFIC_CMAP = plt.cm.RdYlGn_r
QUIET_CMAP = plt.cm.Greens

def heat_colours(values, cmap=TRAFFIC_CMAP):
    arr = pd.to_numeric(pd.Series(values), errors="coerce").astype(float)
    valid = arr.dropna()
    if valid.empty or float(valid.max()) == float(valid.min()):
        return [PALETTE["traffic"] for _ in arr]
    norm = Normalize(vmin=float(valid.min()), vmax=float(valid.max()))
    return [cmap(norm(v)) if pd.notna(v) else "#cccccc" for v in arr]

def plot_heat_line(ax, x_values, y_values, cmap=TRAFFIC_CMAP, linewidth=2.5, label=None, fallback_colour=None):
    x = pd.to_datetime(pd.Series(x_values), errors="coerce")
    y = pd.to_numeric(pd.Series(y_values), errors="coerce")
    mask = x.notna() & y.notna()
    x = x[mask]
    y = y[mask]
    if len(x) < 2:
        ax.plot(x, y, linewidth=linewidth, color=fallback_colour or PALETTE["traffic"], label=label)
        return
    x_num = plt.matplotlib.dates.date2num(x.dt.to_pydatetime())
    points = np.array([x_num, y.to_numpy(dtype=float)]).T.reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)
    seg_values = (y.to_numpy(dtype=float)[:-1] + y.to_numpy(dtype=float)[1:]) / 2.0
    norm = Normalize(vmin=float(np.nanmin(seg_values)), vmax=float(np.nanmax(seg_values)))
    lc = LineCollection(segments, cmap=cmap, norm=norm, linewidth=linewidth)
    lc.set_array(seg_values)
    ax.add_collection(lc)
    ax.autoscale_view()
    if label:
        ax.plot([], [], color=fallback_colour or PALETTE["traffic"], linewidth=linewidth, label=label)

def plot_heat_line_categories(ax, labels, y_values, cmap=TRAFFIC_CMAP, linewidth=2.5):
    y = pd.to_numeric(pd.Series(y_values), errors="coerce")
    x_num = np.arange(len(y))
    mask = y.notna()
    if mask.sum() < 2:
        ax.plot(x_num[mask], y[mask], linewidth=linewidth, color=PALETTE["traffic"])
        return
    points = np.array([x_num[mask], y[mask].to_numpy(dtype=float)]).T.reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)
    seg_values = (y[mask].to_numpy(dtype=float)[:-1] + y[mask].to_numpy(dtype=float)[1:]) / 2.0
    norm = Normalize(vmin=float(np.nanmin(seg_values)), vmax=float(np.nanmax(seg_values)))
    lc = LineCollection(segments, cmap=cmap, norm=norm, linewidth=linewidth)
    lc.set_array(seg_values)
    ax.add_collection(lc)
    ax.autoscale_view()

def add_heat_note(ax, text="Traffic-light colour scale: green = lighter/clearer, amber = medium, red = busiest/heaviest."):
    ax.text(0.01, 0.965, text, transform=ax.transAxes, fontsize=8, va="top", ha="left", alpha=0.72)


# Verified manual overrides for known important sites missing or blank in source lookup files.
# Keep IDs as strings so they never become floats such as 2816.0.
SITE_NAME_OVERRIDES = {
    "2816": "DIAMOND CREEK RD/GREENSBOROUGH HWY/CIVIC",
    "3376": "HODDLE NR STUDLEY (NORTHBOUND)",
}


def read_table_if_exists(path: Path) -> Optional[pd.DataFrame]:
    """General-purpose reader for completed CSV outputs.

    Site lookup spreadsheets are handled separately by read_site_lookup_source()
    because official SCATS XLS files can contain a small caution sheet before
    the real 4,000+ row site table.
    """
    if not path.exists():
        return None
    try:
        suffix = path.suffix.lower()
        if suffix in {".xls", ".xlsx", ".xlsm"}:
            return pd.read_excel(path)
        return pd.read_csv(path)
    except Exception as exc:
        print(f"WARNING: could not read {path}: {exc}")
        return None


def _clean_header_value(value) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def _looks_like_site_id(value) -> bool:
    site = format_site_id(value)
    if site is None or not re.fullmatch(r"\d+", site):
        return False
    try:
        n = int(site)
    except Exception:
        return False
    return 1 <= n <= 99999


def _looks_like_lat(value) -> bool:
    try:
        x = float(value)
    except Exception:
        return False
    return -45.5 <= x <= -30.0


def _looks_like_lon(value) -> bool:
    try:
        x = float(value)
    except Exception:
        return False
    return 140.0 <= x <= 150.5


def _best_string_name_column(df: pd.DataFrame, exclude_cols: set) -> Optional[object]:
    best_col = None
    best_score = -1
    for col in df.columns:
        if col in exclude_cols:
            continue
        s = df[col].dropna().astype(str).str.strip()
        if s.empty:
            continue
        s = s[~s.str.lower().isin(["", "nan", "none", "null"])]
        if s.empty:
            continue
        avg_len = s.str.len().mean()
        alpha_rate = s.str.contains(r"[A-Za-z]", regex=True).mean()
        numeric_like_rate = s.str.fullmatch(r"[-+]?\d+(\.\d+)?").fillna(False).mean()
        score = len(s) * max(alpha_rate, 0) + min(avg_len, 40) * 2 - numeric_like_rate * len(s)
        if avg_len >= 3 and alpha_rate > 0.4 and score > best_score:
            best_score = score
            best_col = col
    return best_col




def _clean_lookup_name_value(value) -> Optional[str]:
    """Return a readable lookup name candidate, or None for blanks/noise."""
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "n/a"}:
        return None
    if re.fullmatch(r"[-+]?\d+(\.\d+)?", text):
        return None
    if not re.search(r"[A-Za-z]", text):
        return None
    low = text.lower()
    noisy = {"scats", "site number", "site no", "latitude", "longitude", "information", "copyright"}
    if low in noisy:
        return None
    return re.sub(r"\s+", " ", text)


def _best_row_name(row: pd.Series, excluded_cols: set) -> Optional[str]:
    """Choose the best descriptive text from a site-listing row."""
    candidates: List[str] = []
    for col, value in row.items():
        if col in excluded_cols:
            continue
        cleaned = _clean_lookup_name_value(value)
        if cleaned:
            candidates.append(cleaned)
    if not candidates:
        return None
    def score(s: str) -> Tuple[int, int, int]:
        roadish = int(any(token in s.upper() for token in ["/", " NR ", " FWY", " HWY", " RD", " ST", " AVE", " CRES", " DR", " PDE"]))
        alpha_count = sum(ch.isalpha() for ch in s)
        return (roadish, min(len(s), 80), alpha_count)
    return max(candidates, key=score)

def _make_unique_headers(values: Iterable[object]) -> List[str]:
    """Return cleaned, unique headers so pandas never returns duplicate-column DataFrames."""
    seen: Dict[str, int] = {}
    headers: List[str] = []
    for i, value in enumerate(values):
        base = _clean_header_value(value) or f"col_{i}"
        count = seen.get(base, 0)
        seen[base] = count + 1
        headers.append(base if count == 0 else f"{base}_{count + 1}")
    return headers


def _series(df: pd.DataFrame, col: object) -> pd.Series:
    """Return one Series even when duplicate labels accidentally produce a DataFrame."""
    value = df[col]
    if isinstance(value, pd.DataFrame):
        return value.iloc[:, 0]
    return value


def _score_col(df: pd.DataFrame, col: object, fn) -> int:
    try:
        return int(_series(df, col).map(fn).sum())
    except Exception:
        return 0


def _candidate_from_table(raw: pd.DataFrame, source_name: str, sheet_name: str, header_row: Optional[int]) -> Optional[pd.DataFrame]:
    """Build a standardized site lookup candidate from a raw sheet/table."""
    if raw is None or raw.empty:
        return None

    if header_row is not None:
        headers = _make_unique_headers(raw.iloc[header_row].tolist())
        work = raw.iloc[header_row + 1:].copy()
        work.columns = headers
        columns = list(work.columns)
        lower_to_col: Dict[str, object] = {}
        for c in columns:
            lower_to_col.setdefault(str(c).lower(), c)

        site_col = None
        for candidate in [
            "scats_site", "scats_site_id", "scats_id", "scats_number",
            "site", "site_id", "site_no", "site_number", "siteid", "id",
        ]:
            if candidate in lower_to_col:
                site_col = lower_to_col[candidate]
                break
        if site_col is None and columns:
            site_col = max(columns, key=lambda c: _score_col(work, c, _looks_like_site_id))

        name_col = None
        for candidate in [
            "site_name", "site_description", "description", "location", "location_description", "location_name",
            "intersection", "intersection_name", "name", "road_name", "site_location",
            "site_desc", "description_name",
        ]:
            if candidate in lower_to_col:
                name_col = lower_to_col[candidate]
                break
        if name_col is None:
            name_col = _best_string_name_column(work, {site_col})

        lat_col = None
        lon_col = None
        for c in columns:
            lc = str(c).lower()
            if lat_col is None and lc in {"lat", "latitude", "y", "y_coord", "y_coordinate"}:
                lat_col = c
            if lon_col is None and lc in {"lon", "long", "lng", "longitude", "x", "x_coord", "x_coordinate"}:
                lon_col = c
        if lat_col is None and columns:
            lat_col = max(columns, key=lambda c: _score_col(work, c, _looks_like_lat))
            if _score_col(work, lat_col, _looks_like_lat) < 10:
                lat_col = None
        if lon_col is None and columns:
            lon_col = max(columns, key=lambda c: _score_col(work, c, _looks_like_lon))
            if _score_col(work, lon_col, _looks_like_lon) < 10:
                lon_col = None
    else:
        work = raw.copy()
        columns = list(work.columns)
        if not columns:
            return None
        site_col = max(columns, key=lambda c: _score_col(work, c, _looks_like_site_id))
        name_col = _best_string_name_column(work, {site_col})
        lat_col = max(columns, key=lambda c: _score_col(work, c, _looks_like_lat))
        if _score_col(work, lat_col, _looks_like_lat) < 10:
            lat_col = None
        lon_col = max(columns, key=lambda c: _score_col(work, c, _looks_like_lon))
        if _score_col(work, lon_col, _looks_like_lon) < 10:
            lon_col = None

    site_count = _score_col(work, site_col, _looks_like_site_id) if site_col is not None else 0
    if site_col is None or site_count < 20:
        return None

    site_series = _series(work, site_col)
    out = pd.DataFrame(index=work.index)
    out["site"] = site_series.map(format_site_id)
    out = out[out["site"].map(lambda x: isinstance(x, str) and re.fullmatch(r"\d+", x) is not None)].copy()
    if out.empty:
        return None

    excluded_for_name = {c for c in [site_col, lat_col, lon_col] if c is not None}
    row_best_names = work.reindex(out.index).apply(lambda row: _best_row_name(row, excluded_for_name), axis=1)

    if name_col is not None:
        name_series = _series(work, name_col).reindex(out.index)
        selected_names = name_series.map(_clean_lookup_name_value)
    else:
        selected_names = pd.Series(index=out.index, dtype=object)

    out["site_name"] = selected_names
    needs_fallback = out["site_name"].isna() | (out["site_name"].astype(str).str.len() < 4)
    out.loc[needs_fallback, "site_name"] = row_best_names.loc[needs_fallback]
    out.loc[out["site_name"].astype(str).str.lower().isin(["", "nan", "none", "null"]), "site_name"] = np.nan

    out["latitude"] = pd.to_numeric(_series(work, lat_col).reindex(out.index), errors="coerce") if lat_col is not None else np.nan
    out["longitude"] = pd.to_numeric(_series(work, lon_col).reindex(out.index), errors="coerce") if lon_col is not None else np.nan
    out["__lookup_source"] = source_name
    out["__sheet_name"] = sheet_name
    out["__detected_header_row"] = -1 if header_row is None else header_row
    out["__valid_site_rows"] = len(out)
    return out[["site", "site_name", "latitude", "longitude", "__lookup_source", "__sheet_name", "__detected_header_row", "__valid_site_rows"]]

def _excel_site_lookup_candidates(path: Path) -> List[pd.DataFrame]:
    """Read every sheet and return standardized site-table candidates."""
    candidates: List[pd.DataFrame] = []
    try:
        sheets = pd.read_excel(path, sheet_name=None, header=None, dtype=object)
    except Exception as exc:
        print(f"WARNING: could not scan all sheets in {path.name}: {exc}")
        return candidates

    for sheet_name, raw in sheets.items():
        if raw is None or raw.empty:
            continue
        raw = raw.dropna(how="all").dropna(axis=1, how="all")
        if raw.empty:
            continue

        sheet_candidates: List[pd.DataFrame] = []
        for header_row in range(min(40, len(raw))):
            row_text = " ".join(str(x).lower() for x in raw.iloc[header_row].dropna().tolist())
            if any(term in row_text for term in ["scats", "site", "location", "description", "intersection", "latitude", "longitude"]):
                cand = _candidate_from_table(raw, path.name, str(sheet_name), header_row)
                if cand is not None:
                    sheet_candidates.append(cand)

        cand = _candidate_from_table(raw, path.name, str(sheet_name), None)
        if cand is not None:
            sheet_candidates.append(cand)

        if sheet_candidates:
            best = max(sheet_candidates, key=len)
            candidates.append(best)
            print(
                f"  Excel sheet candidate: {path.name} / {sheet_name!r} -> "
                f"{len(best):,} valid site rows "
                f"(header row {int(best['__detected_header_row'].iloc[0])})"
            )
        else:
            print(f"  Excel sheet skipped: {path.name} / {sheet_name!r} -> no valid SCATS site table detected")
    return candidates


def read_site_lookup_source(path: Path) -> Optional[pd.DataFrame]:
    """Special reader for SCATS site lookup sources.

    CSV files are read normally. Excel files are scanned sheet-by-sheet, and the
    largest valid SCATS site table is returned. This avoids accidentally using
    the 27-row caution/instructions sheet.
    """
    if not path.exists():
        return None
    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            df = pd.read_csv(path)
            df = df.copy()
            df["__lookup_source"] = path.name
            return df
        if suffix in {".xls", ".xlsx", ".xlsm"}:
            candidates = _excel_site_lookup_candidates(path)
            if not candidates:
                return None
            best = max(candidates, key=len).copy()
            print(f"  Selected Excel site table from {path.name}: {len(best):,} valid site rows")
            return best
        return None
    except Exception as exc:
        print(f"WARNING: could not read site lookup {path}: {exc}")
        return None


def find_table(input_dir: Path, candidates: Iterable[str]) -> Optional[Path]:
    for name in candidates:
        path = input_dir / name
        if path.exists():
            return path
    for name in candidates:
        stem = Path(name).stem
        matches = []
        for ext in (".csv", ".xls", ".xlsx", ".xlsm"):
            matches.extend(input_dir.glob(f"{stem}*{ext}"))
        if matches:
            return sorted(matches)[0]
    return None


def find_all_site_lookup_tables(input_dir: Path) -> List[Path]:
    seen = set()
    paths: List[Path] = []
    for name in CSV_CANDIDATES["site_lookup"]:
        path = input_dir / name
        if path.exists() and path not in seen:
            paths.append(path)
            seen.add(path)
        stem = Path(name).stem
        for ext in (".csv", ".xls", ".xlsx", ".xlsm"):
            for match in sorted(input_dir.glob(f"{stem}*{ext}")):
                if match not in seen:
                    paths.append(match)
                    seen.add(match)
    return paths


def load_sources(input_dir: Path) -> Tuple[Dict[str, pd.DataFrame], Dict[str, str]]:
    data: Dict[str, pd.DataFrame] = {}
    paths: Dict[str, str] = {}
    for key, candidates in CSV_CANDIDATES.items():
        if key == "site_lookup":
            lookup_frames = []
            lookup_paths = []
            for lookup_path in find_all_site_lookup_tables(input_dir):
                df = read_site_lookup_source(lookup_path)
                if df is not None and not df.empty:
                    lookup_frames.append(df)
                    lookup_paths.append(str(lookup_path))
                    print(f"Loaded site_lookup source: {lookup_path.name} ({len(df):,} valid/raw rows)")
            if lookup_frames:
                data[key] = pd.concat(lookup_frames, ignore_index=True, sort=False)
                paths[key] = "; ".join(lookup_paths)
                print(f"Merged site_lookup: {len(lookup_frames)} source files ({len(data[key]):,} raw rows)")
            continue

        path = find_table(input_dir, candidates)
        if path is None:
            continue
        df = read_table_if_exists(path)
        if df is not None:
            data[key] = df
            paths[key] = str(path)
            print(f"Loaded {key}: {path.name} ({len(df):,} rows)")
    return data, paths


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def first_existing(df: pd.DataFrame, names: Iterable[str]) -> Optional[str]:
    for name in names:
        if name in df.columns:
            return name
    return None


def clean_monthly(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "month_label" not in out.columns:
        raise ValueError("Monthly CSV must contain month_label")
    volume_col = first_existing(out, ["month_total_volume", "month_total_cleaned_volume"])
    if volume_col is None:
        raise ValueError("Monthly CSV must contain month_total_volume or month_total_cleaned_volume")

    out = out[out["month_label"].astype(str).str.match(MONTH_RE, na=False)].copy()
    out["month"] = pd.to_datetime(out["month_label"] + "-01", errors="coerce")
    out["volume"] = pd.to_numeric(out[volume_col], errors="coerce").fillna(0)
    out = out.dropna(subset=["month"]).sort_values("month")
    out["year"] = out["month"].dt.year

    out["is_known_data_gap"] = out["month_label"].isin(KNOWN_DATA_GAP_MONTHS)
    out["is_zero_volume"] = out["volume"].eq(0)
    out["volume_for_chart"] = out["volume"].astype(float)
    out.loc[out["is_known_data_gap"] & out["is_zero_volume"], "volume_for_chart"] = np.nan

    return out[["month_label", "month", "year", "volume", "volume_for_chart", "is_known_data_gap", "is_zero_volume"]]


def save_fig(path: Path, title: str, xlabel: str = "", ylabel: str = "") -> None:
    plt.title(title)
    if xlabel:
        plt.xlabel(xlabel)
    if ylabel:
        plt.ylabel(ylabel)
    plt.grid(True, alpha=0.25)
    plt.tight_layout()
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()
    print(f"Wrote {path}")


def billions_axis(ax) -> None:
    ax.yaxis.set_major_formatter(lambda x, pos: f"{x/1_000_000_000:.1f}B")


def millions_axis(ax) -> None:
    """Format a vertical chart y-axis in millions."""
    ax.yaxis.set_major_formatter(lambda x, pos: f"{x/1_000_000:.0f}M")


def x_millions_axis(ax) -> None:
    """Format a horizontal chart x-axis in millions."""
    ax.xaxis.set_major_formatter(lambda x, pos: f"{x/1_000_000:.0f}M")


def x_billions_axis(ax) -> None:
    """Format a horizontal chart x-axis in billions."""
    ax.xaxis.set_major_formatter(lambda x, pos: f"{x/1_000_000_000:.1f}B")


def rotate_x(degrees: int = 45) -> None:
    plt.xticks(rotation=degrees, ha="right")


def annotate_monthly_data_gaps(ax, monthly: pd.DataFrame, y_col: str = "volume_for_chart") -> None:
    if "is_known_data_gap" not in monthly.columns or y_col not in monthly.columns:
        return
    gaps = monthly[monthly["is_known_data_gap"] == True].copy()
    visible = monthly[y_col].dropna()
    if gaps.empty or visible.empty:
        return
    y_mid = visible.median()
    for _, row in gaps.iterrows():
        ax.axvline(row["month"], linestyle="--", linewidth=1.2, alpha=0.7, color=PALETTE["gap"])
        ax.annotate(
            f"Data gap\n{row['month_label']}",
            xy=(row["month"], y_mid),
            xytext=(10, 30),
            textcoords="offset points",
            arrowprops={"arrowstyle": "->", "lw": 1, "alpha": 0.75},
            fontsize=9,
            ha="left",
            va="center",
            bbox={"boxstyle": "round,pad=0.3", "fc": "white", "ec": "0.7", "alpha": 0.9},
        )


def format_site_id(value) -> Optional[str]:
    """Return a SCATS site ID as an integer-only string, never as 4415.0."""
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text == "" or text.lower() in {"nan", "none", "null"}:
        return None
    try:
        number = float(text)
        if np.isfinite(number) and number.is_integer():
            return str(int(number))
    except Exception:
        pass
    if re.fullmatch(r"\d+", text):
        return text
    text = re.sub(r"\.0$", "", text)
    return text

def wrap_label(text: str, width: int = 30) -> str:
    """Wrap long chart labels without breaking words too aggressively."""
    text = str(text).strip()
    if not text:
        return ""
    return "\n".join(textwrap.wrap(text, width=width, break_long_words=False, replace_whitespace=False))


def normalise_site_lookup(site_lookup: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    """Return a standard site lookup table with columns: site, site_name, latitude, longitude."""
    if site_lookup is None or site_lookup.empty:
        return None

    df = site_lookup.copy()
    col_map = {str(c).strip().lower(): c for c in df.columns}

    site_col = None
    for candidate in [
        "scats site", "scats_site", "scats id", "scats_id", "scatsid",
        "site", "site_id", "site id", "site no", "site_no", "site number", "site_number",
        "site number ", "site_no.", "site no.", "siteid"
    ]:
        if candidate in col_map:
            site_col = col_map[candidate]
            break

    name_col = None
    for candidate in [
        "name", "site name", "site_name", "site description", "site_description",
        "location", "location name", "intersection", "description", "desc", "road name",
        "site location"
    ]:
        if candidate in col_map:
            name_col = col_map[candidate]
            break

    lat_col = None
    for candidate in ["latitude", "lat", "y"]:
        if candidate in col_map:
            lat_col = col_map[candidate]
            break

    lon_col = None
    for candidate in ["longitude", "lon", "lng", "long", "x"]:
        if candidate in col_map:
            lon_col = col_map[candidate]
            break

    if site_col is None:
        return None

    out = pd.DataFrame()
    out["site"] = df[site_col].map(format_site_id)
    out = out.dropna(subset=["site"]).copy()

    if name_col is not None:
        out["site_name"] = df[name_col].astype(str).str.strip()
        out.loc[out["site_name"].str.lower().isin(["", "nan", "none", "null"]), "site_name"] = np.nan
    else:
        out["site_name"] = np.nan

    out["latitude"] = pd.to_numeric(df[lat_col], errors="coerce") if lat_col is not None else np.nan
    out["longitude"] = pd.to_numeric(df[lon_col], errors="coerce") if lon_col is not None else np.nan

    if "__lookup_source" in df.columns:
        out["lookup_source"] = df["__lookup_source"].astype(str)
    else:
        out["lookup_source"] = "site_lookup"

    def first_valid(series: pd.Series):
        valid = series.dropna()
        if valid.empty:
            return np.nan
        for value in valid:
            text = str(value).strip()
            if text and text.lower() not in {"nan", "none", "null"}:
                return value
        return np.nan

    out["site_name_clean"] = out["site_name"].map(_clean_lookup_name_value)
    out["name_quality"] = out["site_name_clean"].fillna("").astype(str).str.len()
    out["coord_quality"] = out[["latitude", "longitude"]].notna().sum(axis=1)
    out = out.sort_values(["site", "name_quality", "coord_quality"], ascending=[True, False, False])

    out = (
        out.groupby("site", as_index=False)
        .agg({
            "site_name_clean": first_valid,
            "latitude": first_valid,
            "longitude": first_valid,
            "lookup_source": lambda s: "; ".join(sorted(set(str(x) for x in s.dropna()))),
        })
        .rename(columns={"site_name_clean": "site_name"})
    )

    # Apply verified overrides after all merging/deduping, so no blank or short
    # source lookup row can overwrite these known correct names.
    for site_id, site_name in SITE_NAME_OVERRIDES.items():
        mask = out["site"].astype(str).eq(site_id)
        if mask.any():
            out.loc[mask, "site_name"] = site_name
            out.loc[mask, "lookup_source"] = out.loc[mask, "lookup_source"].astype(str) + "; manual_override"
        else:
            out = pd.concat([
                out,
                pd.DataFrame([{
                    "site": site_id,
                    "site_name": site_name,
                    "latitude": np.nan,
                    "longitude": np.nan,
                    "lookup_source": "manual_override",
                }])
            ], ignore_index=True)

    return out[["site", "site_name", "latitude", "longitude", "lookup_source"]]


def site_display_label(site: str, site_name: Optional[str], width: int = 34) -> str:
    """Readable y-axis label: wrapped site name on top, integer site ID below."""
    name = "" if pd.isna(site_name) else str(site_name).strip()
    if name:
        return f"{wrap_label(name, width)}\nSite {site}"
    return f"Site {site}"


def add_gap_note(ax) -> None:
    ax.text(
        0.01,
        0.01,
        "Known zero-volume source gap shown as broken line: 2018-12",
        transform=ax.transAxes,
        fontsize=8,
        va="bottom",
        ha="left",
        alpha=0.75,
    )


def chart_monthly_totals(monthly: pd.DataFrame, out_dir: Path, manifest: List[dict]) -> None:
    fig, ax = plt.subplots(figsize=(14, 7))
    plot_heat_line(ax, monthly["month"], monthly["volume_for_chart"], linewidth=2.8)
    add_heat_note(ax)
    annotate_monthly_data_gaps(ax, monthly)
    add_gap_note(ax)
    billions_axis(ax)
    path = out_dir / "01_monthly_total_traffic_line.png"
    save_fig(path, "Melbourne SCATS Monthly Cleaned Traffic Volume", "Month", "Cleaned vehicle movements")
    manifest.append({"file": path.name, "title": "Monthly total traffic line chart", "source": "monthly_totals", "gap_handling": "2018-12 shown as a broken line and annotated"})

    chartable = monthly.copy()
    if chartable["volume_for_chart"].notna().sum() >= 6:
        chartable["rolling_6_month_avg"] = chartable["volume_for_chart"].rolling(6, min_periods=1).mean()
        fig, ax = plt.subplots(figsize=(14, 7))
        ax.plot(chartable["month"], chartable["volume_for_chart"], linewidth=1.4, label="Monthly total", color=PALETTE["traffic_light"])
        ax.plot(chartable["month"], chartable["rolling_6_month_avg"], linewidth=2.6, label="6-month rolling average", color=PALETTE["rolling"])
        annotate_monthly_data_gaps(ax, chartable)
        add_gap_note(ax)
        ax.legend()
        billions_axis(ax)
        path = out_dir / "02_monthly_total_traffic_with_rolling_average.png"
        save_fig(path, "Monthly Traffic With 6-Month Rolling Average", "Month", "Cleaned vehicle movements")
        manifest.append({"file": path.name, "title": "Monthly totals with rolling average", "source": "monthly_totals", "gap_handling": "2018-12 shown as a broken line and annotated"})


def chart_yearly_totals(monthly: pd.DataFrame, out_dir: Path, manifest: List[dict]) -> None:
    yearly = monthly.groupby("year", as_index=False)["volume"].sum()
    yearly.to_csv(out_dir / "yearly_totals_from_monthly.csv", index=False)

    fig, ax = plt.subplots(figsize=(12, 7))
    ax.bar(yearly["year"].astype(str), yearly["volume"], color=heat_colours(yearly["volume"]))
    add_heat_note(ax)
    if monthly["is_known_data_gap"].any():
        ax.text(0.01, 0.01, "Note: 2018 includes known missing month 2018-12.", transform=ax.transAxes, fontsize=8, va="bottom", ha="left", alpha=0.75)
    billions_axis(ax)
    rotate_x(45)
    path = out_dir / "03_yearly_total_traffic_bar.png"
    save_fig(path, "Yearly Cleaned Traffic Volume", "Year", "Cleaned vehicle movements")
    manifest.append({"file": path.name, "title": "Yearly total traffic bar chart", "source": "monthly_totals", "gap_handling": "2018 yearly total includes the known missing month as raw zero and is annotated"})

    full_years = yearly[yearly["year"] < yearly["year"].max()].copy()
    full_years["yoy_pct_change"] = full_years["volume"].pct_change() * 100
    full_years.to_csv(out_dir / "yearly_growth_from_monthly.csv", index=False)
    if len(full_years.dropna(subset=["yoy_pct_change"])) >= 2:
        fig, ax = plt.subplots(figsize=(12, 7))
        ax.bar(full_years["year"].astype(str), full_years["yoy_pct_change"], color=[PALETTE["growth_pos"] if v >= 0 else PALETTE["growth_neg"] for v in full_years["yoy_pct_change"].fillna(0)])
        ax.axhline(0, linewidth=1, color=PALETTE["gap"], alpha=0.8)
        ax.text(0.01, 0.01, "2018/2019 affected by known missing month 2018-12.", transform=ax.transAxes, fontsize=8, va="bottom", ha="left", alpha=0.75)
        rotate_x(45)
        path = out_dir / "04_yearly_growth_rate_bar.png"
        save_fig(path, "Year-on-Year Traffic Growth", "Year", "Growth vs previous year (%)")
        manifest.append({"file": path.name, "title": "Year-on-year traffic growth", "source": "monthly_totals", "gap_handling": "2018/2019 growth affected by known 2018-12 gap and annotated"})


def chart_covid_period(monthly: pd.DataFrame, out_dir: Path, manifest: List[dict]) -> None:
    covid = monthly[(monthly["month"] >= "2019-01-01") & (monthly["month"] <= "2022-12-01")].copy()
    if covid.empty:
        return
    fig, ax = plt.subplots(figsize=(13, 7))
    plot_heat_line(ax, covid["month"], covid["volume_for_chart"], linewidth=2.8)
    add_heat_note(ax, "COVID-era traffic heat: green = lighter lockdown traffic, red = heavier/recovered traffic.")
    billions_axis(ax)
    path = out_dir / "05_covid_disruption_and_recovery_monthly.png"
    save_fig(path, "COVID-Era Traffic Disruption and Recovery", "Month", "Cleaned vehicle movements")
    manifest.append({"file": path.name, "title": "COVID disruption and recovery", "source": "monthly_totals"})


def chart_seasonality(monthly: pd.DataFrame, out_dir: Path, manifest: List[dict]) -> None:
    chartable = monthly.dropna(subset=["volume_for_chart"]).copy()
    if chartable.empty:
        return
    chartable["month_of_year"] = chartable["month"].dt.month
    season = chartable.groupby("month_of_year", as_index=False)["volume_for_chart"].mean().rename(columns={"volume_for_chart": "volume"})
    season["month_name"] = pd.to_datetime(season["month_of_year"], format="%m").dt.strftime("%b")
    season.to_csv(out_dir / "monthly_seasonality_average.csv", index=False)

    fig, ax = plt.subplots(figsize=(11, 7))
    ax.bar(season["month_name"], season["volume"], color=heat_colours(season["volume"]))
    add_heat_note(ax, "Monthly seasonality heat: green = lighter months, red = busiest months.")
    billions_axis(ax)
    path = out_dir / "06_average_month_by_seasonality.png"
    save_fig(path, "Average Traffic by Month of Year", "Month", "Average cleaned vehicle movements")
    manifest.append({"file": path.name, "title": "Monthly seasonality", "source": "monthly_totals", "gap_handling": "Known data-gap months excluded from monthly averages"})


def chart_peak_shares(df: pd.DataFrame, out_dir: Path, manifest: List[dict]) -> None:
    required = {"month_label", "month_am_share_pct", "month_pm_share_pct"}
    if not required.issubset(df.columns):
        return
    d = df.copy()
    d = d[d["month_label"].astype(str).str.match(MONTH_RE, na=False)]
    d["month"] = pd.to_datetime(d["month_label"] + "-01", errors="coerce")
    d["am_share"] = pd.to_numeric(d["month_am_share_pct"], errors="coerce")
    d["pm_share"] = pd.to_numeric(d["month_pm_share_pct"], errors="coerce")
    d = d.dropna(subset=["month"]).sort_values("month")
    if d.empty:
        return

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(d["month"], d["am_share"], linewidth=2.2, label="AM peak share", color=PALETTE["am_peak"])
    ax.plot(d["month"], d["pm_share"], linewidth=2.2, label="PM peak share", color=PALETTE["pm_peak"])
    ax.legend()
    path = out_dir / "07_am_pm_peak_share_over_time.png"
    save_fig(path, "AM vs PM Peak Share Over Time", "Month", "Share of monthly traffic (%)")
    manifest.append({"file": path.name, "title": "AM and PM peak share over time", "source": "chunked_peak_shares_monthly"})

    total_col = first_existing(d, ["month_total_volume"])
    am_col = first_existing(df, ["month_am_volume"])
    pm_col = first_existing(df, ["month_pm_volume"])
    if total_col and am_col and pm_col:
        total = pd.to_numeric(df[total_col], errors="coerce").sum()
        am = pd.to_numeric(df[am_col], errors="coerce").sum()
        pm = pd.to_numeric(df[pm_col], errors="coerce").sum()
        off = max(total - am - pm, 0)
        if total > 0:
            fig, ax = plt.subplots(figsize=(10, 7))
            ax.bar(["AM peak\n07:00-10:00", "PM peak\n16:00-19:00", "Other hours"], [am, pm, off], color=[PALETTE["am_peak"], PALETTE["pm_peak"], PALETTE["off_peak"]])
            billions_axis(ax)
            path = out_dir / "08_peak_vs_off_peak_volume_bar.png"
            save_fig(path, "Peak vs Off-Peak Cleaned Traffic Volume", "Period", "Cleaned vehicle movements")
            manifest.append({"file": path.name, "title": "Peak vs off-peak volume", "source": "chunked_peak_shares_monthly"})


def chart_time_bins(df: pd.DataFrame, out_dir: Path, manifest: List[dict]) -> None:
    required = {"time_bin", "month_time_bin_volume", "month_distinct_dates"}
    if not required.issubset(df.columns):
        return
    d = df.copy()
    d["volume"] = pd.to_numeric(d["month_time_bin_volume"], errors="coerce").fillna(0)
    d["dates"] = pd.to_numeric(d["month_distinct_dates"], errors="coerce").fillna(0)
    d = d[d["time_bin"].astype(str).str.match(r"^\d{2}:\d{2}$", na=False)]
    agg = d.groupby("time_bin", as_index=False).agg(total_volume=("volume", "sum"), distinct_dates=("dates", "sum"))
    agg = agg[agg["distinct_dates"] > 0]
    agg["avg_daily_volume"] = agg["total_volume"] / agg["distinct_dates"]
    agg = agg.sort_values("time_bin")
    agg.to_csv(out_dir / "time_bin_profile_aggregated.csv", index=False)
    if agg.empty:
        return

    fig, ax = plt.subplots(figsize=(15, 7))
    plot_heat_line_categories(ax, agg["time_bin"], agg["avg_daily_volume"], linewidth=3.0)
    add_heat_note(ax, "Time-of-day heat: green = quiet/clear, amber = building traffic, red = busiest periods.")
    ax.set_xticks(range(0, len(agg), 4))
    ax.set_xticklabels(agg["time_bin"].iloc[::4], rotation=45, ha="right")
    millions_axis(ax)
    path = out_dir / "09_average_daily_traffic_by_time_of_day.png"
    save_fig(path, "Average Daily Traffic by 15-Minute Time Bin", "Time of day", "Average daily cleaned vehicle movements")
    manifest.append({"file": path.name, "title": "Average daily traffic by time of day", "source": "chunked_busiest_time_bin_monthly"})

    top = agg.sort_values("avg_daily_volume", ascending=False).head(10)
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.bar(top["time_bin"], top["avg_daily_volume"], color=heat_colours(top["avg_daily_volume"]))
    millions_axis(ax)
    path = out_dir / "10_top_10_busiest_time_bins.png"
    save_fig(path, "Top 10 Busiest 15-Minute Time Bins", "Time bin", "Average daily cleaned vehicle movements")
    manifest.append({"file": path.name, "title": "Top 10 busiest time bins", "source": "chunked_busiest_time_bin_monthly"})

    quiet = agg.sort_values("avg_daily_volume", ascending=True).head(10)
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.bar(quiet["time_bin"], quiet["avg_daily_volume"], color=heat_colours(quiet["avg_daily_volume"], cmap=QUIET_CMAP))
    path = out_dir / "11_top_10_quietest_time_bins.png"
    save_fig(path, "Top 10 Quietest 15-Minute Time Bins", "Time bin", "Average daily cleaned vehicle movements")
    manifest.append({"file": path.name, "title": "Top 10 quietest time bins", "source": "chunked_busiest_time_bin_monthly"})


def chart_busiest_days(df: pd.DataFrame, out_dir: Path, manifest: List[dict]) -> None:
    required = {"count_date", "day_total_volume"}
    if not required.issubset(df.columns):
        return
    d = df.copy()
    d["count_date"] = pd.to_datetime(d["count_date"], errors="coerce")
    d["volume"] = pd.to_numeric(d["day_total_volume"], errors="coerce").fillna(0)
    d = d.dropna(subset=["count_date"])
    if d.empty:
        return
    daily = d.groupby("count_date", as_index=False)["volume"].sum().sort_values("volume", ascending=False)
    daily["date_label"] = daily["count_date"].dt.strftime("%Y-%m-%d")
    daily["day_name"] = daily["count_date"].dt.day_name()
    daily.head(50).to_csv(out_dir / "top_50_busiest_days.csv", index=False)

    top = daily.head(10).sort_values("volume")
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.barh(top["date_label"] + "\n" + top["day_name"], top["volume"], color=heat_colours(top["volume"]))
    add_heat_note(ax, "Busiest-day heat: green = lower among top days, red = busiest recorded days.")
    x_millions_axis(ax)
    ax.set_xlim(0, top["volume"].max() * 1.08)
    for y, v in enumerate(top["volume"]):
        ax.text(v, y, f" {v/1_000_000:.1f}M", va="center", fontsize=8, color="#27364a")
    path = out_dir / "12_top_10_busiest_days.png"
    save_fig(path, "Top 10 Busiest Recorded Days", "Cleaned vehicle movements (millions)", "Date")
    manifest.append({"file": path.name, "title": "Top 10 busiest days", "source": "chunked_busiest_day_monthly"})

    d["year"] = d["count_date"].dt.year
    idx = d.groupby("year")["volume"].idxmax()
    by_year = d.loc[idx].copy().sort_values("year")
    by_year["date_label"] = by_year["count_date"].dt.strftime("%Y-%m-%d")
    by_year.to_csv(out_dir / "busiest_day_by_year.csv", index=False)
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.bar(by_year["year"].astype(str), by_year["volume"], color=heat_colours(by_year["volume"]))
    add_heat_note(ax, "Yearly busiest-day heat: green = lower peak days, red = highest peak days.")
    millions_axis(ax)
    rotate_x(45)
    path = out_dir / "13_busiest_day_by_year.png"
    save_fig(path, "Busiest Day Volume by Year", "Year", "Cleaned vehicle movements")
    manifest.append({"file": path.name, "title": "Busiest day by year", "source": "chunked_busiest_day_monthly"})

    weekday = d.groupby(d["count_date"].dt.day_name(), as_index=True)["volume"].mean()
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday = weekday.reindex(order).dropna()
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.bar(weekday.index, weekday.values, color=heat_colours(weekday.values))
    add_heat_note(ax, "Weekday heat: green = lighter days, red = busiest average days.")
    millions_axis(ax)
    rotate_x(30)
    path = out_dir / "14_average_daily_volume_by_weekday.png"
    save_fig(path, "Average Daily Traffic by Day of Week", "Day", "Average cleaned vehicle movements")
    manifest.append({"file": path.name, "title": "Average daily volume by weekday", "source": "chunked_busiest_day_monthly"})


def chart_busiest_sites(
    df: pd.DataFrame,
    out_dir: Path,
    manifest: List[dict],
    site_lookup: Optional[pd.DataFrame] = None,
) -> None:
    required = {"scats_site", "month_site_volume"}
    if not required.issubset(df.columns):
        return
    d = df.copy()

    # SCATS site IDs are identifiers, not measured quantities. Force them to
    # integer-only string labels so matplotlib/pandas can never render them as
    # floats such as 4415.0 or apply million-format tick labels to them.
    d["site"] = d["scats_site"].map(format_site_id)
    d = d.dropna(subset=["site"]).copy()
    d["volume"] = pd.to_numeric(d["month_site_volume"], errors="coerce").fillna(0)

    sites = d.groupby("site", as_index=False)["volume"].sum().sort_values("volume", ascending=False)

    lookup = normalise_site_lookup(site_lookup)
    if lookup is not None:
        sites = sites.merge(lookup, on="site", how="left")
    else:
        sites["site_name"] = np.nan
        sites["latitude"] = np.nan
        sites["longitude"] = np.nan

    sites.to_csv(out_dir / "site_totals_from_monthly.csv", index=False)
    sites.head(20).to_csv(out_dir / "top_20_busiest_scats_sites_named.csv", index=False)
    missing_top_names = []
    if "site_name" in sites.columns:
        missing_top_names = sites.head(20).loc[sites.head(20)["site_name"].isna(), "site"].astype(str).tolist()
    if sites.empty:
        return

    top = sites.head(20).sort_values("volume").copy()
    top["site_label"] = [
        site_display_label(site, name, width=34)
        for site, name in zip(top["site"], top["site_name"])
    ]

    # Wider/taller figure and larger left margin so long location names are legible.
    fig, ax = plt.subplots(figsize=(16, 11.5))
    norm = Normalize(vmin=float(top["volume"].min()), vmax=float(top["volume"].max()))
    colours = plt.cm.YlOrRd(norm(top["volume"].astype(float).values))
    bars = ax.barh(top["site_label"], top["volume"], color=colours, edgecolor="#7f1d1d", linewidth=0.35)
    sm = plt.cm.ScalarMappable(cmap=plt.cm.YlOrRd, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, pad=0.015, fraction=0.028)
    cbar.set_label("Relative site heat by total movements", fontsize=9)
    cbar.ax.tick_params(labelsize=8)
    x_millions_axis(ax)
    ax.set_xlim(0, top["volume"].max() * 1.18)

    for bar, v in zip(bars, top["volume"]):
        ax.text(
            v + top["volume"].max() * 0.008,
            bar.get_y() + bar.get_height() / 2,
            f"{v/1_000_000:.1f}M",
            va="center",
            fontsize=9,
            color="#27364a",
        )

    matched = int(top["site_name"].notna().sum())
    ax.text(
        0.01,
        0.01,
        f"Labels show SCATS site names plus integer site IDs. {matched}/20 top sites have names from the merged lookup table.",
        transform=ax.transAxes,
        fontsize=8,
        va="bottom",
        ha="left",
        alpha=0.75,
    )
    plt.subplots_adjust(left=0.36, right=0.93, top=0.92, bottom=0.08)
    path = out_dir / "15_top_20_busiest_scats_sites.png"
    save_fig(path, "Top 20 Busiest SCATS Sites", "Total cleaned vehicle movements (millions)", "SCATS site name and ID")
    manifest.append({
        "file": path.name,
        "title": "Top 20 busiest SCATS sites",
        "source": "chunked_busiest_site_monthly + site lookup",
        "site_lookup_matches_top_20": matched,
        "missing_top_20_names": missing_top_names,
        "axis_fix": "V3.9 scans all Excel sheets, applies verified manual overrides for sites 2816 and 3376, preserves integer-only IDs, and applies traffic-light heat colouring across charts",
    })

    if "month_label" in d.columns:
        top_site = format_site_id(sites.iloc[0]["site"])
        top_name = None
        if "site_name" in sites.columns:
            vals = sites.loc[sites["site"] == top_site, "site_name"].dropna()
            if not vals.empty:
                top_name = str(vals.iloc[0]).strip()

        ts = d[d["site"] == top_site].copy()
        ts = ts[ts["month_label"].astype(str).str.match(MONTH_RE, na=False)]
        ts["month"] = pd.to_datetime(ts["month_label"] + "-01", errors="coerce")
        ts = ts.sort_values("month")
        if not ts.empty:
            fig, ax = plt.subplots(figsize=(14, 7))
            plot_heat_line(ax, ts["month"], ts["volume"], linewidth=2.8)
            add_heat_note(ax, "Busiest-site monthly heat: green = lighter months, red = busiest months.")
            millions_axis(ax)
            title_site = f"Site {top_site}"
            if top_name:
                title_site = f"{top_name} — Site {top_site}"
            path = out_dir / "16_busiest_site_monthly_trend.png"
            save_fig(path, f"Monthly Trend for Busiest SCATS Site: {title_site}", "Month", "Cleaned vehicle movements")
            manifest.append({
                "file": path.name,
                "title": "Monthly trend for busiest SCATS site",
                "source": "chunked_busiest_site_monthly + site lookup",
                "site_id_format": "integer string",
                "site_id": top_site,
                "site_name": top_name,
            })



def chart_processing_time(data: Dict[str, pd.DataFrame], out_dir: Path, manifest: List[dict]) -> None:
    rows = []
    for key, df in data.items():
        elapsed_col = first_existing(df, ["month_elapsed_seconds"])
        if elapsed_col is None or "month_label" not in df.columns:
            continue
        tmp = df[["month_label", elapsed_col]].drop_duplicates().copy()
        tmp["elapsed_seconds"] = pd.to_numeric(tmp[elapsed_col], errors="coerce")
        tmp = tmp.dropna(subset=["elapsed_seconds"])
        if not tmp.empty:
            rows.append({"source": key, "total_hours": tmp["elapsed_seconds"].sum() / 3600, "months_or_batches": len(tmp)})
    if not rows:
        return
    proc = pd.DataFrame(rows).sort_values("total_hours", ascending=False)
    proc.to_csv(out_dir / "processing_time_summary.csv", index=False)
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.barh(proc["source"], proc["total_hours"], color=PALETTE["processing"])
    ax.set_xlim(0, proc["total_hours"].max() * 1.10)
    for y, v in enumerate(proc["total_hours"]):
        ax.text(v, y, f" {v:.1f}h", va="center", fontsize=8, color="#27364a")
    path = out_dir / "17_processing_time_by_completed_csv.png"
    save_fig(path, "Processing Time Represented by Completed CSVs", "Hours", "")
    manifest.append({"file": path.name, "title": "Processing time by completed CSV", "source": "all CSVs with month_elapsed_seconds"})


def write_manifest(out_dir: Path, manifest: List[dict], source_paths: Dict[str, str]) -> None:
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "chart_count": len(manifest),
        "gap_handling": "Known data-gap month 2018-12 is retained but plotted as NaN/broken line in monthly charts.",
        "colour_scheme": PALETTE,
        "traffic_light_heat_scale": "green = lighter/clearer, amber = medium, red = busiest/heaviest",
        "source_paths": source_paths,
        "charts": manifest,
    }
    path = out_dir / "chart_manifest.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate SCATS charts from completed CSV outputs.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    input_dir = args.input_dir
    output_dir = args.output_dir or (input_dir / "charts")
    ensure_dir(output_dir)

    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "#c9d3df",
        "axes.labelcolor": "#27364a",
        "axes.titlecolor": "#1f2d3d",
        "axes.titlesize": 16,
        "axes.labelsize": 11,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "xtick.color": "#4b5563",
        "ytick.color": "#4b5563",
        "grid.color": "#d9e2ec",
        "legend.fontsize": 10,
    })

    data, paths = load_sources(input_dir)
    manifest: List[dict] = []

    monthly_source = data.get("monthly_totals")
    if monthly_source is None:
        monthly_source = data.get("total_cleaned_volume")
    if monthly_source is not None:
        monthly = clean_monthly(monthly_source)
        monthly.to_csv(output_dir / "monthly_totals_cleaned_for_charts.csv", index=False)
        chart_monthly_totals(monthly, output_dir, manifest)
        chart_yearly_totals(monthly, output_dir, manifest)
        chart_covid_period(monthly, output_dir, manifest)
        chart_seasonality(monthly, output_dir, manifest)
    else:
        print("WARNING: monthly totals CSV not found; skipping monthly/yearly charts")

    if "peak_shares_monthly" in data:
        chart_peak_shares(data["peak_shares_monthly"], output_dir, manifest)
    else:
        print("WARNING: peak shares CSV not found; skipping peak-share charts")

    if "busiest_time_bin_monthly" in data:
        chart_time_bins(data["busiest_time_bin_monthly"], output_dir, manifest)
    else:
        print("WARNING: time-bin CSV not found; skipping time-of-day charts")

    if "busiest_day_monthly" in data:
        chart_busiest_days(data["busiest_day_monthly"], output_dir, manifest)
    else:
        print("WARNING: busiest-day CSV not found; skipping busiest-day charts")

    if "busiest_site_monthly" in data:
        chart_busiest_sites(data["busiest_site_monthly"], output_dir, manifest, data.get("site_lookup"))
    else:
        print("WARNING: busiest-site CSV not found; skipping busiest-site charts")

    chart_processing_time(data, output_dir, manifest)
    write_manifest(output_dir, manifest, paths)

    print("\nDONE")
    print(f"Charts written to: {output_dir}")
    print(f"Chart count: {len(manifest)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
