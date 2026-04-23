<div align="center">

# GOLDY-LUX

**Gold ETF Scenario Analysis & Decision Engine**

*Markov Chain Modeling | Monte Carlo Simulation | Prediction Tracking*

<img src="https://img.shields.io/badge/python-3.9+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
<img src="https://img.shields.io/badge/model-Markov_Chain-FF6F00?style=flat-square" alt="Model">
<img src="https://img.shields.io/badge/simulations-50%2C000-2E7D32?style=flat-square" alt="Simulations">
<img src="https://img.shields.io/badge/scenarios-12_branches-7B1FA2?style=flat-square" alt="Scenarios">

---

*A scenario-based analysis tool for gold ETF trading decisions during geopolitical conflict. Models 12 branching scenarios over 3-12 months using Markov chain state transitions and Monte Carlo simulation.*

</div>

---

## Executive Summary

> **The core question:** Given ongoing geopolitical conflict, when should you buy, hold, or sell a gold ETF?

Goldy-Lux builds a **branching scenario tree** of geopolitical outcomes (peace, stalemate, escalation, wider war), assigns **Markov transition probabilities** between states, and runs **50,000 Monte Carlo simulations** to evaluate investment strategies.

**Key insight from the model:** Gold does _not_ always act as a safe haven during conflict. Oil shocks can drive inflation expectations, push up real yields, strengthen the USD, and actually suppress gold prices. The relationship is complex and state-dependent.

<div align="center">
<img src="output/scenario_tree.png" alt="Scenario Tree" width="90%">
<br><em>Scenario tree: 12 terminal outcomes over 12 months. Node size = probability. Border color = recommended action.</em>
</div>

---

## Bottom Line

<!-- BOTTOM_LINE_START -->

### Updated: 2026-04-23 10:40

**Current Market Snapshot**

| Metric | Value |
|--------|-------|
| Gold (EUR/g) | **130.0** |
| Gold (USD/oz) | **$4,732** |
| Brent Oil | **$98/bbl** |
| EUR/USD | **1.170** |
| Portfolio held | **3,000** |
| Cash available | **3,000** |

**Model Predictions (gold EUR/g)**

| Horizon | Mean | 25th-75th %ile | P(above current) |
|---------|------|----------------|-------------------|
| 3 months | 132.6 | 123.5 - 140.2 | 55% |
| 6 months | 135.6 | 121.0 - 146.6 | 56% |
| 12 months | 140.6 | 116.9 - 156.4 | 55% |

**Key Recommendations**

| Scenario | Action | Detail |
|----------|--------|--------|
| Ceasefire collapses | WAIT | Don't chase spike; buy the 2-4 week pullback |
| Stalemate continues | DCA | Invest 1/3 of available cash per month on dips |
| De-escalation / peace | BUY | Deploy cash aggressively on the dip |
| Wider regional war | SELL | Take profits above ~20% gain; redeploy on pullback |

> _Model validation pending — predictions will be checked after 3+ months of tracking._

<!-- BOTTOM_LINE_END -->

---

## How It Works

### 1. Geopolitical State Model

The world is modeled as being in one of **five geopolitical states**:

| State | Description | Gold Impact |
|-------|-------------|-------------|
| **Peace** | Full deal, sanctions relief, Strait open | Negative (risk premium collapses) |
| **Detente** | Ceasefire holding, gradual normalization | Slightly negative |
| **Stalemate** | Frozen conflict, sporadic incidents | Slightly positive (CB buying supports) |
| **Escalation** | Active strikes, oil disrupted | Mixed (safe haven vs. real yield headwind) |
| **Regional War** | Wider conflict, major oil disruption | Strongly positive (panic > macro headwinds) |

### 2. Markov Chain Transitions

States transition quarterly according to a **Markov transition matrix** — the probability of moving to the next state depends only on the current state:

<div align="center">
<img src="output/markov_transitions.png" alt="Markov Transitions" width="75%">
</div>

**How honest are these numbers?** The transition probabilities (e.g., "48% chance escalation persists") are informed estimates, not measured frequencies. There is no dataset of "100 similar US-Iran conflicts" to calibrate against. They reflect a blend of historical conflict patterns (Gulf War, Iraq 2003, Soleimani 2020), current reporting, and judgment. Realistically they're accurate to ±5-10 percentage points at best. The prediction tracking system (see below) exists precisely to measure how well these estimates perform over time and flag when they need recalibration.

### 3. Scenario Tree

The transition matrix generates a **branching tree** of scenarios:
- **T=0** (now): 1 starting state
- **T=3 months**: 3-4 branches
- **T=6 months**: 8-10 branches
- **T=12 months**: 12 terminal scenarios

