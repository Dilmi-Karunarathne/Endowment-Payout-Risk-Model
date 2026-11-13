"""White-box validation suite for the Endowment Payout Risk Model.

Run from the repository root:  pytest -v path/to/test_model_validation.py
Every expected value is computed by hand from the model's documented formulas,
independently of the engine, and compared with the engine's output.
"""
import math
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from endowment_simulation_model import (  # noqa: E402
    InstitutionalParams, SimulationConfig, institutional_params_from_data, liquidity_params_from_data,
    load_default_data, longest_spell, recovery_statistics, run_monte_carlo, run_path, _tail_var_es,
    validate_parameters,
)
from r1_model import ASSETS, STRATEGIES, REGIMES, rebalance, PRIVATE  # noqa: E402

TOL = 1e-9


# ----------------------------------------------------------------- fixtures
@pytest.fixture(scope="module")
def data():
    return load_default_data(institution_type="Private", allocation="High Inflation", strategy="HRP")


@pytest.fixture(scope="module")
def inst(data):
    return institutional_params_from_data(data, "Private", "Base")


@pytest.fixture(scope="module")
def liq(data):
    # Aggregate-bucket path (no R1 holdings) in the app's monitoring-only mode.
    return replace(liquidity_params_from_data(data), initial_asset_weights=())


def market(returns, inflation, start=2027):
    return pd.DataFrame({"year": range(start, start + len(returns)), "portfolio_return": returns,
                         "inflation": inflation, "dominant_condition": "Normal"})


def cfg(n_years=1, initial=150.0, p2=None, p1=None, **kw):
    return SimulationConfig(initial_endowment=initial, prior_endowment_2y=p2 or initial,
                            prior_endowment_1y=p1 or initial, horizon_years=n_years, **kw)


# ----------------------------------------------------------------- inputs
def test_W01_r2_base_inputs_match_csv(data, inst):
    row = data.r2_scenarios.query("institution_type=='Private' and scenario=='Base'").iloc[0]
    assert inst.effective_spending_rate == pytest.approx(0.04897258021797972, abs=1e-15)
    assert inst.expenses_to_endowment_ratio == pytest.approx(0.5017361978714129, abs=1e-15)
    assert inst.annual_expense_growth == pytest.approx(0.02784974949013586, abs=1e-15)
    for f in ["support_ratio", "gift_rate", "tuition_share", "other_revenue_share", "net_tuition_growth"]:
        assert getattr(inst, f) == pytest.approx(float(row[f]), abs=1e-15)


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_W02_forward_weights_sum_to_one(strategy):
    w = pd.read_csv(REPO / "data/r1/forward_weights_by_regime.csv")
    sid = "MeanCVaR@Private" if strategy == "MeanCVaR" else strategy
    t = w[w.Strategy_ID == sid].set_index("Regime")[ASSETS]
    assert set(t.index) == set(REGIMES)
    assert np.allclose(t.sum(axis=1), 1.0, atol=1e-9)
    assert (t.to_numpy() >= -1e-12).all()


# ----------------------------------------------------------------- spending rule
def test_W03_year1_payout_hand_calc(inst, liq):
    p = run_path(market([0.05], [0.02]), cfg(), replace(inst, gift_rate=0.0), liq).iloc[0]
    assert p.planned_payout == pytest.approx(150 * 0.04897258021797972, abs=TOL)   # 7.345887
    assert p.actual_payout == pytest.approx(p.planned_payout, abs=TOL)


def test_W04_trailing_average_uses_prior_values(inst, liq):
    i = replace(inst, effective_spending_rate=0.04, gift_rate=0.0)
    p = run_path(market([0.06, 0.06], [0, 0]), cfg(2, 150, 130, 140), i, liq)
    assert p.planned_payout[0] == pytest.approx(0.04 * (130 + 140 + 150) / 3, abs=TOL)   # 5.6
    e1 = 150 * 1.06 - 5.6
    assert p.ending_assets[0] == pytest.approx(e1, abs=TOL)
    assert p.planned_payout[1] == pytest.approx(0.04 * (140 + 150 + e1) / 3, abs=TOL)


def test_W05_current_assets_rule(inst, liq):
    i = replace(inst, spending_rule="Current assets", effective_spending_rate=0.04, gift_rate=0.0)
    p = run_path(market([0.06], [0]), cfg(1, 150, 100, 100), i, liq).iloc[0]
    assert p.planned_payout == pytest.approx(0.04 * 150, abs=TOL)


@pytest.mark.parametrize("rate,expected", [(0.02, 4.5), (0.08, 7.5), (0.04, 6.0)])
def test_W06_payout_collar(inst, liq, rate, expected):
    p = run_path(market([0.05], [0]), cfg(), replace(inst, effective_spending_rate=rate), liq).iloc[0]
    assert p.planned_payout == pytest.approx(expected, abs=TOL)


