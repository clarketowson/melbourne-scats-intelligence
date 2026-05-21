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
top_site_volume = int(busiest_sites.iloc[0]["total_volume"])
quiet_site = int(quietest_sites.iloc[0]["scats_site"])
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
top_growth_abs = int(growth.iloc[0]["absolute_change"])
top_decline_site = int(decline.iloc[0]["scats_site"])
top_decline_abs = int(decline.iloc[0]["absolute_change"])

most_predictable_site = int(predictable.iloc[0]["scats_site"])
most_predictable_cv = float(predictable.iloc[0]["cv"])
most_variable_site = int(variable.iloc[0]["scats_site"])
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
plt.figure(figsize=(12, 8))
plt.barh(top20["scats_site"].astype(str), top20["total_volume"])
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

# 6. Busiest times of day top 20
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

# 7. Fastest growth sites top 15
g15 = growth.head(15).copy()
plt.figure(figsize=(12, 7))
plt.barh(g15["scats_site"].astype(str), g15["absolute_change"])
plt.gca().invert_yaxis()
plt.title("Top 15 Growth Sites (Absolute Change)")
plt.xlabel("Absolute Change in Vehicles")
plt.ylabel("SCATS Site")
plt.tight_layout()
plt.savefig(GRAPH_DIR / "top_growth_sites.png", dpi=160)
plt.close()

