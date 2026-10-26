from __future__ import annotations

from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple
import math

import numpy as np
import pandas as pd


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
) -> pd.DataFrame:
    p4 = data.p4_quarterly if p4_history is None else p4_history.copy()
    n_quarters = int(config.horizon_years * 4)
    method = config.return_method.lower()

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
        return path.reset_index(drop=True)

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
        return pd.DataFrame(rows)

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
) -> pd.DataFrame:
    if len(annual_market) != config.horizon_years:
        raise ValueError("Annual market path length must match horizon_years")

    history = [float(config.prior_endowment_2y), float(config.prior_endowment_1y), float(config.initial_endowment)]
    current = float(config.initial_endowment)
    expenses = float(config.initial_endowment * institutional.expenses_to_endowment_ratio)
    cumulative_inflation = 1.0
    nominal_peak = current
    real_peak = current
    out = []

    for i, market in annual_market.reset_index(drop=True).iterrows():
        year = int(market["year"])
        portfolio_return = float(market["portfolio_return"])
        inflation = float(market["inflation"])

        beginning = current
        investment_gain = beginning * portfolio_return
        gifts = beginning * institutional.gift_rate
        other_changes = beginning * institutional.other_changes_rate
        pre_payout = beginning + investment_gain + gifts + other_changes

        planned_payout = float(np.mean(history[-3:]) * institutional.effective_spending_rate)

        liquid_assets = pre_payout * liquidity.liquid_share
        illiquid_assets = pre_payout * liquidity.illiquid_share
        required_liquidity = np.nan
        liquidity_shortfall = np.nan
        forced_sale = 0.0
        forced_sale_loss = 0.0
        other_cash_need = 0.0

        if liquidity.enabled:
            effective_liquid_share = float(np.clip(liquidity.liquid_share * (1.0 - liquidity.liquid_share_haircut), 0.0, 1.0))
            liquid_assets = pre_payout * effective_liquid_share
            illiquid_assets = pre_payout * liquidity.illiquid_share
            other_cash_need = max(0.0, float(liquidity.other_annual_cash_need))
            required_liquidity = planned_payout * max(0.0, liquidity.liquidity_buffer_years) + other_cash_need
            # Reserve and other annual cash needs must be met before the payout is funded from highly liquid assets.
            payout_cash_capacity = max(0.0, liquid_assets - required_liquidity)
            liquidity_shortfall = max(0.0, planned_payout - payout_cash_capacity)

            if liquidity.allow_forced_sales and liquidity_shortfall > 0:
                discount = float(np.clip(liquidity.forced_sale_discount, 0.0, 0.95))
                gross_needed = liquidity_shortfall / max(1e-12, 1.0 - discount)
                forced_sale = min(illiquid_assets, gross_needed)
                net_forced_sale_proceeds = forced_sale * (1.0 - discount)
                forced_sale_loss = forced_sale * discount
                actual_payout = min(planned_payout, payout_cash_capacity + net_forced_sale_proceeds)
            else:
                actual_payout = min(planned_payout, payout_cash_capacity)
        else:
            actual_payout = planned_payout

        ending = pre_payout - actual_payout - forced_sale_loss - other_cash_need
        ending = max(0.0, ending)

        required_support = expenses * institutional.support_ratio
        payout_support_gap = max(0.0, required_support - actual_payout)
        payout_adequacy_ratio = actual_payout / required_support if required_support > 0 else np.nan

        shortfall_amount = max(0.0, planned_payout - actual_payout)
        shortfall_indicator = 1 if shortfall_amount > 1e-12 else 0
        relative_shortfall_depth = shortfall_amount / planned_payout if planned_payout > 0 else 0.0

        nominal_peak = max(nominal_peak, ending)
        nominal_drawdown = ending / nominal_peak - 1.0 if nominal_peak > 0 else 0.0

        cumulative_inflation *= max(1e-9, 1.0 + inflation)
        real_ending = ending / cumulative_inflation
        real_peak = max(real_peak, real_ending)
        real_drawdown = real_ending / real_peak - 1.0 if real_peak > 0 else 0.0

        out.append(
            {
                "year": year,
                "dominant_condition": market.get("dominant_condition", ""),
                "beginning_assets": beginning,
                "portfolio_return": portfolio_return,
                "investment_gain": investment_gain,
                "pre_payout_assets": pre_payout,
                "planned_payout": planned_payout,
                "actual_payout": actual_payout,
                "endowment_gifts": gifts,
                "other_endowment_changes": other_changes,
                "liquid_assets": liquid_assets,
                "illiquid_assets": illiquid_assets,
                "required_liquidity": required_liquidity,
                "liquidity_shortfall": liquidity_shortfall,
                "forced_sale": forced_sale,
                "forced_sale_loss": forced_sale_loss,
                "other_annual_cash_need": other_cash_need,
                "ending_assets": ending,
                "operating_expenses": expenses,
                "required_support": required_support,
                "payout_support_gap": payout_support_gap,
                "payout_adequacy_ratio": payout_adequacy_ratio,
                "nominal_running_peak": nominal_peak,
                "nominal_drawdown": nominal_drawdown,
                "inflation": inflation,
                "cumulative_inflation_index": cumulative_inflation,
                "real_ending_assets": real_ending,
                "real_running_peak": real_peak,
                "real_drawdown": real_drawdown,
                "payout_shortfall_indicator": shortfall_indicator,
                "payout_shortfall_amount": shortfall_amount,
                "relative_shortfall_depth": relative_shortfall_depth,
                "insolvent": ending <= 0.0,
            }
        )

        history.append(ending)
        current = ending
        expenses *= (1.0 + institutional.annual_expense_growth)

    return pd.DataFrame(out)


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
    k = max(1, int(math.ceil((1.0 - alpha) * losses.size)))
    es = float(np.sort(losses)[-k:].mean())
    return var, es


