"""Validation of scenarios against the simplified financial framework."""
from dataclasses import replace
from unittest.mock import patch
import numpy as np
import pandas as pd
import pytest

import test_simple_model as original
from scenario_analysis import *
from simple_analysis import run_baseline
from endowment_simulation_model import quarterly_to_annual,run_path
from investment_model import draw_path,invest_year,liquidity_inputs,PAYOUT_LIQUID,RESTRICTED_IN_SEVERE

@pytest.fixture(autouse=True)
def allow_short_validation_runs():
    # The public application still requires 5,000/10,000. Small runs exercise
    # accounting and overlay boundaries without changing the public contract.
    with patch('simple_analysis.validate_options',lambda _:None):yield


def test_unchanged_baseline_and_neutral_scenario():
    options=BaselineOptions(paths=8)
    a=run_baseline(options)
    b=run_scenario(options,Scenario())
    c=run_scenario(options,Scenario('No changes'))
    pd.testing.assert_frame_equal(a['annual_detail'],b['annual_detail'])
    pd.testing.assert_frame_equal(a['annual_detail'],c['annual_detail'])


@pytest.mark.parametrize('institution',['Private','Public'])
@pytest.mark.parametrize('profile',['Low','Base','High'])
def test_all_institutional_profiles(institution,profile):
    original.assert_one(institution,profile,paths=8)


@pytest.mark.parametrize('strategy',list(STRATEGY_LABELS))
@pytest.mark.parametrize('institution',['Private','Public'])
def test_main_stress_cases_each_institution_and_strategy(institution,strategy):
    lib=stress_library(institution,'Severe')
    suite=run_suite(BaselineOptions(institution=institution,strategy=strategy,paths=8),
        [lib['High inflation & elevated rates'],lib['Prolonged downturn & liquidity pressure']])
    for (_,name),r in suite['cases'].items():
        a=r['annual_detail']
        assert a.accounting_residual.abs().max()<1e-7
        assert (a.actual_payout<=a.planned_payout+1e-9).all()
        assert (a.liquidity_breach_20pct<=a.investment_liquidity_breach).all()
        assert np.allclose(a.restricted_gift_assets_end+a.spendable_assets_end,a.ending_assets)
        assert (a.gifts_available_for_payout==0).all()
        if r['metrics']['probability_at_least_one_shortfall']==0:
            assert r['metrics']['average_shortfall_amount']==0
    row=suite['comparison'].iloc[0]
    assert row['Change in unpaid payout risk (pp)']==0
    assert row['Mean paired change in real endowment ($M)']==0


@pytest.mark.parametrize('severity',['Standard','Severe'])
def test_every_stress_preset(severity):
    suite=run_suite(BaselineOptions(paths=3),list(stress_library(severity=severity).values()))
    assert len(suite['cases'])==12


def test_every_what_if_preset_and_custom():
    cases=list(what_if_library().values())+[
        Scenario('Custom','Custom',annual_return_shift=-.02,return_shift_years=2,
        inflation_add=.01,inflation_years=2,gift_multiplier=.8,gift_years=2,
        reserve_years=.5,spending_rate=.04,spending_years=2,freeze_public_years=1,
        capital_call_multiplier=1.5)]
    suite=run_suite(BaselineOptions(paths=4),cases)
    assert len(suite['cases'])==10
    json.loads(settings_json(suite))
    no_gifts=suite['cases'][('HRP','No new gifts')]['annual_detail']
    assert (no_gifts.restricted_gift_assets_end==0).all()
    policy=suite['cases'][('HRP','Spending rate: 4%')]['annual_detail']
    assert np.allclose(policy[policy.year==2027].planned_payout,6.)
    assert (policy.planned_payout<=policy.beginning_assets*.05+1e-8).all()
    assert (policy.planned_payout>=policy.beginning_assets*.03-1e-8).all()


def test_replay_assets_inflation_and_untouched_tail():
    o=BaselineOptions(paths=1)
    data,cfg,*_=prepare_inputs(o)
    q=draw_path(np.random.default_rng(100),data,cfg)
    s=stress_library()['2008–09 crisis replay']
    before=np.stack(q.asset_returns).copy()
    changed=make_path_transform(data,s)(None,q)
    expected=data.investment_joint.set_index('quarter').loc[list(GFC)]
    np.testing.assert_array_equal(np.stack(changed.asset_returns)[:6],expected[ASSETS].to_numpy())
    np.testing.assert_array_equal(changed.cpi_quarter.iloc[:6],expected.cpi_quarter)
    np.testing.assert_array_equal(np.stack(changed.asset_returns)[6:],before[6:])
    np.testing.assert_array_equal(np.stack(q.asset_returns),before)
    annual=quarterly_to_annual(changed,2027)
    assert np.isclose(annual.iloc[0].inflation,np.prod(1+expected.cpi_quarter.iloc[:4])-1)


