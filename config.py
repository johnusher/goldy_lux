"""
GOLDY-LUX Configuration
========================
Adjust these values to match YOUR portfolio and preferences.
The two most important settings are right at the top.
"""
import os
import numpy as np

# =====================================================================
# YOUR PORTFOLIO — Change these to match your situation
# =====================================================================

# How much you currently have invested in gold ETF (EUR)
PORTFOLIO_HELD = 7000

# How much additional cash you have available to invest (EUR)
PORTFOLIO_AVAILABLE = 3000

# =====================================================================
# YOUR ETF — Which gold ETC/ETF you trade
# =====================================================================

ETF_TICKER = "PPFB.DE"         # iShares Physical Gold ETC on Xetra
ETF_NAME = "iShares Physical Gold ETC"
ETF_FALLBACK_TICKERS = ["IGLN.L", "4GLD.DE", "GC=F"]

# =====================================================================
# CURRENT MARKET SNAPSHOT (auto-updated each run, these are fallbacks)
# =====================================================================

CURRENT_GOLD_USD_OZ = 4186.0   # USD per troy ounce (2026-06-22)
CURRENT_BRENT = 78.0           # USD per barrel (Brent, post-ceasefire ~$75-82)
CURRENT_EURUSD = 1.146         # EUR/USD exchange rate (dollar at 1-yr high, hawkish Fed)
CURRENT_GOLD_EUR_GRAM = CURRENT_GOLD_USD_OZ / CURRENT_EURUSD / 31.1035  # auto-derived (~€117/g)

# =====================================================================
# MODEL PARAMETERS — Adjust with caution
# =====================================================================

N_SIMULATIONS = 50_000         # Monte Carlo paths (more = slower but smoother)
N_QUARTERS = 4                 # Simulation horizon (4 = 12 months)

# Geopolitical states
STATES = ['PEACE', 'DETENTE', 'STALEMATE', 'ESCALATION', 'REGIONAL_WAR']

STATE_LABELS = [
    'Peace Deal', 'De-escalation', 'Stalemate', 'Escalation', 'Wider War'
]

STATE_COLORS = ['#27AE60', '#3498DB', '#F39C12', '#E74C3C', '#8E44AD']

# Quarterly Markov transition matrix
# Rows = "from" state, Columns = "to" state
# Each row sums to 1.0
TRANSITION_MATRIX = np.array([
    # To:   PEACE   DETENTE  STALEMATE  ESCALATION  REGIONAL_WAR
    [0.70,  0.20,   0.08,    0.02,      0.00],   # From PEACE
    [0.25,  0.45,   0.20,    0.08,      0.02],   # From DETENTE
    [0.05,  0.20,   0.45,    0.25,      0.05],   # From STALEMATE
    [0.02,  0.10,   0.25,    0.48,      0.15],   # From ESCALATION
    [0.00,  0.02,   0.10,    0.28,      0.60],   # From REGIONAL_WAR
])

# Current starting state — probabilistic blend
# 2026-06-22: US-Iran peace framework signed (Jun 18), Hormuz reopening, oil -36%
# from peak. De-escalation now dominant, but Geneva follow-up talks postponed
# (Jun 19) so it remains fragile -> DETENTE-led with residual STALEMATE/ESCALATION.
INITIAL_STATE_PROBS = np.array([0.10, 0.45, 0.35, 0.10, 0.00])

# Gold EUR quarterly returns by geopolitical state: (mean, std_dev)
# These incorporate gold-USD, EUR/USD, and central bank buying dynamics
GOLD_EUR_RETURNS = {
    'PEACE':        (-0.040, 0.050),   # Risk premium collapse
    'DETENTE':      (-0.010, 0.060),   # Gradual normalization
    'STALEMATE':    ( 0.015, 0.080),   # Range-bound, CB support
    'ESCALATION':   ( 0.030, 0.120),   # Safe haven vs real-yield headwind
    'REGIONAL_WAR': ( 0.100, 0.180),   # Systemic panic > macro headwinds
}

# =====================================================================
# SELL-OFF / TAIL RISK MODELING
# =====================================================================
# Choose which return model to use: "normal", "fat_tails", "liquidity_crisis", "both"
RETURN_MODEL = "both"

# --- Model B: Fat tails (Student's t-distribution) ---
# Degrees of freedom for Student's t. Lower = fatter tails.
# df=∞ → normal distribution; df=4-5 → realistic financial tails;
# df=3 → very fat (may be too aggressive)
T_DISTRIBUTION_DF = 4.5

# --- Model A: Liquidity crisis overlay ---
# Probability per quarter of a forced-selling cascade, conditional on state.
# Calibrated from: 2008 GFC (30% drawdown), March 2026 (25% drawdown),
# 2013 ETF liquidation. Only fires during stressed states.
LIQUIDITY_CRISIS_PROB = {
    'PEACE':        0.01,   # Very rare — no stress
    'DETENTE':      0.02,   # Low — improving conditions
    'STALEMATE':    0.04,   # Moderate — external shock possible
    'ESCALATION':   0.08,   # Elevated — margin calls from oil/equity stress
    'REGIONAL_WAR': 0.12,   # High — full correlation convergence risk
}

# When a liquidity crisis fires, gold drops sharply then partially recovers
# within the same quarter. Net quarterly return drawn from this distribution:
LIQUIDITY_CRISIS_RETURN = (-0.18, 0.06)  # (mean, std): avg -18%, std 6%

# Cash interest rate (annual). EUR cash in a savings/deposit account.
# ECB deposit rate ~3-4% as of April 2026; using 4% as user-specified.
CASH_ANNUAL_INTEREST = 0.04
CASH_QUARTERLY_INTEREST = (1 + CASH_ANNUAL_INTEREST) ** 0.25 - 1  # ~0.985% per quarter
# Calibrated from: March 2026 (-25% peak-to-trough, partial recovery to ~-15% net),
#                  2008 GFC (-30% drawdown, partial recovery),
#                  2013 (-15% net quarterly)

# =====================================================================
# PATHS — Derived automatically
# =====================================================================

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'output')
DOCS_DIR = os.path.join(PROJECT_ROOT, 'docs')
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
SRC_DIR = os.path.join(PROJECT_ROOT, 'src')
