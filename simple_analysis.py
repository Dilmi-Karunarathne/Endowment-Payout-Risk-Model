"""Single-run R1/R2 analysis with a segregated, nonspendable new-gift pool.

New gifts are credited after the annual investment period and therefore earn
asset-level R1 returns starting in the following year. Gifts and all investment
returns on them remain segregated from payout funding during the five years.
Existing opening assets remain eligible only subject to R1 sale constraints.
"""
from dataclasses import dataclass
from pathlib import Path
from functools import lru_cache

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
from dashboard_contract import RESULT_SCHEMA_VERSION

HORIZON = 5
START_YEAR = 2027
SEED = 42
BLOCK_QUARTERS = 4
INITIAL_REGIME = "High Inflation"
PAYOUT_DEADLINE_MONTHS = 3

@lru_cache(maxsize=1)
def r1_cash_requirement_table():
    """R1 handoff liquidity profile; calls/reserve are proxies, not observed liabilities."""
    path = Path(__file__).resolve().parent / 'data/r1/r1_cash_requirements_by_strategy.csv'
    table = pd.read_csv(path).set_index('strategy')
    if set(STRATEGIES) != set(table.index) or not table.index.is_unique:
        raise ValueError('R1 strategy cash-requirements table must cover all nine strategies')
    for column in ('r1_capital_call_rate_of_beginning_assets', 'r1_reserve_years_of_payout', 'r1_capital_call_duration_years'):
        if not np.isfinite(table[column].to_numpy(dtype=float)).all() or (table[column] < 0).any():
            raise ValueError('Invalid R1 cash assumption: '+column)
    return table


def strategy_cash_requirements(strategy: str):
    row = r1_cash_requirement_table().loc[strategy]
    return {
        'strategy': strategy,
        'annual_capital_call_rate': float(row['r1_capital_call_rate_of_beginning_assets']),
        'capital_call_duration_years': int(row['r1_capital_call_duration_years']),
        'reserve_years_of_planned_payout': float(row['r1_reserve_years_of_payout']),
        'private_equity_and_vc_weight': float(row['private_equity_and_vc_weight']),
    }


@dataclass(frozen=True)
class BaselineOptions:
    institution: str = "Private"
    profile: str = "Base"
    strategy: str = "HRP"
    initial_endowment_m: float = 150.0
    paths: int = 5000


def validate_options(o: BaselineOptions):
    if o.institution not in ("Private", "Public"):
        raise ValueError("Institution must be Public or Private.")
    if o.profile not in ("Low", "Base", "High"):
        raise ValueError("R2 profile must be Low, Base, or High.")
    if o.strategy not in STRATEGIES:
        raise ValueError("Choose a strategy included in R1.")
    if not np.isfinite(o.initial_endowment_m) or o.initial_endowment_m <= 0:
        raise ValueError("Starting endowment must be positive.")
    if o.paths not in (5000, 10000):
        raise ValueError("Choose 5,000 or 10,000 simulation paths (minimum 5,000; maximum 10,000).")


