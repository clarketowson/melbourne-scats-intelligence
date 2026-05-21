. "$PSScriptRoot\00_config.ps1"

# Creates a short master showreel from your completed music videos.
# It trims each segment to a concise length and concatenates them.

$segments = @(
  @{file="time_bin_breathing_with_music.mp4"; start="00:00:00"; dur="00:00:12"},
  @{file="seasonal_metabolism_with_music.mp4"; start="00:00:00"; dur="00:00:12"},
  @{file="top100_ooh_reveal_with_music.mp4"; start="00:00:00"; dur="00:00:12"},
  @{file="monthly_total_growth_animation.mp4"; start="00:00:00"; dur="00:00:08"},
  @{file="daily_total_traffic_animation.mp4"; start="00:00:00"; dur="00:00:12"}
)

$tempList = Join-Path $outDir "showreel_concat_list.txt"
Remove-Item $tempList -ErrorAction SilentlyContinue
$i = 0
foreach ($s in $segments) {
  $in = Join-Path $videoDir $s.file
  if (-not (Test-Path $in)) { Write-Host "Skipping missing $in" -ForegroundColor Yellow; continue }
  $clip = Join-Path $outDir ("showreel_part_{0:D2}.mp4" -f $i)
  Run-FFmpeg @("-y","-ss",$s.start,"-t",$s.dur,"-i",$in,"-vf","scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1","-c:v","libx264","-crf","18","-preset","slow","-c:a","aac","-b:a","256k","-ar","48000",$clip)
  Add-Content -Path $tempList -Value "file '$($clip.Replace("'", "'\''"))'"
  $i++
}

$out = Join-Path $outDir "scats_master_showreelV1.mp4"
Run-FFmpeg @("-y","-f","concat","-safe","0","-i",$tempList,"-c","copy",$out)
Write-Host "Wrote $out" -ForegroundColor Green
