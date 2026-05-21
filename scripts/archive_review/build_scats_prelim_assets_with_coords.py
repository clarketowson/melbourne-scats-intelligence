from pathlib import Path
from datetime import datetime
import html
import pandas as pd
import matplotlib.pyplot as plt

BASE = Path(r"A:\TrafficAnalytics\PROJECTS\reports")
PRIORITY = BASE / "scats_priority_answers"
CLEAN = BASE / "scats_clean_outputs_v2"

OUT_DIR = BASE / "scats_prelim_page"
GRAPH_DIR = OUT_DIR / "graphs"
OUT_HTML = OUT_DIR / "index.html"

# Put your coordinates file here
COORDS_PATH = Path(r"A:\TrafficAnalytics\PROJECTS\reports\busiestSCATSsitesCOORDINATES.csv")

OUT_DIR.mkdir(parents=True, exist_ok=True)
GRAPH_DIR.mkdir(parents=True, exist_ok=True)

def read_csv(folder: Path, filename: str) -> pd.DataFrame:
    path = folder / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return pd.read_csv(path)

def fmt_int(x):
    if pd.isna(x):
        return "—"
    return f"{int(round(float(x))):,}"

def fmt_float(x, digits=1):
    if pd.isna(x):
        return "—"
    return f"{float(x):,.{digits}f}"

def fmt_pct(x, digits=2):
    if pd.isna(x):
        return "—"
    return f"{float(x):.{digits}f}%"

def table_html(df: pd.DataFrame, max_rows: int = 20) -> str:
    show = df.head(max_rows).copy()
    for col in show.columns:
        if "date" in col.lower():
            try:
                show[col] = pd.to_datetime(show[col]).dt.strftime("%Y-%m-%d")
            except Exception:
                pass
    headers = "".join(f"<th>{html.escape(str(c))}</th>" for c in show.columns)
    rows = []
    for _, r in show.iterrows():
        cells = "".join(f"<td>{html.escape(str(v))}</td>" for v in r.tolist())
        rows.append(f"<tr>{cells}</tr>")
    return f"""
    <div class="table-wrap">
      <table>
        <thead><tr>{headers}</tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    """

def image_card(title: str, description: str, filename: str) -> str:
    rel = f"graphs/{filename}"
    return f"""
    <div class="chart-card">
      <h3>{html.escape(title)}</h3>
      <p>{html.escape(description)}</p>
      <a href="{rel}" target="_blank">
        <img src="{rel}" alt="{html.escape(title)}">
      </a>
    </div>
    """