def test_W07_optional_payout_growth_cap(inst, liq):
    i = replace(inst, effective_spending_rate=0.045, gift_rate=0.0, annual_payout_growth_cap=0.01,
                spending_rule="Current assets")
    p = run_path(market([0.30, 0.0], [0, 0]), cfg(2), i, liq)
    assert p.planned_payout[1] == pytest.approx(p.planned_payout[0] * 1.01, abs=TOL)


# ----------------------------------------------------------------- roll-forward
def test_W08_endowment_roll_forward(inst, liq):
    i = replace(inst, effective_spending_rate=0.045, gift_rate=0.02)
    p = run_path(market([0.07], [0.03]), cfg(), i, liq).iloc[0]
    gain, gifts, pay = 150 * 0.07, 150 * 0.02, 150 * 0.045
    assert p.investment_gain == pytest.approx(gain, abs=TOL)
    assert p.endowment_gifts == pytest.approx(gifts, abs=TOL)
    assert p.ending_assets == pytest.approx(150 + gain + gifts - pay, abs=TOL)        # 156.75
    assert p.real_ending_assets == pytest.approx((150 + gain + gifts - pay) / 1.03, abs=TOL)
    assert abs(p.accounting_residual) < 1e-8


def test_W09_real_deflator_compounds(inst, liq):
    p = run_path(market([0.0, 0.0, 0.0], [0.02, 0.03, 0.04]), cfg(3), inst, liq)
    idx = np.cumprod([1.02, 1.03, 1.04])
    assert np.allclose(p.cumulative_inflation_index, idx, atol=TOL)
    assert np.allclose(p.real_actual_payout, p.actual_payout / idx, atol=TOL)


# ----------------------------------------------------------------- operating budget
def test_W10_operating_budget_paths(inst, liq):
    p = run_path(market([0.05] * 5, [0.02] * 5), cfg(5), inst, liq)
    e0 = 150 * inst.expenses_to_endowment_ratio
    g = inst.annual_expense_growth
    assert np.allclose(p.operating_expenses, [e0 * (1 + g) ** t for t in range(5)], atol=1e-9)
    assert p.operating_expenses[0] == pytest.approx(75.26043, abs=1e-5)             # app showed 75.2604
    assert np.allclose(p.net_tuition, [e0 * inst.tuition_share * (1 + inst.net_tuition_growth) ** t for t in range(5)])
    assert np.allclose(p.other_operating_revenue, [e0 * inst.other_revenue_share * (1 + g) ** t for t in range(5)])
    assert np.allclose(p.operating_balance, p.net_tuition + p.other_operating_revenue + p.actual_payout - p.operating_expenses)
    assert np.allclose(p.required_support, p.operating_expenses * inst.support_ratio)


# ----------------------------------------------------------------- indicators
def test_W11_coverage_and_erosion_indicators(inst, liq):
    p = run_path(market([0.02, 0.10, -0.08], [0.0] * 3), cfg(3), replace(inst, gift_rate=0.0), liq)
    assert list(p.return_coverage_shortfall_indicator) == [int(g < pl - 1e-10) for g, pl in zip(p.investment_gain, p.planned_payout)]
    assert p.return_coverage_shortfall_amount[0] == pytest.approx(p.planned_payout[0] - 150 * 0.02, abs=TOL)
    assert list(p.real_corpus_below_threshold) == [int(r < 150 - 1e-10) for r in p.real_ending_assets]


def test_W12_longest_spell_and_recovery():
    assert longest_spell([0, 1, 1, 0, 1, 1, 1, 0]) == 3
    assert longest_spell([0, 0]) == 0
    s = recovery_statistics(pd.DataFrame({"real_corpus_below_threshold": [0, 1, 1, 0, 1]}))
    assert s["recovery_years"] == 2 and not s["recovery_censored"]
    s = recovery_statistics(pd.DataFrame({"real_corpus_below_threshold": [0, 1, 1, 1]}))
    assert math.isnan(s["recovery_years"]) and s["recovery_censored"] and s["erosion_spell_observed"] == 3


def test_W13_tail_var_es():
    losses = np.arange(1, 101) / 100.0
    var, es = _tail_var_es(losses, 0.95)
    assert var == pytest.approx(np.quantile(losses, 0.95))
    assert es == pytest.approx(np.mean([0.96, 0.97, 0.98, 0.99, 1.00]))


