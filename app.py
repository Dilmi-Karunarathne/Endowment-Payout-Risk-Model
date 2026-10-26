from __future__ import annotations

from dataclasses import replace
from io import BytesIO

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from portfolio_return_simulation import compare_return_methods

from endowment_simulation_model import (
    SimulationConfig,
    historical_validation,
    institutional_params_from_data,
    liquidity_params_from_data,
    load_default_data,
    load_excel_overrides,
    percentile_path,
    run_monte_carlo,
    stress_configs,
    summarize_path,
)


st.set_page_config(page_title="Endowment Payout-Risk Simulation", page_icon="📊", layout="wide")


@st.cache_data
def load_data_cached():
    return load_default_data()


def pct(x):
    return f"{x:.2%}" if pd.notna(x) else "—"


def mm(x):
    return f"${x:,.2f}M" if pd.notna(x) else "—"


def risk_metric_card(label, value, help_text=None):
    st.metric(label, value, help=help_text)


def simulation_controls(data, cfg_default, inst_default, liq_default):
    st.sidebar.header("Simulation settings")
    institution_type = st.sidebar.selectbox("Institution type", ["Private", "Public"], index=0)
    scenario = st.sidebar.selectbox("R2 institutional scenario", ["Low", "Base", "High"], index=1)

    initial = st.sidebar.number_input("Initial endowment ($mm)", min_value=1.0, value=float(cfg_default.initial_endowment), step=5.0)
    prior2 = st.sidebar.number_input("Endowment two years before start ($mm)", min_value=1.0, value=float(cfg_default.prior_endowment_2y), step=5.0)
    prior1 = st.sidebar.number_input("Endowment one year before start ($mm)", min_value=1.0, value=float(cfg_default.prior_endowment_1y), step=5.0)
    start_year = st.sidebar.number_input("Projection start year", min_value=2023, max_value=2100, value=2027, step=1)
    horizon = st.sidebar.slider("Projection horizon (years)", 5, 20, 10)
    n_sims = st.sidebar.slider("Monte Carlo paths", 500, 10000, 3000, step=500)
    seed = st.sidebar.number_input("Random seed", min_value=0, value=42, step=1)
    alpha = st.sidebar.slider("VaR / Expected Shortfall confidence", 0.90, 0.99, 0.95, 0.01)

    return_method = st.sidebar.selectbox(
        "Return-generation method",
        ["Quarterly block bootstrap", "Regime-switching bootstrap", "Two-component Normal mixture"],
        index=1,
        help="Block bootstrap samples contiguous historical P4 quarters. Regime switching simulates Normal/Recession/Elevated Inflation using R1 transition probabilities, then samples historical P4 returns conditional on the simulated state. The Normal mixture fits two components to aggregate P4 returns and independently chooses a component each quarter.",
    )
    include_comparison = st.sidebar.checkbox("Include method comparison", value=False,
        help="Also compare block bootstrap and Normal mixture using common assumptions. Adds simulation time.")
    block_size = st.sidebar.slider("Block size (quarters)", 1, 8, 4, disabled="block" not in return_method.lower())
    starting_regime = st.sidebar.selectbox("Starting economic regime", ["Normal", "Recession", "Elevated inflation"], index=0, disabled="regime" not in return_method.lower())

    st.sidebar.subheader("Future scenario assumptions")
    return_shift = st.sidebar.number_input("Annual mean-return shift (percentage points)", min_value=-20.0, max_value=20.0, value=0.0, step=0.5,
        help="Adds this value / 4 to each quarterly return. Zero retains historical calibration; this is not an annual compound-return target.") / 100.0
    vol_multiplier = st.sidebar.number_input("Volatility multiplier", min_value=0.1, max_value=3.0, value=1.0, step=0.1)
    inflation_mode = st.sidebar.selectbox("Inflation assumption", ["Historical", "Fixed annual rate"])
    fixed_inflation = st.sidebar.number_input("Fixed annual inflation (%)", min_value=-5.0, max_value=30.0, value=2.5, step=0.1, disabled=inflation_mode == "Historical") / 100.0
    st.sidebar.caption("P4 allocation maintained throughout; no asset-level drift or rebalancing trades. Historical inflation with the mixture uses the historical mean CPI YoY.")

    inst = institutional_params_from_data(data, institution_type, scenario)
    st.sidebar.subheader("R2 / D2 assumptions")
    other_changes_rate = st.sidebar.number_input(
        "Other endowment changes (% of beginning assets)",
        value=float(inst.other_changes_rate * 100.0),
        step=0.05,
        format="%.3f",
        help="Private values use the provisional R3-derived D2 benchmark. Public has no finalized benchmark and defaults to 0% unless changed here.",
    ) / 100.0
    inst = replace(inst, other_changes_rate=other_changes_rate)

    st.sidebar.subheader("Liquidity / payout execution")
    liquidity_enabled = st.sidebar.checkbox(
        "Activate liquidity constraints",
        value=False,
        help="Off = validated base mechanics, Actual Payout = Planned Payout. On = scenario assumptions determine payout funding capacity and forced sales.",
    )
    liq = liquidity_params_from_data(data, enabled=liquidity_enabled)
    if liquidity_enabled:
        buffer_years = st.sidebar.number_input("Liquidity buffer (years of planned payout)", min_value=0.0, value=0.0, step=0.1)
        other_cash = st.sidebar.number_input("Other annual cash need ($mm)", min_value=0.0, value=0.0, step=0.5)
        discount = st.sidebar.slider("Forced-sale discount", 0.0, 0.60, 0.20, 0.01)
        liquid_haircut = st.sidebar.slider("Accessible-liquid-share haircut", 0.0, 0.90, 0.0, 0.05)
        forced_sales = st.sidebar.checkbox("Allow forced sales", value=True)
        liq = replace(
            liq,
            enabled=True,
            liquidity_buffer_years=buffer_years,
            other_annual_cash_need=other_cash,
            forced_sale_discount=discount,
            liquid_share_haircut=liquid_haircut,
            allow_forced_sales=forced_sales,
        )

    cfg = SimulationConfig(
        initial_endowment=float(initial),
        prior_endowment_2y=float(prior2),
        prior_endowment_1y=float(prior1),
        horizon_years=int(horizon),
        start_year=int(start_year),
        n_sims=int(n_sims),
        seed=int(seed),
        alpha=float(alpha),
        return_method=return_method,
        block_size_quarters=int(block_size),
        starting_regime=starting_regime,
        annual_return_shift=float(return_shift),
        volatility_multiplier=float(vol_multiplier),
        annual_inflation=float(fixed_inflation) if inflation_mode == "Fixed annual rate" else None,
        stress_state=None,
        stress_quarters=0,
    )
    return cfg, inst, liq, include_comparison


