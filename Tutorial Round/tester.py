import re
import pandas as pd
import matplotlib.pyplot as plt


def load_prices(files):
    dfs = []

    for f in files:
        df = pd.read_csv(f, sep=";")
        dfs.append(df)

    df = pd.concat(dfs, ignore_index=True)

    # sort by time properly
    df = df.sort_values(["day", "timestamp", "product"]).reset_index(drop=True)

    return df


def load_trades(files):
    dfs = []

    for f in files:
        df = pd.read_csv(f, sep=";")

        # trades CSVs do not contain a day column, so infer it from filename
        if "day" not in df.columns:
            match = re.search(r"day_(-?\d+)", f)
            if match:
                df["day"] = int(match.group(1))
            else:
                raise ValueError(f"Could not infer day from filename: {f}")

        dfs.append(df)

    df = pd.concat(dfs, ignore_index=True)
    df = df.sort_values(["day", "timestamp", "symbol"]).reset_index(drop=True)

    return df


prices = load_prices(
    ["./data/prices_round_0_day_-2.csv", "./data/prices_round_0_day_-1.csv"]
)

trades = load_trades(
    [
        "./data/trades_round_0_day_-2.csv",
        "./data/trades_round_0_day_-1.csv",
    ]
)

prices["best_bid"] = prices["bid_price_1"]
prices["best_ask"] = prices["ask_price_1"]

# Use raw timestamp for a single-day view
prices["time"] = prices["timestamp"]

# Use raw timestamp for trades as well
trades["time"] = trades["timestamp"]

MAX_TIMESTAMP = 400_000
TARGET_DAY = -1

emerald_prices = prices[
    (prices["product"] == "EMERALDS")
    & (prices["day"] == TARGET_DAY)
    & (prices["timestamp"] <= MAX_TIMESTAMP)
]


tomato_prices = prices[
    (prices["product"] == "TOMATOES")
    & (prices["day"] == TARGET_DAY)
    & (prices["timestamp"] <= MAX_TIMESTAMP)
]

emerald_trades = trades[
    (trades["symbol"] == "EMERALDS")
    & (trades["day"] == TARGET_DAY)
    & (trades["timestamp"] <= MAX_TIMESTAMP)
]


tomato_trades = trades[
    (trades["symbol"] == "TOMATOES")
    & (trades["day"] == TARGET_DAY)
    & (trades["timestamp"] <= MAX_TIMESTAMP)
]


def plot_bid_ask_scatter(df, product_name, filename, trades_df=None):
    df = df.sort_values("time").copy()

    fig, ax = plt.subplots(figsize=(12, 6))

    # Plot bid (blue)
    ax.scatter(
        df["time"],
        df["best_bid"],
        label=f"{product_name} Bid",
        color="blue",
        s=10,
    )

    # Plot ask (red)
    ax.scatter(
        df["time"],
        df["best_ask"],
        label=f"{product_name} Ask",
        color="red",
        s=10,
    )

    # Overlay trades (bold)
    if trades_df is not None and not trades_df.empty:
        trades_df = trades_df.sort_values("time").copy()
        ax.scatter(
            trades_df["time"],
            trades_df["price"],
            label=f"{product_name} Trades",
            color="black",
            s=40,  # bigger dots
            marker="x",  # distinct marker
            linewidths=1.5,  # thicker lines
            alpha=0.9,
        )

    ax.set_title(f"{product_name} Bid vs Ask (Scatter)")
    ax.set_xlabel("Timestamp")
    ax.ticklabel_format(style="plain", axis="x")
    ax.ticklabel_format(style="plain", axis="y")
    ax.get_yaxis().get_major_formatter().set_useOffset(False)
    ax.set_ylabel("Price")
    ax.legend()
    ax.grid(alpha=0.3)
    ax.margins(x=0.01)
    # Force y-axis to reflect actual price range cleanly
    ax.set_ylim(df["best_bid"].min() - 1, df["best_ask"].max() + 1)

    plt.tight_layout()
    plt.savefig(filename)
    print(f"Saved {product_name} bid/ask scatter plot to {filename}")


def plot_trades_scatter(df, product_name, filename):
    df = df.sort_values("time").copy()

    fig, ax = plt.subplots(figsize=(12, 6))

    ax.scatter(
        df["time"],
        df["price"],
        label=f"{product_name} Trades",
        color="purple",
        s=10,
    )

    ax.set_title(f"{product_name} Trades (Scatter)")
    ax.set_xlabel("Timestamp")
    ax.ticklabel_format(style="plain", axis="x")
    ax.ticklabel_format(style="plain", axis="y")
    ax.get_yaxis().get_major_formatter().set_useOffset(False)
    ax.set_ylabel("Trade Price")
    ax.legend()
    ax.grid(alpha=0.3)
    ax.margins(x=0.01)

    plt.tight_layout()
    plt.savefig(filename)
    print(f"Saved {product_name} trades scatter plot to {filename}")


def plot_trades_with_quantity(df, product_name, filename):
    df = df.sort_values("time").copy()

    fig, (ax1, ax2) = plt.subplots(
        2,
        1,
        figsize=(12, 8),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )

    # Top panel: trade price over time
    ax1.scatter(
        df["time"],
        df["price"],
        label=f"{product_name} Trades",
        color="purple",
        s=18,
        alpha=0.8,
    )
    ax1.set_title(f"{product_name} Trades with Quantity")
    ax1.set_ylabel("Trade Price")
    ax1.ticklabel_format(style="plain", axis="y")
    ax1.get_yaxis().get_major_formatter().set_useOffset(False)
    ax1.grid(alpha=0.3)
    ax1.legend(loc="best")

    # Bottom panel: trade quantity over time
    ax2.scatter(
        df["time"],
        df["quantity"],
        color="black",
        s=16,
        alpha=0.8,
    )
    ax2.set_xlabel("Timestamp")
    ax2.set_ylabel("Quantity")
    ax2.ticklabel_format(style="plain", axis="x")
    ax2.ticklabel_format(style="plain", axis="y")
    ax2.get_yaxis().get_major_formatter().set_useOffset(False)
    ax2.grid(alpha=0.3)
    ax2.margins(x=0.01)

    plt.tight_layout()
    plt.savefig(filename)
    print(f"Saved {product_name} trades/quantity plot to {filename}")


plot_bid_ask_scatter(
    emerald_prices, "Emeralds", "emerald_bid_ask_scatter.png", emerald_trades
)
plot_bid_ask_scatter(
    tomato_prices, "Tomatoes", "tomato_bid_ask_scatter.png", tomato_trades
)

plot_trades_with_quantity(
    emerald_trades,
    "Emeralds",
    "emerald_trades_quantity.png",
)
plot_trades_with_quantity(
    tomato_trades,
    "Tomatoes",
    "tomato_trades_quantity.png",
)
