"""Checks the final single-run model and the requested risk outputs.

Run: python test_simple_model.py
"""
import numpy as np
from simple_analysis import BaselineOptions, run_baseline, HORIZON


def assert_one(institution, profile, paths=100):
    r = run_baseline(BaselineOptions(institution=institution, profile=profile, paths=paths))
    a, y, m = r['annual_detail'], r['yearly'], r['metrics']
    assert len(a) == paths * HORIZON
    assert len(r['return_by_path']) == paths
    assert len(y) == HORIZON
    assert a.accounting_residual.abs().max() < 1e-7
    assert np.allclose(a.planned_payout - a.actual_payout, a.payout_shortfall_amount)
    assert (a.actual_payout <= a.planned_payout + 1e-7).all()
    assert np.allclose(a.earnings_gifts_coverage_gap,
        np.maximum(0.0, a.planned_payout - a.investment_gain - a.endowment_gifts))
    assert np.allclose(a.return_coverage_shortfall_amount,
        np.maximum(0.0, a.planned_payout - a.investment_gain))
    assert np.allclose(a.gifts_available_for_payout, 0.0)
    assert np.allclose(a.restricted_gifts_received, a.endowment_gifts)
    assert np.allclose(a.spendable_assets_end + a.restricted_gift_assets_end, a.ending_assets)
    assert np.allclose(a.beginning_spendable_assets + a.beginning_restricted_gift_assets, a.beginning_assets)
    assert np.allclose(a.spendable_investment_gain + a.restricted_gift_investment_gain, a.investment_gain)
    assert np.allclose(a.spendable_earnings_coverage_gap,
        np.maximum(0.0, a.planned_payout - a.spendable_investment_gain))
    assert np.allclose(y.mean_spendable_earnings_gap_m,
        a.groupby('year').spendable_earnings_coverage_gap.mean().to_numpy())
    assert np.allclose(a.real_spendable_assets_end + a.real_restricted_gift_assets_end, a.real_ending_assets)
    assert np.allclose(a.restricted_gift_assets_end, a.beginning_restricted_gift_assets + a.restricted_gift_investment_gain + a.endowment_gifts)
    assert np.allclose(a.spendable_assets_end, a.beginning_spendable_assets + a.spendable_investment_gain
        + a.other_endowment_changes - a.actual_payout - a.other_cash_paid - a.forced_sale_loss)
    assert np.allclose(y.mean_total_assets_m, y.mean_spendable_assets_m + y.mean_restricted_gift_assets_m)
    assert np.allclose(y.mean_real_total_assets_m, y.mean_real_spendable_assets_m + y.mean_real_restricted_gift_assets_m)
    assert np.isclose(r['probability_spendable_real_erosion'], a.groupby('path_id').real_spendable_assets_end.apply(
        lambda x: (x < r['options'].initial_endowment_m-1e-10).any()).mean())
    assert (a.restricted_gift_assets_end >= -1e-9).all()
    assert np.allclose(a.payout_support_gap,
        np.maximum(0.0, a.required_support - a.actual_payout))
    assert np.allclose(y.mean_shortfall_deviation_m, -y.mean_unpaid_payout_m, atol=1e-10)
    assert np.all(y.worst_shortfall_deviation_m <= y.mean_shortfall_deviation_m + 1e-9)
    for year, group in a.groupby('year'):
        assert np.isclose(y.loc[y.year == year].iloc[0].mean_earnings_only_gap_m,
            group.return_coverage_shortfall_amount.mean())
        out = y.loc[y.year == year].iloc[0]
        eg = group.earnings_gifts_coverage_gap
        sp = group.payout_support_gap
        expected_eg_positive = eg[eg > 1e-10].mean() if (eg > 1e-10).any() else 0.0
        expected_sp_positive = sp[sp > 1e-10].mean() if (sp > 1e-10).any() else 0.0
        assert np.isclose(out.mean_earnings_gifts_gap_when_positive_m, expected_eg_positive)
        assert np.isclose(out.mean_support_gap_when_positive_m, expected_sp_positive)
        assert np.isclose(out.earnings_gifts_gap_frequency, (eg > 1e-10).mean())
        assert np.isclose(out.support_gap_year_frequency, (sp > 1e-10).mean())
    terminal = a.groupby('path_id').real_ending_assets.last().to_numpy()
    losses = np.maximum(0, 1 - terminal / r['options'].initial_endowment_m)
    es = np.sort(losses)[-int(np.ceil(.05 * paths)):].mean()
    assert np.isclose(m['purchasing_power_expected_shortfall_pct_initial'], es)
    path_shortfall_prob = a.groupby('path_id').payout_shortfall_amount.apply(lambda v: (v > 1e-10).any()).mean()
    path_erosion_prob = a.groupby('path_id').real_ending_assets.apply(
        lambda v: (v < r['options'].initial_endowment_m - 1e-10).any()).mean()
    path_support_prob = a.groupby('path_id').payout_support_gap.apply(lambda v: (v > 1e-10).any()).mean()
    assert np.isclose(m['probability_at_least_one_shortfall'], path_shortfall_prob)
    assert np.isclose(m['probability_real_corpus_erosion'], path_erosion_prob)
    assert np.isclose(m['probability_any_support_gap'], path_support_prob)
    print(f'{institution}/{profile}: payout risk {path_shortfall_prob:.1%}, '
          f'real erosion {path_erosion_prob:.1%}, support risk {path_support_prob:.1%}, '
          f'95% real ES {es:.1%}')
    return r




