from pathlib import Path
import pandas as pd

BASE = Path(r"A:\TrafficAnalytics\PROJECTS")

json_files = []

for path in BASE.rglob("*.json"):
    try:
        stat = path.stat()

        json_files.append({
            "filename": path.name,
            "full_path": str(path),
            "parent_directory": str(path.parent),
            "size_mb": round(stat.st_size / (1024 * 1024), 3),
            "modified_time": stat.st_mtime,
        })

    except Exception as e:
        print(f"Error reading {path}: {e}")

df = pd.DataFrame(json_files)

if df.empty:
    print("No JSON files found.")
else:
    df = df.sort_values("full_path")

    output_csv = BASE / "all_json_files_inventory.csv"
    df.to_csv(output_csv, index=False)

    print(f"\nFound {len(df):,} JSON files.")
    print(f"Inventory written to:\n{output_csv}\n")

    print(df[[
        "filename",
        "parent_directory",
        "size_mb"
    ]].to_string(index=False))