data = load_data_cached()

st.title("Endowment Payout-Risk Simulation Model")
st.caption("R1 P4 investment calibration + R2 institutional benchmarks + Monte Carlo / stress simulation")

with st.expander("Model scope and current limitations", expanded=False):
    st.markdown(
        """
        - **Validated core:** investment return roll-forward, gifts, other endowment changes, 3-year moving-average payout, expenses, required support, inflation/real corpus and drawdowns.
        - **Simulation baseline:** quarterly block bootstrap, R1 regime-switching bootstrap, or a two-component Normal mixture at portfolio level.
        - **Selected payout-risk measures:** payout shortfall frequency, payout shortfall depth, and Expected Shortfall of terminal real-corpus loss.
        - **Liquidity mechanics are scenario assumptions**, not finalized R2/D2 policy benchmarks. They are off by default.
        - P4 is the current interim R1 Medium | Normal portfolio until the seven-cohort portfolio rebuild is delivered.
        """
    )

uploaded = st.sidebar.file_uploader("Optional: upload updated clean Excel model", type=["xlsx"])
base_cfg = SimulationConfig()
base_inst = institutional_params_from_data(data, "Private", "Base")
base_liq = liquidity_params_from_data(data, enabled=False)
custom_history = None
if uploaded is not None:
    try:
        base_cfg, base_inst, base_liq, custom_history = load_excel_overrides(uploaded.getvalue(), data=data)
        st.sidebar.success("Excel calibration loaded. Simulation settings below can still override it.")
    except Exception as exc:
        st.sidebar.error(f"Could not read workbook overrides: {exc}")

cfg, inst, liq, include_comparison = simulation_controls(data, base_cfg, base_inst, base_liq)

st.sidebar.subheader("Stress testing settings")
recession_q = st.sidebar.slider("Recession stress duration (quarters)", 1, 12, 6)
inflation_q = st.sidebar.slider("Elevated-inflation stress duration (quarters)", 1, 16, 8)

