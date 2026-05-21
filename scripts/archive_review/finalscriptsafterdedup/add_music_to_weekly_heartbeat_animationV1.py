import os
import subprocess

VIDEO_FILE = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\animations\melbourne_weekly_heartbeat.mp4"
MUSIC_FILE = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\animations\Melbourne Weekly Rhythm.mp3"
OUTPUT_FILE = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\animations\melbourne_weekly_heartbeat_with_music.mp4"

MUSIC_VOLUME = 0.45

if not os.path.exists(VIDEO_FILE):
    raise FileNotFoundError(f"Video not found: {VIDEO_FILE}")

if not os.path.exists(MUSIC_FILE):
    raise FileNotFoundError(f"Music not found: {MUSIC_FILE}")

cmd = [
    "ffmpeg", "-y",
    "-i", VIDEO_FILE,
    "-i", MUSIC_FILE,
    "-filter_complex", f"[1:a]volume={MUSIC_VOLUME},afade=t=in:st=0:d=3[music]",
    "-map", "0:v:0",
    "-map", "[music]",
    "-c:v", "copy",
    "-c:a", "aac",
    "-b:a", "320k",
    "-shortest",
    OUTPUT_FILE
]

print("Adding music...")
subprocess.run(cmd, check=True)
print(f"Done: {OUTPUT_FILE}")