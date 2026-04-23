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

START_MARKER = '<!-- BOTTOM_LINE_START -->'
END_MARKER = '<!-- BOTTOM_LINE_END -->'
EXEC_START = '<!-- EXEC_SUMMARY_START -->'
EXEC_END = '<!-- EXEC_SUMMARY_END -->'


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
    """Generate the executive summary strategy table from MC results."""
    if not os.path.exists(MC_REPORT):
        return None

    with open(MC_REPORT) as f:
        mc = json.load(f)

    s = mc['strategies']
    # Pick the three strategies we highlight
    a = s.get('All In Now', {})
    b = s.get('DCA Quarterly', {})
    c = s.get('Hold Current', {})

    if not a:
        return None

    return f"""Three options depending on your risk appetite:

| | If you... | Then... | Expected | Worst 5% |
|-|-----------|---------|----------|----------|
| **A** | Can stomach volatility | **All In Now** — invest remaining cash today | {a['expected_return']:+.1f}% | {a['p5_return']:+.1f}% |
| **B** | Want a smoother ride | **DCA Quarterly** — invest 1/4 of cash each quarter | {b['expected_return']:+.1f}% | {b['p5_return']:+.1f}% |
| **C** | Mainly want to avoid losses | **Hold Current** — keep cash on the side | {c['expected_return']:+.1f}% | {c['p5_return']:+.1f}% |

> _These numbers are re-generated each time `./update_gold.sh` runs. The figures above reflect the model's output at the time of the last update (see Bottom Line below for the latest). The model's inputs are rough estimates — treat these as structured thinking, not precise predictions._"""


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

    with open(README_PATH, 'w') as f:
        f.write(content)

    print("  README.md updated")


if __name__ == '__main__':
    update_readme()
