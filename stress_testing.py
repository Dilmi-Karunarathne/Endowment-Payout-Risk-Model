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

def add_derived_columns(path: pd.DataFrame) -> pd.DataFrame:
    """Real payout and liquidity coverage (cash available for the payout / planned payout; <1 means forced sales
    or payout cuts are needed). Coverage is NaN when liquidity constraints are off."""
    out = path.copy()
    out["real_payout"] = out["actual_payout"] / out["cumulative_inflation_index"]
    cash = (out["liquid_assets"] - out["required_liquidity"]).clip(lower=0.0)
    out["liquidity_coverage"] = cash / out["planned_payout"].where(out["planned_payout"] > 0)
    return out


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
    if not ar.empty:
        ar = add_derived_columns(ar)
        res["annual_results"] = ar
        g = ar.groupby("path_id")
        m["median_total_real_payout"] = float(g["real_payout"].sum().median())
        m["p05_total_real_payout"] = float(g["real_payout"].sum().quantile(0.05))
        first_years = ar[ar["year"] < cfg.start_year + 3]
        m["median_real_payout_first3"] = float(first_years.groupby("path_id")["real_payout"].sum().median())
        m["median_total_support_gap"] = float(g["payout_support_gap"].sum().median())
        m["mean_total_support_gap"] = float(g["payout_support_gap"].sum().mean())
        m["median_avg_payout_adequacy"] = float(g["payout_adequacy_ratio"].mean().median())
        cov = g["liquidity_coverage"].min()
        m["median_min_liquidity_coverage"] = float(cov.median()) if cov.notna().any() else np.nan
        m["p05_min_liquidity_coverage"] = float(cov.quantile(0.05)) if cov.notna().any() else np.nan
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
    if m.regime_state:
        # Deterministic regime stress: use the historical mean P4 return / CPI of that regime for the forced quarters
        # (any replayed quarters are overwritten with the actual history by the transform below).
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
    path = run_path(annual, cfg, inst, scenario_liquidity(liq, scenario), year_overrides=overrides)
    return add_derived_columns(path)


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


# ---------------------------------------------------------------------------
# R3 stress-scenario framework (Sprint Project | R3, "Proposed Stress-Scenario Framework")
#
# Goal: evaluate payout sustainability under two adverse economic regimes.
#   Scenario 1 - High inflation & elevated rates: high inflation, rising cost of capital, elevated operating
#                expenses. Focus: maintaining real payout value and meeting institutional funding needs.
#   Scenario 2 - Prolonged downturn & liquidity squeeze: market losses, delayed private distributions,
#                illiquid asset sales. Focus: meeting required payouts while minimising forced-sale losses.
# Each parameter below carries its severity / duration / recovery role and its evidence basis.
# ---------------------------------------------------------------------------

SCENARIO_1 = "Scenario 1: High inflation & elevated rates"
SCENARIO_2 = "Scenario 2: Prolonged downturn & liquidity squeeze"

INFLATION_REPLAY = ("2022Q1", "2022Q2", "2022Q3", "2022Q4")
GFC_REPLAY = ("2008Q1", "2008Q2", "2008Q3", "2008Q4", "2009Q1", "2009Q2")

# External evidence used for defaults (see calibration_table for the full list with sources).
HEPI_FY2022 = 0.052          # Commonfund HEPI, FY2022 (CPI 7.2% in the same year)
HEPI_FY2023 = 0.041          # Commonfund HEPI, FY2023
VSE_GIVING_FY2009 = -0.119   # CAE Voluntary Support of Education: giving to colleges, FY2009
NACUBO_RETURN_FY2009 = -0.187
SECONDARY_BID_H1_2010 = 0.80  # Cogent Partners: average high bid ~80% of NAV in H1 2010 (after the trough)


@dataclass
class InflationRatesParams:
    """Scenario 1 shock parameters."""
    replay_quarters: Tuple[str, ...] = INFLATION_REPLAY  # severity: actual 2022 stock-and-bond selloff and CPI
    elevated_quarters: int = 16          # duration: forced Elevated-inflation quarters incl. replay (2021Q2-2025Q1 spell)
    cpi_add: Optional[float] = None      # None = calibrate to the latest spell's average CPI
    expense_growth: float = round((HEPI_FY2022 + HEPI_FY2023) / 2, 4)  # elevated operating-expense growth
    expense_years: int = 2
    return_drag: float = 0.0             # optional extra cost-of-capital drag on returns after the replay
    drag_years: int = 0