with st.container(border=True):
    st.markdown("**Selected settings**")
    portfolio_col, endowment_col, horizon_col = st.columns(3)
    portfolio_col.markdown("**Portfolio / cohort**")
    portfolio_col.write("P4 — interim Medium | Normal")
    endowment_col.markdown("**Starting endowment**")
    endowment_col.write(mm(cfg.initial_endowment))
    horizon_col.markdown("**Projection horizon**")
    horizon_col.write(f"{cfg.horizon_years} years ({cfg.horizon_years * 4} quarters)")

    spending_col, method_col, institution_col = st.columns(3)
    spending_col.markdown("**Spending rule**")
    spending_col.write(f"{inst.effective_spending_rate:.2%} of 3-year average endowment")
    method_col.markdown("**Return method**")
    method_col.write(cfg.return_method)
    institution_col.markdown("**Institutional assumptions**")
    institution_col.write(f"{inst.institution_type} / {inst.scenario}")
    st.caption(f"{cfg.n_sims:,} simulation paths per case · Method comparison: {'included' if include_comparison else 'not included'}")

input_signature = repr((cfg, inst, liq, recession_q, inflation_q, include_comparison,
    custom_history.to_json() if custom_history is not None else None))
result_keys = ["mc_result", "stress_df", "return_comparison"]
if st.session_state.get("completed_signature") != input_signature:
    for key in result_keys:
        st.session_state.pop(key, None)
    if "completed_signature" in st.session_state:
        st.warning("Settings changed—run analysis to update results.")
    else:
        st.info("Choose your settings, then click Run analysis.")

if st.button("Run analysis", type="primary", key="run_analysis"):
    # Publish the results together only after all requested runs succeed.
    for key in result_keys:
        st.session_state.pop(key, None)
    try:
        with st.spinner("Running baseline and stress scenarios..."):
            baseline_cfg = replace(cfg, stress_state=None, stress_quarters=0)
            result = run_monte_carlo(data, baseline_cfg, inst, liq, p4_history=custom_history)
            table = []
            base_for_stress = baseline_cfg
            for label, scfg in stress_configs(base_for_stress, recession_q, inflation_q).items():
                res = result if label == "Baseline" else run_monte_carlo(data, scfg, inst, liq, p4_history=custom_history, keep_paths=True)
                m = res["metrics"]
                table.append(
                    {
                        "Scenario": label,
                        "Median terminal nominal ($mm)": m["median_terminal_nominal_assets"],
                        "Median terminal real ($mm)": m["median_terminal_real_assets"],
                        "Payout shortfall probability": m["annual_shortfall_probability"],
                        "Pr(≥1 payout shortfall)": m["probability_at_least_one_shortfall"],
                        "Average relative shortfall depth": m["average_relative_shortfall_depth"],
                        f"VaR {int(cfg.alpha*100)}% real-corpus loss": m["var_terminal_real_corpus_loss"],
                        f"ES {int(cfg.alpha*100)}% real-corpus loss": m["expected_shortfall_terminal_real_corpus_loss"],
                        "Pr(any support gap)": m["probability_any_support_gap"],
                    }
                )
            comparison = compare_return_methods(data, cfg, inst, liq, p4_history=custom_history) if include_comparison else None
        st.session_state["mc_result"] = result
        st.session_state["stress_df"] = pd.DataFrame(table)
        if comparison is not None:
            st.session_state["return_comparison"] = comparison
        st.session_state["completed_signature"] = input_signature
        st.success("Analysis complete. All results below use the selected settings.")
    except Exception as exc:
        st.error(f"Analysis could not complete: {exc}")

mc_tab, stress_tab, comparison_tab, assumptions_tab, validation_tab = st.tabs([
    "Payout-risk results",
    "Stress testing",
    "Method comparison",
    "Assumptions & data",
    "Historical validation",
])

with validation_tab:
    st.subheader("2013–2022 historical mechanics backtest")
    st.caption("Uses actual historical P4 annual returns and D1/R1 historical inflation. This is a mechanics backtest, not out-of-sample predictive validation.")

    hist_cfg = replace(
        cfg,
        start_year=2013,
        horizon_years=10,
        n_sims=1,
        stress_state=None,
        stress_quarters=0,
    )
    hist_liq = replace(liq, enabled=False)
    hist = historical_validation(data, hist_cfg, inst, hist_liq)
    hs = summarize_path(hist, hist_cfg.initial_endowment)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ending endowment", mm(hs["ending_assets"]))
    c2.metric("Terminal real corpus", mm(hs["terminal_real_assets"]))
    c3.metric("Total payout", mm(hs["total_payout"]))
    c4.metric("Max real drawdown", pct(hs["max_real_drawdown"]))

    chart_df = hist.set_index("year")[["ending_assets", "real_ending_assets"]].rename(
        columns={"ending_assets": "Nominal ending assets", "real_ending_assets": "Real ending assets"}
    )
    st.line_chart(chart_df)

    display_cols = [
        "year", "portfolio_return", "beginning_assets", "investment_gain", "planned_payout", "actual_payout",
        "endowment_gifts", "other_endowment_changes", "ending_assets", "inflation", "real_ending_assets",
        "payout_support_gap", "payout_adequacy_ratio", "nominal_drawdown", "real_drawdown"
    ]
    st.dataframe(hist[display_cols], use_container_width=True, hide_index=True)

    csv = hist.to_csv(index=False).encode("utf-8")
    st.download_button("Download historical validation CSV", csv, "historical_validation.csv", "text/csv")

