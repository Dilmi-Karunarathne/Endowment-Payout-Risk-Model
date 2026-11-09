"""Policy comparisons and data-backed allocation construction."""
from dataclasses import replace
import numpy as np
import pandas as pd
from endowment_simulation_model import run_monte_carlo
from portfolio_return_simulation import checked_history


def portfolio_from_assets(asset_history, weights, condition_history):
    required = {'asset', 'weight', 'liquidity_class'}
    if not required.issubset(weights.columns) or 'quarter' not in asset_history:
        raise ValueError('Weights need asset,weight,liquidity_class; returns need quarter plus asset columns.')
    if weights.asset.duplicated().any() or weights.empty:
        raise ValueError('Each asset must appear once in the weights.')
    w = weights.set_index('asset')['weight'].astype(float)
    if not np.isfinite(w).all() or (w < 0).any() or not np.isclose(w.sum(), 1., atol=1e-8):
        raise ValueError('Weights must be finite, nonnegative and sum to 1.')
    allowed = {'Very High', 'High', 'Moderate', 'Low', 'Very Low'}
    if not set(weights.liquidity_class).issubset(allowed):
        raise ValueError('Unknown liquidity class.')
    missing = set(w.index) - set(asset_history.columns)
    if missing:
        raise ValueError('Missing asset-return columns: ' + ', '.join(sorted(missing)))
    a = asset_history[list(w.index)].astype(float)
    if not np.isfinite(a).all().all() or (a <= -1).any().any():
        raise ValueError('Asset returns must be finite decimal quarterly returns above -100%.')
    history = pd.DataFrame({'quarter': asset_history.quarter.astype(str), 'portfolio_return': a.to_numpy() @ w.to_numpy()})
    # Fixed weights imply cost-free quarterly rebalancing of the return benchmark.
    history = history.merge(condition_history[['quarter', 'condition', 'cpi_yoy']], on='quarter', how='left', validate='one_to_one')
    history = checked_history(history)
    if history.condition.isna().any():
        raise ValueError('Every quarter needs a matching economic-condition label in bundled data.')
    liquid = float(weights.loc[weights.liquidity_class.isin(['Very High', 'High']), 'weight'].sum())
    illiquid = float(weights.loc[weights.liquidity_class.isin(['Low', 'Very Low']), 'weight'].sum())
    return history, liquid, illiquid


def policy_cases(config, institution, liquidity, alternate_spending_rate=.04, buffer_years=.5):
    return {
        'Anchor policy': (config, institution, liquidity),
        'Current-assets spending': (config, replace(institution, spending_rule='Current assets'), liquidity),
        'Alternative spending rate': (config, replace(institution, effective_spending_rate=alternate_spending_rate), liquidity),
    }


def comparison_row(label, result):
    m = result['metrics']
    return {'Scenario': label,
        'Pr(liquidity constraint breach)':m['probability_liquidity_breach'],
        'Pr(real payout cut >5%)':m['probability_real_payout_cut'],
        'Median minimum liquid share':m['median_minimum_liquid_share'],
        'Median minimum payout coverage (years)':m['median_minimum_liquidity_coverage'],
        'Annual return-coverage shortfall': m['annual_coverage_shortfall_probability'],
        'Pr(any payout funding shortfall)': m['probability_at_least_one_shortfall'],
        'Annual payout funding shortfall': m['annual_shortfall_probability'],
        'Conditional funding depth': m['average_relative_shortfall_depth'],
        'Median longest coverage spell (years)': m['median_longest_coverage_spell'],
        'Median longest funding spell (years)': m['median_longest_funding_spell'],
        'Pr(real corpus erosion)': m['probability_real_corpus_erosion'],
        'Median terminal real corpus ($M)': m['median_terminal_real_assets'],
        'Median cumulative real payouts ($M)': m['median_cumulative_real_payout'],
        'Terminal real-corpus ES': m['expected_shortfall_terminal_real_corpus_loss'],
        'Pr(unpaid other obligation)': m['probability_unpaid_other_obligation']}


def compare_cases(data, cases, history=None):
    rows = []
    for label, (c, i, l) in cases.items():
        rows.append(comparison_row(label, run_monte_carlo(data, c, i, l, portfolio_history=history, keep_paths=False)))
    return pd.DataFrame(rows)


