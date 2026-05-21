#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
generate_all_scats_sites_interactive_map_html_v1.py

Creates a standalone all-sites interactive Google Maps HTML page from:
  all_scats_sites_map_data.json

Output:
  all_scats_sites_interactive_map.html

The generated HTML embeds the JSON data directly, so it does not need to fetch
a separate JSON file.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


DEFAULT_BASE_DIR = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")


def heat_badge_class(band: str) -> str:
    band = (band or "unknown").lower()
    if band in {"red", "orange", "yellow", "green"}:
        return f"heat-{band}"
    return "heat-unknown"


def build_html(data: list[dict], api_key_placeholder: str = "YOUR_API_KEY") -> str:
    n = len(data)
    bands = {}
    for d in data:
        b = d.get("traffic_band", "unknown")
        bands[b] = bands.get(b, 0) + 1

    top = data[0] if data else {}
    top_table = data[:75]
    data_js = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    rows = ""
    for site in top_table:
        band = html.escape(str(site.get("traffic_band", "unknown")))
        rows += f"""
            <tr>
              <td>{site.get("rank", "")}</td>
              <td>
                <strong>{html.escape(str(site.get("friendly_name", "")))}</strong><br>
                <span class="muted">Official: {html.escape(str(site.get("official_name", "")))}</span>
              </td>
              <td>{html.escape(str(site.get("site_id", "")))}</td>
              <td>{html.escape(str(site.get("municipality", "")))}</td>
              <td>{float(site.get("total_millions", 0)):,.1f}M</td>
              <td>{float(site.get("percentile_rank", 0)):,.2f}</td>
              <td><span class="heat-badge {heat_badge_class(band)}">{band.upper()}</span></td>
              <td><a class="map-link" href="{html.escape(str(site.get("google_maps_url", "#")))}" target="_blank" rel="noopener">Open</a></td>
            </tr>
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>All SCATS Sites — Melbourne Interactive Network Map</title>
  <style>
    :root {{
      --text:#1f2937;
      --muted:#5d6b7c;
      --border:#dbe3ef;
      --surface:#ffffff;
      --soft:#f7f9fc;
      --brand:#007bff;
      --brand-dark:#0a66d1;
      --red:#e53935;
      --orange:#fb8c00;
      --yellow:#fdd835;
      --green:#43a047;
      --grey:#9ca3af;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Arial,sans-serif; color:var(--text); background:#f3f3f3; line-height:1.5; }}
    header {{ background:#fff; border-bottom:1px solid var(--border); padding:24px 28px 18px; }}
    header h1 {{ margin:0 0 8px; font-size:30px; line-height:1.2; }}
    header p {{ margin:0; color:var(--muted); max-width:1100px; font-size:15px; }}
    .page {{ max-width:1450px; margin:22px auto 40px; padding:0 16px; }}
    .card {{ background:var(--surface); border:1px solid var(--border); border-radius:18px; padding:18px; box-shadow:0 4px 16px rgba(0,0,0,.06); margin-bottom:18px; }}
    .summary-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; margin-top:14px; }}
    .metric {{ background:var(--soft); border:1px solid var(--border); border-radius:12px; padding:14px; }}
    .metric h3 {{ margin:0 0 6px; color:#16395f; font-size:14px; }}
    .metric p {{ margin:0; font-size:20px; font-weight:700; }}
    .map-shell {{ position:relative; border:1px solid var(--border); border-radius:18px; overflow:hidden; background:#fff; box-shadow:0 4px 16px rgba(0,0,0,.08); margin-bottom:18px; }}
    #allSitesMap {{ width:100%; height:820px; }}
    .legend {{ position:absolute; z-index:5; left:18px; top:18px; background:rgba(255,255,255,.96); border:1px solid var(--border); border-radius:14px; padding:14px 16px; box-shadow:0 3px 12px rgba(0,0,0,.16); min-width:320px; font-size:14px; }}
    .legend h3 {{ margin:0 0 10px; font-size:16px; color:#16395f; }}
    .legend-row {{ display:flex; align-items:center; gap:8px; margin:7px 0; }}
    .dot {{ width:14px; height:14px; border-radius:50%; display:inline-block; border:1px solid rgba(0,0,0,.18); }}
    .legend-note {{ margin-top:10px; color:var(--muted); font-size:12px; line-height:1.35; }}
    .control-panel {{ position:absolute; z-index:5; right:18px; top:18px; background:rgba(255,255,255,.96); border:1px solid var(--border); border-radius:14px; padding:14px 16px; box-shadow:0 3px 12px rgba(0,0,0,.16); width:min(380px, calc(100% - 36px)); font-size:14px; }}
    .control-panel h3 {{ margin:0 0 10px; font-size:16px; color:#16395f; }}
    .control-panel label {{ display:block; margin:7px 0; }}
    .control-panel input[type="text"] {{ width:100%; padding:9px 10px; border:1px solid var(--border); border-radius:9px; margin-bottom:8px; font-size:14px; }}
    .control-actions {{ display:flex; gap:8px; flex-wrap:wrap; margin-top:10px; }}
    .btn {{ border:none; border-radius:9px; padding:8px 10px; background:var(--brand); color:white; font-weight:700; cursor:pointer; font-size:13px; }}
    .btn:hover {{ background:var(--brand-dark); }}
    .btn.secondary {{ background:#e5e7eb; color:#111827; }}
    .btn.secondary:hover {{ background:#d1d5db; }}
    .status {{ margin-top:8px; color:var(--muted); font-size:12px; }}
    .gm-popup {{ font-family:Arial,sans-serif; max-width:360px; line-height:1.45; }}
    .gm-popup h3 {{ margin:0 0 6px; font-size:16px; color:#16395f; }}
    .gm-popup p {{ margin:4px 0; font-size:13px; }}
    .gm-popup .official {{ color:#5d6b7c; font-size:12px; }}
    .gm-popup a {{ display:inline-block; margin-top:8px; background:var(--brand); color:white; padding:7px 10px; border-radius:8px; text-decoration:none; font-weight:700; font-size:13px; }}
    .gm-popup a:hover {{ background:var(--brand-dark); }}
    .table-wrap {{ overflow-x:auto; margin-top:14px; }}
    table {{ width:100%; border-collapse:collapse; background:#fff; border:1px solid var(--border); border-radius:12px; overflow:hidden; }}
    th,td {{ padding:10px 12px; border-bottom:1px solid var(--border); text-align:left; font-size:14px; vertical-align:top; }}
    th {{ background:var(--soft); color:#16395f; }}
    tr:last-child td {{ border-bottom:none; }}
    .muted {{ color:var(--muted); font-size:12px; }}
    .map-link {{ color:var(--brand); font-weight:700; text-decoration:none; }}
    .map-link:hover {{ text-decoration:underline; }}
    .heat-badge {{ display:inline-block; padding:4px 8px; border-radius:999px; color:#111827; font-size:12px; font-weight:700; border:1px solid rgba(0,0,0,.12); }}
    .heat-red {{ background:#ffcdd2; }}
    .heat-orange {{ background:#ffe0b2; }}
    .heat-yellow {{ background:#fff9c4; }}
    .heat-green {{ background:#c8e6c9; }}
    .heat-unknown {{ background:#e5e7eb; }}
    .note {{ background:#eef7ff; border:1px solid var(--border); border-left:6px solid var(--brand); border-radius:12px; padding:14px 16px; color:#334155; margin-top:14px; }}
    @media (max-width:900px) {{
      header h1 {{ font-size:24px; }}
      #allSitesMap {{ height:700px; }}
      .legend,.control-panel {{ position:static; width:100%; border-radius:0; box-shadow:none; border-left:none; border-right:none; border-top:none; }}
      .map-shell {{ border-radius:14px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>All SCATS Sites — Melbourne Interactive Network Map</h1>
    <p>
      Explore every mapped SCATS-controlled traffic site in the cleaned archive.
      Colour bands show relative traffic intensity by percentile, so readers can zoom into their own area and see how busy local intersections are.
    </p>
  </header>

  <div class="page">
    <section class="card">
      <h2 style="margin-top:0;">Melbourne-Wide SCATS Network Map</h2>
      <p>
        This map plots every SCATS site in the generated map dataset with valid coordinates.
        Click a point to view the site name, official SCATS label, site ID, municipality, percentile rank, total cleaned movements, and Google Maps link.
      </p>
      <div class="summary-grid">
        <div class="metric"><h3>Mapped Sites</h3><p>{n:,}</p></div>
        <div class="metric"><h3>Top Site</h3><p>{html.escape(str(top.get("site_id", "")))}</p></div>
        <div class="metric"><h3>Top Volume</h3><p>{float(top.get("total_millions", 0)):,.1f}M</p></div>
        <div class="metric"><h3>Traffic Bands</h3><p>{len(bands)}</p></div>
      </div>
      <div class="note">
        <strong>Performance note:</strong> This all-sites version uses simple clickable Google Maps circles, no labels, and click-only popups so the browser can handle thousands of locations.
      </div>
    </section>

    <section class="map-shell">
      <div class="legend">
        <h3>Traffic Intensity Legend</h3>
        <div class="legend-row"><span class="dot" style="background:#e53935;"></span><strong>Red</strong> — Top 5% busiest sites</div>
        <div class="legend-row"><span class="dot" style="background:#fb8c00;"></span><strong>Orange</strong> — Top 20% busiest sites</div>
        <div class="legend-row"><span class="dot" style="background:#fdd835;"></span><strong>Yellow</strong> — Middle-volume sites</div>
        <div class="legend-row"><span class="dot" style="background:#43a047;"></span><strong>Green</strong> — Lower-volume mapped sites</div>
        <div class="legend-note">Circle size is scaled lightly by volume. Colours are based on percentile rank among sites in the cleaned archive.</div>
      </div>

      <div class="control-panel">
        <h3>Map Controls</h3>
        <input type="text" id="siteSearch" placeholder="Search site ID, road, or municipality, e.g. Hoddle, 4415, Nepean">
        <label><input type="checkbox" class="band-toggle" value="red" checked> Red — top 5%</label>
        <label><input type="checkbox" class="band-toggle" value="orange" checked> Orange — top 20%</label>
        <label><input type="checkbox" class="band-toggle" value="yellow" checked> Yellow — middle</label>
        <label><input type="checkbox" class="band-toggle" value="green" checked> Green — lower</label>
        <div class="control-actions">
          <button class="btn" onclick="applyFilters()">Apply filters</button>
          <button class="btn secondary" onclick="resetFilters()">Reset</button>
        </div>
        <div class="status" id="mapStatus">Showing all mapped sites.</div>
      </div>

      <div id="allSitesMap"></div>
    </section>

    <section class="card">
      <h2 style="margin-top:0;">Top 75 Mapped SCATS Sites</h2>
      <p>This table lists the highest-volume mapped sites so readers can compare the map against the underlying ranking.</p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Rank</th>
              <th>Friendly Location Name</th>
              <th>SCATS ID</th>
              <th>Municipality</th>
              <th>Total Movements</th>
              <th>Percentile</th>
              <th>Band</th>
              <th>Map</th>
            </tr>
          </thead>
          <tbody>
{rows}
          </tbody>
        </table>
      </div>
    </section>
  </div>

  <script>
    const SCATS_ALL_SITES = {data_js};

    let map;
    let circles = [];
    let activeInfo = null;

    function getColor(band) {{
      if (band === "red") return "#e53935";
      if (band === "orange") return "#fb8c00";
      if (band === "yellow") return "#fdd835";
      if (band === "green") return "#43a047";
      return "#9ca3af";
    }}

    function getRadius(site) {{
      return 18 + Math.sqrt(Math.max(site.volume_ratio || 0, 0.006)) * 115;
    }}

    function makePopup(site) {{
      return `
        <div class="gm-popup">
          <h3>#${{site.rank}} — ${{site.friendly_name}}</h3>
          <p class="official"><strong>Official SCATS label:</strong> ${{site.official_name}}</p>
          <p><strong>SCATS Site:</strong> ${{site.site_id}}</p>
          <p><strong>Municipality:</strong> ${{site.municipality || "N/A"}}</p>
          <p><strong>Total movements:</strong> ${{site.total.toLocaleString()}} (${{site.total_millions}}M)</p>
          <p><strong>Percentile rank:</strong> ${{site.percentile_rank}}</p>
          <p><strong>Traffic band:</strong> ${{site.traffic_band.toUpperCase()}}</p>
          <a href="${{site.google_maps_url}}" target="_blank" rel="noopener">Open in Google Maps</a>
        </div>
      `;
    }}

    function createCircle(site) {{
      const position = new google.maps.LatLng(site.lat, site.lng);
      const color = getColor(site.traffic_band);

      const circle = new google.maps.Circle({{
        strokeColor: color,
        strokeOpacity: 0.82,
        strokeWeight: 1,
        fillColor: color,
        fillOpacity: 0.50,
        map: map,
        center: position,
        radius: getRadius(site)
      }});

      const info = new google.maps.InfoWindow({{ content: makePopup(site) }});

      circle.addListener("click", () => {{
        if (activeInfo) activeInfo.close();
        activeInfo = info;
        info.setPosition(position);
        info.open(map);
      }});

      circle._siteData = site;
      circles.push(circle);
      return circle;
    }}

    function initMap() {{
      map = new google.maps.Map(document.getElementById("allSitesMap"), {{
        zoom: 9,
        center: {{ lat: -37.8136, lng: 144.9631 }},
        mapTypeControl: true,
        streetViewControl: false,
        fullscreenControl: true
      }});

      const bounds = new google.maps.LatLngBounds();

      SCATS_ALL_SITES.forEach(site => {{
        createCircle(site);
        bounds.extend(new google.maps.LatLng(site.lat, site.lng));
      }});

      if (!bounds.isEmpty()) {{
        map.fitBounds(bounds);
      }}

      document.getElementById("siteSearch").addEventListener("keydown", function(event) {{
        if (event.key === "Enter") applyFilters();
      }});

      updateStatus();
    }}

    function getSelectedBands() {{
      return Array.from(document.querySelectorAll(".band-toggle"))
        .filter(cb => cb.checked)
        .map(cb => cb.value);
    }}

    function applyFilters() {{
      const q = document.getElementById("siteSearch").value.trim().toLowerCase();
      const selected = new Set(getSelectedBands());
      let visible = 0;
      const bounds = new google.maps.LatLngBounds();

      circles.forEach(circle => {{
        const site = circle._siteData;
        const haystack = [
          site.site_id,
          site.friendly_name,
          site.official_name,
          site.municipality,
          site.traffic_band
        ].join(" ").toLowerCase();

        const bandOk = selected.has(site.traffic_band);
        const searchOk = !q || haystack.includes(q);
        const show = bandOk && searchOk;

        circle.setMap(show ? map : null);

        if (show) {{
          visible++;
          bounds.extend(circle.getCenter());
        }}
      }});

      if (visible > 0 && q) {{
        map.fitBounds(bounds);
      }}

      updateStatus(visible);
    }}

    function resetFilters() {{
      document.getElementById("siteSearch").value = "";
      document.querySelectorAll(".band-toggle").forEach(cb => cb.checked = true);
      circles.forEach(circle => circle.setMap(map));
      updateStatus(circles.length);
    }}

    function updateStatus(count) {{
      const visible = typeof count === "number"
        ? count
        : circles.filter(c => c.getMap()).length;
      document.getElementById("mapStatus").textContent =
        `Showing ${{visible.toLocaleString()}} of ${{circles.length.toLocaleString()}} mapped SCATS sites.`;
    }}
  </script>

  <script async src="https://maps.googleapis.com/maps/api/js?key={api_key_placeholder}&callback=initMap"></script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", default=str(DEFAULT_BASE_DIR))
    parser.add_argument("--input-json", default=None)
    parser.add_argument("--output-html", default=None)
    parser.add_argument("--api-key", default="YOUR_API_KEY")
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    input_json = Path(args.input_json) if args.input_json else base_dir / "all_scats_sites_map_data.json"
    output_html = Path(args.output_html) if args.output_html else base_dir / "all_scats_sites_interactive_map.html"

    with open(input_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    html_text = build_html(data, api_key_placeholder=args.api_key)
    output_html.write_text(html_text, encoding="utf-8")

    print(f"Wrote HTML: {output_html}")
    print(f"Embedded records: {len(data):,}")


if __name__ == "__main__":
    main()