@dataclass
class DownturnLiquidityParams:
    """Scenario 2 shock parameters."""
    replay_quarters: Tuple[str, ...] = GFC_REPLAY  # severity: actual GFC P4 path
    recovery_drag: float = -0.03          # recovery path: slower-than-2009 recovery (assumption)
    recovery_years: int = 2
    gift_multiplier: float = round(1.0 + VSE_GIVING_FY2009, 3)
    gift_years: int = 2
    private_cash_drain: float = 0.02      # delayed distributions while capital calls continue, % of corpus / yr
    drain_years: int = 3
    liquid_haircut: float = 0.50          # share of liquid assets not available for the payout (rebalancing, collateral)
    haircut_years: int = 2
    buffer_years: float = 1.0             # liquidity reserve, years of planned payout (policy assumption)
    forced_sale_discount: float = 0.30    # discount when illiquid assets are sold
    allow_forced_sales: bool = True


def latest_spell(data: ModelData, condition: str) -> Dict[str, object]:
    c = data.condition_history.copy()
    c["spell"] = (c["condition"] != c["condition"].shift()).cumsum()
    spells = c[c["condition"] == condition].groupby("spell").agg(
        start=("quarter", "first"), end=("quarter", "last"), quarters=("quarter", "size"), cpi=("cpi_yoy", "mean"))
    last = spells.iloc[-1]
    longest = spells.sort_values("quarters").iloc[-1]
    return {
        "start": last["start"], "end": last["end"], "quarters": int(last["quarters"]), "cpi": float(last["cpi"]),
        "longest_start": longest["start"], "longest_end": longest["end"], "longest_quarters": int(longest["quarters"]),
        "longest_cpi": float(longest["cpi"]),
        "regime_cpi": float(c.loc[c["condition"] == condition, "cpi_yoy"].mean()),
    }


def default_cpi_add(data: ModelData) -> float:
    """CPI add-on so the stress window matches the 2021-25 elevated-inflation spell instead of the all-history average."""
    sp = latest_spell(data, "Elevated inflation")
    return max(0.0, sp["longest_cpi"] - sp["regime_cpi"])


def build_inflation_rates_scenario(data: ModelData, inst: InstitutionalParams,
                                   p: Optional[InflationRatesParams] = None) -> StressScenario:
    p = p or InflationRatesParams()
    n_replay = len(p.replay_quarters)
    post_years = max(0, int(np.ceil((p.elevated_quarters - n_replay) / 4)))
    cpi_add = default_cpi_add(data) if p.cpi_add is None else float(p.cpi_add)
    return StressScenario(
        SCENARIO_1, "R3 framework",
        "High inflation, rising cost of capital and elevated operating expenses. Replays 2022 (stocks and bonds fell "
        "together while CPI ran at 7-9%), keeps the Elevated-inflation regime for the stress window, lifts operating-"
        "expense growth to the HEPI level, then recovers through the R1 transition matrix.",
        MarketShock(replay_quarters=tuple(p.replay_quarters), regime_state="Elevated inflation",
                    regime_quarters=int(max(p.elevated_quarters, n_replay)),
                    inflation_add=cpi_add, inflation_years=post_years,
                    return_drag_annual=float(p.return_drag), drag_years=int(p.drag_years)),
        EndowmentShock(expense_growth_add=max(0.0, float(p.expense_growth) - inst.annual_expense_growth),
                       expense_growth_years=int(p.expense_years)),
    )


def build_downturn_liquidity_scenario(data: ModelData, inst: InstitutionalParams,
                                      p: Optional[DownturnLiquidityParams] = None) -> StressScenario:
    p = p or DownturnLiquidityParams()
    return StressScenario(
        SCENARIO_2, "R3 framework",
        "Market losses, delayed private distributions and illiquid asset sales. Replays the GFC (2008Q1-2009Q2), "
        "slows the recovery, cuts gifts by the FY2009 amount, and turns liquidity constraints on: private capital "
        "keeps being called while distributions stall, part of the liquid book is unavailable, and any funding gap "
        "is met by selling illiquid assets at a discount.",
        MarketShock(replay_quarters=tuple(p.replay_quarters), return_drag_annual=float(p.recovery_drag),
                    drag_years=int(p.recovery_years)),
        EndowmentShock(gift_multiplier=float(p.gift_multiplier), gift_years=int(p.gift_years),
                       capital_call_rate=float(p.private_cash_drain), capital_call_years=int(p.drain_years),
                       liquid_haircut_add=float(p.liquid_haircut), liquid_haircut_years=int(p.haircut_years),
                       liquidity_overrides=dict(enabled=True, liquidity_buffer_years=float(p.buffer_years),
                                                forced_sale_discount=float(p.forced_sale_discount),
                                                allow_forced_sales=bool(p.allow_forced_sales))),
    )


