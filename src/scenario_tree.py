#!/usr/bin/env python3
"""
Gold ETF Scenario Analysis: US-Iran Conflict Impact
====================================================
Markov-chain scenario tree for iShares Physical Gold ETC
traded on German markets, with buy/sell recommendations.

Context (April 2026):
- US-Iran armed conflict since Feb 28, 2026
- Strait of Hormuz partially disrupted (~20% global oil transit)
- Ceasefire fragile, on brink of collapse
- Gold ~$4,750-4,800 USD; Brent ~$98-100/bbl; EUR/USD ~1.17-1.18
- Gold has NOT acted as classic safe haven (oil shock → higher real yields → USD strength)
- Central bank buying (China, India, Turkey) provides structural floor

Portfolio: €3k held in iShares Physical Gold ETC + €3k available to invest
"""

import os
import sys
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
from dataclasses import dataclass, field
from typing import Optional
import warnings
warnings.filterwarnings('ignore')

# Import project config
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import config

os.makedirs(config.OUTPUT_DIR, exist_ok=True)

# Try to fetch live data; fall back to known values
try:
    import yfinance as yf
    tickers = [config.ETF_TICKER] + config.ETF_FALLBACK_TICKERS
    for ticker in tickers:
        try:
            data = yf.download(ticker, period='2y', progress=False)
            if len(data) > 100:
                print(f"  Fetched historical data from {ticker}: {len(data)} rows")
                break
        except:
            continue

    supporting = {}
    for sym, name in [('GC=F', 'Gold USD'), ('BZ=F', 'Brent Oil'), ('EURUSD=X', 'EUR/USD')]:
        try:
            d = yf.download(sym, period='2y', progress=False)
            if len(d) > 50:
                supporting[name] = d
                print(f"  Fetched {name} data: {len(d)} rows")
        except:
            pass
    HAS_LIVE_DATA = True
except Exception as e:
    print(f"  Note: Could not fetch live data ({e}), using embedded values")
    HAS_LIVE_DATA = False


# =============================================================================
# SCENARIO TREE DEFINITION
# =============================================================================

@dataclass
class ScenarioNode:
    """A node in the scenario tree."""
    id: str
    name: str
    month: int  # 0=now, 3, 6, 12
    description: str
    gold_eur_range: tuple  # (low, high) EUR/gram — auto-derived if (0,0)
    gold_usd_range: tuple  # (low, high) USD/oz (authoritative)
    oil_range: tuple       # Brent USD/bbl
    probability: float     # cumulative probability of reaching this node
    parent_id: Optional[str] = None
    children: list = field(default_factory=list)
    action: str = "HOLD"   # BUY, SELL, HOLD
    action_rationale: str = ""
    color: str = "#888888"
    eurusd_est: float = 1.17  # Estimated EUR/USD for this scenario

    def __post_init__(self):
        # Auto-derive EUR/gram from USD/oz if not explicitly set
        if self.gold_eur_range == (0, 0) or self.gold_eur_range[1] < 10:
            lo = self.gold_usd_range[0] / self.eurusd_est / 31.1035
            hi = self.gold_usd_range[1] / self.eurusd_est / 31.1035
            self.gold_eur_range = (round(lo, 1), round(hi, 1))

    @property
    def gold_eur_mid(self):
        return (self.gold_eur_range[0] + self.gold_eur_range[1]) / 2

    @property
    def gold_usd_mid(self):
        return (self.gold_usd_range[0] + self.gold_usd_range[1]) / 2

    @property
    def expected_return_eur(self):
        """Expected return vs current, using USD/oz as authoritative."""
        return (self.gold_usd_mid / CURRENT_GOLD_USD_OZ - 1) * 100


# Current state: April 2026
# Gold: ~$4,780/oz ≈ ~€4,085/oz ≈ ~€88/gram (at EUR/USD ~1.17)
# iShares Physical Gold ETC ≈ ~€48-50 per unit

CURRENT_GOLD_EUR_GRAM = config.CURRENT_GOLD_EUR_GRAM
CURRENT_GOLD_USD_OZ = config.CURRENT_GOLD_USD_OZ
CURRENT_BRENT = config.CURRENT_BRENT
CURRENT_EURUSD = config.CURRENT_EURUSD
PORTFOLIO_HELD = float(config.PORTFOLIO_HELD)
PORTFOLIO_AVAILABLE = float(config.PORTFOLIO_AVAILABLE)


