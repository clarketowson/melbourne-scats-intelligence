import pandas as pd

# --------------------------------------------
# FILE PATHS (update if needed)
# --------------------------------------------

SITE_TOTALS_FILE = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\site_totals.csv"

SITE_LOCATIONS_FILE = r"A:\TrafficAnalytics\DATA\SCATS\scats_site_locations.csv"

OUTPUT_FILE = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\kepler_site_totals.csv"

# --------------------------------------------
# LOAD DATA
# --------------------------------------------

print("Loading site totals...")
site_totals = pd.read_csv(SITE_TOTALS_FILE)

print("Loading site locations...")
site_locations = pd.read_csv(SITE_LOCATIONS_FILE)

# --------------------------------------------
# STANDARDISE COLUMN NAMES
# --------------------------------------------

site_totals.columns = site_totals.columns.str.lower()
site_locations.columns = site_locations.columns.str.lower()

# Rename if necessary
rename_map = {
    "site_id": "scats_site",
    "site": "scats_site",
    "lat": "latitude",
    "lon": "longitude"
}

site_locations.rename(columns=rename_map, inplace=True)

# --------------------------------------------
# MERGE DATA
# --------------------------------------------

print("Merging datasets...")

merged = pd.merge(
    site_totals,
    site_locations,
    on="scats_site",
    how="left"
)

# --------------------------------------------
# CHECK FOR MISSING LOCATIONS
# --------------------------------------------

missing = merged["latitude"].isna().sum()

print(f"Missing coordinates: {missing}")

if missing > 0:
    print("WARNING: Some SCATS sites have no coordinates!")

# --------------------------------------------
# SELECT FINAL COLUMNS
# --------------------------------------------

final_columns = [
    "scats_site",
    "site_name",
    "latitude",
    "longitude",
    "total_volume"
]

# Keep only columns that exist
final_columns = [c for c in final_columns if c in merged.columns]

merged = merged[final_columns]

# --------------------------------------------
# SAVE OUTPUT
# --------------------------------------------

merged.to_csv(OUTPUT_FILE, index=False)

print("Done.")
print("Output file:")
print(OUTPUT_FILE)