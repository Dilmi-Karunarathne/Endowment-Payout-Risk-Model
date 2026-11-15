"""Focus on the November 2026 portfolio inputs and restored payout risk outputs."""
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
import pytest
from investment_model import ASSETS, STRATEGIES, inputs, crisis_liquidity_weights, draw_path
from simple_analysis import BaselineOptions, run_baseline, strategy_cash_requirements
from endowment_simulation_model import load_default_data, SimulationConfig
from scenario_analysis import make_path_transform, stress_library
from dashboard_contract import validate_result_schema

@pytest.mark.parametrize('strategy',STRATEGIES)
def test_ten_portfolios_have_valid_handoff_inputs(strategy):
    h,w,t,j=inputs(strategy,'Calm')
    assert len(h)==102 and len(j)==102
    assert len(ASSETS)==13
    assert list(t.index)==['Calm','Turbulent']
    assert np.isclose(w.weight.sum(),1)
    assert np.allclose(t.sum(axis=1),1)
    assert (t.to_numpy()>=-1e-10).all()
    assert j.market_regime.isin(['Calm','Turbulent']).all()
    if strategy.endswith('_Static'):
        np.testing.assert_allclose(t.loc['Calm'],t.loc['Turbulent'])
    policy=strategy_cash_requirements(strategy)
    assert .01 < policy['annual_capital_call_rate'] < .09
    assert policy['capital_call_duration_years']==3
    assert policy['reserve_years_of_planned_payout'] in (.25,1.0)


def test_research_liquidity_definitions_distinct_and_consistent():
    h,w,t,j=inputs('HRP_Dynamic','Calm')
    handoff=Path(__file__).parent/'data'/'investment'
    liq=pd.read_csv(handoff/'liquidity_data_datateam.csv').set_index('asset_id').loc[ASSETS]
    g=crisis_liquidity_weights()
    np.testing.assert_allclose(g,liq['Crisis_Value_g_Aug_2026'])
    assert not np.allclose(g,liq['Stressed_1m_Weight_h'])
    assert np.dot(t.loc['Calm'],g)>=.2 - 1e-7


def test_replay_switches_dynamic_portfolio_to_turbulent_weights():
    d=load_default_data(strategy='MeanCVaR_Dynamic',allocation='Calm')
    cfg=SimulationConfig(return_method='Investment dynamic asset bootstrap')
    q=draw_path(np.random.default_rng(5),d,cfg)
    stressed=make_path_transform(d,stress_library()['2008–09 crisis replay'])(None,q)
    assert set(stressed.investment_condition.iloc[:6])=={'Turbulent'}
    assert set(stressed.targets.iloc[0])=={'Calm','Turbulent'}


@pytest.mark.parametrize('institution',('Private','Public'))
@pytest.mark.parametrize('strategy',('HRP_Dynamic','MeanCVaR_Dynamic','EqualWeight_Dynamic','PeerCVaR_Static'))
def test_risk_measures_are_available_for_both_institutions(institution,strategy):
    with patch('simple_analysis.validate_options',lambda _:None):
        r=run_baseline(BaselineOptions(institution=institution,strategy=strategy,paths=12))
    ok,msg=validate_result_schema(r)
    assert ok,msg
    assert 'probability_total_real_erosion' in r
    assert 'probability_spendable_real_erosion' in r
    m=r['metrics']
    for k in ['probability_at_least_one_shortfall','probability_any_support_gap',
              'purchasing_power_expected_shortfall_pct_initial',
              'probability_r1_crisis_liquidity_breach_20pct']:
        assert 0<=m[k]<=1
    assert m['probability_liquid_share_below_20pct'] <=m['probability_investment_liquidity_breach']+1e-10
    a=r['annual_detail']
    assert (a['research1_crisis_breach_20pct'].isin([0,1])).all()
    assert np.allclose(a.ending_assets,a.spendable_assets_end+a.restricted_gift_assets_end)
    assert np.allclose(a.payout_shortfall_amount,np.maximum(0,a.planned_payout-a.actual_payout))