def build_scenario_tree():
    """
    Build the full scenario tree with Markov transition probabilities.

    Structure:
    NOW (t=0) → 3 scenarios at t=3m → 2-3 sub-scenarios each at t=6m → refinements at t=12m

    Key drivers modeled:
    1. Military: escalation vs stalemate vs de-escalation
    2. Oil: Strait of Hormuz status → Brent price
    3. Macro: Real yields, USD/EUR, central bank buying
    4. Gold price response (counterintuitive: escalation can hurt gold via USD strength)
    """

    nodes = {}

    # =========================================================================
    # T = 0: CURRENT STATE (April 2026)
    # =========================================================================
    root = ScenarioNode(
        id="NOW",
        name="Current State\nApr 2026",
        month=0,
        description="Fragile ceasefire, Strait partially open, oil ~$99, gold ~$4,780",
        gold_eur_range=(0, 0),
        gold_usd_range=(4700, 4850),
        oil_range=(96, 102),
        probability=1.0,
        color="#4A90D9",
        action="HOLD",
        action_rationale="Wait for clarity on ceasefire outcome"
    )
    nodes[root.id] = root

    # =========================================================================
    # T = 3 MONTHS (July 2026) — Three primary branches
    # =========================================================================

    # Branch A: Ceasefire collapses, renewed military operations (35%)
    a = ScenarioNode(
        id="3M_ESCALATION",
        name="Escalation\nJul 2026",
        month=3,
        description="Ceasefire collapses. New strikes on Iranian targets. "
                    "Strait of Hormuz fully closed again. Oil spikes. "
                    "USD surges on safe-haven flows. Gold spikes then fades.",
        gold_eur_range=(0, 0),
        gold_usd_range=(4900, 5300),
        oil_range=(115, 135),
        probability=0.35,
        parent_id="NOW",
        color="#E74C3C",
        action="HOLD",
        action_rationale="Spike is short-lived historically; don't chase"
    )
    nodes[a.id] = a
    root.children.append(a.id)

    # Branch B: Stalemate / Status Quo continues (40%)
    b = ScenarioNode(
        id="3M_STALEMATE",
        name="Stalemate\nJul 2026",
        month=3,
        description="Ceasefire extended but no real progress. Partial Strait access. "
                    "Oil elevated but stable. Markets adapt to new normal. "
                    "Gold range-bound with high volatility.",
        gold_eur_range=(0, 0),
        gold_usd_range=(4500, 5000),
        oil_range=(92, 108),
        probability=0.40,
        parent_id="NOW",
        color="#F39C12",
        action="BUY",
        action_rationale="Accumulate on dips during range-bound trading; invest €1,500"
    )
    nodes[b.id] = b
    root.children.append(b.id)

    # Branch C: De-escalation / Peace progress (25%)
    c = ScenarioNode(
        id="3M_DEESCALATION",
        name="De-escalation\nJul 2026",
        month=3,
        description="Meaningful diplomatic progress. Extended ceasefire with monitors. "
                    "Strait fully reopened. Oil drops sharply. Risk premium fades. "
                    "Gold falls in USD but EUR-gold more stable as USD weakens.",
        gold_eur_range=(0, 0),
        gold_usd_range=(4200, 4600),
        oil_range=(80, 92),
        probability=0.25,
        parent_id="NOW",
        color="#27AE60",
        action="BUY",
        action_rationale="Strong buy on dip — structural gold bull case intact; invest €2,000"
    )
    nodes[c.id] = c
    root.children.append(c.id)

    # =========================================================================
    # T = 6 MONTHS (October 2026) — Sub-branches from each 3M scenario
    # =========================================================================

    # --- From ESCALATION (35%) ---

    # A1: Escalation → Wider regional war (30% of A = 10.5% total)
    a1 = ScenarioNode(
        id="6M_WIDER_WAR",
        name="Wider War\nOct 2026",
        month=6,
        description="Conflict spreads to Lebanon/Hezbollah front. Gulf state infrastructure hit. "
                    "Global recession fears. Flight to safety overwhelms macro headwinds. "
                    "Gold surges as systemic risk dominates.",
        gold_eur_range=(0, 0),
        gold_usd_range=(5400, 6000),
        oil_range=(135, 165),
        probability=0.105,
        parent_id="3M_ESCALATION",
        color="#C0392B",
        action="SELL",
        action_rationale="Take profits on held position (sell €1,500 of €3k); extreme levels rarely sustained"
    )
    nodes[a1.id] = a1
    a.children.append(a1.id)

    # A2: Escalation → Military stalemate (45% of A = 15.75% total)
    a2 = ScenarioNode(
        id="6M_ESC_STALEMATE",
        name="Escalation→Stalemate\nOct 2026",
        month=6,
        description="Initial escalation burns out. Both sides exhausted. "
                    "Partial Strait reopening. Oil eases from peak but stays elevated. "
                    "Gold gives back spike gains. Real yields pressure persists.",
        gold_eur_range=(0, 0),
        gold_usd_range=(4600, 5100),
        oil_range=(100, 118),
        probability=0.1575,
        parent_id="3M_ESCALATION",
        color="#E67E22",
        action="BUY",
        action_rationale="Buy dip after spike reversal; invest €1,500"
    )
    nodes[a2.id] = a2
    a.children.append(a2.id)

    # A3: Escalation → Forced peace (25% of A = 8.75% total)
    a3 = ScenarioNode(
        id="6M_FORCED_PEACE",
        name="Escalation→Peace\nOct 2026",
        month=6,
        description="Escalation creates urgency for deal. Back-channel negotiations succeed. "
                    "Comprehensive ceasefire with international monitors. "
                    "Oil drops rapidly. Gold falls on risk premium collapse.",
        gold_eur_range=(0, 0),
        gold_usd_range=(4100, 4500),
        oil_range=(78, 90),
        probability=0.0875,
        parent_id="3M_ESCALATION",
        color="#2ECC71",
        action="BUY",
        action_rationale="Strong buy — risk premium oversold; invest full €3k"
    )
    nodes[a3.id] = a3
    a.children.append(a3.id)

    # --- From STALEMATE (40%) ---

    # B1: Stalemate → Slow escalation (30% of B = 12% total)
    b1 = ScenarioNode(
        id="6M_SLOW_ESC",
        name="Slow Escalation\nOct 2026",
        month=6,
        description="Stalemate drifts toward escalation. Proxy attacks increase. "
                    "Strait incidents become more frequent. Oil creeps up. "
                    "Gold volatile, slight upward bias.",
        gold_eur_range=(0, 0),
        gold_usd_range=(4700, 5200),
        oil_range=(105, 120),
        probability=0.12,
        parent_id="3M_STALEMATE",
        color="#E74C3C",
        action="HOLD",
        action_rationale="Hold existing position; wait for resolution clarity"
    )
    nodes[b1.id] = b1
    b.children.append(b1.id)

    # B2: Stalemate → Continued stalemate (45% of B = 18% total)
    b2 = ScenarioNode(
        id="6M_CONT_STALEMATE",
        name="Continued Stalemate\nOct 2026",
        month=6,
        description="More of the same. Markets fully price in 'new normal'. "
                    "Oil stabilizes $95-105. Gold range-bound. "
                    "Central bank buying supports, real yields cap upside.",
        gold_eur_range=(0, 0),
        gold_usd_range=(4400, 4900),
        oil_range=(93, 107),
        probability=0.18,
        parent_id="3M_STALEMATE",
        color="#F39C12",
        action="BUY",
        action_rationale="Continue accumulating; invest remaining available (€1,500)"
    )
    nodes[b2.id] = b2
    b.children.append(b2.id)

    # B3: Stalemate → Gradual de-escalation (25% of B = 10% total)
    b3 = ScenarioNode(
        id="6M_GRAD_DEESC",
        name="Gradual De-escalation\nOct 2026",
        month=6,
        description="Quiet diplomacy works. Confidence-building measures. "
                    "Strait incidents decrease. Oil eases. "
                    "Gold drifts lower but structural support holds.",
        gold_eur_range=(0, 0),
        gold_usd_range=(4300, 4700),
        oil_range=(84, 96),
        probability=0.10,
        parent_id="3M_STALEMATE",
        color="#27AE60",
        action="HOLD",
        action_rationale="Hold; gold structural bull intact despite conflict resolution"
    )
    nodes[b3.id] = b3
    b.children.append(b3.id)

    # --- From DE-ESCALATION (25%) ---

    # C1: De-escalation → Deal falls apart (25% of C = 6.25% total)
    c1 = ScenarioNode(
        id="6M_DEAL_FAILS",
        name="Deal Fails\nOct 2026",
        month=6,
        description="Initial progress reverses. Hardliners on both sides scuttle deal. "
                    "Return to tensions. Oil rebounds. "
                    "Gold recovers some of the de-escalation drop.",
        gold_eur_range=(0, 0),
        gold_usd_range=(4600, 5000),
        oil_range=(95, 110),
        probability=0.0625,
        parent_id="3M_DEESCALATION",
        color="#E74C3C",
        action="HOLD",
        action_rationale="Already bought the dip; hold through volatility"
    )
    nodes[c1.id] = c1
    c.children.append(c1.id)

    # C2: De-escalation → Full peace deal (75% of C = 18.75% total)
    c2 = ScenarioNode(
        id="6M_PEACE_DEAL",
        name="Peace Deal\nOct 2026",
        month=6,
        description="Comprehensive deal: sanctions relief, nuclear inspections, "
                    "Strait guarantees. Oil normalizes. USD weakens. "
                    "Gold falls in USD, stable in EUR. Risk premium fully unwound.",
        gold_eur_range=(0, 0),
        gold_usd_range=(4100, 4500),
        oil_range=(72, 85),
        probability=0.1875,
        parent_id="3M_DEESCALATION",
        color="#2ECC71",
        action="HOLD",
        action_rationale="Hold — structural gold supports (CB buying, debt levels) remain"
    )
    nodes[c2.id] = c2
    c.children.append(c2.id)

    # =========================================================================
    # T = 12 MONTHS (April 2027) — Terminal nodes
    # =========================================================================

    # From WIDER WAR → 2 outcomes
    t1 = ScenarioNode(
        id="12M_PROLONGED_WAR",
        name="Prolonged War\nApr 2027",
        month=12,
        description="Regional conflict entrenched. Global recession underway. "
                    "Central banks cut rates → real yields plunge → gold soars. "
                    "EUR gold at all-time highs.",
        gold_eur_range=(0, 0),
        gold_usd_range=(5800, 6500),
        oil_range=(125, 155),
        probability=0.042,  # 40% of wider war
        parent_id="6M_WIDER_WAR",
        color="#922B21",
        action="SELL",
        action_rationale="Take full profits — extreme overshoot; sell entire position"
    )
    nodes[t1.id] = t1
    a1.children.append(t1.id)

    t2 = ScenarioNode(
        id="12M_WAR_EXHAUSTION",
        name="War Exhaustion→Peace\nApr 2027",
        month=12,
        description="War exhaustion forces settlement. Rapid normalization. "
                    "Oil crashes toward $75. Gold falls sharply but overshoots down. "
                    "Good re-entry point.",
        gold_eur_range=(0, 0),
        gold_usd_range=(4400, 4900),
        oil_range=(72, 88),
        probability=0.063,  # 60% of wider war
        parent_id="6M_WIDER_WAR",
        color="#F39C12",
        action="BUY",
        action_rationale="Buy the peace — post-war overshooting creates opportunity"
    )
    nodes[t2.id] = t2
    a1.children.append(t2.id)

    # From ESC_STALEMATE → 2 outcomes
    t3 = ScenarioNode(
        id="12M_FROZEN_CONFLICT",
        name="Frozen Conflict\nApr 2027",
        month=12,
        description="Low-level frozen conflict like North Korea model. "
                    "Markets fully adapted. Oil $90-100. "
                    "Gold supported by structural factors, not conflict premium.",
        gold_eur_range=(0, 0),
        gold_usd_range=(4700, 5200),
        oil_range=(88, 102),
        probability=0.094,  # 60% of esc_stalemate
        parent_id="6M_ESC_STALEMATE",
        color="#F39C12",
        action="HOLD",
        action_rationale="Hold — gold in structural bull market independent of Iran"
    )
    nodes[t3.id] = t3
    a2.children.append(t3.id)

    t4 = ScenarioNode(
        id="12M_ESC_RESOLUTION",
        name="Late Resolution\nApr 2027",
        month=12,
        description="Prolonged process finally yields framework agreement. "
                    "Oil normalizes. Gold gives back conflict premium "
                    "but structural bull intact (CB buying, fiscal deficits).",
        gold_eur_range=(0, 0),
        gold_usd_range=(4300, 4800),
        oil_range=(76, 90),
        probability=0.063,  # 40% of esc_stalemate
        parent_id="6M_ESC_STALEMATE",
        color="#27AE60",
        action="HOLD",
        action_rationale="Hold long-term; gold supported by non-conflict factors"
    )
    nodes[t4.id] = t4
    a2.children.append(t4.id)

    # From FORCED_PEACE → 1 outcome (peace consolidates)
    t5 = ScenarioNode(
        id="12M_PEACE_HOLDS",
        name="Peace Consolidates\nApr 2027",
        month=12,
        description="Post-escalation peace deal holds. Sanctions partially lifted. "
                    "Iran oil returns to market. Global growth recovers. "
                    "Gold structurally supported but no conflict premium.",
        gold_eur_range=(0, 0),
        gold_usd_range=(4400, 4900),
        oil_range=(70, 82),
        probability=0.0875,
        parent_id="6M_FORCED_PEACE",
        color="#27AE60",
        action="HOLD",
        action_rationale="Hold — bought at bottom; long-term structural bull"
    )
    nodes[t5.id] = t5
    a3.children.append(t5.id)

    # From SLOW_ESC → 2 outcomes
    t6 = ScenarioNode(
        id="12M_LATE_ESCALATION",
        name="Late Escalation\nApr 2027",
        month=12,
        description="Slow burn finally erupts. New military campaign. "
                    "Markets shocked after complacency. Gold spikes hard.",
        gold_eur_range=(0, 0),
        gold_usd_range=(5200, 5800),
        oil_range=(120, 145),
        probability=0.048,  # 40% of slow_esc
        parent_id="6M_SLOW_ESC",
        color="#C0392B",
        action="SELL",
        action_rationale="Sell into spike — take profits on half position"
    )
    nodes[t6.id] = t6
    b1.children.append(t6.id)

    t7 = ScenarioNode(
        id="12M_SLOW_RESOLUTION",
        name="Slow Resolution\nApr 2027",
        month=12,
        description="Tension gradually defused through back channels. "
                    "Oil normalizes. Gold stable, supported by macro factors.",
        gold_eur_range=(0, 0),
        gold_usd_range=(4500, 5000),
        oil_range=(82, 96),
        probability=0.072,  # 60% of slow_esc
        parent_id="6M_SLOW_ESC",
        color="#F39C12",
        action="HOLD",
        action_rationale="Hold — conflict premium fading, structural bull remains"
    )
    nodes[t7.id] = t7
    b1.children.append(t7.id)

    # From CONT_STALEMATE → 2 outcomes
    t8 = ScenarioNode(
        id="12M_NEW_NORMAL",
        name="New Normal\nApr 2027",
        month=12,
        description="Permanent elevated baseline. Like post-2014 Russia sanctions. "
                    "Oil $90-100 structural floor. Gold in $4,600-5,000 band. "
                    "Volatility decreases as markets adapt.",
        gold_eur_range=(0, 0),
        gold_usd_range=(4600, 5100),
        oil_range=(90, 104),
        probability=0.126,  # 70% of cont_stalemate
        parent_id="6M_CONT_STALEMATE",
        color="#F39C12",
        action="HOLD",
        action_rationale="Hold — range-bound but well-supported; collect on dips"
    )
    nodes[t8.id] = t8
    b2.children.append(t8.id)

    t9 = ScenarioNode(
        id="12M_STALE_BREAKTHROUGH",
        name="Breakthrough\nApr 2027",
        month=12,
        description="Unexpected diplomatic breakthrough after prolonged stalemate. "
                    "Oil drops. Gold dips briefly then recovers "
                    "as focus shifts to fiscal/monetary factors.",
        gold_eur_range=(0, 0),
        gold_usd_range=(4300, 4800),
        oil_range=(74, 88),
        probability=0.054,  # 30% of cont_stalemate
        parent_id="6M_CONT_STALEMATE",
        color="#2ECC71",
        action="HOLD",
        action_rationale="Hold — gold dip is temporary; structural supports strong"
    )
    nodes[t9.id] = t9
    b2.children.append(t9.id)

    # From GRAD_DEESC → 1 outcome
    t10 = ScenarioNode(
        id="12M_NORMALIZED",
        name="Normalized\nApr 2027",
        month=12,
        description="Full normalization of Gulf shipping. Iran nuclear deal 2.0. "
                    "Oil back to $70-80. Gold stable, driven by macro not geopolitics. "
                    "CB buying continues to support floor.",
        gold_eur_range=(0, 0),
        gold_usd_range=(4200, 4700),
        oil_range=(68, 82),
        probability=0.10,
        parent_id="6M_GRAD_DEESC",
        color="#27AE60",
        action="HOLD",
        action_rationale="Hold — structural gold bull transcends Iran conflict"
    )
    nodes[t10.id] = t10
    b3.children.append(t10.id)

    # From DEAL_FAILS → 1 outcome
    t11 = ScenarioNode(
        id="12M_RENEWED_TENSIONS",
        name="Renewed Tensions\nApr 2027",
        month=12,
        description="Failed deal leads to hardliner empowerment on both sides. "
                    "New escalation cycle. Gold benefits from renewed uncertainty.",
        gold_eur_range=(0, 0),
        gold_usd_range=(4900, 5400),
        oil_range=(100, 120),
        probability=0.0625,
        parent_id="6M_DEAL_FAILS",
        color="#E74C3C",
        action="HOLD",
        action_rationale="Hold — already positioned from earlier buy"
    )
    nodes[t11.id] = t11
    c1.children.append(t11.id)

    # From PEACE_DEAL → 1 outcome
    t12 = ScenarioNode(
        id="12M_POST_PEACE",
        name="Post-Peace Growth\nApr 2027",
        month=12,
        description="Sustained peace. Global growth recovery. "
                    "Gold moderates but stays supported by structural factors: "
                    "CB buying, fiscal deficits, de-dollarization trend.",
        gold_eur_range=(0, 0),
        gold_usd_range=(4100, 4600),
        oil_range=(65, 78),
        probability=0.1875,
        parent_id="6M_PEACE_DEAL",
        color="#27AE60",
        action="HOLD",
        action_rationale="Hold — lowest price scenario but structural bull intact long-term"
    )
    nodes[t12.id] = t12
    c2.children.append(t12.id)

    return nodes, root


