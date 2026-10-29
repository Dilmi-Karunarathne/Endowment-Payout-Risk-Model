from __future__ import annotations

from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple
import math

import numpy as np
import pandas as pd


YEAR_OVERRIDE_DEFAULTS = {
    "gift_multiplier": 1.0,          # x institutional.gift_rate
    "spending_rate_add": 0.0,        # + effective_spending_rate (absolute, e.g. 0.01 = +1pp)
    "other_changes_add": 0.0,        # + other_changes_rate (absolute)
    "expense_level_shock": 0.0,      # one-off % jump in operating expenses applied at the start of that year
    "expense_growth_add": 0.0,       # + annual_expense_growth after that year (absolute)
    "special_draw_rate": 0.0,        # extra outflow from the corpus, % of beginning assets (e.g. emergency appropriation)
    "capital_call_rate": 0.0,        # liquidity demand, % of beginning assets; moves liquid -> illiquid, no corpus loss
    "liquid_share_haircut_add": 0.0, # additional haircut on accessible liquid share (only when liquidity is enabled)
}


def validate_year_overrides(overrides, horizon):
    if overrides is None:
        return pd.DataFrame({k:[v]*horizon for k,v in YEAR_OVERRIDE_DEFAULTS.items()})
    if len(overrides)!=horizon or set(overrides.columns)-set(YEAR_OVERRIDE_DEFAULTS):
        raise ValueError("Stress overrides must have one row per year and known columns.")
    result=pd.DataFrame({k:[v]*horizon for k,v in YEAR_OVERRIDE_DEFAULTS.items()})
    for k in overrides:
        result[k]=overrides[k].to_numpy(dtype=float)
    if not np.isfinite(result.to_numpy()).all():
        raise ValueError("Stress overrides must be finite.")
    if (result[["gift_multiplier","special_draw_rate","capital_call_rate"]]<0).any().any() or (result.expense_level_shock < -1).any():
        raise ValueError("Invalid stress cash-flow or expense override.")
    return result


STATE_ORDER = ["Normal", "Recession", "Elevated inflation"]


@dataclass
class InstitutionalParams:
    institution_type: str = "Private"
    scenario: str = "Base"
    effective_spending_rate: float = 0.04890714173742258
    support_ratio: float = 0.09761966133238931
    expenses_to_endowment_ratio: float = 0.4997373752519529
    annual_expense_growth: float = 0.02784974949013586
    gift_rate: float = 0.01663160466941044
    other_changes_rate: float = 0.001996783679265606
    spending_rule: str = "Trailing average"
    smoothing_years: int = 3
    annual_payout_growth_cap: Optional[float] = None
    annual_payout_growth_floor: Optional[float] = None


@dataclass
class LiquidityParams:
    enabled: bool = False
    liquid_share: float = 0.5567641523873877
    illiquid_share: float = 0.2416515013895071
    liquidity_buffer_years: float = 0.0
    other_annual_cash_need: float = 0.0
    forced_sale_discount: float = 0.0
    allow_forced_sales: bool = True
    liquid_share_haircut: float = 0.0
    minimum_cash_reserve: float = 0.0
    moderately_liquid_access: float = 0.0


@dataclass
class SimulationConfig:
    initial_endowment: float = 150.0
    prior_endowment_2y: float = 150.0
    prior_endowment_1y: float = 150.0
    horizon_years: int = 10
    start_year: int = 2027
    n_sims: int = 5000
    seed: int = 42
    alpha: float = 0.95
    return_method: str = "Regime-switching bootstrap"
    block_size_quarters: int = 4
    starting_regime: str = "Normal"
    stress_state: Optional[str] = None
    stress_quarters: int = 0
    # Shared future scenario: shift annual arithmetic mean, scale deviations.
    annual_return_shift: float = 0.0
    volatility_multiplier: float = 1.0
    # None preserves historical inflation sampling; a number fixes annual CPI.
    annual_inflation: Optional[float] = None
    adverse_probability: Optional[float] = None
    adverse_mean: Optional[float] = None
    adverse_std: Optional[float] = None
    real_corpus_threshold: float = 1.0


@dataclass
class ModelData:
    p4_quarterly: pd.DataFrame
    condition_history: pd.DataFrame
    transition_matrix: pd.DataFrame
    r2_scenarios: pd.DataFrame
    p4_weights: pd.DataFrame
    validation_annual_returns: pd.DataFrame
    calibration: Dict[str, float]


def _default_data_dir() -> Path:
    return Path(__file__).resolve().parent / "data"


def load_default_data(data_dir: Optional[Path] = None) -> ModelData:
    data_dir = Path(data_dir) if data_dir is not None else _default_data_dir()
    p4 = pd.read_csv(data_dir / "p4_quarterly_history.csv")
    cond = pd.read_csv(data_dir / "condition_history.csv")
    trans = pd.read_csv(data_dir / "transition_matrix.csv", index_col=0)
    r2 = pd.read_csv(data_dir / "r2_scenarios.csv")
    weights = pd.read_csv(data_dir / "p4_weights.csv")
    validation = pd.read_csv(data_dir / "validation_annual_returns.csv")
    cal_df = pd.read_csv(data_dir / "calibration.csv")
    calibration = dict(zip(cal_df["key"], cal_df["value"].astype(float)))

    p4["p4_return"] = pd.to_numeric(p4["p4_return"], errors="coerce")
    cond["cpi_yoy"] = pd.to_numeric(cond["cpi_yoy"], errors="coerce")
    validation["year"] = validation["year"].astype(int)
    validation["p4_annual_return"] = pd.to_numeric(validation["p4_annual_return"], errors="coerce")

    # Attach the historical CPI YoY observation for the exact return-sample quarter.
    p4 = p4.merge(cond[["quarter", "cpi_yoy"]], on="quarter", how="left", validate="one_to_one")
    return ModelData(p4, cond, trans, r2, weights, validation, calibration)


