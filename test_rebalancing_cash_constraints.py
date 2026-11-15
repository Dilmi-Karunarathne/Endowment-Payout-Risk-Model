"""Regression tests for the rare no-liquid-cash quarterly rebalancing failure."""
import numpy as np
import pytest

from investment_model import (
    ASSETS, REGIMES, PRIVATE, RESTRICTED_IN_SEVERE, PAYOUT_LIQUID,
    feasible_rebalance, invest_year, liquidity_inputs,
)

CASH = ASSETS.index('cash_tbill')
PE = ASSETS.index('private_equity')
VC = ASSETS.index('venture_capital')
HF = ASSETS.index('hedge_funds')
EM = ASSETS.index('emerging_markets')
HY = ASSETS.index('high_yield_fixed_income')


def _one_quarter(holdings, *, state='Turbulent', restrict=False, target=None):
    if target is None:
        target = np.zeros(len(ASSETS))
        target[PE] = 0.5
        target[VC] = 0.25
        target[HF] = 0.15
        target[CASH] = 0.10
    targets = {regime: dict(zip(ASSETS, target)) for regime in REGIMES}
    record = dict(investment_condition=state, targets=targets,
                  asset_returns=np.zeros(len(ASSETS)), return_add=0)
    out = invest_year(holdings, [record], liquidity_inputs()[0], PAYOUT_LIQUID,
                      stress_costs=True, restrict_em_hy=restrict)
    return out[0], out[4]


def test_all_private_assets_and_zero_cash_trading_is_safely_deferred():
    h = np.zeros(len(ASSETS))
    h[PE], h[VC], h[HF] = 61., 31., 8.
    end, cost = _one_quarter(h)
    np.testing.assert_allclose(end, h, rtol=0, atol=1e-9)
    assert cost == 0


def test_depleted_liquid_assets_no_crash_or_hidden_private_sales():
    h = np.zeros(len(ASSETS))
    h[PE], h[VC], h[HF], h[CASH] = 58.06, 30.98, 17.60, 0.001
    end, cost = _one_quarter(h)
    assert (end >= -1e-10).all()
    assert end[PE] >= h[PE] - 1e-9
    assert end[VC] >= h[VC] - 1e-9
    assert end[HF] >= h[HF] - 1e-9
    assert np.isclose(end.sum(), h.sum()-cost, atol=1e-8)
    assert cost <= h[CASH] + 1e-8


def test_extreme_rebalance_is_scaled_to_affordable_cash():
    h = np.zeros(len(ASSETS)); h[PE]=58; h[VC]=31; h[HF]=19; h[CASH]=.1
    target=np.zeros(len(ASSETS));target[PE]=80; target[VC]=40;target[HF]=40;target[CASH]=.1
    rates=np.zeros(len(ASSETS));rates[CASH]=.05
    post, fee, fraction=feasible_rebalance(
        h,target,locked=[PE,VC,HF],frozen=[],rates=rates,fee_payers=[CASH])
    assert 0 <= fraction <= 1
    assert post[PE] >= h[PE]
    assert post[VC] >= h[VC]
    assert post[HF] >= h[HF]
    assert fee <= post[CASH]+1e-9
    assert np.isclose(post.sum(),h.sum(),atol=1e-9)


def test_eligible_cash_cost_is_not_duplicated():
    h = np.zeros(len(ASSETS));h[CASH]=45.;h[ASSETS.index('treasuries')]=55.
    target=np.zeros(len(ASSETS));target[CASH]=5;target[ASSETS.index('treasuries')]=95.
    rates=np.zeros(len(ASSETS));rates[CASH]=.01;rates[ASSETS.index('treasuries')]=.02
    post,fee,fraction=feasible_rebalance(h,target,locked=[PE,VC],frozen=[],rates=rates,
        fee_payers=[CASH,ASSETS.index('treasuries')])
    assert fraction==1
    assert np.isclose(fee,1.2)
    assert np.isclose(post.sum(),100)


def test_emerging_market_high_yield_frozen_during_funding_stress():
    h=np.zeros(len(ASSETS));h[PE]=40;h[VC]=30;h[HF]=10;h[EM]=10;h[HY]=9;h[CASH]=1
    end,cost=_one_quarter(h,restrict=True)
    assert end[EM]==h[EM] and end[HY]==h[HY]
    assert (end[[PE,VC,HF]]>=h[[PE,VC,HF]]-1e-9).all()
    assert np.isclose(end.sum(), h.sum()-cost,atol=1e-8)