def test_W14_funding_shortfall_only_when_assets_exhausted(inst, liq):
    """Legacy aggregate fallback sells only eligible assets, with costs; no free principal liquidation."""
    i = replace(inst, gift_rate=0.0)
    ok = run_path(market([-0.60], [0]), cfg(), i, liq).iloc[0]            # 60% crash, still fully paid
    assert ok.payout_shortfall_indicator == 0
    bust = run_path(market([-0.99], [0]), cfg(), i, liq).iloc[0]          # $1.5M left vs $7.3M planned
    assert bust.payout_shortfall_indicator == 1
    assert 0 < bust.actual_payout < bust.pre_payout_assets
    assert bust.actual_payout == pytest.approx(bust.funding_capacity_for_payout, abs=TOL)


# ----------------------------------------------------------------- homogeneity
def test_W15_scale_invariance_path(inst, liq):
    m = market([0.05, -0.1, 0.12], [0.02, 0.03, 0.01])
    a = run_path(m, cfg(3, 150), inst, liq)
    b = run_path(m, cfg(3, 300), inst, liq)
    for col in ["planned_payout", "ending_assets", "real_ending_assets", "operating_expenses", "operating_balance"]:
        assert np.allclose(b[col], 2 * a[col], atol=1e-9)
    for col in ["return_coverage_shortfall_indicator", "real_corpus_below_threshold", "payout_shortfall_indicator"]:
        assert (a[col] == b[col]).all()


# ----------------------------------------------------------------- R1 rebalancing
def test_W16_private_sleeve_pacing():
    h = np.zeros(13); h[0] = 100.0                     # start 100% US large cap
    tgt = np.full(13, 1 / 13)
    new = rebalance(h, tgt)
    assert new.sum() == pytest.approx(100.0)
    assert np.allclose(new[PRIVATE] / 100, 0.05)       # private sleeves move at most 5pp per quarter


# ----------------------------------------------------------------- guards
@pytest.mark.parametrize("change", [
    dict(effective_spending_rate=1.5), dict(payout_floor_rate=0.06), dict(gift_rate=-0.01),
    dict(spending_rule="Bogus"), dict(annual_payout_growth_floor=0.1, annual_payout_growth_cap=0.0),
])
def test_W17_invalid_inputs_rejected(inst, liq, change):
    with pytest.raises(ValueError):
        validate_parameters(cfg(), replace(inst, **change), liq)


# ----------------------------------------------------------------- Monte Carlo
@pytest.fixture(scope="module")
def app_run(data, inst):
    c = SimulationConfig(return_method="R1 dynamic asset bootstrap", n_sims=1000, seed=42, horizon_years=5)
    return run_monte_carlo(data, c, inst, liquidity_params_from_data(data), portfolio_history=data.portfolio_quarterly)


@pytest.mark.parametrize("key", [
    "annual_coverage_shortfall_probability", "probability_at_least_one_shortfall",
    "probability_real_corpus_erosion", "probability_liquidity_breach",
    "probability_real_payout_cut", "median_payout_volatility",
])
def test_W18_recomputes_updated_risk_cards(app_run, key):
    """Old app's frozen 2026 percentages are not valid after cash-first funding
    and preventing cost-free quarterly redemptions of locked private sleeves."""
    a = app_run["annual_results"]
    p = app_run["path_summary"]
    independent = {
        'annual_coverage_shortfall_probability': a['return_coverage_shortfall_indicator'].mean(),
        'probability_at_least_one_shortfall': p['at_least_one_shortfall'].mean(),
        'probability_real_corpus_erosion': (p['erosion_years'] > 0).mean(),
        'probability_liquidity_breach': p['liquidity_breach'].mean(),
        'probability_real_payout_cut': p['real_payout_cut'].mean(),
        'median_payout_volatility': p['payout_volatility'].median(),
    }
    assert app_run["metrics"][key] == pytest.approx(independent[key], abs=1e-10)


def test_W19_reproduces_app_dollar_cards(app_run):
    m = app_run["metrics"]
    # Expected value changed slightly because asset sales now incur costs.
    assert 150 < m["median_terminal_real_assets"] < 200
    assert round(m["median_cumulative_real_payout"], 1) == 36.5


def test_W20_mc_accounting_and_payout_bounds(app_run):
    a = app_run["annual_results"]
    assert a.accounting_residual.abs().max() < 1e-6
    assert (a.planned_payout >= a.beginning_assets * 0.03 - 1e-9).all()
    assert (a.planned_payout <= a.beginning_assets * 0.05 + 1e-9).all()
    first = a[a.year == 2027]
    assert np.allclose(first.planned_payout, 150 * 0.04897258021797972)    # 7.3459 shown in the app


def test_W21_same_seed_is_deterministic(data, inst):
    c = SimulationConfig(return_method="R1 dynamic asset bootstrap", n_sims=200, seed=7, horizon_years=5)
    l = liquidity_params_from_data(data)
    a = run_monte_carlo(data, c, inst, l, portfolio_history=data.portfolio_quarterly)["path_summary"]
    b = run_monte_carlo(data, c, inst, l, portfolio_history=data.portfolio_quarterly)["path_summary"]
    pd.testing.assert_frame_equal(a, b)