Each terminal node carries a probability, expected gold price range, and a buy/sell/hold recommendation.

### 4. Monte Carlo Simulation

A single simulation = "roll the dice" once per quarter through the Markov chain, sampling a random gold return at each step, and see where the portfolio ends up. That's one possible future. Repeat many times and you get a **distribution** of outcomes — letting you say things like "56% of futures were profitable" rather than just a single point forecast.

**Why 50,000 paths?** Monte Carlo estimation error shrinks as 1/sqrt(N):

| Simulations | MC Error | Runtime | Notes |
|-------------|----------|---------|-------|
| 1,000 | ~3% | <1s | Visibly noisy between runs |
| 10,000 | ~1% | ~1s | Stable for most purposes |
| **50,000** | **~0.45%** | **~2s** | Default — diminishing returns beyond here |
| 500,000 | ~0.14% | ~15s | Only needed for extreme tail estimates |

**An important caveat:** The input parameters — transition probabilities, return distributions — are themselves rough estimates, probably accurate to ±5-10% at best. A Monte Carlo error of 0.45% is absurdly more precise than the inputs warrant. **10,000 simulations would be perfectly adequate.** The 50k default is cheap (2 seconds) so we use it, but don't mistake the smooth output distributions for genuine precision. The real uncertainty is in the model assumptions, not the simulation count. You can change `N_SIMULATIONS` in `config.py` — try 1,000 and re-run a few times to see the estimates wobble, then try 10,000 and watch them stabilize. Beyond that, more simulations buy you almost nothing.

