# Reproducibility

This repository is intended to make the SCATS intelligence pipeline inspectable and reproducible.

## What is included

- processing scripts
- aggregation scripts
- wrapper scripts
- selected output CSVs and JSON files
- audit reports
- chart/report generation assets where practical
- selected skipped CSV, TXT, JSON and LOG files under extras/skipped_text_data_logs/
- manually reviewed include files under extras/reviewed_includes/

## What is excluded

- raw databases
- DuckDB database files
- SQLite databases
- videos
- music
- temporary binary files
- very large generated exports over GitHub-safe limits

## Why large files are excluded

The working project is much larger than the GitHub repository. Large databases and generated media should be recreated locally or distributed through a separate large-file channel.

## Suggested reproduction workflow

1. Download the relevant source data.
2. Build the local database.
3. Run cleaning and deduplication scripts.
4. Run monthly chunked aggregation scripts.
5. Validate completion metadata.
6. Generate charts, maps and public outputs.
