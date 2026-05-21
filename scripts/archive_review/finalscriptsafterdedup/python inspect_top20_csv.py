import pandas as pd

file = r"A:\TrafficAnalytics\PROJECTS\reports\deduped\charts\top_20_busiest_scats_sites_named.csv"

df = pd.read_csv(file)

print("\nColumns found:\n")
for c in df.columns:
    print(c)

print("\nPreview:\n")
print(df.head(5))