# DuckDB Schema Exports

This folder contains schema-only exports from the DuckDB databases used in the Melbourne SCATS Intelligence project.

The full DuckDB database files are intentionally excluded from GitHub because they are too large for normal repository storage.

## Included bundle

- `scats_schema_bundle_2026-04-14/`

## Included schema types

The bundle includes schema, index and table-list exports for the main SCATS DuckDB databases, including:

- `scats_schema.sql`
- `scats_indexes.sql`
- `scats_tables.txt`
- `scats_continuation_schema.sql`
- `scats_continuation_indexes.sql`
- `scats_continuation_tables.txt`
- `scats_recovery_schema.sql`
- `scats_recovery_indexes.sql`
- `scats_recovery_tables.txt`

## Core tables and views

The SCATS databases use a detector-day structure as the main fact model. Important schema objects include:

- `scats_detector_day`
- `scats_expected_date`
- `scats_site`
- `source_file`
- `scats_15min_long`
- `scats_missing_dates`

## Why this matters

These schema exports allow engineers and researchers to inspect the database structure without needing the full local DuckDB database files.

They are included to improve reproducibility, portability and adaptation to other cities.