SUMMARY_COLUMNS = [
    "path_id", "year", "beginning_assets", "portfolio_return", "investment_gain",
    "endowment_gifts", "restricted_gifts_received", "gifts_available_for_payout",
    "beginning_spendable_assets", "beginning_restricted_gift_assets",
    "spendable_investment_gain", "restricted_gift_investment_gain",
    "restricted_gift_assets_end", "spendable_assets_end",
    "real_spendable_assets_end", "real_restricted_gift_assets_end",
    "planned_payout", "actual_payout", "payout_shortfall_amount",
    "earnings_gifts_coverage_gap", "return_coverage_shortfall_amount",
    "spendable_earnings_coverage_gap",
    "funding_capacity_for_payout", "payout_liquidity_coverage_ratio",
    "cash_before_sales", "actual_net_asset_sale_proceeds", "forced_sale_loss",
    "capital_call", "capital_call_paid", "unpaid_capital_call",
    "reserve_target", "reserve_shortfall",
    "other_endowment_changes", "other_cash_paid",
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
    r1_cash_policy = strategy_cash_requirements(o.strategy)
    capital_call_overrides = pd.DataFrame({
        'capital_call_rate': [r1_cash_policy['annual_capital_call_rate']
                              if t < r1_cash_policy['capital_call_duration_years'] else 0.
                              for t in range(HORIZON)]
    })
    liquidity = liquidity_params_from_data(data,
        time_to_cash_months=PAYOUT_DEADLINE_MONTHS,
        liquidity_buffer_years=r1_cash_policy["reserve_years_of_planned_payout"],
        minimum_cash_reserve=0.0,
        other_annual_cash_need=0.0,
        liquid_share_haircut=0.0,
        forced_sale_discount=0.0,
        ringfence_new_gifts=True,
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
    results = run_monte_carlo(data, config, institution, liquidity,
                              year_overrides=capital_call_overrides)
    annual = results['annual_results']
    if len(annual) != o.paths * HORIZON:
        raise AssertionError("Unexpected number of annual simulation records")
    if not np.isfinite(annual['accounting_residual']).all() or annual['accounting_residual'].abs().max() > 1e-6:
        raise AssertionError("Endowment cash-flow reconciliation failed")
    if not np.allclose(annual['planned_payout'] - annual['actual_payout'], annual['payout_shortfall_amount'], atol=1e-7):
        raise AssertionError("Payout shortfall calculation failed")
    if not np.allclose(annual['earnings_gifts_coverage_gap'],
                           np.maximum(0, annual['planned_payout'] - annual['investment_gain'] - annual['endowment_gifts']), atol=1e-7):
        raise AssertionError("Earnings-plus-gifts diagnostic reconciliation failed")
    if not np.allclose(annual['return_coverage_shortfall_amount'],
                           np.maximum(0, annual['planned_payout'] - annual['investment_gain']), atol=1e-7):
        raise AssertionError("Earnings-only coverage gap reconciliation failed")
    if not np.allclose(annual['spendable_earnings_coverage_gap'],
                           np.maximum(0, annual['planned_payout'] - annual['spendable_investment_gain']), atol=1e-7):
        raise AssertionError('Eligible-pool investment earnings gap reconciliation failed')
    if not np.allclose(annual['beginning_spendable_assets'] + annual['beginning_restricted_gift_assets'],
                       annual['beginning_assets'], atol=1e-7):
        raise AssertionError('Opening asset pools do not reconcile')
    if not np.allclose(annual['spendable_investment_gain'] + annual['restricted_gift_investment_gain'],
                       annual['investment_gain'], atol=1e-7):
        raise AssertionError('Investment gains by pool do not reconcile')
    if not np.allclose(annual['spendable_assets_end'] + annual['restricted_gift_assets_end'],
                       annual['ending_assets'], atol=1e-7):
        raise AssertionError('Closing asset pools do not reconcile')
    if not np.allclose(annual['real_spendable_assets_end'] + annual['real_restricted_gift_assets_end'],
                       annual['real_ending_assets'], atol=1e-7):
        raise AssertionError('Real asset pools do not reconcile')
    # Cash-first liquidation costs reduce the existing/spendable investment pool;
    # restricted gifts and their gains remain ring-fenced.
    if not np.allclose(annual['restricted_gift_assets_end'],
                       annual['beginning_restricted_gift_assets']
                       + annual['restricted_gift_investment_gain'] + annual['endowment_gifts'], atol=1e-7):
        raise AssertionError('Gift pool roll-forward does not reconcile')
    if not np.allclose(annual['spendable_assets_end'],
                       annual['beginning_spendable_assets'] + annual['spendable_investment_gain']
                       + annual['other_endowment_changes'] - annual['actual_payout']
                       - annual['other_cash_paid'] - annual['forced_sale_loss'], atol=1e-6):
        raise AssertionError('Spendable pool roll-forward does not reconcile')
    if not (annual['gifts_available_for_payout'].abs() < 1e-10).all():
        raise AssertionError('Newly received gifts incorrectly made payout-eligible')
    if not np.allclose(annual['restricted_gifts_received'], annual['endowment_gifts']):
        raise AssertionError('Gift restrictions mismatch')
    if not np.allclose(annual['restricted_gift_assets_end'] + annual['spendable_assets_end'], annual['ending_assets'], atol=1e-7):
        raise AssertionError('Segregated portfolio ledgers do not sum to endowment wealth')

    # R1 strategy-specific funding assumptions are applied in every path-year.
    for j, year in enumerate(range(START_YEAR, START_YEAR+HORIZON)):
        records = annual[annual.year == year]
        rate = float(capital_call_overrides.iloc[j]['capital_call_rate'])
        if not np.allclose(records['capital_call'], records['beginning_assets'] * rate, atol=1e-8):
            raise AssertionError('R1 capital-call proxy was not applied as scheduled')
        if not np.allclose(records['reserve_target'], records['planned_payout'] * r1_cash_policy['reserve_years_of_planned_payout'], atol=1e-8):
            raise AssertionError('R1 strategy-specific payout reserve was not applied')
        if not np.allclose(records['capital_call'] - records['capital_call_paid'], records['unpaid_capital_call'], atol=1e-7):
            raise AssertionError('Capital-call cash accounting failed')
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
        mean_spendable_earnings_gap_m=('spendable_earnings_coverage_gap', 'mean'),
        spendable_earnings_gap_frequency=('spendable_earnings_coverage_gap', lambda x: (x > 1e-10).mean()),
        mean_earnings_only_gap_m=('return_coverage_shortfall_amount', 'mean'),
        earnings_only_gap_frequency=('return_coverage_shortfall_amount', lambda x: (x > 1e-10).mean()),
        mean_earnings_gifts_gap_m=('earnings_gifts_coverage_gap', 'mean'),
        mean_restricted_gift_assets_m=('restricted_gift_assets_end', 'mean'),
        mean_spendable_assets_m=('spendable_assets_end', 'mean'),
        mean_total_assets_m=('ending_assets', 'mean'),
        mean_real_total_assets_m=('real_ending_assets', 'mean'),
        mean_real_spendable_assets_m=('real_spendable_assets_end', 'mean'),
        mean_real_restricted_gift_assets_m=('real_restricted_gift_assets_end', 'mean'),
        mean_spendable_investment_gain_m=('spendable_investment_gain', 'mean'),
        mean_restricted_gift_investment_gain_m=('restricted_gift_investment_gain', 'mean'),
        mean_asset_sale_cost_m=('forced_sale_loss', 'mean'),
        mean_r1_capital_call_requested_m=('capital_call', 'mean'),
        mean_r1_capital_call_paid_m=('capital_call_paid', 'mean'),
        mean_r1_capital_call_unpaid_m=('unpaid_capital_call', 'mean'),
        mean_r1_reserve_target_m=('reserve_target', 'mean'),
        mean_r1_reserve_shortfall_m=('reserve_shortfall', 'mean'),
        mean_net_asset_sales_m=('actual_net_asset_sale_proceeds', 'mean'),
        earnings_gifts_gap_frequency=('earnings_gifts_coverage_gap', lambda x: (x > 1e-10).mean()),
        median_liquidity_coverage_x=('payout_liquidity_coverage_ratio', 'median'),
        mean_support_gap_m=('payout_support_gap', 'mean'),
        median_real_endowment_m=('real_ending_assets', 'median'),
        median_real_payout_m=('real_actual_payout', 'median'),
    ).reset_index()
    # Means decompose exactly; medians of different pools usually do NOT add
    # to the median of their total. Use means for the three-pool reconciliation.
    if not np.allclose(yearly['mean_spendable_assets_m'] + yearly['mean_restricted_gift_assets_m'],
                       yearly['mean_total_assets_m'], atol=1e-7):
        raise AssertionError('Annual mean nominal asset pools fail to reconcile')
    if not np.allclose(yearly['mean_real_spendable_assets_m'] + yearly['mean_real_restricted_gift_assets_m'],
                       yearly['mean_real_total_assets_m'], atol=1e-7):
        raise AssertionError('Annual mean real asset pools fail to reconcile')
    yearly['real_spendable_assets_p10_m'] = grouped['real_spendable_assets_end'].quantile(.1).to_numpy()
    yearly['real_spendable_assets_p90_m'] = grouped['real_spendable_assets_end'].quantile(.9).to_numpy()
    yearly['median_real_spendable_assets_m'] = grouped['real_spendable_assets_end'].median().to_numpy()
    yearly['median_real_restricted_assets_m'] = grouped['real_restricted_gift_assets_end'].median().to_numpy()
    yearly['real_endowment_p10_m'] = grouped['real_ending_assets'].quantile(.1).to_numpy()
    yearly['real_endowment_p90_m'] = grouped['real_ending_assets'].quantile(.9).to_numpy()
    yearly['real_payout_p10_m'] = grouped['real_actual_payout'].quantile(.1).to_numpy()
    yearly['real_payout_p90_m'] = grouped['real_actual_payout'].quantile(.9).to_numpy()

    # RISK OUTPUTS: explicit event-conditioned dollar gaps and path-based risks.
    # An earnings-plus-gifts gap is an economic coverage diagnostic, NOT
    # evidence that liquid cash is unavailable or an actual payout went unpaid.
    yearly['mean_shortfall_deviation_m'] = (grouped['actual_payout'].mean()
        - grouped['planned_payout'].mean()).to_numpy()
    yearly['worst_shortfall_deviation_m'] = annual.assign(
        _payout_deviation=annual['actual_payout'] - annual['planned_payout']
    ).groupby('year', sort=True)['_payout_deviation'].min().to_numpy()
    yearly['funding_shortfall_year_frequency'] = grouped['payout_shortfall_indicator'].mean().to_numpy()
    yearly['mean_spendable_earnings_gap_when_positive_m'] = grouped['spendable_earnings_coverage_gap'].apply(
        lambda x: float(x[x > 1e-10].mean()) if (x > 1e-10).any() else 0.0).to_numpy()
    yearly['mean_earnings_only_gap_when_positive_m'] = grouped['return_coverage_shortfall_amount'].apply(
        lambda x: float(x[x > 1e-10].mean()) if (x > 1e-10).any() else 0.0).to_numpy()
    yearly['mean_earnings_gifts_gap_when_positive_m'] = grouped['earnings_gifts_coverage_gap'].apply(
        lambda x: float(x[x > 1e-10].mean()) if (x > 1e-10).any() else 0.0).to_numpy()
    yearly['support_gap_year_frequency'] = grouped['payout_support_gap'].apply(
        lambda x: float((x > 1e-10).mean())).to_numpy()
    yearly['mean_support_gap_when_positive_m'] = grouped['payout_support_gap'].apply(
        lambda x: float(x[x > 1e-10].mean()) if (x > 1e-10).any() else 0.0).to_numpy()

    # Confirm that the displayed 95% purchasing-power Expected Shortfall is
    # the mean of the worst 5% of terminal real losses / initial endowment.
    terminal_real = annual.sort_values('year').groupby('path_id')['real_ending_assets'].last()
    losses = np.maximum(0.0, 1.0 - terminal_real.to_numpy()/o.initial_endowment_m)
    worst_count = max(1, int(np.ceil(.05 * len(losses)-1e-12)))
    computed_es95 = float(np.sort(losses)[-worst_count:].mean())
    reported_es95 = results['metrics']['purchasing_power_expected_shortfall_pct_initial']
    if not np.isclose(computed_es95, reported_es95, atol=1e-10):
        raise AssertionError('Purchasing-power Expected Shortfall does not reconcile')
    if not np.isclose(yearly['mean_shortfall_deviation_m'].to_numpy(),
                      -yearly['mean_unpaid_payout_m'].to_numpy(), atol=1e-9).all():
        raise AssertionError('Unpaid payout deviation does not reconcile')

    spendable_real_erosion_by_path = (annual['real_spendable_assets_end'] <
        o.initial_endowment_m - 1e-10).groupby(annual['path_id']).any()
    spendable_real_erosion_prob = float(spendable_real_erosion_by_path.mean())

    return {
        'result_schema_version': RESULT_SCHEMA_VERSION,
        'probability_spendable_real_erosion': spendable_real_erosion_prob,
        'options': o,
        'institutional': institution,
        'r1_cash_policy': r1_cash_policy,
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
