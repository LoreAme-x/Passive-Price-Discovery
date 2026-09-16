"""
THE DASHBOARD (optional)
========================

Run it with:    streamlit run app.py

Four tabs, in the order you would explain the project to someone. You need to
have run steps 1 to 4 first, because this only reads what they produced.
"""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config

st.set_page_config(page_title="Passive investing and price discovery", layout="wide")

COLORS = {"sp500": "#1F2A44", "sp400": "#7B8794", "sp600": "#C0562D"}
LABELS = {"sp500": "S&P 500", "sp400": "S&P 400 MidCap", "sp600": "S&P 600 SmallCap"}


@st.cache_data
def load():
    return (pd.read_csv(config.STOCK_CSV),
            pd.read_csv(config.YEARLY_CSV),
            pd.read_csv(config.REGRESSION_CSV),
            pd.read_csv(config.COST_CSV))


try:
    by_stock, by_year, regressions, cost = load()
except FileNotFoundError:
    st.error("No results found. Run step1 to step4 first.")
    st.stop()

by_stock["label"] = by_stock["tier"].map(LABELS)
by_year["label"] = by_year["tier"].map(LABELS)

st.title("Passive investing and price discovery")
st.write(
    f"Index funds went from roughly 19% of US long-term fund assets in 2010 to over 50% "
    f"in 2024. They buy every stock in the index in proportion to size, without any view "
    f"on whether the company is any good. **Sample: {len(by_stock)} stocks from the S&P "
    f"500, 400 and 600, {len(by_year):,} stock-year observations, "
    f"{config.START_DATE[:4]}–{config.END_DATE[:4]}.**"
)

tab1, tab2, tab3, tab4 = st.tabs([
    "1. The picture",
    "2. Is it just size?",
    "3. Does it reach the cost of capital?",
    "How it works",
])


# ------------------------------------------------------------------- TAB 1
with tab1:
    measure = st.selectbox(
        "Measure",
        ["comovement_r2", "own_volatility", "reaction_delay", "beta"],
        format_func=lambda c: {
            "comovement_r2": "Comovement with the market (R²)",
            "own_volatility": "Company-specific volatility",
            "reaction_delay": "Reaction delay",
            "beta": "Beta",
        }[c])

    col1, col2 = st.columns([3, 2])

    with col1:
        yearly = by_year.groupby(["year", "label"])[measure].mean().reset_index()
        fig = px.line(yearly, x="year", y=measure, color="label",
                      color_discrete_map={LABELS[k]: v for k, v in COLORS.items()},
                      markers=True)
        fig.update_layout(height=420, legend_title_text="", xaxis_title="")
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "**Data:** `measures_by_year.csv` — one regression per stock per year.  \n"
            "**Why a line chart:** the question is about a trend, so the shape over time "
            "is the answer. A single average would hide it.")

    with col2:
        fig = px.histogram(by_stock, x=measure, color="label", nbins=40,
                           opacity=0.6, barmode="overlay",
                           color_discrete_map={LABELS[k]: v for k, v in COLORS.items()})
        fig.update_layout(height=420, legend_title_text="", yaxis_title="stocks")
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "**Data:** `measures_by_stock.csv`.  \n"
            "**Why a histogram:** with hundreds of stocks the spread inside each group "
            "matters. Heavily overlapping distributions make a difference in averages a "
            "weaker statement than it looks.")

    summary = by_stock.groupby("label").agg(
        firms=("ticker", "count"),
        beta=("beta", "mean"),
        comovement=("comovement_r2", "mean"),
        own_volatility=("own_volatility", "mean"),
        reaction_delay=("reaction_delay", "mean"),
        trading_cost=("trading_range_pct", "mean")).round(3)
    st.dataframe(summary, use_container_width=True)


# ------------------------------------------------------------------- TAB 2
with tab2:
    st.subheader("The obvious objection, and the answer")
    st.write(
        "S&P 500 companies are bigger, and bigger companies differ in analyst coverage, "
        "liquidity and ownership — all of which could produce the same pattern with no help "
        "from index funds. Here is the problem, drawn:")

    fig = px.scatter(by_stock, x=np.log10(by_stock["dollar_volume"]), y="comovement_r2",
                     color="label", opacity=0.65,
                     color_discrete_map={LABELS[k]: v for k, v in COLORS.items()},
                     hover_data=["ticker"],
                     labels={"x": "log10 average daily dollar volume",
                             "comovement_r2": "Comovement (R²)"})
    fig.update_layout(height=470, legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "**Data:** `measures_by_stock.csv`.  \n"
        "**Why a scatter:** the tiers sit at different points on one continuous size "
        "gradient. Showing that honestly is better than hoping nobody asks.")

    st.markdown("""
So instead of comparing averages, the project runs a regression:

```
comovement = a + b × (in the S&P 500) + c × log(size) + year effects
```

and reports `b` — what survives once size is accounted for. Standard errors are
**clustered by firm**, because the same company appears once per year and its errors are
correlated across years. Ordinary standard errors would be far too small.

The last row is the **matched sample**: the smallest S&P 500 companies against the largest
S&P 400 companies. Similar in size, opposite sides of the index boundary.
""")

    dependent = st.selectbox("Dependent variable",
                             sorted(regressions["dependent_variable"].unique()))
    table = regressions[regressions["dependent_variable"] == dependent]
    st.dataframe(table[["sample", "size_control", "year_effects", "sp500_coefficient",
                        "standard_error", "t_statistic", "significance",
                        "observations", "firms"]],
                 use_container_width=True, hide_index=True)
    st.caption("`*** |t| > 2.58,  ** |t| > 1.96,  * |t| > 1.65`")

    raw = table[table["size_control"] == "no"]
    controlled = table[(table["sample"] == "all stocks") & (table["year_effects"] == "yes")]
    if not raw.empty and not controlled.empty:
        raw_value = raw["sp500_coefficient"].iloc[0]
        controlled_value = controlled["sp500_coefficient"].iloc[0]
        shrink = 1 - abs(controlled_value) / abs(raw_value) if raw_value else 0
        st.info(
            f"Raw gap **{raw_value:+.3f}** → after size and year effects "
            f"**{controlled_value:+.3f}** (t = {controlled['t_statistic'].iloc[0]:.1f}). "
            f"Controlling for size removes about **{shrink:.0%}** of the raw difference. "
            f"What is left is the number worth talking about — and it is still not a causal "
            f"estimate, because index membership is not randomly assigned.", icon="📊")


