"""
STEP 1 — BUILD THE UNIVERSE AND GET THE DATA
============================================

Run it with:    python step1_download.py

Two jobs: build the list of stocks, and download their prices.

The list comes from the actual constituents of the S&P 500, S&P 400 (MidCap)
and S&P 600 (SmallCap), read from Wikipedia. That matters more than it looks: a
sample you picked yourself is a sample you could have picked to prove your point.

THE IMPORTANT PART: THIS SCRIPT IS RESUMABLE.

Yahoo Finance rate-limits you. Ask for 450 symbols in a few minutes and it will
serve a couple of hundred and then start refusing everything, including symbols
that exist perfectly well. There is no way around it, only around the problem.

So every ticker that downloads successfully is saved to its own file in
data/cache/. When you run this script again it skips whatever is already there
and only asks for what is missing. Two or three runs, a few minutes apart, and
you have the whole sample. Nothing is lost when Yahoo cuts you off.

Three other details that matter:

  - The BENCHMARK is downloaded first, on its own, before the quota is spent.
    Everything downstream is measured against it.
  - Batches are small and requests are spaced out, which gets you further before
    the throttling starts.
  - Tickers that never arrive are simply DROPPED from the sample rather than
    filled with made-up numbers. A slightly smaller real sample beats a full
    fake one.
"""

import io
import logging
import sqlite3
import time

import pandas as pd

import config

# yfinance prints a paragraph about every failed ticker. We track failures
# ourselves and report them once at the end.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

CACHE_DIR = config.DATA_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)

BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/122.0 Safari/537.36")
}

# Gentle settings. Slower, but you get much further before Yahoo cuts you off.
BATCH_SIZE = 12
PAUSE_BETWEEN_BATCHES = 3       # seconds
PAUSE_BEFORE_RETRY = 60         # seconds
RETRY_ROUNDS = 2
MIN_USABLE_STOCKS = 120         # below this, the analysis is not worth running

FALLBACK_TICKERS = {
    "sp500": ["AAPL", "MSFT", "JNJ", "PG", "KO", "XOM", "JPM", "V", "WMT", "HD",
              "MRK", "PEP", "CVX", "ABT", "MCD", "CSCO", "VZ", "INTC", "T", "IBM",
              "CAT", "GE", "MMM", "HON", "UPS", "LOW", "NKE", "ORCL", "TXN", "QCOM"],
    "sp400": ["ETSY", "DKS", "CROX", "THO", "AAON", "WSM", "RL", "MUSA", "CASY",
              "EME", "JBL", "LSCC", "SAIA", "MANH", "CHDN", "EXP", "OLED",
              "FIVE", "HQY", "KBH", "OSK", "RS", "TTEK", "WWD", "AMG", "BC", "CBT",
              "DCI", "FFIN", "MSM"],
    "sp600": ["PLUG", "ROKU", "FSLY", "CALM", "SHOO", "MYRG", "PLXS", "AEIS",
              "ANDE", "ARCB", "AWR", "AZZ", "BCPC", "BMI", "CARG", "CENT", "CNMD",
              "CRVL", "DIOD", "DORM", "EPC", "EXPO", "FELE", "HELE", "HNI",
              "ICUI", "KFY", "LANC", "MATX", "NPO"],
}


# ---------------------------------------------------------------------------
# The list of stocks
# ---------------------------------------------------------------------------
def tickers_from_wikipedia(url):
    """
    Reads the constituents table from a Wikipedia page.

    Wikipedia returns 403 to requests that do not identify themselves, which is
    what happens if you hand the URL straight to pandas.read_html. So the page
    is fetched with requests and a browser User-Agent, then parsed.
    """
    try:
        import requests

        response = requests.get(url, headers=BROWSER_HEADERS, timeout=30)
        response.raise_for_status()
        tables = pd.read_html(io.StringIO(response.text))
    except Exception as error:
        print(f"    could not read the page ({type(error).__name__})")
        return []

    for table in tables:
        columns = [str(c) for c in table.columns]
        for name in ("Symbol", "Ticker symbol", "Ticker"):
            if name in columns:
                symbols = table[name].astype(str).str.strip()
                # Yahoo writes share classes with a dash, Wikipedia with a dot
                symbols = symbols.str.replace(".", "-", regex=False)
                found = [s for s in symbols if s and s.upper() != "NAN"]
                if len(found) > 50:      # a real constituents table, not a sidebar
                    return found
    return []


