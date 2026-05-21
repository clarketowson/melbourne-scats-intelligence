$ErrorActionPreference = "Stop"

Write-Host "Running all COVID animation scripts V1..." -ForegroundColor Cyan

python .\generate_covid_recovery_map_animationV1.py
if ($LASTEXITCODE -ne 0) { throw "generate_covid_recovery_map_animationV1.py failed" }

python .\generate_covid_24hour_heartbeat_animationV1.py
if ($LASTEXITCODE -ne 0) { throw "generate_covid_24hour_heartbeat_animationV1.py failed" }

python .\generate_covid_shock_recovery_scatter_animationV1.py
if ($LASTEXITCODE -ne 0) { throw "generate_covid_shock_recovery_scatter_animationV1.py failed" }

python .\generate_covid_leaderboard_animationsV1.py
if ($LASTEXITCODE -ne 0) { throw "generate_covid_leaderboard_animationsV1.py failed" }

python .\generate_covid_heatmap_reveal_animationV1.py
if ($LASTEXITCODE -ne 0) { throw "generate_covid_heatmap_reveal_animationV1.py failed" }

Write-Host ""
Write-Host "All COVID animations created." -ForegroundColor Green
Write-Host "Now optionally run: .\add_music_to_covid_animationsV1.ps1" -ForegroundColor Yellow
