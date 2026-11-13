"""One-run baseline analysis of the original v11 R1/R2 cash-first engine.

This module does not alter the market-return sampler or payout calculation.
It selects a documented, fixed baseline and prepares a small, transparent
set of results for the simplified Streamlit dashboard.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from endowment_simulation_model import (
    SimulationConfig,
    institutional_params_from_data,
    liquidity_params_from_data,
    load_default_data,
    run_monte_carlo,
)
from r1_model import STRATEGIES

HORIZON = 5
START_YEAR = 2027
SEED = 42
BLOCK_QUARTERS = 4
INITIAL_REGIME = "High Inflation"
PAYOUT_DEADLINE_MONTHS = 3


@dataclass(frozen=True)
class BaselineOptions:
    institution: str = "Private"
    profile: str = "Base"
    strategy: str = "HRP"
    initial_endowment_m: float = 150.0
    paths: int = 1000


def validate_options(o: BaselineOptions):
    if o.institution not in ("Private", "Public"):
        raise ValueError("Institution must be Public or Private.")
    if o.profile not in ("Low", "Base", "High"):
        raise ValueError("R2 profile must be Low, Base, or High.")
    if o.strategy not in STRATEGIES:
        raise ValueError("Choose a strategy included in R1.")
    if not np.isfinite(o.initial_endowment_m) or o.initial_endowment_m <= 0:
        raise ValueError("Starting endowment must be positive.")
    if o.paths not in (100, 500, 1000, 5000):
        raise ValueError("Choose 100, 500, 1,000, or 5,000 simulation paths.")


SUMMARY_COLUMNS = [
    "path_id", "year", "beginning_assets", "portfolio_return", "investment_gain",
    "endowment_gifts", "planned_payout", "actual_payout", "payout_shortfall_amount",
    "earnings_gifts_coverage_gap", "return_coverage_shortfall_amount",
    "funding_capacity_for_payout", "payout_liquidity_coverage_ratio",
    "cash_before_sales", "actual_net_asset_sale_proceeds", "forced_sale_loss",
    "ending_cash", "ending_assets", "real_ending_assets", "real_actual_payout",
    "operating_expenses", "net_tuition", "other_operating_revenue",
    "required_support", "payout_support_gap", "accounting_residual",
]


def run_baseline(o: BaselineOptions):
    validate_options(o)
    data = load_default_data(
        institution_type=o.institution,
        allocation=INITIAL_REGIME,
        strategy=o.strategy,
    )
    institution = institutional_params_from_data(data, o.institution, o.profile)
    liquidity = liquidity_params_from_data(data,
        time_to_cash_months=PAYOUT_DEADLINE_MONTHS,
        liquidity_buffer_years=0.0,
        minimum_cash_reserve=0.0,
        other_annual_cash_need=0.0,
        liquid_share_haircut=0.0,
        forced_sale_discount=0.0,
    )
    config = SimulationConfig(
        initial_endowment=o.initial_endowment_m,
        prior_endowment_1y=o.initial_endowment_m,
        prior_endowment_2y=o.initial_endowment_m,
        horizon_years=HORIZON,
        start_year=START_YEAR,
        n_sims=o.paths,
        seed=SEED,
        return_method="R1 dynamic asset bootstrap",
        block_size_quarters=BLOCK_QUARTERS,
        annual_return_shift=0.0,
        volatility_multiplier=1.0,
        annual_inflation=None,
        alpha=0.95,
        real_corpus_threshold=1.0,
    )
    results = run_monte_carlo(data, config, institution, liquidity)
    annual = results['annual_results']
    if len(annual) != o.paths * HORIZON:
        raise AssertionError("Unexpected number of annual simulation records")
    if not np.isfinite(annual['accounting_residual']).all() or annual['accounting_residual'].abs().max() > 1e-6:
        raise AssertionError("Endowment cash-flow reconciliation failed")
    if not np.allclose(annual['planned_payout'] - annual['actual_payout'], annual['payout_shortfall_amount'], atol=1e-7):
        raise AssertionError("Payout shortfall calculation failed")
    if not np.allclose(annual['earnings_gifts_coverage_gap'],
                           np.maximum(0, annual['planned_payout'] - annual['investment_gain'] - annual['endowment_gifts']), atol=1e-7):
        raise AssertionError("Earnings-plus-gifts gap reconciliation failed")

    # Annual investment returns exclude gifts and payouts. Calculate CAGR per path first.
    path_returns = annual.pivot(index='path_id', columns='year', values='portfolio_return').sort_index()
    cagr = np.expm1(np.log1p(path_returns.to_numpy()).sum(axis=1) / HORIZON)
    return_by_path = path_returns.reset_index()
    return_by_path['five_year_cagr'] = cagr

    grouped = annual.groupby('year', sort=True)
    yearly = grouped.agg(
        mean_investment_return=('portfolio_return', 'mean'),
        mean_investment_gain_m=('investment_gain', 'mean'),
        mean_gifts_m=('endowment_gifts', 'mean'),
        mean_planned_payout_m=('planned_payout', 'mean'),
        mean_actual_payout_m=('actual_payout', 'mean'),
        mean_unpaid_payout_m=('payout_shortfall_amount', 'mean'),
        mean_earnings_gifts_gap_m=('earnings_gifts_coverage_gap', 'mean'),
        earnings_gifts_gap_frequency=('earnings_gifts_coverage_gap', lambda x: (x > 1e-10).mean()),
        median_liquidity_coverage_x=('payout_liquidity_coverage_ratio', 'median'),
        mean_support_gap_m=('payout_support_gap', 'mean'),
        median_real_endowment_m=('real_ending_assets', 'median'),
        median_real_payout_m=('real_actual_payout', 'median'),
    ).reset_index()
    yearly['real_endowment_p10_m'] = grouped['real_ending_assets'].quantile(.1).to_numpy()
    yearly['real_endowment_p90_m'] = grouped['real_ending_assets'].quantile(.9).to_numpy()
    yearly['real_payout_p10_m'] = grouped['real_actual_payout'].quantile(.1).to_numpy()
    yearly['real_payout_p90_m'] = grouped['real_actual_payout'].quantile(.9).to_numpy()

    return {
        'options': o,
        'institutional': institution,
        'metrics': results['metrics'],
        'yearly': yearly,
        'annual_detail': annual[SUMMARY_COLUMNS].copy(),
        'return_by_path': return_by_path,
        'return_stats': {
            'median_cagr': float(np.median(cagr)),
            'mean_cagr': float(np.mean(cagr)),
            'p05_cagr': float(np.quantile(cagr, .05)),
            'p95_cagr': float(np.quantile(cagr, .95)),
        },
    }
