import pandas as pd
from pathlib import Path
from html import escape

BASE_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")

SITE_TOTALS = BASE_DIR / "site_totals.csv"
MAP_DATA = BASE_DIR / "all_scats_sites_map_data_audit.csv"

OUT_CSV = BASE_DIR / "top100_billboard_ticker.csv"
OUT_HTML = BASE_DIR / "billboard_ticker_snippet.html"

TOP_N = 100

site_totals = pd.read_csv(
    SITE_TOTALS,
    dtype={"scats_site": str},
    low_memory=False
)

map_data = pd.read_csv(
    MAP_DATA,
    dtype={"site_id": str},
    low_memory=False
)

# Keep real monthly rows only if row_type exists
if "row_type" in site_totals.columns:
    site_totals = site_totals[site_totals["row_type"].eq("data")]

# Work out the volume column
volume_col = None
for candidate in ["month_site_volume", "total_volume", "volume_24hour"]:
    if candidate in site_totals.columns:
        volume_col = candidate
        break

if volume_col is None:
    raise ValueError(f"No usable volume column found. Columns are: {list(site_totals.columns)}")

# Aggregate total volume per SCATS site
totals = (
    site_totals
    .groupby("scats_site", as_index=False)[volume_col]
    .sum()
    .rename(columns={volume_col: "total_volume"})
)

# Prepare map metadata
if "site_id" in map_data.columns:
    map_data = map_data.rename(columns={"site_id": "scats_site"})

map_data["scats_site"] = map_data["scats_site"].astype(str)
totals["scats_site"] = totals["scats_site"].astype(str)

merged = totals.merge(map_data, on="scats_site", how="left")

# Require coordinates
merged = merged[
    merged["latitude"].notna()
    & merged["longitude"].notna()
].copy()

merged = merged.sort_values("total_volume", ascending=False).head(TOP_N)

# Replace existing rank column safely
if "rank" in merged.columns:
    merged = merged.drop(columns=["rank"])

merged.insert(0, "rank", range(1, len(merged) + 1))

def pick_name(row):
    for col in [
        "friendly_name",
        "site_name",
        "site_name_from_volume_csv",
        "intersection",
        "location",
        "name",
    ]:
        if col in row.index:
            val = row.get(col)
            if pd.notna(val) and str(val).strip():
                return str(val).strip()

    return f"SCATS Site {row['scats_site']}"

merged["display_name"] = merged.apply(pick_name, axis=1)

merged["google_maps_url"] = merged.apply(
    lambda r: f"https://www.google.com/maps/search/?api=1&query={r['latitude']},{r['longitude']}",
    axis=1
)

optional_cols = [
    "municipality",
    "traffic_band",
    "region_code",
]

final_cols = [
    "rank",
    "scats_site",
    "display_name",
    "total_volume",
    "latitude",
    "longitude",
    "google_maps_url",
]

for col in optional_cols:
    if col in merged.columns:
        final_cols.append(col)

merged[final_cols].to_csv(OUT_CSV, index=False)

items = []

def humanize_volume(v):
    if v >= 1_000_000:
        return f"{v / 1_000_000:.2f}M vehicle movements"
    elif v >= 1_000:
        return f"{v / 1_000:.2f}K vehicle movements"
    return f"{int(v)} vehicle movements"

for _, r in merged.iterrows():
    name = escape(str(r["display_name"]).upper())
    volume = humanize_volume(r["total_volume"])
    url = escape(str(r["google_maps_url"]))

    items.append(
        f'''<a class="billboard-ticker-item" href="{url}" target="_blank" rel="noopener">
  <span class="ticker-rank">#{int(r["rank"])}</span>
  <span class="ticker-name">{name}</span>
  <span class="ticker-volume">{volume}</span>
  <span class="ticker-separator">●</span>
</a>'''
    )

ticker_items = "\n".join(items)

html = f'''
<!-- Bloomberg Style Billboard Opportunity Ticker -->
<section class="billboard-ticker-section" id="billboard-opportunity-ticker">

  <div class="billboard-ticker-topbar">
    <span class="ticker-live-dot"></span>
    MELBOURNE TRAFFIC EXPOSURE TERMINAL
  </div>

  <div class="billboard-ticker-header">
    TOP 100 SCATS LOCATIONS RANKED BY VEHICLE MOVEMENTS
  </div>

  <div class="billboard-ticker-wrap">
    <div class="billboard-ticker-track">
      {ticker_items}
      {ticker_items}
    </div>
  </div>

</section>

<style>

.billboard-ticker-section {{
    margin: 28px 0;
    background: #000000;
    border: 1px solid #222;
    overflow: hidden;
    box-shadow:
        0 0 20px rgba(255,140,0,0.08),
        0 0 60px rgba(255,140,0,0.03);
    font-family:
        "Arial Narrow",
        Arial,
        sans-serif;
}}

.billboard-ticker-topbar {{
    background: #ff7b00;
    color: #000;
    font-weight: 800;
    font-size: 12px;
    letter-spacing: 1px;
    padding: 6px 14px;
    display: flex;
    align-items: center;
    gap: 8px;
}}

.ticker-live-dot {{
    width: 8px;
    height: 8px;
    background: #000;
    border-radius: 50%;
    display: inline-block;
}}

.billboard-ticker-header {{
    background: #111;
    color: #f59e0b;
    padding: 10px 14px;
    font-size: 13px;
    letter-spacing: 1.4px;
    border-bottom: 1px solid #222;
    text-transform: uppercase;
}}

.billboard-ticker-wrap {{
    overflow: hidden;
    white-space: nowrap;
    background: #050505;
}}

.billboard-ticker-track {{
    display: inline-flex;
    width: max-content;
    animation: billboardTickerScroll 320s linear infinite;
}}

.billboard-ticker-wrap:hover .billboard-ticker-track {{
    animation-play-state: paused;
}}

.billboard-ticker-item {{
    display: inline-flex;
    align-items: center;
    gap: 12px;
    padding: 14px 24px;
    text-decoration: none;
    color: #ddd;
    border-right: 1px solid #161616;
    transition:
        background 0.25s ease,
        color 0.25s ease;
}}

.billboard-ticker-item:hover {{
    background: #111;
    color: #fff;
}}

.ticker-rank {{
    color: #ff9500;
    font-weight: 900;
    font-size: 15px;
}}

.ticker-name {{
    color: #ffffff;
    font-weight: 700;
    font-size: 14px;
    letter-spacing: 0.5px;
}}

.ticker-volume {{
    color: #00d4ff;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.3px;
}}

.ticker-separator {{
    color: #444;
    font-size: 10px;
}}

@keyframes billboardTickerScroll {{
    from {{
        transform: translateX(0);
    }}

    to {{
        transform: translateX(-50%);
    }}
}}

@media (max-width: 700px) {{

    .billboard-ticker-track {{
        animation-duration: 480s;
    }}

    .billboard-ticker-item {{
        padding: 12px 18px;
    }}

    .ticker-name {{
        font-size: 13px;
    }}

    .ticker-volume {{
        font-size: 12px;
    }}
}}

</style>
'''

OUT_HTML.write_text(html, encoding="utf-8")

print(f"Created: {OUT_CSV}")
print(f"Created: {OUT_HTML}")
print(f"Rows: {len(merged)}")
print("Done.")