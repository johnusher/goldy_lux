#!/usr/bin/env python3
"""
Monte Carlo Simulation for Gold ETF Strategy Comparison
========================================================
Uses the Markov transition model from the scenario tree
to run 50,000 simulated paths and evaluate strategies rigorously.
"""

import os
import sys
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
warnings.filterwarnings('ignore')

# Import project config
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import config

os.makedirs(config.OUTPUT_DIR, exist_ok=True)

try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False

np.random.seed(42)

# =============================================================================
# MARKOV MODEL PARAMETERS (from config)
# =============================================================================

STATES = config.STATES
STATE_LABELS = config.STATE_LABELS
STATE_COLORS = config.STATE_COLORS

TRANS = config.TRANSITION_MATRIX
INITIAL_STATE_PROBS = config.INITIAL_STATE_PROBS
RETURNS = config.GOLD_EUR_RETURNS

# Portfolio parameters (from config)
HELD_EUR = float(config.PORTFOLIO_HELD)
AVAILABLE_EUR = float(config.PORTFOLIO_AVAILABLE)
CURRENT_GOLD_EUR_GRAM = config.CURRENT_GOLD_EUR_GRAM

N_SIMULATIONS = config.N_SIMULATIONS
N_QUARTERS = config.N_QUARTERS


# =============================================================================
# MONTE CARLO ENGINE
# =============================================================================

def simulate_paths(n_sim=N_SIMULATIONS, n_quarters=N_QUARTERS):
    """Simulate n_sim paths through the Markov chain."""

    # State trajectories: shape (n_sim, n_quarters+1)
    states = np.zeros((n_sim, n_quarters + 1), dtype=int)

    # Sample initial states
    states[:, 0] = np.random.choice(5, size=n_sim, p=INITIAL_STATE_PROBS)

    # Quarterly gold returns: shape (n_sim, n_quarters)
    gold_returns = np.zeros((n_sim, n_quarters))

    for q in range(n_quarters):
        for s in range(5):
            mask = states[:, q] == s
            n = mask.sum()
            if n == 0:
                continue

            # Sample next states
            states[mask, q + 1] = np.random.choice(5, size=n, p=TRANS[s])

        # Sample gold returns based on the NEW state (state determines environment)
        for s in range(5):
            mask = states[:, q + 1] == s
            n = mask.sum()
            if n == 0:
                continue
            mean, std = RETURNS[STATES[s]]
            gold_returns[mask, q] = np.random.normal(mean, std, size=n)

    # Cumulative gold price factor at each quarter
    # gold_factor[i, q] = cumulative return from time 0 to end of quarter q
    gold_factors = np.cumprod(1 + gold_returns, axis=1)

    return states, gold_returns, gold_factors


# =============================================================================
# STRATEGY DEFINITIONS
# =============================================================================

