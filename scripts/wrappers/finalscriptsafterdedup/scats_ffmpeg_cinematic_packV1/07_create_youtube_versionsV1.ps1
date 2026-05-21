. "$PSScriptRoot\00_config.ps1"

# Creates clean YouTube-ready 1080p versions with good audio bitrate.

$items = @(
  "time_bin_breathing_with_music.mp4",
  "seasonal_metabolism_with_music.mp4",
  "top100_ooh_reveal_with_music.mp4"
)

foreach ($file in $items) {
  $in = Join-Path $videoDir $file
  if (-not (Test-Path $in)) { Write-Host "Skipping missing $in" -ForegroundColor Yellow; continue }
  $base = [System.IO.Path]::GetFileNameWithoutExtension($file)
  $out = Join-Path $outDir ("$base`_youtube_1080p.mp4")
  $vf = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1"
  Run-FFmpeg @("-y","-i",$in,"-vf",$vf,"-c:v","libx264","-crf","18","-preset","slow","-c:a","aac","-b:a","320k","-ar","48000","-pix_fmt","yuv420p","-movflags","+faststart",$out)
  Write-Host "Wrote $out" -ForegroundColor Green
}
