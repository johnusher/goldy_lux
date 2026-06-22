#!/usr/bin/env python3
"""
Generate the date-stamped 'Bottom Line' section for README.md.
Replaces content between <!-- BOTTOM_LINE_START --> and <!-- BOTTOM_LINE_END -->.
"""

import os
import sys
import json
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import config

README_PATH = os.path.join(ROOT, 'README.md')
METRICS_FILE = os.path.join(config.DATA_DIR, 'model_metrics.json')
REPORT_FILE = os.path.join(config.OUTPUT_DIR, 'analysis_report.txt')
MC_REPORT = os.path.join(config.OUTPUT_DIR, 'mc_summary.json')
HISTORY_FILE = os.path.join(config.DATA_DIR, 'decision_history.json')

START_MARKER = '<!-- BOTTOM_LINE_START -->'
END_MARKER = '<!-- BOTTOM_LINE_END -->'
EXEC_START = '<!-- EXEC_SUMMARY_START -->'
EXEC_END = '<!-- EXEC_SUMMARY_END -->'
HISTORY_START = '<!-- DECISION_HISTORY_START -->'
HISTORY_END = '<!-- DECISION_HISTORY_END -->'


def generate_bottom_line():
    """Generate the bottom line markdown section."""

    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    # Load metrics
    try:
        with open(METRICS_FILE) as f:
            data = json.load(f)
        prices = data['latest_prices']
        predictions = data['latest_predictions']
        metrics = data['metrics']
    except FileNotFoundError:
        return f"> _Run `./update_gold.sh` to generate analysis (last attempted: {now})_\n"

    gold_eur = prices['gold_eur_gram']
    gold_usd = prices['gold_usd_oz']
    brent = prices['brent_usd']
    eurusd = prices['eurusd']

    p3 = predictions.get('3m', {})
    p6 = predictions.get('6m', {})
    p12 = predictions.get('12m', {})

    section = f"""### Updated: {now}

**Current Market Snapshot**

| Metric | Value |
|--------|-------|
| Gold (EUR/g) | **{gold_eur:.1f}** |
| Gold (USD/oz) | **${gold_usd:,.0f}** |
| Brent Oil | **${brent:.0f}/bbl** |
| EUR/USD | **{eurusd:.3f}** |
| Portfolio held | **{config.PORTFOLIO_HELD:,}** |
| Cash available | **{config.PORTFOLIO_AVAILABLE:,}** |

**Model Predictions (gold EUR/g)**

| Horizon | Mean | 25th-75th %ile | P(above current) |
|---------|------|----------------|-------------------|
| 3 months | {p3.get('mean', '?'):.1f} | {p3.get('p25', '?'):.1f} - {p3.get('p75', '?'):.1f} | {p3.get('prob_above_current', 0):.0%} |
| 6 months | {p6.get('mean', '?'):.1f} | {p6.get('p25', '?'):.1f} - {p6.get('p75', '?'):.1f} | {p6.get('prob_above_current', 0):.0%} |
| 12 months | {p12.get('mean', '?'):.1f} | {p12.get('p25', '?'):.1f} - {p12.get('p75', '?'):.1f} | {p12.get('prob_above_current', 0):.0%} |

**Key Recommendations**

| Scenario | Action | Detail |
|----------|--------|--------|
| Ceasefire collapses | WAIT | Don't chase spike; buy the 2-4 week pullback |
| Stalemate continues | DCA | Invest 1/3 of available cash per month on dips |
| De-escalation / peace | BUY | Deploy cash aggressively on the dip |
| Wider regional war | SELL | Take profits above ~20% gain; redeploy on pullback |
"""

    # Add model performance if available
    if metrics.get('n_validated', 0) > 0:
        section += f"""
**Model Performance** ({metrics['n_validated']} predictions validated)

| Metric | Value |
|--------|-------|
| Mean Absolute Error | {metrics['mean_abs_error_pct']:.1f}% |
| Within IQR | {metrics['pct_within_iqr']:.0f}% |
| Directional Accuracy | {metrics['directional_accuracy_pct']:.0f}% |
"""
    else:
        section += f"\n> _Model validation pending — predictions will be checked after 3+ months of tracking._\n"

    return section


def generate_exec_summary():
    """Executive-summary strategy table from MC results, ranked by expected return."""
    if not os.path.exists(MC_REPORT):
        return None

    with open(MC_REPORT) as f:
        mc = json.load(f)
    s = mc['strategies']
    if not s:
        return None

    # Rank all strategies by expected return (descending)
    ranked = sorted(s.items(), key=lambda kv: -kv[1]['expected_return'])

    lines = [
        "The full menu — **buy more, hold, DCA, or sell some/all?** — evaluated across every strategy, ranked by expected return:",
        "",
        "| Rank | Strategy | Expected | Worst 5% | Best 5% | P(Loss) |",
        "|------|----------|----------|----------|---------|---------|",
    ]
    for i, (name, v) in enumerate(ranked):
        rank = f"**#{i+1} (model pick)**" if i == 0 else f"#{i+1}"
        lines.append(
            f"| {rank} | **{name}** | {v['expected_return']:+.1f}% | "
            f"{v['p5_return']:+.1f}% | {v['p95_return']:+.1f}% | {v['p_loss']:.0f}% |"
        )

    top_name = ranked[0][0]
    top_exp = ranked[0][1]['expected_return']

    body = "\n".join(lines)

    note = f"""
> _Re-generated each time `./update_gold.sh` runs. Inputs are informed estimates (not fitted from data) — treat these as structured thinking, not precise predictions._

**Model's top pick right now: `{top_name}` at {top_exp:+.1f}% expected return.**

**Cash earns {config.CASH_ANNUAL_INTEREST:.0%} annual interest** in this model (ECB deposit rate). Sell All and Sell Half returns include this.

**Important sensitivities the model can't tell you about:**

1. **Tax (Germany):** Selling the gold ETC after a 1-year hold is tax-free (Spekulationsfrist); selling before the year is up triggers full income tax. This tips Sell All toward favourable or unfavourable depending on your hold period — the model treats selling as frictionless.
2. **Behavioural:** "Sell now, buy back on a dip" is one of the most reliable ways retail investors underperform — the dip either doesn't come or gets missed. A written rule ("buy back when gold drops below €X/g") helps.
3. **Input uncertainty:** the ranking is highly sensitive to `INITIAL_STATE_PROBS` and the state-conditional return means in `config.py`. If you think the current geopolitical mix is more benign (e.g., more DETENTE, less ESCALATION), the buy-and-hold strategies' expected returns rise. Edit `config.py` and re-run to see."""

    return body + note