def build_universe():
    rows = []
    used_fallback = []

    for tier, url in config.INDEX_TIERS.items():
        print(f"  {tier}: reading constituents...")
        tickers = tickers_from_wikipedia(url)

        if not tickers:
            tickers = FALLBACK_TICKERS[tier]
            used_fallback.append(tier)
            print(f"    -> fallback list, only {len(tickers)} tickers")
        else:
            print(f"    -> {len(tickers)} constituents found")

        rows += [{"ticker": t, "tier": tier} for t in tickers[:config.MAX_PER_TIER]]

    return pd.DataFrame(rows).drop_duplicates(subset="ticker"), used_fallback


# ---------------------------------------------------------------------------
# The cache
# ---------------------------------------------------------------------------
def cache_path(ticker):
    # slashes and dots would break file names
    return CACHE_DIR / f"{ticker.replace('/', '-')}.csv"


def is_cached(ticker):
    path = cache_path(ticker)
    return path.exists() and path.stat().st_size > 1000


def save_to_cache(ticker, df):
    df.to_csv(cache_path(ticker), index=False)


def load_from_cache(ticker):
    return pd.read_csv(cache_path(ticker))


# ---------------------------------------------------------------------------
# Downloading
# ---------------------------------------------------------------------------
def tidy(one, ticker):
    """Turns one raw yfinance frame into our standard columns, or None."""
    one = one.dropna(how="all").reset_index()
    one.columns = [str(c).lower() for c in one.columns]
    if "close" not in one.columns or "date" not in one.columns or len(one) < 250:
        return None
    one["date"] = pd.to_datetime(one["date"]).dt.strftime("%Y-%m-%d")
    one = one[["date", "open", "high", "low", "close", "volume"]].dropna()
    one.insert(0, "ticker", ticker)
    return one if len(one) >= 250 else None


def download_batch(tickers):
    """
    Downloads a small group of tickers and writes each one to the cache
    immediately. Returns the set of tickers that succeeded.

    Writing straight to the cache is the whole point: if Yahoo cuts us off on
    the next batch, everything already downloaded is safe on disk.
    """
    try:
        import yfinance as yf

        raw = yf.download(tickers, start=config.START_DATE, end=config.END_DATE,
                          progress=False, auto_adjust=True, group_by="ticker",
                          threads=False)          # sequential: much gentler
        if raw is None or raw.empty:
            return set()

        succeeded = set()
        for ticker in tickers:
            try:
                one = raw[ticker] if isinstance(raw.columns, pd.MultiIndex) else raw
            except KeyError:
                continue
            clean = tidy(one, ticker)
            if clean is not None:
                save_to_cache(ticker, clean)
                succeeded.add(ticker)
        return succeeded

    except Exception:
        return set()


def download_missing(symbols):
    """
    Downloads whatever is not already cached, in small spaced-out batches,
    with a couple of long-pause retry rounds.
    """
    for round_number in range(RETRY_ROUNDS + 1):
        missing = [t for t in symbols if not is_cached(t)]
        if not missing:
            break

        if round_number > 0:
            print(f"\n  {len(missing)} still missing. Yahoo is probably throttling.")
            print(f"  Waiting {PAUSE_BEFORE_RETRY}s before trying again...")
            time.sleep(PAUSE_BEFORE_RETRY)

        for start in range(0, len(missing), BATCH_SIZE):
            batch = missing[start:start + BATCH_SIZE]
            download_batch(batch)
            cached_now = sum(1 for t in symbols if is_cached(t))
            print(f"  {cached_now}/{len(symbols)} symbols ready", end="\r", flush=True)
            time.sleep(PAUSE_BETWEEN_BATCHES)
        print()

    return [t for t in symbols if not is_cached(t)]


