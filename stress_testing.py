"""Stress-testing layer for the Endowment Payout-Risk model.

Adds market and endowment stress scenarios on top of ``endowment_simulation_model`` without changing
its validated core mechanics. A scenario combines:

* ``MarketShock`` – overlays applied to every simulated quarterly market path:
    - historical replay of actual P4 quarters (e.g. 2008Q1-2009Q2) at the start of the projection
    - an instantaneous asset-class shock, converted to a portfolio shock with the R1 P4 weights
    - a sustained annual return drag and/or inflation add-on for a number of years
    - a forced economic regime (Recession / Elevated inflation) for a number of quarters
* ``EndowmentShock`` – institution-side shocks passed to ``run_path`` as per-year overrides:
    gift decline, higher spending rate, expense jump / faster expense growth, special draws,
    capital calls, liquidity haircuts and liquidity-constraint settings.

Each scenario can be run as
* a Monte Carlo stress (shocks overlaid on every regime-switching / block-bootstrap path), and
* a deterministic stress path (shocks overlaid on a constant expected-return path) that is easy to
  explain line by line.

Also provides a reverse stress test (how large an instantaneous market shock breaks a target) and a
two-way sensitivity grid (market shock x spending rate).

All hypothetical shock sizes below are illustrative scenario assumptions, not calibrated forecasts.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from endowment_simulation_model import (
    STATE_ORDER,
    YEAR_OVERRIDE_DEFAULTS,
    InstitutionalParams,
    LiquidityParams,
    ModelData,
    SimulationConfig,
    percentile_path,
    quarterly_to_annual,
    run_monte_carlo,
    run_path,
)


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

@dataclass
class MarketShock:
    replay_quarters: Tuple[str, ...] = ()            # actual P4 quarters replayed at the start
    asset_shocks: Dict[str, float] = field(default_factory=dict)  # instantaneous, first quarter
    portfolio_shock: Optional[float] = None          # direct portfolio shock (overrides asset_shocks)
    return_drag_annual: float = 0.0                  # e.g. -0.03 = 3% lower return every year
    drag_years: int = 0
    inflation_add: float = 0.0                       # e.g. 0.02 = +2pp CPI
    inflation_years: int = 0
    regime_state: Optional[str] = None               # forced R1 regime
    regime_quarters: int = 0


@dataclass
class EndowmentShock:
    gift_multiplier: float = 1.0
    gift_years: int = 0
    spending_rate_add: float = 0.0
    spending_years: int = 0
    expense_level_shock: float = 0.0                 # one-off jump in operating expenses, year 1
    expense_growth_add: float = 0.0
    expense_growth_years: int = 0
    other_changes_add: float = 0.0
    other_changes_years: int = 0
    special_draw_rate: float = 0.0                   # extra appropriation out of the corpus
    special_draw_years: int = 0
    capital_call_rate: float = 0.0                   # unfunded-commitment calls competing for liquidity
    capital_call_years: int = 0
    liquid_haircut_add: float = 0.0
    liquid_haircut_years: int = 0
    liquidity_overrides: Dict[str, object] = field(default_factory=dict)  # LiquidityParams fields


@dataclass
class StressScenario:
    name: str
    category: str
    narrative: str
    market: MarketShock = field(default_factory=MarketShock)
    endowment: EndowmentShock = field(default_factory=EndowmentShock)


# Illustrative instantaneous asset-class shocks (hypothetical, not calibrated).
EQUITY_CRASH_SHOCKS = {
    "US Large Cap Equity": -0.35,
    "Developed ex-US Equity": -0.38,
    "Emerging Markets Equity": -0.45,
    "Global Equity": -0.36,
    "Venture Capital": -0.30,   # appraisal-based marks fall less on impact
    "Private Equity": -0.22,
    "Hedge Funds": -0.12,
    "Investment Grade Bonds": 0.04,
    "High Yield Bonds": -0.18,
    "Private Debt": -0.10,
    "Cash / T-Bills": 0.0,
    "Private Real Estate": -0.15,
}

RATE_SHOCK_SHOCKS = {
    "US Large Cap Equity": -0.20,
    "Developed ex-US Equity": -0.20,
    "Emerging Markets Equity": -0.22,
    "Global Equity": -0.20,
    "Venture Capital": -0.25,
    "Private Equity": -0.12,
    "Hedge Funds": -0.05,
    "Investment Grade Bonds": -0.15,
    "High Yield Bonds": -0.12,
    "Private Debt": -0.05,
    "Cash / T-Bills": 0.01,
    "Private Real Estate": -0.10,
}

LIQUIDITY_SQUEEZE = dict(
    enabled=True,
    liquidity_buffer_years=1.5,
    forced_sale_discount=0.25,
    allow_forced_sales=True,
)

LIQUIDITY_FREEZE = dict(
    enabled=True,
    liquidity_buffer_years=1.0,
    forced_sale_discount=0.35,
    allow_forced_sales=False,  # secondaries closed / funds gated: payout is cut instead
)


def default_scenarios() -> List[StressScenario]:
    return [
        StressScenario(
            "Baseline", "Baseline",
            "No stress. Same return method, regime and institutional settings as the main simulation.",
        ),
        # --- Regime stress (the existing repo scenarios) -------------------------------------
        StressScenario(
            "Recession start (6q)", "Regime",
            "Forces the R1 Recession regime for the first 6 quarters, then follows the transition matrix.",
            MarketShock(regime_state="Recession", regime_quarters=6),
        ),
        StressScenario(
            "Elevated-inflation start (8q)", "Regime",
            "Forces the R1 Elevated-inflation regime for the first 8 quarters.",
            MarketShock(regime_state="Elevated inflation", regime_quarters=8),
        ),
        # --- Historical replays -------------------------------------------------------------
        StressScenario(
            "GFC replay (2008Q1-2009Q2)", "Historical",
            "Replays the actual P4 returns and CPI of the Global Financial Crisis, then continues from the Recession regime.",
            MarketShock(replay_quarters=("2008Q1", "2008Q2", "2008Q3", "2008Q4", "2009Q1", "2009Q2")),
        ),
        StressScenario(
            "COVID crash replay (2020Q1-Q2)", "Historical",
            "Replays the sharp 2020Q1 drawdown and 2020Q2 rebound.",
            MarketShock(replay_quarters=("2020Q1", "2020Q2")),
        ),
        StressScenario(
            "2022 inflation & rates replay", "Historical",
            "Replays 2022: stocks and bonds fell together while inflation was elevated.",
            MarketShock(replay_quarters=("2022Q1", "2022Q2", "2022Q3", "2022Q4")),
        ),
        # --- Hypothetical market --------------------------------------------------------------
        StressScenario(
            "Equity crash (asset-class shock)", "Hypothetical market",
            "Instant shock: public equity -35% to -45%, PE -22%, VC -30%, HY -18%, real estate -15%, IG bonds +4%.",
            MarketShock(asset_shocks=EQUITY_CRASH_SHOCKS),
        ),
        StressScenario(
            "Rate shock (stocks & bonds down)", "Hypothetical market",
            "Instant shock with positive stock-bond correlation (equity -20%, IG bonds -15%) and +2pp CPI for 2 years.",
            MarketShock(asset_shocks=RATE_SHOCK_SHOCKS, inflation_add=0.02, inflation_years=2),
        ),
        StressScenario(
            "Stagflation", "Hypothetical market",
            "Elevated-inflation regime for 12 quarters, returns 3% lower and CPI +2pp for 5 years.",
            MarketShock(regime_state="Elevated inflation", regime_quarters=12,
                        return_drag_annual=-0.03, drag_years=5, inflation_add=0.02, inflation_years=5),
        ),
        StressScenario(
            "Lost decade", "Hypothetical market",
            "Returns 5% lower every year for 10 years (P4 long-run ~7.4% falls to ~2%).",
            MarketShock(return_drag_annual=-0.05, drag_years=10),
        ),
        # --- Endowment / institutional ------------------------------------------------------
        StressScenario(
            "Donor retreat", "Endowment",
            "New gifts fall 60% for 3 years.",
            endowment=EndowmentShock(gift_multiplier=0.4, gift_years=3),
        ),
        StressScenario(
            "Spending & expense pressure", "Endowment",
            "Spending rate +1pp for the full horizon, operating expenses jump 10% and grow 2pp faster for 5 years.",
            endowment=EndowmentShock(spending_rate_add=0.01, spending_years=99, expense_level_shock=0.10,
                                     expense_growth_add=0.02, expense_growth_years=5),
        ),
        StressScenario(
            "Special appropriation", "Endowment",
            "Board approves an extra 5% draw from the corpus in years 1-2 (e.g. operating crisis).",
            endowment=EndowmentShock(special_draw_rate=0.05, special_draw_years=2),
        ),
        StressScenario(
            "Liquidity squeeze", "Endowment",
            "Liquidity constraints ON: 1.5-year payout buffer, 60% haircut on accessible liquid assets and 6% capital "
            "calls for 3 years; illiquid assets sold at a 25% discount if the payout can't be funded.",
            endowment=EndowmentShock(capital_call_rate=0.06, capital_call_years=3, liquid_haircut_add=0.60,
                                     liquid_haircut_years=3, liquidity_overrides=dict(LIQUIDITY_SQUEEZE)),
        ),
        StressScenario(
            "Severe liquidity freeze", "Endowment",
            "Liquidity constraints ON: 1-year buffer, 75% haircut on accessible liquid assets, 6% capital calls for "
            "2 years and no forced sales possible, so any funding gap becomes a payout cut.",
            endowment=EndowmentShock(capital_call_rate=0.06, capital_call_years=2, liquid_haircut_add=0.75,
                                     liquid_haircut_years=2, liquidity_overrides=dict(LIQUIDITY_FREEZE)),
        ),
        # --- Combined -------------------------------------------------------------------------
        StressScenario(
            "Severe combined: GFC + donors + liquidity", "Combined",
            "GFC replay, gifts -60% for 3 years, liquidity squeeze and a 3% special draw in years 1-2.",
            MarketShock(replay_quarters=("2008Q1", "2008Q2", "2008Q3", "2008Q4", "2009Q1", "2009Q2")),
            EndowmentShock(gift_multiplier=0.4, gift_years=3, special_draw_rate=0.03, special_draw_years=2,
                           capital_call_rate=0.06, capital_call_years=3, liquid_haircut_add=0.60,
                           liquid_haircut_years=3, liquidity_overrides=dict(LIQUIDITY_SQUEEZE)),
        ),
        StressScenario(
            "Stagflation + spending pressure", "Combined",
            "Stagflation market path with spending +1pp and expenses +10% / growing 2pp faster.",
            MarketShock(regime_state="Elevated inflation", regime_quarters=12,
                        return_drag_annual=-0.03, drag_years=5, inflation_add=0.02, inflation_years=5),
            EndowmentShock(spending_rate_add=0.01, spending_years=99, expense_level_shock=0.10,
                           expense_growth_add=0.02, expense_growth_years=5),
        ),
    ]


def scenario_library() -> Dict[str, StressScenario]:
    return {s.name: s for s in default_scenarios()}


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

def portfolio_shock_from_assets(data: ModelData, asset_shocks: Dict[str, float]) -> float:
    """Weighted instantaneous portfolio return implied by asset-class shocks and R1 P4 weights."""
    w = data.p4_weights.set_index("asset")["weight"].astype(float)
    w = w / w.sum()
    return float(sum(w.get(a, 0.0) * s for a, s in asset_shocks.items()))


def asset_shock_table(data: ModelData, asset_shocks: Dict[str, float]) -> pd.DataFrame:
    w = data.p4_weights.copy()
    w["weight"] = w["weight"] / w["weight"].sum()
    w["shock"] = w["asset"].map(asset_shocks).fillna(0.0)
    w["contribution"] = w["weight"] * w["shock"]
    return w[["asset", "liquidity_class", "weight", "shock", "contribution"]]


def market_portfolio_shock(data: ModelData, shock: MarketShock) -> float:
    if shock.portfolio_shock is not None:
        return float(shock.portfolio_shock)
    if shock.asset_shocks:
        return portfolio_shock_from_assets(data, shock.asset_shocks)
    return 0.0


def replay_cumulative_return(data: ModelData, quarters: Sequence[str], p4_history: Optional[pd.DataFrame] = None) -> float:
    hist = (data.p4_quarterly if p4_history is None else p4_history).set_index("quarter")
    return float(np.prod(1.0 + hist.loc[list(quarters), "p4_return"].to_numpy(dtype=float)) - 1.0)


def _replay_rows(data: ModelData, quarters: Sequence[str], p4_history: Optional[pd.DataFrame]) -> pd.DataFrame:
    hist = (data.p4_quarterly if p4_history is None else p4_history).copy()
    if "cpi_yoy" not in hist.columns:
        hist = hist.merge(data.condition_history[["quarter", "cpi_yoy"]], on="quarter", how="left")
    hist = hist.set_index("quarter")
    missing = [q for q in quarters if q not in hist.index]
    if missing:
        raise ValueError(f"Replay quarters not in P4 history: {missing}")
    rows = hist.loc[list(quarters), ["p4_return", "condition", "cpi_yoy"]].reset_index(drop=True)
    # Fall back to the regime CPI history if a replay quarter has no CPI observation.
    if rows["cpi_yoy"].isna().any():
        rows["cpi_yoy"] = rows["cpi_yoy"].fillna(float(data.condition_history["cpi_yoy"].mean()))
    return rows


def make_path_transform(data: ModelData, shock: MarketShock, p4_history: Optional[pd.DataFrame] = None):
    """Return a function (rng, quarterly_path) -> stressed quarterly_path, or None for no market stress."""
    replay = _replay_rows(data, shock.replay_quarters, p4_history) if shock.replay_quarters else None
    n_replay = 0 if replay is None else len(replay)
    instant = market_portfolio_shock(data, shock)
    drag_q = (1.0 + shock.return_drag_annual) ** 0.25 - 1.0 if shock.return_drag_annual else 0.0

    if n_replay == 0 and instant == 0.0 and drag_q == 0.0 and shock.inflation_add == 0.0:
        return None

    def transform(rng: np.random.Generator, qpath: pd.DataFrame) -> pd.DataFrame:
        q = qpath.copy().reset_index(drop=True)
        n = len(q)
        if replay is not None:
            k = min(n_replay, n)
            for col in ("p4_return", "condition", "cpi_yoy"):
                q.loc[: k - 1, col] = replay[col].iloc[:k].to_numpy()
        r = np.array(q["p4_return"], dtype=float, copy=True)
        cpi = np.array(q["cpi_yoy"], dtype=float, copy=True)
        idx = np.arange(n)
        not_replay = idx >= n_replay  # replayed quarters are historical fact; overlays apply afterwards
        if instant != 0.0:
            r[0] = (1.0 + r[0]) * (1.0 + instant) - 1.0
        if drag_q != 0.0:
            m = not_replay & (idx < n_replay + shock.drag_years * 4)
            r[m] = (1.0 + r[m]) * (1.0 + drag_q) - 1.0
        if shock.inflation_add != 0.0:
            m = not_replay & (idx < n_replay + shock.inflation_years * 4)
            cpi[m] = cpi[m] + shock.inflation_add
        q["p4_return"] = r
        q["cpi_yoy"] = cpi
        return q

    return transform


def build_year_overrides(shock: EndowmentShock, horizon: int) -> Optional[pd.DataFrame]:
    ov = pd.DataFrame({k: [v] * horizon for k, v in YEAR_OVERRIDE_DEFAULTS.items()})
    years = np.arange(horizon)

    def window(n):
        return years < max(0, int(n))

    ov.loc[window(shock.gift_years), "gift_multiplier"] = shock.gift_multiplier
    ov.loc[window(shock.spending_years), "spending_rate_add"] = shock.spending_rate_add
    ov.loc[window(shock.other_changes_years), "other_changes_add"] = shock.other_changes_add
    ov.loc[window(shock.expense_growth_years), "expense_growth_add"] = shock.expense_growth_add
    ov.loc[window(shock.special_draw_years), "special_draw_rate"] = shock.special_draw_rate
    ov.loc[window(shock.capital_call_years), "capital_call_rate"] = shock.capital_call_rate
    ov.loc[window(shock.liquid_haircut_years), "liquid_share_haircut_add"] = shock.liquid_haircut_add
    if horizon > 0:
        ov.loc[0, "expense_level_shock"] = shock.expense_level_shock

    neutral = all(np.allclose(ov[k].to_numpy(dtype=float), v) for k, v in YEAR_OVERRIDE_DEFAULTS.items())
    return None if neutral else ov


def scenario_config(cfg: SimulationConfig, scenario: StressScenario, data: Optional[ModelData] = None,
                    p4_history: Optional[pd.DataFrame] = None) -> SimulationConfig:
    m = scenario.market
    if m.replay_quarters and data is not None:
        # Keep the regime chain consistent: force the replay's regimes, then transition from its last state.
        replay = _replay_rows(data, m.replay_quarters, p4_history)
        last_state = str(replay["condition"].iloc[-1])
        last_state = last_state if last_state in STATE_ORDER else "Normal"
        forced_q = len(replay)
        if m.regime_state:
            last_state, forced_q = m.regime_state, max(forced_q, m.regime_quarters)
        return replace(cfg, stress_state=last_state, stress_quarters=forced_q)
    if m.regime_state:
        return replace(cfg, stress_state=m.regime_state, stress_quarters=int(m.regime_quarters))
    return replace(cfg, stress_state=None, stress_quarters=0)


def scenario_liquidity(liq: LiquidityParams, scenario: StressScenario) -> LiquidityParams:
    return replace(liq, **scenario.endowment.liquidity_overrides) if scenario.endowment.liquidity_overrides else liq


# ---------------------------------------------------------------------------
# Monte Carlo stress
# ---------------------------------------------------------------------------

def run_stress_scenario(
    data: ModelData,
    cfg: SimulationConfig,
    inst: InstitutionalParams,
    liq: LiquidityParams,
    scenario: StressScenario,
    p4_history: Optional[pd.DataFrame] = None,
) -> Dict[str, object]:
    scfg = scenario_config(cfg, scenario, data, p4_history)
    sliq = scenario_liquidity(liq, scenario)
    transform = make_path_transform(data, scenario.market, p4_history)
    overrides = build_year_overrides(scenario.endowment, cfg.horizon_years)
    res = run_monte_carlo(data, scfg, inst, sliq, p4_history=p4_history, keep_paths=True,
                          path_transform=transform, year_overrides=overrides)
    ps = res["path_summary"]
    m = dict(res["metrics"])
    m["probability_real_corpus_below_initial"] = float((ps["terminal_real_assets"] < cfg.initial_endowment).mean())
    m["median_total_payout"] = float(ps["total_payout"].median())
    m["p05_total_payout"] = float(ps["total_payout"].quantile(0.05))
    m["median_min_payout_adequacy"] = float(ps["min_payout_adequacy"].median())
    m["liquidity_constraints"] = bool(sliq.enabled)
    ar = res["annual_results"]
    per_path_loss = ar.groupby("path_id")["forced_sale_loss"].sum() if not ar.empty else pd.Series(dtype=float)
    m["mean_forced_sale_loss"] = float(per_path_loss.mean()) if len(per_path_loss) else 0.0
    m["probability_forced_sale"] = float((ar.groupby("path_id")["forced_sale"].sum() > 0).mean()) if not ar.empty else 0.0
    res["metrics"] = m
    res["scenario"] = scenario
    return res


def run_stress_suite(
    data: ModelData,
    cfg: SimulationConfig,
    inst: InstitutionalParams,
    liq: LiquidityParams,
    scenarios: Sequence[StressScenario],
    p4_history: Optional[pd.DataFrame] = None,
    progress=None,
) -> Tuple[pd.DataFrame, Dict[str, Dict[str, object]]]:
    """Run each scenario with the same seed (common random numbers) and return a comparison table."""
    names = [s.name for s in scenarios]
    if "Baseline" not in names:
        scenarios = [scenario_library()["Baseline"], *scenarios]
    results: Dict[str, Dict[str, object]] = {}
    for i, sc in enumerate(scenarios):
        results[sc.name] = run_stress_scenario(data, cfg, inst, liq, sc, p4_history)
        if progress is not None:
            progress((i + 1) / len(scenarios), sc.name)

    base = results["Baseline"]["metrics"]
    rows = []
    for name, res in results.items():
        m = res["metrics"]
        sc = res["scenario"]
        rows.append({
            "Scenario": name,
            "Category": sc.category,
            "Median terminal real ($mm)": m["median_terminal_real_assets"],
            "5th pct terminal real ($mm)": m["p05_terminal_real_assets"],
            "Δ median real vs baseline": m["median_terminal_real_assets"] / base["median_terminal_real_assets"] - 1.0,
            "Pr(real corpus < initial)": m["probability_real_corpus_below_initial"],
            f"VaR {int(cfg.alpha*100)}% real-corpus loss": m["var_terminal_real_corpus_loss"],
            f"ES {int(cfg.alpha*100)}% real-corpus loss": m["expected_shortfall_terminal_real_corpus_loss"],
            "Median max real drawdown": m["median_max_real_drawdown"],
            "Median cumulative payout ($mm)": m["median_total_payout"],
            "Δ payout vs baseline": m["median_total_payout"] / base["median_total_payout"] - 1.0,
            "Pr(any support gap)": m["probability_any_support_gap"],
            "Pr(≥1 payout shortfall)": m["probability_at_least_one_shortfall"],
            "Avg shortfall depth": m["average_relative_shortfall_depth"],
            "Pr(forced sale)": m["probability_forced_sale"],
            "Mean forced-sale loss ($mm)": m["mean_forced_sale_loss"],
            "Pr(insolvency)": m["probability_insolvency"],
            "Liquidity constraints": "On" if m["liquidity_constraints"] else "Off",
        })
    return pd.DataFrame(rows), results


def median_real_paths(results: Dict[str, Dict[str, object]], column: str = "real_ending_assets") -> pd.DataFrame:
    frames = []
    for name, res in results.items():
        p = percentile_path(res["annual_results"], column, (0.05, 0.5)).rename(columns={"p05": "p05", "p50": "p50"})
        p["Scenario"] = name
        frames.append(p)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ---------------------------------------------------------------------------
# Deterministic stress path
# ---------------------------------------------------------------------------

def expected_quarterly_path(data: ModelData, horizon_years: int, annual_return: Optional[float] = None,
                            inflation: Optional[float] = None) -> pd.DataFrame:
    g = float(data.calibration["geometric_annual_return"]) if annual_return is None else float(annual_return)
    pi = float(data.condition_history["cpi_yoy"].mean()) if inflation is None else float(inflation)
    n = int(horizon_years * 4)
    return pd.DataFrame({
        "p4_return": [(1.0 + g) ** 0.25 - 1.0] * n,
        "condition": ["Normal"] * n,
        "cpi_yoy": [pi] * n,
    })


def _recovery_years(path: pd.DataFrame, initial: float) -> float:
    below = path["real_ending_assets"] < initial - 1e-9
    if not below.any():
        return 0.0
    first = int(np.argmax(below.to_numpy()))
    after = path["real_ending_assets"].iloc[first:].to_numpy() >= initial - 1e-9
    return float(np.argmax(after) + 1) if after.any() else np.nan


def run_deterministic_stress(
    data: ModelData,
    cfg: SimulationConfig,
    inst: InstitutionalParams,
    liq: LiquidityParams,
    scenario: StressScenario,
    p4_history: Optional[pd.DataFrame] = None,
    annual_return: Optional[float] = None,
    inflation: Optional[float] = None,
) -> pd.DataFrame:
    q = expected_quarterly_path(data, cfg.horizon_years, annual_return, inflation)
    m = scenario.market
    if m.regime_state and not m.replay_quarters:
        # Deterministic regime stress: use the historical mean P4 return / CPI of that regime for the forced quarters.
        hist = data.p4_quarterly if p4_history is None else p4_history
        k = min(int(m.regime_quarters), len(q))
        q.loc[: k - 1, "p4_return"] = float(hist.loc[hist["condition"] == m.regime_state, "p4_return"].mean())
        q.loc[: k - 1, "cpi_yoy"] = float(data.condition_history.loc[data.condition_history["condition"] == m.regime_state, "cpi_yoy"].mean())
        q.loc[: k - 1, "condition"] = m.regime_state
    transform = make_path_transform(data, m, p4_history)
    if transform is not None:
        q = transform(np.random.default_rng(0), q)
    annual = quarterly_to_annual(q, cfg.start_year)
    overrides = build_year_overrides(scenario.endowment, cfg.horizon_years)
    return run_path(annual, cfg, inst, scenario_liquidity(liq, scenario), year_overrides=overrides)


def deterministic_summary(path: pd.DataFrame, initial: float) -> Dict[str, float]:
    return {
        "terminal_nominal": float(path["ending_assets"].iloc[-1]),
        "terminal_real": float(path["real_ending_assets"].iloc[-1]),
        "terminal_real_pct_initial": float(path["real_ending_assets"].iloc[-1] / initial),
        "max_real_drawdown": float(path["real_drawdown"].min()),
        "cumulative_payout": float(path["actual_payout"].sum()),
        "min_payout": float(path["actual_payout"].min()),
        "support_gap_years": int((path["payout_support_gap"] > 0).sum()),
        "payout_shortfall_years": int(path["payout_shortfall_indicator"].sum()),
        "forced_sale_loss": float(path["forced_sale_loss"].sum()),
        "real_recovery_years": _recovery_years(path, initial),
    }


def run_deterministic_suite(data, cfg, inst, liq, scenarios, p4_history=None) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
    paths = {sc.name: run_deterministic_stress(data, cfg, inst, liq, sc, p4_history) for sc in scenarios}
    if "Baseline" not in paths:
        paths = {"Baseline": run_deterministic_stress(data, cfg, inst, liq, scenario_library()["Baseline"], p4_history), **paths}
    base = deterministic_summary(paths["Baseline"], cfg.initial_endowment)
    rows = []
    for name, p in paths.items():
        s = deterministic_summary(p, cfg.initial_endowment)
        rows.append({
            "Scenario": name,
            "Terminal real ($mm)": s["terminal_real"],
            "Terminal real % of initial": s["terminal_real_pct_initial"],
            "Max real drawdown": s["max_real_drawdown"],
            "Cumulative payout ($mm)": s["cumulative_payout"],
            "Δ payout vs baseline": s["cumulative_payout"] / base["cumulative_payout"] - 1.0,
            "Lowest annual payout ($mm)": s["min_payout"],
            "Years to recover real corpus": s["real_recovery_years"],
            "Support-gap years": s["support_gap_years"],
            "Payout-shortfall years": s["payout_shortfall_years"],
            "Forced-sale loss ($mm)": s["forced_sale_loss"],
        })
    return pd.DataFrame(rows), paths


# ---------------------------------------------------------------------------
# Reverse stress test and sensitivity grid (deterministic, fast)
# ---------------------------------------------------------------------------

def _with_instant_shock(scenario: StressScenario, shock: float) -> StressScenario:
    """Add an extra instantaneous portfolio shock on top of a scenario's existing market shock."""
    m = scenario.market
    base_instant = float(m.portfolio_shock) if m.portfolio_shock is not None else 0.0
    combined = (1.0 + base_instant) * (1.0 + shock) - 1.0
    return replace(scenario, market=replace(m, portfolio_shock=combined))