def evaluate_strategies(states, gold_returns, gold_factors):
    """Evaluate multiple investment strategies against simulated paths."""

    n_sim = states.shape[0]
    results = {}

    # --- Strategy 1: HOLD CURRENT ---
    # Keep €3k in gold, €3k in cash. No trades.
    gold_val = HELD_EUR * gold_factors[:, -1]
    cash_val = np.full(n_sim, AVAILABLE_EUR)
    results['Hold Current\n(€3k gold + €3k cash)'] = gold_val + cash_val

    # --- Strategy 2: ALL IN NOW ---
    # Invest full €6k immediately
    total = (HELD_EUR + AVAILABLE_EUR)
    results['All In Now\n(€6k gold)'] = total * gold_factors[:, -1]

    # --- Strategy 3: DCA QUARTERLY ---
    # €3k in gold now, invest €750 each quarter for 4 quarters
    dca_amount = AVAILABLE_EUR / N_QUARTERS  # €750
    gold_holdings = np.full(n_sim, HELD_EUR)
    cash_remaining = np.full(n_sim, AVAILABLE_EUR)

    for q in range(N_QUARTERS):
        # Invest dca_amount at beginning of quarter
        # Gold price has changed by gold_factors[:, q-1] if q > 0
        if q == 0:
            factor_at_buy = 1.0
        else:
            factor_at_buy = gold_factors[:, q - 1]

        # Convert EUR to "gold units" at current price, then track value
        units_bought = dca_amount / factor_at_buy  # effective units
        gold_holdings += units_bought * factor_at_buy  # add at current gold value
        cash_remaining -= dca_amount

    # Final gold value
    final_gold_dca = HELD_EUR * gold_factors[:, -1]
    # DCA portions: each quarter's investment grows by the remaining factors
    for q in range(N_QUARTERS):
        if q == 0:
            dca_growth = gold_factors[:, -1]
        else:
            dca_growth = gold_factors[:, -1] / gold_factors[:, q - 1]
        final_gold_dca += dca_amount * dca_growth

    results['DCA Quarterly\n(€3k now + €750/q)'] = final_gold_dca

    # --- Strategy 4: BUY THE DIP ---
    # Keep €3k in gold. Deploy €3k only when gold drops >7% at any quarterly checkpoint.
    # If never dips, stay in cash.
    dip_threshold = -0.07
    bought = np.zeros(n_sim, dtype=bool)
    buy_quarter = np.full(n_sim, -1)

    for q in range(N_QUARTERS):
        factor = gold_factors[:, q]
        # Check if gold has dropped > threshold from initial
        dipped = (factor - 1.0) < dip_threshold
        new_buys = dipped & ~bought
        bought |= new_buys
        buy_quarter[new_buys] = q

    final_held = HELD_EUR * gold_factors[:, -1]
    final_deployed = np.zeros(n_sim)

    for q in range(N_QUARTERS):
        mask = buy_quarter == q
        if mask.sum() > 0:
            # Growth from buy point to end
            remaining_growth = gold_factors[mask, -1] / gold_factors[mask, q]
            final_deployed[mask] = AVAILABLE_EUR * remaining_growth

    # For those who never bought, cash stays
    never_bought = buy_quarter == -1
    final_deployed[never_bought] = AVAILABLE_EUR

    results['Buy the Dip\n(deploy €3k on -7%)'] = final_held + final_deployed

    # --- Strategy 5: SELL ALL NOW ---
    # Sell existing €3k, hold €6k cash
    results['Sell All Now\n(€6k cash)'] = np.full(n_sim, HELD_EUR + AVAILABLE_EUR)

    # --- Strategy 6: TACTICAL ---
    # Start with €3k gold. At each quarter:
    # - If state is PEACE or DETENTE: deploy remaining cash
    # - If state is REGIONAL_WAR: sell gold position
    gold_pos = np.full(n_sim, HELD_EUR)
    cash_pos = np.full(n_sim, AVAILABLE_EUR)
    deployed_tactical = np.zeros(n_sim, dtype=bool)
    sold_tactical = np.zeros(n_sim, dtype=bool)

    for q in range(N_QUARTERS):
        state = states[:, q + 1]

        # Buy signal: PEACE(0) or DETENTE(1)
        buy_signal = ((state == 0) | (state == 1)) & ~deployed_tactical & ~sold_tactical
        if buy_signal.sum() > 0:
            # Deploy cash into gold at current price
            if q == 0:
                buy_factor = 1.0
            else:
                buy_factor = gold_factors[buy_signal, q - 1] if q > 0 else 1.0

            deployed_tactical[buy_signal] = True
            # Mark that this cash is now in gold from this point

        # Sell signal: REGIONAL_WAR(4)
        sell_signal = (state == 4) & ~sold_tactical
        if sell_signal.sum() > 0:
            sold_tactical[sell_signal] = True

    # Compute final values
    tactical_final = np.zeros(n_sim)

    for i in range(n_sim):
        gold_val_i = HELD_EUR * gold_factors[i, -1]

        if sold_tactical[i]:
            # Find when sold
            sell_q = None
            for q in range(N_QUARTERS):
                if states[i, q + 1] == 4 and sell_q is None:
                    sell_q = q
                    break
            if sell_q is not None:
                gold_val_i = HELD_EUR * gold_factors[i, sell_q]  # value at sale time

        cash_val_i = AVAILABLE_EUR
        if deployed_tactical[i]:
            # Find when deployed
            deploy_q = None
            for q in range(N_QUARTERS):
                if states[i, q + 1] in [0, 1] and deploy_q is None:
                    deploy_q = q
                    break
            if deploy_q is not None:
                if sold_tactical[i]:
                    # Also sold later — cash out the deployed amount too
                    sell_q_val = None
                    for q in range(deploy_q + 1, N_QUARTERS):
                        if states[i, q + 1] == 4:
                            sell_q_val = q
                            break
                    if sell_q_val is not None:
                        cash_val_i = AVAILABLE_EUR * gold_factors[i, sell_q_val] / (gold_factors[i, deploy_q] if deploy_q > 0 else 1.0)
                    else:
                        cash_val_i = AVAILABLE_EUR * gold_factors[i, -1] / (gold_factors[i, deploy_q] if deploy_q > 0 else 1.0)
                else:
                    growth = gold_factors[i, -1] / (gold_factors[i, deploy_q] if deploy_q > 0 else 1.0)
                    cash_val_i = AVAILABLE_EUR * growth

        tactical_final[i] = gold_val_i + cash_val_i

    results['Tactical\n(buy peace, sell war)'] = tactical_final

    return results