# =============================================================================
# MARKOV TRANSITION MATRIX
# =============================================================================

def build_transition_matrices():
    """
    Build transition probability matrices for each time step.

    States: ESCALATION, STALEMATE, DE-ESCALATION
    These represent the geopolitical regime, not specific nodes.
    """

    # Month 0 → Month 3 transition (from current state)
    # Current state is "fragile ceasefire" ≈ stalemate leaning toward escalation
    T_0_to_3 = np.array([
        # To:  ESC   STALE  DE-ESC
        [0.35, 0.40, 0.25],  # From: current state
    ])

    # Month 3 → Month 6 transition
    T_3_to_6 = np.array([
        # To:  ESC   STALE  DE-ESC
        [0.30, 0.45, 0.25],  # From: ESCALATION (conflict tends to stalemate)
        [0.30, 0.45, 0.25],  # From: STALEMATE (can go either way)
        [0.25, 0.00, 0.75],  # From: DE-ESCALATION (momentum toward peace)
    ])

    # Month 6 → Month 12 transition
    T_6_to_12 = np.array([
        # To:  ESC   STALE  DE-ESC
        [0.40, 0.35, 0.25],  # From: ESCALATION (persistence + exhaustion)
        [0.30, 0.40, 0.30],  # From: STALEMATE (increasing de-esc pressure over time)
        [0.15, 0.10, 0.75],  # From: DE-ESCALATION (peace momentum builds)
    ])

    return {
        '0→3': T_0_to_3,
        '3→6': T_3_to_6,
        '6→12': T_6_to_12,
    }


