$ErrorActionPreference = "Stop"

$ffmpeg = "E:\Program Files\ImageMagick-7.0.8-Q16\ffmpeg.EXE"
if (!(Test-Path $ffmpeg)) { $ffmpeg = "ffmpeg" }

$videoDir = "A:\TrafficAnalytics\PROJECTS\reports\deduped\animations\covid"
$musicDir = "A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\scats animation music"

$jobs = @(
  @{Video="covid_recovery_map_animation.mp4"; Music="COVID Collapse & Recovery.mp3"; Out="covid_recovery_map_with_music.mp4"},
  @{Video="covid_24hour_heartbeat_animation.mp4"; Music="Melbourne Breathes.mp3"; Out="covid_24hour_heartbeat_with_music.mp4"},
  @{Video="covid_shock_recovery_scatter_animation.mp4"; Music="Traffic Weather Radar.mp3"; Out="covid_shock_recovery_scatter_with_music.mp4"},
  @{Video="covid_top30_collapse_leaderboard_animation.mp4"; Music="COVID Collapse & Recovery.mp3"; Out="covid_top30_collapse_leaderboard_with_music.mp4"},
  @{Video="covid_top30_growth_leaderboard_animation.mp4"; Music="12-Year Melbourne Evolution.mp3"; Out="covid_top30_growth_leaderboard_with_music.mp4"},
  @{Video="covid_heatmap_reveal_animation.mp4"; Music="Traffic Weather Radar.mp3"; Out="covid_heatmap_reveal_with_music.mp4"}
)

foreach ($job in $jobs) {
  $inputVideo = Join-Path $videoDir $job.Video
  $music = Join-Path $musicDir $job.Music
  $outputVideo = Join-Path $videoDir $job.Out

  if (!(Test-Path $inputVideo)) {
    Write-Host "Skipping missing video: $inputVideo" -ForegroundColor Yellow
    continue
  }
  if (!(Test-Path $music)) {
    Write-Host "Skipping missing music: $music" -ForegroundColor Yellow
    continue
  }

  Write-Host "Adding music to $($job.Video)..." -ForegroundColor Cyan

  & $ffmpeg -y -i "$inputVideo" -i "$music" -c:v libx264 -crf 18 -preset slow -c:a aac -b:a 320k -shortest "$outputVideo"

  if ($LASTEXITCODE -ne 0) {
    throw "ffmpeg failed for $($job.Video)"
  }

  Write-Host "Wrote: $outputVideo" -ForegroundColor Green
}