# =============================================================================
# VISUALIZATION
# =============================================================================

def plot_strategy_distributions(results):
    """Create violin + box plots for strategy comparison."""

    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.6, 0.4],
        subplot_titles=['Portfolio Value Distribution at 12 Months',
                        'Risk-Return Profile'],
        vertical_spacing=0.15,
    )

    strategies = list(results.keys())
    initial_capital = HELD_EUR + AVAILABLE_EUR

    # Violin plots
    for i, (name, values) in enumerate(results.items()):
        fig.add_trace(go.Violin(
            y=values,
            name=name.replace('\n', ' '),
            box_visible=True,
            meanline_visible=True,
            line_color=STATE_COLORS[i % len(STATE_COLORS)],
            fillcolor=f"rgba({int(STATE_COLORS[i % len(STATE_COLORS)][1:3], 16)}, "
                      f"{int(STATE_COLORS[i % len(STATE_COLORS)][3:5], 16)}, "
                      f"{int(STATE_COLORS[i % len(STATE_COLORS)][5:7], 16)}, 0.3)",
            showlegend=False,
        ), row=1, col=1)

    # Reference line
    fig.add_hline(y=initial_capital, line_dash="dash", line_color="gray",
                  annotation_text=f"Initial: €{initial_capital:,.0f}", row=1, col=1)

    # Risk-return scatter
    for i, (name, values) in enumerate(results.items()):
        expected_return = (np.mean(values) / initial_capital - 1) * 100
        volatility = np.std(values) / initial_capital * 100
        p5 = np.percentile(values, 5)
        max_loss = (p5 / initial_capital - 1) * 100

        fig.add_trace(go.Scatter(
            x=[volatility],
            y=[expected_return],
            mode='markers+text',
            name=name.replace('\n', ' '),
            text=[name.split('\n')[0]],
            textposition='top center',
            marker=dict(
                size=20,
                color=STATE_COLORS[i % len(STATE_COLORS)],
                line=dict(width=2, color='white'),
            ),
            showlegend=False,
        ), row=2, col=1)

    fig.update_layout(
        title=dict(
            text="<b>Monte Carlo Strategy Analysis: 50,000 Simulated Paths</b><br>"
                 "<sup>iShares Physical Gold ETC | Markov chain with 5 geopolitical states</sup>",
            font=dict(size=16),
        ),
        width=1100,
        height=900,
        plot_bgcolor='white',
        paper_bgcolor='#FAFAFA',
    )

    fig.update_yaxes(title_text="Portfolio Value (EUR)", row=1, col=1)
    fig.update_yaxes(title_text="Expected Return (%)", row=2, col=1)
    fig.update_xaxes(title_text="Volatility (%)", row=2, col=1)

    return fig