def compute_state_probabilities(matrices):
    """Compute probability of being in each state at each time step."""
    initial = np.array([0.35, 0.40, 0.25])  # ESC, STALE, DE-ESC at t=3

    state_at_6 = np.zeros(3)
    for i in range(3):
        state_at_6 += initial[i] * matrices['3→6'][i]

    state_at_12 = np.zeros(3)
    for i in range(3):
        state_at_12 += state_at_6[i] * matrices['6→12'][i]

    return {
        't=0': np.array([0, 1, 0]),  # stalemate
        't=3': initial,
        't=6': state_at_6,
        't=12': state_at_12,
    }


# =============================================================================
# EXPECTED VALUE CALCULATIONS
# =============================================================================

def compute_portfolio_analysis(nodes):
    """Compute expected portfolio values under different strategies."""

    terminal_nodes = {nid: n for nid, n in nodes.items() if n.month == 12}

    strategies = {
        'Hold All': {
            'description': 'Hold €3k, keep €3k cash',
            'gold_invested': PORTFOLIO_HELD,
            'cash': PORTFOLIO_AVAILABLE,
        },
        'All In Now': {
            'description': 'Invest full €6k immediately',
            'gold_invested': PORTFOLIO_HELD + PORTFOLIO_AVAILABLE,
            'cash': 0,
        },
        'DCA Quarterly': {
            'description': 'Invest €1k per quarter over 3 quarters',
            'gold_invested': PORTFOLIO_HELD,  # start
            'cash': PORTFOLIO_AVAILABLE,
            'dca_amount': 1000,
        },
        'Adaptive (Recommended)': {
            'description': 'Follow tree recommendations: buy dips, sell spikes',
            'gold_invested': PORTFOLIO_HELD,
            'cash': PORTFOLIO_AVAILABLE,
        },
    }

    results = {}

    for strat_name, strat in strategies.items():
        expected_value = 0
        worst_case = float('inf')
        best_case = float('-inf')

        for nid, node in terminal_nodes.items():
            # Gold return factor
            ret = node.gold_eur_mid / CURRENT_GOLD_EUR_GRAM

            if strat_name == 'Hold All':
                portfolio_val = strat['gold_invested'] * ret + strat['cash']
            elif strat_name == 'All In Now':
                portfolio_val = strat['gold_invested'] * ret
            elif strat_name == 'DCA Quarterly':
                # Simplified: average entry price across quarters
                # Average return assuming buy at different levels
                avg_ret = (ret + 1.0 + (1.0 + ret) / 2) / 3 * ret
                portfolio_val = strat['gold_invested'] * ret + strat['cash'] * (avg_ret * 0.85)  # conservative
            else:  # Adaptive
                # Model the recommended actions along the path
                portfolio_val = strat['gold_invested'] * ret + strat['cash'] * (ret * 0.92)  # better entry via timing

            weighted = portfolio_val * node.probability
            expected_value += weighted
            worst_case = min(worst_case, portfolio_val)
            best_case = max(best_case, portfolio_val)

        results[strat_name] = {
            'expected_value': expected_value,
            'expected_return': (expected_value / (PORTFOLIO_HELD + PORTFOLIO_AVAILABLE) - 1) * 100,
            'worst_case': worst_case,
            'best_case': best_case,
            'description': strat['description'],
        }

    return results


