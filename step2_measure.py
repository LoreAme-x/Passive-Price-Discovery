"""
STEP 2 — MEASURE PRICE DISCOVERY
================================

Run it with:    python step2_measure.py

"Price discovery" means: does a stock's price reflect what is happening to that
company, or does it just move with the market?

Everything comes from one regression, run for each stock and each year:

        stock return  =  a  +  b * market return  +  error

  1. BETA           b, how much the stock moves when the market moves.
  2. COMOVEMENT     the R-squared. How much of the stock's movement the market
                    alone explains. Close to 1 means the stock is basically the
                    index; close to 0 means it moves on its own news.
  3. OWN VOLATILITY the size of the "error", annualised. The company-specific
                    movement that is left over.
  4. REACTION DELAY run the regression again with yesterday's and the previous
                    days' market returns added. If those lagged terms add a lot
                    of explanatory power, the stock reacts late.

Plus two things needed later:

  5. TRADING RANGE  average daily (high - low) / close, in %. A rough proxy for
                    what it costs to trade.
  6. DOLLAR VOLUME  average close x volume. Used as the size control in step 3.

Output: output/measures_by_stock.csv and output/measures_by_year.csv
"""

import sqlite3

import numpy as np
import pandas as pd

import config


def load_returns():
    """
    Reads prices from SQLite and computes daily log returns.

    The previous day's close comes from the SQL window function LAG(), with
    PARTITION BY ticker. The partition matters: without it you would compute a
    "return" between the last day of one stock and the first day of the next.

    The logarithm is taken in Python, not SQL. In SQLite, LOG() is the base-10
    logarithm and LN() is the natural one, and neither is guaranteed to exist
    depending on how SQLite was compiled. Getting that wrong raises no error --
    it just multiplies every return by 0.43 and the numbers still look fine.
    """
    query = """
        SELECT ticker, date, close, volume, high, low,
               LAG(close) OVER (PARTITION BY ticker ORDER BY date) AS previous_close
        FROM prices
        ORDER BY ticker, date
    """
    with sqlite3.connect(config.DB_FILE) as conn:
        df = pd.read_sql_query(query, conn)
        universe = pd.read_sql_query("SELECT * FROM universe", conn)

    df["date"] = pd.to_datetime(df["date"])
    df["ret"] = np.log(df["close"] / df["previous_close"])
    return df.dropna(subset=["ret"]), universe


def regression(y, X):
    """
    Plain OLS with an intercept. Returns (coefficients, r_squared, residuals).
    A column of ones is added so the regression has an intercept.
    """
    X_with_intercept = np.column_stack([np.ones(len(y)), X])
    coefficients, *_ = np.linalg.lstsq(X_with_intercept, y, rcond=None)
    residuals = y - X_with_intercept @ coefficients

    total_variation = ((y - y.mean()) ** 2).sum()
    r_squared = 1 - (residuals ** 2).sum() / total_variation if total_variation > 0 else np.nan
    return coefficients, r_squared, residuals


def measure_one(stock_rows, market_returns):
    """All six measures for one stock over one stretch of time."""
    data = pd.DataFrame({"stock": stock_rows["ret"], "market": market_returns}).dropna()
    for lag in range(1, config.MARKET_LAGS + 1):
        data[f"lag{lag}"] = market_returns.reindex(data.index).shift(lag)
    data = data.dropna()

    if len(data) < config.MIN_DAYS_PER_YEAR:
        return None

    y = data["stock"].to_numpy()
    market = data["market"].to_numpy()

    # --- same-day regression ---
    coefficients, r_squared, residuals = regression(y, market.reshape(-1, 1))
    beta = coefficients[1]
    own_volatility = residuals.std(ddof=1) * np.sqrt(config.TRADING_DAYS_PER_YEAR)

    # --- same regression plus lagged market returns ---
    lag_names = [f"lag{lag}" for lag in range(1, config.MARKET_LAGS + 1)]
    _, r_squared_with_lags, _ = regression(y, data[["market"] + lag_names].to_numpy())

    if r_squared_with_lags and r_squared_with_lags > 0:
        reaction_delay = 1 - r_squared / r_squared_with_lags
    else:
        reaction_delay = np.nan

    # --- trading cost and size ---
    rows = stock_rows.loc[stock_rows.index.intersection(data.index)]
    trading_range = ((rows["high"] - rows["low"]) / rows["close"]).mean() * 100
    dollar_volume = (rows["close"] * rows["volume"]).mean()

    return {
        "days": len(data),
        "beta": round(float(beta), 4),
        "comovement_r2": round(float(r_squared), 4),
        "own_volatility": round(float(own_volatility), 4),
        "reaction_delay": round(float(reaction_delay), 4),
        "trading_range_pct": round(float(trading_range), 4),
        "dollar_volume": round(float(dollar_volume), 0),
    }


def main():
    print("STEP 2 — measuring price discovery\n")

    data, universe = load_returns()
    tier_of = dict(zip(universe["ticker"], universe["tier"]))

    market = (data[data["ticker"] == config.BENCHMARK]
              .set_index("date")["ret"].sort_index())

    if market.empty:
        raise SystemExit("No benchmark data found. Re-run step1.")

    by_stock_rows = []
    by_year_rows = []
    tickers = [t for t in universe["ticker"] if t in set(data["ticker"])]

    for i, ticker in enumerate(tickers, start=1):
        stock = data[data["ticker"] == ticker].set_index("date").sort_index()

        full_sample = measure_one(stock, market)
        if full_sample:
            by_stock_rows.append({"ticker": ticker, "tier": tier_of[ticker],
                                  **full_sample})

        for year, year_rows in stock.groupby(stock.index.year):
            one_year = measure_one(year_rows, market)
            if one_year:
                by_year_rows.append({"ticker": ticker, "tier": tier_of[ticker],
                                     "year": int(year), **one_year})

        if i % 50 == 0 or i == len(tickers):
            print(f"  {i}/{len(tickers)} stocks measured")

    by_stock = pd.DataFrame(by_stock_rows)
    by_year = pd.DataFrame(by_year_rows)

    # Size rank within the whole sample, used to build the matched sample later
    by_stock["size_rank"] = by_stock["dollar_volume"].rank(ascending=False)

    by_stock.to_csv(config.STOCK_CSV, index=False)
    by_year.to_csv(config.YEARLY_CSV, index=False)

    with sqlite3.connect(config.DB_FILE) as conn:
        by_stock.to_sql("measures_by_stock", conn, if_exists="replace", index=False)
        by_year.to_sql("measures_by_year", conn, if_exists="replace", index=False)

    print(f"\n  {len(by_stock)} stocks, {len(by_year)} stock-years\n")
    print("Averages by index tier:")
    summary = by_stock.groupby("tier")[
        ["beta", "comovement_r2", "own_volatility", "reaction_delay",
         "trading_range_pct"]].mean().round(3)
    counts = by_stock.groupby("tier").size().rename("n")
    print(pd.concat([counts, summary], axis=1).to_string())

    print("\nNext: python step3_regression.py")


if __name__ == "__main__":
    main()
