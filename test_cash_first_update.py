"""Independent examples validating the new asset-specific payout-funding approach."""
import numpy as np
import pandas as pd
import pytest
from dataclasses import replace
from r1_model import ASSETS
from payout_funding import execute_r1_cash_first
from endowment_simulation_model import (SimulationConfig, load_default_data,
    institutional_params_from_data, liquidity_params_from_data, run_path, run_monte_carlo)


def holdings(**positions):
    h = np.zeros(len(ASSETS))
    for name, amount in positions.items():
        h[ASSETS.index(name)] = amount
    return h


def test_illiquid_endowment_cannot_fund_payout():
    h = holdings(private_equity=100.)
    r = execute_r1_cash_first(h, payout=5., months=3)
    assert r.actual_payout == 0.
    assert r.gross_sales == 0.
    assert r.holdings.sum() == pytest.approx(100.)
    assert r.funding_capacity == 0.


def test_cash_first_sell_only_net_needed_and_charge_cost_once():
    h = holdings(cash_tbill=2., investment_grade_corporate_bonds=58., private_equity=40.)
    r = execute_r1_cash_first(h, payout=5., months=3)
    expected_gross = 3. / (1 - .0015)
    assert r.actual_payout == pytest.approx(5.)
    assert r.sales_by_asset[ASSETS.index('investment_grade_corporate_bonds')] == pytest.approx(expected_gross)
    assert r.sale_cost == pytest.approx(expected_gross*.0015)
    assert r.holdings.sum() == pytest.approx(95. - r.sale_cost)
    assert r.holdings[ASSETS.index('private_equity')] == pytest.approx(40.)
    assert r.holdings[ASSETS.index('cash_tbill')] == pytest.approx(0.)


def test_stressed_lockup_and_sale_deadline():
    h = holdings(hedge_funds=20., private_equity=20., cash_tbill=0.)
    normal3 = execute_r1_cash_first(h, payout=5., months=3)
    stress3 = execute_r1_cash_first(h, payout=5., months=3, stressed=True)
    stress12 = execute_r1_cash_first(h, payout=5., months=12, stressed=True)
    assert normal3.actual_payout == pytest.approx(5.)
    assert stress3.actual_payout == 0.
    assert stress12.actual_payout == pytest.approx(5.)
    assert stress3.holdings.sum() == pytest.approx(40.)


def test_capital_calls_are_transfers_and_can_crowd_out_payouts():
    h = holdings(cash_tbill=4., private_equity=96.)
    r = execute_r1_cash_first(h, payout=5., capital_call=3., months=3)
    assert r.capital_paid == pytest.approx(3.)
    assert r.actual_payout == pytest.approx(1.)
    assert r.holdings.sum() == pytest.approx(99.)
    assert r.holdings[ASSETS.index('private_equity')] == pytest.approx(99.)


def test_protected_cash_reserve_makes_payout_unavailable():
    h = holdings(cash_tbill=5., venture_capital=95.)
    r = execute_r1_cash_first(h, payout=5., reserve=3., months=3)
    assert r.actual_payout == pytest.approx(2.)
    assert r.holdings[ASSETS.index('cash_tbill')] == pytest.approx(3.)


def test_r1_path_honors_cash_availability_without_fictitious_private_sales():
    data=load_default_data()
    i=replace(institutional_params_from_data(data), gift_rate=0.)
    l=replace(liquidity_params_from_data(data),
              initial_asset_weights=tuple(holdings(private_equity=1.0)),
              cash_share=0., liquid_share=0., illiquid_share=1., hedge_share=0.)
    c=SimulationConfig(initial_endowment=100.,prior_endowment_1y=100.,prior_endowment_2y=100.,horizon_years=1)
    market=pd.DataFrame({'year':[2027],'portfolio_return':[0.],'inflation':[0.],'dominant_condition':['Normal']})
    a=run_path(market,c,i,l).iloc[0]
    assert a.beginning_assets == 100.
    assert a.pre_payout_assets == 100.
    assert a.planned_payout > 0.
    assert a.actual_payout == 0.
    assert a.payout_shortfall_amount == pytest.approx(a.planned_payout)
    assert a.ending_private_equity == pytest.approx(100.)
    assert a.accounting_residual == pytest.approx(0.)


def test_earnings_and_gifts_gap_does_not_equal_cash_shortfall():
    data=load_default_data()
    i=institutional_params_from_data(data)
    l=liquidity_params_from_data(data)
    c=SimulationConfig(horizon_years=1,n_sims=1)
    market=pd.DataFrame({'year':[2027],'portfolio_return':[.02],'inflation':[0.],'dominant_condition':['Normal']})
    a=run_path(market,c,i,l).iloc[0]
    assert a.earnings_gifts_coverage_gap == pytest.approx(max(0.,a.planned_payout-a.investment_gain-a.endowment_gifts))
    assert a.actual_payout == pytest.approx(a.planned_payout)
    assert a.payout_shortfall_amount == 0.


def test_updated_monte_carlo_metrics_and_reconciliation():
    data=load_default_data()
    r=run_monte_carlo(data,SimulationConfig(n_sims=12,horizon_years=3,seed=42),
        institutional_params_from_data(data),liquidity_params_from_data(data))
    m=r['metrics']; a=r['annual_results']
    assert abs(a.accounting_residual).max()<1e-7
    assert np.allclose(a.planned_payout-a.actual_payout,a.payout_shortfall_amount)
    assert np.allclose(a.earnings_gifts_coverage_gap,
                       np.maximum(0.,a.planned_payout-a.investment_gain-a.endowment_gifts))
    assert (a['sale_private_equity'] == 0).all() and (a['sale_venture_capital'] == 0).all()
    for name in ('probability_any_support_gap','conditional_average_support_gap_m',
                 'purchasing_power_expected_shortfall_pct_initial',
                 'median_minimum_payout_liquidity_coverage_ratio'):
        assert name in m and np.isfinite(m[name])
    assert m['purchasing_power_expected_shortfall_pct_initial'] == m['expected_shortfall_terminal_real_corpus_loss']


def test_quarterly_rebalance_cannot_redeem_locked_private_assets():
    from r1_model import invest_year, liquidity_inputs, PAYOUT_LIQUID
    h=holdings(private_equity=50., venture_capital=20., cash_tbill=30.)
    target={a:0. for a in ASSETS}
    target['us_large_cap']=1.
    rec={'r1_condition':'Normal','targets':{'Normal':target},
         'asset_returns':np.zeros(len(ASSETS))}
    final, _, _, _, cost = invest_year(h,[rec],liquidity_inputs()[0],PAYOUT_LIQUID)
    assert final[ASSETS.index('private_equity')] == pytest.approx(50.)
    assert final[ASSETS.index('venture_capital')] == pytest.approx(20.)
    assert final.sum() == pytest.approx(100.-cost)


def test_gate_prevents_asset_sales_even_if_total_wealth_is_high():
    h=holdings(cash_tbill=1., us_large_cap=50., private_equity=49.)
    r=execute_r1_cash_first(h,payout=5.,months=3,restriction=1.)
    assert r.actual_payout == pytest.approx(1.)
    assert r.funding_capacity == pytest.approx(1.)
    assert r.holdings.sum() == pytest.approx(99.)
