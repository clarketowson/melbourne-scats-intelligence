# Quickstart

This repository is designed as a reproducible reference implementation, not as a small toy example.

## 1. Prepare local folders

Recommended local working structure:

A:\TrafficAnalytics\
  DATA\
  PROJECTS\
  DuckDBTemp\

The public GitHub repository intentionally excludes raw databases, large CSV archives, videos and temporary files.

## 2. Install dependencies

Recommended stack:

- Python 3.12+
- DuckDB
- pandas
- matplotlib
- PowerShell on Windows

## 3. Understand the pipeline

The broad pipeline is:

raw source data
  -> ingest
  -> clean
  -> deduplicate
  -> normalize to 15-minute observations
  -> aggregate by month
  -> merge outputs
  -> generate charts/maps/reports

## 4. Start with the documentation

Read these files first:

- METHODOLOGY.md
- REPRODUCIBILITY.md
- CITY_ADAPTATION_GUIDE.md
- HARDWARE_NOTES.md

## 5. Run carefully

Many scripts are designed for large datasets and may take hours. Review paths and configuration inside each script before running.
