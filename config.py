"""
PROJECT SETTINGS
================

This is the only file you normally need to edit. Everything else reads from here.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# 1. THE UNIVERSE
# ---------------------------------------------------------------------------
# Instead of hand-picking a few stocks, the project downloads the actual
# constituents of three S&P indices. They differ in how much index money
# mechanically buys them:
#
#   S&P 500  - the index nearly every passive fund tracks. Very high index
#              ownership.
#   S&P 400  - MidCap. Tracked, but by far fewer and smaller funds.
#   S&P 600  - SmallCap. Tracked least of all.
#
# Using real constituent lists rather than a hand-picked sample matters: a
# sample you chose yourself is a sample you can accidentally choose to prove
# your point.

INDEX_TIERS = {
    "sp500": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
    "sp400": "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies",
    "sp600": "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies",
}

# How many stocks to take from each index. The full lists are 500 / 400 / 600,
# which is about 20 minutes of downloading. 150 each is a few minutes and is
# already a real sample. Raise it when you have time.
MAX_PER_TIER = 150

# The market benchmark. SPY is the S&P 500 ETF: both the natural proxy for
# "the market" and the largest passive vehicle in existence.
BENCHMARK = "SPY"

# ---------------------------------------------------------------------------
# 2. THE MATCHED "BOUNDARY" SAMPLE
# ---------------------------------------------------------------------------
# The obvious objection to comparing S&P 500 names with S&P 600 names is that
# they differ in size, not just in index ownership. So the project also builds
# a second, narrower sample: the SMALLEST companies in the S&P 500 against the
# LARGEST companies in the S&P 400.
#
# Those two sets are similar in size but sit on opposite sides of a line that
# determines how much passive money has to own them. If the difference survives
# in that sample, size alone is a weaker explanation for it.
BOUNDARY_SAMPLE_SIZE = 60   # how many stocks from each side

# ---------------------------------------------------------------------------
# 3. THE PERIOD
# ---------------------------------------------------------------------------
# A long window is needed to see a trend. Index funds went from about 19% of
# US long-term fund assets in 2010 to over 50% in 2024 (ICI / Morningstar).
START_DATE = "2012-01-01"
END_DATE = "2025-01-01"

# ---------------------------------------------------------------------------
# 4. COST OF CAPITAL ASSUMPTIONS
# ---------------------------------------------------------------------------
# These are NOT estimated from the data. They are assumptions you choose.
# They live here, together, so every number the project reports in basis points
# can be traced back to a line in this file.

RISK_FREE_RATE = 0.042          # 4.2% a year (roughly the 10-year US Treasury)
MARKET_RISK_PREMIUM = 0.050     # 5.0% a year, the standard textbook value

# Illiquidity premium: basis points of extra required return per 1 percentage
# point of trading cost. The idea comes from Amihud & Mendelson (1986):
# investors want to be paid for holding something expensive to trade.
# This is a CALIBRATION, not an estimate. Change it and watch the answer move.
ILLIQUIDITY_PREMIUM_BP = 80.0
ILLIQUIDITY_PREMIUM_LOW = 20.0
ILLIQUIDITY_PREMIUM_HIGH = 200.0

# ---------------------------------------------------------------------------
# 5. TECHNICAL SETTINGS
# ---------------------------------------------------------------------------
TRADING_DAYS_PER_YEAR = 252
MARKET_LAGS = 3            # days of delay tested in the reaction-speed measure
MIN_DAYS_PER_YEAR = 150    # skip a stock-year with fewer trading days than this
DOWNLOAD_BATCH = 40        # tickers per Yahoo Finance request

# ---------------------------------------------------------------------------
# 6. FILE LOCATIONS
# ---------------------------------------------------------------------------
FOLDER = Path(__file__).resolve().parent
DATA_DIR = FOLDER / "data"
OUTPUT_DIR = FOLDER / "output"
FIGURES_DIR = OUTPUT_DIR / "figures"

DB_FILE = DATA_DIR / "market.db"
UNIVERSE_CSV = DATA_DIR / "universe.csv"
YEARLY_CSV = OUTPUT_DIR / "measures_by_year.csv"
STOCK_CSV = OUTPUT_DIR / "measures_by_stock.csv"
REGRESSION_CSV = OUTPUT_DIR / "regression_results.csv"
COST_CSV = OUTPUT_DIR / "cost_of_equity.csv"
REPORT_FILE = OUTPUT_DIR / "report.md"
PRIVATE_DIR = FOLDER / "private"      # never committed - see .gitignore
GUIDE_FILE = PRIVATE_DIR / "study_guide.pdf"

DATA_DIR.mkdir(exist_ok=True)
PRIVATE_DIR.mkdir(exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)
