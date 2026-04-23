#!/usr/bin/env python3
"""
Prediction Tracker — Records predictions and validates against reality.

Each run:
1. Fetches current gold/oil/FX prices
2. Validates any past predictions whose target date has passed
3. Records new predictions for +3m, +6m, +12m
4. Computes cumulative model performance metrics
"""

import os
import sys
import json
import hashlib
from datetime import datetime, timedelta

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import config

try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False

HISTORY_FILE = os.path.join(config.DATA_DIR, 'prediction_history.json')


def load_history():
    """Load or initialize prediction history."""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return {
        'predictions': [],
        'validations': [],
        'metadata': {
            'created': datetime.now().isoformat(),
            'model_version': '1.0',
        }
    }


def save_history(history):
    """Save prediction history."""
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2, default=str)


def fetch_current_prices():
    """Fetch current market prices."""
    prices = {
        'gold_usd_oz': config.CURRENT_GOLD_USD_OZ,
        'brent_usd': config.CURRENT_BRENT,
        'eurusd': config.CURRENT_EURUSD,
        'gold_eur_gram': config.CURRENT_GOLD_EUR_GRAM,
    }

    if not HAS_YF:
        prices['source'] = 'config_fallback'
        return prices

    try:
        for sym, key in [('GC=F', 'gold_usd_oz'), ('BZ=F', 'brent_usd'), ('EURUSD=X', 'eurusd')]:
            d = yf.download(sym, period='5d', progress=False)
            if len(d) > 0:
                val = d['Close'].iloc[-1]
                prices[key] = float(val.iloc[0]) if hasattr(val, 'iloc') else float(val)

        prices['gold_eur_gram'] = prices['gold_usd_oz'] / prices['eurusd'] / 31.1035
        prices['source'] = 'yfinance_live'
    except Exception as e:
        prices['source'] = f'partial_fallback: {e}'

    return prices


def compute_model_hash():
    """Hash the model parameters so we can detect when they change."""
    params = {
        'transition_matrix': config.TRANSITION_MATRIX.tolist(),
        'initial_state_probs': config.INITIAL_STATE_PROBS.tolist(),
        'gold_eur_returns': {k: list(v) for k, v in config.GOLD_EUR_RETURNS.items()},
    }
    return hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()[:12]


def generate_predictions(prices):
    """Generate Monte Carlo predictions for +3m, +6m, +12m."""
    n_sim = 10_000  # Faster than full MC, enough for tracking
    n_quarters = 4

    states = np.zeros((n_sim, n_quarters + 1), dtype=int)
    states[:, 0] = np.random.choice(5, size=n_sim, p=config.INITIAL_STATE_PROBS)
    returns = np.zeros((n_sim, n_quarters))

    for q in range(n_quarters):
        for s in range(5):
            mask = states[:, q] == s
            n = mask.sum()
            if n == 0:
                continue
            states[mask, q + 1] = np.random.choice(5, size=n, p=config.TRANSITION_MATRIX[s])

        for s in range(5):
            mask = states[:, q + 1] == s
            n = mask.sum()
            if n == 0:
                continue
            mean, std = config.GOLD_EUR_RETURNS[config.STATES[s]]
            returns[mask, q] = np.random.normal(mean, std, size=n)

    cum_factors = np.cumprod(1 + returns, axis=1)
    current_gold = prices['gold_eur_gram']

    predictions = {}
    for q, label in [(0, '3m'), (1, '6m'), (3, '12m')]:
        factors = cum_factors[:, q]
        price_dist = current_gold * factors
        predictions[label] = {
            'target_date': (datetime.now() + timedelta(days=(q + 1) * 91)).strftime('%Y-%m-%d'),
            'mean': round(float(np.mean(price_dist)), 2),
            'median': round(float(np.median(price_dist)), 2),
            'p10': round(float(np.percentile(price_dist, 10)), 2),
            'p25': round(float(np.percentile(price_dist, 25)), 2),
            'p75': round(float(np.percentile(price_dist, 75)), 2),
            'p90': round(float(np.percentile(price_dist, 90)), 2),
            'prob_above_current': round(float((factors > 1.0).mean()), 4),
        }

    return predictions