def calibration_table(data: ModelData, inst: InstitutionalParams,
                      p1: Optional[InflationRatesParams] = None,
                      p2: Optional[DownturnLiquidityParams] = None) -> pd.DataFrame:
    """Shock parameters, their quantitative impact, and the evidence behind each (for the R3 calibration requirements)."""
    p1 = p1 or InflationRatesParams()
    p2 = p2 or DownturnLiquidityParams()
    sp = latest_spell(data, "Elevated inflation")
    cpi_add = default_cpi_add(data) if p1.cpi_add is None else p1.cpi_add
    q = data.p4_quarterly.set_index("quarter")
    infl_ret = replay_cumulative_return(data, p1.replay_quarters)
    infl_cpi = float(q.loc[list(p1.replay_quarters), "cpi_yoy"].mean())
    gfc_ret = replay_cumulative_return(data, p2.replay_quarters)
    trans = data.transition_matrix
    stay_e = float(trans.loc["Elevated inflation", "Elevated inflation"])
    stay_r = float(trans.loc["Recession", "Recession"])
    hist = "Historical data (R1 / D1)"
    ext = "External evidence"
    assum = "Assumption (to be confirmed)"
    rows = [
        (SCENARIO_1, "Severity", "Asset returns", f"Replay {p1.replay_quarters[0]}-{p1.replay_quarters[-1]}",
         f"P4 {infl_ret:.1%} cumulative; CPI {infl_cpi:.1%} avg", hist,
         "Actual P4 quarterly returns and CPI YoY in 2022, when equities and bonds fell together as policy rates rose."),
        (SCENARIO_1, "Duration", "Inflation", f"{p1.elevated_quarters} quarters in Elevated-inflation regime",
         f"CPI +{cpi_add:.1%} pts after the replay", hist,
         f"Longest elevated spell in the CPI history: {sp['longest_start']}-{sp['longest_end']} "
         f"({sp['longest_quarters']} quarters, CPI {sp['longest_cpi']:.1%} avg vs {sp['regime_cpi']:.1%} for all "
         "elevated quarters); the add-on closes that gap."),
        (SCENARIO_1, "Variable impact", "Operating expenses",
         f"Expense growth {p1.expense_growth:.1%} for {p1.expense_years} yrs",
         f"+{max(0.0, p1.expense_growth - inst.annual_expense_growth):.1%} pts vs R2 base {inst.annual_expense_growth:.1%}",
         ext, f"Commonfund HEPI: {HEPI_FY2022:.1%} in FY2022 and {HEPI_FY2023:.1%} in FY2023 (highest since 2001)."),
        (SCENARIO_1, "Variable impact", "Cost of capital",
         f"Return drag {p1.return_drag:.1%}/yr for {p1.drag_years} yrs" if p1.drag_years else "Within the 2022 replay",
         "Bond and equity repricing", hist if not p1.drag_years else assum,
         "The 2022 replay already contains the rate-driven repricing of bonds and equities; an extra drag is optional."),
        (SCENARIO_1, "Recovery path", "Regime", "R1 transition matrix after the stress window",
         f"P(stay Elevated) {stay_e:.0%}/qtr", hist,
         "Exit from the forced window follows the full-history Normal / Recession / Elevated transition probabilities."),
        (SCENARIO_2, "Severity", "Asset returns", f"Replay {p2.replay_quarters[0]}-{p2.replay_quarters[-1]}",
         f"P4 {gfc_ret:.1%} cumulative", hist,
         f"Actual P4 GFC path. Cross-check: NACUBO average endowment return FY2009 {NACUBO_RETURN_FY2009:.1%}."),
        (SCENARIO_2, "Duration / recovery path", "Asset returns",
         f"Return drag {p2.recovery_drag:.1%}/yr for {p2.recovery_years} yrs after the replay",
         "Slower recovery than 2009Q3 onward", assum,
         f"P4 rebounded quickly after 2009Q2; the drag tests a prolonged downturn. Then R1 matrix (P(stay Recession) "
         f"{stay_r:.0%}/qtr)."),
        (SCENARIO_2, "Variable impact", "Gifts", f"Gifts x {p2.gift_multiplier:.2f} for {p2.gift_years} yrs",
         f"{p2.gift_multiplier - 1:.1%} vs normal", ext,
         f"CAE Voluntary Support of Education: giving to colleges fell {abs(VSE_GIVING_FY2009):.1%} in FY2009."),
        (SCENARIO_2, "Variable impact", "Liquidity: delayed distributions",
         f"Net private cash drain {p2.private_cash_drain:.1%} of corpus/yr for {p2.drain_years} yrs",
         "Competes with the payout for liquid assets", assum,
         "In the GFC, private-fund capital calls fell ~50% while distributions fell 60-82% (AltamarCAM), so LP net "
         "cash flow turned negative. Size depends on unfunded commitments (awaiting R2/D2 benchmark)."),
        (SCENARIO_2, "Variable impact", "Liquidity: accessible liquid assets",
         f"{p2.liquid_haircut:.0%} haircut for {p2.haircut_years} yrs; buffer {p2.buffer_years:.1f} yrs of payout",
         f"P4 liquid share {float(data.calibration['liquid_share']):.1%}", assum,
         "Policy reserve and rebalancing/collateral needs; R2/D2 have not finalised institution-level liquidity "
         "benchmarks."),
        (SCENARIO_2, "Variable impact", "Liquidity: forced-sale discount", f"{p2.forced_sale_discount:.0%} of NAV",
         "Loss on illiquid sales", ext,
         f"Secondary bids were still ~{SECONDARY_BID_H1_2010:.0%} of NAV in H1 2010 after recovering (Cogent Partners), "
         "so crisis-trough discounts were deeper than 20%."),
    ]
    return pd.DataFrame(rows, columns=["Scenario", "Role", "Variable", "Setting", "Quantitative impact",
                                       "Evidence type", "Basis"])