For background on Monte Carlo methods in finance, see [Glasserman (2003), *Monte Carlo Methods in Financial Engineering*](https://link.springer.com/book/10.1007/978-0-387-21617-1) or the [Wikipedia overview](https://en.wikipedia.org/wiki/Monte_Carlo_methods_in_finance).

<div align="center">
<img src="output/mc_simulated_paths.png" alt="Monte Carlo Paths" width="80%">
<br><em>200 sample paths from 50k simulations. Black lines = percentile bands. Right labels = terminal state distribution.</em>
</div>

### 5. Strategy Evaluation

Six investment strategies are evaluated against all 50,000 simulated paths:

| Strategy | Description |
|----------|-------------|
| **Hold Current** | Keep existing gold position, hold cash |
| **All In Now** | Deploy all available cash immediately |
| **DCA Quarterly** | Dollar-cost average over 4 quarters |
| **Buy the Dip** | Deploy cash only if gold drops >7% |
| **Sell All** | Exit gold entirely |
| **Tactical** | Buy on peace signals, sell on war signals |

<div align="center">
<img src="output/mc_strategy_analysis.png" alt="Strategy Comparison" width="80%">
<br><em>Top: outcome distributions by strategy. Bottom: risk-return scatter (higher = better return, left = lower risk).</em>
</div>

### 6. Prediction Tracking & Model Validation

Each run records the model's predictions with timestamps. When a prediction's target date passes, it is automatically validated against actual prices:

- **Mean Absolute Error** — how far off the predictions were
- **IQR Coverage** — did reality fall within the predicted 25th-75th percentile band?
- **Directional Accuracy** — did the model correctly predict up vs. down?

This creates a feedback loop to assess and improve model calibration over time.

---

## Quick Start

### Prerequisites

```bash
pip install yfinance plotly kaleido numpy pandas
```

### Run Analysis

```bash
# Clone
git clone git@github.com:johnusher/goldy_lux.git
cd goldy_lux

# Run full analysis
./update_gold.sh

# Quick mode (skip Monte Carlo)
./update_gold.sh --quick

# Auto-commit and push results
./update_gold.sh --push
```

### View Results

- **Interactive charts**: Open any `.html` file in `output/` in your browser
- **GitHub Pages**: If enabled, visit `https://johnusher.github.io/goldy_lux/`
- **Terminal summary**: Printed during `update_gold.sh` run
- **Full report**: `output/analysis_report.txt`

---

## Configuration

Edit **`config.py`** to adjust portfolio and model parameters:

```python
# === YOUR PORTFOLIO — Change these to match your situation ===

PORTFOLIO_HELD = 3000       # EUR currently invested in gold ETF
PORTFOLIO_AVAILABLE = 3000  # EUR available to invest

# === YOUR ETF ===

ETF_TICKER = "PPFB.DE"     # iShares Physical Gold ETC on Xetra
```

All model parameters (transition matrix, return distributions, initial state) are also in `config.py` with documentation. The transition matrix and return parameters are the key knobs for tuning the model.

---

## Project Structure

```
goldy_lux/
  config.py                  # All user-configurable parameters
  update_gold.sh             # One-command update script
  README.md                  # This file (bottom line auto-updated)
  src/
    scenario_tree.py         # Scenario tree model & visualization
    monte_carlo.py           # Monte Carlo simulation & strategy analysis
    prediction_tracker.py    # Record predictions, validate vs reality
    generate_readme_section.py  # Auto-update README bottom line
  output/                    # Generated charts & reports
    *.html                   # Interactive Plotly visualizations
    *.png                    # Static chart images
    analysis_report.txt      # Full text report
    scenario_data.json       # Raw scenario data
  docs/                      # HTML copies for GitHub Pages
  data/
    prediction_history.json  # Prediction tracking state machine
    model_metrics.json       # Latest performance metrics
```

---

## Output Files

| File | Description |
|------|-------------|
| `scenario_tree.html/png` | Interactive branching scenario tree |
| `mc_simulated_paths.html/png` | 50k Monte Carlo gold price paths |
| `mc_strategy_analysis.html/png` | Strategy comparison (violin + risk-return) |
| `mc_optimal_timing.html/png` | When to enter for best risk-adjusted return |
| `historical_context.html/png` | Gold ETC + Brent oil with conflict events |
| `price_heatmap.html/png` | Gold price probability distribution over time |
| `decision_timeline.html/png` | Buy/sell signals across scenarios |
| `markov_transitions.html/png` | Transition matrices & state evolution |
| `strategy_comparison.html/png` | Simple strategy bar chart |

---

## Model Validation

The prediction tracker implements a **state machine** for model accountability:

```
[First Run]                    [Subsequent Runs]
     |                              |
     v                              v
Record predictions            Fetch current prices
for +3m, +6m, +12m          Compare to past predictions
     |                       whose target date has passed
     v                              |
Save to                             v
prediction_history.json      Record validation results
                             Compute performance metrics
                                    |
                                    v
                             Update README bottom line
                             with latest accuracy data
```

**How to assess model quality:**
- After 3+ months of tracking, check `data/prediction_history.json` for validation results
- The README's bottom line section shows current model performance
- If directional accuracy falls below 50%, the model is no better than a coin flip and the transition matrix or return parameters should be re-calibrated

**Tuning the model:**
1. Adjust `TRANSITION_MATRIX` in `config.py` if geopolitical dynamics change
2. Adjust `GOLD_EUR_RETURNS` if gold's response to states differs from expectations
3. Adjust `INITIAL_STATE_PROBS` when the current geopolitical situation changes
4. Re-run `./update_gold.sh` to see the effect

---

## Design Choices & Assumptions

> Every model encodes assumptions. Here are ours, stated plainly, so you can judge whether they're reasonable for your situation.

### Why Brent crude oil?

The model tracks Brent (`BZ=F`) as its oil benchmark. There are several alternatives — here's why Brent is the right one for this specific use case:

| Benchmark | What it is | Hormuz sensitivity | Data quality |
|-----------|-----------|-------------------|-------------|
| **Brent** | International reference (~80% of global trade) | **High** — Gulf exports are priced off Brent | Real-time futures via `BZ=F` |
| WTI | US domestic benchmark | Lower — US is now a net exporter | Good, but wrong benchmark |
| Dubai/Oman | Physical Middle East crude | Highest | Poor — lagged, hard to source |
| OPEC Basket | OPEC composite | High | Reported with 1-2 day lag |

Brent captures the full transmission chain that matters for a EUR-denominated gold investor: **Strait of Hormuz disruption → Brent spike → EU energy inflation → ECB policy response → EUR/USD move → gold price in EUR**. WTI would understate Gulf disruption impact because US domestic supply is largely insulated. Dubai/Oman crude would be the most direct measure but is impractical to source programmatically.

### Why these five geopolitical states?

The model discretizes a continuous spectrum of conflict intensity into five bins. Fewer states (e.g., "war" vs "peace") would miss the critical middle ground — the stalemate/detente range where most of the probability mass sits. More states (e.g., 8-10) would require even more subjective transition estimates with no meaningful gain in decision quality. Five states capture the main regimes that produce *qualitatively different* gold market dynamics.

### Why quarterly transitions?

Geopolitical shifts don't happen on a quarterly schedule, but quarterly steps are the coarsest resolution that still captures the key decision points: "should I invest now, in 3 months, in 6 months, or in 9 months?" Monthly steps would quadruple the number of transitions to estimate without changing the strategic conclusions. Weekly steps would be false precision given the ±5-10% uncertainty in the transition probabilities themselves.

### Gold returns per state — where do these come from?

The return distributions (e.g., "Escalation: mean +3%, std 12% per quarter") are calibrated from:

1. **Historical conflict episodes**: Gold's behaviour during Gulf War 1990 (+13% then reversal), Iraq 2003 (buy-the-rumour/sell-the-news), Soleimani strike 2020 (+3.4% initial, +24.6% at 12m but amplified by COVID), and the current 2026 conflict itself (worst month since 2008 in March — the "safe haven failure").
2. **Macro mechanism analysis**: In this conflict, oil shock → inflation expectations → higher real yields → stronger USD has *suppressed* gold, not lifted it. The return distributions reflect this counterintuitive dynamic rather than naive "war = gold up" assumptions.
3. **Central bank buying data**: 1,000+ tonnes/year of central bank gold purchases (led by China, India, Turkey) creates a structural floor that is state-independent.

These are informed estimates, not fitted parameters. They are honest guesses. The prediction tracker exists to measure how wrong they are over time.

### Why not use real historical data to fit the model?

There is no dataset of "200 US-Iran conflicts with quarterly gold returns." Geopolitical events are unique enough that pure statistical fitting would be overfit to irrelevant history. The model instead uses historical episodes for *calibration* (what order of magnitude?) and *mechanism validation* (does gold actually go up during escalation, or does the USD channel dominate?), then applies judgment. This is inherently subjective — see [Tetlock & Gardner, *Superforecasting* (2015)](https://en.wikipedia.org/wiki/Superforecasting) for context on structured geopolitical probability estimation.

### Cash earns 0%

The model treats uninvested cash as earning nothing. In practice, EUR cash earns the ECB deposit rate (~3-4% annualized as of 2026). This means the model slightly overstates the advantage of gold strategies vs. holding cash. For a 12-month horizon and €3k cash, this is roughly €90-120 of unmodelled return — not negligible, but not decision-changing either.

### EUR/USD is implicit, not modelled separately

Gold trades in USD. The iShares Physical Gold ETC is not EUR-hedged, so its EUR price depends on both gold-USD and EUR/USD. The model folds both into a single "gold EUR return" distribution per state rather than modelling them separately. This simplification loses the correlation structure — in an escalation scenario, gold-USD might be flat while EUR weakens against USD (safe-haven flows), making gold-EUR positive. The return distributions were designed to incorporate this effect implicitly, but it's a simplification.

### iShares Physical Gold ETC tracking

The model assumes the ETC perfectly tracks the spot gold price in EUR. In practice, the ETC has:
- A total expense ratio (TER) of 0.12%
- Bid-ask spreads (typically tight on Xetra, but can widen in volatile markets)
- Slight tracking error from the physical gold backing mechanism

Over a 12-month horizon on a ~€6k position, these frictions amount to ~€7-15 — negligible for the level of precision in this model.

---

## Limitations

> This tool is a structured framework for thinking about scenarios, not a crystal ball.

**Structural limitations:**
- **Markov assumption**: The next state depends only on the current state, not history. In reality, geopolitical momentum and path-dependency matter — six months of stalemate creates different dynamics than a fresh stalemate after escalation.
- **Normal distributions**: Gold returns are modeled as normally distributed. Real markets have fat tails — extreme moves (Black Swan events) are more likely than the model suggests. The model will *underestimate* the probability of very large moves in either direction.
- **Static parameters**: The transition matrix and return distributions don't update automatically from market data — they require manual recalibration when the world changes. This is the model's biggest weakness for long-term use.
- **No tax effects**: Capital gains tax (Abgeltungsteuer in Germany: 26.375% on gains) is not modelled. It would reduce the advantage of active trading strategies (tactical, sell-and-rebuy) relative to buy-and-hold.
- **Subjective probabilities**: The transition matrix reflects expert judgment, not objective calibration. Different analysts would assign different numbers. The prediction tracker is the mechanism for accountability.

**Data limitations:**
- Historical data from Yahoo Finance may have gaps, delays, or retroactive adjustments
- Gold price in EUR depends on both gold-USD and EUR/USD, each with their own dynamics
- Central bank gold buying data (a key structural driver) is reported with a 1-2 month lag by the World Gold Council

---

## Disclaimer

**This tool is for educational and research purposes only. It does not constitute financial advice, investment advice, or a recommendation to buy or sell any security.**

- All probabilities and predictions are **subjective model estimates** based on scenario analysis
- Past performance does not predict future results
- Gold prices can move in ways not captured by this model
- The authors are not financial advisors and accept no liability for investment decisions made using this tool
- Always consult a qualified financial advisor before making investment decisions
- This is a **public repository** — do not commit personal financial data beyond what is in `config.py`

---

<div align="center">

*Built with Python, Plotly, and a healthy respect for uncertainty.*

</div>
