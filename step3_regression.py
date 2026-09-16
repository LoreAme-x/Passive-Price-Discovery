"""
STEP 3 — THE REGRESSION
=======================

Run it with:    python step3_regression.py

Step 2 produced averages by index tier. The obvious objection to those averages
is: S&P 500 companies are bigger, and bigger companies are different for a dozen
reasons that have nothing to do with index funds. This step is the answer to
that objection, and it does three things.

1. CONTROLS. Instead of comparing group averages, it runs a regression with
   size on the right-hand side:

       comovement = a + b * (in the S&P 500) + c * log(size) + year effects

   The coefficient b is the difference that is left after size is accounted for.
   If b collapses once size is added, the story was always about size.

2. YEAR FIXED EFFECTS. A dummy for every year, which absorbs anything that
   happened to the whole market in a given year (2020, say). Without them a
   common shock could masquerade as a group difference.

3. STANDARD ERRORS CLUSTERED BY FIRM. The same company appears once per year, so
   its observations are not independent: an error in 2015 is related to the same
   company's error in 2016. Ordinary standard errors ignore that and come out
   far too small, which makes everything look significant. Clustering by firm
   fixes it. This is the single most common mistake in panel work of this kind.

Then it repeats the main regression on the MATCHED sample: the smallest
companies in the S&P 500 against the largest in the S&P 400. Those two sets are
similar in size but sit on opposite sides of the line that decides how much
index money has to own them. If the result survives there, size alone is a
weaker explanation.

Output: output/regression_results.csv
"""

import numpy as np
import pandas as pd

import config


# ---------------------------------------------------------------------------
# OLS with standard errors clustered by firm
# ---------------------------------------------------------------------------
def ols_clustered(y, X, cluster_ids):
    """
    Ordinary least squares, with a covariance matrix that allows the errors of
    the same firm to be correlated across years.

    y            the dependent variable, length N
    X            the regressors INCLUDING a column of ones, N x K
    cluster_ids  one label per observation saying which firm it belongs to

    Returns (coefficients, standard_errors, r_squared, n_obs, n_clusters).
    """
    n, k = X.shape

    XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    residuals = y - X @ beta

    # The "meat" of the sandwich: sum over firms of (X_g' u_g)(X_g' u_g)'
    meat = np.zeros((k, k))
    unique_clusters = pd.unique(cluster_ids)
    for firm in unique_clusters:
        rows = cluster_ids == firm
        Xg = X[rows]
        ug = residuals[rows]
        score = Xg.T @ ug
        meat += np.outer(score, score)

    n_clusters = len(unique_clusters)
    correction = (n_clusters / (n_clusters - 1)) * ((n - 1) / (n - k))
    covariance = XtX_inv @ meat @ XtX_inv * correction
    standard_errors = np.sqrt(np.diag(covariance))

    total_variation = ((y - y.mean()) ** 2).sum()
    r_squared = 1 - (residuals ** 2).sum() / total_variation

    return beta, standard_errors, r_squared, n, n_clusters


def stars(t_statistic):
    """The usual significance markers."""
    t = abs(t_statistic)
    if t > 2.58:
        return "***"
    if t > 1.96:
        return "**"
    if t > 1.65:
        return "*"
    return ""


# ---------------------------------------------------------------------------
# Building the regressors
# ---------------------------------------------------------------------------
def build_design_matrix(panel, use_size_control, use_year_effects):
    """
    Assembles the X matrix. Always includes an intercept and the S&P 500 dummy;
    the controls are switched on and off so we can show what each one does.
    """
    columns = [np.ones(len(panel))]           # intercept
    names = ["intercept"]

    columns.append(panel["in_sp500"].to_numpy(float))
    names.append("in_sp500")

    if use_size_control:
        columns.append(np.log(panel["dollar_volume"].to_numpy(float)))
        names.append("log_size")

    if use_year_effects:
        # One dummy per year, dropping the first to avoid perfect collinearity
        years = sorted(panel["year"].unique())[1:]
        for year in years:
            columns.append((panel["year"] == year).to_numpy(float))
            names.append(f"year_{year}")

    return np.column_stack(columns), names


def run_specification(panel, dependent, label,
                      use_size_control, use_year_effects):
    """Runs one regression and returns a one-row summary."""
    data = panel.dropna(subset=[dependent, "dollar_volume"])
    if len(data) < 50:
        return None

    y = data[dependent].to_numpy(float)
    X, names = build_design_matrix(data, use_size_control, use_year_effects)

    beta, se, r_squared, n, n_clusters = ols_clustered(
        y, X, data["ticker"].to_numpy())

    position = names.index("in_sp500")
    coefficient = beta[position]
    standard_error = se[position]
    t_statistic = coefficient / standard_error if standard_error > 0 else np.nan

    return {
        "dependent_variable": dependent,
        "sample": label,
        "size_control": "yes" if use_size_control else "no",
        "year_effects": "yes" if use_year_effects else "no",
        "sp500_coefficient": round(float(coefficient), 4),
        "standard_error": round(float(standard_error), 4),
        "t_statistic": round(float(t_statistic), 2),
        "significance": stars(t_statistic),
        "r_squared": round(float(r_squared), 3),
        "observations": int(n),
        "firms": int(n_clusters),
    }