def reverse_stress_test(
    data: ModelData,
    cfg: SimulationConfig,
    inst: InstitutionalParams,
    liq: LiquidityParams,
    target_real_pct: float = 0.80,
    base_scenario: Optional[StressScenario] = None,
    p4_history: Optional[pd.DataFrame] = None,
    tol: float = 1e-4,
) -> Dict[str, float]:
    """Smallest instantaneous portfolio shock at which the deterministic terminal real corpus falls to
    ``target_real_pct`` x initial endowment. Returns NaN shock if the target holds even after a -95% shock,
    and 0 if the target is already breached with no market shock."""
    base_scenario = base_scenario or scenario_library()["Baseline"]
    if base_scenario.market.asset_shocks and base_scenario.market.portfolio_shock is None:
        base_scenario = replace(base_scenario, market=replace(
            base_scenario.market, portfolio_shock=portfolio_shock_from_assets(data, base_scenario.market.asset_shocks)))
    target = target_real_pct * cfg.initial_endowment

    def terminal(shock: float) -> float:
        p = run_deterministic_stress(data, cfg, inst, liq, _with_instant_shock(base_scenario, shock), p4_history)
        return float(p["real_ending_assets"].iloc[-1])

    no_shock = terminal(0.0)
    if no_shock <= target:
        return {"breaking_shock": 0.0, "terminal_real_no_shock": no_shock, "target_real": target}
    if terminal(-0.95) > target:
        return {"breaking_shock": np.nan, "terminal_real_no_shock": no_shock, "target_real": target}
    lo, hi = -0.95, 0.0  # terminal(lo) <= target < terminal(hi)
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if terminal(mid) <= target:
            lo = mid
        else:
            hi = mid
    return {"breaking_shock": lo, "terminal_real_no_shock": no_shock, "target_real": target}