with mc_tab:
    st.subheader("Payout-risk results")
    if not liq.enabled:
        st.info("Liquidity constraints are OFF, so Actual Payout = Planned Payout. Payout shortfall frequency/depth will therefore be zero; Expected Shortfall and payout-support risk still vary with market/inflation outcomes.")

    result = st.session_state.get("mc_result")
    if result is not None:
        m = result["metrics"]
        row1 = st.columns(4)
        row1[0].metric("Median terminal nominal corpus", mm(m["median_terminal_nominal_assets"]))
        row1[1].metric("Median terminal real corpus", mm(m["median_terminal_real_assets"]))
        row1[2].metric("Annual payout shortfall probability", pct(m["annual_shortfall_probability"]))
        row1[3].metric("Pr(at least one payout shortfall)", pct(m["probability_at_least_one_shortfall"]))

        row2 = st.columns(4)
        row2[0].metric("Avg. relative shortfall depth", pct(m["average_relative_shortfall_depth"]))
        row2[1].metric(f"VaR {int(m['alpha']*100)}% – terminal real loss", pct(m["var_terminal_real_corpus_loss"]))
        row2[2].metric(f"Expected Shortfall {int(m['alpha']*100)}%", pct(m["expected_shortfall_terminal_real_corpus_loss"]))
        row2[3].metric("Pr(any support gap)", pct(m["probability_any_support_gap"]))

        st.markdown("#### Simulated real-endowment path")
        ppath = percentile_path(result["annual_results"], "real_ending_assets", (0.05, 0.50, 0.95)).set_index("year")
        ppath = ppath.rename(columns={"p05": "5th percentile", "p50": "Median", "p95": "95th percentile"})
        st.line_chart(ppath)

        left, right = st.columns(2)
        with left:
            st.markdown("#### Annual payout shortfall probability")
            asp = result["annual_shortfall_probability"].set_index("year")
            st.bar_chart(asp)
        with right:
            st.markdown("#### Terminal real-corpus distribution")
            ps = result["path_summary"]
            fig = px.histogram(ps, x="terminal_real_assets", nbins=40, labels={"terminal_real_assets": "Terminal real corpus ($mm)"})
            fig.update_layout(showlegend=False, margin=dict(l=10, r=10, t=25, b=10))
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Path-level simulation results")
        st.dataframe(result["path_summary"].head(250), use_container_width=True, hide_index=True)
        st.download_button(
            "Download Monte Carlo path summary",
            result["path_summary"].to_csv(index=False).encode("utf-8"),
            "monte_carlo_path_summary.csv",
            "text/csv",
        )
        st.download_button(
            "Download annual simulated results",
            result["annual_results"].to_csv(index=False).encode("utf-8"),
            "monte_carlo_annual_results.csv",
            "text/csv",
        )

with comparison_tab:
    st.subheader("P4: block bootstrap versus two-component Normal mixture")
    st.caption("Uses the sidebar horizon, simulation count, seed, endowment, R2 assumptions, liquidity settings and future-return adjustments for both methods. Stress overrides are excluded from this baseline comparison.")
    st.info("Both methods use the SAME constant inflation rate: your fixed rate, or the historical mean CPI YoY when Historical is selected. This isolates differences in return generation.")
    st.caption("Block bootstrap retains observed sequences within each block. The mixture independently selects a lower-mean adverse or higher-mean ordinary component each quarter; these are statistical components, not economic regimes.")
    if not include_comparison:
        st.info("Select Include method comparison, then Run analysis to populate this tab.")
    comparison = st.session_state.get("return_comparison")
    if comparison is not None:
        table, parameters, inflation, method_results = comparison
        st.caption(f"P4 | {cfg.horizon_years} years ({cfg.horizon_years*4} quarters) | {cfg.n_sims:,} paths per method | Shared inflation {inflation:.2%}")
        st.dataframe(table.style.format("{:.3f}"), use_container_width=True)
        component_table = pd.DataFrame({
            "Component": ["Ordinary (higher mean)", "Adverse (lower mean)"],
            "Probability": [1-parameters["adverse_probability"], parameters["adverse_probability"]],
            "Quarterly mean": [parameters["ordinary_mean"], parameters["adverse_mean"]],
            "Quarterly standard deviation": [parameters["ordinary_std"], parameters["adverse_std"]],
        })
        st.markdown("**Historical mixture calibration (before scenario adjustments)**")
        st.dataframe(component_table.style.format({c: "{:.2%}" for c in component_table.columns if c != "Component"}), hide_index=True)
        st.caption("Both components can produce gains and losses. Returns below -100% are redrawn from the same component, so component distributions are truncated. Historical fit is provisional, not a validated forecast.")
        if not liq.enabled:
            st.caption("Liquidity is OFF: payout execution shortfall measures are zero by construction. Support gaps and real-corpus risk still vary.")
        st.download_button("Download return-method comparison", table.to_csv().encode("utf-8"), "portfolio_return_comparison.csv", "text/csv")

