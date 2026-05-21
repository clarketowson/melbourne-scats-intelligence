$python = "A:\TrafficAnalytics\PROJECTS\env\Scripts\python.exe"
$script = "A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\generate_site_visuals_v2.py"

& $python $script `
  --input-dir "A:\TrafficAnalytics\PROJECTS\reports\deduped\site_intelligence" `
  --output-dir "A:\TrafficAnalytics\PROJECTS\reports\deduped\site_intelligence\charts_v2"