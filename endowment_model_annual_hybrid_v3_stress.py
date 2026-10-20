"""
Hybrid Annual Endowment Payout-Risk Model
==========================================

Frequency design
----------------
* D1 asset data remain MONTHLY and are used inside the market-simulation layer.
* Twelve monthly market returns are compounded into one ANNUAL portfolio return.
* IPEDS spending, gifts/additions and other endowment changes are applied ANNUALLY.
* Additional D2 budget files calibrate tuition dependence, tuition/net-tuition growth,
  expense growth and endowment-support ratios for the institutional budget module.
* NACUBO annual endowment histories are used as ANNUAL peer validation benchmarks.

Default horizon: 10 years. Amounts are USD millions unless stated.
"""

from dataclasses import dataclass, replace
from pathlib import Path
import numpy as np
import pandas as pd

ASSETS = ["Public Equity", "Fixed Income", "Private Equity", "Real Assets", "Cash"]

D1_ASSET_MAP = {
    "Public Equity": "global_equity",
    "Fixed Income": "investment_grade_corporate_bonds",
    "Private Equity": "private_equity",
    "Real Assets": "listed_real_estate",
    "Cash": "cash_tbill",
}

COHORTS = [
    "Under $50M", "$50M–$100M", "$100M–$250M", "$250M–$500M",
    "$500M–$1B", "$1B–$5B", "Over $5B",
]

NACUBO_SHEET_MAP = {
    "Under $50M": "Under 50M",
    "$50M–$100M": "51M to 100M",
    "$100M–$250M": "101M to 250M",
    "$250M–$500M": "251M to 500M",
    "$500M–$1B": "501M to 1B",
    "$1B–$5B": "1B to 5B",
    "Over $5B": "Above 5 Billion",
}


@dataclass
class Params:
    initial_endowment: float = 100.0
    horizon_years: int = 10

    # Portfolio
    weights: tuple = (0.35, 0.20, 0.25, 0.15, 0.05)

    # Annual endowment-flow assumptions (IPEDS-calibrated when applied)
    spending_rate: float = 0.05
    annual_gift_rate: float = 0.0
    annual_other_endowment_change_rate: float = 0.0

    # Annual institutional budget
    # other_revenue_y1 is the starting operating-revenue base EXCLUDING endowment payout.
    other_revenue_y1: float = 18.0
    opex_y1: float = 24.0

    # D2 budget calibration (defaults are current preliminary benchmarks).
    # Tuition dependence = net tuition / total institutional revenue in the D2 source.
    # Because that denominator is broader than this model's operating-revenue base,
    # treat the split as a provisional calibration / scenario assumption until confirmed.
    tuition_dependence: float = 0.2890
    tuition_revenue_growth: float = 0.0056
    non_tuition_revenue_growth: float = 0.0
    expense_growth: float = 0.0472

    # Endowment support / total-expense benchmark. 25th/median/75th from D2 are
    # approximately 1.67%, 5.19% and 11.85%; support_ratio selects the active scenario.
    support_ratio: float = 0.0519

    # Legacy whole-revenue growth field kept for backward compatibility only.
    # It is not used when the tuition/non-tuition split is active.
    revenue_growth: float = 0.0

    # Annual liquidity assumptions
    liquid_allocation: float = 0.70
    liquidity_buffer_years: float = 0.50   # 6 months = 0.5 years
    other_annual_cash_need: float = 12.0  # old $1m/month assumption annualized
    forced_sale_discount: float = 0.20
    lockup_years: float = 5.0             # old 60 months = 5 years

    @property
    def illiquid_allocation(self) -> float:
        return 1.0 - self.liquid_allocation

    @property
    def peer_cohort(self) -> str:
        return size_cohort(self.initial_endowment)


def size_cohort(endowment_millions: float) -> str:
    x = float(endowment_millions)
    if x < 50:
        return "Under $50M"
    if x < 100:
        return "$50M–$100M"
    if x < 250:
        return "$100M–$250M"
    if x < 500:
        return "$250M–$500M"
    if x < 1000:
        return "$500M–$1B"
    if x < 5000:
        return "$1B–$5B"
    return "Over $5B"


