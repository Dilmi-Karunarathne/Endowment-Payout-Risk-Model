from __future__ import annotations

from dataclasses import replace
from io import BytesIO

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

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
        ["Quarterly block bootstrap", "Regime-switching bootstrap"],
        index=1,
        help="Block bootstrap samples contiguous historical P4 quarters. Regime switching simulates Normal/Recession/Elevated Inflation using R1 transition probabilities, then samples historical P4 returns conditional on the simulated state.",
    )
    block_size = st.sidebar.slider("Block size (quarters)", 1, 8, 4, disabled="block" not in return_method.lower())
    starting_regime = st.sidebar.selectbox("Starting economic regime", ["Normal", "Recession", "Elevated inflation"], index=0)

    st.sidebar.subheader("Economic stress")
    stress_label = st.sidebar.selectbox("Stress regime", ["None", "Recession start", "Elevated inflation start"], index=0)
    if stress_label == "Recession start":
        stress_state = "Recession"
        default_q = 6
    elif stress_label == "Elevated inflation start":
        stress_state = "Elevated inflation"
        default_q = 8
    else:
        stress_state = None
        default_q = 0
    stress_quarters = st.sidebar.slider("Forced stress duration (quarters)", 0, 16, default_q, disabled=stress_state is None)

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
        stress_state=stress_state,
        stress_quarters=int(stress_quarters),
    )
    return cfg, inst, liq


data = load_data_cached()

st.title("Endowment Payout-Risk Simulation Model")
st.caption("R1 P4 investment calibration + R2 institutional benchmarks + Monte Carlo / stress simulation")

with st.expander("Model scope and current limitations", expanded=False):
    st.markdown(
        """
        - **Validated core:** investment return roll-forward, gifts, other endowment changes, 3-year moving-average payout, expenses, required support, inflation/real corpus and drawdowns.
        - **Simulation baseline:** quarterly block bootstrap or R1 regime-switching bootstrap.
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

cfg, inst, liq = simulation_controls(data, base_cfg, base_inst, base_liq)

validation_tab, mc_tab, stress_tab, assumptions_tab = st.tabs([
    "Historical validation",
    "Monte Carlo simulation",
    "Stress comparison",
    "Assumptions & data",
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
    st.subheader("Monte Carlo payout-risk simulation")
    if not liq.enabled:
        st.info("Liquidity constraints are OFF, so Actual Payout = Planned Payout. Payout shortfall frequency/depth will therefore be zero; Expected Shortfall and payout-support risk still vary with market/inflation outcomes.")

    run_mc = st.button("Run Monte Carlo simulation", type="primary", key="run_mc")
    if run_mc:
        with st.spinner("Running simulation..."):
            result = run_monte_carlo(data, cfg, inst, liq, p4_history=custom_history)
        st.session_state["mc_result"] = result
        st.session_state["mc_cfg"] = cfg

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

with stress_tab:
    st.subheader("Stress comparison")
    st.caption("Compares the same model under baseline, a forced Recession start, and a forced Elevated Inflation start. Stress duration is configurable and uses R1 historical condition-specific return/inflation observations rather than arbitrary return shocks.")

    c1, c2, c3 = st.columns(3)
    recession_q = c1.slider("Recession stress duration (quarters)", 1, 12, 6)
    inflation_q = c2.slider("Elevated-inflation stress duration (quarters)", 1, 16, 8)
    stress_sims = c3.selectbox("Paths per stress case", [500, 1000, 2000, 3000], index=1)

    run_stress = st.button("Run stress comparison", key="run_stress")
    if run_stress:
        table = []
        with st.spinner("Running stress cases..."):
            base_for_stress = replace(cfg, n_sims=int(stress_sims), stress_state=None, stress_quarters=0)
            for label, scfg in stress_configs(base_for_stress, recession_q, inflation_q).items():
                res = run_monte_carlo(data, scfg, inst, liq, p4_history=custom_history, keep_paths=True)
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
        stress_df = pd.DataFrame(table)
        st.session_state["stress_df"] = stress_df

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
