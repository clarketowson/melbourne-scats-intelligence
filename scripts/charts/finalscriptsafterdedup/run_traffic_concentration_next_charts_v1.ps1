$python = "A:\TrafficAnalytics\PROJECTS\env\Scripts\python.exe"
$script = "A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\generate_traffic_concentration_next_charts_v1.py"

& $python $script `
  --input-dir "A:\TrafficAnalytics\PROJECTS\reports\deduped\site_intelligence" `
  --output-dir "A:\TrafficAnalytics\PROJECTS\reports\deduped\site_intelligence\concentration_charts"