def update_decision_history():
    """Append current run's key results to decision_history.json."""
    if not os.path.exists(MC_REPORT) or not os.path.exists(METRICS_FILE):
        return

    with open(MC_REPORT) as f:
        mc = json.load(f)
    with open(METRICS_FILE) as f:
        metrics = json.load(f)

    strategies = mc.get('strategies', {})
    prices = metrics.get('latest_prices', {})
    gold_eur = prices.get('gold_eur_gram', 0)
    today = datetime.now().strftime('%Y-%m-%d')

    # Determine winning strategy (highest expected return)
    if strategies:
        winner = max(strategies.items(), key=lambda kv: kv[1]['expected_return'])
        winner_name = winner[0]
    else:
        return

    # 12-month projected portfolio values for the three key scenarios
    invest = strategies.get('All In Now', {})
    sell = strategies.get('Sell All Now', {})
    hold = strategies.get('Hold Current', {})

    entry = {
        'date': today,
        'gold_eur_gram': round(gold_eur, 1),
        'gold_usd_oz': round(prices.get('gold_usd_oz', 0), 0),
        'winner': winner_name,
        'invest_3k_expected_pct': invest.get('expected_return', 0),
        'sell_all_expected_pct': sell.get('expected_return', 0),
        'hold_expected_pct': hold.get('expected_return', 0),
        'invest_3k_p5_pct': invest.get('p5_return', 0),
        'sell_all_p5_pct': sell.get('p5_return', 0),
        'hold_p5_pct': hold.get('p5_return', 0),
    }

    # Load existing history
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            history = json.load(f)

    # Skip if we already have an entry for today
    if history and history[-1].get('date') == today:
        history[-1] = entry  # update today's entry
    else:
        history.append(entry)

    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

    print(f"  Decision history updated ({len(history)} entries)")


def generate_decision_history():
    """Generate the decision history markdown table for README."""
    if not os.path.exists(HISTORY_FILE):
        return None

    with open(HISTORY_FILE) as f:
        history = json.load(f)

    if not history:
        return None

    cash_rate = config.CASH_ANNUAL_INTEREST

    lines = [
        f"Each row is one `./update_gold.sh` run. Cash earns **{cash_rate:.0%}/year** in all strategies.",
        f"12-month expected return shown for three decisions with your current portfolio "
        f"(held: {config.PORTFOLIO_HELD:,}, available: {config.PORTFOLIO_AVAILABLE:,}).",
        "",
        "| Date | Gold (EUR/g) | Best Strategy | Invest All | Hold | Sell All |",
        "|------|-------------|---------------|------------|------|----------|",
    ]

    for e in history:
        lines.append(
            f"| {e['date']} | {e['gold_eur_gram']:.1f} | **{e['winner']}** | "
            f"{e['invest_3k_expected_pct']:+.1f}% | "
            f"{e['hold_expected_pct']:+.1f}% | "
            f"{e['sell_all_expected_pct']:+.1f}% |"
        )

    return "\n".join(lines)


def update_readme():
    """Update the README.md with the latest bottom line and exec summary."""
    if not os.path.exists(README_PATH):
        print(f"  README.md not found at {README_PATH}, skipping update")
        return

    with open(README_PATH) as f:
        content = f.read()

    # Update bottom line
    if START_MARKER in content and END_MARKER in content:
        before = content.split(START_MARKER)[0]
        after = content.split(END_MARKER)[1]
        bottom_line = generate_bottom_line()
        content = f"{before}{START_MARKER}\n\n{bottom_line}\n{END_MARKER}{after}"

    # Update exec summary table
    if EXEC_START in content and EXEC_END in content:
        exec_section = generate_exec_summary()
        if exec_section:
            before = content.split(EXEC_START)[0]
            after = content.split(EXEC_END)[1]
            content = f"{before}{EXEC_START}\n\n{exec_section}\n\n{EXEC_END}{after}"

    # Update decision history
    if HISTORY_START in content and HISTORY_END in content:
        history_section = generate_decision_history()
        if history_section:
            before = content.split(HISTORY_START)[0]
            after = content.split(HISTORY_END)[1]
            content = f"{before}{HISTORY_START}\n\n{history_section}\n\n{HISTORY_END}{after}"

    with open(README_PATH, 'w') as f:
        f.write(content)

    print("  README.md updated")


if __name__ == '__main__':
    update_decision_history()
    update_readme()