# ------------------------------------------------------------------- TAB 3
with tab3:
    st.subheader("Cost of equity")
    st.write(
        "Two pieces: the textbook CAPM part, and a liquidity premium that depends on an "
        "assumption you choose. Move the sliders and watch how much of the answer is the "
        "assumption rather than the data.")

    col1, col2, col3 = st.columns(3)
    k = col1.slider("Liquidity premium (bp per 1% trading cost)",
                    10.0, 250.0, float(config.ILLIQUIDITY_PREMIUM_BP), 5.0)
    risk_free = col2.slider("Risk-free rate", 0.01, 0.07,
                            float(config.RISK_FREE_RATE), 0.002)
    premium = col3.slider("Market risk premium", 0.03, 0.08,
                          float(config.MARKET_RISK_PREMIUM), 0.005)

    live = cost[["ticker", "tier", "beta", "trading_cost_pct"]].copy()
    live["capm_pct"] = (risk_free + live["beta"] * premium) * 100
    live["liquidity_pct"] = live["trading_cost_pct"] * k / 100
    live["total_pct"] = live["capm_pct"] + live["liquidity_pct"]

    grouped = live.groupby("tier")[["capm_pct", "liquidity_pct", "total_pct"]].mean()
    grouped = grouped.reindex([t for t in ["sp500", "sp400", "sp600"] if t in grouped.index])

    fig = go.Figure()
    fig.add_bar(x=[LABELS[t] for t in grouped.index], y=grouped["capm_pct"],
                name="CAPM part", marker_color="#1F2A44")
    fig.add_bar(x=[LABELS[t] for t in grouped.index], y=grouped["liquidity_pct"],
                name="Liquidity part (assumption)", marker_color="#C9A227")
    fig.update_layout(barmode="stack", height=430,
                      yaxis_title="Average cost of equity (%)", legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "**Data:** `cost_of_equity.csv`, recombined live with the sliders.  \n"
        "**Why stacked bars:** the question is not the total, it is how much of the total "
        "comes from each piece — and how much of it you chose rather than measured.")

    st.dataframe(grouped.round(2), use_container_width=True)

    if "sp500" in grouped.index and "sp600" in grouped.index:
        gap = (grouped.loc["sp600", "liquidity_pct"]
               - grouped.loc["sp500", "liquidity_pct"]) * 100
        costs = live.groupby("tier")["trading_cost_pct"].mean()
        low_gap = (costs["sp600"] - costs["sp500"]) * 10
        high_gap = (costs["sp600"] - costs["sp500"]) * 250
        st.warning(
            f"At the current setting the S&P 600 carries **{gap:.0f} basis points** more "
            f"liquidity premium than the S&P 500. Moving the slider across its full range "
            f"moves that same gap from **{low_gap:.0f} to {high_gap:.0f} basis points**. "
            f"The assumption moves the answer more than the data does — which is why nobody "
            f"can honestly quote a precise figure for how much index investing raised the "
            f"cost of capital.", icon="📌")


# ------------------------------------------------------------------- TAB 4
with tab4:
    st.subheader("How the project works")
    st.code(
        "step1_download.py        real S&P 500/400/600 constituent lists -> prices -> SQLite\n"
        "step2_measure.py         one regression per stock per year -> four measures\n"
        "step3_regression.py      panel regression with size controls, year effects,\n"
        "                         firm-clustered standard errors, matched sample\n"
        "step4_cost_of_capital.py CAPM + liquidity premium, three scenarios\n"
        "step5_report.py          charts + output/report.md",
        language="text")

    st.markdown("""
**The core regression**

```
stock return  =  a  +  b × market return  +  error
```

`b` is the beta, the fit is the comovement, the size of the error is the company-specific
volatility, and re-running it with *yesterday's* market returns gives the reaction delay.

**Three things worth being able to explain**

- **Why clustered standard errors.** Each company appears once per year, so its errors are
  correlated across years. Ordinary standard errors assume independence, come out far too
  small, and make everything look significant.
- **Why a matched sample.** The smallest S&P 500 names against the largest S&P 400 names:
  similar size, opposite sides of the line that decides how much index money must own them.
- **Why the logarithm is taken in Python, not SQL.** In SQLite `LOG()` is base-10 and
  `LN()` is natural, and neither is guaranteed to exist. Getting it wrong raises no error —
  it silently multiplies every return by 0.43.

**What this does not show**

It is not a causal estimate. Index membership is not randomly assigned, the constituent
lists are today's applied backwards (survivorship), and size is proxied by dollar volume
rather than market capitalisation.
""")
