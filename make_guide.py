"""
THE STUDY GUIDE (optional)
==========================

Run it with:    python make_guide.py

Produces output/study_guide.pdf: a short document for your own use, explaining
the project in plain language and preparing you to talk about it. It reads the
results from the CSV files, so re-running it after a new run refreshes it.

It is written to private/, a folder that .gitignore excludes entirely, so it
never reaches GitHub. That is deliberate: it contains your interview answers,
and they work better if the interviewer has not read them first.
"""

from datetime import date

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)

import config

NAVY = colors.HexColor("#1F2A44")
RUST = colors.HexColor("#C0562D")
GREY = colors.HexColor("#5A6472")
LIGHT = colors.HexColor("#F2F4F7")

base = getSampleStyleSheet()
STYLE = {
    "title": ParagraphStyle("t", parent=base["Title"], fontSize=20, leading=24,
                            textColor=NAVY, spaceAfter=4),
    "sub": ParagraphStyle("s", parent=base["Normal"], fontSize=10, leading=13,
                          textColor=GREY, spaceAfter=12),
    "h1": ParagraphStyle("h1", parent=base["Heading1"], fontSize=14, leading=17,
                         textColor=NAVY, spaceBefore=12, spaceAfter=6),
    "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=11, leading=13,
                         textColor=RUST, spaceBefore=9, spaceAfter=4),
    "body": ParagraphStyle("b", parent=base["BodyText"], fontSize=9.5, leading=13,
                           alignment=TA_JUSTIFY, spaceAfter=6),
    "bullet": ParagraphStyle("bu", parent=base["BodyText"], fontSize=9.5, leading=13,
                             leftIndent=11, spaceAfter=3),
    "q": ParagraphStyle("q", parent=base["BodyText"], fontSize=9.8, leading=12.5,
                        fontName="Helvetica-Bold", textColor=NAVY,
                        spaceBefore=8, spaceAfter=3),
    "cell": ParagraphStyle("c", parent=base["Normal"], fontSize=8.2, leading=10.5),
    "cellb": ParagraphStyle("cb", parent=base["Normal"], fontSize=8.2, leading=10.5,
                            fontName="Helvetica-Bold", textColor=colors.white),
}


def P(text, style="body"):
    return Paragraph(text, STYLE[style])


def B(text):
    return Paragraph(text, STYLE["bullet"], bulletText="\u2022")


def box(text):
    t = Table([[Paragraph(text, STYLE["body"])]], colWidths=[166 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, RUST),
    ]))
    return t


def table(header, rows, widths):
    data = [[Paragraph(h, STYLE["cellb"]) for h in header]]
    data += [[Paragraph(str(c), STYLE["cell"]) for c in r] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D5DAE1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def average(df, tier, column, fmt="{:.2f}"):
    try:
        value = df[df["tier"] == tier][column].mean()
        return fmt.format(value)
    except Exception:
        return "n/a"


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, A4[1] - 8 * mm, A4[0], 8 * mm, stroke=0, fill=1)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(GREY)
    canvas.drawString(22 * mm, 12 * mm, "Passive investing and price discovery - study guide")
    canvas.drawRightString(A4[0] - 22 * mm, 12 * mm, f"p. {doc.page}")
    canvas.restoreState()