def run_monte_carlo(
    data: ModelData,
    config: SimulationConfig,
    institutional: InstitutionalParams,
    liquidity: LiquidityParams,
    p4_history: Optional[pd.DataFrame] = None,
    keep_paths: bool = True,
) -> Dict[str, object]:
    rng = np.random.default_rng(config.seed)
    annual_records = []
    path_records = []

    for path_id in range(config.n_sims):
        qpath = sample_quarterly_path(rng, data, config, p4_history=p4_history)
        annual_market = quarterly_to_annual(qpath, config.start_year)
        path = run_path(annual_market, config, institutional, liquidity)
        path.insert(0, "path_id", path_id)
        if keep_paths:
            annual_records.append(path)

        short_mask = path["payout_shortfall_indicator"].astype(bool)
        terminal_real = float(path["real_ending_assets"].iloc[-1])
        terminal_nominal = float(path["ending_assets"].iloc[-1])
        path_records.append(
            {
                "path_id": path_id,
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

    metrics = {
        "n_sims": int(config.n_sims),
        "alpha": float(config.alpha),
        "median_terminal_nominal_assets": float(path_summary["terminal_nominal_assets"].median()),
        "median_terminal_real_assets": float(path_summary["terminal_real_assets"].median()),
        "p05_terminal_real_assets": float(path_summary["terminal_real_assets"].quantile(0.05)),
        "p95_terminal_real_assets": float(path_summary["terminal_real_assets"].quantile(0.95)),
        "annual_shortfall_probability": float(annual_results["payout_shortfall_indicator"].mean()) if not annual_results.empty else np.nan,
        "probability_at_least_one_shortfall": float(path_summary["at_least_one_shortfall"].mean()),
        "average_shortfall_amount": float(shortfall_events["payout_shortfall_amount"].mean()) if not shortfall_events.empty else 0.0,
        "average_relative_shortfall_depth": float(shortfall_events["relative_shortfall_depth"].mean()) if not shortfall_events.empty else 0.0,
        "var_terminal_real_corpus_loss": var,
        "expected_shortfall_terminal_real_corpus_loss": es,
        "probability_any_support_gap": float((path_summary["support_gap_years"] > 0).mean()),
        "probability_insolvency": float(path_summary["insolvent"].mean()),
        "median_max_real_drawdown": float(path_summary["max_real_drawdown"].median()),
    }

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