def reverse_stress_frontier(data, cfg, inst, liq, targets=(1.0, 0.9, 0.8, 0.7, 0.6, 0.5), base_scenario=None,
                            p4_history=None) -> pd.DataFrame:
    rows = []
    for t in targets:
        r = reverse_stress_test(data, cfg, inst, liq, t, base_scenario, p4_history)
        rows.append({"Target terminal real (% of initial)": t, "Breaking instantaneous shock": r["breaking_shock"]})
    return pd.DataFrame(rows)


def sensitivity_grid(
    data: ModelData,
    cfg: SimulationConfig,
    inst: InstitutionalParams,
    liq: LiquidityParams,
    shocks: Sequence[float] = (0.0, -0.10, -0.20, -0.30, -0.40, -0.50),
    spending_rates: Optional[Sequence[float]] = None,
    gift_multiplier: float = 1.0,
    metric: str = "terminal_real_pct_initial",
    p4_history: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Deterministic grid: instantaneous market shock (rows) x effective spending rate (columns)."""
    if spending_rates is None:
        s0 = inst.effective_spending_rate
        spending_rates = [round(x, 4) for x in (s0 - 0.01, s0 - 0.005, s0, s0 + 0.005, s0 + 0.01, s0 + 0.015)]
    out = pd.DataFrame(index=list(shocks), columns=list(spending_rates), dtype=float)
    for sh in shocks:
        for sr in spending_rates:
            sc = StressScenario("grid", "Grid", "", MarketShock(portfolio_shock=sh),
                                EndowmentShock(gift_multiplier=gift_multiplier, gift_years=99 if gift_multiplier != 1.0 else 0))
            i2 = replace(inst, effective_spending_rate=float(sr))
            p = run_deterministic_stress(data, cfg, i2, liq, sc, p4_history)
            out.loc[sh, sr] = deterministic_summary(p, cfg.initial_endowment)[metric]
    out.index.name = "Instantaneous shock"
    out.columns.name = "Spending rate"
    return out


if __name__ == "__main__":
    from endowment_simulation_model import institutional_params_from_data, liquidity_params_from_data, load_default_data

    data = load_default_data()
    inst = institutional_params_from_data(data, "Private", "Base")
    liq = liquidity_params_from_data(data, enabled=False)
    cfg = SimulationConfig(n_sims=300, seed=7)

    print("Equity-crash portfolio shock:", f"{portfolio_shock_from_assets(data, EQUITY_CRASH_SHOCKS):.2%}")
    print("GFC replay cumulative P4 return:", f"{replay_cumulative_return(data, default_scenarios()[3].market.replay_quarters):.2%}")

    det, _ = run_deterministic_suite(data, cfg, inst, liq, default_scenarios())
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print("\n=== Deterministic stress ===")
        print(det.round(3).to_string(index=False))
        table, _ = run_stress_suite(data, cfg, inst, liq, default_scenarios())
        print("\n=== Monte Carlo stress ===")
        print(table.round(3).to_string(index=False))
        print("\n=== Reverse stress frontier ===")
        print(reverse_stress_frontier(data, cfg, inst, liq).round(4).to_string(index=False))