def _coerce_excel_dates(s: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_datetime(s, unit="D", origin="1899-12-30", errors="coerce")
    return pd.to_datetime(s, errors="coerce")


# -----------------------------------------------------------------------------
# D1 market data
# -----------------------------------------------------------------------------
def load_d1_asset_returns(file_path: str) -> pd.DataFrame:
    raw = pd.read_excel(file_path, sheet_name="monthly return")
    needed = ["Date"] + list(D1_ASSET_MAP.values())
    missing = [c for c in needed if c not in raw.columns]
    if missing:
        raise ValueError(f"D1 monthly return sheet is missing columns: {missing}")
    df = raw[needed].copy()
    df["Date"] = _coerce_excel_dates(df["Date"])
    df = df.rename(columns={v: k for k, v in D1_ASSET_MAP.items()})
    return df.dropna(subset=ASSETS).sort_values("Date").reset_index(drop=True)[["Date"] + ASSETS]


def load_d1_inflation(file_path: str) -> pd.DataFrame:
    raw = pd.read_excel(file_path, sheet_name="Economic Data")
    if "Date" not in raw.columns or "CPIAUCSL" not in raw.columns:
        raise ValueError("D1 Economic Data must contain Date and CPIAUCSL.")
    df = raw[["Date", "CPIAUCSL"]].copy()
    df["Date"] = _coerce_excel_dates(df["Date"])
    df = df.dropna().sort_values("Date")
    df["Year"] = df["Date"].dt.year
    # Year-end CPI; annual inflation is year-end to year-end.
    year_end = df.groupby("Year", as_index=False).tail(1).set_index("Year")
    year_end["Inflation"] = year_end["CPIAUCSL"].pct_change(fill_method=None)
    return year_end[["Inflation"]].dropna()


def annual_asset_history(asset_returns: pd.DataFrame) -> pd.DataFrame:
    """Compound monthly D1 asset returns into complete calendar-year asset returns."""
    x = asset_returns.copy()
    x["Year"] = x["Date"].dt.year
    x["Month"] = x["Date"].dt.month
    counts = x.groupby("Year")["Month"].nunique()
    complete_years = counts[counts == 12].index
    x = x[x["Year"].isin(complete_years)]
    annual = x.groupby("Year")[ASSETS].agg(lambda s: float(np.prod(1.0 + s.to_numpy()) - 1.0))
    return annual


def annual_portfolio_history(asset_returns: pd.DataFrame, weights) -> pd.Series:
    """Annual portfolio return from monthly weighted portfolio returns, allowing monthly rebalancing."""
    w = np.asarray(weights, dtype=float)
    if not np.isclose(w.sum(), 1.0):
        raise ValueError("Portfolio weights must sum to 1.0.")
    x = asset_returns.copy()
    x["Year"] = x["Date"].dt.year
    x["Month"] = x["Date"].dt.month
    x["Monthly Portfolio Return"] = x[ASSETS].to_numpy(dtype=float) @ w
    counts = x.groupby("Year")["Month"].nunique()
    complete_years = counts[counts == 12].index
    x = x[x["Year"].isin(complete_years)]
    return x.groupby("Year")["Monthly Portfolio Return"].agg(
        lambda s: float(np.prod(1.0 + s.to_numpy()) - 1.0)
    )


def latest_complete_annual_scenario(asset_returns: pd.DataFrame, weights, years: int = 10) -> pd.DataFrame:
    """Latest complete calendar years from D1, used as a transparent deterministic annual scenario."""
    annual_assets = annual_asset_history(asset_returns)
    portfolio = annual_portfolio_history(asset_returns, weights)
    out = annual_assets.join(portfolio.rename("Portfolio Return"), how="inner").tail(years).copy()
    out.index.name = "Scenario Year"
    return out


def simulate_annual_returns_from_monthly_bootstrap(
    asset_returns: pd.DataFrame,
    weights,
    years: int = 10,
    seed=None,
    block_size: int = 3,
) -> pd.DataFrame:
    """
    Hybrid simulation: bootstrap D1 monthly return blocks, but report annual results.

    This preserves observed non-normal monthly returns, cross-asset dependence, and
    short-run clustering, while the institutional model itself remains annual.
    """
    hist = asset_returns[ASSETS].dropna().reset_index(drop=True)
    if block_size < 1 or len(hist) < block_size:
        raise ValueError("Invalid bootstrap block size.")
    w = np.asarray(weights, dtype=float)
    rng = np.random.default_rng(seed)
    months_needed = years * 12
    pieces = []
    while sum(len(p) for p in pieces) < months_needed:
        start = int(rng.integers(0, len(hist) - block_size + 1))
        pieces.append(hist.iloc[start:start + block_size].to_numpy(dtype=float))
    monthly = np.vstack(pieces)[:months_needed]

    rows = []
    for y in range(years):
        block = monthly[y * 12:(y + 1) * 12]
        asset_ann = np.prod(1.0 + block, axis=0) - 1.0
        monthly_port = block @ w
        port_ann = float(np.prod(1.0 + monthly_port) - 1.0)
        row = {asset: float(asset_ann[i]) for i, asset in enumerate(ASSETS)}
        row["Portfolio Return"] = port_ann
        rows.append(row)
    return pd.DataFrame(rows, index=pd.RangeIndex(1, years + 1, name="Year"))


# -----------------------------------------------------------------------------
# D2 IPEDS calibration
# -----------------------------------------------------------------------------
def load_ipeds_calibration(file_path: str) -> pd.DataFrame:
    pieces = []
    for year in range(2020, 2025):
        df = pd.read_excel(file_path, sheet_name=f"FISCAL YEAR {year}")
        b = "Value of endowment assets at the beginning of the fiscal year ($)"
        e = "Value of endowment assets at the end of the fiscal year ($)"
        g = "New gifts and additions ($)"
        inv = "Endowment net investment return ($)"
        s = "Endowment Spending ($)"
        o = "Other changes in value of endowment net assets ($)"
        x = df[["Institution Name", "Size Cohort", b, e, g, inv, s, o]].copy()
        begin = pd.to_numeric(x[b], errors="coerce")
        x = x[begin > 0].copy()
        begin = pd.to_numeric(x[b], errors="coerce")
        x["Spending Rate"] = pd.to_numeric(x[s], errors="coerce") / begin
        x["Gift Rate"] = pd.to_numeric(x[g], errors="coerce") / begin
        x["Investment Return Rate"] = pd.to_numeric(x[inv], errors="coerce") / begin
        x["Other Change Rate"] = pd.to_numeric(x[o], errors="coerce") / begin
        x["Net Endowment Growth"] = (pd.to_numeric(x[e], errors="coerce") - begin) / begin
        pieces.append(x)
    panel = pd.concat(pieces, ignore_index=True)
    return panel.groupby("Size Cohort").agg(
        Observations=("Institution Name", "count"),
        Median_Spending_Rate=("Spending Rate", "median"),
        Median_Gift_Rate=("Gift Rate", "median"),
        Median_Investment_Return_Rate=("Investment Return Rate", "median"),
        Median_Other_Change_Rate=("Other Change Rate", "median"),
        Median_Net_Endowment_Growth=("Net Endowment Growth", "median"),
    ).reindex(COHORTS)


def apply_ipeds_calibration(p: Params, ipeds_summary: pd.DataFrame) -> Params:
    row = ipeds_summary.loc[p.peer_cohort]
    return replace(
        p,
        spending_rate=float(row["Median_Spending_Rate"]),
        annual_gift_rate=float(row["Median_Gift_Rate"]),
        annual_other_endowment_change_rate=float(row["Median_Other_Change_Rate"]),
    )


# -----------------------------------------------------------------------------
# D2 institutional-budget calibration
# -----------------------------------------------------------------------------
def _read_fy_series(file_path, sheets, value_col):
    """Read UnitID-level annual values from a list of fiscal-year sheets."""
    pieces = []
    for label, sheet in sheets:
        df = pd.read_excel(file_path, sheet_name=sheet)
        needed = ["UnitID", value_col]
        missing = [c for c in needed if c not in df.columns]
        if missing:
            raise ValueError(f"{sheet} is missing columns: {missing}")
        x = df[needed].copy()
        x["UnitID"] = x["UnitID"].astype(str)
        x[value_col] = pd.to_numeric(x[value_col], errors="coerce")
        x["FY"] = label
        pieces.append(x.dropna(subset=[value_col]))
    return pd.concat(pieces, ignore_index=True)


def _median_growth_from_panel(panel, value_col, order):
    """Median institution-year growth across consecutive fiscal-year observations."""
    wide = panel.pivot_table(index="UnitID", columns="FY", values=value_col, aggfunc="first")
    growths = []
    for a, b in zip(order[:-1], order[1:]):
        if a not in wide.columns or b not in wide.columns:
            continue
        base = pd.to_numeric(wide[a], errors="coerce")
        nxt = pd.to_numeric(wide[b], errors="coerce")
        g = nxt / base - 1.0
        g = g.replace([np.inf, -np.inf], np.nan).dropna()
        # Remove impossible / obvious data-error jumps without trimming ordinary stress.
        g = g[(g > -0.95) & (g < 5.0)]
        growths.extend(g.tolist())
    return float(np.median(growths)) if growths else np.nan


def load_d2_budget_calibration(
    tuition_dependence_file=None,
    net_tuition_file=None,
    tuition_file=None,
    total_expenses_file=None,
    spending_distribution_file=None,
):
    """
    Calculate D2 institutional-budget calibration statistics.

    Returns a Series containing:
      * latest-year median tuition dependence;
      * median net-tuition revenue growth across FY2019-20..FY2023-24;
      * median undergraduate tuition-price growth (context / scenario benchmark);
      * median total-expense growth;
      * 25th/median/75th endowment-support-to-expense ratios.

    Any missing source file simply leaves the corresponding statistic as NaN.
    """
    out = {
        "Median tuition dependence": np.nan,
        "Median net tuition revenue growth": np.nan,
        "Median undergraduate tuition price growth": np.nan,
        "Median total expense growth": np.nan,
        "25th percentile endowment support / total expenses": np.nan,
        "Median endowment support / total expenses": np.nan,
        "75th percentile endowment support / total expenses": np.nan,
    }

    if tuition_dependence_file is not None:
        td = pd.read_excel(tuition_dependence_file, sheet_name="FY2023-24")
        col = "Tuition Dependence (%)"
        if col not in td.columns:
            raise ValueError("Tuition-dependence file is missing 'Tuition Dependence (%)'.")
        vals = pd.to_numeric(td[col], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        out["Median tuition dependence"] = float(vals.median())

    fy_order = ["FY2019-20", "FY2020-21", "FY2021-22", "FY2022-23", "FY2023-24"]

    if net_tuition_file is not None:
        panel = _read_fy_series(
            net_tuition_file,
            [(x, x) for x in fy_order],
            "Net Tuition and Fee Revenue",
        )
        out["Median net tuition revenue growth"] = _median_growth_from_panel(
            panel, "Net Tuition and Fee Revenue", fy_order
        )

    if total_expenses_file is not None:
        panel = _read_fy_series(
            total_expenses_file,
            [(x, x) for x in fy_order],
            "Total Expenses",
        )
        out["Median total expense growth"] = _median_growth_from_panel(
            panel, "Total Expenses", fy_order
        )

    if tuition_file is not None:
        tuition_order = ["FY 2020", "FY 2021", "FY 2022", "FY 2023", "FY 2024"]
        value_cols = [
            "In-state average tuition for full-time undergraduates",
            "Out-of-state average tuition for full-time undergraduates",
        ]
        growth_estimates = []
        for value_col in value_cols:
            panel = _read_fy_series(
                tuition_file,
                [(x, x) for x in tuition_order],
                value_col,
            )
            g = _median_growth_from_panel(panel, value_col, tuition_order)
            if np.isfinite(g):
                growth_estimates.append(g)
        if growth_estimates:
            out["Median undergraduate tuition price growth"] = float(np.median(growth_estimates))

    if spending_distribution_file is not None and total_expenses_file is not None:
        sp = pd.read_excel(spending_distribution_file, sheet_name="FY2023-24")
        ex = pd.read_excel(total_expenses_file, sheet_name="FY2023-24")
        sp_col = "Spending Distribution for Current Use"
        ex_col = "Total Expenses"
        if sp_col not in sp.columns or ex_col not in ex.columns:
            raise ValueError("Spending/expense files do not contain the expected FY2023-24 columns.")
        m = sp[["UnitID", sp_col]].merge(ex[["UnitID", ex_col]], on="UnitID", how="inner")
        m[sp_col] = pd.to_numeric(m[sp_col], errors="coerce")
        m[ex_col] = pd.to_numeric(m[ex_col], errors="coerce")
        ratio = (m[sp_col].abs() / m[ex_col]).replace([np.inf, -np.inf], np.nan).dropna()
        ratio = ratio[(ratio >= 0) & (ratio < 1)]
        if len(ratio):
            out["25th percentile endowment support / total expenses"] = float(ratio.quantile(0.25))
            out["Median endowment support / total expenses"] = float(ratio.median())
            out["75th percentile endowment support / total expenses"] = float(ratio.quantile(0.75))

    return pd.Series(out)


def apply_d2_budget_calibration(
    p: Params,
    calibration: pd.Series,
    use_net_tuition_growth: bool = True,
    support_scenario: str = "Median",
    non_tuition_growth: float = None,
) -> Params:
    """Apply available D2 budget benchmarks to Params while preserving missing defaults."""
    kwargs = {}
    if np.isfinite(calibration.get("Median tuition dependence", np.nan)):
        kwargs["tuition_dependence"] = float(calibration["Median tuition dependence"])

    growth_key = (
        "Median net tuition revenue growth"
        if use_net_tuition_growth
        else "Median undergraduate tuition price growth"
    )
    if np.isfinite(calibration.get(growth_key, np.nan)):
        kwargs["tuition_revenue_growth"] = float(calibration[growth_key])

    if np.isfinite(calibration.get("Median total expense growth", np.nan)):
        kwargs["expense_growth"] = float(calibration["Median total expense growth"])

    scenario_map = {
        "Low (25th percentile)": "25th percentile endowment support / total expenses",
        "Median": "Median endowment support / total expenses",
        "High (75th percentile)": "75th percentile endowment support / total expenses",
    }
    key = scenario_map.get(support_scenario, scenario_map["Median"])
    if np.isfinite(calibration.get(key, np.nan)):
        kwargs["support_ratio"] = float(calibration[key])

    if non_tuition_growth is not None:
        kwargs["non_tuition_revenue_growth"] = float(non_tuition_growth)

    return replace(p, **kwargs)


# -----------------------------------------------------------------------------
# D2 NACUBO validation
# -----------------------------------------------------------------------------
def _nacubo_institution_metrics(row: pd.Series, years):
    vals = []
    for y in years:
        key = str(y) if str(y) in row.index else (y if y in row.index else None)
        if key is None:
            continue
        v = pd.to_numeric(row[key], errors="coerce")
        if pd.notna(v) and v > 0:
            vals.append((int(y), float(v)))
    if len(vals) < 2:
        return None
    vals.sort()

    growths = []
    for (y0, v0), (y1, v1) in zip(vals[:-1], vals[1:]):
        if y1 == y0 + 1 and v0 > 0:
            g = v1 / v0 - 1
            if -0.95 < g < 5.0:
                growths.append(g)

    peak_val, peak_year = vals[0][1], vals[0][0]
    max_dd, dd_peak_year, trough_year = 0.0, None, None
    for y, v in vals:
        if v > peak_val:
            peak_val, peak_year = v, y
        dd = v / peak_val - 1
        if dd < max_dd:
            max_dd, dd_peak_year, trough_year = dd, peak_year, y

    recovery_years = np.nan
    if dd_peak_year is not None:
        peak_for_dd = next(v for y, v in vals if y == dd_peak_year)
        rec = [y for y, v in vals if y > trough_year and v >= peak_for_dd]
        if rec:
            recovery_years = min(rec) - trough_year

    return growths, max_dd, recovery_years


def load_nacubo_validation(file_path: str) -> pd.DataFrame:
    rows = []
    for cohort in COHORTS:
        df = pd.read_excel(file_path, sheet_name=NACUBO_SHEET_MAP[cohort])
        years = [y for y in range(1974, 2026) if str(y) in map(str, df.columns)]
        growths, dds, recs, n = [], [], [], 0
        for _, row in df.iterrows():
            m = _nacubo_institution_metrics(row, years)
            if m is None:
                continue
            g, dd, rec = m
            growths.extend(g)
            dds.append(dd)
            if np.isfinite(rec):
                recs.append(rec)
            n += 1
        growths = np.asarray(growths, dtype=float)
        rows.append({
            "Size Cohort": cohort,
            "Institutions": n,
            "Annual Growth Observations": len(growths),
            "Median Annual Growth": float(np.median(growths)),
            "10th Percentile Annual Growth": float(np.quantile(growths, 0.10)),
            "Negative Growth Frequency": float(np.mean(growths < 0)),
            "Median Maximum Drawdown": float(np.median(dds)),
            "Median Recovery Years": float(np.median(recs)) if recs else np.nan,
        })
    return pd.DataFrame(rows).set_index("Size Cohort")


# -----------------------------------------------------------------------------
# Annual institutional/endowment engine
# -----------------------------------------------------------------------------
def run_annual_model(
    p: Params,
    annual_returns: pd.DataFrame,
    annual_inflation=None,
    payout_override=None,
    annual_overrides: pd.DataFrame = None,
) -> pd.DataFrame:
    """Run annual portfolio, payout, institutional budget, liquidity and risk modules."""
    if "Portfolio Return" not in annual_returns.columns:
        raise ValueError("annual_returns must contain 'Portfolio Return'.")
    years = len(annual_returns)
    if annual_inflation is None:
        inflation = pd.Series(0.0, index=annual_returns.index)
    elif isinstance(annual_inflation, pd.Series):
        inflation = annual_inflation.reindex(annual_returns.index).fillna(0.0)
    else:
        inflation = pd.Series(list(annual_inflation), index=annual_returns.index).fillna(0.0)

    begin = p.initial_endowment
    # Provisional D2 split: apply tuition dependence to the model's starting
    # operating-revenue base. This remains a scenario assumption until the
    # tuition-dependence denominator is confirmed to match the model definition.
    tuition_revenue = p.other_revenue_y1 * p.tuition_dependence
    non_tuition_revenue = p.other_revenue_y1 - tuition_revenue
    opex = p.opex_y1
    nominal_peak = begin
    real_peak = begin
    cumulative_inflation = 1.0
    rows = []

    for i, idx in enumerate(annual_returns.index, start=1):
        # Scenario-specific annual overrides. Missing values fall back to Params.
        ov = {}
        if annual_overrides is not None and idx in annual_overrides.index:
            ov = annual_overrides.loc[idx].dropna().to_dict()

        port_ret = float(annual_returns.loc[idx, "Portfolio Return"])
        investment_gain = begin * port_ret
        pre_payout = begin + investment_gain

        planned = begin * p.spending_rate
        actual = planned
        if payout_override is not None and idx in payout_override.index and pd.notna(payout_override.loc[idx]):
            actual = float(payout_override.loc[idx])

        gifts = begin * p.annual_gift_rate
        other_changes = begin * p.annual_other_endowment_change_rate

        liquid_allocation = float(ov.get("Liquid Allocation", p.liquid_allocation))
        liquidity_buffer_years = float(ov.get("Liquidity Buffer Years", p.liquidity_buffer_years))
        other_annual_cash_need = float(ov.get("Other Annual Cash Need", p.other_annual_cash_need))
        forced_sale_discount = float(ov.get("Forced Sale Discount", p.forced_sale_discount))

        liquid = begin * liquid_allocation
        illiquid = begin * (1.0 - liquid_allocation)
        required_liquidity = actual * liquidity_buffer_years + other_annual_cash_need
        liquidity_shortfall = max(0.0, required_liquidity - liquid)
        forced_sale = (
            liquidity_shortfall / (1.0 - forced_sale_discount)
            if liquidity_shortfall > 0 and forced_sale_discount < 1.0 else 0.0
        )
        forced_sale_loss = forced_sale * forced_sale_discount

        ending = pre_payout + gifts + other_changes - actual - forced_sale_loss

        operating_revenue = tuition_revenue + non_tuition_revenue
        total_revenue = operating_revenue + actual
        budget_balance = total_revenue - opex

        support_ratio = float(ov.get("Support Ratio", p.support_ratio))
        benchmark_support_need = opex * support_ratio
        payout_support_gap = max(0.0, benchmark_support_need - actual)
        payout_adequacy_ratio = (
            actual / benchmark_support_need
            if benchmark_support_need > 0 else np.nan
        )

        nominal_peak = max(nominal_peak, ending)
        nominal_drawdown = ending / nominal_peak - 1.0

        inflation_rate = float(inflation.loc[idx])
        cumulative_inflation *= 1.0 + inflation_rate
        real_ending = ending / cumulative_inflation
        real_peak = max(real_peak, real_ending)
        real_drawdown = real_ending / real_peak - 1.0

        rows.append({
            "Year": i,
            "Scenario Year": idx,
            "Beginning Assets": begin,
            "Portfolio Return": port_ret,
            "Investment Gain": investment_gain,
            "Pre-Payout Assets": pre_payout,
            "Planned Payout": planned,
            "Actual Payout": actual,
            "Endowment Gifts/Additions": gifts,
            "Other Endowment Changes": other_changes,
            "Forced-Sale Loss": forced_sale_loss,
            "Ending Assets": ending,
            "Tuition Revenue": tuition_revenue,
            "Non-Tuition Revenue": non_tuition_revenue,
            "Other Operating Revenue": operating_revenue,
            "Total Operating Revenue incl. Payout": total_revenue,
            "Operating Expenses": opex,
            "Budget Surplus/(Deficit)": budget_balance,
            "D2 Benchmark Endowment Support Need": benchmark_support_need,
            "Payout Support Gap": payout_support_gap,
            "Payout Adequacy Ratio": payout_adequacy_ratio,
            "Support Ratio": support_ratio,
            "Liquid Allocation": liquid_allocation,
            "Forced Sale Discount": forced_sale_discount,
            "Liquid Assets": liquid,
            "Illiquid Assets": illiquid,
            "Required Liquidity": required_liquidity,
            "Liquidity Shortfall": liquidity_shortfall,
            "Forced Sale": forced_sale,
            "Shortfall Flag": int(liquidity_shortfall > 0),
            "Nominal Running Peak": nominal_peak,
            "Nominal Drawdown": nominal_drawdown,
            "Inflation": inflation_rate,
            "Real Ending Assets": real_ending,
            "Real Running Peak": real_peak,
            "Real Drawdown": real_drawdown,
        })

        begin = ending
        tuition_growth = float(ov.get("Tuition Revenue Growth", p.tuition_revenue_growth))
        non_tuition_growth = float(ov.get("Non-Tuition Revenue Growth", p.non_tuition_revenue_growth))
        expense_growth = float(ov.get("Expense Growth", p.expense_growth))
        tuition_revenue *= 1.0 + tuition_growth
        non_tuition_revenue *= 1.0 + non_tuition_growth
        opex *= 1.0 + expense_growth

    return pd.DataFrame(rows).set_index("Year")



# -----------------------------------------------------------------------------
# Structured stress scenarios
# -----------------------------------------------------------------------------
def build_stress_scenario(
    p: Params,
    base_returns: pd.DataFrame,
    base_inflation: pd.Series,
    scenario: str,
    *,
    high_inflation_peak: float = 0.06,
    high_inflation_years: int = 3,
    high_inflation_return_shock: float = -0.02,
    high_inflation_extra_expense_growth: float = 0.02,
    downturn_initial_return: float = -0.20,
    downturn_second_return: float = -0.10,
    downturn_recovery_return: float = 0.05,
    downturn_stress_years: int = 3,
    stressed_liquid_allocation: float = 0.35,
    stressed_forced_sale_discount: float = 0.30,
    stressed_cash_need_multiplier: float = 1.50,
):
    """
    Create a structured annual stress path.

    Defaults are illustrative starting points, not final calibrated assumptions.
    They should be replaced when Research 1 / Research 2 / Data-team evidence is confirmed.
    """
    returns = base_returns.copy()
    inflation = pd.Series(base_inflation, index=base_returns.index, dtype=float).copy()
    overrides = pd.DataFrame(index=base_returns.index)

    if scenario == "Base":
        return returns, inflation, overrides

    if scenario == "High Inflation & Elevated Rates":
        n = min(int(high_inflation_years), len(returns))
        if n > 0:
            inflation.iloc[:n] = np.linspace(high_inflation_peak, 0.03, n)
            returns.loc[returns.index[:n], "Portfolio Return"] = (
                returns.loc[returns.index[:n], "Portfolio Return"] + high_inflation_return_shock
            )
            overrides.loc[overrides.index[:n], "Expense Growth"] = (
                p.expense_growth + high_inflation_extra_expense_growth
            )
        return returns, inflation, overrides

    if scenario == "Prolonged Downturn & Liquidity Squeeze":
        n = min(int(downturn_stress_years), len(returns))
        stress_returns = [downturn_initial_return, downturn_second_return, downturn_recovery_return]
        if n > 0:
            vals = (stress_returns + [downturn_recovery_return] * n)[:n]
            returns.loc[returns.index[:n], "Portfolio Return"] = vals
            overrides.loc[overrides.index[:n], "Liquid Allocation"] = stressed_liquid_allocation
            overrides.loc[overrides.index[:n], "Forced Sale Discount"] = stressed_forced_sale_discount
            overrides.loc[overrides.index[:n], "Other Annual Cash Need"] = (
                p.other_annual_cash_need * stressed_cash_need_multiplier
            )
        return returns, inflation, overrides

    raise ValueError(f"Unknown stress scenario: {scenario}")


def run_structured_stress_test(
    p: Params,
    base_returns: pd.DataFrame,
    base_inflation: pd.Series,
    scenario: str,
    **scenario_kwargs,
) -> pd.DataFrame:
    """Run one structured deterministic stress scenario."""
    stressed_returns, stressed_inflation, overrides = build_stress_scenario(
        p, base_returns, base_inflation, scenario, **scenario_kwargs
    )
    result = run_annual_model(
        p,
        stressed_returns,
        annual_inflation=stressed_inflation,
        annual_overrides=overrides,
    )
    result["Stress Scenario"] = scenario
    return result


def compare_stress_scenarios(
    p: Params,
    base_returns: pd.DataFrame,
    base_inflation: pd.Series,
    scenario_settings: dict = None,
) -> pd.DataFrame:
    """Run Base plus the two proposed structured stresses."""
    scenario_settings = scenario_settings or {}
    rows = []
    for scenario in [
        "Base",
        "High Inflation & Elevated Rates",
        "Prolonged Downturn & Liquidity Squeeze",
    ]:
        result = run_structured_stress_test(
            p, base_returns, base_inflation, scenario, **scenario_settings
        )
        beginning = float(result["Beginning Assets"].iloc[0])
        ending = float(result["Ending Assets"].iloc[-1])
        years = len(result)
        rows.append({
            "Scenario": scenario,
            "Ending Endowment ($M)": ending,
            "Ending Real Endowment ($M)": float(result["Real Ending Assets"].iloc[-1]),
            "Nominal CAGR": (ending / beginning) ** (1.0 / years) - 1.0,
            "Maximum Nominal Drawdown": float(result["Nominal Drawdown"].min()),
            "Maximum Real Drawdown": float(result["Real Drawdown"].min()),
            "Total Payout ($M)": float(result["Actual Payout"].sum()),
            "Years with Budget Deficit": int((result["Budget Surplus/(Deficit)"] < 0).sum()),
            "Years with Payout Support Gap": int((result["Payout Support Gap"] > 0).sum()),
            "Maximum Payout Support Gap ($M)": float(result["Payout Support Gap"].max()),
            "Years with Liquidity Shortfall": int((result["Liquidity Shortfall"] > 0).sum()),
            "Maximum Liquidity Shortfall ($M)": float(result["Liquidity Shortfall"].max()),
            "Total Forced-Sale Loss ($M)": float(result["Forced-Sale Loss"].sum()),
        })
    return pd.DataFrame(rows).set_index("Scenario")

def summarize_annual(df: pd.DataFrame, p: Params,
                     ipeds_summary=None, nacubo_summary=None) -> pd.Series:
    beginning = float(df["Beginning Assets"].iloc[0])
    ending = float(df["Ending Assets"].iloc[-1])
    years = len(df)
    out = {
        "Projection horizon (years)": years,
        "Peer cohort": p.peer_cohort,
        "Beginning endowment ($mm)": beginning,
        "Ending endowment ($mm)": ending,
        "Nominal endowment CAGR": (ending / beginning) ** (1.0 / years) - 1.0,
        "Ending real endowment ($mm, base-year dollars)": df["Real Ending Assets"].iloc[-1],
        "Maximum nominal drawdown": df["Nominal Drawdown"].min(),
        "Maximum real drawdown": df["Real Drawdown"].min(),
        "Total payout ($mm)": df["Actual Payout"].sum(),
        "Total gifts/additions ($mm)": df["Endowment Gifts/Additions"].sum(),
        "Total forced-sale loss ($mm)": df["Forced-Sale Loss"].sum(),
        "Years with budget deficit": int((df["Budget Surplus/(Deficit)"] < 0).sum()),
        "Years with payout support gap": int((df["Payout Support Gap"] > 0).sum()),
        "Maximum payout support gap ($mm)": df["Payout Support Gap"].max(),
        "Minimum payout adequacy ratio": df["Payout Adequacy Ratio"].min(),
        "D2 endowment-support scenario ratio": p.support_ratio,
        "Tuition dependence assumption": p.tuition_dependence,
        "Tuition revenue growth assumption": p.tuition_revenue_growth,
        "Non-tuition revenue growth assumption": p.non_tuition_revenue_growth,
        "Expense growth assumption": p.expense_growth,
        "Liquidity-shortfall frequency": df["Shortfall Flag"].mean(),
        "Maximum liquidity shortfall ($mm)": df["Liquidity Shortfall"].max(),
        "Payout volatility ($mm)": df["Actual Payout"].std(ddof=1) if years > 1 else 0.0,
    }
    if ipeds_summary is not None and p.peer_cohort in ipeds_summary.index:
        r = ipeds_summary.loc[p.peer_cohort]
        out["IPEDS median spending rate"] = r["Median_Spending_Rate"]
        out["IPEDS median net endowment growth"] = r["Median_Net_Endowment_Growth"]
    if nacubo_summary is not None and p.peer_cohort in nacubo_summary.index:
        r = nacubo_summary.loc[p.peer_cohort]
        out["NACUBO median annual growth"] = r["Median Annual Growth"]
        out["NACUBO 10th percentile annual growth"] = r["10th Percentile Annual Growth"]
        out["NACUBO negative-growth frequency"] = r["Negative Growth Frequency"]
        out["NACUBO median maximum drawdown"] = r["Median Maximum Drawdown"]
        out["NACUBO median recovery years"] = r["Median Recovery Years"]
    return pd.Series(out)


def monte_carlo_annual(
    p: Params,
    historical_returns: pd.DataFrame,
    n_sims: int = 2000,
    seed: int = 42,
    block_size: int = 3,
    inflation_history: pd.DataFrame = None,
    nacubo_summary: pd.DataFrame = None,
) -> pd.Series:
    """Monte Carlo with monthly D1 bootstrap internally and annual institutional updates."""
    rng = np.random.default_rng(seed)
    inflation_values = None
    if inflation_history is not None and "Inflation" in inflation_history.columns:
        inflation_values = inflation_history["Inflation"].dropna().to_numpy(dtype=float)

    peer_dd = np.nan
    if nacubo_summary is not None and p.peer_cohort in nacubo_summary.index:
        peer_dd = float(nacubo_summary.loc[p.peer_cohort, "Median Maximum Drawdown"])

    records = []
    for _ in range(n_sims):
        sim_seed = int(rng.integers(1 << 31))
        annual_ret = simulate_annual_returns_from_monthly_bootstrap(
            historical_returns, p.weights, years=p.horizon_years,
            seed=sim_seed, block_size=block_size,
        )
        if inflation_values is not None and len(inflation_values):
            sim_infl = pd.Series(
                rng.choice(inflation_values, size=p.horizon_years, replace=True),
                index=annual_ret.index,
            )
        else:
            sim_infl = None
        df = run_annual_model(p, annual_ret, annual_inflation=sim_infl)
        records.append({
            "Ending Assets": df["Ending Assets"].iloc[-1],
            "Ending Real Assets": df["Real Ending Assets"].iloc[-1],
            "Total Payout": df["Actual Payout"].sum(),
            "Any Budget Deficit": int((df["Budget Surplus/(Deficit)"] < 0).any()),
            "Any Payout Support Gap": int((df["Payout Support Gap"] > 0).any()),
            "Minimum Payout Adequacy Ratio": df["Payout Adequacy Ratio"].min(),
            "Maximum Payout Support Gap": df["Payout Support Gap"].max(),
            "Any Liquidity Shortfall": int(df["Shortfall Flag"].sum() > 0),
            "Max Nominal Drawdown": df["Nominal Drawdown"].min(),
            "Max Real Drawdown": df["Real Drawdown"].min(),
            "Forced-Sale Loss": df["Forced-Sale Loss"].sum(),
        })

    a = pd.DataFrame(records)
    out = {
        "Simulations": n_sims,
        "Projection horizon (years)": p.horizon_years,
        "Mean ending endowment ($mm)": a["Ending Assets"].mean(),
        "5th percentile ending endowment ($mm)": a["Ending Assets"].quantile(0.05),
        "P(ending nominal endowment below initial)": (a["Ending Assets"] < p.initial_endowment).mean(),
        "P(ending real endowment below initial)": (a["Ending Real Assets"] < p.initial_endowment).mean(),
        "Mean total payout ($mm)": a["Total Payout"].mean(),
        "P(budget deficit in any year)": a["Any Budget Deficit"].mean(),
        "P(payout support gap in any year)": a["Any Payout Support Gap"].mean(),
        "Mean minimum payout adequacy ratio": a["Minimum Payout Adequacy Ratio"].mean(),
        "95th percentile maximum payout support gap ($mm)": a["Maximum Payout Support Gap"].quantile(0.95),
        "P(liquidity shortfall in any year)": a["Any Liquidity Shortfall"].mean(),
        "Mean maximum nominal drawdown": a["Max Nominal Drawdown"].mean(),
        "5th percentile maximum nominal drawdown": a["Max Nominal Drawdown"].quantile(0.05),
        "Mean maximum real drawdown": a["Max Real Drawdown"].mean(),
        "Mean forced-sale loss ($mm)": a["Forced-Sale Loss"].mean(),
    }
    if np.isfinite(peer_dd):
        out["NACUBO peer median maximum drawdown"] = peer_dd
        out["P(drawdown worse than NACUBO peer median)"] = (a["Max Nominal Drawdown"] < peer_dd).mean()
    return pd.Series(out)


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 40)
    pd.set_option("display.float_format", "{:,.4f}".format)

    d1_path = Path("D1_AssetEconomicData_092126_v1.xlsx")
    ipeds_path = Path("D2_IPEDSData_092226_v0.xlsx")
    nacubo_path = Path("D2_NACUBOHistoricalData19742025_092226.xlsx")

    p = Params()
    ipeds = load_ipeds_calibration(str(ipeds_path)) if ipeds_path.exists() else None
    if ipeds is not None:
        p = apply_ipeds_calibration(p, ipeds)
    nacubo = load_nacubo_validation(str(nacubo_path)) if nacubo_path.exists() else None

    if not d1_path.exists():
        raise FileNotFoundError("D1 workbook is required for the hybrid annual market engine.")

    monthly_returns = load_d1_asset_returns(str(d1_path))
    inflation_hist = load_d1_inflation(str(d1_path))

    deterministic = latest_complete_annual_scenario(monthly_returns, p.weights, years=p.horizon_years)
    det_infl = inflation_hist["Inflation"].reindex(deterministic.index).fillna(0.0)
    result = run_annual_model(p, deterministic, det_infl)

    print("=== Hybrid annual deterministic scenario ===")
    print(deterministic.to_string())
    print("\n=== Annual model summary ===")
    print(summarize_annual(result, p, ipeds, nacubo).to_string())

    print("\n=== Hybrid annual Monte Carlo ===")
    print(monte_carlo_annual(
        p,
        historical_returns=monthly_returns,
        n_sims=2000,
        seed=42,
        block_size=3,
        inflation_history=inflation_hist,
        nacubo_summary=nacubo,
    ).to_string())

    result.to_csv("annual_endowment_model_results.csv")
