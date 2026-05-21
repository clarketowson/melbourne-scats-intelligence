SCATS Next Kepler Animation Export Pack V1
==========================================

Purpose
-------
This pack creates Kepler.gl-ready CSV files for the next generation of Melbourne SCATS animations.
These scripts output CSVs, not PNG frames. Load the CSVs into Kepler.gl and animate using the timestamp fields.

Output directory
----------------
A:\TrafficAnalytics\PROJECTS\reports\deduped\kepler_animation_exports

Included scripts
----------------
1. generate_kepler_city_pulse_weekV2.py
   Exports a 7-day 15-minute city pulse map.
   Default: 2024-05-13 to 2024-05-19.

2. generate_kepler_never_sleeps_overnightV1.py
   Exports only overnight movement, default 00:00 to 05:00 across 7 days.

3. generate_kepler_am_pm_comparisonV1.py
   Exports AM and PM peak windows for a selected day.
   Includes true lat/lon and side-by-side comparison_latitude/comparison_longitude fields.

4. generate_kepler_covid_comparison_daysV1.py
   Exports selected comparison days for pre-COVID, COVID shock, recovery, recent normal, and busiest day.
   Use animation_timestamp as the Kepler time field.

5. generate_kepler_top100_ooh_revealV2.py
   Exports Top 100 SCATS/OOH opportunity nodes with reveal timestamps.

6. generate_kepler_seasonal_top100_monthly_pulseV1.py
   Exports monthly Top 100 site intensity across the site_month_totals.csv history.

Run all
-------
.\run_all_next_kepler_exportsV1.ps1

Individual examples
-------------------
python .\generate_kepler_city_pulse_weekV2.py --start-date 2024-05-13
python .\generate_kepler_never_sleeps_overnightV1.py --start-date 2024-05-13 --days 7
python .\generate_kepler_am_pm_comparisonV1.py --date 2024-05-15
python .\generate_kepler_covid_comparison_daysV1.py
python .\generate_kepler_top100_ooh_revealV2.py
python .\generate_kepler_seasonal_top100_monthly_pulseV1.py

Kepler.gl setup hints
---------------------
Layer type: Point
Latitude: latitude
Longitude: longitude
Time field: timestamp, except COVID script where animation_timestamp is usually best
Size field: scaled_volume_0_100 or volume
Colour field: intensity_band, day_name, peak_period, comparison_period, rank_tier, or opportunity_tier

For AM vs PM comparison:
- true geographic overlay: use latitude / longitude
- side-by-side comparison: use comparison_latitude / comparison_longitude

Recommended Kepler animation speed
----------------------------------
7-day pulse: use a narrow time window and moderate playback speed.
Top 100 reveal: use timestamp and reveal_rank; pause at the end.
COVID comparison: use animation_timestamp, colour by comparison_period.
