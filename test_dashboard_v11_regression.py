"""Regression: a successful simulation must never crash in the risk comparison tab.

Tests the exact column mismatch that broke the previous Streamlit Cloud deployment.
Short runs are developer-only; the public UI continues to require 5,000 or 10,000 paths.
"""
from unittest.mock import patch
import pandas as pd
import pytest
from simple_analysis import BaselineOptions
from scenario_analysis import run_suite, stress_library, policy_response_library
from dashboard_contract import validate_comparison_schema, REQUIRED_COMPARISON_COLUMNS


def _validated_suite(institution, policies=(), strategies=('HRP_Dynamic',)):
    with patch('simple_analysis.validate_options', lambda _: None):
        return run_suite(BaselineOptions(institution=institution,paths=6),
                         policies,strategies=strategies)


@pytest.mark.parametrize('institution',['Private','Public'])
def test_baseline_produces_every_column_used_by_payout_risk_table(institution):
    suite=_validated_suite(institution,strategies=('HRP_Dynamic','MeanCVaR_Dynamic'))
    ok,reason=validate_comparison_schema(suite['comparison'])
    assert ok,reason
    assert REQUIRED_COMPARISON_COLUMNS <= set(suite['comparison'].columns)
    df=suite['comparison']
    assert 'Portfolio crisis-value 20% breach probability (%)' in df
    assert 'R1 crisis-value 20% breach probability (%)' not in df
    assert df['Below 20% liquid-share probability (%)'].le(
       df['Below 40% liquid-share probability (%)']+1e-8).all()
    assert len(df)==2


def test_stress_and_policy_cases_keep_comparison_columns():
    lib=stress_library('Private','Severe')
    policies=policy_response_library('Private','Severe','Prolonged downturn & liquidity pressure')
    chosen=[lib['Prolonged downturn & liquidity pressure'],next(iter(policies.values()))]
    suite=_validated_suite('Private',chosen)
    ok,reason=validate_comparison_schema(suite['comparison'])
    assert ok,reason
    assert len(suite['comparison'])==3
    policy=suite['comparison'].loc[suite['comparison']['Policy reference'].astype(bool)].iloc[0]
    assert pd.notna(policy['Policy vs same stress: Change in minimum liquidity buffer (×)'])


def test_missing_field_produces_actionable_warning_instead_of_keyerror():
    suite=_validated_suite('Private')
    broken=suite['comparison'].drop(columns=['Portfolio crisis-value 20% breach probability (%)'])
    ok,reason=validate_comparison_schema(broken)
    assert not ok
    assert 'Portfolio crisis-value 20% breach probability (%)' in reason
    assert 'Update' in reason and 'reboot' in reason
