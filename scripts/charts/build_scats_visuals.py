from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

BASE = Path(r"A:\TrafficAnalytics\PROJECTS\reports\scats_clean_outputs_v2")
OUT = BASE / "visuals"
OUT.mkdir(exist_ok=True)

print("Loading datasets...")

daily = pd.read_csv(BASE / "04_daily_total_volume.csv")
time_profile = pd.read_csv(BASE / "08_time_bin_profile_network.csv")
top_sites = pd.read_csv(BASE / "05_top_100_sites_by_total_volume.csv")

# -------------------------
# DAILY TOTAL VOLUME
# -------------------------

print("Building daily volume chart...")

daily["count_date"] = pd.to_datetime(daily["count_date"])

plt.figure(figsize=(16,6))
plt.plot(daily["count_date"], daily["total_volume"])
plt.title("Daily Traffic Volume (Network Wide)")
plt.xlabel("Date")
plt.ylabel("Vehicles")
plt.tight_layout()

plt.savefig(OUT / "daily_volume_timeseries.png")
plt.close()

# -------------------------
# TIME OF DAY PROFILE
# -------------------------

print("Building time profile chart...")

plt.figure(figsize=(14,6))
plt.plot(time_profile["time_bin"], time_profile["total_volume"])
plt.xticks(rotation=90)
plt.title("Network Traffic Profile by Time of Day")
plt.xlabel("Time")
plt.ylabel("Vehicles")
plt.tight_layout()

plt.savefig(OUT / "network_time_profile.png")
plt.close()

# -------------------------
# TOP 100 SITES
# -------------------------

print("Building top sites chart...")

top20 = top_sites.head(20)

plt.figure(figsize=(12,8))
plt.barh(
    top20["scats_site"].astype(str),
    top20["total_volume"]
)

plt.gca().invert_yaxis()

plt.title("Top 20 SCATS Sites by Total Volume")
plt.xlabel("Total Vehicles")
plt.ylabel("SCATS Site")

plt.tight_layout()

plt.savefig(OUT / "top_20_sites_bar_chart.png")
plt.close()

print("\nCharts created in:")
print(OUT)