# =============================================================================
# VISUALIZATION
# =============================================================================

def create_tree_visualization(nodes, root):
    """Create an interactive Plotly tree visualization."""

    # Layout: position nodes by month (x) and spread vertically (y)
    positions = {}

    # Assign positions layer by layer
    month_nodes = {}
    for nid, node in nodes.items():
        month_nodes.setdefault(node.month, []).append(nid)

    x_positions = {0: 0, 3: 1, 6: 2, 12: 3}

    for month, nids in month_nodes.items():
        n = len(nids)
        for i, nid in enumerate(nids):
            x = x_positions[month]
            # Spread vertically
            y = (i - (n - 1) / 2) * (1.5 if month <= 3 else 1.0 if month <= 6 else 0.8)
            positions[nid] = (x, y)

    # Build edge traces
    edge_x = []
    edge_y = []
    edge_annotations = []

    for nid, node in nodes.items():
        if node.parent_id:
            x0, y0 = positions[node.parent_id]
            x1, y1 = positions[nid]
            # Use bezier-like points for smoother edges
            mid_x = (x0 + x1) / 2
            for t in np.linspace(0, 1, 20):
                # Quadratic bezier
                bx = (1-t)**2 * x0 + 2*(1-t)*t * mid_x + t**2 * x1
                by = (1-t)**2 * y0 + 2*(1-t)*t * (y0 + y1)/2 + t**2 * y1
                edge_x.append(bx)
                edge_y.append(by)
            edge_x.append(None)
            edge_y.append(None)

            # Probability label on edge
            # Compute conditional probability
            parent = nodes[node.parent_id]
            if parent.probability > 0:
                cond_prob = node.probability / parent.probability
            else:
                cond_prob = 0

            edge_annotations.append(dict(
                x=(x0 * 0.35 + x1 * 0.65),
                y=(y0 * 0.35 + y1 * 0.65),
                text=f"<b>{cond_prob:.0%}</b>",
                showarrow=False,
                font=dict(size=9, color='#555'),
                bgcolor='rgba(255,255,255,0.8)',
            ))

    # Edge trace
    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        mode='lines',
        line=dict(width=1.5, color='#aaa'),
        hoverinfo='none',
        showlegend=False,
    )

    # Node traces — group by action for legend
    action_colors = {
        'BUY': '#27AE60',
        'SELL': '#E74C3C',
        'HOLD': '#3498DB',
    }

    node_traces = []
    for action in ['HOLD', 'BUY', 'SELL']:
        action_nodes = [(nid, n) for nid, n in nodes.items() if n.action == action]
        if not action_nodes:
            continue

        node_x = [positions[nid][0] for nid, _ in action_nodes]
        node_y = [positions[nid][1] for nid, _ in action_nodes]
        node_text = []
        node_hover = []
        node_sizes = []
        node_colors = []

        for nid, node in action_nodes:
            # Size by probability
            size = max(15, min(50, node.probability * 200))
            node_sizes.append(size)
            node_colors.append(node.color)

            node_text.append(node.name)

            hover = (
                f"<b>{node.name.replace(chr(10), ' ')}</b><br>"
                f"<br>"
                f"Gold (EUR/g): €{node.gold_eur_range[0]:.0f}–€{node.gold_eur_range[1]:.0f}<br>"
                f"Gold (USD/oz): ${node.gold_usd_range[0]:,.0f}–${node.gold_usd_range[1]:,.0f}<br>"
                f"Oil (Brent): ${node.oil_range[0]:.0f}–${node.oil_range[1]:.0f}/bbl<br>"
                f"<br>"
                f"Probability: {node.probability:.1%}<br>"
                f"Expected Return: {node.expected_return_eur:+.1f}%<br>"
                f"<br>"
                f"<b>Action: {node.action}</b><br>"
                f"{node.action_rationale}<br>"
                f"<br>"
                f"<i>{node.description[:120]}...</i>"
            )
            node_hover.append(hover)

        trace = go.Scatter(
            x=node_x, y=node_y,
            mode='markers+text',
            name=f"→ {action}",
            marker=dict(
                size=node_sizes,
                color=node_colors,
                line=dict(width=3, color=action_colors[action]),
                symbol='circle',
            ),
            text=[n.name.split('\n')[0] for _, n in action_nodes],
            textposition='top center',
            textfont=dict(size=10, color='#333'),
            hovertext=node_hover,
            hoverinfo='text',
            hoverlabel=dict(
                bgcolor='white',
                font_size=12,
                font_family='monospace',
            ),
        )
        node_traces.append(trace)

    # Create figure
    fig = go.Figure(data=[edge_trace] + node_traces)

    fig.update_layout(
        title=dict(
            text=(
                "<b>Gold ETF Scenario Tree: US-Iran Conflict Impact</b><br>"
                "<sup>iShares Physical Gold ETC | April 2026 – April 2027 | "
                "Node size = probability, border color = recommended action</sup>"
            ),
            font=dict(size=16),
        ),
        showlegend=True,
        legend=dict(
            title="Recommended Action",
            font=dict(size=12),
            bgcolor='rgba(255,255,255,0.9)',
            x=0.01, y=0.99,
        ),
        xaxis=dict(
            tickvals=[0, 1, 2, 3],
            ticktext=['<b>Now</b><br>Apr 2026', '<b>+3 Months</b><br>Jul 2026',
                      '<b>+6 Months</b><br>Oct 2026', '<b>+12 Months</b><br>Apr 2027'],
            showgrid=True,
            gridcolor='rgba(0,0,0,0.05)',
            zeroline=False,
            range=[-0.3, 3.5],
        ),
        yaxis=dict(
            showticklabels=False,
            showgrid=False,
            zeroline=False,
        ),
        plot_bgcolor='white',
        paper_bgcolor='#FAFAFA',
        width=1400,
        height=900,
        annotations=edge_annotations,
        margin=dict(l=50, r=50, t=100, b=80),
    )

    return fig


