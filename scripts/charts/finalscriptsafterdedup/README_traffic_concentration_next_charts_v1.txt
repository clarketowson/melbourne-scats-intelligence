TRAFFIC CONCENTRATION NEXT CHARTS V1

Files:
- generate_traffic_concentration_next_charts_v1.py
- run_traffic_concentration_next_charts_v1.ps1

Install/copy:
1. Copy generate_traffic_concentration_next_charts_v1.py to:
   A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\

2. Copy run_traffic_concentration_next_charts_v1.ps1 to:
   A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\

Run:
   cd A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup
   .\run_traffic_concentration_next_charts_v1.ps1

Outputs:
   A:\TrafficAnalytics\PROJECTS\reports\deduped\site_intelligence\concentration_charts

Generated charts:
1. Top 100 vs remaining network
2. Top 500 / next 500 / remaining
3. City-level concentration curve
4. Sites required for traffic thresholds
5. Remaining traffic after selection
6. Average volume per site group
7. Traffic share by rank group
8. Commercial portfolio ladder

Generated CSV summaries:
- city_level_concentration_summary.csv
- traffic_threshold_sites_required.csv
- rank_group_density_summary.csv
- traffic_concentration_next_chart_index.csv