def assert_restricted_gifts_cannot_fund_locked_portfolio():
    """One-year zero-market test: gifts arrive, but VC is not saleable in 3m."""
    from dataclasses import replace
    import pandas as pd
    from endowment_simulation_model import (load_default_data, institutional_params_from_data,
        liquidity_params_from_data, SimulationConfig, run_path)
    from r1_model import ASSETS

    data = load_default_data(strategy='HRP')
    inst = replace(institutional_params_from_data(data), gift_rate=0.10,
        effective_spending_rate=0.05)
    locked = np.zeros(len(ASSETS))
    locked[ASSETS.index('venture_capital')] = 1.0
    cfg = SimulationConfig(initial_endowment=100, prior_endowment_1y=100,
        prior_endowment_2y=100, horizon_years=1, n_sims=1)
    q = dict(asset_returns=np.zeros(len(ASSETS)), return_add=0.,
             r1_condition='High Inflation', freeze_rebalance=True,
             targets=data.r1_targets.to_dict('index'))
    market = pd.DataFrame([dict(year=2027, portfolio_return=0.0,
        inflation=0.0, dominant_condition='Normal', r1_records=[q]*4)])
    common = dict(initial_asset_weights=tuple(locked),time_to_cash_months=3,
        liquidity_buffer_years=0.,minimum_cash_reserve=0.)
    with_restrictions = run_path(market,cfg,inst,
        liquidity_params_from_data(data,ringfence_new_gifts=True,**common)).iloc[0]
    unrestricted = run_path(market,cfg,inst,
        liquidity_params_from_data(data,ringfence_new_gifts=False,**common)).iloc[0]
    assert np.isclose(with_restrictions.endowment_gifts, 10)
    assert np.isclose(with_restrictions.restricted_gift_assets_end, 10)
    assert np.isclose(with_restrictions.actual_payout, 0)
    assert np.isclose(with_restrictions.payout_shortfall_amount, 5)
    assert np.isclose(with_restrictions.gifts_available_for_payout, 0)
    assert np.isclose(with_restrictions.ending_assets, 110)
    assert np.isclose(unrestricted.actual_payout,5)
    assert np.isclose(unrestricted.ending_assets,105)
    print('Segregated gifts cannot fund payout from illiquid opening portfolio: PASSED')


