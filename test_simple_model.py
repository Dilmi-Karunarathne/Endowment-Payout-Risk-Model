"""Checks the final single-run model and the requested risk outputs.

Run: python test_simple_model.py
"""
import numpy as np
from simple_analysis import BaselineOptions, run_baseline, validate_options, HORIZON, strategy_cash_requirements
from unittest.mock import patch


def assert_one(institution, profile, paths=100):
    # Developer-only short smoke runs; public app/API still strictly require 5k or 10k.
    with patch('simple_analysis.validate_options', lambda _: None):
        r = run_baseline(BaselineOptions(institution=institution, profile=profile, paths=paths))
    a, y, m = r['annual_detail'], r['yearly'], r['metrics']
    assert len(a) == paths * HORIZON
    assert len(r['return_by_path']) == paths
    assert len(y) == HORIZON
    cash_policy = strategy_cash_requirements(r['options'].strategy)
    for j, year in enumerate(sorted(a.year.unique())):
        v = a[a.year == year]
        expected = cash_policy['annual_capital_call_rate'] if j < cash_policy['capital_call_duration_years'] else 0.
        assert np.allclose(v.capital_call, expected * v.beginning_assets)
        assert np.allclose(v.reserve_target, cash_policy['reserve_years_of_planned_payout'] * v.planned_payout)
        assert np.allclose(v.capital_call - v.capital_call_paid, v.unpaid_capital_call)
        assert np.isclose(y.iloc[j].mean_r1_capital_call_requested_m, v.capital_call.mean())
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




def assert_path_bounds():
    """The user-facing model must accept exactly 5,000 or 10,000 paths."""
    for valid in (5000, 10000):
        validate_options(BaselineOptions(paths=valid))
    for invalid in (0, 100, 1000, 4999, 5001, 9999, 10001):
        try:
            validate_options(BaselineOptions(paths=invalid))
        except ValueError as exc:
            assert '5,000' in str(exc) and '10,000' in str(exc)
        else:
            raise AssertionError(f'Unexpected accepted simulation count {invalid}')
    print('User-facing simulation count restricted to 5,000 or 10,000: PASSED')


def assert_gift_earned_return_starts_in_year_after_receipt():
    """2027 gift earns zero that year, earns 2028 R1 investment income; never pays payouts."""
    from dataclasses import replace
    import pandas as pd
    from endowment_simulation_model import (load_default_data, institutional_params_from_data,
        liquidity_params_from_data, SimulationConfig, run_path)
    from r1_model import ASSETS
    data = load_default_data(strategy='HRP')
    inst = replace(institutional_params_from_data(data), gift_rate=.10, effective_spending_rate=.05)
    locked = np.zeros(len(ASSETS)); locked[ASSETS.index('venture_capital')] = 1.
    records=[]
    for yr, quarterly_return in ((2027, 0.0), (2028, 0.02)):
        q=dict(asset_returns=np.full(len(ASSETS), quarterly_return), return_add=0.,
               r1_condition='High Inflation', freeze_rebalance=True,
               targets=data.r1_targets.to_dict('index'))
        records.append(dict(year=yr, portfolio_return=(1+quarterly_return)**4-1,
                            inflation=0., dominant_condition='Normal', r1_records=[q]*4))
    cfg=SimulationConfig(initial_endowment=100., prior_endowment_1y=100.,
        prior_endowment_2y=100., horizon_years=2, n_sims=1)
    liquid=liquidity_params_from_data(data, ringfence_new_gifts=True,
        initial_asset_weights=tuple(locked), time_to_cash_months=3)
    path=run_path(pd.DataFrame(records), cfg, inst, liquid)
    first, second=path.iloc[0], path.iloc[1]
    assert np.isclose(first.endowment_gifts, 10.)
    assert np.isclose(first.restricted_gift_investment_gain, 0.)
    assert np.isclose(first.restricted_gift_assets_end, 10.)
    assert np.isclose(second.beginning_restricted_gift_assets, 10.)
    growth = 10. * ((1.02)**4-1)
    assert np.isclose(second.restricted_gift_investment_gain, growth, atol=1e-7)
    assert np.isclose(second.restricted_gift_assets_end,
                      10. + growth + second.endowment_gifts, atol=1e-7)
    assert np.isclose(first.gifts_available_for_payout, 0.)
    assert np.isclose(second.gifts_available_for_payout, 0.)
    assert np.allclose(path.actual_payout, 0.)
    assert np.allclose(path.spendable_assets_end+path.restricted_gift_assets_end, path.ending_assets)
    print(f'2027 restricted gift earns {growth:.6f}M in 2028 but cannot pay payouts: PASSED')


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

def assert_capital_calls_and_reserve_preserve_net_wealth():
    """Capital calls are internal investment transfers; reserve is not an expense."""
    import numpy as np
    from payout_funding import execute_r1_cash_first, CASH_INDEX, PE_INDEX, VC_INDEX
    from r1_model import ASSETS
    h=np.zeros(len(ASSETS)); h[CASH_INDEX]=100.
    result=execute_r1_cash_first(h,payout=5., capital_call=10.,reserve=5., months=3)
    assert np.isclose(result.actual_payout,5.)
    assert np.isclose(result.capital_paid,10.)
    assert np.isclose(result.holdings.sum(),95.)
    assert np.isclose(result.holdings[PE_INDEX]+result.holdings[VC_INDEX],10.)
    assert np.isclose(result.holdings[CASH_INDEX],85.)
    assert np.isclose(result.reserve_shortfall,0.)
    limited=np.zeros(len(ASSETS));limited[CASH_INDEX]=10.
    squeezed=execute_r1_cash_first(limited,payout=5.,capital_call=10.,reserve=5.,months=3)
    assert np.isclose(squeezed.actual_payout,0.)
    assert np.isclose(squeezed.capital_paid,5.)
    assert np.isclose(squeezed.capital_unpaid,5.)
    assert np.isclose(squeezed.holdings.sum(),10.)
    print('Capital-call transfer, reserve priority, and cash insufficiency: PASSED')


def assert_r1_cash_assumptions_by_strategy():
    from simple_analysis import strategy_cash_requirements
    from r1_model import STRATEGIES
    for strat in STRATEGIES:
        setting=strategy_cash_requirements(strat)
        assert setting['annual_capital_call_rate'] > 0
        assert setting['capital_call_duration_years'] == 3
        assert 0.5 <= setting['reserve_years_of_planned_payout'] <= 1.
    assert np.isclose(strategy_cash_requirements('HRP')['annual_capital_call_rate'],0.030356,atol=1e-6)
    assert np.isclose(strategy_cash_requirements('HRP')['reserve_years_of_planned_payout'],1.)
    print('All 9 strategy-specific R1 cash input tables: PASSED')


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
    assert_path_bounds()
    assert_gift_earned_return_starts_in_year_after_receipt()
    assert_capital_calls_and_reserve_preserve_net_wealth()
    assert_r1_cash_assumptions_by_strategy()
    assert_total_growth_can_hide_spendable_decline()
    assert_restricted_gifts_cannot_fund_locked_portfolio()
    assert_restricted_gifts_are_invested_but_never_sale_eligible()
    for institution in ('Private', 'Public'):
        for profile in ('Low', 'Base', 'High'):
            assert_one(institution, profile)
    print('All six profiles, restricted-gift controls, and risk outputs passed.')
