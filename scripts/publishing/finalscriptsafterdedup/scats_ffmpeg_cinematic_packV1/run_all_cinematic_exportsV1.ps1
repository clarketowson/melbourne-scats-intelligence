$ErrorActionPreference = "Stop"
Write-Host "Running SCATS cinematic ffmpeg pack V1..." -ForegroundColor Cyan

& "$PSScriptRoot\01_create_title_cardsV1.ps1"
& "$PSScriptRoot\02_create_master_showreelV1.ps1"
& "$PSScriptRoot\03_create_split_screen_comparisonsV1.ps1"
& "$PSScriptRoot\04_create_hud_overlay_versionsV1.ps1"
& "$PSScriptRoot\05_create_ken_burns_versionsV1.ps1"
& "$PSScriptRoot\06_create_social_clipsV1.ps1"
& "$PSScriptRoot\07_create_youtube_versionsV1.ps1"

Write-Host "All cinematic exports complete." -ForegroundColor Green
