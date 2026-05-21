import pandas as pd
import json
from pathlib import Path

INPUT = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped\charts\top_20_busiest_scats_sites_named.csv")
OUTPUT = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped\top_20_scats_map_data.json")

df = pd.read_csv(INPUT)

# Normalise column names
df.columns = [c.strip().lower() for c in df.columns]

# Rename if needed
rename_map = {
    "lat": "latitude",
    "lon": "longitude",
    "lng": "longitude",
    "volume": "total_cleaned_volume",
    "total_volume": "total_cleaned_volume",
    "site": "site_id",
    "name": "site_name",
}

df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

required = ["site_id", "site_name", "latitude", "longitude", "total_cleaned_volume"]
missing = [c for c in required if c not in df.columns]

if missing:
    raise RuntimeError(f"Missing required columns: {missing}. Available columns: {list(df.columns)}")

df = df.dropna(subset=["latitude", "longitude"])

df["site_id"] = df["site_id"].astype(float).astype(int).astype(str)
df["site_name"] = df["site_name"].fillna("").astype(str)
df["latitude"] = df["latitude"].astype(float)
df["longitude"] = df["longitude"].astype(float)
df["total_cleaned_volume"] = df["total_cleaned_volume"].astype(float).astype(int)

records = []

for _, row in df.iterrows():
    records.append({
        "site_id": row["site_id"],
        "name": row["site_name"],
        "lat": row["latitude"],
        "lng": row["longitude"],
        "total": int(row["total_cleaned_volume"]),
        "total_millions": round(row["total_cleaned_volume"] / 1_000_000, 1),
        "google_maps_url": f"https://www.google.com/maps/search/?api=1&query={row['latitude']},{row['longitude']}"
    })

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(records, f, indent=2, ensure_ascii=False)

print(f"Wrote {OUTPUT}")
print(f"Records: {len(records)}")