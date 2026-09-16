"""
STEP 4 — FROM PRICE DISCOVERY TO THE COST OF CAPITAL
====================================================

Run it with:    python step4_cost_of_capital.py

Steps 2 and 3 measured how prices behave. This step asks the question a company
actually cares about: does any of it change what it costs to raise equity?

The cost of equity is built in two pieces.

PIECE 1 — the textbook part (CAPM)

        cost of equity  =  risk-free rate  +  beta * market risk premium

PIECE 2 — the liquidity part

    Amihud & Mendelson (1986): investors demand a higher return to hold assets
    that are expensive to trade. So:

        extra return  =  k  *  trading cost

    where k is an ASSUMPTION set in config.py, not estimated from this data.
    The script therefore reports a low, a base and a high case.

The honest finding is usually that the range created by the assumption is wider
than the difference between the groups of stocks. That is worth saying out loud:
it is the reason nobody can quote a precise figure for how much index investing
has raised the cost of capital.

Output: output/cost_of_equity.csv
"""

import sqlite3

import pandas as pd

import config


def capm_cost_of_equity(beta):
    """Risk-free rate plus beta times the market risk premium, in percent."""
    return (config.RISK_FREE_RATE + beta * config.MARKET_RISK_PREMIUM) * 100


def liquidity_premium_bp(trading_cost_pct, k):
    """Extra required return in basis points per year."""
    return k * trading_cost_pct


def main():
    print("STEP 4 — cost of equity\n")

    measures = pd.read_csv(config.STOCK_CSV)

    rows = []
    for _, stock in measures.iterrows():
        capm = capm_cost_of_equity(stock["beta"])
        trading_cost = stock["trading_range_pct"]

        base = liquidity_premium_bp(trading_cost, config.ILLIQUIDITY_PREMIUM_BP)
        low = liquidity_premium_bp(trading_cost, config.ILLIQUIDITY_PREMIUM_LOW)
        high = liquidity_premium_bp(trading_cost, config.ILLIQUIDITY_PREMIUM_HIGH)

        rows.append({
            "ticker": stock["ticker"],
            "tier": stock["tier"],
            "beta": stock["beta"],
            "capm_pct": round(capm, 2),
            "trading_cost_pct": round(trading_cost, 3),
            "liquidity_premium_low_bp": round(low, 0),
            "liquidity_premium_bp": round(base, 0),
            "liquidity_premium_high_bp": round(high, 0),
            "total_cost_of_equity_pct": round(capm + base / 100, 2),
            # assumptions stored next to the numbers they produced, so you can
            # always answer "where did this come from?"
            "assumed_risk_free": config.RISK_FREE_RATE,
            "assumed_market_premium": config.MARKET_RISK_PREMIUM,
            "assumed_k_bp_per_pct": config.ILLIQUIDITY_PREMIUM_BP,
        })

    cost = pd.DataFrame(rows)
    cost.to_csv(config.COST_CSV, index=False)

    with sqlite3.connect(config.DB_FILE) as conn:
        cost.to_sql("cost_of_equity", conn, if_exists="replace", index=False)

    by_tier = cost.groupby("tier")[
        ["beta", "capm_pct", "trading_cost_pct", "liquidity_premium_low_bp",
         "liquidity_premium_bp", "liquidity_premium_high_bp",
         "total_cost_of_equity_pct"]].mean().round(2)

    print("Average by index tier:")
    print(by_tier.to_string())

    if "sp500" in by_tier.index and "sp600" in by_tier.index:
        gap = abs(by_tier.loc["sp600", "liquidity_premium_bp"]
                  - by_tier.loc["sp500", "liquidity_premium_bp"])
        assumption_range = (by_tier["liquidity_premium_high_bp"].mean()
                            - by_tier["liquidity_premium_low_bp"].mean())

        print("\n" + "-" * 72)
        print(f"  Gap between S&P 500 and S&P 600, base case:  {gap:.0f} basis points")
        print(f"  Range created by the assumption alone:       {assumption_range:.0f} basis points")
        if assumption_range > gap:
            print("\n  The assumption moves the answer more than the data does.")
            print("  You can show a difference exists; you cannot put a precise")
            print("  number on it with this evidence. Say so rather than hide it.")
        print("-" * 72)

    print("\nNext: python step5_report.py")


if __name__ == "__main__":
    main()