def plot_simulated_paths(gold_factors, states, n_show=200):
    """Plot a sample of simulated gold price paths, colored by final state."""

    fig = go.Figure()

    months = [0, 3, 6, 9, 12]
    sample_idx = np.random.choice(len(gold_factors), size=min(n_show, len(gold_factors)), replace=False)

    # Group by final state for coloring
    for s in range(5):
        mask = states[sample_idx, -1] == s
        indices = sample_idx[mask]

        for idx in indices:
            path = np.concatenate([[1.0], gold_factors[idx]])
            gold_eur = CURRENT_GOLD_EUR_GRAM * path

            fig.add_trace(go.Scatter(
                x=months,
                y=gold_eur,
                mode='lines',
                line=dict(color=STATE_COLORS[s], width=0.5),
                opacity=0.15,
                showlegend=False,
                hoverinfo='skip',
            ))

    # Add percentile bands
    all_paths = np.column_stack([np.ones(len(gold_factors)), gold_factors]) * CURRENT_GOLD_EUR_GRAM

    for pct, label, dash in [(5, '5th %ile', 'dot'), (25, '25th', 'dash'),
                              (50, 'Median', 'solid'),
                              (75, '75th', 'dash'), (95, '95th %ile', 'dot')]:
        percentile_path = np.percentile(all_paths, pct, axis=0)
        fig.add_trace(go.Scatter(
            x=months,
            y=percentile_path,
            mode='lines',
            name=f'{label}',
            line=dict(color='black', width=2, dash=dash),
        ))

    # State probability annotations at right edge
    final_states = states[:, -1]
    for s in range(5):
        pct = (final_states == s).mean()
        if pct > 0.01:
            # Average gold price in this final state
            mask = final_states == s
            avg_price = (CURRENT_GOLD_EUR_GRAM * gold_factors[mask, -1]).mean()
            fig.add_annotation(
                x=12.3,
                y=avg_price,
                text=f"<b>{STATE_LABELS[s]}</b><br>{pct:.0%}",
                showarrow=True,
                arrowhead=2,
                arrowcolor=STATE_COLORS[s],
                font=dict(size=10, color=STATE_COLORS[s]),
                bgcolor='rgba(255,255,255,0.8)',
                bordercolor=STATE_COLORS[s],
            )

    fig.add_hline(y=CURRENT_GOLD_EUR_GRAM, line_dash="dash", line_color="gray",
                  annotation_text=f"Current: €{CURRENT_GOLD_EUR_GRAM:.0f}/g")

    fig.update_layout(
        title=dict(
            text="<b>Monte Carlo Simulated Gold Price Paths (EUR/gram)</b><br>"
                 "<sup>200 sample paths colored by final geopolitical state | "
                 "Black lines show percentile bands</sup>",
            font=dict(size=14),
        ),
        xaxis=dict(
            tickvals=months,
            ticktext=['Now', '+3m', '+6m', '+9m', '+12m'],
            title='Timeline',
        ),
        yaxis_title='Gold Price (EUR/gram)',
        width=1100,
        height=700,
        plot_bgcolor='white',
        paper_bgcolor='#FAFAFA',
        legend=dict(x=0.01, y=0.99),
    )

    return fig


def plot_historical_context():
    """Plot historical gold ETC prices with conflict events."""

    if not HAS_YF:
        return None

    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.65, 0.35],
        shared_xaxes=True,
        subplot_titles=['iShares Physical Gold ETC (PPFB.DE)', 'Brent Crude Oil (BZ=F)'],
        vertical_spacing=0.08,
    )

    # Gold ETC
    for ticker, name, row in [('PPFB.DE', 'Gold ETC (EUR)', 1), ('BZ=F', 'Brent Oil (USD)', 2)]:
        try:
            df = yf.download(ticker, period='2y', progress=False)
            if len(df) > 0:
                color = '#FFB300' if row == 1 else '#1565C0'
                fig.add_trace(go.Scatter(
                    x=df.index,
                    y=df['Close'].values.flatten() if hasattr(df['Close'], 'values') else df['Close'],
                    mode='lines',
                    name=name,
                    line=dict(color=color, width=2),
                ), row=row, col=1)
        except:
            pass

    # Add conflict event markers
    events = [
        ('2026-01-29', 'Gold >$5,500\nIran tensions', '#FFB300'),
        ('2026-02-28', 'US-Israel strikes\non Iran', '#E74C3C'),
        ('2026-03-12', 'Strait of Hormuz\nclosed', '#C0392B'),
        ('2026-03-31', 'Gold worst month\nsince 2008', '#FF6600'),
        ('2026-04-12', 'US-Iran talks\nno deal', '#F39C12'),
        ('2026-04-17', 'Strait partially\nreopened', '#27AE60'),
        ('2026-04-20', 'Ship seized,\nceasefire brink', '#E74C3C'),
    ]

    for date_str, label, color in events:
        try:
            for row in [1, 2]:
                fig.add_vline(
                    x=date_str, line_dash="dot", line_color=color,
                    opacity=0.5, row=row, col=1,
                )
            fig.add_annotation(
                x=date_str, y=1.02, yref='paper',
                text=label, showarrow=False,
                font=dict(size=8, color=color),
                textangle=-45,
            )
        except:
            pass

    fig.update_layout(
        title=dict(
            text="<b>Historical Context: Gold ETC & Oil During US-Iran Conflict</b><br>"
                 "<sup>Key: Gold has NOT acted as safe haven — oil shock dynamics dominate</sup>",
            font=dict(size=14),
        ),
        width=1100,
        height=700,
        plot_bgcolor='white',
        paper_bgcolor='#FAFAFA',
        showlegend=True,
        legend=dict(x=0.01, y=0.98),
    )

    fig.update_yaxes(title_text="EUR per share", row=1, col=1)
    fig.update_yaxes(title_text="USD per barrel", row=2, col=1)

    return fig