with stress_tab:
    st.subheader("Stress testing")
    st.caption("Compares the same model under baseline, a forced Recession start, and a forced Elevated Inflation start. Stress duration is configurable and uses R1 historical condition-specific return/inflation observations rather than arbitrary return shocks.")

    stress_df = st.session_state.get("stress_df")
    if stress_df is not None:
        formatted = stress_df.copy()
        for col in formatted.columns:
            if col == "Scenario":
                continue
            if "($mm)" in col:
                formatted[col] = formatted[col].map(lambda x: f"{x:,.2f}")
            else:
                formatted[col] = formatted[col].map(lambda x: f"{x:.2%}")
        st.dataframe(formatted, use_container_width=True, hide_index=True)
        st.bar_chart(stress_df.set_index("Scenario")[["Median terminal real ($mm)"]])
        st.download_button("Download stress comparison", stress_df.to_csv(index=False).encode("utf-8"), "stress_comparison.csv", "text/csv")

with assumptions_tab:
    st.subheader("Forward-looking framework")
    st.markdown(f"""
    - **Portfolio:** P4, interim Medium | Normal allocation, held constant throughout.
    - **Rebalancing convention:** assume the P4 allocation is maintained each quarter; portfolio-level data cannot verify or simulate trades. No costs, allocation drift or tactical changes.
    - **Horizon:** {cfg.horizon_years} years, {4*cfg.horizon_years} quarterly returns; compounded into annual returns for the existing annual payout engine.
    - **Return baseline:** historical P4 behavior persists unless the user changes the annual mean shift or volatility multiplier. The shift is divided by four; volatility scales deviations around the historical quarterly mean.
    - **Mixture:** two fitted Normal components, chosen independently each quarter. No copula or regime persistence in this method.
    - **Inflation:** historical sampling remains available for the existing methods; the mixture uses historical mean CPI YoY unless a fixed rate is chosen. The controlled comparison always uses one shared constant rate.
    - **Stress:** forced initial quarters use historical condition-specific returns, then resume the selected generator. For mixture this is a hybrid historical stress override, not a fitted regime mixture.
    - **Limits:** historical calibration does not predict future events; outputs are conditional scenarios. Payout timing stays annual.
    """)
    st.subheader("R2 scenario parameters")
    st.dataframe(data.r2_scenarios, use_container_width=True, hide_index=True)

    st.subheader("R1 P4 asset weights and liquidity")
    p4w = data.p4_weights.copy()
    p4w["weight_pct"] = p4w["weight"] * 100.0
    st.dataframe(p4w[["asset", "weight_pct", "liquidity_class"]], use_container_width=True, hide_index=True)

    st.subheader("R1 full-history regime transition matrix")
    st.dataframe(data.transition_matrix.style.format("{:.2%}"), use_container_width=True)

    st.subheader("Calibration notes")
    st.markdown(
        f"""
        - P4 liquid share (Very High + High): **{data.calibration['liquid_share']:.2%}**
        - P4 illiquid share (Low + Very Low): **{data.calibration['illiquid_share']:.2%}**
        - P4 historical geometric annual return: **{data.calibration['geometric_annual_return']:.2%}**
        - P4 historical annualized volatility: **{data.calibration['annualized_volatility']:.2%}**
        - P4 historical maximum drawdown: **{data.calibration['historical_max_drawdown']:.2%}**
        - Private Base other-endowment-changes rate: **{data.calibration['other_changes_rate_base']:.3%}** (provisional R3-derived D2 benchmark)
        """
    )

st.divider()
st.caption("Research 3 model. Baseline liquidity constraints are intentionally inactive until institution-level liquidity benchmarks are finalized.")