def validate_past_predictions(history, current_prices):
    """Check past predictions against current reality."""
    today = datetime.now().strftime('%Y-%m-%d')
    actual_gold = current_prices['gold_eur_gram']
    new_validations = []

    for pred in history['predictions']:
        for horizon in ['3m', '6m', '12m']:
            if horizon not in pred.get('predictions', {}):
                continue

            target_date = pred['predictions'][horizon]['target_date']
            pred_id = f"{pred['date']}_{horizon}"

            # Already validated?
            if any(v['pred_id'] == pred_id for v in history['validations']):
                continue

            # Target date passed?
            if target_date > today:
                continue

            predicted_mean = pred['predictions'][horizon]['mean']
            predicted_p25 = pred['predictions'][horizon]['p25']
            predicted_p75 = pred['predictions'][horizon]['p75']
            predicted_p10 = pred['predictions'][horizon]['p10']
            predicted_p90 = pred['predictions'][horizon]['p90']

            error_pct = ((actual_gold - predicted_mean) / predicted_mean) * 100
            within_iqr = predicted_p25 <= actual_gold <= predicted_p75
            within_80 = predicted_p10 <= actual_gold <= predicted_p90

            # Directional accuracy
            was_above_current = pred['actual_gold_eur_gram']
            predicted_direction = 'up' if predicted_mean > was_above_current else 'down'
            actual_direction = 'up' if actual_gold > was_above_current else 'down'
            direction_correct = predicted_direction == actual_direction

            validation = {
                'pred_id': pred_id,
                'validation_date': today,
                'prediction_date': pred['date'],
                'horizon': horizon,
                'predicted_mean': predicted_mean,
                'predicted_iqr': [predicted_p25, predicted_p75],
                'actual': round(actual_gold, 2),
                'error_pct': round(error_pct, 2),
                'within_iqr': within_iqr,
                'within_80pct_band': within_80,
                'direction_correct': direction_correct,
            }
            new_validations.append(validation)

    return new_validations


def compute_performance_metrics(history):
    """Compute cumulative model performance metrics."""
    validations = history.get('validations', [])

    if not validations:
        return {
            'n_validated': 0,
            'status': 'No predictions validated yet — run again after 3+ months',
        }

    n = len(validations)
    errors = [abs(v['error_pct']) for v in validations]
    iqr_hits = sum(1 for v in validations if v['within_iqr'])
    band_hits = sum(1 for v in validations if v['within_80pct_band'])
    dir_hits = sum(1 for v in validations if v['direction_correct'])

    return {
        'n_validated': n,
        'mean_abs_error_pct': round(np.mean(errors), 2),
        'median_abs_error_pct': round(np.median(errors), 2),
        'pct_within_iqr': round(iqr_hits / n * 100, 1),
        'pct_within_80_band': round(band_hits / n * 100, 1),
        'directional_accuracy_pct': round(dir_hits / n * 100, 1),
        'status': 'Tracking',
    }


def main():
    print("Loading prediction history...")
    history = load_history()

    print("Fetching current prices...")
    prices = fetch_current_prices()
    print(f"  Gold: €{prices['gold_eur_gram']:.1f}/g  |  "
          f"${prices['gold_usd_oz']:,.0f}/oz  |  "
          f"Brent: ${prices['brent_usd']:.0f}  |  "
          f"EUR/USD: {prices['eurusd']:.3f}")
    print(f"  Source: {prices['source']}")

    # Validate past predictions
    new_validations = validate_past_predictions(history, prices)
    if new_validations:
        history['validations'].extend(new_validations)
        print(f"  Validated {len(new_validations)} past prediction(s)")
    else:
        print("  No past predictions due for validation yet")

    # Generate new predictions
    print("Generating predictions...")
    predictions = generate_predictions(prices)

    entry = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'timestamp': datetime.now().isoformat(),
        'actual_gold_eur_gram': round(prices['gold_eur_gram'], 2),
        'actual_gold_usd_oz': round(prices['gold_usd_oz'], 2),
        'actual_brent': round(prices['brent_usd'], 2),
        'actual_eurusd': round(prices['eurusd'], 4),
        'model_hash': compute_model_hash(),
        'predictions': predictions,
    }

    history['predictions'].append(entry)
    history['metadata']['last_updated'] = datetime.now().isoformat()
    history['metadata']['n_predictions'] = len(history['predictions'])

    # Compute performance
    metrics = compute_performance_metrics(history)

    # Save
    save_history(history)
    print(f"  Prediction recorded. Total: {len(history['predictions'])} snapshots")

    # Also save metrics for README generator
    metrics_file = os.path.join(config.DATA_DIR, 'model_metrics.json')
    with open(metrics_file, 'w') as f:
        json.dump({
            'metrics': metrics,
            'latest_prices': prices,
            'latest_predictions': predictions,
            'run_date': datetime.now().isoformat(),
        }, f, indent=2, default=str)
    print(f"  Metrics saved to {metrics_file}")

    # Print summary
    print(f"\n  Predictions (gold EUR/g):")
    for h, p in predictions.items():
        print(f"    {h}: €{p['mean']:.1f} "
              f"[€{p['p25']:.1f}–€{p['p75']:.1f}] "
              f"P(up)={p['prob_above_current']:.0%}")

    if metrics['n_validated'] > 0:
        print(f"\n  Model Performance ({metrics['n_validated']} validated):")
        print(f"    Mean error: {metrics['mean_abs_error_pct']:.1f}%")
        print(f"    Within IQR: {metrics['pct_within_iqr']:.0f}%")
        print(f"    Direction:  {metrics['directional_accuracy_pct']:.0f}%")
    else:
        print(f"\n  {metrics['status']}")


if __name__ == '__main__':
    main()
