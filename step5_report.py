"""
STEP 5 — CHARTS AND THE WRITTEN REPORT
======================================

Run it with:    python step5_report.py

Produces the charts in output/figures/ and writes output/report.md, which is
the document someone should be able to read without running anything.
"""

import matplotlib
matplotlib.use("Agg")          # draw to files, not to a window
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config

COLORS = {"sp500": "#1F2A44", "sp400": "#7B8794", "sp600": "#C0562D"}
LABELS = {"sp500": "S&P 500 (most indexed)",
          "sp400": "S&P 400 MidCap",
          "sp600": "S&P 600 SmallCap (least indexed)"}
ORDER = ["sp500", "sp400", "sp600"]


def save(fig, filename):
    fig.tight_layout()
    fig.savefig(config.FIGURES_DIR / filename, dpi=150)
    plt.close(fig)
    print(f"  chart: {filename}")


def chart_over_time(by_year, column, title, ylabel, filename):
    """One line per index tier, averaged across stocks, year by year."""
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for tier in ORDER:
        data = by_year[by_year["tier"] == tier]
        if data.empty:
            continue
        yearly = data.groupby("year")[column].mean()
        ax.plot(yearly.index, yearly.values, marker="o", linewidth=2,
                color=COLORS[tier], label=LABELS[tier])
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=9)
    save(fig, filename)


def chart_distribution(by_stock, column, title, xlabel, filename):
    """
    Distributions rather than bars. With hundreds of stocks a bar per stock is
    unreadable, and the spread within a group is part of the answer: if the two
    distributions overlap heavily, the average difference means less.
    """
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for tier in ORDER:
        values = by_stock.loc[by_stock["tier"] == tier, column].dropna()
        if values.empty:
            continue
        ax.hist(values, bins=30, alpha=0.55, color=COLORS[tier],
                label=f"{LABELS[tier]} (n={len(values)})", density=True)
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Density")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8)
    save(fig, filename)