def assert_restricted_gifts_are_invested_but_never_sale_eligible():
    """Multi-year test: restricted gifts earn market returns but do not leak to payouts."""
    import pandas as pd
    from dataclasses import replace
    from endowment_simulation_model import (load_default_data, institutional_params_from_data,
        liquidity_params_from_data, SimulationConfig, run_path)
    from r1_model import ASSETS
    data = load_default_data(strategy='HRP')
    inst = replace(institutional_params_from_data(data), gift_rate=.05, effective_spending_rate=.05)
    locked = np.zeros(len(ASSETS)); locked[ASSETS.index('venture_capital')] = 1.
    q = dict(asset_returns=np.full(len(ASSETS),.02), return_add=0.,
             r1_condition='High Inflation', freeze_rebalance=True,
             targets=data.r1_targets.to_dict('index'))
    market = pd.DataFrame([dict(year=2027+t, portfolio_return=.02,
        inflation=0.0, dominant_condition='Normal', r1_records=[q]*4) for t in range(2)])
    cfg = SimulationConfig(initial_endowment=100, prior_endowment_1y=100,
        prior_endowment_2y=100, horizon_years=2, n_sims=1)
    liquidity = liquidity_params_from_data(data,ringfence_new_gifts=True,
        initial_asset_weights=tuple(locked),time_to_cash_months=3)
    path=run_path(market,cfg,inst,liquidity)
    assert (path.actual_payout < 1e-7).all()
    assert (path.gifts_available_for_payout == 0).all()
    assert path.restricted_gift_assets_end.iloc[1] > path.restricted_gift_assets_end.iloc[0]
    assert np.allclose(path.spendable_assets_end + path.restricted_gift_assets_end, path.ending_assets)
    print('Segregated gifts remain excluded across years and earn R1 returns: PASSED')

def assert_total_growth_can_hide_spendable_decline():
    """If gifts grow restricted wealth, total can increase while spendable falls."""
    from dataclasses import replace
    import pandas as pd
    from endowment_simulation_model import (load_default_data, institutional_params_from_data,
        liquidity_params_from_data, SimulationConfig, run_path)
    from r1_model import ASSETS
    data = load_default_data(strategy='HRP')
    inst = replace(institutional_params_from_data(data), gift_rate=0.10,
        effective_spending_rate=0.05)
    starting = np.zeros(len(ASSETS))
    starting[ASSETS.index('cash_tbill')]=1.0
    cfg = SimulationConfig(initial_endowment=100, prior_endowment_1y=100,
        prior_endowment_2y=100, horizon_years=1, n_sims=1)
    quarterly=dict(asset_returns=np.zeros(len(ASSETS)), return_add=0.,
        r1_condition='High Inflation', freeze_rebalance=True,
        targets=data.r1_targets.to_dict('index'))
    market=pd.DataFrame([dict(year=2027, portfolio_return=0., inflation=0.,
        dominant_condition='Normal', r1_records=[quarterly]*4)])
    liquidity=liquidity_params_from_data(data,ringfence_new_gifts=True,
        initial_asset_weights=tuple(starting), time_to_cash_months=3)
    row=run_path(market,cfg,inst,liquidity).iloc[0]
    assert np.isclose(row.actual_payout,5.)
    assert np.isclose(row.ending_assets,105.)
    assert np.isclose(row.spendable_assets_end,95.)
    assert np.isclose(row.restricted_gift_assets_end,10.)
    assert np.isclose(row.spendable_investment_gain,0.)
    assert np.isclose(row.restricted_gift_investment_gain,0.)
    print('Total can grow from restricted gifts even as spendable funds decline: PASSED')


if __name__ == '__main__':
    assert_total_growth_can_hide_spendable_decline()
    assert_restricted_gifts_cannot_fund_locked_portfolio()
    assert_restricted_gifts_are_invested_but_never_sale_eligible()
    for institution in ('Private', 'Public'):
        for profile in ('Low', 'Base', 'High'):
            assert_one(institution, profile)
    print('All six profiles, restricted-gift controls, and risk outputs passed.')