def institutional_params_from_data(
    data: ModelData,
    institution_type: str = "Private",
    scenario: str = "Base",
    other_changes_rate: Optional[float] = None,
) -> InstitutionalParams:
    row = data.r2_scenarios[
        (data.r2_scenarios["institution_type"] == institution_type)
        & (data.r2_scenarios["scenario"] == scenario)
    ]
    if row.empty:
        raise ValueError(f"No R2 scenario found for {institution_type} / {scenario}")
    x = row.iloc[0]
    if other_changes_rate is None:
        if institution_type == "Private":
            # R3-derived provisional D2 benchmark. Base is the median; low/high are available as calibration references.
            key = {"Low": "other_changes_rate_low", "Base": "other_changes_rate_base", "High": "other_changes_rate_high"}.get(scenario, "other_changes_rate_base")
            other_changes_rate = float(data.calibration.get(key, data.calibration["other_changes_rate_base"]))
        else:
            # No public cohort benchmark has been finalized for this variable.
            other_changes_rate = 0.0
    return InstitutionalParams(
        institution_type=institution_type,
        scenario=scenario,
        effective_spending_rate=float(x["effective_spending_rate"]),
        support_ratio=float(x["support_ratio"]),
        expenses_to_endowment_ratio=float(x["expenses_to_endowment_ratio"]),
        annual_expense_growth=float(x["annual_expense_growth"]),
        gift_rate=float(x["gift_rate"]),
        other_changes_rate=float(other_changes_rate),
    )


def liquidity_params_from_data(data: ModelData, **overrides) -> LiquidityParams:
    base = LiquidityParams(
        liquid_share=float(data.calibration["liquid_share"]),
        illiquid_share=float(data.calibration["illiquid_share"]),
    )
    return replace(base, **overrides)


def load_excel_overrides(file_or_bytes, data: Optional[ModelData] = None) -> Tuple[SimulationConfig, InstitutionalParams, LiquidityParams, Optional[pd.DataFrame]]:
    """Load the known clean-model cells from an uploaded workbook.

    The workbook is optional; bundled CSV calibration remains the default. Cached Excel formula values
    are used, so users should save/recalculate the workbook in Excel before uploading it.
    """
    from openpyxl import load_workbook

    if isinstance(file_or_bytes, (bytes, bytearray)):
        source = BytesIO(file_or_bytes)
    elif hasattr(file_or_bytes, "read"):
        source = BytesIO(file_or_bytes.read())
    else:
        source = file_or_bytes

    wb = load_workbook(source, data_only=True, read_only=True)
    mi = wb["Model Inputs"]
    r2 = wb["R2 Inputs"]
    r1 = wb["R1 Inputs"]

    cfg = SimulationConfig(
        initial_endowment=float(mi["B8"].value or 150.0),
        prior_endowment_2y=float(mi["B9"].value or mi["B8"].value or 150.0),
        prior_endowment_1y=float(mi["B10"].value or mi["B8"].value or 150.0),
    )
    inst = InstitutionalParams(
        institution_type="Private",
        scenario="Base",
        effective_spending_rate=float(r2["B5"].value),
        gift_rate=float(r2["B6"].value),
        expenses_to_endowment_ratio=float(r2["B7"].value),
        annual_expense_growth=float(r2["B8"].value),
        support_ratio=float(r2["B9"].value),
        other_changes_rate=float(r2["B10"].value or 0.0),
    )
    liq = LiquidityParams(
        enabled=False,
        liquid_share=float(mi["B22"].value),
        illiquid_share=float(mi["B24"].value),
        liquidity_buffer_years=float(mi["B31"].value or 0.0),
        other_annual_cash_need=float(mi["B32"].value or 0.0),
        forced_sale_discount=float(mi["B33"].value or 0.0),
    )

    hist = []
    for row in range(23, 89):
        q = r1[f"A{row}"].value
        if q is None:
            continue
        hist.append(
            {
                "quarter": str(q),
                "condition": str(r1[f"C{row}"].value),
                "p4_return": float(r1[f"D{row}"].value),
            }
        )
    hist_df = pd.DataFrame(hist) if hist else None
    if hist_df is not None and data is not None:
        hist_df = hist_df.merge(data.condition_history[["quarter", "cpi_yoy"]], on="quarter", how="left")
    return cfg, inst, liq, hist_df


def _normalize_probabilities(values: Iterable[float]) -> np.ndarray:
    p = np.asarray(list(values), dtype=float)
    p = np.clip(p, 0.0, None)
    s = p.sum()
    if s <= 0:
        raise ValueError("Transition row has no positive probability")
    return p / s