def plot_optimal_timing(gold_factors):
    """Analyze and visualize optimal buy/sell timing."""

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=[
            'Expected Return by Entry Point',
            'Probability of Profit by Holding Period'
        ],
    )

    # Panel 1: If you buy at month X, what's your expected return at month 12?
    months = [0, 3, 6, 9]
    month_labels = ['Now', '+3m', '+6m', '+9m']
    expected_returns = []
    p25_returns = []
    p75_returns = []

    for q in range(4):
        if q == 0:
            returns = gold_factors[:, -1] - 1
        else:
            returns = gold_factors[:, -1] / gold_factors[:, q - 1] - 1
        expected_returns.append(np.mean(returns) * 100)
        p25_returns.append(np.percentile(returns, 25) * 100)
        p75_returns.append(np.percentile(returns, 75) * 100)

    fig.add_trace(go.Bar(
        x=month_labels,
        y=expected_returns,
        name='Expected Return',
        marker_color='#3498DB',
        error_y=dict(
            type='data',
            symmetric=False,
            array=[p75 - exp for exp, p75 in zip(expected_returns, p75_returns)],
            arrayminus=[exp - p25 for exp, p25 in zip(expected_returns, p25_returns)],
            color='#555',
        ),
        text=[f"{r:+.1f}%" for r in expected_returns],
        textposition='outside',
    ), row=1, col=1)

    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=1, col=1)

    # Panel 2: Probability of being profitable
    holding_periods = [1, 2, 3, 4]
    holding_labels = ['3 months', '6 months', '9 months', '12 months']

    prob_profit = []
    for h in holding_periods:
        if h == 1:
            ret = gold_factors[:, 0]
        else:
            ret = gold_factors[:, h - 1]
        prob_profit.append((ret > 1.0).mean() * 100)

    fig.add_trace(go.Bar(
        x=holding_labels,
        y=prob_profit,
        name='P(Profit)',
        marker_color=['#E74C3C' if p < 50 else '#F39C12' if p < 55 else '#27AE60' for p in prob_profit],
        text=[f"{p:.0f}%" for p in prob_profit],
        textposition='outside',
    ), row=1, col=2)

    fig.add_hline(y=50, line_dash="dash", line_color="gray",
                  annotation_text="50% (coin flip)", row=1, col=2)

    fig.update_layout(
        title=dict(
            text="<b>Optimal Entry Timing Analysis</b><br>"
                 "<sup>Based on 50,000 Monte Carlo simulations | Error bars = 25th-75th percentile</sup>",
            font=dict(size=14),
        ),
        width=1100,
        height=500,
        plot_bgcolor='white',
        paper_bgcolor='#FAFAFA',
        showlegend=False,
    )

    fig.update_yaxes(title_text="Expected Return (%)", row=1, col=1)
    fig.update_yaxes(title_text="Probability of Profit (%)", row=1, col=2)

    return fig