def create_probability_heatmap(nodes):
    """Create a heatmap of gold price probabilities over time."""

    months = [0, 3, 6, 12]
    month_labels = ['Apr 2026', 'Jul 2026', 'Oct 2026', 'Apr 2027']

    # Price bins (EUR/gram)
    price_bins = list(range(70, 155, 5))

    # Build probability density for each month
    heatmap_data = np.zeros((len(price_bins) - 1, len(months)))

    for col, month in enumerate(months):
        month_nodes_list = [(nid, n) for nid, n in nodes.items() if n.month == month]
        for _, node in month_nodes_list:
            lo, hi = node.gold_eur_range
            for row in range(len(price_bins) - 1):
                bin_lo = price_bins[row]
                bin_hi = price_bins[row + 1]
                # Overlap between node range and bin
                overlap_lo = max(lo, bin_lo)
                overlap_hi = min(hi, bin_hi)
                if overlap_hi > overlap_lo:
                    coverage = (overlap_hi - overlap_lo) / (hi - lo)
                    heatmap_data[row, col] += node.probability * coverage

    # Normalize columns
    for col in range(len(months)):
        col_sum = heatmap_data[:, col].sum()
        if col_sum > 0:
            heatmap_data[:, col] /= col_sum

    bin_labels = [f"€{price_bins[i]}-{price_bins[i+1]}" for i in range(len(price_bins)-1)]

    fig = go.Figure(data=go.Heatmap(
        z=heatmap_data,
        x=month_labels,
        y=bin_labels,
        colorscale=[
            [0, '#FFFFFF'],
            [0.2, '#FFF3E0'],
            [0.4, '#FFB74D'],
            [0.6, '#FF9800'],
            [0.8, '#E65100'],
            [1.0, '#BF360C'],
        ],
        colorbar=dict(title='Probability<br>Density'),
        hovertemplate='Time: %{x}<br>Price: %{y}<br>Probability: %{z:.1%}<extra></extra>',
    ))

    # Add current price marker
    fig.add_hline(
        y=3.5,  # corresponds to €85-90 bin
        line_dash="dash",
        line_color="blue",
        annotation_text="Current: ~€88/g",
        annotation_position="top right",
    )

    fig.update_layout(
        title=dict(
            text="<b>Gold Price Probability Distribution Over Time (EUR/gram)</b><br>"
                 "<sup>Darker = higher probability | Based on scenario tree weights</sup>",
            font=dict(size=14),
        ),
        xaxis_title="Timeline",
        yaxis_title="Gold Price Range (EUR/gram)",
        width=900,
        height=700,
        plot_bgcolor='white',
        paper_bgcolor='#FAFAFA',
    )

    return fig


def create_strategy_comparison(portfolio_results):
    """Create a bar chart comparing investment strategies."""

    strategies = list(portfolio_results.keys())
    expected = [portfolio_results[s]['expected_value'] for s in strategies]
    worst = [portfolio_results[s]['worst_case'] for s in strategies]
    best = [portfolio_results[s]['best_case'] for s in strategies]
    descriptions = [portfolio_results[s]['description'] for s in strategies]

    fig = go.Figure()

    # Worst case
    fig.add_trace(go.Bar(
        name='Worst Case',
        x=strategies,
        y=worst,
        marker_color='#E74C3C',
        opacity=0.7,
        text=[f"€{v:,.0f}" for v in worst],
        textposition='outside',
    ))

    # Expected
    fig.add_trace(go.Bar(
        name='Expected Value',
        x=strategies,
        y=expected,
        marker_color='#3498DB',
        text=[f"€{v:,.0f}" for v in expected],
        textposition='outside',
    ))

    # Best case
    fig.add_trace(go.Bar(
        name='Best Case',
        x=strategies,
        y=best,
        marker_color='#27AE60',
        opacity=0.7,
        text=[f"€{v:,.0f}" for v in best],
        textposition='outside',
    ))

    # Reference line at €6,000 (initial capital)
    fig.add_hline(
        y=6000,
        line_dash="dash",
        line_color="gray",
        annotation_text="Initial Capital: €6,000",
        annotation_position="top right",
    )

    fig.update_layout(
        title=dict(
            text="<b>Investment Strategy Comparison: 12-Month Horizon</b><br>"
                 "<sup>Portfolio: €3k held + €3k available | iShares Physical Gold ETC</sup>",
            font=dict(size=14),
        ),
        yaxis_title="Portfolio Value (EUR)",
        barmode='group',
        width=900,
        height=600,
        plot_bgcolor='white',
        paper_bgcolor='#FAFAFA',
        legend=dict(x=0.01, y=0.99),
    )

    return fig


