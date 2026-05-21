# COVID Chunked Export Pack V2.1

Fixes:

- Automatically finds `_common_scats_kepler.py` in the parent `scats_next_animation_packV1` folder.
- Removes the invalid escape sequence warning in the docstring.
- Keeps the chunked one-day-at-a-time behaviour.

## Where to put these files

Recommended:

```text
A:\TrafficAnalytics\PROJECTS\scripts\finalscriptsafterdedup\scats_next_animation_packV1\
```

You can also keep them in the `covid_chunked_export_packV2` subfolder now, because V2.1 searches parent folders.

## Run

```powershell
.\run_generate_kepler_covid_comparison_daysV21_chunked.ps1
```

or:

```powershell
python .\generate_kepler_covid_comparison_daysV21_chunked.py --memory-limit 20GB --threads 6 --keep-chunks
```