def build_story(measures, cost, regressions):
    s = []
    hi, lo = "sp500", "sp600"

    s += [Spacer(1, 5 * mm),
          P("Passive investing and price discovery", "title"),
          P(f"Study guide &mdash; generated {date.today():%d %B %Y}. "
            f"Sample: {len(measures)} US stocks from the S&amp;P 500, 400 and 600, "
            f"{config.START_DATE} to {config.END_DATE}, benchmark {config.BENCHMARK}.", "sub")]

    # ---------------------------------------------------------------- part 1
    s += [P("1. What the project does, in plain language", "h1"),
          P("Index funds and ETFs buy every stock in an index in proportion to its size. "
            "They do not form a view about whether any individual company is any good. "
            "Over the last fifteen years they have gone from roughly a fifth of US fund "
            "assets to more than half. The obvious question is what that does to prices: if "
            "a growing share of the money is not judging companies, do prices still tell you "
            "anything about a specific company?"),
          P("The project answers three questions with public daily price data:"),
          B("<b>Have stocks started moving together more over time?</b>"),
          B("<b>Are heavily indexed stocks less \u2018individual\u2019 than less indexed ones?</b>"),
          B("<b>Does any of that show up in what it costs a company to raise equity?</b>"),
          Spacer(1, 3 * mm),
          box("<b>The one distinction to keep straight.</b> Index funds have made trading "
              "cheaper &mdash; that part is not in dispute. The open question is whether they "
              "have made prices less <i>informative</i> about individual companies. Those are "
              "two different things, and people constantly mix them up.")]

    # ---------------------------------------------------------------- part 2
    s += [P("2. The measures, and where they come from", "h1"),
          P("Everything comes from one regression, run for each stock and each year:"),
          P("<font face='Courier'>stock return = a + b &times; market return + error</font>"),
          table(["Measure", "What it is", "How to read it"],
                [["Beta", "the <font face='Courier'>b</font> in the equation",
                  "How much the stock moves when the market moves. Beta 1.2 means it "
                  "typically moves 20% more than the market."],
                 ["Comovement (R-squared)", "how well the regression fits",
                  "Close to 1: almost all the stock's movement is the market. Close to 0: it "
                  "moves on its own news. This is the headline price-discovery measure."],
                 ["Own volatility", "the size of the <font face='Courier'>error</font>, "
                  "annualised",
                  "The company-specific movement that is left over. The mirror image of "
                  "comovement, but in units you can interpret."],
                 ["Reaction delay", "extra fit from adding <i>yesterday's</i> market returns",
                  "0 means the stock reacts to market news immediately. Higher means it "
                  "reacts late, which is a sign of a thinly-followed stock."],
                 ["Trading range", "average daily (high - low) / close",
                  "A rough proxy for what it costs to trade. Not the real bid-ask spread, "
                  "which needs intraday data."],
                 ["Amihud illiquidity", "average price move per dollar traded",
                  "Higher means a given trade moves the price more, i.e. less liquid. Only "
                  "the ranking is meaningful, not the level."]],
                [30 * mm, 48 * mm, 88 * mm])]

    # ------------------------------------------------- the regression section
    comovement = regressions[regressions["dependent_variable"] == "comovement_r2"]
    raw_row = comovement[comovement["size_control"] == "no"]
    ctrl_row = comovement[(comovement["sample"] == "all stocks")
                          & (comovement["year_effects"] == "yes")]
    matched_row = comovement[comovement["sample"].str.startswith("matched")]

    s += [PageBreak(), P("3. The obvious objection, and the answer", "h1"),
          P("This is the most important section of the project and the one to talk about "
            "first if someone asks what you learned. The raw comparison shows S&amp;P 500 "
            "stocks moving with the market far more than smaller stocks. The obvious "
            "objection is that S&amp;P 500 companies are simply bigger, and bigger companies "
            "differ in analyst coverage, liquidity and ownership &mdash; all of which could "
            "produce the same pattern with no help from index funds."),
          P("The project answers it in three ways rather than putting it in a footnote."),
          B("<b>Controls.</b> Instead of comparing averages, run a regression with size on "
            "the right-hand side: <font face='Courier' size='8'>comovement = a + b x "
            "(in the S&amp;P 500) + c x log(size) + year effects</font>. The coefficient "
            "<font face='Courier'>b</font> is what survives once size is accounted for. If "
            "it collapses, the story was always about size."),
          B("<b>Year fixed effects.</b> A dummy for each year, which absorbs anything that "
            "happened to the whole market in a given year. Without them a common shock could "
            "masquerade as a group difference."),
          B("<b>Standard errors clustered by firm.</b> Each company appears once per year, "
            "so its errors are correlated across years. Ordinary standard errors assume "
            "independence, come out far too small, and make everything look significant. "
            "This is the most common mistake in panel work of this kind, and being able to "
            "say why you did it is worth more than the result itself."),
          B("<b>A matched sample.</b> The smallest companies in the S&amp;P 500 against the "
            "largest in the S&amp;P 400: similar in size, opposite sides of the line that "
            "decides how much index money must own them. If the difference survives there, "
            "size alone is a weaker explanation."),
          Spacer(1, 3 * mm),
          table(["Specification", "Coefficient on \u2018in the S&P 500\u2019",
                 "t-statistic", "What it tells you"],
                [["Raw difference, no controls",
                  f"{raw_row['sp500_coefficient'].iloc[0]:+.3f}" if not raw_row.empty else "n/a",
                  f"{raw_row['t_statistic'].iloc[0]:.1f}" if not raw_row.empty else "n/a",
                  "The headline gap, and an overstatement."],
                 ["Plus size and year effects",
                  f"{ctrl_row['sp500_coefficient'].iloc[0]:+.3f}" if not ctrl_row.empty else "n/a",
                  f"{ctrl_row['t_statistic'].iloc[0]:.1f}" if not ctrl_row.empty else "n/a",
                  "What is left once size is accounted for. This is the number to quote."],
                 ["Matched sample",
                  f"{matched_row['sp500_coefficient'].iloc[0]:+.3f}" if not matched_row.empty else "n/a",
                  f"{matched_row['t_statistic'].iloc[0]:.1f}" if not matched_row.empty else "n/a",
                  "Similar-sized firms either side of the index boundary."]],
                [42 * mm, 42 * mm, 22 * mm, 60 * mm]),
          Spacer(1, 2 * mm),
          box("<b>Say this, not the raw number.</b> \u201cThe raw gap overstates it. Once I "
              "control for size and year effects the coefficient drops, and what is left is "
              "the number I would defend. It is still not a causal estimate &mdash; index "
              "membership is not randomly assigned &mdash; but it is a much more honest one "
              "than the raw comparison.\u201d")]

    # ---------------------------------------------------------------- part 3
    s += [PageBreak(), P("4. The cost of capital step", "h1"),
          P("This is where the project answers the question a company would actually ask. "
            "The cost of equity is the return shareholders demand to put money in; it is the "
            "discount rate in a valuation, and the bar a project has to clear to be worth "
            "doing. It is built here in two pieces."),
          P("<b>Piece one, CAPM:</b> "
            "<font face='Courier'>risk-free rate + beta &times; market risk premium</font>. "
            "Standard, uncontroversial, and the beta comes straight from step 2."),
          P("<b>Piece two, liquidity:</b> Amihud and Mendelson showed in 1986 that investors "
            "demand a higher return to hold assets that are expensive to trade. So a stock "
            "with higher trading costs carries an extra premium, "
            "<font face='Courier'>k &times; trading cost</font>."),
          box("<b>The catch, and the most interesting part of the project.</b> The coefficient "
              "<font face='Courier'>k</font> is an assumption you choose, not something "
              "estimated from this data. So the project reports a low case, a base case and a "
              "high case. In the current run the gap between the two groups is about "
              f"{abs(cost[cost['tier'] == hi]['liquidity_premium_bp'].mean() - cost[cost['tier'] == lo]['liquidity_premium_bp'].mean()):.0f} "
              "basis points, while moving the assumption across its plausible range moves "
              "that same gap by several hundred. <b>The assumption moves the answer more than "
              "the data does.</b> Saying that plainly is better than producing a confident "
              "number, and it is exactly why nobody can honestly tell you how much index "
              "investing has raised the cost of capital."),
          Spacer(1, 3 * mm),
          P("Current results by group", "h2"),
          table(["Group", "Beta", "Comovement", "Own vol.", "Trading cost",
                 "CAPM", "Liquidity", "Total"],
                [["S&P 500", average(measures, hi, "beta"),
                  average(measures, hi, "comovement_r2"),
                  average(measures, hi, "own_volatility"),
                  average(cost, hi, "trading_cost_pct") + "%",
                  average(cost, hi, "capm_pct") + "%",
                  average(cost, hi, "liquidity_premium_bp", "{:.0f}") + " bp",
                  average(cost, hi, "total_cost_of_equity_pct") + "%"],
                 ["S&P 600", average(measures, lo, "beta"),
                  average(measures, lo, "comovement_r2"),
                  average(measures, lo, "own_volatility"),
                  average(cost, lo, "trading_cost_pct") + "%",
                  average(cost, lo, "capm_pct") + "%",
                  average(cost, lo, "liquidity_premium_bp", "{:.0f}") + " bp",
                  average(cost, lo, "total_cost_of_equity_pct") + "%"]],
                [27 * mm, 16 * mm, 24 * mm, 19 * mm, 22 * mm, 17 * mm, 21 * mm, 18 * mm])]

    # ---------------------------------------------------------------- part 4
    s += [P("5. How the code is organised", "h1"),
          P("Four numbered scripts, run in order. Each does one thing you can name."),
          table(["File", "What it does", "What it produces"],
                [["<font face='Courier'>config.py</font>",
                  "All the settings: stocks, dates, assumptions. The only file you normally "
                  "edit.", "nothing &mdash; it is read by the others"],
                 ["<font face='Courier'>step1_download.py</font>",
                  "Reads the real S&amp;P 500 / 400 / 600 constituent lists from Wikipedia, "
                  "then downloads daily prices in batches and loads them into SQLite.",
                  "<font face='Courier'>data/universe.csv</font>, "
                  "<font face='Courier'>data/market.db</font>"],
                 ["<font face='Courier'>step2_measure.py</font>",
                  "Pulls returns out of SQL with a LAG window function, runs the regressions, "
                  "computes the six measures per stock and per year.",
                  "<font face='Courier'>measures_by_stock.csv</font>, "
                  "<font face='Courier'>measures_by_year.csv</font>"],
                 ["<font face='Courier'>step3_regression.py</font>",
                  "The panel regression: size controls, year fixed effects, standard errors "
                  "clustered by firm, and the matched boundary sample.",
                  "<font face='Courier'>regression_results.csv</font>"],
                 ["<font face='Courier'>step4_cost_of_capital.py</font>",
                  "Turns beta and trading cost into a cost of equity, with the low/base/high "
                  "scenarios.", "<font face='Courier'>cost_of_equity.csv</font>"],
                 ["<font face='Courier'>step5_report.py</font>",
                  "Draws the five charts and writes the report.",
                  "<font face='Courier'>output/report.md</font>, "
                  "<font face='Courier'>output/figures/</font>"],
                 ["<font face='Courier'>app.py</font>",
                  "Optional interactive dashboard with the assumption slider.",
                  "a web page"]],
                [40 * mm, 76 * mm, 50 * mm]),
          Spacer(1, 2 * mm),
          P("Two details worth being able to explain", "h2"),
          B("<b>Why SQL at all.</b> The daily return needs yesterday's closing price. "
            "<font face='Courier' size='8'>LAG(close) OVER (PARTITION BY ticker ORDER BY "
            "date)</font> does that in one line, and the "
            "<font face='Courier'>PARTITION BY</font> makes it impossible to accidentally "
            "compute a return between the last day of one stock and the first day of the "
            "next &mdash; a real mistake people make doing this in pandas."),
          B("<b>Why the logarithm is taken in Python, not SQL.</b> In SQLite, "
            "<font face='Courier'>LOG()</font> is the base-10 logarithm and "
            "<font face='Courier'>LN()</font> is the natural one, and neither is guaranteed to "
            "exist depending on how SQLite was built. Getting that wrong does not raise an "
            "error &mdash; it silently multiplies every return by 0.43 and the numbers still "
            "look plausible.")]

    # ---------------------------------------------------------------- part 5
    s += [PageBreak(), P("6. How to present it (about two minutes)", "h1")]
    s += [box(
        "\u201cIndex funds have gone from about a fifth of US fund assets to more than half "
        "in fifteen years. They buy every stock in the index in proportion to its size, "
        "without forming any view about whether the company is any good. So I wanted to look "
        "at what that does to prices, using only public daily data.<br/><br/>"

        "The core of it is one regression per stock per year: the stock's return on the "
        "market's return. The beta comes out of it, but what I actually care about is the "
        "R-squared &mdash; how much of a stock's movement is just the index. If a company's "
        "price is basically the index wearing a ticker, it is not telling you much about the "
        "company. I ran that on a few hundred stocks across the S&amp;P 500, 400 and 600, "
        "which differ a lot in how much passive money has to own them.<br/><br/>"

        "The raw gap is big, but the obvious objection is that S&amp;P 500 companies are just "
        "bigger. So I didn't stop at group averages &mdash; I put size and year fixed effects "
        "into a panel regression, with standard errors clustered by firm because each company "
        "shows up once a year. Controlling for size removes a big chunk of the raw gap, and I "
        "quote what's left, not the headline number. I also built a matched sample: the "
        "smallest S&amp;P 500 names against the largest S&amp;P 400 names, similar size but "
        "opposite sides of the index boundary.<br/><br/>"

        "Then I took it one step further, to the question a CFO would ask: does this reach "
        "the cost of capital? I built the cost of equity in two pieces &mdash; the CAPM part, "
        "which is standard, and a liquidity premium, because investors want to be paid for "
        "holding something expensive to trade.<br/><br/>"

        "And the most interesting thing I found was in that second piece. The liquidity "
        "coefficient is an assumption, not something I can estimate from price data. When I "
        "moved it across its plausible range, it changed the answer more than the difference "
        "between my two groups of stocks did. So what I can honestly say is that a difference "
        "exists and roughly how big it might be &mdash; not that index investing raised the "
        "cost of capital by X basis points. I'd rather show that clearly than produce a "
        "confident number I can't defend.<br/><br/>"

        "The obvious limitation is that my two groups differ in size as well as in index "
        "ownership, so it is descriptive, not causal. With actual index-ownership percentages "
        "and stocks matched on size, it would be a much stronger design.\u201d")]

    s += [Spacer(1, 3 * mm), P("Delivery notes", "h2"),
          B("Lead with the idea, not the method. Anyone understands \u2018is this price "
            "telling me about the company or just about the market?\u2019"),
          B("The assumption-sensitivity point is your best material. Most people present a "
            "number; presenting the reason a number cannot be trusted is rarer and better."),
          B("Say the limitation before they ask. Being the person who names their own "
            "weakness reads as confidence; being caught by it does not."),
          B("Have two numbers memorised: the average comovement for each group.")]

    # ---------------------------------------------------------------- part 6
    s += [P("7. Questions you should expect", "h1")]
    questions = [
        ("Why does a high R-squared mean the price is less informative?",
         "Because the R-squared is the share of the stock's movement that the market alone "
         "explains. Whatever is left over is the part that responds to news about the company "
         "itself. So if R-squared rises, a smaller share of the price is reacting to the "
         "company. The caveat, which I'd give unprompted: a high R-squared can also just mean "
         "the company genuinely has market-like earnings. A regulated utility and a biotech "
         "should not have the same R-squared for reasons that have nothing to do with index "
         "funds. That is why I look at the trend over time and the comparison between groups "
         "rather than the level for any one stock."),

        ("Why did you cluster the standard errors, and what happens if you don't?",
         "Because each company appears once per year, so its observations are not "
         "independent: whatever makes a company unusual in 2015 probably still makes it "
         "unusual in 2016. Ordinary standard errors assume every observation is independent, "
         "so with a few hundred firms times a dozen years they treat several thousand "
         "correlated observations as if they were several thousand independent ones. The "
         "standard errors come out far too small and everything looks significant. Clustering "
         "by firm allows the errors of the same company to be correlated across years. I "
         "implemented the sandwich estimator directly in numpy rather than importing it, so I "
         "could see what it does. Caveat: clustering fixes the within-firm correlation, not a "
         "common shock hitting every firm in the same year &mdash; that is what the year "
         "fixed effects are for."),

        ("Does this prove index investing caused any of it?",
         "No, and I would push back on anyone reading it that way. My two groups differ in "
         "size, analyst coverage and volatility, not only in index ownership, so any gap is "
         "consistent with the index story and equally consistent with a pure size story. To "
         "do better I would need actual index-ownership percentages per company and a set of "
         "stocks matched on size, so the groups differ mainly in the thing I care about. The "
         "project measures a difference; it does not attribute it."),

        ("Why did you use the daily high-low range instead of the bid-ask spread?",
         "Because the real spread needs intraday quote data, which is not free. The daily "
         "range is a proxy: a stock that swings a lot within the day is usually one that is "
         "harder to trade in size. It is rough, and it also picks up genuine volatility, not "
         "only trading costs, which means it overstates the trading cost of a volatile but "
         "liquid stock. I say so in the report rather than presenting it as a spread. I also "
         "compute the Amihud illiquidity measure as a cross-check, and the two give the same "
         "ranking, which is some reassurance."),

        ("Your liquidity premium assumption does a lot of work. Isn't that a problem?",
         "It is the finding, not a flaw. I cannot estimate that coefficient from price data, "
         "so I set it explicitly in the config file, stored it in the output next to every "
         "number it produced, and ran a low, base and high case. It turns out the range "
         "created by the assumption is wider than the difference between my two groups of "
         "stocks. The alternative would have been to pick one value and report a confident "
         "figure, which would have been a worse piece of work that looked better. Anyone "
         "quoting a precise basis-point effect of index investing on the cost of capital is "
         "either using data I don't have or isn't being careful."),

        ("What would you do with six more months and a data budget?",
         "Three things. Actual index-ownership percentages per company, so the treatment "
         "variable is the real thing rather than a size proxy. A few hundred stocks matched "
         "on size and sector, so the comparison is between similar companies. And a within-"
         "company design: instead of comparing different firms, track the same firm as its "
         "index ownership changes over time, which removes everything that is fixed about the "
         "company. That last one is what would turn it from descriptive into something with a "
         "real argument behind it."),

        ("Walk me through the code.",
         "Four numbered scripts you run in order. The first downloads prices into a SQLite "
         "database. The second pulls the returns back out with a SQL window function and runs "
         "one regression per stock per year to get the four measures. The third turns beta and "
         "trading cost into a cost of equity with the three assumption scenarios. The fourth "
         "draws the charts and writes the report. There is also a Streamlit dashboard with a "
         "slider for the liquidity assumption, which is the fastest way to show someone that "
         "the assumption matters more than the data. Everything configurable is in one file, "
         "so changing the stocks or the period means editing one place and re-running."),
    ]
    for i, (q, a) in enumerate(questions, start=1):
        s.append(KeepTogether([P(f"Q{i}. {q}", "q"), P(a)]))

    s += [Spacer(1, 4 * mm),
          P("8. Things to revise before an interview", "h1"),
          B("<b>CAPM.</b> cost of equity = risk-free + beta &times; market risk premium. Know "
            "what each piece is and why beta is the only risk that gets paid for."),
          B("<b>What R-squared actually is.</b> The share of the variation in the dependent "
            "variable explained by the model. Be able to say that without hesitating."),
          B("<b>Systematic vs idiosyncratic risk.</b> Why diversification removes one and not "
            "the other, and why that is the reason CAPM prices only beta."),
          B("<b>Liquidity and required return.</b> Amihud &amp; Mendelson (1986): investors "
            "demand compensation for holding assets that are expensive to trade."),
          B("<b>Why index funds might matter here.</b> They allocate money by index weight "
            "rather than by any judgement about the company, so as their share grows, a "
            "smaller fraction of trading reflects a view on a specific firm."),
          B("<b>The difference between descriptive and causal.</b> Know which one your project "
            "is (descriptive) and what would make it the other.")]

    return s


def main():
    measures = pd.read_csv(config.STOCK_CSV)
    cost = pd.read_csv(config.COST_CSV)
    regressions = pd.read_csv(config.REGRESSION_CSV)

    doc = BaseDocTemplate(str(config.GUIDE_FILE), pagesize=A4,
                          leftMargin=22 * mm, rightMargin=22 * mm,
                          topMargin=18 * mm, bottomMargin=20 * mm,
                          title="Passive investing and price discovery - study guide")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=header_footer)])
    doc.build(build_story(measures, cost, regressions))

    print(f"Study guide written to {config.GUIDE_FILE}")


if __name__ == "__main__":
    main()
