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

BLUE = "#1f77b4"
AM_BLUE = "#2b6cb0"
PM_ORANGE = "#f97316"
GRID = "#d9e2ec"
TEXT = "#1f2937"


def find_file(candidates):
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("Could not find any of: " + ", ".join(str(p) for p in candidates))


def detect_time_and_volume(df):
    time_col = next((c for c in df.columns if c.lower() in ["time_bin", "time", "hhmm"]), None)
    volume_col = next((c for c in df.columns if "volume" in c.lower() or "movement" in c.lower()), None)

    if time_col is None and "interval_index" in df.columns:
        df["time_bin"] = df["interval_index"].apply(
            lambda i: f"{int(i)//4:02d}:{(int(i)%4)*15:02d}"
        )
        time_col = "time_bin"

    if time_col is None:
        raise ValueError("Could not detect time-bin column.")

    if volume_col is None:
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if not numeric_cols:
            raise ValueError("Could not detect numeric volume column.")
        volume_col = numeric_cols[-1]

    return time_col, volume_col


def make_network_time_of_day_profile():
    src = find_file(TIME_BIN_CANDIDATES)
    df = pd.read_csv(src)

    time_col, volume_col = detect_time_and_volume(df)

    grouped = (
        df.groupby(time_col, as_index=False)[volume_col]
        .sum()
        .sort_values(time_col)
    )

    fig, ax = plt.subplots(figsize=(16, 7))

    ax.plot(
        grouped[time_col],
        grouped[volume_col],
        color=BLUE,
        linewidth=2.8,
        label="Total cleaned volume"
    )

    # Highlight AM and PM peak windows if 15-minute HH:MM labels exist
    labels = grouped[time_col].astype(str).tolist()

    def shade_window(start, end, color, label):
        if start in labels and end in labels:
            ax.axvspan(
                labels.index(start),
                labels.index(end),
                color=color,
                alpha=0.14,
                label=label
            )

    shade_window("07:00", "10:00", AM_BLUE, "AM peak window")
    shade_window("16:00", "19:00", PM_ORANGE, "PM peak window")

    ax.set_title(
        "Network Time-of-Day Profile — Melbourne SCATS Network",
        fontsize=18,
        fontweight="bold",
        color=TEXT,
        pad=18
    )
    ax.set_xlabel("15-minute time bin", fontsize=12, color=TEXT)
    ax.set_ylabel("Total cleaned traffic volume", fontsize=12, color=TEXT)

    ax.grid(True, axis="y", color=GRID, linewidth=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ax.tick_params(axis="x", rotation=90, labelsize=8)
    ax.tick_params(axis="y", labelsize=10)

    ax.legend(frameon=False, loc="upper left")

    fig.tight_layout()

    out = CHARTS / "33_network_time_of_day_profile.png"
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)

    print(f"Saved: {out}")


def make_peak_window_share_bar():
    src = find_file(PEAK_SHARE_CANDIDATES)
    df = pd.read_csv(src)

    am_col = next((c for c in df.columns if "am" in c.lower() and "share" in c.lower()), None)
    pm_col = next((c for c in df.columns if "pm" in c.lower() and "share" in c.lower()), None)

    if am_col and pm_col:
        plot_df = pd.DataFrame({
            "Peak Window": ["AM Peak", "PM Peak"],
            "Share": [df[am_col].mean(), df[pm_col].mean()]
        })
    else:
        category_col = next(
            (c for c in df.columns if c.lower() in ["window", "peak_window", "period", "category"]),
            None
        )
        share_col = next(
            (c for c in df.columns if "share" in c.lower() or "percent" in c.lower() or "pct" in c.lower()),
            None
        )

        if category_col is None or share_col is None:
            raise ValueError("Could not detect peak-share columns.")

        plot_df = (
            df.groupby(category_col, as_index=False)[share_col]
            .mean()
            .rename(columns={category_col: "Peak Window", share_col: "Share"})
        )

    if plot_df["Share"].max() <= 1:
        plot_df["Share"] *= 100

    colors = [
        AM_BLUE if "am" in str(label).lower() else PM_ORANGE
        for label in plot_df["Peak Window"]
    ]

    fig, ax = plt.subplots(figsize=(10, 6))

    bars = ax.bar(
        plot_df["Peak Window"],
        plot_df["Share"],
        color=colors,
        edgecolor="white",
        linewidth=1.5
    )

    ax.set_title(
        "Peak Window Share — Melbourne SCATS Network",
        fontsize=18,
        fontweight="bold",
        color=TEXT,
        pad=18
    )
    ax.set_xlabel("Peak window", fontsize=12, color=TEXT)
    ax.set_ylabel("Share of total cleaned traffic volume (%)", fontsize=12, color=TEXT)

    ax.grid(True, axis="y", color=GRID, linewidth=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    for bar, val in zip(bars, plot_df["Share"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            val,
            f"{val:.2f}%",
            ha="center",
            va="bottom",
            fontsize=12,
            fontweight="bold",
            color=TEXT
        )

    fig.tight_layout()

    out = CHARTS / "34_peak_window_share_bar.png"
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)

    print(f"Saved: {out}")


if __name__ == "__main__":
    make_network_time_of_day_profile()
    make_peak_window_share_bar()
    print("Done.")