def simulate_regime_path(
    rng: np.random.Generator,
    n_quarters: int,
    start_state: str,
    transition_matrix: pd.DataFrame,
    stress_state: Optional[str] = None,
    stress_quarters: int = 0,
) -> list[str]:
    if start_state not in STATE_ORDER:
        raise ValueError(f"Unknown start state {start_state}")
    states = []
    current = start_state
    for q in range(n_quarters):
        if stress_state is not None and q < stress_quarters:
            current = stress_state
        elif q > 0:
            probs = _normalize_probabilities(transition_matrix.loc[current, STATE_ORDER].values)
            current = str(rng.choice(STATE_ORDER, p=probs))
        states.append(current)
    return states


def _sample_from_condition(rng: np.random.Generator, df: pd.DataFrame, state: str, column: str) -> float:
    pool = df.loc[df["condition"] == state, column].dropna().to_numpy(dtype=float)
    if pool.size == 0:
        raise ValueError(f"No historical {column} observations for condition {state}")
    return float(rng.choice(pool))


def sample_quarterly_path(
    rng: np.random.Generator,
    data: ModelData,
    config: SimulationConfig,
    p4_history: Optional[pd.DataFrame] = None,
    mixture_parameters=None,
) -> pd.DataFrame:
    p4 = data.p4_quarterly if p4_history is None else p4_history.copy()
    n_quarters = int(config.horizon_years * 4)
    method = config.return_method.lower()

    def finish(path):
        # Same scenario transformation for every return method.
        center = float(p4["p4_return"].mean())
        path["p4_return"] = (center + config.volatility_multiplier *
            (path["p4_return"] - center) + config.annual_return_shift / 4.0)
        if (path["p4_return"] <= -1).any():
            raise ValueError("Scenario produced returns <= -100%; reduce scenario severity.")
        if config.annual_inflation is not None:
            start=min(config.stress_quarters,len(path)) if config.stress_state else 0
            path.loc[path.index[start:], "cpi_yoy"] = config.annual_inflation
        return path.reset_index(drop=True)

    if method == "single normal":
        from portfolio_return_simulation import sample_mixture
        mean = float(p4["p4_return"].mean())
        std = float(p4["p4_return"].std(ddof=1))
        parameters = dict(ordinary_mean=mean, ordinary_std=std,
                          adverse_mean=mean, adverse_std=std, adverse_probability=0.0)
        path = pd.DataFrame({"p4_return": sample_mixture(rng, n_quarters, parameters),
                             "condition": "Single Normal", "cpi_yoy": float(p4["cpi_yoy"].mean())})
        if config.stress_state and config.stress_quarters > 0:
            for q in range(min(config.stress_quarters, n_quarters)):
                path.loc[q, "condition"] = config.stress_state
                path.loc[q, "p4_return"] = _sample_from_condition(rng, p4, config.stress_state, "p4_return")
                path.loc[q, "cpi_yoy"] = _sample_from_condition(rng, data.condition_history, config.stress_state, "cpi_yoy")
        return finish(path)

    if "mixture" in method:
        from portfolio_return_simulation import fit_mixture, sample_mixture
        parameters = mixture_parameters if mixture_parameters is not None else fit_mixture(p4["p4_return"].to_numpy())
        parameters = dict(parameters)
        for key in ["adverse_probability", "adverse_mean", "adverse_std"]:
            if getattr(config, key) is not None:
                parameters[key] = getattr(config, key)
        path = pd.DataFrame({
            "p4_return": sample_mixture(rng, n_quarters, parameters),
            "condition": "Portfolio mixture",
            # No estimated return/inflation dependence in this simple mixture.
            "cpi_yoy": float(p4["cpi_yoy"].mean()),
        })
        if config.stress_state and config.stress_quarters > 0:
            for q in range(min(config.stress_quarters, n_quarters)):
                state = config.stress_state
                path.loc[q, "condition"] = state
                path.loc[q, "p4_return"] = _sample_from_condition(rng, p4, state, "p4_return")
                path.loc[q, "cpi_yoy"] = _sample_from_condition(rng, data.condition_history, state, "cpi_yoy")
        return finish(path)

    if "block" in method:
        block = max(1, int(config.block_size_quarters))
        rows = []
        max_start = max(0, len(p4) - block)
        while len(rows) < n_quarters:
            start = int(rng.integers(0, max_start + 1))
            chunk = p4.iloc[start : start + block]
            rows.extend(chunk.to_dict("records"))
        path = pd.DataFrame(rows[:n_quarters])[["p4_return", "condition", "cpi_yoy"]].copy()

        # Stress override: replace the first stress window with condition-specific historical observations.
        if config.stress_state and config.stress_quarters > 0:
            for q in range(min(config.stress_quarters, n_quarters)):
                state = config.stress_state
                path.loc[q, "condition"] = state
                path.loc[q, "p4_return"] = _sample_from_condition(rng, p4, state, "p4_return")
                path.loc[q, "cpi_yoy"] = _sample_from_condition(rng, data.condition_history, state, "cpi_yoy")
        return finish(path)

    if "regime" in method:
        states = simulate_regime_path(
            rng,
            n_quarters=n_quarters,
            start_state=config.starting_regime,
            transition_matrix=data.transition_matrix,
            stress_state=config.stress_state,
            stress_quarters=config.stress_quarters,
        )
        rows = []
        for state in states:
            rows.append(
                {
                    "condition": state,
                    "p4_return": _sample_from_condition(rng, p4, state, "p4_return"),
                    "cpi_yoy": _sample_from_condition(rng, data.condition_history, state, "cpi_yoy"),
                }
            )
        return finish(pd.DataFrame(rows))

    raise ValueError(f"Unsupported return method: {config.return_method}")


