"""Policy comparisons and data-backed allocation construction."""
from dataclasses import replace
import numpy as np
import pandas as pd
from endowment_simulation_model import run_monte_carlo
from portfolio_return_simulation import checked_history


def portfolio_from_assets(asset_history, weights, condition_history):
    required = {'asset', 'weight', 'liquidity_class'}
    if not required.issubset(weights.columns) or 'quarter' not in asset_history:
        raise ValueError('Weights need asset,weight,liquidity_class; returns need quarter plus asset columns.')
    if weights.asset.duplicated().any() or weights.empty:
        raise ValueError('Each asset must appear once in the weights.')
    w = weights.set_index('asset')['weight'].astype(float)
    if not np.isfinite(w).all() or (w < 0).any() or not np.isclose(w.sum(), 1., atol=1e-8):
        raise ValueError('Weights must be finite, nonnegative and sum to 1.')
    allowed = {'Very High', 'High', 'Moderate', 'Low', 'Very Low'}
    if not set(weights.liquidity_class).issubset(allowed):
        raise ValueError('Unknown liquidity class.')
    missing = set(w.index) - set(asset_history.columns)
    if missing:
        raise ValueError('Missing asset-return columns: ' + ', '.join(sorted(missing)))
    a = asset_history[list(w.index)].astype(float)
    if not np.isfinite(a).all().all() or (a <= -1).any().any():
        raise ValueError('Asset returns must be finite decimal quarterly returns above -100%.')
    history = pd.DataFrame({'quarter': asset_history.quarter.astype(str), 'p4_return': a.to_numpy() @ w.to_numpy()})
    # Fixed weights imply cost-free quarterly rebalancing of the return benchmark.
    history = history.merge(condition_history[['quarter', 'condition', 'cpi_yoy']], on='quarter', how='left', validate='one_to_one')
    history = checked_history(history)
    if history.condition.isna().any():
        raise ValueError('Every quarter needs a matching economic-condition label in bundled data.')
    liquid = float(weights.loc[weights.liquidity_class.isin(['Very High', 'High']), 'weight'].sum())
    illiquid = float(weights.loc[weights.liquidity_class.isin(['Low', 'Very Low']), 'weight'].sum())
    return history, liquid, illiquid


def policy_cases(config, institution, liquidity, alternate_spending_rate=.04, buffer_years=.5):
    return {
        'Anchor policy': (config, institution, liquidity),
        'Current-assets spending': (config, replace(institution, spending_rule='Current assets'), liquidity),
        'Alternative spending rate': (config, replace(institution, effective_spending_rate=alternate_spending_rate), liquidity),
        'Reserve buffer': (config, institution, replace(liquidity, enabled=True, liquidity_buffer_years=buffer_years)),
    }


def comparison_row(label, result):
    m = result['metrics']
    return {'Scenario': label,
        'Annual return-coverage shortfall': m['annual_coverage_shortfall_probability'],
        'Pr(any payout funding shortfall)': m['probability_at_least_one_shortfall'],
        'Annual payout funding shortfall': m['annual_shortfall_probability'],
        'Conditional funding depth': m['average_relative_shortfall_depth'],
        'Median longest coverage spell (years)': m['median_longest_coverage_spell'],
        'Median longest funding spell (years)': m['median_longest_funding_spell'],
        'Pr(real corpus erosion)': m['probability_real_corpus_erosion'],
        'Median terminal real corpus ($M)': m['median_terminal_real_assets'],
        'Median cumulative real payouts ($M)': m['median_cumulative_real_payout'],
        'Terminal real-corpus ES': m['expected_shortfall_terminal_real_corpus_loss'],
        'Pr(unpaid other obligation)': m['probability_unpaid_other_obligation']}


def compare_cases(data, cases, history=None):
    rows = []
    for label, (c, i, l) in cases.items():
        rows.append(comparison_row(label, run_monte_carlo(data, c, i, l, p4_history=history, keep_paths=False)))
    return pd.DataFrame(rows)