# ---------------------------------------------------------------------------
# The matched "boundary" sample
# ---------------------------------------------------------------------------
def build_matched_sample(by_stock, panel):
    """
    The smallest S&P 500 companies against the largest S&P 400 companies.

    Both sides are picked on average dollar volume, which is the size proxy used
    throughout. The point is to compare companies of similar size that sit on
    opposite sides of the index boundary.
    """
    n = config.BOUNDARY_SAMPLE_SIZE

    smallest_large = (by_stock[by_stock["tier"] == "sp500"]
                      .nsmallest(n, "dollar_volume")["ticker"])
    largest_mid = (by_stock[by_stock["tier"] == "sp400"]
                   .nlargest(n, "dollar_volume")["ticker"])

    chosen = set(smallest_large) | set(largest_mid)
    return panel[panel["ticker"].isin(chosen)].copy()


def balance_table(by_stock, matched_tickers):
    """
    Shows how similar the two sides of the matched sample actually are.
    If the size gap is still large, say so rather than pretending otherwise.
    """
    subset = by_stock[by_stock["ticker"].isin(matched_tickers)]
    table = subset.groupby("tier").agg(
        firms=("ticker", "count"),
        median_dollar_volume=("dollar_volume", "median"),
        mean_beta=("beta", "mean"),
        mean_comovement=("comovement_r2", "mean"),
    ).round(3)
    return table


# ---------------------------------------------------------------------------
def main():
    print("STEP 3 — regressions\n")

    panel = pd.read_csv(config.YEARLY_CSV)
    by_stock = pd.read_csv(config.STOCK_CSV)

    panel["in_sp500"] = (panel["tier"] == "sp500").astype(int)

    results = []

    # --- full sample, three specifications, three dependent variables ---
    for dependent in ["comovement_r2", "own_volatility", "reaction_delay"]:
        for label, size_control, year_effects in [
            ("all stocks", False, False),
            ("all stocks", True, False),
            ("all stocks", True, True),
        ]:
            row = run_specification(panel, dependent, label, size_control, year_effects)
            if row:
                results.append(row)

    # --- matched sample ---
    matched = build_matched_sample(by_stock, panel)
    matched_tickers = set(matched["ticker"])

    for dependent in ["comovement_r2", "own_volatility", "reaction_delay"]:
        row = run_specification(matched, dependent, "matched (S&P 500 small vs S&P 400 large)",
                                use_size_control=True, use_year_effects=True)
        if row:
            results.append(row)

    table = pd.DataFrame(results)
    table.to_csv(config.REGRESSION_CSV, index=False)

    # --- printing ---
    print("Size balance in the matched sample:")
    print(balance_table(by_stock, matched_tickers).to_string())

    print("\nRegression results — the coefficient on 'in the S&P 500':\n")
    show = table[["dependent_variable", "sample", "size_control", "year_effects",
                  "sp500_coefficient", "standard_error", "t_statistic",
                  "significance", "observations", "firms"]]
    print(show.to_string(index=False))

    print("\n  Standard errors are clustered by firm.")
    print("  *** |t| > 2.58   ** |t| > 1.96   * |t| > 1.65\n")

    # --- the one sentence that matters ---
    raw = table[(table["dependent_variable"] == "comovement_r2")
                & (table["size_control"] == "no")]
    controlled = table[(table["dependent_variable"] == "comovement_r2")
                       & (table["sample"] == "all stocks")
                       & (table["year_effects"] == "yes")]
    matched_row = table[(table["dependent_variable"] == "comovement_r2")
                        & (table["sample"].str.startswith("matched"))]

    if not raw.empty and not controlled.empty:
        raw_value = raw["sp500_coefficient"].iloc[0]
        controlled_value = controlled["sp500_coefficient"].iloc[0]
        print("-" * 72)
        print(f"  Comovement gap, no controls:        {raw_value:+.3f}")
        print(f"  After size and year effects:        {controlled_value:+.3f}"
              f"  (t = {controlled['t_statistic'].iloc[0]:.1f})")
        if not matched_row.empty:
            print(f"  In the matched sample:              "
                  f"{matched_row['sp500_coefficient'].iloc[0]:+.3f}"
                  f"  (t = {matched_row['t_statistic'].iloc[0]:.1f})")
        shrinkage = 1 - abs(controlled_value) / abs(raw_value) if raw_value else np.nan
        print(f"\n  Controlling for size removes about {shrinkage:.0%} of the raw gap.")
        print("-" * 72)

    print("\nNext: python step4_cost_of_capital.py")


if __name__ == "__main__":
    main()
