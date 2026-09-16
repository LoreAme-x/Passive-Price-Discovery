# Passive investing and price discovery

Index funds and ETFs went from roughly 19% of US long-term fund assets in 2010 to over 50%
in 2024 (ICI / Morningstar). An index fund buys every stock in its index in proportion to
size, without forming any view about whether a particular company is any good.

This project measures what that does to prices, and whether it reaches the cost of capital.

**Sample:** 443 US stocks taken from the actual constituent lists of the **S&P 500**,
**S&P 400 MidCap** and **S&P 600 SmallCap** — three indices that differ sharply in how much
passive money mechanically has to own them. 2012–2025, roughly 5,000 stock-year
observations.

## What I found

The raw gap in market comovement between S&P 500 stocks and small caps is about
6 R² points. **Once size and year effects are controlled for, 81% of that gap disappears**,
and what remains (+0.012, t = 0.9) is not statistically distinguishable from zero.

In a matched sample — the smallest S&P 500 companies against the largest S&P 400
companies, similar in size but on opposite sides of the index boundary — the
coefficient is larger (+0.034) and marginally significant (t = 1.8), but not
enough to build a claim on.

The honest conclusion: most of what looks like an index-membership effect is
size. Whether anything survives beyond that, this sample cannot tell.

---

## The measures

Everything comes from one regression, run for each stock and each year:

```
stock return  =  a  +  b × market return  +  error
```

| Measure | What it is | How to read it |
|---|---|---|
| **Beta** | the `b` | how much the stock moves when the market moves |
| **Comovement (R²)** | fit of the regression | close to 1: the stock is basically the index. Close to 0: it moves on its own news |
| **Own volatility** | size of the `error`, annualised | the company-specific movement left over |
| **Reaction delay** | extra fit from adding *yesterday's* market returns | 0 = reacts immediately; higher = reacts late |
| **Trading range** | average daily (high − low) / close | rough proxy for what it costs to trade |

---

## The part that matters: is it just size?

S&P 500 companies are bigger, and bigger companies differ in coverage, liquidity and
ownership — all of which could produce the same pattern without index funds doing anything.
The project answers that objection rather than footnoting it.

1. **A regression with controls**, not a comparison of group averages:

   ```
   comovement = a + b × (in the S&P 500) + c × log(size) + year effects
   ```

   and it reports what is left of `b` once size is in.

2. **Year fixed effects**, so a shock that hit the whole market in one year cannot
   masquerade as a group difference.

3. **Standard errors clustered by firm.** The same company appears once per year, so its
   errors are correlated across years. Ordinary standard errors assume independence, come
   out far too small, and make everything look significant. The cluster-robust sandwich
   estimator is implemented directly in `step3_regression.py`.

4. **A matched sample**: the 60 smallest companies in the S&P 500 against the 60 largest in
   the S&P 400. Similar size, opposite sides of the line that determines how much index
   money must own them.

---

## And then the cost of capital

```
cost of equity  =  risk-free rate + beta × market premium      (CAPM)
                 + k × trading cost                            (liquidity premium)
```

`k` is an **assumption** set in `config.py`, not something estimated from price data, so the
project reports a low, base and high case. The recurring finding is that **the range created
by the assumption is wider than the difference between the index tiers** — which is exactly
why nobody can honestly quote a precise figure for how much index investing has raised the
cost of capital. The report says so rather than hiding it.

---

## Running it

```bash
pip install -r requirements.txt

python step1_download.py          # constituent lists + prices → SQLite   (slow: a few minutes)
python step2_measure.py           # one regression per stock per year
python step3_regression.py        # panel regression, controls, clustered SEs
python step4_cost_of_capital.py   # CAPM + liquidity premium
python step5_report.py            # charts + output/report.md

streamlit run app.py              # optional: interactive dashboard
python make_guide.py              # optional: PDF study guide → private/
```

Run them in order — each prints what to run next. To change the universe, the period or the
assumptions, edit `config.py` and re-run from step 1.

**Step 1 is resumable.** Yahoo Finance rate-limits bulk requests: ask for 450 symbols and it
will serve a couple of hundred before refusing everything. Each ticker that downloads is
cached to `data/cache/`, so re-running the script skips what it already has and fetches only
what is missing. Two or three runs a few minutes apart gets the whole sample, and nothing is
lost when Yahoo cuts you off. Tickers that never arrive are dropped rather than filled with
invented numbers.

---

## Files

```
├── config.py                  all settings — the only file you normally edit
├── step1_download.py          index constituents + prices
├── step2_measure.py           the four price-discovery measures
├── step3_regression.py        panel regression with clustered standard errors
├── step4_cost_of_capital.py   CAPM + liquidity premium, three scenarios
├── step5_report.py            charts and the written report
├── app.py                     optional Streamlit dashboard
├── make_guide.py              optional PDF study guide (written to private/)
├── data/                      universe + SQLite database (not committed, ~30 MB)
├── private/                   personal notes — never committed
└── output/                    figures, CSV results, report.md (committed, ~0.5 MB)
```

The dashboard reads only the CSV files in `output/`, not the database, so it runs
anywhere those files go — including a free Streamlit Community Cloud deployment.

Prices live in SQLite; daily returns come out of a `LAG()` window function partitioned by
ticker, so a return can never be computed across a ticker boundary.

---

## What this does not show

- **It is not a causal estimate.** Controls narrow the gap between explanations; they do not
  close it. Index membership is not randomly assigned, and the matched sample is a partial
  fix, not an experiment.
- **Size is proxied by average dollar volume**, not market capitalisation.
- **Comovement is blunt.** A high R² can mean the price carries little company-specific
  information, or simply that the company genuinely has market-like earnings.
- **Survivorship.** The constituent lists are today's, applied backwards.

## What would make it stronger

1. Actual index-ownership percentages per company instead of index membership as a proxy.
2. Point-in-time constituent lists, which removes the survivorship problem.
3. Market capitalisation as the size control.
4. A within-company design: track the same firm as its index membership changes.
