from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

BASE = Path(r"A:\TrafficAnalytics\PROJECTS\reports\deduped")
CHARTS = BASE / "charts"
CHARTS.mkdir(exist_ok=True)

TIME_BIN_CANDIDATES = [
    BASE / "time_bin_profile.csv",
    BASE / "chunked_busiest_time_bin_monthly.csv",
]

PEAK_SHARE_CANDIDATES = [
    BASE / "peak_shares.csv",
    BASE / "chunked_peak_shares_monthly.csv",
]


def find_file(candidates):
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("Could not find any of: " + ", ".join(str(p) for p in candidates))


def make_network_time_of_day_profile():
    src = find_file(TIME_BIN_CANDIDATES)
    df = pd.read_csv(src)

    print(f"Loaded time-bin data: {src}")
    print(df.columns.tolist())

    # Try to detect useful columns
    time_col = next((c for c in df.columns if c.lower() in ["time_bin", "time", "hhmm"]), None)
    volume_col = next((c for c in df.columns if "volume" in c.lower() or "movement" in c.lower()), None)

    if time_col is None:
        if "interval_index" in df.columns:
            df["time_bin"] = df["interval_index"].apply(
                lambda i: f"{int(i)//4:02d}:{(int(i)%4)*15:02d}"
            )
            time_col = "time_bin"
        else:
            raise ValueError("Could not detect time-bin column.")

    if volume_col is None:
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if not numeric_cols:
            raise ValueError("Could not detect numeric volume column.")
        volume_col = numeric_cols[-1]

    grouped = (
        df.groupby(time_col, as_index=False)[volume_col]
        .sum()
        .sort_values(time_col)
    )

    plt.figure(figsize=(16, 7))
    plt.plot(grouped[time_col], grouped[volume_col], linewidth=2)
    plt.xticks(rotation=90)
    plt.title("Network Time-of-Day Profile — Melbourne SCATS Network")
    plt.xlabel("15-minute time bin")
    plt.ylabel("Total cleaned traffic volume")
    plt.tight_layout()

    out = CHARTS / "33_network_time_of_day_profile.png"
    plt.savefig(out, dpi=180)
    plt.close()

    print(f"Saved: {out}")


def make_peak_window_share_bar():
    src = find_file(PEAK_SHARE_CANDIDATES)
    df = pd.read_csv(src)

    print(f"Loaded peak-share data: {src}")
    print(df.columns.tolist())

    # If already has AM/PM share columns
    lower_cols = {c.lower(): c for c in df.columns}

    am_col = next((c for c in df.columns if "am" in c.lower() and "share" in c.lower()), None)
    pm_col = next((c for c in df.columns if "pm" in c.lower() and "share" in c.lower()), None)

    if am_col and pm_col:
        am_val = df[am_col].mean()
        pm_val = df[pm_col].mean()

        plot_df = pd.DataFrame({
            "Peak Window": ["AM Peak", "PM Peak"],
            "Share": [am_val, pm_val]
        })

    else:
        # Fallback: try long format with window/category + share/value
        category_col = next(
            (c for c in df.columns if c.lower() in ["window", "peak_window", "period", "category"]),
            None
        )
        share_col = next(
            (c for c in df.columns if "share" in c.lower() or "percent" in c.lower() or "pct" in c.lower()),
            None
        )

        if category_col is None or share_col is None:
            raise ValueError(
                "Could not detect peak-share structure. "
                "Expected AM/PM share columns or long format with window/share columns."
            )

        plot_df = (
            df.groupby(category_col, as_index=False)[share_col]
            .mean()
            .rename(columns={category_col: "Peak Window", share_col: "Share"})
        )

    # Convert fraction to percent if needed
    if plot_df["Share"].max() <= 1:
        plot_df["Share"] = plot_df["Share"] * 100

    plt.figure(figsize=(10, 6))
    plt.bar(plot_df["Peak Window"], plot_df["Share"])
    plt.title("Peak Window Share — Melbourne SCATS Network")
    plt.xlabel("Peak window")
    plt.ylabel("Share of total cleaned traffic volume (%)")

    for i, val in enumerate(plot_df["Share"]):
        plt.text(i, val, f"{val:.2f}%", ha="center", va="bottom")

    plt.tight_layout()

    out = CHARTS / "34_peak_window_share_bar.png"
    plt.savefig(out, dpi=180)
    plt.close()

    print(f"Saved: {out}")


if __name__ == "__main__":
    make_network_time_of_day_profile()
    make_peak_window_share_bar()
    print("Done.")