def quarterly_to_annual(quarterly_path: pd.DataFrame, start_year: int) -> pd.DataFrame:
    if len(quarterly_path) % 4 != 0:
        raise ValueError("Quarterly path length must be divisible by four")
    rows = []
    for y in range(len(quarterly_path) // 4):
        block = quarterly_path.iloc[y * 4 : (y + 1) * 4]
        annual_return = float(np.prod(1.0 + block["p4_return"].to_numpy(dtype=float)) - 1.0)
        # Consistent with the validation workbook: annual average of quarterly CPI YoY observations.
        annual_inflation = float(block["cpi_yoy"].mean())
        dominant_state = str(block["condition"].mode().iloc[0])
        rows.append(
            {
                "year": int(start_year + y),
                "portfolio_return": annual_return,
                "inflation": annual_inflation,
                "dominant_condition": dominant_state,
            }
        )
    return pd.DataFrame(rows)


def run_path(
    annual_market: pd.DataFrame,
    config: SimulationConfig,
    institutional: InstitutionalParams,
    liquidity: LiquidityParams,
    year_overrides: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    validate_parameters(config, institutional, liquidity)
    if len(annual_market) != config.horizon_years:
        raise ValueError("Annual market path length must match horizon_years")
    overrides=validate_year_overrides(year_overrides,config.horizon_years)
    history = [config.prior_endowment_2y, config.prior_endowment_1y, config.initial_endowment]
    current = config.initial_endowment
    expenses = current * institutional.expenses_to_endowment_ratio
    cumulative_inflation = 1.0
    nominal_peak = real_peak = current
    # Persistent holdings: uniform portfolio return is applied to each liquidity bucket.
    # No annual reset to target weights; transfers only occur when accessible cash is needed.
    buckets = current * np.array([liquidity.liquid_share,
        1 - liquidity.liquid_share - liquidity.illiquid_share, liquidity.illiquid_share], dtype=float)
    previous_planned = None
    out = []
    for t, market in annual_market.reset_index(drop=True).iterrows():
        r, inflation = float(market["portfolio_return"]), float(market["inflation"])
        if not np.isfinite([r, inflation]).all() or r < -1 or inflation <= -1:
            raise ValueError("Returns must be >= -100%; inflation must exceed -100%.")
        ov=overrides.iloc[t]
        expenses *= 1+ov.expense_level_shock
        expense_growth=institutional.annual_expense_growth+ov.expense_growth_add
        if expense_growth < -1:raise ValueError('Expense growth must be >= -100%.')
        beginning = current
        capital_call=beginning*ov.capital_call_rate
        special_draw=beginning*ov.special_draw_rate
        gain = beginning * r
        gifts = beginning * institutional.gift_rate * ov.gift_multiplier
        changes = beginning * (institutional.other_changes_rate+ov.other_changes_add)
        pre = beginning + gain + gifts + changes
        if pre < -1e-10:
            raise ValueError("Negative assets before distributions; revise other-changes assumption.")
        pre = max(0., pre)
        buckets *= 1 + r
        flows = gifts + changes
        if flows >= 0:
            buckets[0] += flows  # gifts/other positive changes are assumed liquid and unrestricted
        else:
            total = buckets.sum()
            buckets *= max(0., (total + flows) / total) if total > 0 else 0.
        base = beginning if institutional.spending_rule == "Current assets" else np.mean(history[-institutional.smoothing_years:])
        planned = max(0., base * np.clip(institutional.effective_spending_rate+ov.spending_rate_add,0.,1.))
        if previous_planned is not None:
            if institutional.annual_payout_growth_floor is not None:
                planned = max(planned, previous_planned * (1 + institutional.annual_payout_growth_floor))
            if institutional.annual_payout_growth_cap is not None:
                planned = min(planned, previous_planned * (1 + institutional.annual_payout_growth_cap))
        previous_planned = planned
        policy_planned=planned
        planned += special_draw
        requested_other = liquidity.other_annual_cash_need  # endowment-funded only
        reserve = (planned * liquidity.liquidity_buffer_years + liquidity.minimum_cash_reserve) if liquidity.enabled else 0.
        haircut = np.clip(liquidity.liquid_share_haircut+ov.liquid_share_haircut_add,0.,1.) if liquidity.enabled else 0.
        liquid_assets, moderate_assets, illiquid_assets = buckets.copy()
        accessible = buckets[0] * (1 - haircut)
        forced_sale = forced_loss = moderate_sale = 0.
        need = requested_other + capital_call + planned + reserve
        if liquidity.enabled:
            moderate_sale = min(buckets[1] * liquidity.moderately_liquid_access, max(0., need - accessible))
            buckets[1] -= moderate_sale
            buckets[0] += moderate_sale
            accessible += moderate_sale
            if liquidity.allow_forced_sales:
                forced_sale = min(buckets[2], max(0., need - accessible) / (1 - liquidity.forced_sale_discount))
                forced_loss = forced_sale * liquidity.forced_sale_discount
                buckets[2] -= forced_sale
                buckets[0] += forced_sale - forced_loss
                accessible += forced_sale - forced_loss
        else:
            # All assets may be sold at carrying value, but no external funding is assumed.
            accessible = pre
        capacity = max(0., accessible - reserve)
        other_paid = min(requested_other, capacity)
        capital_paid=min(capital_call,max(0.,capacity-other_paid))
        actual = min(planned, max(0., capacity - other_paid - capital_paid))
        total_paid = other_paid + capital_paid + actual
        if liquidity.enabled:
            buckets[0] -= total_paid
        else:
            total = buckets.sum()
            buckets *= max(0., (total - total_paid) / total) if total > 0 else 0.
        buckets[2] += capital_paid
        buckets = np.maximum(buckets, 0.)
        buckets[buckets < 1e-12] = 0.
        ending = float(buckets.sum())
        residual = ending - (pre - actual - other_paid - forced_loss)
        if abs(residual) > 1e-8 * max(1., pre):
            raise ArithmeticError("Endowment roll-forward failed.")
        support = expenses * institutional.support_ratio
        shortfall = max(0., planned - actual)
        coverage_gap = max(0., planned - gain)
        nominal_peak = max(nominal_peak, ending)
        cumulative_inflation *= 1 + inflation
        real = ending / cumulative_inflation
        real_peak = max(real_peak, real)
        out.append(dict(
            year=int(market["year"]), dominant_condition=market.get("dominant_condition", ""),
            beginning_assets=beginning, portfolio_return=r, investment_gain=gain,
            pre_payout_assets=pre, planned_payout=planned, actual_payout=actual,
            capital_call=capital_call, capital_call_paid=capital_paid, unpaid_capital_call=capital_call-capital_paid,
            special_draw_requested=special_draw, special_draw_paid=min(special_draw,max(0.,actual-policy_planned)),
            effective_liquid_haircut=haircut,
            endowment_gifts=gifts, other_endowment_changes=changes,
            liquid_assets=liquid_assets, moderately_liquid_assets=moderate_assets, illiquid_assets=illiquid_assets,
            ending_liquid_assets=buckets[0], ending_moderately_liquid_assets=buckets[1], ending_illiquid_assets=buckets[2],
            required_liquidity=reserve + requested_other + capital_call if liquidity.enabled else np.nan,
            liquidity_shortfall=max(0., planned + requested_other + capital_call + reserve - liquid_assets * (1-haircut)) if liquidity.enabled else np.nan,
            forced_sale=forced_sale, forced_sale_loss=forced_loss, moderately_liquid_sale=moderate_sale,
            other_annual_cash_need=requested_other, other_cash_paid=other_paid,
            unpaid_other_cash_need=requested_other-other_paid, reserve_target=reserve,
            reserve_shortfall=max(0., reserve-max(0., accessible-total_paid)),
            ending_assets=ending, accounting_residual=residual, operating_expenses=expenses,
            required_support=support, payout_support_gap=max(0., support-actual),
            payout_adequacy_ratio=actual/support if support > 0 else np.nan,
            nominal_running_peak=nominal_peak, nominal_drawdown=ending/nominal_peak-1,
            inflation=inflation, cumulative_inflation_index=cumulative_inflation,
            real_ending_assets=real, real_running_peak=real_peak, real_drawdown=real/real_peak-1,
            real_actual_payout=actual/cumulative_inflation,
            payout_shortfall_indicator=int(shortfall > 1e-10), payout_shortfall_amount=shortfall,
            relative_shortfall_depth=shortfall/planned if planned > 0 else 0.,
            return_coverage_shortfall_indicator=int(coverage_gap > 1e-10),
            return_coverage_shortfall_amount=coverage_gap,
            relative_coverage_shortfall_depth=coverage_gap/planned if planned > 0 else 0.,
            effective_payout_requirement=planned/beginning if beginning > 0 else np.nan,
            real_corpus_below_threshold=int(real < config.initial_endowment*config.real_corpus_threshold-1e-10),
            insolvent=ending <= 1e-12))
        history.append(ending)
        current = ending
        expenses *= 1 + expense_growth
    return pd.DataFrame(out)


def validate_parameters(config, institution, liquidity):
    numeric = [v for obj in (config, institution, liquidity) for v in vars(obj).values()
               if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not np.isfinite(numeric).all():
        raise ValueError("All numeric inputs must be finite.")
    if min(config.initial_endowment, config.prior_endowment_1y, config.prior_endowment_2y) <= 0:
        raise ValueError("Starting and prior endowments must be positive.")
    if config.horizon_years < 1 or config.n_sims < 1 or config.volatility_multiplier <= 0 or (config.annual_inflation is not None and config.annual_inflation <= -1):
        raise ValueError("Invalid horizon, path count, volatility or inflation.")
    if not 0 < config.alpha < 1 or not 0 < config.real_corpus_threshold <= 1:
        raise ValueError("Confidence and corpus threshold must lie in their valid ranges.")
    if institution.spending_rule not in ["Trailing average", "Current assets"] or not 1 <= institution.smoothing_years <= 3:
        raise ValueError("Use Current assets or a 1–3 year Trailing average rule.")
    if not 0 <= institution.effective_spending_rate <= 1 or institution.gift_rate < 0 or institution.expenses_to_endowment_ratio < 0:
        raise ValueError("Invalid spending, gift, or expense assumption.")
    floor, cap = institution.annual_payout_growth_floor, institution.annual_payout_growth_cap
    if any(x is not None and x < -1 for x in (floor, cap)) or (floor is not None and cap is not None and floor > cap):
        raise ValueError("Invalid payout growth floor/cap.")
    if institution.annual_expense_growth < -1 or institution.support_ratio < 0:
        raise ValueError("Invalid support or expense growth assumption.")
    if not 0 <= liquidity.liquid_share <= 1 or not 0 <= liquidity.illiquid_share <= 1 or liquidity.liquid_share + liquidity.illiquid_share > 1 + 1e-12:
        raise ValueError("Liquid and illiquid shares must be nonnegative and sum to at most 100%.")
    if min(liquidity.other_annual_cash_need, liquidity.minimum_cash_reserve, liquidity.liquidity_buffer_years) < 0:
        raise ValueError("Cash obligations and reserves cannot be negative.")
    if not 0 <= liquidity.forced_sale_discount < 1 or not 0 <= liquidity.liquid_share_haircut <= 1 or not 0 <= liquidity.moderately_liquid_access <= 1:
        raise ValueError("Invalid liquidity access or discount assumption.")
    if config.adverse_probability is not None and not 0 <= config.adverse_probability <= 1:
        raise ValueError("Adverse probability must be between zero and one.")
    if config.adverse_std is not None and config.adverse_std <= 0:
        raise ValueError("Adverse volatility must be positive.")


def longest_spell(indicators):
    longest = current = 0
    for flag in indicators:
        current = current + 1 if flag else 0
        longest = max(longest, current)
    return longest


def recovery_statistics(path):
    """First threshold breach to first recovery; incomplete spells are right censored."""
    below = path["real_corpus_below_threshold"].to_numpy(bool)
    if not below.any():
        return dict(recovery_years=np.nan, recovery_censored=False, erosion_spell_observed=0)
    start = int(np.flatnonzero(below)[0])
    recoveries = np.flatnonzero(~below[start+1:])
    observed = int(recoveries[0]+1) if len(recoveries) else len(below)-start
    return dict(recovery_years=observed if len(recoveries) else np.nan,
                recovery_censored=not bool(len(recoveries)), erosion_spell_observed=observed)


def historical_validation(
    data: ModelData,
    config: Optional[SimulationConfig] = None,
    institutional: Optional[InstitutionalParams] = None,
    liquidity: Optional[LiquidityParams] = None,
) -> pd.DataFrame:
    config = config or SimulationConfig(start_year=2013, horizon_years=10, n_sims=1)
    institutional = institutional or institutional_params_from_data(data, "Private", "Base")
    liquidity = liquidity or liquidity_params_from_data(data, enabled=False)

    q = data.p4_quarterly.copy()
    q["year"] = q["quarter"].str[:4].astype(int)
    q = q[(q["year"] >= 2013) & (q["year"] <= 2022)].copy()
    annual = quarterly_to_annual(q[["p4_return", "condition", "cpi_yoy"]], start_year=2013)
    return run_path(annual, config, institutional, liquidity)


def summarize_path(path: pd.DataFrame, initial_endowment: float) -> Dict[str, float]:
    short = path["payout_shortfall_indicator"].astype(bool)
    terminal_real = float(path["real_ending_assets"].iloc[-1])
    return {
        "ending_assets": float(path["ending_assets"].iloc[-1]),
        "terminal_real_assets": terminal_real,
        "total_payout": float(path["actual_payout"].sum()),
        "total_gifts": float(path["endowment_gifts"].sum()),
        "shortfall_frequency": float(path["payout_shortfall_indicator"].mean()),
        "average_shortfall_amount": float(path.loc[short, "payout_shortfall_amount"].mean()) if short.any() else 0.0,
        "average_relative_shortfall_depth": float(path.loc[short, "relative_shortfall_depth"].mean()) if short.any() else 0.0,
        "max_nominal_drawdown": float(path["nominal_drawdown"].min()),
        "max_real_drawdown": float(path["real_drawdown"].min()),
        "terminal_real_corpus_loss": max(0.0, 1.0 - terminal_real / initial_endowment),
        "years_with_support_gap": float((path["payout_support_gap"] > 0).sum()),
        "average_payout_adequacy": float(path["payout_adequacy_ratio"].mean()),
    }


def _tail_var_es(losses: np.ndarray, alpha: float) -> Tuple[float, float]:
    losses = np.asarray(losses, dtype=float)
    losses = losses[np.isfinite(losses)]
    if losses.size == 0:
        return np.nan, np.nan
    alpha = float(np.clip(alpha, 0.50, 0.999))
    var = float(np.quantile(losses, alpha))
    k = max(1, int(math.ceil((1.0 - alpha) * losses.size - 1e-12)))
    es = float(np.sort(losses)[-k:].mean())
    return var, es


def run_monte_carlo(
    data: ModelData,
    config: SimulationConfig,
    institutional: InstitutionalParams,
    liquidity: LiquidityParams,
    p4_history: Optional[pd.DataFrame] = None,
    keep_paths: bool = True,
    path_transform=None,
    year_overrides: Optional[pd.DataFrame] = None,
) -> Dict[str, object]:
    from portfolio_return_simulation import checked_history, fit_mixture
    validate_parameters(config, institutional, liquidity)
    history = checked_history(data.p4_quarterly if p4_history is None else p4_history)
    if config.n_sims < 1 or config.horizon_years < 1:
        raise ValueError("Use a positive simulation count and horizon.")
    if not 1 <= config.block_size_quarters <= len(history):
        raise ValueError("Block size must fit within the history.")
    if config.volatility_multiplier <= 0 or (config.annual_inflation is not None and config.annual_inflation <= -1):
        raise ValueError("Invalid volatility or inflation assumption.")
    mixture = fit_mixture(history["p4_return"].to_numpy()) if "mixture" in config.return_method.lower() else None
    rng = np.random.default_rng(config.seed)
    quarterly_returns = []
    investment_drawdowns = []
    annual_records = []
    path_records = []

    for path_id in range(config.n_sims):
        qpath = sample_quarterly_path(rng, data, config, p4_history=history, mixture_parameters=mixture)
        if path_transform is not None:qpath=path_transform(rng,qpath)
        if len(qpath)!=config.horizon_years*4 or not np.isfinite(qpath[['p4_return','cpi_yoy']].to_numpy()).all() or (qpath.p4_return < -1).any() or (qpath.cpi_yoy <= -1).any():
            raise ValueError('Invalid stressed quarterly path.')
        returns = qpath["p4_return"].to_numpy()
        quarterly_returns.append(returns)
        wealth = np.r_[1.0, np.cumprod(1.0 + returns)]
        investment_drawdowns.append(float((wealth / np.maximum.accumulate(wealth) - 1).min()))
        annual_market = quarterly_to_annual(qpath, config.start_year)
        path = run_path(annual_market, config, institutional, liquidity,year_overrides=year_overrides)
        path.insert(0, "path_id", path_id)
        if keep_paths:
            annual_records.append(path)

        short_mask = path["payout_shortfall_indicator"].astype(bool)
        terminal_real = float(path["real_ending_assets"].iloc[-1])
        terminal_nominal = float(path["ending_assets"].iloc[-1])
        path_records.append(
            {
                "path_id": path_id,
                "coverage_shortfall_years": int(path["return_coverage_shortfall_indicator"].sum()),
                "longest_coverage_shortfall_spell": longest_spell(path["return_coverage_shortfall_indicator"]),
                "longest_funding_shortfall_spell": longest_spell(path["payout_shortfall_indicator"]),
                "erosion_years": int(path["real_corpus_below_threshold"].sum()),
                "longest_erosion_spell": longest_spell(path["real_corpus_below_threshold"]),
                "cumulative_real_payout": float(path["real_actual_payout"].sum()),
                "total_unpaid_other_cash": float(path["unpaid_other_cash_need"].sum()),
                "coverage_gap_sum": float(path["return_coverage_shortfall_amount"].sum()),
                "relative_coverage_gap_sum": float(path["relative_coverage_shortfall_depth"].sum()),
                "funding_gap_sum": float(path["payout_shortfall_amount"].sum()),
                "relative_funding_gap_sum": float(path["relative_shortfall_depth"].sum()),
                **recovery_statistics(path),
                "terminal_nominal_assets": terminal_nominal,
                "terminal_real_assets": terminal_real,
                "terminal_real_corpus_loss": max(0.0, 1.0 - terminal_real / config.initial_endowment),
                "shortfall_years": int(short_mask.sum()),
                "at_least_one_shortfall": int(short_mask.any()),
                "avg_shortfall_amount": float(path.loc[short_mask, "payout_shortfall_amount"].mean()) if short_mask.any() else 0.0,
                "avg_relative_shortfall_depth": float(path.loc[short_mask, "relative_shortfall_depth"].mean()) if short_mask.any() else 0.0,
                "max_relative_shortfall_depth": float(path["relative_shortfall_depth"].max()),
                "max_nominal_drawdown": float(path["nominal_drawdown"].min()),
                "max_real_drawdown": float(path["real_drawdown"].min()),
                "support_gap_years": int((path["payout_support_gap"] > 0).sum()),
                "total_support_gap": float(path["payout_support_gap"].sum()),
                "insolvent": int(path["insolvent"].any()),
            }
        )

    path_summary = pd.DataFrame(path_records)
    annual_results = pd.concat(annual_records, ignore_index=True) if keep_paths else pd.DataFrame()
    var, es = _tail_var_es(path_summary["terminal_real_corpus_loss"].to_numpy(), config.alpha)

    shortfall_events = annual_results[annual_results["payout_shortfall_indicator"] == 1] if not annual_results.empty else pd.DataFrame()
    annual_shortfall_probability = (
        annual_results.groupby("year")["payout_shortfall_indicator"].mean().rename("shortfall_probability").reset_index()
        if not annual_results.empty
        else pd.DataFrame(columns=["year", "shortfall_probability"])
    )

    returns_flat = np.concatenate(quarterly_returns)
    tail_count = max(1, int(math.ceil(0.05 * len(returns_flat))))
    metrics = {
        "negative_quarter_probability": float((returns_flat < 0).mean()),
        "p05_quarterly_return": float(np.quantile(returns_flat, 0.05)),
        "quarterly_tail_mean": float(np.sort(returns_flat)[:tail_count].mean()),
        "median_investment_drawdown": float(np.median(investment_drawdowns)),
        "n_sims": int(config.n_sims),
        "alpha": float(config.alpha),
        "median_terminal_nominal_assets": float(path_summary["terminal_nominal_assets"].median()),
        "median_terminal_real_assets": float(path_summary["terminal_real_assets"].median()),
        "p05_terminal_real_assets": float(path_summary["terminal_real_assets"].quantile(0.05)),
        "p95_terminal_real_assets": float(path_summary["terminal_real_assets"].quantile(0.95)),
        "annual_shortfall_probability": float(path_summary["shortfall_years"].sum() / (config.n_sims * config.horizon_years)),
        "probability_at_least_one_shortfall": float(path_summary["at_least_one_shortfall"].mean()),
        "average_shortfall_amount": float(path_summary["funding_gap_sum"].sum() / max(1, path_summary["shortfall_years"].sum())),
        "average_relative_shortfall_depth": float(path_summary["relative_funding_gap_sum"].sum() / max(1, path_summary["shortfall_years"].sum())),
        "var_terminal_real_corpus_loss": var,
        "expected_shortfall_terminal_real_corpus_loss": es,
        "probability_any_support_gap": float((path_summary["support_gap_years"] > 0).mean()),
        "probability_insolvency": float(path_summary["insolvent"].mean()),
        "median_max_real_drawdown": float(path_summary["max_real_drawdown"].median()),
    }

    metrics.update({
        "annual_coverage_shortfall_probability": float(path_summary.coverage_shortfall_years.sum() / (config.n_sims*config.horizon_years)),
        "probability_any_coverage_shortfall": float((path_summary.coverage_shortfall_years > 0).mean()),
        "conditional_coverage_shortfall_amount": float(path_summary.coverage_gap_sum.sum()/max(1, path_summary.coverage_shortfall_years.sum())),
        "conditional_relative_coverage_shortfall_depth": float(path_summary.relative_coverage_gap_sum.sum()/max(1, path_summary.coverage_shortfall_years.sum())),
        "median_longest_coverage_spell": float(path_summary.longest_coverage_shortfall_spell.median()),
        "median_longest_funding_spell": float(path_summary.longest_funding_shortfall_spell.median()),
        "probability_real_corpus_erosion": float((path_summary.erosion_years > 0).mean()),
        "median_erosion_years": float(path_summary.erosion_years.median()),
        "median_longest_erosion_spell": float(path_summary.longest_erosion_spell.median()),
        "median_completed_recovery_years": float(path_summary.recovery_years.median()) if path_summary.recovery_years.notna().any() else np.nan,
        "probability_unrecovered_given_erosion": float(path_summary.loc[path_summary.erosion_years > 0, "recovery_censored"].mean()) if (path_summary.erosion_years > 0).any() else np.nan,
        "median_cumulative_real_payout": float(path_summary.cumulative_real_payout.median()),
        "probability_unpaid_other_obligation": float((path_summary.total_unpaid_other_cash > 1e-10).mean()),
    })
    return {
        "metrics": metrics,
        "path_summary": path_summary,
        "annual_results": annual_results,
        "annual_shortfall_probability": annual_shortfall_probability,
    }


def percentile_path(annual_results: pd.DataFrame, column: str = "real_ending_assets", percentiles=(0.05, 0.5, 0.95)) -> pd.DataFrame:
    if annual_results.empty:
        return pd.DataFrame()
    frames = []
    for p in percentiles:
        x = annual_results.groupby("year")[column].quantile(p).rename(f"p{int(round(p*100)):02d}")
        frames.append(x)
    return pd.concat(frames, axis=1).reset_index()


def stress_configs(base: SimulationConfig, recession_quarters: int = 6, inflation_quarters: int = 8) -> Dict[str, SimulationConfig]:
    return {
        "Baseline": replace(base, stress_state=None, stress_quarters=0),
        "Recession start": replace(base, stress_state="Recession", stress_quarters=int(recession_quarters)),
        "Elevated inflation start": replace(base, stress_state="Elevated inflation", stress_quarters=int(inflation_quarters)),
    }


if __name__ == "__main__":
    data = load_default_data()
    inst = institutional_params_from_data(data, "Private", "Base")
    liq = liquidity_params_from_data(data, enabled=False)

    print("=== Historical validation ===")
    hist_cfg = SimulationConfig(start_year=2013, horizon_years=10, n_sims=1)
    hist = historical_validation(data, hist_cfg, inst, liq)
    print(hist[["year", "portfolio_return", "ending_assets", "real_ending_assets", "payout_support_gap"]].to_string(index=False))
    print(summarize_path(hist, hist_cfg.initial_endowment))

    print("\n=== Monte Carlo smoke test ===")
    cfg = SimulationConfig(n_sims=250, return_method="Regime-switching bootstrap", seed=7)
    mc = run_monte_carlo(data, cfg, inst, liq)
    print(pd.Series(mc["metrics"]).to_string())
