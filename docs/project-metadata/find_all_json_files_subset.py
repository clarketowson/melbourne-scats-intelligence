from pathlib import Path
import pandas as pd

BASE = Path(r"A:\TrafficAnalytics\PROJECTS")

KEYWORDS = [
    "scats",
    "monthly",
    "daily",
    "runtime",
    "processing",
    "time_bin",
    "peak",
    "weekday",
    "weekend",
    "site",
    "traffic",
    "archetype",
    "kepler",
    "animation",
    "summary",
    "profile",
    "volume",
]

results = []

for path in BASE.rglob("*.json"):
    lower = str(path).lower()

    if any(k in lower for k in KEYWORDS):
        results.append({
            "filename": path.name,
            "full_path": str(path),
            "parent_directory": str(path.parent),
        })

df = pd.DataFrame(results)

output = BASE / "scats_relevant_json_files.csv"
df.to_csv(output, index=False)

print(f"Found {len(df):,} relevant JSON files")
print(f"Written to: {output}")