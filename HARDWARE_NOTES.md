# Hardware Notes

This project was built for large local analytics.

## Recommended environment

- 64 GB RAM or more where possible
- NVMe storage for temporary DuckDB spill files
- Windows or Linux workstation
- DuckDB
- Python
- PowerShell wrappers for long-running jobs

## Performance notes

Large aggregations may spill hundreds of gigabytes to temporary storage. Avoid slow network drives for DuckDB temp directories where possible.

## Practical advice

Run the pipeline in chunks, especially by month. Avoid trying to process the entire historical dataset in one giant query unless you have enough memory and fast local storage.
