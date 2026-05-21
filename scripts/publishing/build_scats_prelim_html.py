from pathlib import Path
from datetime import datetime
import html
import math
import pandas as pd

BASE = Path(r"A:\TrafficAnalytics\PROJECTS\reports")
PRIORITY = BASE / "scats_priority_answers"
CLEAN = BASE / "scats_clean_outputs_v2"
VISUALS = CLEAN / "visuals"

OUT_HTML = BASE / "scats_preliminary_report.html"

def read_csv(name: str, folder: Path) -> pd.DataFrame:
    path = folder / name
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

def format_date_series(v):
    return pd.to_datetime(v).dt.strftime("%Y-%m-%d")

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
    body = "".join(rows)
    return f"""
    <div class="table-wrap">
      <table>
        <thead><tr>{headers}</tr></thead>
        <tbody>{body}</tbody>
      </table>
    </div>
    """

def image_card(title: str, description: str, filename: str) -> str:
    img_path = VISUALS / filename
    if not img_path.exists():
        return ""
    rel = img_path.as_posix()
    return f"""
    <div class="chart-card">
      <h3>{html.escape(title)}</h3>
      <p>{html.escape(description)}</p>
      <a href="{rel}" target="_blank">
        <img src="{rel}" alt="{html.escape(title)}">
      </a>
    </div>
    """

# Load core outputs
dataset_summary = read_csv("01_dataset_summary.csv", PRIORITY)
busiest_sites = read_csv("02_busiest_intersections_top_100.csv", PRIORITY)
quietest_sites = read_csv("03_quietest_intersections_bottom_100.csv", PRIORITY)
busiest_times = read_csv("04_busiest_time_of_day_network.csv", PRIORITY)
quietest_times = read_csv("05_quietest_time_of_day_network.csv", PRIORITY)
busiest_days = read_csv("06_busiest_days_top_100.csv", PRIORITY)
quietest_days = read_csv("07_quietest_days_bottom_100.csv", PRIORITY)
weekday_weekend = read_csv("08_weekday_vs_weekend_network.csv", PRIORITY)
monday_friday = read_csv("09_monday_vs_friday_network.csv", PRIORITY)
peak_site = read_csv("10_peak_15min_period_each_site_top_100_by_peak.csv", PRIORITY)
growth = read_csv("16_fastest_growth_sites_top_100.csv", PRIORITY)
decline = read_csv("17_biggest_decline_sites_bottom_100.csv", PRIORITY)
predictable = read_csv("18_most_predictable_sites_top_100.csv", PRIORITY)
variable = read_csv("19_most_variable_sites_top_100.csv", PRIORITY)
shares = read_csv("20_peak_offpeak_overnight_shares_network.csv", PRIORITY)

clean_row_count = read_csv("01_cleaned_row_count.csv", CLEAN)
clean_total = read_csv("02_cleaned_total_volume.csv", CLEAN)
clean_date_range = read_csv("03_cleaned_date_range.csv", CLEAN)
daily_totals = read_csv("04_daily_total_volume.csv", CLEAN)
top_sites_clean = read_csv("05_top_100_sites_by_total_volume.csv", CLEAN)

# Extract headline values
summary_row = dataset_summary.iloc[0]
cleaned_rows = int(summary_row["cleaned_rows"])
distinct_sites = int(summary_row["distinct_sites"])
min_date = pd.to_datetime(summary_row["min_date"]).strftime("%Y-%m-%d")
max_date = pd.to_datetime(summary_row["max_date"]).strftime("%Y-%m-%d")
cleaned_total_volume = int(summary_row["cleaned_total_volume"])

top_site = int(busiest_sites.iloc[0]["scats_site"])
top_site_volume = int(busiest_sites.iloc[0]["total_volume"])
quiet_site = int(quietest_sites.iloc[0]["scats_site"])
quiet_site_volume = int(quietest_sites.iloc[0]["total_volume"])

busiest_time = str(busiest_times.iloc[0]["time_bin"])
busiest_time_volume = int(busiest_times.iloc[0]["total_volume"])
quietest_time = str(quietest_times.iloc[0]["time_bin"])
quietest_time_volume = int(quietest_times.iloc[0]["total_volume"])

