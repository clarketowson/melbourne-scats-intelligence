$python = "A:\TrafficAnalytics\PROJECTS\env\Scripts\python.exe"
$script = "A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\generate_campaign_simulation_visuals_v1.py"

& $python $script `
  --input-dir "A:\TrafficAnalytics\PROJECTS\reports\deduped\site_intelligence" `
  --output-dir "A:\TrafficAnalytics\PROJECTS\reports\deduped\site_intelligence\campaign_charts"