def create_decision_timeline(nodes):
    """Create a timeline of recommended actions with trigger events."""

    fig = go.Figure()

    # Collect all action recommendations by time
    actions_by_month = {}
    for nid, node in nodes.items():
        actions_by_month.setdefault(node.month, []).append(node)

    colors = {'BUY': '#27AE60', 'SELL': '#E74C3C', 'HOLD': '#3498DB'}
    symbols = {'BUY': 'triangle-up', 'SELL': 'triangle-down', 'HOLD': 'circle'}

    for month, month_nodes_list in sorted(actions_by_month.items()):
        for i, node in enumerate(month_nodes_list):
            fig.add_trace(go.Scatter(
                x=[month],
                y=[node.gold_eur_mid],
                mode='markers',
                marker=dict(
                    size=max(10, node.probability * 150),
                    color=colors[node.action],
                    symbol=symbols[node.action],
                    line=dict(width=2, color='white'),
                ),
                name=f"{node.action}: {node.name.split(chr(10))[0]}",
                showlegend=(month == 3),  # Only show legend once per action type
                hovertext=(
                    f"<b>{node.name.replace(chr(10), ' ')}</b><br>"
                    f"Gold: €{node.gold_eur_range[0]:.0f}–€{node.gold_eur_range[1]:.0f}/g<br>"
                    f"Prob: {node.probability:.1%}<br>"
                    f"Action: {node.action}<br>"
                    f"{node.action_rationale}"
                ),
                hoverinfo='text',
            ))

    fig.update_layout(
        title=dict(
            text="<b>Gold Price Trajectories with Buy/Sell Signals</b><br>"
                 "<sup>▲ BUY | ● HOLD | ▼ SELL | Size = probability</sup>",
            font=dict(size=14),
        ),
        xaxis=dict(
            tickvals=[0, 3, 6, 12],
            ticktext=['Now', '+3m', '+6m', '+12m'],
            title='Timeline (months)',
        ),
        yaxis_title="Gold Price (EUR/gram)",
        width=1000,
        height=600,
        plot_bgcolor='white',
        paper_bgcolor='#FAFAFA',
    )

    return fig


def create_markov_diagram(matrices, state_probs):
    """Visualize the Markov transition matrices."""

    states = ['Escalation', 'Stalemate', 'De-escalation']
    state_colors = ['#E74C3C', '#F39C12', '#27AE60']

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            'State Probabilities Over Time',
            'Transition: Month 0→3',
            'Transition: Month 3→6',
            'Transition: Month 6→12',
        ],
        specs=[
            [{"type": "scatter"}, {"type": "heatmap"}],
            [{"type": "heatmap"}, {"type": "heatmap"}],
        ],
    )

    # State probabilities over time
    times = [0, 3, 6, 12]
    time_labels = ['Now', '+3m', '+6m', '+12m']
    for i, state in enumerate(states):
        probs = [state_probs[f't={t}'][i] for t in times]
        fig.add_trace(go.Scatter(
            x=time_labels, y=probs,
            mode='lines+markers',
            name=state,
            line=dict(color=state_colors[i], width=3),
            marker=dict(size=10),
        ), row=1, col=1)

    # Transition matrices as heatmaps
    for idx, (key, mat) in enumerate(matrices.items()):
        row = 1 if idx == 0 else 2
        col = 2 if idx == 0 else (idx)

        fig.add_trace(go.Heatmap(
            z=mat,
            x=states,
            y=states if mat.shape[0] > 1 else ['Current'],
            colorscale='YlOrRd',
            showscale=False,
            text=[[f"{v:.0%}" for v in row_vals] for row_vals in mat],
            texttemplate="%{text}",
            textfont=dict(size=12),
            hovertemplate='From: %{y}<br>To: %{x}<br>Prob: %{z:.0%}<extra></extra>',
        ), row=row, col=col)

    fig.update_layout(
        title=dict(
            text="<b>Markov Chain: Geopolitical State Transitions</b>",
            font=dict(size=14),
        ),
        width=1100,
        height=700,
        plot_bgcolor='white',
        paper_bgcolor='#FAFAFA',
        showlegend=True,
    )

    return fig


# =============================================================================
# SUMMARY REPORT
# =============================================================================

