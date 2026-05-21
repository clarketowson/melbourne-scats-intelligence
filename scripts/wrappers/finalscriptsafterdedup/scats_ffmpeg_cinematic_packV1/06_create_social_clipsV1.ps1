. "$PSScriptRoot\00_config.ps1"

# Creates short social-friendly 1080x1920 vertical clips from the finished videos.
# These are good for Shorts/Reels/TikTok teasers.

$items = @(
  @{file="time_bin_breathing_with_music.mp4"; out="vertical_melbourne_breathes_short.mp4"; dur="00:00:15"},
  @{file="seasonal_metabolism_with_music.mp4"; out="vertical_seasonal_metabolism_short.mp4"; dur="00:00:15"},
  @{file="top100_ooh_reveal_with_music.mp4"; out="vertical_top100_reveal_short.mp4"; dur="00:00:15"}
)

foreach ($it in $items) {
  $in = Join-Path $videoDir $it.file
  if (-not (Test-Path $in)) { Write-Host "Skipping missing $in" -ForegroundColor Yellow; continue }
  $out = Join-Path $outDir $it.out
  $vf = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1"
  Run-FFmpeg @("-y","-t",$it.dur,"-i",$in,"-vf",$vf,"-c:v","libx264","-crf","18","-preset","slow","-c:a","aac","-b:a","256k","-pix_fmt","yuv420p",$out)
  Write-Host "Wrote $out" -ForegroundColor Green
}
