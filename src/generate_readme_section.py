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

START_MARKER = '<!-- BOTTOM_LINE_START -->'
END_MARKER = '<!-- BOTTOM_LINE_END -->'


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


def update_readme():
    """Update the README.md with the latest bottom line section."""
    if not os.path.exists(README_PATH):
        print(f"  README.md not found at {README_PATH}, skipping update")
        return

    with open(README_PATH) as f:
        content = f.read()

    if START_MARKER not in content or END_MARKER not in content:
        print("  Markers not found in README.md — cannot update bottom line")
        return

    before = content.split(START_MARKER)[0]
    after = content.split(END_MARKER)[1]

    bottom_line = generate_bottom_line()
    new_content = f"{before}{START_MARKER}\n\n{bottom_line}\n{END_MARKER}{after}"

    with open(README_PATH, 'w') as f:
        f.write(new_content)

    print("  README.md bottom line updated")


if __name__ == '__main__':
    update_readme()