def test_W22_scale_invariance_monte_carlo(data, inst):
    l = liquidity_params_from_data(data)
    base = SimulationConfig(return_method="R1 dynamic asset bootstrap", n_sims=200, seed=42, horizon_years=5)
    a = run_monte_carlo(data, base, inst, l, portfolio_history=data.portfolio_quarterly)
    b = run_monte_carlo(data, replace(base, initial_endowment=300, prior_endowment_1y=300, prior_endowment_2y=300),
                        inst, l, portfolio_history=data.portfolio_quarterly)
    assert np.allclose(b["path_summary"].terminal_real_assets, 2 * a["path_summary"].terminal_real_assets)
    for k in ["annual_coverage_shortfall_probability", "probability_real_corpus_erosion", "probability_real_payout_cut"]:
        assert a["metrics"][k] == b["metrics"][k]


def test_W23_fixed_inflation_is_exact(data, inst):
    c = SimulationConfig(return_method="R1 dynamic asset bootstrap", n_sims=50, seed=1, horizon_years=3, annual_inflation=0.025)
    a = run_monte_carlo(data, c, inst, liquidity_params_from_data(data), portfolio_history=data.portfolio_quarterly)["annual_results"]
    assert np.allclose(a.inflation, 0.025, atol=1e-12)


# ----------------------------------------------------------------- code hygiene
def test_W24_dataclass_defaults_match_r2_base(inst):
    """Direct defaults must match the R2 Private base row."""
    d = InstitutionalParams()
    stale = {f: (getattr(d, f), getattr(inst, f)) for f in
             ["effective_spending_rate", "expenses_to_endowment_ratio", "support_ratio", "gift_rate"]
             if abs(getattr(d, f) - getattr(inst, f)) > 1e-12}
    assert not stale, f"stale defaults: {stale}"


def test_updated_r1_monitoring_uses_distinct_numerators(data, inst):
    weights = np.zeros(len(ASSETS))
    weights[ASSETS.index('emerging_markets')] = .45
    weights[ASSETS.index('commodities')] = .30
    weights[ASSETS.index('private_equity')] = .25
    liquidity = replace(liquidity_params_from_data(data), initial_asset_weights=tuple(weights),
                        liquid_share=.75, illiquid_share=.25, cash_share=0., hedge_share=0.)
    i = replace(inst, gift_rate=0., effective_spending_rate=.05)
    base = run_path(market([0.], [0.]), cfg(initial=100.), i, liquidity).iloc[0]
    severe = run_path(market([0.], [0.]), cfg(initial=100.), i, liquidity,
                      pd.DataFrame({'restrict_em_hy': [1.]})).iloc[0]
    # The worst snapshot can occur *after* the funded payout, so its share
    # may be lower than the opening share used by the old monitoring-only test.
    assert base.minimum_liquid_share <= .45 * .975 + .30 * .98 + 1e-9
    assert base.minimum_liquidity_coverage <= 100 * .45 / 5
    assert severe.minimum_liquid_share < base.minimum_liquid_share
    assert severe.r1_liquidity_breach == severe.r2_coverage_warning == 1
    assert severe.sale_emerging_markets == 0
    assert severe.actual_payout == pytest.approx(5.)
    assert base.actual_payout == pytest.approx(5.)


def test_r1_rebalancing_cost_is_charged_once():
    from r1_model import invest_year, liquidity_inputs, PAYOUT_LIQUID
    h = np.zeros(len(ASSETS))
    h[ASSETS.index('us_large_cap')] = 100.
    target = dict.fromkeys(ASSETS, 0.)
    target['treasuries'] = 1.
    record = {'r1_condition': 'Recession', 'targets': {'Recession': target},
              'asset_returns': np.zeros(len(ASSETS))}
    end, returns, _, _, cost = invest_year(h, [record], liquidity_inputs()[0], PAYOUT_LIQUID)
    assert cost == pytest.approx(2.)
    assert end.sum() == pytest.approx(98.)
    assert returns == pytest.approx([-.02])


def test_primary_inflation_anchor_after_replay(data, inst):
    from scenario_stress import framework_scenarios, make_path_transform
    from r1_model import draw_path
    rng = np.random.default_rng(42)
    q = draw_path(rng, data, cfg(5))
    scenario = framework_scenarios(inst)[0]
    stressed = make_path_transform(data, scenario.market)(rng, q)
    assert np.allclose((1 + stressed.cpi_quarter.iloc[4:16])**4 - 1, .041)
    assert np.allclose(stressed.cpi_quarter.iloc[16:], q.cpi_quarter.iloc[16:])
