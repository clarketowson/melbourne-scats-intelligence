SITE TOTALS POST-PROCESSING SCRIPTS
===================================

Main script:
  generate_site_intelligence_v1.py

Runner:
  run_site_intelligence_v1.ps1

Purpose:
  Converts site_totals.csv into template-ready outputs:
    - site_network_summary.json
    - site_rankings.csv/json
    - top_10_sites.csv/json
    - top_25_sites.csv/json
    - top_50_sites.csv/json
    - top_100_sites.csv/json
    - top_500_sites.csv/json
    - top_1000_sites.csv/json
    - site_totals_monthly_network_trend.csv/json
    - site_volume_percentile_bands.csv/json

Recommended install location:
  Copy generate_site_intelligence_v1.py to:
    A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\

  Copy run_site_intelligence_v1.ps1 wherever convenient, or keep it in the same scripts folder.

Run:
  powershell -ExecutionPolicy Bypass -File A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\run_site_intelligence_v1.ps1

Optional site name/location enrichment:
  If you have a CSV with scats_site plus site_name/location/suburb/lat/lon fields, edit the PowerShell
  runner and uncomment the $SiteLookup line and the command with --site-lookup.

Important:
  The script works now on partial data and should be rerun once site_totals reaches 148/148.
  It deduplicates month+site rows by keeping the latest completed_at_epoch to prevent double-counting.