def load_six_portfolio_weights(path=None):
    """Validate supplied weights without assigning unconfirmed cohort labels."""
    from pathlib import Path
    path=Path(path) if path is not None else Path(__file__).with_name('data')/'six_portfolio_weights.csv'
    frame=pd.read_csv(path,encoding='utf-8-sig')
    identifiers=['asset_id','asset_name','bucket']
    columns={f'{institution}_{state}_weight':(institution.title(),label)
             for institution in ['private','public']
             for state,label in [('normal','Normal'),('elevated_inflation','Elevated Inflation'),('recession','Recession')]}
    if not set(identifiers+list(columns)).issubset(frame.columns):
        raise ValueError('The six-portfolio file is missing asset identifiers or one of its six weight columns.')
    if frame.empty or frame.asset_id.isna().any() or frame.asset_id.duplicated().any():
        raise ValueError('Each asset ID must be present and unique.')
    values=frame[list(columns)].apply(pd.to_numeric,errors='raise')
    if not np.isfinite(values.to_numpy()).all() or (values<0).any().any():
        raise ValueError('Portfolio weights must be finite and nonnegative.')
    if not np.allclose(values.sum().to_numpy(),1.,atol=1e-8,rtol=0):
        raise ValueError('Each of the six portfolios must sum to 100%.')
    rows=[]
    for col,(institution,state) in columns.items():
        block=frame[identifiers].copy()
        block['institution']=institution;block['economic_condition']=state
        block['weight']=values[col];rows.append(block)
    return pd.concat(rows,ignore_index=True)


def build_selected_portfolio(monthly_assets, matrix, conditions, institution, allocation):
    """Fixed weights rebalanced monthly, then geometrically aggregated by quarter.

    The as-of allocations applied retrospectively are calibration benchmarks,
    not executable historical strategies. Liquidity classes are provisional.
    """
    selection = matrix[(matrix.institution == institution) & (matrix.economic_condition == allocation)].copy()
    if selection.empty:
        raise ValueError(f"Unknown portfolio: {institution} / {allocation}")
    ids = selection.asset_id.tolist()
    missing = set(ids) - set(monthly_assets.columns)
    if missing:
        raise ValueError("Missing required asset returns: " + ", ".join(sorted(missing)))
    dates = pd.to_datetime(monthly_assets["Date"], errors="raise")
    periods = pd.PeriodIndex(dates, freq="M")
    if periods.has_duplicates:
        raise ValueError("Asset history must contain one observation per month.")
    sample = monthly_assets[ids].apply(pd.to_numeric, errors="raise").copy()
    sample.index = periods
    sample = sample.sort_index().loc["2007-01":]
    if sample.empty or not np.isfinite(sample.to_numpy()).all() or (sample <= -1).any().any():
        raise ValueError("Monthly returns must be finite decimal returns above -100% from January 2007 onward.")
    if sample.index[0] != pd.Period("2007-01", freq="M") or not np.all(np.diff(sample.index.asi8) == 1):
        raise ValueError("Monthly returns must be consecutive from January 2007.")
    monthly = pd.Series(sample.to_numpy() @ selection.weight.to_numpy(), index=sample.index)
    quarter = monthly.index.asfreq("Q")
    counts = monthly.groupby(quarter).size()
    # Exclude the trailing partial quarter, never treat two months as a quarter.
    complete = counts[counts == 3].index
    returns = (1 + monthly).groupby(quarter).prod().loc[complete] - 1
    history = pd.DataFrame({"quarter": complete.astype(str), "portfolio_return": returns.to_numpy()})
    history = history.merge(conditions[["quarter", "condition", "cpi_yoy"]], on="quarter", how="left", validate="one_to_one")
    if history.condition.isna().any():
        raise ValueError("Every complete return quarter needs a matching economic label.")
    history = checked_history(history)
    classes = {asset: "High" for asset in ids}
    classes.update(cash_tbill="Very High", private_equity="Very Low", venture_capital="Very Low", hedge_funds="Low")
    weights = selection[["asset_id", "asset_name", "bucket", "weight"]].rename(columns={"asset_id": "asset"})
    weights["liquidity_class"] = weights.asset.map(classes)
    metadata = {"institution": institution, "allocation": allocation,
                "monthly_source": "asset_monthly_returns.csv", "weight_source": "six_portfolio_weights.csv",
                "calibration_start": str(complete[0]), "calibration_end": str(complete[-1]),
                "complete_quarters": len(complete), "excluded_partial_quarters": counts[counts != 3].index.astype(str).tolist(),
                "rebalancing": "Fixed target weights, cost-free monthly rebalancing of return benchmark",
                "history_warning": "User-supplied backfilled source; pre-2007 excluded. Native-data equivalence not independently verified.",
                "signal_warning": "Existing quarterly condition labels and transition matrix retained; not R1 monthly actionable signals.",
                "liquidity_warning": "Provisional: public sleeves liquid; PE/VC/HF illiquid. Not verified notice periods or gates.",
                "strategy": "Static candidate allocation, no automatic regime-driven weight switching"}
    return history, weights, metadata
