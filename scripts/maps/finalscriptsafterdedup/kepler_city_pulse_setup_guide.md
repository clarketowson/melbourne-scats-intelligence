# Kepler.gl Setup Guide — Melbourne SCATS City Pulse Animation

## Generated file

The script creates:

```text
A:\TrafficAnalytics\PROJECTS\reports\deduped\kepler_city_pulse\kepler_city_pulse_YYYY-MM-DD.csv
```

## Load into Kepler.gl

1. Open Kepler.gl.
2. Drag in the CSV.
3. Create a **Point** layer.
4. Set:
   - Latitude: `latitude`
   - Longitude: `longitude`
   - Time field: `timestamp`
   - Radius / size: `scaled_volume_0_100`
   - Colour: `volume` or `intensity_band`

## Recommended visual settings

Use a dark basemap.

Suggested layer setup:

- Point radius: use `scaled_volume_0_100`
- Radius scale: start around 8–20
- Opacity: 0.45–0.70
- Enable colour based on `volume` or `intensity_band`
- Use additive / glowing visual style if available
- Time playback window: 15–30 minutes
- Animation speed: medium-fast

## Story title

**A Day in the Life of Melbourne — 24 Hours of SCATS Traffic Movement**

## Best export

Record a 15–30 second screen capture showing:
- midnight quiet period
- AM activation
- midday plateau
- 5:15 PM peak
- evening fade