# ---------------------------------------------------------------------------
def save_to_database(prices, universe):
    with sqlite3.connect(config.DB_FILE) as conn:
        conn.execute("DROP TABLE IF EXISTS prices")
        conn.execute("""
            CREATE TABLE prices (
                ticker  TEXT NOT NULL,
                date    TEXT NOT NULL,
                open    REAL, high REAL, low REAL, close REAL,
                volume  INTEGER,
                PRIMARY KEY (ticker, date)
            )
        """)
        conn.execute("CREATE INDEX idx_ticker ON prices(ticker)")
        prices.to_sql("prices", conn, if_exists="append", index=False)
        universe.to_sql("universe", conn, if_exists="replace", index=False)


def main():
    print("STEP 1 — building the universe\n")
    universe, used_fallback = build_universe()

    already = sum(1 for t in universe["ticker"] if is_cached(t))
    if already:
        print(f"\n  {already} tickers already downloaded in a previous run — skipping those")

    # --- the benchmark comes first, while the quota is fresh ---
    print(f"\n  downloading the benchmark ({config.BENCHMARK}) first...")
    for attempt in range(4):
        if is_cached(config.BENCHMARK):
            break
        download_batch([config.BENCHMARK])
        if not is_cached(config.BENCHMARK):
            print(f"    attempt {attempt + 1} failed, waiting 20s")
            time.sleep(20)

    if not is_cached(config.BENCHMARK):
        print("\n" + "=" * 70)
        print(f"  STOPPING: could not download {config.BENCHMARK}.")
        print()
        print("  Everything here is measured against the benchmark, so continuing")
        print("  without it would produce numbers that look fine and mean nothing.")
        print()
        print("  Yahoo is refusing requests right now. Wait 15 minutes and run this")
        print("  script again — nothing you already downloaded will be lost.")
        print("=" * 70)
        raise SystemExit(1)
    print(f"    {config.BENCHMARK} ready")

    # --- everything else ---
    tickers = list(universe["ticker"])
    print(f"\n  {len(tickers)} stocks to fetch (small batches, this takes a few minutes)\n")
    missing = download_missing(tickers)

    # --- assemble from the cache ---
    have = [t for t in tickers if is_cached(t)]
    frames = [load_from_cache(t) for t in have] + [load_from_cache(config.BENCHMARK)]
    prices = pd.concat(frames, ignore_index=True)

    # Tickers we never got are dropped, not invented. A smaller real sample is
    # worth more than a full fake one.
    universe = universe[universe["ticker"].isin(have)]

    universe.to_csv(config.UNIVERSE_CSV, index=False)
    save_to_database(prices, universe)

    print(f"\n  {len(prices):,} price rows for {len(have)} stocks + the benchmark")
    print(f"  still missing: {len(missing)}")

    print("\n" + "-" * 70)
    if used_fallback:
        print(f"  PROBLEM: Wikipedia was unreachable for {', '.join(used_fallback)},")
        print("  so a short built-in list was used instead. Your sample is much")
        print("  smaller than intended. Check your connection and run this again.")
    elif len(have) < MIN_USABLE_STOCKS:
        print(f"  NOT ENOUGH DATA YET: only {len(have)} stocks.")
        print("  Yahoo cut you off. Wait about 15 minutes and RUN THIS SCRIPT AGAIN.")
        print("  It will skip everything already downloaded and only fetch the rest.")
    elif missing:
        print(f"  Usable: {len(have)} stocks. {len(missing)} are still missing.")
        print("  You can go on to step 2, but running this script again in 15")
        print("  minutes will fill in the rest and give you a bigger sample.")
    else:
        print(f"  Complete: all {len(have)} stocks downloaded.")
    print("-" * 70)

    if len(have) >= MIN_USABLE_STOCKS:
        print("\nNext: python step2_measure.py")
    else:
        print("\nNext: wait 15 minutes, then run python step1_download.py again")


if __name__ == "__main__":
    main()