def test_shock_applied_once_to_asset_returns():
    data,cfg,*_=prepare_inputs(BaselineOptions(paths=1))
    q=draw_path(np.random.default_rng(8),data,cfg)
    s=Scenario('Shock',asset_shocks={a:-.2 for a in ASSETS})
    changed=make_path_transform(data,s)(None,q)
    assert np.allclose(changed.asset_returns.iloc[0],(1+q.asset_returns.iloc[0])*.8-1)
    assert np.allclose(np.stack(changed.asset_returns)[1:],np.stack(q.asset_returns)[1:])


def test_duration_and_no_capital_call_double_count():
    o=BaselineOptions(paths=1)
    data,cfg,inst,liq,base,policy=prepare_inputs(o)
    s=stress_library('Private','Severe')['Prolonged downturn & liquidity pressure']
    ov=build_overrides(base,inst,policy,s)
    assert np.allclose(ov.capital_call_rate.iloc[:4],policy['annual_capital_call_rate']*1.5)
    assert ov.capital_call_rate.iloc[4]==0
    assert ov.restrict_em_hy.tolist()==[1,1,0,0,0]
    assert ov.gift_multiplier.tolist()==[.57,.57,1,1,1]
    market=stress_library()['High inflation & elevated rates']
    ov=build_overrides(base,inst,policy,market)
    assert np.allclose(ov.capital_call_rate,base.capital_call_rate)
    q=draw_path(np.random.default_rng(10),data,cfg)
    changed=make_path_transform(data,market)(None,q)
    assert np.allclose(changed.return_add.iloc[:4],0)
    assert np.allclose(changed.return_add.iloc[4:16],-.02/4)
    assert np.allclose(changed.return_add.iloc[16:],0)
    assert np.allclose(changed.cpi_quarter.iloc[16:],q.cpi_quarter.iloc[16:])


def test_frozen_assets_cannot_escape_via_rebalance():
    data,cfg,*_=prepare_inputs(BaselineOptions(paths=1))
    h=np.zeros(len(ASSETS)); h[3]=40;h[6]=20;h[11]=40
    targets={state:{a:float(a=='cash_tbill') for a in ASSETS} for state in REGIMES}
    record=dict(investment_condition='Normal',targets=targets,asset_returns=np.zeros(len(ASSETS)),return_add=0)
    out=invest_year(h,[record],liquidity_inputs()[0],PAYOUT_LIQUID,restrict_em_hy=True)
    assert np.array_equal(out[0][RESTRICTED_IN_SEVERE],h[RESTRICTED_IN_SEVERE])
    assert np.isclose(out[0].sum(),100)


def test_matched_asset_paths_across_strategies():
    ref=None
    s=stress_library()['High inflation & elevated rates']
    for strategy in ['HRP','MinVar','MeanCVaR']:
        data,cfg,*_=prepare_inputs(BaselineOptions(strategy=strategy,paths=1))
        q=draw_path(np.random.default_rng(234),data,cfg)
        q=make_path_transform(data,s)(None,q)
        value=np.column_stack([np.stack(q.asset_returns),q.cpi_quarter])
        if ref is not None:np.testing.assert_array_equal(value,ref)
        ref=value


def test_expense_only_stress_and_recovery():
    o=BaselineOptions(paths=2)
    base=run_scenario(o,Scenario())
    s=Scenario('Expenses',expense_growth=.0945,expense_years=1)
    test=run_scenario(o,s)
    a,b=base['annual_detail'],test['annual_detail']
    ratio=(1+.0945)/(1+base['institutional'].annual_expense_growth)
    assert np.allclose(b.operating_expenses/a.operating_expenses,ratio)
    assert np.allclose(a.ending_assets,b.ending_assets)
    assert (b.required_support>=a.required_support).all()


@pytest.mark.parametrize('scenario',[
    Scenario('Invalid',gift_multiplier=-1,gift_years=1),
    Scenario('Invalid',reserve_years=float('nan')),
    Scenario('Invalid',spending_rate=.07,spending_years=1),
    Scenario('Invalid',replay_quarters=GFC,asset_shocks={'cash_tbill':-.1}),
    Scenario('Invalid',regime='Recession',regime_quarters=1.5),
    Scenario('Invalid',annual_return_shift=-.02),
    Scenario('Baseline',gift_multiplier=0,gift_years=5),
])
def test_invalid_scenarios_rejected(scenario):
    with pytest.raises(ValueError):validate_scenario(scenario)


def test_existing_gift_and_cash_accounting():
    original.assert_gift_earned_return_starts_in_year_after_receipt()
    original.assert_capital_calls_and_reserve_preserve_net_wealth()
    original.assert_restricted_gifts_cannot_fund_locked_portfolio()
    original.assert_restricted_gifts_are_invested_but_never_sale_eligible()
    original.assert_total_growth_can_hide_spendable_decline()
