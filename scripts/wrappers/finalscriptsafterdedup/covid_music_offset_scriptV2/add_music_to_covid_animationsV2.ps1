$ErrorActionPreference = "Stop"

# add_music_to_covid_animationsV2.ps1
#
# Uses ONLY:
#   COVID Collapse & Recovery.mp3
#
# Each animation starts at a different offset into the same MP3 so the videos
# do not all use the exact same opening section of the soundtrack.

$ffmpeg = "E:\Program Files\ImageMagick-7.0.8-Q16\ffmpeg.EXE"
if (!(Test-Path $ffmpeg)) {
  $ffmpeg = "ffmpeg"
}

$ffprobe = "E:\Program Files\ImageMagick-7.0.8-Q16\ffprobe.EXE"
if (!(Test-Path $ffprobe)) {
  $ffprobe = "ffprobe"
}

$videoDir = "A:\TrafficAnalytics\PROJECTS\reports\deduped\animations\covid"
$musicDir = "A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\scats animation music"
$music = Join-Path $musicDir "COVID Collapse & Recovery.mp3"

if (!(Test-Path $music)) {
  throw "Music file not found: $music"
}

# Offsets are in seconds.
# Adjust these if you want different music sections.
$jobs = @(
  @{Video="covid_recovery_map_animation.mp4";                 Offset=0;   Out="covid_recovery_map_with_music.mp4"},
  @{Video="covid_24hour_heartbeat_animation.mp4";             Offset=35;  Out="covid_24hour_heartbeat_with_music.mp4"},
  @{Video="covid_shock_recovery_scatter_animation.mp4";       Offset=70;  Out="covid_shock_recovery_scatter_with_music.mp4"},
  @{Video="covid_top30_collapse_leaderboard_animation.mp4";   Offset=105; Out="covid_top30_collapse_leaderboard_with_music.mp4"},
  @{Video="covid_top30_growth_leaderboard_animation.mp4";     Offset=140; Out="covid_top30_growth_leaderboard_with_music.mp4"},
  @{Video="covid_heatmap_reveal_animation.mp4";               Offset=175; Out="covid_heatmap_reveal_with_music.mp4"}
)

Write-Host "Using music: $music" -ForegroundColor Cyan
Write-Host ""

foreach ($job in $jobs) {
  $inputVideo = Join-Path $videoDir $job.Video
  $outputVideo = Join-Path $videoDir $job.Out
  $offset = $job.Offset

  if (!(Test-Path $inputVideo)) {
    Write-Host "Skipping missing video: $inputVideo" -ForegroundColor Yellow
    continue
  }

  Write-Host "Adding music to: $($job.Video)" -ForegroundColor Cyan
  Write-Host "Music offset    : $offset seconds"
  Write-Host "Output          : $outputVideo"

  # Important:
  # -ss before the music input seeks into the MP3 before encoding.
  # -stream_loop -1 loops the MP3 so even if the offset is near the end,
  # the soundtrack continues for the full video length.
  & $ffmpeg -y `
    -i "$inputVideo" `
    -stream_loop -1 -ss $offset -i "$music" `
    -c:v libx264 `
    -crf 18 `
    -preset slow `
    -c:a aac `
    -b:a 320k `
    -shortest `
    "$outputVideo"

  if ($LASTEXITCODE -ne 0) {
    throw "ffmpeg failed for $($job.Video)"
  }

  Write-Host "Wrote: $outputVideo" -ForegroundColor Green
  Write-Host ""
}

Write-Host "All available COVID videos now have offset music." -ForegroundColor Green