busiest_day = pd.to_datetime(busiest_days.iloc[0]["count_date"]).strftime("%Y-%m-%d")
busiest_day_volume = int(busiest_days.iloc[0]["total_volume"])
quietest_day = pd.to_datetime(quietest_days.iloc[0]["count_date"]).strftime("%Y-%m-%d")
quietest_day_volume = int(quietest_days.iloc[0]["total_volume"])

ww = {
    row["day_type"]: float(row["avg_daily_volume"])
    for _, row in weekday_weekend.iterrows()
}
mf = {
    row["day_name"]: float(row["avg_daily_volume"])
    for _, row in monday_friday.iterrows()
}

share_row = shares.iloc[0]
am_peak_pct = float(share_row["am_peak_pct"])
pm_peak_pct = float(share_row["pm_peak_pct"])
overnight_pct = float(share_row["overnight_pct"])
before_9am_pct = float(share_row["before_9am_pct"])
after_6pm_pct = float(share_row["after_6pm_pct"])

top_growth_site = int(growth.iloc[0]["scats_site"])
top_growth_abs = int(growth.iloc[0]["absolute_change"])
top_growth_pct = growth.iloc[0]["pct_change"]

top_decline_site = int(decline.iloc[0]["scats_site"])
top_decline_abs = int(decline.iloc[0]["absolute_change"])
top_decline_pct = decline.iloc[0]["pct_change"]

most_predictable_site = int(predictable.iloc[0]["scats_site"])
most_predictable_cv = predictable.iloc[0]["cv"]
most_variable_site = int(variable.iloc[0]["scats_site"])
most_variable_cv = variable.iloc[0]["cv"]

peak_site_top = int(peak_site.iloc[0]["scats_site"])
peak_site_time = str(peak_site.iloc[0]["peak_time_bin"])
peak_site_avg = float(peak_site.iloc[0]["avg_peak_15m_volume"])

generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Explanatory text
top_line = (
    f"The current cleaned SCATS archive already shows a large, credible city-scale signal: "
    f"{fmt_int(cleaned_rows)} cleaned 15-minute observations across {fmt_int(distinct_sites)} sites, "
    f"covering {min_date} to {max_date}, with {fmt_int(cleaned_total_volume)} total vehicles counted."
)

prelim_note = (
    "This page is preliminary. More years remain to be loaded, and failed CSV files still need to be imported "
    "and reconciled before this becomes media-ready."
)

what_it_shows = (
    "Even in preliminary form, the cleaned dataset already answers high-value public-interest questions about "
    "how Melbourne moves: the busiest intersections, the busiest and quietest times of day, the busiest and "
    "quietest days, weekday versus weekend structure, and which locations appear to be growing or declining fastest."
)

daily_chart_note = (
    "The daily network-wide series already shows a believable city-scale rhythm: strong weekday/weekend oscillation, "
    "growth through the pre-COVID years, a pronounced COVID-era shock, and recovery thereafter. Any abrupt linear "
    "segments or isolated visual discontinuities should be treated as possible partial-coverage artefacts pending "
    "full ingestion of missing and failed files."
)

timeofday_note = (
    "The network time-of-day profile shows Melbourne waking up rapidly from the early morning, building into a clear "
    "morning peak, staying elevated through the middle of the day, and then pushing into an even stronger late-afternoon "
    "to early-evening peak before tapering off overnight."
)

topsites_note = (
    "The top-site ranking identifies the SCATS locations carrying the largest accumulated volumes across the currently "
    "loaded archive. These are not yet the final all-years rankings, but they are already useful as an early map of "
    "network pressure points."
)

