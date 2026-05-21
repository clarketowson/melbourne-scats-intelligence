# City Adaptation Guide

This project is Melbourne-specific at the source-data layer, but the architecture can be adapted to other cities.

## What another city needs

A city can adapt this pipeline if it has some form of historical traffic observation data, such as:

- traffic signal detector volumes
- loop detector data
- classified vehicle counts
- road sensor data
- corridor speed/flow data
- timestamped intersection counts

## Target normalized schema

The key adaptation step is to transform local data into a common 15-minute observation model:

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

## Adaptation steps

1. Write a local ingest adapter.
2. Normalize timestamps or interval columns into 15-minute bins.
3. Add site metadata.
4. Clean invalid or missing values.
5. Deduplicate repeated observations.
6. Produce a city-wide long-format table or view.
7. Reuse aggregation, charting and reporting scripts where possible.

## What will need changing

- source file parsing
- site metadata format
- timezone assumptions
- detector naming conventions
- local road/intersection naming
- map projections or coordinate systems
- public dashboard copy and city-specific explanations

## What should remain reusable

- chunked processing design
- DuckDB-based local analytics
- 15-minute interval model
- aggregation patterns
- reproducibility metadata
- public reporting structure