# 8. Biggest decline sites top 15
d15 = decline.head(15).copy()
plt.figure(figsize=(12, 7))
plt.barh(d15["scats_site"].astype(str), d15["absolute_change"])
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
  <meta name="description" content="Preliminary Melbourne SCATS traffic analysis with PNG graphs and explanatory text.">
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
    <p><em>Early cleaned-output page with PNG graphs and preliminary interpretations.</em></p>
    <div class="button-row">
      <a href="#visual-analysis" class="secondary-btn">View Charts</a>
      <a href="#headline-metrics" class="secondary-btn">View Headline Metrics</a>
      <a href="#priority-findings" class="secondary-btn">View Priority Findings</a>
    </div>
  </header>

  <div class="page">
    <section class="hero-card">
      <h2 style="margin-top:0;">About this page</h2>
      <p>{html.escape(top_line)}</p>
      <p><strong>Generated at:</strong> {generated_at}</p>
      <div class="summary-box">
        <strong>Top-line reading:</strong><br>
        The current cleaned SCATS archive is already large enough to show meaningful city-scale structure, but this page should still be treated as a <strong>preliminary analytical preview</strong>.
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
        <li>The busiest currently loaded intersection is <strong>SCATS site {top_site}</strong>.</li>
        <li>The busiest network time-of-day is currently <strong>{html.escape(busiest_time)}</strong>.</li>
        <li>The charts already show believable weekday/weekend rhythm, pre-COVID growth, and a strong COVID-era shock.</li>
      </ul>
    </section>

    <section class="toc-card">
      <h2>Jump to section</h2>
      <ul class="toc-list">
        <li><a href="#headline-metrics">Headline Metrics</a></li>
        <li><a href="#visual-analysis">Visual Analysis</a></li>
        <li><a href="#priority-findings">Priority Findings</a></li>
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
        <div class="metric-card"><h3>Quietest Site</h3><p>{quiet_site}</p></div>
        <div class="metric-card"><h3>Busiest Time</h3><p>{html.escape(busiest_time)}</p></div>
        <div class="metric-card"><h3>Quietest Time</h3><p>{html.escape(quietest_time)}</p></div>
        <div class="metric-card"><h3>Busiest Day</h3><p>{busiest_day}</p></div>
        <div class="metric-card"><h3>Quietest Day</h3><p>{quietest_day}</p></div>
        <div class="metric-card"><h3>AM Peak Share</h3><p>{fmt_pct(am_peak_pct)}</p></div>
        <div class="metric-card"><h3>PM Peak Share</h3><p>{fmt_pct(pm_peak_pct)}</p></div>
        <div class="metric-card"><h3>Overnight Share</h3><p>{fmt_pct(overnight_pct)}</p></div>
        <div class="metric-card"><h3>Before 9 AM Share</h3><p>{fmt_pct(before_9am_pct)}</p></div>
      </div>
    </section>

    <section class="card" id="visual-analysis">
      <h2>Visual Analysis</h2>
      <div class="summary-box">
        <strong>Quick visual takeaway:</strong><br>
        The current charts already show a believable city-wide movement signature: a strong weekday/weekend rhythm, a pronounced morning build-up, an even stronger later-day demand wave, and a visible COVID-era break in normal behaviour.
      </div>
      <div class="chart-grid">
        {image_card("Daily Traffic Volume (Network Wide)", "This chart shows the network-wide daily traffic signature across the currently loaded cleaned SCATS archive. It already reveals strong weekday/weekend rhythm, long-run growth through the pre-COVID years, a major COVID-era shock, and subsequent recovery.", "daily_volume_timeseries.png")}
        {image_card("Network Traffic Profile by Time of Day", "This chart shows how Melbourne moves across the day. It reveals a quiet overnight period, rapid build-up through the morning, a strong daytime plateau, and a larger late-afternoon / early-evening peak.", "network_time_profile.png")}
        {image_card("Top 20 SCATS Sites by Total Volume", "This ranking shows the heaviest currently loaded SCATS sites by total accumulated traffic volume. These are preliminary rankings based on the years currently loaded and cleaned.", "top_20_sites_bar_chart.png")}
        {image_card("Weekday vs Weekend Average Daily Volume", "This chart shows the structural split between weekday and weekend movement. It helps quantify how much more strongly the network is used on working days.", "weekday_vs_weekend.png")}
        {image_card("Monday vs Friday Average Daily Volume", "This chart compares two important bookend commuter days. It helps show whether Friday behaviour appears heavier or lighter than Monday in the current cleaned archive.", "monday_vs_friday.png")}
        {image_card("Top Network Time Bins by Total Volume", "This chart shows the heaviest 15-minute network time bins across the loaded archive, helping identify the strongest repeating daily demand windows.", "busiest_time_bins.png")}
        {image_card("Top 15 Growth Sites", "This chart shows the currently strongest site-level growth results in absolute terms across the loaded archive. These remain preliminary until the full intended archive is loaded.", "top_growth_sites.png")}
        {image_card("Top 15 Decline Sites", "This chart shows the sites with the largest currently observed absolute declines across the loaded archive. Some of these results may still shift as more years and failed files are ingested.", "top_decline_sites.png")}
        {image_card("Selected Traffic Share Measures", "This chart summarizes how much of total network volume currently falls into selected windows such as AM peak, PM peak, overnight, before 9 AM, and after 6 PM.", "traffic_share_summary.png")}
      </div>
    </section>

    <section class="card" id="priority-findings">
      <h2>Priority Findings</h2>
      <ul>
        <li><strong>Busiest currently loaded intersection:</strong> site {top_site} with <strong>{fmt_int(top_site_volume)}</strong> vehicles.</li>
        <li><strong>Quietest currently loaded intersection:</strong> site {quiet_site} with <strong>{fmt_int(quiet_site_volume)}</strong> vehicles.</li>
        <li><strong>Weekday vs weekend:</strong> weekdays average <strong>{fmt_int(ww.get("Weekday", float("nan")))}</strong> vehicles/day versus <strong>{fmt_int(ww.get("Weekend", float("nan")))}</strong> on weekends.</li>
        <li><strong>Monday vs Friday:</strong> Mondays average <strong>{fmt_int(mf.get("Monday", float("nan")))}</strong> versus <strong>{fmt_int(mf.get("Friday", float("nan")))}</strong> on Fridays.</li>
        <li><strong>Strongest average site-specific 15-minute peak in the current results:</strong> site <strong>{peak_site_top}</strong> at <strong>{html.escape(peak_site_time)}</strong> with average 15-minute flow <strong>{fmt_float(peak_site_avg, 2)}</strong>.</li>
        <li><strong>Fastest currently observed growth site:</strong> site <strong>{top_growth_site}</strong> with absolute change of <strong>{fmt_int(top_growth_abs)}</strong>.</li>
        <li><strong>Largest currently observed decline site:</strong> site <strong>{top_decline_site}</strong> with absolute change of <strong>{fmt_int(top_decline_abs)}</strong>.</li>
        <li><strong>Most predictable currently loaded site:</strong> <strong>{most_predictable_site}</strong> with coefficient of variation <strong>{fmt_float(most_predictable_cv, 4)}</strong>.</li>
        <li><strong>Most variable currently loaded site:</strong> <strong>{most_variable_site}</strong> with coefficient of variation <strong>{fmt_float(most_variable_cv, 4)}</strong>.</li>
      </ul>
    </section>

    <section class="card" id="busiest-sites">
      <h2>Busiest Sites</h2>
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
        <li>The page is suitable as an early analytical preview, not yet the final media-ready release.</li>
      </ul>
    </section>

    <div class="footer-note">
      Generated automatically from cleaned SCATS CSV outputs on {generated_at}.
    </div>
  </div>
</body>
</html>
"""

OUT_HTML.write_text(html_doc, encoding="utf-8")
print(f"Page written to: {OUT_HTML}")
print(f"Graphs written to: {GRAPH_DIR}")