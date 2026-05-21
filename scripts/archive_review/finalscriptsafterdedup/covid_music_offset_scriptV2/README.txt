# COVID Music Offset Script V2

This replaces `add_music_to_covid_animationsV1.ps1`.

It uses only:

```text
COVID Collapse & Recovery.mp3
```

but starts each video at a different offset into the same MP3.

## Run

```powershell
.\add_music_to_covid_animationsV2.ps1
```

## Default offsets

- recovery map: 0 seconds
- 24-hour heartbeat: 35 seconds
- shock/recovery scatter: 70 seconds
- collapse leaderboard: 105 seconds
- growth leaderboard: 140 seconds
- heatmap reveal: 175 seconds

You can edit the `$jobs` array in the PowerShell file to change offsets.
