# Methodology

This project converts long-term traffic signal volume data into city-scale movement intelligence.

## Conceptual model

The central analytical unit is a cleaned 15-minute traffic observation.

A portable schema for other cities would look like:

site_id
site_name
latitude
longitude
count_date
detector_id
interval_index
time_bin
volume_15m
source_file

Once data is transformed into this shape, downstream analysis can be reused across cities.

## Processing strategy

The project uses a chunked processing strategy because city-scale historical traffic datasets can be very large.

Common methods include:

- monthly processing
- resumable outputs
- completion metadata
- CSV/JSON sidecar files
- DuckDB for large local analytics
- avoiding all-at-once memory-heavy queries where possible

## Output categories

Typical outputs include:

- monthly totals
- daily totals
- site totals
- site-month totals
- busiest locations
- busiest time bins
- peak-window shares
- weekday/weekend splits
- chart-ready CSVs
- JSON completion metadata
