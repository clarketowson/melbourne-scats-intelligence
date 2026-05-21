# add_music_to_kepler_24hour_animation.ps1
#
# Adds cinematic music to your recorded Kepler SCATS animation.

$ErrorActionPreference = "Stop"

$ffmpeg = "E:\Program Files\ImageMagick-7.0.8-Q16\ffmpeg.EXE"
if (!(Test-Path $ffmpeg)) {
    $ffmpeg = "ffmpeg"
}

# -------------------------------------------------------------------
# INPUT VIDEO
# -------------------------------------------------------------------

$inputVideo = "A:\screenrecordings\2026-05-08 08-40-32_cinematic_topfixed2.mp4"

# -------------------------------------------------------------------
# MUSIC
# -------------------------------------------------------------------

$music = "A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\scats animation music\Seasonal Metabolism2.mp3"

# -------------------------------------------------------------------
# OUTPUT VIDEO
# -------------------------------------------------------------------

$outputVideo = "A:\screenrecordings\2026-05-08 08-40-32_with_music.mp4"

# -------------------------------------------------------------------
# CHECK FILES
# -------------------------------------------------------------------

if (!(Test-Path $inputVideo)) {
    throw "Input video not found: $inputVideo"
}

if (!(Test-Path $music)) {
    throw "Music file not found: $music"
}

# -------------------------------------------------------------------
# ADD MUSIC
# -------------------------------------------------------------------

Write-Host ""
Write-Host "Adding cinematic music to Kepler SCATS animation..." -ForegroundColor Cyan
Write-Host ""

& $ffmpeg -y `
    -i "$inputVideo" `
    -i "$music" `
    -map 0:v:0 `
    -map 1:a:0 `
    -c:v libx264 `
    -crf 18 `
    -preset slow `
    -c:a aac `
    -b:a 320k `
    -shortest `
    "$outputVideo"

if ($LASTEXITCODE -ne 0) {
    throw "ffmpeg failed."
}

Write-Host ""
Write-Host "DONE." -ForegroundColor Green
Write-Host "Output:"
Write-Host "$outputVideo"