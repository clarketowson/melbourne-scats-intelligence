
$python = "A:\TrafficAnalytics\PROJECTS\env\Scripts\python.exe"
$script = "A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\generate_revenue_simulation_v2_scenarios.py"

& $python $script `
  --input-dir "A:\TrafficAnalytics\PROJECTS\reports\deduped\site_intelligence" `
  --output-dir "A:\TrafficAnalytics\PROJECTS\reports\deduped\site_intelligence\revenue_charts_v2" `
  --cost-per-site 12000