def normalize_coords(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    rename_map = {}
    for c in out.columns:
        cl = c.strip().lower()
        if cl in ("scats site", "scats_site", "site", "site_id"):
            rename_map[c] = "scats_site"
        elif cl in ("name", "site_name", "intersection", "location"):
            rename_map[c] = "site_name"
        elif cl in ("latitude", "lat"):
            rename_map[c] = "latitude"
        elif cl in ("longitude", "lon", "lng", "long"):
            rename_map[c] = "longitude"
    out = out.rename(columns=rename_map)

    required = ["scats_site", "site_name", "latitude", "longitude"]
    missing = [c for c in required if c not in out.columns]
    if missing:
        raise ValueError(
            f"Coordinate file is missing required columns after normalization: {missing}. "
            f"Expected something like SCATS Site, Name, Latitude, Longitude."
        )

    out["scats_site"] = pd.to_numeric(out["scats_site"], errors="coerce").astype("Int64")
    out["latitude"] = pd.to_numeric(out["latitude"], errors="coerce")
    out["longitude"] = pd.to_numeric(out["longitude"], errors="coerce")
    out["site_name"] = out["site_name"].astype(str)

    out = out.dropna(subset=["scats_site", "latitude", "longitude"]).copy()
    out["scats_site"] = out["scats_site"].astype(int)
    return out[["scats_site", "site_name", "latitude", "longitude"]].drop_duplicates()

# ----------------------------
# LOAD DATA
# ----------------------------
dataset_summary = read_csv(PRIORITY, "01_dataset_summary.csv")
busiest_sites = read_csv(PRIORITY, "02_busiest_intersections_top_100.csv")
quietest_sites = read_csv(PRIORITY, "03_quietest_intersections_bottom_100.csv")
busiest_times = read_csv(PRIORITY, "04_busiest_time_of_day_network.csv")
quietest_times = read_csv(PRIORITY, "05_quietest_time_of_day_network.csv")
busiest_days = read_csv(PRIORITY, "06_busiest_days_top_100.csv")
quietest_days = read_csv(PRIORITY, "07_quietest_days_bottom_100.csv")
weekday_weekend = read_csv(PRIORITY, "08_weekday_vs_weekend_network.csv")
monday_friday = read_csv(PRIORITY, "09_monday_vs_friday_network.csv")
peak_site = read_csv(PRIORITY, "10_peak_15min_period_each_site_top_100_by_peak.csv")
growth = read_csv(PRIORITY, "16_fastest_growth_sites_top_100.csv")
decline = read_csv(PRIORITY, "17_biggest_decline_sites_bottom_100.csv")
predictable = read_csv(PRIORITY, "18_most_predictable_sites_top_100.csv")
variable = read_csv(PRIORITY, "19_most_variable_sites_top_100.csv")
shares = read_csv(PRIORITY, "20_peak_offpeak_overnight_shares_network.csv")

daily_totals = read_csv(CLEAN, "04_daily_total_volume.csv")
top_sites_clean = read_csv(CLEAN, "05_top_100_sites_by_total_volume.csv")
time_profile = read_csv(CLEAN, "08_time_bin_profile_network.csv")

coords = normalize_coords(pd.read_csv(COORDS_PATH))

# Merge coordinates into key tables
busiest_sites = busiest_sites.merge(coords, on="scats_site", how="left")
quietest_sites = quietest_sites.merge(coords, on="scats_site", how="left")
growth = growth.merge(coords, on="scats_site", how="left")
decline = decline.merge(coords, on="scats_site", how="left")
predictable = predictable.merge(coords, on="scats_site", how="left")
variable = variable.merge(coords, on="scats_site", how="left")
top_sites_clean = top_sites_clean.merge(coords, on="scats_site", how="left")

# ----------------------------
# EXTRACT KEY VALUES
# ----------------------------
row = dataset_summary.iloc[0]
cleaned_rows = int(row["cleaned_rows"])
distinct_sites = int(row["distinct_sites"])
min_date = pd.to_datetime(row["min_date"]).strftime("%Y-%m-%d")
max_date = pd.to_datetime(row["max_date"]).strftime("%Y-%m-%d")
cleaned_total_volume = int(row["cleaned_total_volume"])

top_site = int(busiest_sites.iloc[0]["scats_site"])
top_site_name = str(busiest_sites.iloc[0].get("site_name", "Unknown"))
top_site_volume = int(busiest_sites.iloc[0]["total_volume"])

quiet_site = int(quietest_sites.iloc[0]["scats_site"])
quiet_site_name = str(quietest_sites.iloc[0].get("site_name", "Unknown"))
quiet_site_volume = int(quietest_sites.iloc[0]["total_volume"])

busiest_time = str(busiest_times.iloc[0]["time_bin"])
quietest_time = str(quietest_times.iloc[0]["time_bin"])
busiest_day = pd.to_datetime(busiest_days.iloc[0]["count_date"]).strftime("%Y-%m-%d")
quietest_day = pd.to_datetime(quietest_days.iloc[0]["count_date"]).strftime("%Y-%m-%d")

ww = {r["day_type"]: float(r["avg_daily_volume"]) for _, r in weekday_weekend.iterrows()}
mf = {r["day_name"]: float(r["avg_daily_volume"]) for _, r in monday_friday.iterrows()}

share_row = shares.iloc[0]
am_peak_pct = float(share_row["am_peak_pct"])
pm_peak_pct = float(share_row["pm_peak_pct"])
overnight_pct = float(share_row["overnight_pct"])
before_9am_pct = float(share_row["before_9am_pct"])
after_6pm_pct = float(share_row["after_6pm_pct"])

top_growth_site = int(growth.iloc[0]["scats_site"])
top_growth_name = str(growth.iloc[0].get("site_name", "Unknown"))
top_growth_abs = int(growth.iloc[0]["absolute_change"])

top_decline_site = int(decline.iloc[0]["scats_site"])
top_decline_name = str(decline.iloc[0].get("site_name", "Unknown"))
top_decline_abs = int(decline.iloc[0]["absolute_change"])

most_predictable_site = int(predictable.iloc[0]["scats_site"])
most_predictable_name = str(predictable.iloc[0].get("site_name", "Unknown"))
most_predictable_cv = float(predictable.iloc[0]["cv"])

most_variable_site = int(variable.iloc[0]["scats_site"])
most_variable_name = str(variable.iloc[0].get("site_name", "Unknown"))
most_variable_cv = float(variable.iloc[0]["cv"])

peak_site_top = int(peak_site.iloc[0]["scats_site"])
peak_site_time = str(peak_site.iloc[0]["peak_time_bin"])
peak_site_avg = float(peak_site.iloc[0]["avg_peak_15m_volume"])

generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ----------------------------
# BUILD PNG GRAPHS
# ----------------------------

# 1. Daily traffic volume
daily = daily_totals.copy()
daily["count_date"] = pd.to_datetime(daily["count_date"])

plt.figure(figsize=(16, 6))
plt.plot(daily["count_date"], daily["total_volume"])
plt.title("Daily Traffic Volume (Network Wide)")
plt.xlabel("Date")
plt.ylabel("Vehicles")
plt.tight_layout()
plt.savefig(GRAPH_DIR / "daily_volume_timeseries.png", dpi=160)
plt.close()

# 2. Network time-of-day profile
tp = time_profile.copy()
plt.figure(figsize=(14, 6))
plt.plot(tp["time_bin"], tp["total_volume"])
plt.xticks(rotation=90)
plt.title("Network Traffic Profile by Time of Day")
plt.xlabel("Time")
plt.ylabel("Vehicles")
plt.tight_layout()
plt.savefig(GRAPH_DIR / "network_time_profile.png", dpi=160)
plt.close()

# 3. Top 20 sites
top20 = top_sites_clean.head(20).copy()
top20["label"] = top20.apply(
    lambda r: f"{int(r['scats_site'])} - {str(r['site_name'])[:28]}",
    axis=1
)

plt.figure(figsize=(14, 9))
plt.barh(top20["label"], top20["total_volume"])
plt.gca().invert_yaxis()
plt.title("Top 20 SCATS Sites by Total Volume")
plt.xlabel("Total Vehicles")
plt.ylabel("SCATS Site")
plt.tight_layout()
plt.savefig(GRAPH_DIR / "top_20_sites_bar_chart.png", dpi=160)
plt.close()

# 4. Weekday vs weekend
ww_df = weekday_weekend.copy()
plt.figure(figsize=(8, 5))
plt.bar(ww_df["day_type"], ww_df["avg_daily_volume"])
plt.title("Weekday vs Weekend Average Daily Volume")
plt.xlabel("Day Type")
plt.ylabel("Average Daily Vehicles")
plt.tight_layout()
plt.savefig(GRAPH_DIR / "weekday_vs_weekend.png", dpi=160)
plt.close()

# 5. Monday vs Friday
mf_df = monday_friday.copy()
plt.figure(figsize=(8, 5))
plt.bar(mf_df["day_name"], mf_df["avg_daily_volume"])
plt.title("Monday vs Friday Average Daily Volume")
plt.xlabel("Day")
plt.ylabel("Average Daily Vehicles")
plt.tight_layout()
plt.savefig(GRAPH_DIR / "monday_vs_friday.png", dpi=160)
plt.close()

# 6. Busiest times of day
bt = busiest_times.copy().sort_values("time_bin")
plt.figure(figsize=(10, 5))
plt.bar(bt["time_bin"], bt["total_volume"])
plt.xticks(rotation=90)
plt.title("Top Network Time Bins by Total Volume")
plt.xlabel("Time Bin")
plt.ylabel("Total Vehicles")
plt.tight_layout()
plt.savefig(GRAPH_DIR / "busiest_time_bins.png", dpi=160)
plt.close()

# 7. Growth sites
g15 = growth.head(15).copy()
g15["label"] = g15.apply(
    lambda r: f"{int(r['scats_site'])} - {str(r['site_name'])[:28]}",
    axis=1
)
plt.figure(figsize=(14, 8))
plt.barh(g15["label"], g15["absolute_change"])
plt.gca().invert_yaxis()
plt.title("Top 15 Growth Sites (Absolute Change)")
plt.xlabel("Absolute Change in Vehicles")
plt.ylabel("SCATS Site")
plt.tight_layout()
plt.savefig(GRAPH_DIR / "top_growth_sites.png", dpi=160)
plt.close()

# 8. Decline sites
d15 = decline.head(15).copy()
d15["label"] = d15.apply(
    lambda r: f"{int(r['scats_site'])} - {str(r['site_name'])[:28]}",
    axis=1
)
plt.figure(figsize=(14, 8))
plt.barh(d15["label"], d15["absolute_change"])
plt.gca().invert_yaxis()
plt.title("Top 15 Decline Sites (Absolute Change)")
plt.xlabel("Absolute Change in Vehicles")
plt.ylabel("SCATS Site")
plt.tight_layout()
plt.savefig(GRAPH_DIR / "top_decline_sites.png", dpi=160)
plt.close()

# 9. Traffic share summary
share_labels = ["AM Peak", "PM Peak", "Overnight", "Before 9 AM", "After 6 PM"]
share_values = [am_peak_pct, pm_peak_pct, overnight_pct, before_9am_pct, after_6pm_pct]
plt.figure(figsize=(10, 5))
plt.bar(share_labels, share_values)
plt.title("Selected Traffic Share Measures")
plt.ylabel("Percent of Total Volume")
plt.xticks(rotation=15)
plt.tight_layout()
plt.savefig(GRAPH_DIR / "traffic_share_summary.png", dpi=160)
plt.close()

# 10. Geographic hotspot map
map_df = top_sites_clean.dropna(subset=["latitude", "longitude"]).head(20).copy()

plt.figure(figsize=(10, 8))
plt.scatter(map_df["longitude"], map_df["latitude"], s=80)
for _, r in map_df.iterrows():
    plt.annotate(
        f"{int(r['scats_site'])}",
        (r["longitude"], r["latitude"]),
        xytext=(4, 4),
        textcoords="offset points",
        fontsize=8
    )
plt.title("Top 20 Loaded SCATS Hotspots by Location")
plt.xlabel("Longitude")
plt.ylabel("Latitude")
plt.tight_layout()
plt.savefig(GRAPH_DIR / "top_20_sites_map.png", dpi=160)
plt.close()

# 11. Geographic hotspot map with names in ranking order
geo_table = map_df[["scats_site", "site_name", "latitude", "longitude", "total_volume"]].copy()
geo_table = geo_table.sort_values("total_volume", ascending=False)

# ----------------------------
# BUILD HTML
# ----------------------------
top_line = (
    f"The current cleaned SCATS archive already shows a large, credible city-scale signal: "
    f"{fmt_int(cleaned_rows)} cleaned 15-minute observations across {fmt_int(distinct_sites)} sites, "
    f"covering {min_date} to {max_date}, with {fmt_int(cleaned_total_volume)} total vehicles counted."
)

prelim_note = (
    "This page is preliminary. More years remain to be loaded, and failed CSV files still need to be imported "
    "and reconciled before this becomes media-ready."
)

html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Melbourne SCATS Preliminary Traffic Analysis | Spotswood Trailers</title>
  <meta name="description" content="Preliminary Melbourne SCATS traffic analysis with PNG graphs, site names, and geographic hotspot mapping.">
  <style>
    :root{{
      --bg:#f3f3f3;
      --surface:#ffffff;
      --surface-soft:#f7f9fc;
      --border:#dbe3ef;
      --text:#333;
      --muted:#5d6b7c;
      --brand:#007bff;
      --brand-dark:#0a66d1;
      --brand-soft:#eef7ff;
      --accent:#b00020;
      --shadow:0 4px 16px rgba(0,0,0,.06);
      --radius:14px;
      --radius-lg:18px;
      --max:1280px;
    }}
    *{{box-sizing:border-box}}
    body{{margin:0;font-family:Arial,sans-serif;background:var(--bg);color:var(--text);line-height:1.55}}
    a{{color:#1e90ff;text-decoration:none}}
    a:hover{{text-decoration:underline}}
    header{{text-align:center;padding:40px 20px 24px;background:#fff;border-bottom:1px solid #e6e6e6}}
    .hero-button{{display:inline-flex;align-items:center;gap:10px;padding:14px 22px;background:var(--accent);color:#fff;font-size:1.02rem;font-weight:700;border-radius:12px;text-decoration:none;box-shadow:0 6px 18px rgba(0,0,0,.2)}}
    .hero-button:hover{{background:#92001a;text-decoration:none}}
    .button-row{{display:flex;gap:14px;flex-wrap:wrap;justify-content:center;margin-top:20px}}
    .secondary-btn{{display:inline-block;background:var(--brand);color:#fff;padding:12px 18px;border-radius:10px;text-decoration:none;font-weight:bold;box-shadow:0 3px 10px rgba(0,0,0,.08)}}
    .secondary-btn:hover{{background:var(--brand-dark);text-decoration:none}}
    .page{{max-width:var(--max);margin:28px auto 60px;padding:0 16px}}
    .hero-card,.card,.toc-card,.note,.summary-box{{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);box-shadow:var(--shadow)}}
    .hero-card{{padding:28px;margin-bottom:20px}}
    .toc-card{{padding:18px 20px;margin-bottom:20px}}
    .note,.summary-box{{padding:18px 20px;margin:20px 0}}
    .note{{background:var(--brand-soft);border-left:6px solid var(--brand);border-top-left-radius:8px;border-bottom-left-radius:8px}}
    .summary-box{{background:#fffbe6;border-color:#e0d18c}}
    .metric-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px;margin:20px 0 28px}}
    .metric-card{{background:var(--surface-soft);border:1px solid var(--border);border-radius:12px;padding:18px;box-shadow:0 2px 6px rgba(0,0,0,.04)}}
    .metric-card h3{{margin:0 0 8px 0;font-size:.95rem;color:#1d3c6a}}
    .metric-card p{{margin:0;font-size:1.25rem;font-weight:bold}}
    .card{{padding:18px;overflow:hidden;margin-bottom:18px}}
    .toc-list{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px 18px;margin:0;padding-left:18px}}
    .chart-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin-top:14px}}
    .chart-card{{background:var(--surface-soft);border:1px solid var(--border);border-radius:14px;padding:14px;box-shadow:0 2px 6px rgba(0,0,0,.04)}}
    .chart-card h3{{margin:0 0 8px;font-size:1.02rem;color:#16395f}}
    .chart-card p{{margin:0 0 12px;color:var(--muted);font-size:14px;line-height:1.45}}
    .chart-card img{{display:block;width:100%;height:auto;border-radius:10px;border:1px solid var(--border);background:#fff}}
    .table-wrap{{overflow-x:auto;border:1px solid var(--border);border-radius:12px;background:#fff}}
    table{{width:100%;border-collapse:collapse;font-size:13px;min-width:760px}}
    th,td{{padding:9px 8px;border-bottom:1px solid #e9eef4;text-align:left;vertical-align:top;white-space:nowrap}}
    th{{background:#f4f7fb;text-transform:uppercase;font-size:11px;color:#536476;letter-spacing:.08em}}
    tbody tr:nth-child(even){{background:#fcfdff}}
    tbody tr:hover{{background:#f4f9ff}}
    .footer-note{{text-align:center;color:var(--muted);font-size:12px;margin-top:26px}}
    @media (max-width:900px){{ .chart-grid{{grid-template-columns:1fr}} }}
    @media (max-width:760px){{ .toc-list{{grid-template-columns:1fr}} .secondary-btn{{width:100%;text-align:center}} .button-row{{align-items:stretch}} }}
  </style>
</head>
<body>
  <header>
    <div style="margin:24px auto 10px; display:flex; justify-content:center;">
      <a href="#" class="hero-button">📊 Melbourne SCATS Preliminary Analysis</a>
    </div>
    <h1>Melbourne SCATS Preliminary Traffic Analysis</h1>
    <p><em>Early cleaned-output page with PNG graphs, site names, coordinates and geographic hotspot context.</em></p>
    <div class="button-row">
      <a href="#visual-analysis" class="secondary-btn">View Charts</a>
      <a href="#headline-metrics" class="secondary-btn">View Headline Metrics</a>
      <a href="#geography" class="secondary-btn">View Hotspot Geography</a>
    </div>
  </header>

  <div class="page">
    <section class="hero-card">
      <h2 style="margin-top:0;">About this page</h2>
      <p>{html.escape(top_line)}</p>
      <p><strong>Generated at:</strong> {generated_at}</p>
      <div class="summary-box">
        <strong>Top-line reading:</strong><br>
        The current cleaned SCATS archive is already large enough to show meaningful city-scale structure, and now also has enough linked site metadata to begin showing where the busiest currently loaded hotspots sit geographically.
      </div>
      <div class="note">
        <strong>Important preliminary note:</strong> {html.escape(prelim_note)}
      </div>
    </section>

    <section class="summary-box">
      <h2 style="margin-top:0;">5 Key Takeaways</h2>
      <ul>
        <li>The cleaned archive already contains <strong>{fmt_int(cleaned_rows)}</strong> usable 15-minute observations across <strong>{fmt_int(distinct_sites)}</strong> sites.</li>
        <li>The current loaded date range is <strong>{min_date}</strong> to <strong>{max_date}</strong>.</li>
        <li>The busiest currently loaded intersection is <strong>SCATS site {top_site}</strong> — <strong>{html.escape(top_site_name)}</strong>.</li>
        <li>The quietest currently loaded intersection is <strong>SCATS site {quiet_site}</strong> — <strong>{html.escape(quiet_site_name)}</strong>.</li>
        <li>The page now links volume rankings to names and coordinates, making the early hotspot geography much easier to interpret.</li>
      </ul>
    </section>

    <section class="toc-card">
      <h2>Jump to section</h2>
      <ul class="toc-list">
        <li><a href="#headline-metrics">Headline Metrics</a></li>
        <li><a href="#visual-analysis">Visual Analysis</a></li>
        <li><a href="#priority-findings">Priority Findings</a></li>
        <li><a href="#geography">Geographic Hotspots</a></li>
        <li><a href="#busiest-sites">Busiest Sites</a></li>
        <li><a href="#growth">Growth and Decline</a></li>
        <li><a href="#reliability">Predictability and Variability</a></li>
        <li><a href="#limitations">Data Confidence and Limitations</a></li>
      </ul>
    </section>

    <section id="headline-metrics">
      <h2>Headline Metrics</h2>
      <div class="metric-grid">
        <div class="metric-card"><h3>Cleaned Rows</h3><p>{fmt_int(cleaned_rows)}</p></div>
        <div class="metric-card"><h3>Distinct Sites</h3><p>{fmt_int(distinct_sites)}</p></div>
        <div class="metric-card"><h3>Date Range Start</h3><p>{min_date}</p></div>
        <div class="metric-card"><h3>Date Range End</h3><p>{max_date}</p></div>
        <div class="metric-card"><h3>Total Cleaned Volume</h3><p>{fmt_int(cleaned_total_volume)}</p></div>
        <div class="metric-card"><h3>Busiest Site</h3><p>{top_site}</p></div>
        <div class="metric-card"><h3>Busiest Site Name</h3><p>{html.escape(top_site_name)}</p></div>
        <div class="metric-card"><h3>Quietest Site</h3><p>{quiet_site}</p></div>
        <div class="metric-card"><h3>Quietest Site Name</h3><p>{html.escape(quiet_site_name)}</p></div>
        <div class="metric-card"><h3>Busiest Time</h3><p>{html.escape(busiest_time)}</p></div>
        <div class="metric-card"><h3>Quietest Time</h3><p>{html.escape(quietest_time)}</p></div>
        <div class="metric-card"><h3>Busiest Day</h3><p>{busiest_day}</p></div>
        <div class="metric-card"><h3>Quietest Day</h3><p>{quietest_day}</p></div>
        <div class="metric-card"><h3>AM Peak Share</h3><p>{fmt_pct(am_peak_pct)}</p></div>
        <div class="metric-card"><h3>PM Peak Share</h3><p>{fmt_pct(pm_peak_pct)}</p></div>
      </div>
    </section>

    <section class="card" id="visual-analysis">
      <h2>Visual Analysis</h2>
      <div class="summary-box">
        <strong>Quick visual takeaway:</strong><br>
        The current charts already show a believable city-wide movement signature, and the addition of site metadata now starts to tie that movement back to named locations on the ground.
      </div>
      <div class="chart-grid">
        {image_card("Daily Traffic Volume (Network Wide)", "This chart shows the network-wide daily traffic signature across the currently loaded cleaned SCATS archive.", "daily_volume_timeseries.png")}
        {image_card("Network Traffic Profile by Time of Day", "This chart shows how Melbourne moves across the day, including morning build-up and the stronger later-day demand wave.", "network_time_profile.png")}
        {image_card("Top 20 SCATS Sites by Total Volume", "This ranking now includes site names in the PNG labels, making the heaviest currently loaded hotspots much easier to recognise.", "top_20_sites_bar_chart.png")}
        {image_card("Weekday vs Weekend Average Daily Volume", "This chart quantifies the structural split between weekday and weekend network usage.", "weekday_vs_weekend.png")}
        {image_card("Monday vs Friday Average Daily Volume", "This chart compares two important commuter bookend days in the current cleaned archive.", "monday_vs_friday.png")}
        {image_card("Top Network Time Bins by Total Volume", "This chart shows the heaviest repeating 15-minute demand windows across the network.", "busiest_time_bins.png")}
        {image_card("Top 15 Growth Sites", "This chart shows the strongest currently observed site-level growth results in absolute terms.", "top_growth_sites.png")}
        {image_card("Top 15 Decline Sites", "This chart shows the largest currently observed site-level declines in absolute terms.", "top_decline_sites.png")}
        {image_card("Selected Traffic Share Measures", "This chart summarizes how much of total network volume falls into selected traffic windows.", "traffic_share_summary.png")}
      </div>
    </section>

    <section class="card" id="geography">
      <h2>Geographic Hotspots</h2>
      <p>
        One of the most useful upgrades in this preliminary page is the addition of site names and coordinates.
        That means the current top-volume rankings are no longer just abstract SCATS site numbers — they now begin
        to show where the busiest loaded hotspots sit geographically.
      </p>
      <div class="chart-grid">
        {image_card("Top 20 Loaded SCATS Hotspots by Location", "This PNG map places the top 20 currently loaded SCATS sites by volume onto a simple latitude/longitude scatter, making the current hotspot geography much easier to read.", "top_20_sites_map.png")}
      </div>
      <h3 style="margin-top:22px;">Top loaded hotspot locations</h3>
      {table_html(geo_table, 20)}
    </section>

    <section class="card" id="priority-findings">
      <h2>Priority Findings</h2>
      <ul>
        <li><strong>Busiest currently loaded intersection:</strong> site {top_site} — <strong>{html.escape(top_site_name)}</strong> — with <strong>{fmt_int(top_site_volume)}</strong> vehicles.</li>
        <li><strong>Quietest currently loaded intersection:</strong> site {quiet_site} — <strong>{html.escape(quiet_site_name)}</strong> — with <strong>{fmt_int(quiet_site_volume)}</strong> vehicles.</li>
        <li><strong>Weekday vs weekend:</strong> weekdays average <strong>{fmt_int(ww.get("Weekday", float("nan")))}</strong> vehicles/day versus <strong>{fmt_int(ww.get("Weekend", float("nan")))}</strong> on weekends.</li>
        <li><strong>Monday vs Friday:</strong> Mondays average <strong>{fmt_int(mf.get("Monday", float("nan")))}</strong> versus <strong>{fmt_int(mf.get("Friday", float("nan")))}</strong> on Fridays.</li>
        <li><strong>Strongest average site-specific 15-minute peak:</strong> site <strong>{peak_site_top}</strong> at <strong>{html.escape(peak_site_time)}</strong> with average 15-minute flow <strong>{fmt_float(peak_site_avg, 2)}</strong>.</li>
        <li><strong>Fastest currently observed growth site:</strong> site <strong>{top_growth_site}</strong> — <strong>{html.escape(top_growth_name)}</strong> — with absolute change of <strong>{fmt_int(top_growth_abs)}</strong>.</li>
        <li><strong>Largest currently observed decline site:</strong> site <strong>{top_decline_site}</strong> — <strong>{html.escape(top_decline_name)}</strong> — with absolute change of <strong>{fmt_int(top_decline_abs)}</strong>.</li>
        <li><strong>Most predictable currently loaded site:</strong> <strong>{most_predictable_site}</strong> — <strong>{html.escape(most_predictable_name)}</strong> — with coefficient of variation <strong>{fmt_float(most_predictable_cv, 4)}</strong>.</li>
        <li><strong>Most variable currently loaded site:</strong> <strong>{most_variable_site}</strong> — <strong>{html.escape(most_variable_name)}</strong> — with coefficient of variation <strong>{fmt_float(most_variable_cv, 4)}</strong>.</li>
      </ul>
    </section>

    <section class="card" id="busiest-sites">
      <h2>Busiest Sites</h2>
      <p>The table below now includes site names and coordinates where available.</p>
      {table_html(busiest_sites, 20)}
    </section>

    <section class="card" id="growth">
      <h2>Growth and Decline</h2>
      <p>This section is preliminary and compares the first loaded year with the last loaded year currently available in the cleaned archive.</p>
      <h3>Top 20 growth sites</h3>
      {table_html(growth, 20)}
      <h3 style="margin-top:22px;">Top 20 decline sites</h3>
      {table_html(decline, 20)}
    </section>

    <section class="card" id="reliability">
      <h2>Predictability and Variability</h2>
      <h3>Most predictable sites</h3>
      {table_html(predictable, 20)}
      <h3 style="margin-top:22px;">Most variable sites</h3>
      {table_html(variable, 20)}
    </section>

    <section class="note" id="limitations">
      <h2 style="margin-top:0;">Data Confidence and Limitations</h2>
      <ul>
        <li>The current cleaned archive covers <strong>{min_date}</strong> to <strong>{max_date}</strong>, but is still incomplete relative to the intended final SCATS database.</li>
        <li>More years remain to be loaded.</li>
        <li>Failed CSV files still need to be imported and reconciled.</li>
        <li>Any rankings or strongest/quietest claims on this page should be treated as <strong>preliminary</strong>.</li>
        <li>The addition of site metadata improves interpretability, but not all final network geography questions can be answered until the full archive is loaded.</li>
      </ul>
    </section>

    <div class="footer-note">
      Generated automatically from cleaned SCATS CSV outputs and site metadata on {generated_at}.
    </div>
  </div>
</body>
</html>
"""

OUT_HTML.write_text(html_doc, encoding="utf-8")

print(f"Page written to: {OUT_HTML}")
print(f"Graphs written to: {GRAPH_DIR}")