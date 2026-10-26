"""P4 portfolio-level Normal mixture and controlled bootstrap comparison.

Quarterly arithmetic returns; historical calibration is an assumption, not a forecast.
P4 allocation is held constant. No asset-level drift, trading costs or trade engine.
"""
import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture

SEED = 42

def fit_mixture(history):
    """
    Estimate two Normal components from P4's quarterly returns.

    Lower mean = adverse component.
    Higher mean = ordinary component.

    Historical estimates initialize our future assumptions.
    """

    model = GaussianMixture(
        n_components=2,
        covariance_type="full",
        n_init=20,
        max_iter=1000,
        reg_covar=0.000001,
        random_state=SEED,
    )

    model.fit(history.reshape(-1, 1))

    if not model.converged_:
        raise ValueError("Mixture fitting did not converge.")

    means = model.means_.flatten()
    stds = np.sqrt(model.covariances_.flatten())

    adverse, ordinary = np.argsort(means)

    return {
        "ordinary_mean": means[ordinary],
        "ordinary_std": stds[ordinary],
        "adverse_mean": means[adverse],
        "adverse_std": stds[adverse],
        "adverse_probability": model.weights_[adverse],
    }



def sample_mixture(rng, quarters, assumptions):
    """Independent component choice per quarter; reject returns <= -100%."""
    if not all(np.isfinite(v) for v in assumptions.values()) or not 0 <= assumptions["adverse_probability"] <= 1 or min(assumptions["ordinary_std"], assumptions["adverse_std"]) <= 0:
        raise ValueError("Invalid Normal component assumptions.")
    adverse = rng.random(quarters) < assumptions["adverse_probability"]
    means = np.where(adverse, assumptions["adverse_mean"], assumptions["ordinary_mean"])
    stds = np.where(adverse, assumptions["adverse_std"], assumptions["ordinary_std"])
    returns = rng.normal(means, stds)
    for _ in range(100):
        bad = returns <= -1
        if not bad.any():
            return returns
        returns[bad] = rng.normal(means[bad], stds[bad])
    raise ValueError("Assumptions produced too many returns below -100%.")


def checked_history(table):
    table = table.sort_values("quarter").reset_index(drop=True).copy()
    quarters = pd.PeriodIndex(table["quarter"], freq="Q")
    returns = table["p4_return"].to_numpy(dtype=float)
    if quarters.has_duplicates or not np.all(np.diff(quarters.asi8) == 1):
        raise ValueError("Historical quarters must be unique and consecutive.")
    if len(returns) < 12 or not np.isfinite(returns).all() or (returns <= -1).any() or returns.std() < 1e-8:
        raise ValueError("Need at least 12 valid, varying quarterly portfolio returns.")
    if not np.isfinite(table["cpi_yoy"].to_numpy(dtype=float)).all():
        raise ValueError("Each historical quarter needs an inflation observation.")
    return table


def compare_return_methods(data, config, institution, liquidity, p4_history=None):
    """Change ONLY the generator; share portfolio, settings and fixed inflation.

    If the dashboard uses sampled inflation, use the historical CPI YoY mean
    for BOTH comparison runs to isolate the return-generation effect.
    Sidebar stress overrides are deliberately excluded from this baseline test.
    """
    from dataclasses import replace
    from endowment_simulation_model import run_monte_carlo

    history = checked_history(data.p4_quarterly if p4_history is None else p4_history)
    inflation = config.annual_inflation
    if inflation is None:
        inflation = float(history["cpi_yoy"].mean())
    shared = replace(config, annual_inflation=inflation, stress_state=None, stress_quarters=0)
    rows = {}
    results = {}
    for method in ["Single Normal", "Two-component Normal mixture", "Quarterly block bootstrap"]:
        result = run_monte_carlo(data, replace(shared, return_method=method), institution, liquidity, p4_history=history)
        results[method] = result
        m = result["metrics"]
        rows[method] = {
            "Negative quarters (%)": 100*m["negative_quarter_probability"],
            "5th percentile quarterly return (%)": 100*m["p05_quarterly_return"],
            "Average worst 5% quarterly return (%)": 100*m["quarterly_tail_mean"],
            "Median maximum investment drawdown (%)": 100*m["median_investment_drawdown"],
            "Median terminal real endowment ($M)": m["median_terminal_real_assets"],
            "5th percentile terminal real endowment ($M)": m["p05_terminal_real_assets"],
            "Annual payout execution shortfall (%)": 100*m["annual_shortfall_probability"],
            "Average relative execution shortfall depth (%)": 100*m["average_relative_shortfall_depth"],
            "Probability of any support gap (%)": 100*m["probability_any_support_gap"],
            f"ES {config.alpha:.0%} terminal real-corpus loss (%)": 100*m["expected_shortfall_terminal_real_corpus_loss"],
        }
    return pd.DataFrame(rows), fit_mixture(history["p4_return"].to_numpy()), inflation, results


if __name__ == "__main__":
    from endowment_simulation_model import (load_default_data, SimulationConfig,
        institutional_params_from_data, liquidity_params_from_data)
    data = load_default_data()
    table, assumptions, inflation, _ = compare_return_methods(
        data, SimulationConfig(), institutional_params_from_data(data), liquidity_params_from_data(data))
    print(f"Shared annual inflation: {inflation:.2%}")
    print(pd.Series(assumptions).to_string())
    print(table.round(3).to_string())