html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Melbourne SCATS Preliminary Traffic Analysis | Spotswood Trailers</title>
  <meta name="description" content="Preliminary Melbourne SCATS traffic analysis using cleaned SCATS data, early charts, and initial high-value findings.">
  <meta name="author" content="Clarke Towson Spotswood Trailers - INTJ Billing Pty Ltd">
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
    body{{
      margin:0;
      font-family:Arial,sans-serif;
      background:var(--bg);
      color:var(--text);
      line-height:1.55;
    }}
    a{{color:#1e90ff;text-decoration:none}}
    a:hover{{text-decoration:underline}}
    header{{
      text-align:center;
      padding:40px 20px 24px;
      background:#fff;
      border-bottom:1px solid #e6e6e6;
    }}
    .hero-button{{
      display:inline-flex;
      align-items:center;
      gap:10px;
      padding:14px 22px;
      background:var(--accent);
      color:#fff;
      font-size:1.02rem;
      font-weight:700;
      border-radius:12px;
      text-decoration:none;
      box-shadow:0 6px 18px rgba(0,0,0,.2);
    }}
    .hero-button:hover{{background:#92001a;text-decoration:none}}
    .button-row{{
      display:flex;
      gap:14px;
      flex-wrap:wrap;
      justify-content:center;
      margin-top:20px;
    }}
    .secondary-btn{{
      display:inline-block;
      background:var(--brand);
      color:#fff;
      padding:12px 18px;
      border-radius:10px;
      text-decoration:none;
      font-weight:bold;
      box-shadow:0 3px 10px rgba(0,0,0,.08);
    }}
    .secondary-btn:hover{{background:var(--brand-dark);text-decoration:none}}
    .page{{max-width:var(--max);margin:28px auto 60px;padding:0 16px}}
    .hero-card,.card,.toc-card,.note,.summary-box{{
      background:var(--surface);
      border:1px solid var(--border);
      border-radius:var(--radius-lg);
      box-shadow:var(--shadow);
    }}
    .hero-card{{padding:28px;margin-bottom:20px}}
    .toc-card{{padding:18px 20px;margin-bottom:20px}}
    .note,.summary-box{{padding:18px 20px;margin:20px 0}}
    .note{{
      background:var(--brand-soft);
      border-left:6px solid var(--brand);
      border-top-left-radius:8px;
      border-bottom-left-radius:8px;
    }}
    .summary-box{{background:#fffbe6;border-color:#e0d18c}}
    .metric-grid{{
      display:grid;
      grid-template-columns:repeat(auto-fit,minmax(210px,1fr));
      gap:16px;
      margin:20px 0 28px;
    }}
    .metric-card{{
      background:var(--surface-soft);
      border:1px solid var(--border);
      border-radius:12px;
      padding:18px;
      box-shadow:0 2px 6px rgba(0,0,0,.04);
    }}
    .metric-card h3{{margin:0 0 8px 0;font-size:.95rem;color:#1d3c6a}}
    .metric-card p{{margin:0;font-size:1.25rem;font-weight:bold}}
    .card{{padding:18px;overflow:hidden;margin-bottom:18px}}
    .toc-list{{
      display:grid;
      grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
      gap:10px 18px;
      margin:0;
      padding-left:18px;
    }}
    .chart-grid{{
      display:grid;
      grid-template-columns:repeat(2,minmax(0,1fr));
      gap:18px;
      margin-top:14px;
    }}
    .chart-card{{
      background:var(--surface-soft);
      border:1px solid var(--border);
      border-radius:14px;
      padding:14px;
      box-shadow:0 2px 6px rgba(0,0,0,.04);
    }}
    .chart-card h3{{margin:0 0 8px;font-size:1.02rem;color:#16395f}}
    .chart-card p{{margin:0 0 12px;color:var(--muted);font-size:14px;line-height:1.45}}
    .chart-card img{{
      display:block;
      width:100%;
      height:auto;
      border-radius:10px;
      border:1px solid var(--border);
      background:#fff;
    }}
    .table-wrap{{overflow-x:auto;border:1px solid var(--border);border-radius:12px;background:#fff}}
    table{{width:100%;border-collapse:collapse;font-size:13px;min-width:760px}}
    th,td{{padding:9px 8px;border-bottom:1px solid #e9eef4;text-align:left;vertical-align:top;white-space:nowrap}}
    th{{background:#f4f7fb;text-transform:uppercase;font-size:11px;color:#536476;letter-spacing:.08em}}
    tbody tr:nth-child(even){{background:#fcfdff}}
    tbody tr:hover{{background:#f4f9ff}}
    .footer-note{{text-align:center;color:var(--muted);font-size:12px;margin-top:26px}}
    @media (max-width:900px){{ .chart-grid{{grid-template-columns:1fr}} }}
    @media (max-width:760px){{
      header{{padding:28px 16px 18px}}
      .hero-card{{padding:20px}}
      .page{{padding:0 10px}}
      .toc-list{{grid-template-columns:1fr}}
      .secondary-btn{{width:100%;text-align:center}}
      .button-row{{align-items:stretch}}
    }}
  </style>
</head>
<body>
  <header>
    <div style="margin:24px auto 10px; display:flex; justify-content:center;">
      <a href="#" class="hero-button">📊 Melbourne SCATS Preliminary Analysis</a>
    </div>
    <h1>Melbourne SCATS Preliminary Traffic Analysis</h1>
    <p><em>Early cleaned-output page generated from the SCATS database using the same broad public-page styling pattern as the uploaded Spotswood Trailers analysis page.</em></p>
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
      <p>{html.escape(what_it_shows)}</p>
      <div class="summary-box">
        <strong>Top-line reading:</strong><br>
        Melbourne’s current cleaned SCATS archive is already large enough to show meaningful city-scale structure, but this page should still be treated as an <strong>early analytical preview</strong> rather than a final public release.
      </div>
      <div class="note">
        <strong>Important preliminary note:</strong> {html.escape(prelim_note)}
      </div>
    </section>

    <section class="summary-box" id="five-key-takeaways">
      <h2 style="margin-top:0;">5 Key Takeaways</h2>
      <ul>
        <li>The cleaned archive already contains <strong>{fmt_int(cleaned_rows)}</strong> usable 15-minute observations across <strong>{fmt_int(distinct_sites)}</strong> SCATS sites.</li>
        <li>The current loaded date range is <strong>{min_date}</strong> to <strong>{max_date}</strong>, which is substantial but still incomplete for the full intended archive.</li>
        <li>The busiest currently loaded intersection by total volume is <strong>SCATS site {top_site}</strong>, with <strong>{fmt_int(top_site_volume)}</strong> vehicles across the loaded period.</li>
        <li>The busiest network time-of-day is currently <strong>{html.escape(busiest_time)}</strong>, while the quietest is <strong>{html.escape(quietest_time)}</strong>.</li>
        <li>The charts already show believable network-wide structure, including weekday/weekend rhythm, long-run growth before COVID, and a major COVID-era disruption.</li>
      </ul>
    </section>

    <section class="card" id="why-it-matters">
      <h2>Why This Matters</h2>
      <p>
        This is not yet the final SCATS story. But even this preliminary stage is already useful because it starts answering
        high-value public questions: where Melbourne’s heaviest traffic pressure appears to sit, what time of day carries the
        most demand, how weekday and weekend movement differ, and how the network changed across the loaded historical window.
      </p>
      <p>
        In practical terms, this is the first stage of converting a very large SCATS archive into something readable by journalists,
        decision-makers and the public. The point of this page is to show that the pipeline is working, the charts are believable,
        and the early findings are already significant — while also being upfront about the fact that more ingestion and cleanup
        work remains before publication-grade claims should be made.
      </p>
    </section>

    <section class="toc-card">
      <h2>Jump to section</h2>
      <ul class="toc-list">
        <li><a href="#headline-metrics">Headline Metrics</a></li>
        <li><a href="#visual-analysis">Visual Analysis</a></li>
        <li><a href="#priority-findings">Priority Findings</a></li>
        <li><a href="#busiest-sites">Busiest Sites</a></li>
        <li><a href="#busiest-days">Busiest and Quietest Days</a></li>
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
        {image_card("Daily Traffic Volume (Network Wide)", daily_chart_note, "daily_volume_timeseries.png")}
        {image_card("Network Traffic Profile by Time of Day", timeofday_note, "network_time_profile.png")}
        {image_card("Top 20 SCATS Sites by Total Volume", topsites_note, "top_20_sites_bar_chart.png")}
      </div>
    </section>

    <section class="card" id="priority-findings">
      <h2>Priority Findings</h2>
      <ul>
        <li><strong>Busiest currently loaded intersection:</strong> site {top_site} with <strong>{fmt_int(top_site_volume)}</strong> vehicles.</li>
        <li><strong>Quietest currently loaded intersection:</strong> site {quiet_site} with <strong>{fmt_int(quiet_site_volume)}</strong> vehicles.</li>
        <li><strong>Busiest network time-of-day:</strong> <strong>{html.escape(busiest_time)}</strong> with cumulative volume <strong>{fmt_int(busiest_time_volume)}</strong>.</li>
        <li><strong>Quietest network time-of-day:</strong> <strong>{html.escape(quietest_time)}</strong> with cumulative volume <strong>{fmt_int(quietest_time_volume)}</strong>.</li>
        <li><strong>Busiest currently loaded day:</strong> <strong>{busiest_day}</strong> with <strong>{fmt_int(busiest_day_volume)}</strong> vehicles.</li>
        <li><strong>Quietest currently loaded day:</strong> <strong>{quietest_day}</strong> with <strong>{fmt_int(quietest_day_volume)}</strong> vehicles.</li>
        <li><strong>Weekday vs weekend:</strong> weekdays average <strong>{fmt_int(ww.get("Weekday", float("nan")))}</strong> vehicles/day versus <strong>{fmt_int(ww.get("Weekend", float("nan")))}</strong> on weekends.</li>
        <li><strong>Monday vs Friday:</strong> Mondays average <strong>{fmt_int(mf.get("Monday", float("nan")))}</strong> versus <strong>{fmt_int(mf.get("Friday", float("nan")))}</strong> on Fridays.</li>
        <li><strong>Strongest average site-specific 15-minute peak in the current results:</strong> site <strong>{peak_site_top}</strong> at <strong>{html.escape(peak_site_time)}</strong> with average 15-minute flow <strong>{fmt_float(peak_site_avg, 2)}</strong>.</li>
      </ul>
    </section>

    <section class="card" id="busiest-sites">
      <h2>Busiest Sites</h2>
      <p>The table below shows the highest-volume SCATS sites in the currently loaded archive. These are preliminary rankings based only on the years currently loaded and cleaned.</p>
      {table_html(busiest_sites, 20)}
    </section>

    <section class="card">
      <h2>Quietest Sites</h2>
      <p>This table shows the lowest-volume SCATS sites in the currently loaded archive. These may include lightly used locations, partial-period sites, or locations whose lower totals reflect incomplete historical coverage.</p>
      {table_html(quietest_sites, 20)}
    </section>

    <section class="card" id="busiest-days">
      <h2>Busiest and Quietest Days</h2>
      <p>The loaded archive already shows extreme day-to-day variation. Some of that is genuine city behaviour, while some of it may still reflect partial-coverage days that will be improved as failed files are ingested.</p>
      <h3>Top 20 busiest days</h3>
      {table_html(busiest_days, 20)}
      <h3 style="margin-top:22px;">Top 20 quietest days</h3>
      {table_html(quietest_days, 20)}
    </section>

    <section class="card" id="growth">
      <h2>Growth and Decline</h2>
      <div class="note">
        These growth rankings are preliminary. They compare the first loaded year against the last loaded year currently present in the cleaned archive, not yet the final full-history ingest.
      </div>
      <p><strong>Fastest growth site in the current outputs:</strong> site {top_growth_site} with absolute growth of <strong>{fmt_int(top_growth_abs)}</strong> vehicles and percentage change of <strong>{fmt_pct(top_growth_pct)}</strong>.</p>
      <p><strong>Largest decline site in the current outputs:</strong> site {top_decline_site} with absolute change of <strong>{fmt_int(top_decline_abs)}</strong> vehicles and percentage change of <strong>{fmt_pct(top_decline_pct)}</strong>.</p>
      <h3>Top 20 growth sites</h3>
      {table_html(growth, 20)}
      <h3 style="margin-top:22px;">Top 20 decline sites</h3>
      {table_html(decline, 20)}
    </section>

    <section class="card" id="reliability">
      <h2>Predictability and Variability</h2>
      <p>
        The current outputs also begin to answer one of the more powerful planning questions: which locations behave consistently,
        and which behave in a highly volatile way. These rankings use coefficient of variation across site-level daily totals.
      </p>
      <p><strong>Most predictable currently loaded site:</strong> {most_predictable_site} with coefficient of variation <strong>{fmt_float(most_predictable_cv, 4)}</strong>.</p>
      <p><strong>Most variable currently loaded site:</strong> {most_variable_site} with coefficient of variation <strong>{fmt_float(most_variable_cv, 4)}</strong>.</p>
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
        <li>Any rankings or “most / least” claims on this page should be treated as <strong>preliminary</strong> until the ingest is complete.</li>
        <li>The charts are already useful as proof that the pipeline is working and the traffic structure is real, but not yet the final media-ready form.</li>
      </ul>
      <p>
        This page is designed to be honest about the state of the pipeline: strong enough to show real findings now, but still early enough that final publication should wait for the remaining ingest and cleanup work.
      </p>
    </section>

    <div class="footer-note">
      Generated automatically from cleaned SCATS CSV outputs on {generated_at}.
    </div>
  </div>
</body>
</html>
"""

OUT_HTML.write_text(html_doc, encoding="utf-8")
print(f"HTML page written to: {OUT_HTML}")