def liquidity_breaking_point(data, cfg, inst, liq, p2: Optional[DownturnLiquidityParams] = None,
                             p4_history=None, tol: float = 1e-3) -> Dict[str, float]:
    """Scenario 2 reverse test on the deterministic path: the smallest liquid-asset haircut, and separately the
    smallest net private cash drain, at which cash no longer covers the payout (coverage < 1x), i.e. forced sales
    or payout cuts begin. NaN = not reached within the search range."""
    p2 = p2 or DownturnLiquidityParams()

    def min_cov(params: DownturnLiquidityParams) -> float:
        sc = build_downturn_liquidity_scenario(data, inst, params)
        path = run_deterministic_stress(data, cfg, inst, liq, sc, p4_history)
        return float(path["liquidity_coverage"].min())

    def search(field: str, hi: float) -> float:
        if min_cov(replace(p2, **{field: hi})) >= 1.0:
            return np.nan
        lo_v, hi_v = 0.0, hi
        if min_cov(replace(p2, **{field: 0.0})) < 1.0:
            return 0.0
        while hi_v - lo_v > tol:
            mid = 0.5 * (lo_v + hi_v)
            if min_cov(replace(p2, **{field: mid})) < 1.0:
                hi_v = mid
            else:
                lo_v = mid
        return hi_v

    return {
        "current_min_coverage": min_cov(p2),
        "breaking_haircut": search("liquid_haircut", 1.0),
        "breaking_cash_drain": search("private_cash_drain", 0.5),
    }


R3_EVIDENCE_SOURCES = [
    ("Commonfund HEPI FY2022 (Higher Ed Dive)", "https://www.highereddive.com/news/hepi-2022-higher-ed-inflation/638923/"),
    ("Commonfund HEPI FY2023 (Higher Ed Dive)", "https://www.highereddive.com/news/colleges-inflation-costs-increased-4-percent-in-fy23/702457/"),
    ("Giving to colleges fell 11.9% in 2009 (Chronicle of Philanthropy)", "https://www.philanthropy.com/news/giving-to-private-colleges-dropped-last-year-survey-finds/"),
    ("NACUBO FY2009 average endowment return (Chronicle)", "https://www.chronicle.com/article/average-return-on-endowment-investments-is-worst-in-almost-40-years/"),
    ("Private equity cash flows in times of upheaval (AltamarCAM)", "https://www.altamarcam.com/?p=98739"),
    ("Secondaries bids soar in H1 2010 (Private Funds CFO)", "https://www.privatefundscfo.com/print-editions/2010-07/secondaries-bids-soar-in-h1-2010/"),
    ("Harvard endowment 2009 liquidity and commitments (Harvard Magazine)", "https://harvardmagazine.com/2009/11/harvard-endowment-update?page=all"),
]


def r3_scenarios(data: ModelData, inst: InstitutionalParams,
                 p1: Optional[InflationRatesParams] = None, p2: Optional[DownturnLiquidityParams] = None,
                 include: Sequence[str] = (SCENARIO_1, SCENARIO_2)) -> List[StressScenario]:
    out = []
    if SCENARIO_1 in include:
        out.append(build_inflation_rates_scenario(data, inst, p1))
    if SCENARIO_2 in include:
        out.append(build_downturn_liquidity_scenario(data, inst, p2))
    return out