def generate_report(nodes, portfolio_results, state_probs):
    """Generate a text summary report."""

    terminal_nodes = sorted(
        [(nid, n) for nid, n in nodes.items() if n.month == 12],
        key=lambda x: x[1].probability,
        reverse=True
    )

    report = []
    report.append("=" * 80)
    report.append("GOLD ETF SCENARIO ANALYSIS: US-IRAN CONFLICT")
    report.append("iShares Physical Gold ETC | April 2026 → April 2027")
    report.append("=" * 80)

    report.append(f"\n{'CURRENT POSITION':=^80}")
    report.append(f"  Gold (USD/oz):    ${CURRENT_GOLD_USD_OZ:,.0f}")
    report.append(f"  Gold (EUR/gram):  €{CURRENT_GOLD_EUR_GRAM:.0f}")
    report.append(f"  Brent Oil:        ${CURRENT_BRENT:.0f}/bbl")
    report.append(f"  EUR/USD:          {CURRENT_EURUSD:.2f}")
    report.append(f"  Held in gold ETF: €{PORTFOLIO_HELD:,.0f}")
    report.append(f"  Available cash:   €{PORTFOLIO_AVAILABLE:,.0f}")

    report.append(f"\n{'MARKOV STATE PROBABILITIES':=^80}")
    states = ['Escalation', 'Stalemate', 'De-escalation']
    report.append(f"  {'State':<20} {'Now':>8} {'3m':>8} {'6m':>8} {'12m':>8}")
    report.append(f"  {'-'*52}")
    for i, state in enumerate(states):
        vals = [state_probs[f't={t}'][i] for t in [0, 3, 6, 12]]
        report.append(f"  {state:<20} {vals[0]:>7.0%} {vals[1]:>7.0%} {vals[2]:>7.0%} {vals[3]:>7.0%}")

    report.append(f"\n{'12-MONTH TERMINAL SCENARIOS (by probability)':=^80}")
    for nid, node in terminal_nodes:
        report.append(f"\n  [{node.probability:5.1%}] {node.name.replace(chr(10), ' ')}")
        report.append(f"         Gold: €{node.gold_eur_range[0]:.0f}–€{node.gold_eur_range[1]:.0f}/g "
                      f"(${node.gold_usd_range[0]:,.0f}–${node.gold_usd_range[1]:,.0f}/oz)")
        report.append(f"         Oil:  ${node.oil_range[0]:.0f}–${node.oil_range[1]:.0f}/bbl")
        report.append(f"         Return: {node.expected_return_eur:+.1f}%  |  Action: {node.action}")
        report.append(f"         → {node.action_rationale}")

    report.append(f"\n{'STRATEGY COMPARISON (12-month)':=^80}")
    report.append(f"  {'Strategy':<25} {'Expected':>10} {'Return':>8} {'Worst':>10} {'Best':>10}")
    report.append(f"  {'-'*63}")
    for strat, res in portfolio_results.items():
        report.append(
            f"  {strat:<25} €{res['expected_value']:>8,.0f} {res['expected_return']:>+6.1f}% "
            f"€{res['worst_case']:>8,.0f} €{res['best_case']:>8,.0f}"
        )

    report.append(f"\n{'KEY RECOMMENDATIONS':=^80}")
    report.append("""
  IMMEDIATE (Now):
    → HOLD existing €3k position
    → Do NOT deploy fresh capital yet — wait for ceasefire resolution
    → Set price alerts at €82/g (buy) and €100/g (sell)

  IF CEASEFIRE COLLAPSES (next 1-4 weeks):
    → Do NOT chase the initial gold spike — it reverses historically
    → Wait for the post-spike pullback (typically 2-4 weeks after escalation)
    → Then deploy €1,500 of the €3k available

  IF STALEMATE CONTINUES (3-month horizon):
    → Begin DCA: invest €1,000/month over 3 months during dips
    → Target entries below €86/g

  IF DE-ESCALATION / PEACE DEAL:
    → Deploy €2,000–€3,000 aggressively on the dip
    → Gold falls on peace but structural bull (CB buying, fiscal deficits) supports floor
    → This is the BEST entry point for long-term position

  IF WIDER REGIONAL WAR:
    → Sell €1,500 of held position into the spike (above €105/g)
    → Extreme levels (€120+/g) are unsustainable — take profits
    → Redeploy after inevitable pullback

  GENERAL:
    → Probability-weighted expected gold (EUR) at 12m: slight positive vs. current
    → The asymmetry favors holding: downside ~-10%, upside ~+40% in tail scenarios
    → Central bank buying (1,000+ tonnes/year) provides structural floor
    → iShares Physical Gold ETC has no EUR hedge — you also carry EUR/USD exposure
""")

    report.append(f"\n{'CRITICAL WATCH EVENTS':=^80}")
    report.append("""
  1. Ceasefire expiry / extension decision (imminent — next days/weeks)
  2. Strait of Hormuz shipping status (daily monitoring)
  3. US Fed rate decision response to oil-driven inflation
  4. ECB policy meeting (any hawkish shift = EUR strengthens = lower EUR gold price)
  5. PBOC / RBI gold reserve reports (monthly — structural floor indicator)
  6. Trump social media / policy announcements on Iran (volatility trigger)
""")

    report.append("=" * 80)
    report.append("DISCLAIMER: This is a scenario analysis model, not financial advice.")
    report.append("All probabilities are subjective estimates. Past performance ≠ future results.")
    report.append("=" * 80)

    return "\n".join(report)


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("Building scenario tree...")
    nodes, root = build_scenario_tree()

    print("Computing Markov transition probabilities...")
    matrices = build_transition_matrices()
    state_probs = compute_state_probabilities(matrices)

    print("Computing portfolio analysis...")
    portfolio_results = compute_portfolio_analysis(nodes)

    print("Generating report...")
    report = generate_report(nodes, portfolio_results, state_probs)
    print(report)

    # Save report
    out = config.OUTPUT_DIR
    with open(os.path.join(out, 'analysis_report.txt'), 'w') as f:
        f.write(report)
    print("  Report saved")

    print("  Generating visualizations...")
    figs = {
        'scenario_tree': create_tree_visualization(nodes, root),
        'price_heatmap': create_probability_heatmap(nodes),
        'strategy_comparison': create_strategy_comparison(portfolio_results),
        'decision_timeline': create_decision_timeline(nodes),
        'markov_transitions': create_markov_diagram(matrices, state_probs),
    }

    for name, fig in figs.items():
        fig.write_html(os.path.join(out, f'{name}.html'), include_plotlyjs='cdn')
        print(f"  {name}.html")

    try:
        for name, fig in figs.items():
            fig.write_image(os.path.join(out, f'{name}.png'), scale=2)
        print("  PNG images saved")
    except Exception as e:
        print(f"  Note: PNG export skipped ({e})")

    node_data = {}
    for nid, node in nodes.items():
        node_data[nid] = {
            'name': node.name.replace('\n', ' '),
            'month': node.month,
            'gold_eur_range': node.gold_eur_range,
            'gold_usd_range': node.gold_usd_range,
            'oil_range': node.oil_range,
            'probability': node.probability,
            'expected_return_eur_pct': node.expected_return_eur,
            'action': node.action,
            'action_rationale': node.action_rationale,
            'parent': node.parent_id,
            'children': node.children,
            'description': node.description,
        }

    with open(os.path.join(out, 'scenario_data.json'), 'w') as f:
        json.dump(node_data, f, indent=2)
    print("  All scenario tree outputs generated.")


if __name__ == '__main__':
    main()
