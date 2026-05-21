$ffmpeg = "E:\Program Files\ImageMagick-7.0.8-Q16\ffmpeg.EXE"

$videoDir = "A:\TrafficAnalytics\PROJECTS\reports\deduped\animations"
$musicDir = "A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\scats animation music"

& $ffmpeg -y `
-i "$videoDir\time_bin_breathing_animation.mp4" `
-i "$musicDir\Melbourne Breathes.mp3" `
-c:v copy `
-c:a aac `
-shortest `
"$videoDir\time_bin_breathing_with_music.mp4"

& $ffmpeg -y `
-i "$videoDir\seasonal_metabolism_animation.mp4" `
-i "$musicDir\Seasonal Metabolism.mp3" `
-c:v copy `
-c:a aac `
-shortest `
"$videoDir\seasonal_metabolism_with_music.mp4"

& $ffmpeg -y `
-i "$videoDir\top100_ooh_reveal_animation.mp4" `
-i "$musicDir\Top 100 Traffic Empire Reveal.mp3" `
-c:v copy `
-c:a aac `
-shortest `
"$videoDir\top100_ooh_reveal_with_music.mp4"

Write-Host ""
Write-Host "All soundtrack merges complete."