def r3_focus_table(results: Dict[str, Dict[str, object]], cfg: SimulationConfig) -> pd.DataFrame:
    """One row per scenario with the R3 focus measures for both scenarios plus common corpus-risk measures."""
    base = results["Baseline"]["metrics"]
    rows = []
    for name, res in results.items():
        m = res["metrics"]
        rows.append({
            "Scenario": name,
            # Scenario 1 focus: real payout value and funding needs
            "Cumulative real payout ($mm)": m["median_total_real_payout"],
            "Δ real payout vs baseline": m["median_total_real_payout"] / base["median_total_real_payout"] - 1.0,
            "Real payout, first 3 yrs ($mm)": m["median_real_payout_first3"],
            "Pr(any support gap)": m["probability_any_support_gap"],
            "Total support gap ($mm)": m["median_total_support_gap"],
            "Avg payout adequacy": m["median_avg_payout_adequacy"],
            # Scenario 2 focus: required payouts and forced-sale losses
            "Pr(≥1 payout shortfall)": m["probability_at_least_one_shortfall"],
            "Avg shortfall depth": m["average_relative_shortfall_depth"],
            "Pr(forced sale)": m["probability_forced_sale"],
            "Mean forced-sale loss ($mm)": m["mean_forced_sale_loss"],
            "Lowest liquidity coverage (median)": m["median_min_liquidity_coverage"],
            # Common corpus risk
            "Median terminal real ($mm)": m["median_terminal_real_assets"],
            "Δ median real vs baseline": m["median_terminal_real_assets"] / base["median_terminal_real_assets"] - 1.0,
            "5th pct terminal real ($mm)": m["p05_terminal_real_assets"],
            "Pr(real corpus < initial)": m["probability_real_corpus_below_initial"],
            f"ES {int(cfg.alpha*100)}% real-corpus loss": m["expected_shortfall_terminal_real_corpus_loss"],
            "Liquidity constraints": "On" if m["liquidity_constraints"] else "Off",
        })
    return pd.DataFrame(rows)


def variable_impact_table(base_path: pd.DataFrame, stress_path: pd.DataFrame, years: int = 5) -> pd.DataFrame:
    """Year-by-year quantitative effect of a scenario on returns, inflation, expenses, payout and liquidity
    (deterministic path), next to the baseline."""
    b = base_path.head(years).reset_index(drop=True)
    s = stress_path.head(years).reset_index(drop=True)
    rows = []
    spec = [
        ("Portfolio return", "portfolio_return", "pct"),
        ("Inflation (CPI)", "inflation", "pct"),
        ("Operating expenses ($mm)", "operating_expenses", "mm"),
        ("Gifts ($mm)", "endowment_gifts", "mm"),
        ("Real payout ($mm)", "real_payout", "mm"),
        ("Payout support gap ($mm)", "payout_support_gap", "mm"),
        ("Liquidity coverage (x payout)", "liquidity_coverage", "x"),
        ("Private cash drain ($mm)", "capital_call", "mm"),
        ("Forced-sale loss ($mm)", "forced_sale_loss", "mm"),
        ("Real ending assets ($mm)", "real_ending_assets", "mm"),
    ]
    for label, col, kind in spec:
        for which, df in (("Baseline", b), ("Stress", s)):
            row = {"Variable": label, "Path": which, "Unit": kind}
            for i in range(len(df)):
                row[str(int(df.loc[i, "year"]))] = float(df.loc[i, col]) if pd.notna(df.loc[i, col]) else np.nan
            rows.append(row)
    return pd.DataFrame(rows)


def run_r3_framework(data, cfg, inst, liq, p1=None, p2=None, include=(SCENARIO_1, SCENARIO_2),
                     p4_history=None, progress=None):
    scenarios = r3_scenarios(data, inst, p1, p2, include)
    table, results = run_stress_suite(data, cfg, inst, liq, scenarios, p4_history=p4_history, progress=progress)
    det_table, det_paths = run_deterministic_suite(data, cfg, inst, liq, scenarios, p4_history=p4_history)
    return {
        "focus": r3_focus_table(results, cfg),
        "table": table,
        "results": results,
        "det_table": det_table,
        "det_paths": det_paths,
        "paths": median_real_paths(results),
        "real_payout_paths": median_real_paths(results, "real_payout"),
        "calibration": calibration_table(data, inst, p1, p2),
    }



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