def chart_size_vs_comovement(by_stock, filename):
    """
    The picture that shows the identification problem honestly: comovement
    plotted against size. If the tiers separate only because they sit at
    different points on the same size gradient, you can see it here.
    """
    fig, ax = plt.subplots(figsize=(8, 5))
    for tier in ORDER:
        data = by_stock[by_stock["tier"] == tier]
        if data.empty:
            continue
        ax.scatter(np.log10(data["dollar_volume"]), data["comovement_r2"],
                   s=14, alpha=0.6, color=COLORS[tier], label=LABELS[tier])
    ax.set_title("Comovement against size — the identification problem, drawn",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("log10 average daily dollar volume")
    ax.set_ylabel("Comovement with the market (R-squared)")
    ax.grid(alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8)
    save(fig, filename)


def chart_cost_of_equity(cost, filename):
    """Average cost of equity by tier, split into its two pieces."""
    tiers = [t for t in ORDER if t in set(cost["tier"])]
    grouped = cost.groupby("tier")

    capm = [grouped.get_group(t)["capm_pct"].mean() for t in tiers]
    base = [grouped.get_group(t)["liquidity_premium_bp"].mean() / 100 for t in tiers]
    low = [grouped.get_group(t)["liquidity_premium_low_bp"].mean() / 100 for t in tiers]
    high = [grouped.get_group(t)["liquidity_premium_high_bp"].mean() / 100 for t in tiers]

    labels = [LABELS[t] for t in tiers]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.bar(labels, capm, color="#1F2A44", label="CAPM part (risk-free + beta x premium)")
    ax.bar(labels, base, bottom=capm, color="#C9A227",
           label="Liquidity part (assumption-driven)")

    middle = np.array(capm) + np.array(base)
    lower = np.array(capm) + np.array(low)
    upper = np.array(capm) + np.array(high)
    ax.errorbar(labels, middle, yerr=[middle - lower, upper - middle],
                fmt="none", ecolor="#333", capsize=5, linewidth=1.3,
                label="range if you change the assumption")

    ax.set_title("Cost of equity, and how much of it is an assumption",
                 fontsize=13, fontweight="bold")
    ax.set_ylabel("Cost of equity (%)")
    ax.grid(axis="y", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8)
    save(fig, filename)


def write_report(by_stock, by_year, regressions, cost):
    tier_summary = by_stock.groupby("tier").agg(
        firms=("ticker", "count"),
        beta=("beta", "mean"),
        comovement=("comovement_r2", "mean"),
        own_volatility=("own_volatility", "mean"),
        reaction_delay=("reaction_delay", "mean"),
        trading_cost_pct=("trading_range_pct", "mean"),
    ).round(3).reindex([t for t in ORDER if t in by_stock["tier"].unique()])

    first_years = by_year[by_year["year"] <= by_year["year"].min() + 2]
    last_years = by_year[by_year["year"] >= by_year["year"].max() - 2]
    trend = pd.DataFrame({
        "first 3 years": first_years.groupby("tier")["comovement_r2"].mean(),
        "last 3 years": last_years.groupby("tier")["comovement_r2"].mean(),
    }).round(3)
    trend["change"] = (trend["last 3 years"] - trend["first 3 years"]).round(3)

    cost_summary = cost.groupby("tier")[
        ["capm_pct", "trading_cost_pct", "liquidity_premium_low_bp",
         "liquidity_premium_bp", "liquidity_premium_high_bp",
         "total_cost_of_equity_pct"]].mean().round(2).reindex(trend.index)

    main_regressions = regressions[
        regressions["dependent_variable"] == "comovement_r2"]

    text = f"""# Passive investing and price discovery

Index funds and ETFs went from roughly 19% of US long-term fund assets in 2010 to over
50% in 2024 (ICI / Morningstar). An index fund buys every stock in its index in proportion
to size, without forming any view about whether a particular company is any good.

This project asks what that does to prices, and whether it reaches the cost of capital.

**Sample:** {len(by_stock)} US stocks drawn from the actual constituent lists of the S&P 500,
S&P 400 MidCap and S&P 600 SmallCap — three indices that differ in how much passive money
mechanically has to own them. Period {config.START_DATE} to {config.END_DATE}, benchmark
{config.BENCHMARK}. That is {len(by_year):,} stock-year observations.

---

## How price discovery is measured

Everything comes from one regression, run for each stock and each year:

```
stock return  =  a  +  b × market return  +  error
```

| Measure | What it is | How to read it |
|---|---|---|
| **Beta** | the `b` | how much the stock moves when the market moves |
| **Comovement (R²)** | fit of the regression | close to 1: the stock is basically the index. Close to 0: it moves on its own news |
| **Own volatility** | size of the `error`, annualised | the company-specific movement left over |
| **Reaction delay** | extra fit from adding *yesterday's* market returns | 0 means it reacts immediately; higher means it reacts late |
| **Trading range** | average daily (high − low) / close | rough proxy for what it costs to trade |

---

## 1. The raw picture

{tier_summary.to_markdown()}

![Comovement over time](figures/1_comovement_over_time.png)

![Own volatility over time](figures/2_own_volatility_over_time.png)

Average comovement, first three years versus last three years:

{trend.to_markdown()}

![Distribution of comovement](figures/3_comovement_distribution.png)

The histograms matter as much as the averages. If the distributions overlap heavily, a
difference in means is a weaker statement than it looks.

---

## 2. But is it just size?

This is the obvious objection, and it deserves a real answer rather than a footnote.
S&P 500 companies are larger, and larger companies differ in analyst coverage, liquidity
and institutional ownership — all of which could produce the same pattern with no help from
index funds.

![Comovement against size](figures/4_size_vs_comovement.png)

The chart shows the problem directly: the tiers sit at different points on one continuous
size gradient.

So instead of comparing averages, the project runs a regression:

```
comovement = a + b × (in the S&P 500) + c × log(size) + year effects
```

and reports the coefficient `b` — the difference that survives once size is accounted for.
Standard errors are **clustered by firm**, because the same company appears once per year
and its errors are correlated across years. Ordinary standard errors would be far too small
here and would make almost everything look significant.

The last row uses a **matched sample**: the {config.BOUNDARY_SAMPLE_SIZE} smallest companies
in the S&P 500 against the {config.BOUNDARY_SAMPLE_SIZE} largest in the S&P 400. Similar in
size, opposite sides of the line that determines how much index money has to own them.

{main_regressions[["sample", "size_control", "year_effects", "sp500_coefficient",
                   "standard_error", "t_statistic", "significance", "observations",
                   "firms"]].to_markdown(index=False)}

`*** |t| > 2.58, ** |t| > 1.96, * |t| > 1.65`

Full results for all three dependent variables are in `output/regression_results.csv`.

---

## 3. Does it reach the cost of capital?

The cost of equity is built in two pieces:

```
cost of equity  =  risk-free rate + beta × market premium      (CAPM)
                 + k × trading cost                            (liquidity premium)
```

Assumptions, all set in `config.py`:

- risk-free rate **{config.RISK_FREE_RATE:.1%}**
- market risk premium **{config.MARKET_RISK_PREMIUM:.1%}**
- liquidity coefficient k **{config.ILLIQUIDITY_PREMIUM_BP:.0f} bp** per 1% of trading cost
  (low {config.ILLIQUIDITY_PREMIUM_LOW:.0f}, high {config.ILLIQUIDITY_PREMIUM_HIGH:.0f})

![Cost of equity](figures/5_cost_of_equity.png)

{cost_summary.to_markdown()}

### The honest conclusion

The black bars show what happens to the liquidity component when the assumption `k` moves
from its low case to its high case. That range is wider than the gap between the index
tiers. In other words, **the uncertainty in the assumption is larger than the difference in
the data**.

That is the reason nobody can honestly quote a precise figure for how much index investing
has raised the cost of capital. What this project can show is that a difference exists, how
much of it survives controls, and roughly how big the cost-of-capital consequence might be
under stated assumptions.

---

## What this does not show

- **It is not a causal estimate.** Controlling for size and year effects narrows the gap
  between explanations; it does not close it. Index membership is not randomly assigned, and
  the matched sample is a partial fix, not an experiment.
- **Size is proxied by average dollar volume**, not market capitalisation, because market
  cap requires a per-company data request. The proxy is highly correlated with size but is
  not the same thing.
- **Comovement is a blunt measure.** A high R² can mean the price carries little
  company-specific information, or simply that the company genuinely has market-like
  earnings. A regulated utility and a biotech should not have the same R² for reasons that
  have nothing to do with index funds.
- **The trading range is a proxy for the bid-ask spread**, not the spread itself. Real
  spreads need intraday data.
- **Survivorship.** The constituent lists are today's, applied backwards, so companies that
  dropped out of an index are missing.

## What would make it stronger

1. Actual index-ownership percentages per company, instead of index membership as a proxy.
2. Point-in-time constituent lists, which removes the survivorship problem.
3. Market capitalisation as the size control instead of dollar volume.
4. A within-company design: track the same firm as its index membership changes, which
   removes everything that is fixed about the company.
"""
    config.REPORT_FILE.write_text(text)
    print(f"\n  report: {config.REPORT_FILE}")


def main():
    print("STEP 5 — charts and report\n")

    by_stock = pd.read_csv(config.STOCK_CSV)
    by_year = pd.read_csv(config.YEARLY_CSV)
    regressions = pd.read_csv(config.REGRESSION_CSV)
    cost = pd.read_csv(config.COST_CSV)

    chart_over_time(by_year, "comovement_r2",
                    "How much of a stock's movement is just the market?",
                    "Average R-squared vs the S&P 500", "1_comovement_over_time.png")
    chart_over_time(by_year, "own_volatility",
                    "How much company-specific movement is left?",
                    "Annualised own volatility", "2_own_volatility_over_time.png")
    chart_distribution(by_stock, "comovement_r2",
                       "Distribution of comovement across stocks",
                       "R-squared vs the market", "3_comovement_distribution.png")
    chart_size_vs_comovement(by_stock, "4_size_vs_comovement.png")
    chart_cost_of_equity(cost, "5_cost_of_equity.png")

    write_report(by_stock, by_year, regressions, cost)

    print("\nAll done. Open output/report.md")
    print("Optional: streamlit run app.py   |   python make_guide.py")


if __name__ == "__main__":
    main()
