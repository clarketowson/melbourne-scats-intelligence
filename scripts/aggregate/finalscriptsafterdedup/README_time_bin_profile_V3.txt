TIME BIN PROFILE V3 SCRIPT PACK

Files:
- generate_time_bin_profile_chunkedV3.py
- run_time_bin_profile_until_done_v3.ps1

Install:
Copy both files into:
A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\

Run:
cd A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup
.\run_time_bin_profile_until_done_v3.ps1

Outputs:
A:\TrafficAnalytics\PROJECTS\reports\deduped\time_bin_profile.csv
A:\TrafficAnalytics\PROJECTS\reports\deduped\time_bin_profile_final.json

Main safeguards:
- One month per execution.
- Resumes from existing CSV.
- Explicit zero-row month marker to avoid endless retry loops.
- Defensive CSV parsing.
- Final JSON rebuilt after each successful month.
- DuckDB progress bar disabled for clean PowerShell output.
- C:\DuckDBTemp default temp directory.
