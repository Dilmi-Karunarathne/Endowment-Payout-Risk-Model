"""Focused tests of scenario impact and policy-under-stress features."""
from dataclasses import replace, asdict
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from simple_analysis import BaselineOptions
from scenario_analysis import (
    Scenario, stress_library, policy_response_library, run_suite,
    funding_duration_diagnostics, _longest_true_streak, build_overrides,
    prepare_inputs,
)


@pytest.fixture(autouse=True)
def short_dev_only_runs():
    # Public UI remains restricted to 5,000 or 10,000 paths per case.
    with patch('simple_analysis.validate_options', lambda _o: None):
        yield


def test_consecutive_year_counts_are_path_level_not_annual_probabilities():
    flags=np.array([[1,1,0,1,0], [0,0,0,0,0], [0,1,1,1,0]])
    np.testing.assert_array_equal(_longest_true_streak(flags),[2,0,3])
    assert _longest_true_streak(flags).shape==(3,)


def test_first_year_failure_and_earnings_gap_diagnostics():
    years=np.arange(2027,2032)
    a=pd.DataFrame([{'year':year,'path_id':pid,
        'payout_shortfall_amount':(.7 if ((pid==0 and year in (2028,2029)) or (pid==1 and year==2030)) else 0.),
        'spendable_earnings_coverage_gap':(1. if ((pid==0 and year in (2027,2028,2029)) or (pid==2 and year==2030)) else 0.)}
        for pid in range(3) for year in years])
    info=funding_duration_diagnostics(a)
    assert info['Median first unpaid-payout year, when any']==2029
    assert np.isclose(info['Probability of 2+ consecutive unpaid-payout years (%)'],100/3)
    assert np.isclose(info['Probability of 2+ consecutive earnings gaps (%)'],100/3)
    assert np.isclose(info['Mean total unpaid payout per path ($M)'],.7)
    assert np.isclose(info['Mean total unpaid payout when at least one occurs ($M)'],1.05)


def test_scenario_policy_preserves_exact_stress_parameters():
    for institution,target in [('Private',.04),('Public',.035)]:
        standard=stress_library(institution,'Severe')['Prolonged downturn & liquidity pressure']
        policy=policy_response_library(institution,'Severe')["Lower spending during stress"]
        assert policy.policy_reference==standard.name
        assert policy.spending_rate==target
        assert policy.spending_years==5
        assert policy.replay_quarters==standard.replay_quarters
        for attribute in ('annual_return_shift','inflation_add','return_shift_years',
            'inflation_years','gift_multiplier','gift_years','expense_growth',
            'capital_call_multiplier','capital_call_years','liquidity_stress_years',
            'freeze_public_years'):
            assert getattr(policy,attribute)==getattr(standard,attribute)
        reserve=policy_response_library(institution,'Severe')["Protect a 1.5-year payout reserve"]
        assert reserve.reserve_years==1.5
        assert reserve.spending_rate==standard.spending_rate


def test_stress_responses_run_and_return_paired_incremental_measures():
    for institution in ('Private','Public'):
        stress=stress_library(institution,'Severe')['Prolonged downturn & liquidity pressure']
        policy=policy_response_library(institution,'Severe')['Lower spending during stress']
        result=run_suite(BaselineOptions(institution=institution,paths=12),[stress,policy],strategies=['HRP_Dynamic'])
        table=result['comparison']
        assert len(table)==3
        assert table.loc[0,'Change in annualized return (pp)']==0
        assert table.loc[0,'Change in unpaid payout risk (pp)']==0
        policy_row=table.iloc[-1]
        assert policy_row['Policy reference']==stress.name
        for metric in ['Change in unpaid payout risk (pp)','Change in minimum liquidity buffer (×)',
                       'Change in purchasing-power ES 95% (pp)',
                       'Change in mean cumulative real payouts ($M)']:
            delta=policy_row['Policy vs same stress: '+metric]
            assert np.isfinite(delta)
            assert np.isclose(delta,policy_row[metric]-table.iloc[1][metric])
        s=result['cases'][('HRP_Dynamic',stress.name)]['annual_detail']
        p=result['cases'][('HRP_Dynamic',policy.name)]['annual_detail']
        np.testing.assert_array_equal(s.inflation,p.inflation)
        assert (p.loc[p.year==2027,'planned_payout'].to_numpy()
                <s.loc[s.year==2027,'planned_payout'].to_numpy()).all()
        for data in (p,s):
            assert data.accounting_residual.abs().max()<1e-7
            assert (data.actual_payout<=data.planned_payout+1e-9).all()
            assert (data.liquidity_breach_20pct<=data.investment_liquidity_breach).all()


def test_policy_comparison_requires_unchanged_stress_case():
    response=policy_response_library()['Lower spending during stress']
    with pytest.raises(ValueError,match='Include the unchanged stress'):
        run_suite(BaselineOptions(paths=2),[response])
    stress=stress_library()['Prolonged downturn & liquidity pressure']
    with pytest.raises(ValueError,match='evaluated before'):
        run_suite(BaselineOptions(paths=2),[response,stress])


def test_reserve_adjustment_only_changes_protected_cash_policy():
    stress=stress_library(severity='Severe')['High inflation & elevated rates']
    reserve=policy_response_library(stress_name=stress.name)['Protect a half-year payout reserve']
    opts=BaselineOptions(paths=3)
    _,_,inst,_,base,cash_policy=prepare_inputs(opts)
    original=build_overrides(base,inst,cash_policy,stress)
    amended=build_overrides(base,inst,cash_policy,reserve)
    pd.testing.assert_frame_equal(original,amended)
    assert reserve.reserve_years==.5
