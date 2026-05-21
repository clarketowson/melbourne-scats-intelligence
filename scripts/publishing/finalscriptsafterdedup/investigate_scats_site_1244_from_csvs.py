import argparse
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

SITE_ID = 1244
SITE_LABEL = "Koo Wee Rup-Longwarry (Rossiter) / Streetation"

def read_csv_if_exists(path):
    if path.exists():
        return pd.read_csv(path)
    return None

def save_line(df, x, y, title, subtitle, outpath):
    fig, ax = plt.subplots(figsize=(15, 7))
    ax.plot(df[x], df[y], linewidth=1.8)
    ax.set_title(title, fontsize=18, pad=24)
    ax.text(0.5, 1.02, subtitle, transform=ax.transAxes, ha="center", fontsize=11)
    ax.set_xlabel("")
    ax.set_ylabel("Vehicle movements")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(outpath, dpi=180)
    plt.close(fig)

def save_bar(df, x, y, title, subtitle, outpath):
    fig, ax = plt.subplots(figsize=(13, 7))
    ax.bar(df[x], df[y])
    ax.set_title(title, fontsize=18, pad=24)
    ax.text(0.5, 1.02, subtitle, transform=ax.transAxes, ha="center", fontsize=11)
    ax.set_xlabel("")
    ax.set_ylabel("Vehicle movements")
    ax.tick_params(axis="x", rotation=45)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(outpath, dpi=180)
    plt.close(fig)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-dir",
        default=r"A:\TrafficAnalytics\PROJECTS\reports\deduped",
        help="Folder containing existing deduped CSV output files"
    )
    parser.add_argument("--site", type=int, default=SITE_ID)
    args = parser.parse_args()

    base = Path(args.base_dir)
    out = base / f"site_{args.site}_csv_investigation"
    out.mkdir(parents=True, exist_ok=True)

    site_month_path = base / "site_month_totals.csv"
    site_totals_path = base / "site_totals.csv"
    map_path = base / "all_scats_sites_map_data_audit.csv"
    monthly_path = base / "monthly_totals.csv"

    site_month = read_csv_if_exists(site_month_path)
    if site_month is None:
        site_month = read_csv_if_exists(site_totals_path)

    if site_month is None:
        raise FileNotFoundError("Could not find site_month_totals.csv or site_totals.csv")

    site_month["scats_site"] = pd.to_numeric(site_month["scats_site"], errors="coerce")
    site_month = site_month[site_month["scats_site"] == args.site].copy()

    if site_month.empty:
        raise SystemExit(f"No rows found for SCATS site {args.site}")

    site_month["month_start"] = pd.to_datetime(site_month["month_start"], errors="coerce")
    site_month = site_month.sort_values("month_start")

    site_month["month_site_volume"] = pd.to_numeric(
        site_month["month_site_volume"], errors="coerce"
    )

    site_month["year"] = site_month["month_start"].dt.year
    site_month["month_num"] = site_month["month_start"].dt.month
    site_month["month_name"] = site_month["month_start"].dt.strftime("%b")

    # Metadata
    metadata = None
    map_df = read_csv_if_exists(map_path)
    if map_df is not None:
        map_df["site_id"] = pd.to_numeric(map_df["site_id"], errors="coerce")
        hit = map_df[map_df["site_id"] == args.site]
        if not hit.empty:
            metadata = hit.iloc[0].to_dict()

    # Network comparison
    monthly = read_csv_if_exists(monthly_path)
    if monthly is not None and "volume" in monthly.columns:
        monthly["month_start"] = pd.to_datetime(monthly["month_start"], errors="coerce")
        monthly["volume"] = pd.to_numeric(monthly["volume"], errors="coerce")
        site_month = site_month.merge(
            monthly[["month_start", "volume"]].rename(columns={"volume": "network_month_volume"}),
            on="month_start",
            how="left"
        )
        site_month["share_of_network"] = (
            site_month["month_site_volume"] / site_month["network_month_volume"]
        )

    # Rolling trend and anomaly flags
    site_month["rolling_12m_avg"] = (
        site_month["month_site_volume"]
        .rolling(12, min_periods=3)
        .mean()
    )
    site_month["ratio_to_12m_avg"] = (
        site_month["month_site_volume"] / site_month["rolling_12m_avg"]
    )

    anomalies = site_month[
        (site_month["ratio_to_12m_avg"] >= 1.5) |
        (site_month["ratio_to_12m_avg"] <= 0.5)
    ].copy()

    # Month-of-year profile
    seasonality = (
        site_month
        .groupby(["month_num", "month_name"], as_index=False)
        .agg(
            avg_month_volume=("month_site_volume", "mean"),
            median_month_volume=("month_site_volume", "median"),
            max_month_volume=("month_site_volume", "max"),
            years_seen=("year", "nunique")
        )
        .sort_values("month_num")
    )

    # Yearly profile
    yearly = (
        site_month
        .groupby("year", as_index=False)
        .agg(
            annual_volume=("month_site_volume", "sum"),
            months_seen=("month_site_volume", "count"),
            avg_month_volume=("month_site_volume", "mean")
        )
    )

    # Monthly rank among all SCATS sites
    all_sites = pd.read_csv(site_month_path if site_month_path.exists() else site_totals_path)
    all_sites["scats_site"] = pd.to_numeric(all_sites["scats_site"], errors="coerce")
    all_sites["month_start"] = pd.to_datetime(all_sites["month_start"], errors="coerce")
    all_sites["month_site_volume"] = pd.to_numeric(all_sites["month_site_volume"], errors="coerce")

    ranks = all_sites.dropna(subset=["month_start", "month_site_volume"]).copy()
    ranks["monthly_rank"] = ranks.groupby("month_start")["month_site_volume"].rank(
        method="min", ascending=False
    )
    ranks["monthly_site_count"] = ranks.groupby("month_start")["scats_site"].transform("nunique")
    ranks = ranks[ranks["scats_site"] == args.site][
        ["month_start", "monthly_rank", "monthly_site_count"]
    ]

    site_month = site_month.merge(ranks, on="month_start", how="left")

    # Outputs
    site_month.to_csv(out / f"scats_{args.site}_monthly_investigation.csv", index=False)
    yearly.to_csv(out / f"scats_{args.site}_yearly_profile.csv", index=False)
    seasonality.to_csv(out / f"scats_{args.site}_month_of_year_profile.csv", index=False)
    anomalies.to_csv(out / f"scats_{args.site}_possible_monthly_anomalies.csv", index=False)

    save_line(
        site_month,
        "month_start",
        "month_site_volume",
        f"SCATS {args.site} Monthly Traffic Volume",
        SITE_LABEL,
        out / f"scats_{args.site}_monthly_volume.png"
    )

    save_line(
        site_month,
        "month_start",
        "rolling_12m_avg",
        f"SCATS {args.site} 12-Month Rolling Average",
        SITE_LABEL,
        out / f"scats_{args.site}_rolling_12m_average.png"
    )

    save_bar(
        yearly,
        "year",
        "annual_volume",
        f"SCATS {args.site} Annual Traffic Volume",
        SITE_LABEL,
        out / f"scats_{args.site}_yearly_volume.png"
    )

    save_bar(
        seasonality,
        "month_name",
        "avg_month_volume",
        f"SCATS {args.site} Average Month-of-Year Profile",
        SITE_LABEL,
        out / f"scats_{args.site}_month_of_year_profile.png"
    )

    if "share_of_network" in site_month.columns:
        save_line(
            site_month,
            "month_start",
            "share_of_network",
            f"SCATS {args.site} Share of Total SCATS Network Volume",
            SITE_LABEL,
            out / f"scats_{args.site}_share_of_network.png"
        )

    if "monthly_rank" in site_month.columns:
        save_line(
            site_month,
            "month_start",
            "monthly_rank",
            f"SCATS {args.site} Monthly Rank Among SCATS Sites",
            "Lower rank is busier",
            out / f"scats_{args.site}_monthly_rank.png"
        )

    summary = {
        "scats_site": args.site,
        "label": SITE_LABEL,
        "months_seen": int(len(site_month)),
        "first_month": str(site_month["month_start"].min().date()),
        "last_month": str(site_month["month_start"].max().date()),
        "total_volume": int(site_month["month_site_volume"].sum()),
        "avg_monthly_volume": float(site_month["month_site_volume"].mean()),
        "max_monthly_volume": int(site_month["month_site_volume"].max()),
        "busiest_month": str(site_month.loc[site_month["month_site_volume"].idxmax(), "month_start"].date()),
        "possible_anomaly_months": int(len(anomalies)),
    }

    if metadata:
        summary["map_name"] = metadata.get("friendly_name") or metadata.get("site_name")
        summary["municipality"] = metadata.get("municipality")
        summary["latitude"] = metadata.get("latitude")
        summary["longitude"] = metadata.get("longitude")
        summary["traffic_band"] = metadata.get("traffic_band")
        summary["network_rank"] = metadata.get("rank")

    pd.Series(summary).to_json(out / f"scats_{args.site}_summary.json", indent=2)

    print("DONE")
    print(f"Output folder: {out}")
    print()
    for k, v in summary.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    main()