def print_summary(results):
    """Print summary statistics for all strategies."""

    initial = HELD_EUR + AVAILABLE_EUR
    print("\n" + "=" * 90)
    print("MONTE CARLO STRATEGY COMPARISON — 50,000 Simulated Paths")
    print("=" * 90)

    header = (f"{'Strategy':<30} {'E[Value]':>9} {'E[Ret]':>7} {'Median':>9} "
              f"{'P5':>9} {'P95':>9} {'P(Loss)':>7} {'Sharpe':>7}")
    print(header)
    print("-" * 90)

    best_strategy = None
    best_sharpe = -999

    for name, values in results.items():
        display_name = name.replace('\n', ' ')
        if len(display_name) > 28:
            display_name = display_name[:28]

        ev = np.mean(values)
        med = np.median(values)
        p5 = np.percentile(values, 5)
        p95 = np.percentile(values, 95)
        ret = (ev / initial - 1) * 100
        p_loss = (values < initial).mean() * 100
        sharpe = (ev - initial) / np.std(values) if np.std(values) > 0 else 0

        if sharpe > best_sharpe:
            best_sharpe = sharpe
            best_strategy = name.split('\n')[0]

        marker = " ★" if sharpe == best_sharpe else ""

        print(f"{display_name:<30} €{ev:>7,.0f} {ret:>+5.1f}% €{med:>7,.0f} "
              f"€{p5:>7,.0f} €{p95:>7,.0f} {p_loss:>5.1f}% {sharpe:>6.3f}{marker}")

    print("-" * 90)
    print(f"\n★ Best risk-adjusted strategy: {best_strategy}")
    print(f"  (Highest Sharpe ratio = excess return per unit of risk)")

    # Key insights
    all_in = results['All In Now\n(€6k gold)']
    hold = results['Hold Current\n(€3k gold + €3k cash)']
    dca = results['DCA Quarterly\n(€3k now + €750/q)']

    print(f"\nKEY INSIGHTS:")
    print(f"  • All-In expected: €{np.mean(all_in):,.0f} ({(np.mean(all_in)/initial-1)*100:+.1f}%)")
    print(f"    but 5th percentile: €{np.percentile(all_in, 5):,.0f} "
          f"({(np.percentile(all_in, 5)/initial-1)*100:+.1f}%) — significant downside risk")
    print(f"  • Hold Current expected: €{np.mean(hold):,.0f} — cash cushion limits downside")
    print(f"    worst 5%: €{np.percentile(hold, 5):,.0f} vs All-In worst 5%: €{np.percentile(all_in, 5):,.0f}")
    print(f"  • DCA smooths entry: median €{np.median(dca):,.0f}, less sensitive to timing")
    print(f"  • P(gold up in 12m): {(np.mean(all_in) > initial)*100:.0f}% in expectation, "
          f"but {(all_in > initial).mean()*100:.0f}% of simulations")

    # Regime probabilities at 12 months
    return best_strategy


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("Running Monte Carlo simulation (50,000 paths × 4 quarters)...")
    states, gold_returns, gold_factors = simulate_paths()

    print("Evaluating strategies...")
    results = evaluate_strategies(states, gold_returns, gold_factors)

    best = print_summary(results)

    # State distribution at 12 months
    print(f"\nFINAL STATE DISTRIBUTION (12 months):")
    final_states = states[:, -1]
    for s in range(5):
        pct = (final_states == s).mean()
        avg_ret = (gold_factors[final_states == s, -1].mean() - 1) * 100 if (final_states == s).sum() > 0 else 0
        print(f"  {STATE_LABELS[s]:<20} {pct:>5.1%}  (avg gold return: {avg_ret:+.1f}%)")

    # Save summary JSON for README auto-update
    initial = HELD_EUR + AVAILABLE_EUR
    summary_data = {'strategies': {}}
    strategy_name_map = {
        'Hold Current\n(€3k gold + €3k cash)': 'Hold Current',
        'All In Now\n(€6k gold)': 'All In Now',
        'DCA Quarterly\n(€3k now + €750/q)': 'DCA Quarterly',
        'Buy the Dip\n(deploy €3k on -7%)': 'Buy the Dip',
        'Sell All Now\n(€6k cash)': 'Sell All Now',
        'Tactical\n(buy peace, sell war)': 'Tactical',
    }
    for name, values in results.items():
        short = strategy_name_map.get(name, name.split('\n')[0])
        summary_data['strategies'][short] = {
            'expected_value': round(float(np.mean(values)), 0),
            'expected_return': round(float((np.mean(values) / initial - 1) * 100), 1),
            'p5_return': round(float((np.percentile(values, 5) / initial - 1) * 100), 1),
            'p95_return': round(float((np.percentile(values, 95) / initial - 1) * 100), 1),
            'p_loss': round(float((values < initial).mean() * 100), 1),
        }

    import json as _json
    with open(os.path.join(config.OUTPUT_DIR, 'mc_summary.json'), 'w') as f:
        _json.dump(summary_data, f, indent=2)
    print("  mc_summary.json saved")

    print("\nGenerating visualizations...")

    out = config.OUTPUT_DIR
    figs = {
        'mc_strategy_analysis': plot_strategy_distributions(results),
        'mc_simulated_paths': plot_simulated_paths(gold_factors, states),
        'mc_optimal_timing': plot_optimal_timing(gold_factors),
    }

    fig_hist = plot_historical_context()
    if fig_hist:
        figs['historical_context'] = fig_hist

    for name, fig in figs.items():
        fig.write_html(os.path.join(out, f'{name}.html'), include_plotlyjs='cdn')
        print(f"  {name}.html")

    try:
        for name, fig in figs.items():
            fig.write_image(os.path.join(out, f'{name}.png'), scale=2)
        print("  PNG images saved")
    except Exception as e:
        print(f"  Note: PNG export skipped ({e})")

    print("  All Monte Carlo outputs generated.")


if __name__ == '__main__':
    main()
