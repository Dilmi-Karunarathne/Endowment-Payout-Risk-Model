"""Streamlit UI for the Stress testing tab of app.py.

The tab leads with the two R3 framework scenarios (high inflation & elevated rates; prolonged downturn &
liquidity squeeze). The earlier exploratory scenario library, custom builder, reverse stress test and
sensitivity grid are still available behind a toggle."""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from stress_testing import (
    R3_EVIDENCE_SOURCES,
    SCENARIO_1,
    SCENARIO_2,
    DownturnLiquidityParams,
    InflationRatesParams,
    default_cpi_add,
    liquidity_breaking_point,
    run_r3_framework,
    variable_impact_table,
    EQUITY_CRASH_SHOCKS,
    EndowmentShock,
    MarketShock,
    StressScenario,
    asset_shock_table,
    market_portfolio_shock,
    median_real_paths,
    replay_cumulative_return,
    reverse_stress_frontier,
    run_deterministic_suite,
    run_stress_suite,
    scenario_library,
    sensitivity_grid,
)

DEFAULT_SELECTION = [
    "Baseline",
    "Recession start (6q)",
    "GFC replay (2008Q1-2009Q2)",
    "2022 inflation & rates replay",
    "Equity crash (asset-class shock)",
    "Stagflation",
    "Donor retreat",
    "Liquidity squeeze",
    "Severe combined: GFC + donors + liquidity",
]

REPLAY_WINDOWS = {
    "None": (),
    "GFC 2008Q1-2009Q2": ("2008Q1", "2008Q2", "2008Q3", "2008Q4", "2009Q1", "2009Q2"),
    "COVID 2020Q1-Q2": ("2020Q1", "2020Q2"),
    "2022 inflation 2022Q1-Q4": ("2022Q1", "2022Q2", "2022Q3", "2022Q4"),
}


def _fmt_table(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if col in ("Scenario", "Category", "Liquidity constraints"):
            continue
        if "($mm)" in col:
            out[col] = out[col].map(lambda x: f"{x:,.2f}" if pd.notna(x) else "—")
        elif "years" in col.lower() or "Years" in col:
            out[col] = out[col].map(lambda x: "Not within horizon" if pd.isna(x) else f"{x:.0f}")
        else:
            out[col] = out[col].map(lambda x: f"{x:.1%}" if pd.notna(x) else "—")
    return out


def _all_scenarios():
    lib = scenario_library()
    for sc in st.session_state.get("custom_scenarios", []):
        lib[sc.name] = sc
    return lib


def _custom_builder(data, horizon):
    with st.expander("Build a custom scenario", expanded=False):
        with st.form("custom_scenario_form", clear_on_submit=False):
            name = st.text_input("Scenario name", "My custom stress")
            st.markdown("**Market shock**")
            m1, m2, m3 = st.columns(3)
            replay_label = m1.selectbox("Historical replay at start", list(REPLAY_WINDOWS), index=0)
            shock_mode = m2.radio("Instantaneous shock", ["Portfolio %", "By asset class"], horizontal=True)
            portfolio_shock = m3.slider("Portfolio shock (quarter 1)", -0.60, 0.0, 0.0, 0.01, disabled=shock_mode != "Portfolio %")
            asset_shocks = {}
            if shock_mode == "By asset class":
                base = asset_shock_table(data, EQUITY_CRASH_SHOCKS)[["asset", "weight", "shock"]]
                edited = st.data_editor(
                    base, hide_index=True, use_container_width=True, key="asset_shock_editor",
                    column_config={
                        "weight": st.column_config.NumberColumn("P4 weight", format="%.3f", disabled=True),
                        "shock": st.column_config.NumberColumn("Shock (e.g. -0.35)", min_value=-1.0, max_value=1.0, step=0.01),
                        "asset": st.column_config.TextColumn("Asset", disabled=True),
                    },
                )
                asset_shocks = dict(zip(edited["asset"], edited["shock"].astype(float)))
            m4, m5, m6 = st.columns(3)
            drag = m4.slider("Annual return drag", -0.08, 0.0, 0.0, 0.005)
            drag_years = m4.slider("Drag duration (years)", 0, horizon, 0)
            infl = m5.slider("CPI add-on (pp)", 0.0, 0.06, 0.0, 0.005)
            infl_years = m5.slider("CPI add-on duration (years)", 0, horizon, 0)
            regime = m6.selectbox("Force regime", ["None", "Recession", "Elevated inflation"])
            regime_q = m6.slider("Forced regime quarters", 0, 16, 0)

            st.markdown("**Endowment / institutional shock**")
            e1, e2, e3 = st.columns(3)
            gift_mult = e1.slider("Gifts as % of normal", 0.0, 1.5, 1.0, 0.05)
            gift_years = e1.slider("Gift shock duration (years)", 0, horizon, 0)
            spend_add = e2.slider("Spending-rate change (pp)", -0.02, 0.03, 0.0, 0.0025)
            spend_years = e2.slider("Spending change duration (years)", 0, horizon, 0)
            exp_jump = e3.slider("One-off expense jump (year 1)", 0.0, 0.30, 0.0, 0.01)
            exp_g = e3.slider("Extra expense growth (pp)", 0.0, 0.05, 0.0, 0.0025)
            exp_g_years = e3.slider("Extra expense growth duration (years)", 0, horizon, 0)
            e4, e5, e6 = st.columns(3)
            draw = e4.slider("Special draw (% of corpus)", 0.0, 0.15, 0.0, 0.005)
            draw_years = e4.slider("Special draw duration (years)", 0, horizon, 0)
            liq_on = e5.checkbox("Activate liquidity constraints in this scenario", value=False)
            haircut = e5.slider("Liquid-asset haircut", 0.0, 0.9, 0.0, 0.05)
            haircut_years = e5.slider("Haircut duration (years)", 0, horizon, 0)
            calls = e6.slider("Capital calls (% of corpus)", 0.0, 0.12, 0.0, 0.005)
            calls_years = e6.slider("Capital-call duration (years)", 0, horizon, 0)
            buffer = e6.number_input("Liquidity buffer (years of payout)", 0.0, 3.0, 1.0, 0.25)
            discount = e6.slider("Forced-sale discount", 0.0, 0.6, 0.25, 0.01)
            forced = e6.checkbox("Allow forced sales", value=True)

            submitted = st.form_submit_button("Add scenario to library")
        if submitted:
            sc = StressScenario(
                name=name.strip() or "Custom",
                category="Custom",
                narrative="User-defined scenario.",
                market=MarketShock(
                    replay_quarters=REPLAY_WINDOWS[replay_label],
                    portfolio_shock=float(portfolio_shock) if shock_mode == "Portfolio %" and portfolio_shock != 0 else None,
                    asset_shocks=asset_shocks if shock_mode == "By asset class" else {},
                    return_drag_annual=float(drag), drag_years=int(drag_years),
                    inflation_add=float(infl), inflation_years=int(infl_years),
                    regime_state=None if regime == "None" else regime, regime_quarters=int(regime_q),
                ),
                endowment=EndowmentShock(
                    gift_multiplier=float(gift_mult), gift_years=int(gift_years),
                    spending_rate_add=float(spend_add), spending_years=int(spend_years),
                    expense_level_shock=float(exp_jump), expense_growth_add=float(exp_g), expense_growth_years=int(exp_g_years),
                    special_draw_rate=float(draw), special_draw_years=int(draw_years),
                    capital_call_rate=float(calls), capital_call_years=int(calls_years),
                    liquid_haircut_add=float(haircut), liquid_haircut_years=int(haircut_years),
                    liquidity_overrides=dict(enabled=True, liquidity_buffer_years=float(buffer),
                                             forced_sale_discount=float(discount), allow_forced_sales=bool(forced)) if liq_on else {},
                ),
            )
            customs = [c for c in st.session_state.get("custom_scenarios", []) if c.name != sc.name]
            st.session_state["custom_scenarios"] = customs + [sc]
            st.success(f"Added “{sc.name}” — select it in the scenario list above.")


def _scenario_library_view(data, lib):
    rows = []
    for sc in lib.values():
        m = sc.market
        rows.append({
            "Scenario": sc.name,
            "Category": sc.category,
            "Instant portfolio shock": market_portfolio_shock(data, m),
            "Replay cumulative P4 return": replay_cumulative_return(data, m.replay_quarters) if m.replay_quarters else np.nan,
            "Description": sc.narrative,
        })
    df = pd.DataFrame(rows)
    df["Instant portfolio shock"] = df["Instant portfolio shock"].map(lambda x: f"{x:.1%}" if x else "—")
    df["Replay cumulative P4 return"] = df["Replay cumulative P4 return"].map(lambda x: f"{x:.1%}" if pd.notna(x) else "—")
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.markdown("**Equity-crash asset-class shocks × R1 P4 weights**")
    t = asset_shock_table(data, EQUITY_CRASH_SHOCKS)
    st.dataframe(
        t.style.format({"weight": "{:.1%}", "shock": "{:.0%}", "contribution": "{:.2%}"}),
        use_container_width=True, hide_index=True,
    )
    st.caption("Hypothetical shock sizes are illustrative scenario assumptions, not calibrated forecasts. "
               "Historical replays use actual R1 P4 quarterly returns and CPI.")


def _render_exploratory(data, cfg, inst, liq, custom_history=None):
    st.markdown("### Additional exploratory scenarios")
    st.caption(
        "Each scenario overlays market shocks (historical replays, asset-class shocks, return drag, inflation, forced regimes) "
        "and/or endowment shocks (gifts, spending, expenses, special draws, liquidity) on the same model. All scenarios use "
        "the same random seed, so differences come from the stress, not sampling noise."
    )

    lib = _all_scenarios()
    with st.expander("Scenario library", expanded=False):
        _scenario_library_view(data, lib)
    _custom_builder(data, int(cfg.horizon_years))

    lib = _all_scenarios()
    default = [n for n in DEFAULT_SELECTION if n in lib]
    c1, c2 = st.columns([3, 1])
    chosen = c1.multiselect("Scenarios to run", list(lib), default=default)
    n_paths = c2.selectbox("Paths per scenario", [250, 500, 1000, 2000], index=1)

    if st.button("Run stress tests", type="primary", key="run_stress_lab"):
        scenarios = [lib[n] for n in chosen]
        run_cfg = replace(cfg, n_sims=int(n_paths), stress_state=None, stress_quarters=0)
        bar = st.progress(0.0, text="Running stress scenarios…")
        table, results = run_stress_suite(
            data, run_cfg, inst, liq, scenarios, p4_history=custom_history,
            progress=lambda f, name: bar.progress(f, text=f"Finished {name}"),
        )
        det_table, det_paths = run_deterministic_suite(data, run_cfg, inst, liq, scenarios, p4_history=custom_history)
        bar.empty()
        st.session_state["stress_lab"] = {
            "table": table,
            "paths": median_real_paths(results),
            "det_table": det_table,
            "det_paths": det_paths,
            "initial": run_cfg.initial_endowment,
        }

    res = st.session_state.get("stress_lab")
    if res is not None:
        table = res["table"]
        st.markdown("#### Monte Carlo stress results")
        if liq.enabled:
            st.caption("Liquidity constraints are ON in the main settings, so every scenario uses them.")
        else:
            st.caption("Liquidity constraints are OFF in the main settings; only scenarios that activate them show "
                       "payout shortfalls and forced sales (see the 'Liquidity constraints' column).")
        st.dataframe(_fmt_table(table), use_container_width=True, hide_index=True)

        alpha_col = [c for c in table.columns if c.startswith("ES ")][0]
        left, right = st.columns(2)
        with left:
            fig = px.bar(table, x="Δ median real vs baseline", y="Scenario", orientation="h", color="Category",
                         title="Median terminal real corpus vs baseline")
            fig.update_layout(xaxis_tickformat=".0%", yaxis={"categoryorder": "total descending"},
                              margin=dict(l=10, r=10, t=40, b=10), legend_title_text="")
            st.plotly_chart(fig, use_container_width=True)
        with right:
            fig = px.bar(table, x=alpha_col, y="Scenario", orientation="h", color="Category",
                         title=f"{alpha_col} (tail risk)")
            fig.update_layout(xaxis_tickformat=".0%", yaxis={"categoryorder": "total ascending"},
                              margin=dict(l=10, r=10, t=40, b=10), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        paths = res["paths"]
        fig = px.line(paths, x="year", y="p50", color="Scenario",
                      labels={"p50": "Median real ending assets ($mm)", "year": ""},
                      title="Median real endowment path by scenario")
        fig.add_hline(y=res["initial"], line_dash="dot", annotation_text="Initial corpus")
        fig.update_layout(margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)

        fig = px.scatter(table, x="Δ payout vs baseline", y="Δ median real vs baseline", color="Category",
                         hover_name="Scenario", title="Trade-off: payout to the institution vs corpus preservation")
        fig.update_traces(marker=dict(size=12))
        fig.update_layout(xaxis_tickformat=".0%", yaxis_tickformat=".0%", margin=dict(l=10, r=10, t=40, b=10))
        fig.add_hline(y=0, line_color="gray", line_width=1)
        fig.add_vline(x=0, line_color="gray", line_width=1)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Deterministic stress path")
        st.caption("Same shocks applied to a single constant-return path (P4 long-run geometric return and average "
                   "historical CPI). Easier to explain line by line than Monte Carlo medians.")
        st.dataframe(_fmt_table(res["det_table"]), use_container_width=True, hide_index=True)
        det_choice = st.selectbox("Inspect deterministic path", list(res["det_paths"]))
        dp = res["det_paths"][det_choice]
        fig = go.Figure()
        fig.add_bar(x=dp["year"], y=dp["actual_payout"], name="Actual payout", yaxis="y2", opacity=0.45)
        fig.add_scatter(x=dp["year"], y=dp["ending_assets"], name="Nominal ending assets", mode="lines+markers")
        fig.add_scatter(x=dp["year"], y=dp["real_ending_assets"], name="Real ending assets", mode="lines+markers")
        fig.update_layout(
            yaxis=dict(title="Assets ($mm)"), yaxis2=dict(title="Payout ($mm)", overlaying="y", side="right", showgrid=False),
            margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", y=-0.15),
        )
        st.plotly_chart(fig, use_container_width=True)
        with st.expander("Year-by-year detail"):
            cols = ["year", "portfolio_return", "inflation", "beginning_assets", "endowment_gifts", "planned_payout",
                    "actual_payout", "special_draw", "capital_call", "forced_sale_loss", "ending_assets",
                    "real_ending_assets", "payout_support_gap"]
            st.dataframe(dp[cols], use_container_width=True, hide_index=True)

        d1, d2 = st.columns(2)
        d1.download_button("Download Monte Carlo stress table", table.to_csv(index=False).encode("utf-8"),
                           "stress_test_monte_carlo.csv", "text/csv")
        d2.download_button("Download deterministic stress table", res["det_table"].to_csv(index=False).encode("utf-8"),
                           "stress_test_deterministic.csv", "text/csv")

    st.divider()
    st.markdown("#### Reverse stress test")
    st.caption("How large an instantaneous market shock at the start of the projection would leave the real corpus at a "
               "given % of today's endowment at the end of the horizon? Uses the deterministic path, optionally on top "
               "of an endowment scenario.")
    lib = _all_scenarios()
    r1, r2 = st.columns([2, 1])
    endow_options = ["Baseline"] + [n for n, s in lib.items() if s.category in ("Endowment", "Custom")]
    base_name = r1.selectbox("Apply on top of", endow_options, index=0)
    target = r2.slider("Target terminal real corpus (% of initial)", 0.3, 1.2, 0.8, 0.05)
    if st.button("Run reverse stress test", key="run_reverse"):
        base_sc = lib[base_name]
        targets = sorted({round(x, 2) for x in (1.0, 0.9, 0.8, 0.7, 0.6, 0.5, target)}, reverse=True)
        st.session_state["reverse"] = (base_name, target, reverse_stress_frontier(
            data, cfg, inst, liq, targets=targets, base_scenario=base_sc, p4_history=custom_history))
    if st.session_state.get("reverse") is not None:
        base_name_r, target_r, frontier = st.session_state["reverse"]
        hit = frontier.loc[np.isclose(frontier["Target terminal real (% of initial)"], target_r), "Breaking instantaneous shock"]
        val = float(hit.iloc[0]) if len(hit) else np.nan
        if pd.isna(val):
            st.info(f"Under “{base_name_r}”, even a −95% shock does not push the real corpus below {target_r:.0%} of initial.")
        elif val == 0.0:
            st.warning(f"Under “{base_name_r}”, the real corpus ends below {target_r:.0%} of initial even with no market shock.")
        else:
            st.metric(f"Breaking shock for {target_r:.0%} real corpus ({base_name_r})", f"{val:.1%}",
                      help="Compare with the P4 historical max drawdown and the GFC replay cumulative return.")
            st.caption(f"Reference points: P4 historical max drawdown {data.calibration['historical_max_drawdown']:.1%}; "
                       f"GFC replay cumulative P4 return {replay_cumulative_return(data, REPLAY_WINDOWS['GFC 2008Q1-2009Q2']):.1%}.")
        fig = px.line(frontier, x="Target terminal real (% of initial)", y="Breaking instantaneous shock", markers=True,
                      title="Reverse stress frontier")
        fig.update_layout(xaxis_tickformat=".0%", yaxis_tickformat=".0%", margin=dict(l=10, r=10, t=40, b=10))
        fig.add_hline(y=float(data.calibration["historical_max_drawdown"]), line_dash="dot",
                      annotation_text="P4 historical max drawdown")
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.markdown("#### Sensitivity grid: market shock × spending rate")
    g1, g2 = st.columns(2)
    metric_label = g1.selectbox("Metric", ["Terminal real corpus (% of initial)", "Cumulative payout ($mm)"])
    gift_mult = g2.slider("Gifts as % of normal (all years)", 0.0, 1.5, 1.0, 0.1, key="grid_gift")
    if st.button("Build sensitivity grid", key="run_grid"):
        metric = "terminal_real_pct_initial" if metric_label.startswith("Terminal") else "cumulative_payout"
        st.session_state["grid"] = (metric_label, sensitivity_grid(
            data, cfg, inst, liq, gift_multiplier=gift_mult, metric=metric, p4_history=custom_history))
    if st.session_state.get("grid") is not None:
        label, grid = st.session_state["grid"]
        is_pct = label.startswith("Terminal")
        z = grid.to_numpy(dtype=float)
        fig = px.imshow(
            z,
            x=[f"{c:.2%}" for c in grid.columns],
            y=[f"{r:.0%}" for r in grid.index],
            color_continuous_scale="RdYlGn",
            labels=dict(x="Effective spending rate", y="Instantaneous market shock", color=label),
            text_auto=".0%" if is_pct else ".1f",
            aspect="auto",
            color_continuous_midpoint=1.0 if is_pct else None,
        )
        fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Deterministic path. Current R2 spending rate: {inst.effective_spending_rate:.2%}. "
                   "Green = corpus preserved / higher payout; red = erosion.")


# ---------------------------------------------------------------------------
# R3 stress-scenario framework view
# ---------------------------------------------------------------------------

S1_COLS = ["Cumulative real payout ($mm)", "Δ real payout vs baseline", "Real payout, first 3 yrs ($mm)",
           "Pr(any support gap)", "Total support gap ($mm)", "Avg payout adequacy"]
S2_COLS = ["Pr(≥1 payout shortfall)", "Avg shortfall depth", "Pr(forced sale)", "Mean forced-sale loss ($mm)",
           "Lowest liquidity coverage (median)", "Liquidity constraints"]


def _fmt_focus(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if col in ("Scenario", "Liquidity constraints"):
            continue
        if "($mm)" in col:
            out[col] = out[col].map(lambda x: f"{x:,.2f}" if pd.notna(x) else "—")
        elif "coverage" in col.lower():
            out[col] = out[col].map(lambda x: f"{x:.1f}x" if pd.notna(x) else "off")
        else:
            out[col] = out[col].map(lambda x: f"{x:.1%}" if pd.notna(x) else "—")
    return out


def _fmt_impact(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    year_cols = [c for c in out.columns if c.isdigit()]
    out[year_cols] = out[year_cols].astype(object)
    for i, row in df.iterrows():
        for c in year_cols:
            v = row[c]
            if pd.isna(v):
                out.at[i, c] = "—"
            elif row["Unit"] == "pct":
                out.at[i, c] = f"{v:.1%}"
            elif row["Unit"] == "x":
                out.at[i, c] = f"{v:.1f}x"
            else:
                out.at[i, c] = f"{v:,.2f}"
    return out.drop(columns=["Unit"])


def _s1_controls(data, horizon):
    d = InflationRatesParams()
    st.caption("Severity: actual 2022 P4 returns and CPI (stocks and bonds fell together as rates rose). "
               "Recovery: R1 transition matrix after the stress window.")
    a, b = st.columns(2)
    elevated_q = a.slider("Duration in Elevated-inflation regime (quarters, incl. 2022 replay)", 4, 24, d.elevated_quarters,
                          help="Default 16 = the 2021Q2-2025Q1 elevated-inflation spell in the CPI history.")
    cpi_add = a.slider("Extra CPI after the replay (pp)", 0.0, 0.05, round(default_cpi_add(data), 3), 0.001, format="%.3f",
                       help="Default lifts post-replay CPI from the all-history elevated-regime average to the 2021-25 spell average.")
    exp_g = b.slider("Operating-expense growth during stress", 0.02, 0.08, d.expense_growth, 0.001, format="%.3f",
                     help="Default 4.7% = average of Commonfund HEPI FY2022 (5.2%) and FY2023 (4.1%).")
    exp_y = b.slider("Expense-stress duration (years)", 0, min(10, horizon), d.expense_years)
    c, e = st.columns(2)
    drag = c.slider("Extra cost-of-capital return drag (per year, after replay)", -0.04, 0.0, 0.0, 0.005, format="%.3f",
                    help="Optional. The 2022 replay already includes the rate-driven repricing.")
    drag_y = e.slider("Return-drag duration (years)", 0, min(10, horizon), 0)
    return InflationRatesParams(elevated_quarters=int(elevated_q), cpi_add=float(cpi_add), expense_growth=float(exp_g),
                                expense_years=int(exp_y), return_drag=float(drag), drag_years=int(drag_y))


def _s2_controls(horizon):
    d = DownturnLiquidityParams()
    st.caption("Severity: actual GFC P4 path 2008Q1-2009Q2 (-22.0%). Liquidity constraints are switched ON for this scenario.")
    a, b = st.columns(2)
    rec_drag = a.slider("Slow-recovery return drag (per year, after replay)", -0.06, 0.0, d.recovery_drag, 0.005, format="%.3f",
                        help="Assumption: P4 rebounded quickly after 2009Q2; the drag tests a prolonged downturn.")
    rec_y = a.slider("Slow-recovery duration (years)", 0, min(10, horizon), d.recovery_years)
    gift = b.slider("Gifts as share of normal", 0.5, 1.0, d.gift_multiplier, 0.01,
                    help="Default 0.88 = giving to colleges fell 11.9% in FY2009 (CAE VSE).")
    gift_y = b.slider("Gift-shock duration (years)", 0, min(10, horizon), d.gift_years)
    st.markdown("**Liquidity squeeze**")
    c, e, f = st.columns(3)
    drain = c.slider("Net private cash drain (% of corpus / yr)", 0.0, 0.12, d.private_cash_drain, 0.005, format="%.3f",
                     help="Capital calls continue while private distributions are delayed.")
    drain_y = c.slider("Cash-drain duration (years)", 0, min(10, horizon), d.drain_years)
    haircut = e.slider("Liquid assets unavailable for payout", 0.0, 0.95, d.liquid_haircut, 0.05,
                       help="Share of the liquid book held back for rebalancing, collateral or because of depressed prices.")
    haircut_y = e.slider("Haircut duration (years)", 0, min(10, horizon), d.haircut_years)
    buffer = f.number_input("Liquidity reserve (years of payout)", 0.0, 3.0, d.buffer_years, 0.25)
    disc = f.slider("Forced-sale discount on illiquid assets", 0.0, 0.6, d.forced_sale_discount, 0.01,
                    help="Secondary bids were still ~80% of NAV in H1 2010, after the recovery; trough discounts were deeper.")
    forced = f.checkbox("Allow forced sales (otherwise the payout is cut)", value=d.allow_forced_sales)
    return DownturnLiquidityParams(recovery_drag=float(rec_drag), recovery_years=int(rec_y), gift_multiplier=float(gift),
                                   gift_years=int(gift_y), private_cash_drain=float(drain), drain_years=int(drain_y),
                                   liquid_haircut=float(haircut), haircut_years=int(haircut_y), buffer_years=float(buffer),
                                   forced_sale_discount=float(disc), allow_forced_sales=bool(forced))


def _year_median(results, column):
    frames = []
    for name, res in results.items():
        ar = res["annual_results"]
        if ar.empty or column not in ar.columns or ar[column].isna().all():
            continue
        x = ar.groupby("year")[column].median().reset_index()
        x["Scenario"] = name
        frames.append(x)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def render_stress_tab(data, cfg, inst, liq, custom_history=None):
    st.subheader("Stress testing: R3 stress-scenario framework")
    st.caption("Goal: evaluate payout sustainability under two major adverse economic regimes. Both scenarios run "
               "against the same baseline with the same random seed, so differences come from the stress, not sampling noise.")

    horizon = int(cfg.horizon_years)
    c1, c2 = st.columns(2)
    with c1:
        use1 = st.checkbox(SCENARIO_1, value=True)
        st.caption("**Conditions:** high inflation, rising cost of capital, elevated operating expenses.  \n"
                   "**Focus:** maintaining real payout value and meeting institutional funding needs.")
    with c2:
        use2 = st.checkbox(SCENARIO_2, value=True)
        st.caption("**Conditions:** market losses, delayed private distributions, illiquid asset sales.  \n"
                   "**Focus:** meeting required payouts while minimising forced-sale asset losses.")

    with st.expander("Scenario 1 shock parameters (severity, duration, recovery)", expanded=False):
        p1 = _s1_controls(data, horizon)
    with st.expander("Scenario 2 shock parameters (severity, duration, recovery, liquidity)", expanded=False):
        p2 = _s2_controls(horizon)

    r1, r2 = st.columns([1, 3])
    n_paths = r1.selectbox("Paths per scenario", [250, 500, 1000, 2000], index=1, key="r3_paths")
    include = [n for n, on in ((SCENARIO_1, use1), (SCENARIO_2, use2)) if on]
    r2.write("")
    run = r2.button("Run R3 stress scenarios", type="primary", key="run_r3", disabled=not include)
    if not include:
        st.info("Select at least one scenario.")

    if run and include:
        run_cfg = replace(cfg, n_sims=int(n_paths), stress_state=None, stress_quarters=0)
        bar = st.progress(0.0, text="Running scenarios…")
        out = run_r3_framework(data, run_cfg, inst, liq, p1, p2, include=include, p4_history=custom_history,
                               progress=lambda f, name: bar.progress(f, text=f"Finished {name}"))
        out["breaking"] = (liquidity_breaking_point(data, run_cfg, inst, liq, p2, p4_history=custom_history)
                           if SCENARIO_2 in include else None)
        out["include"] = include
        bar.empty()
        st.session_state["r3"] = out

    res = st.session_state.get("r3")
    if res is not None:
        focus = res["focus"]
        base = focus.iloc[0]
        st.markdown("#### Headline results")
        if SCENARIO_1 in res["include"]:
            r = focus.set_index("Scenario").loc[SCENARIO_1]
            st.markdown(f"**{SCENARIO_1}**")
            m = st.columns(4)
            m[0].metric("Cumulative real payout", f"${r['Cumulative real payout ($mm)']:,.1f}M",
                        f"{r['Δ real payout vs baseline']:.1%} vs baseline")
            m[1].metric("Pr(any support gap)", f"{r['Pr(any support gap)']:.0%}",
                        f"{r['Pr(any support gap)'] - base['Pr(any support gap)']:+.0%} vs baseline", delta_color="inverse")
            m[2].metric("Total support gap (median)", f"${r['Total support gap ($mm)']:,.1f}M")
            m[3].metric("Median terminal real corpus", f"${r['Median terminal real ($mm)']:,.1f}M",
                        f"{r['Δ median real vs baseline']:.1%} vs baseline")
        if SCENARIO_2 in res["include"]:
            r = focus.set_index("Scenario").loc[SCENARIO_2]
            st.markdown(f"**{SCENARIO_2}**")
            m = st.columns(4)
            m[0].metric("Pr(≥1 payout shortfall)", f"{r['Pr(≥1 payout shortfall)']:.0%}",
                        f"avg depth {r['Avg shortfall depth']:.1%}", delta_color="off")
            m[1].metric("Pr(forced sale)", f"{r['Pr(forced sale)']:.0%}")
            m[2].metric("Mean forced-sale loss", f"${r['Mean forced-sale loss ($mm)']:,.2f}M")
            cov = r["Lowest liquidity coverage (median)"]
            m[3].metric("Lowest liquidity coverage", f"{cov:.1f}x" if pd.notna(cov) else "—",
                        help="Cash available for the payout ÷ planned payout, at its worst year (median path). Below 1x, "
                             "forced sales or payout cuts are needed.")
            b = res.get("breaking")
            if b:
                h, dr = b["breaking_haircut"], b["breaking_cash_drain"]
                st.caption(
                    "**Liquidity breaking point (deterministic path):** forced sales or payout cuts begin once "
                    + (f"**{h:.0%}** of liquid assets are unavailable" if pd.notna(h) else "no haircut up to 100% is enough")
                    + " (other settings unchanged), or once the net private cash drain reaches "
                    + (f"**{dr:.1%}** of the corpus per year." if pd.notna(dr) else "more than 50% of the corpus per year."))

        st.markdown("#### Scenario 1 focus: real payout value and funding needs")
        st.dataframe(_fmt_focus(focus[["Scenario"] + S1_COLS]), use_container_width=True, hide_index=True)
        st.markdown("#### Scenario 2 focus: required payouts and forced-sale losses")
        st.dataframe(_fmt_focus(focus[["Scenario"] + S2_COLS]), use_container_width=True, hide_index=True)
        st.markdown("#### Corpus risk (both scenarios)")
        corpus_cols = ["Median terminal real ($mm)", "Δ median real vs baseline", "5th pct terminal real ($mm)",
                       "Pr(real corpus < initial)", [c for c in focus.columns if c.startswith("ES ")][0]]
        st.dataframe(_fmt_focus(focus[["Scenario"] + corpus_cols]), use_container_width=True, hide_index=True)

        left, right = st.columns(2)
        with left:
            rp = _year_median(res["results"], "real_payout")
            fig = px.line(rp, x="year", y="real_payout", color="Scenario", markers=True,
                          labels={"real_payout": "Median real payout ($mm)", "year": ""}, title="Real payout value by year")
            fig.update_layout(margin=dict(l=10, r=10, t=40, b=10), legend=dict(orientation="h", y=-0.2), legend_title_text="")
            st.plotly_chart(fig, use_container_width=True)
        with right:
            paths = res["paths"]
            fig = px.line(paths, x="year", y="p50", color="Scenario", markers=True,
                          labels={"p50": "Median real ending assets ($mm)", "year": ""}, title="Real endowment by year")
            fig.add_hline(y=float(cfg.initial_endowment), line_dash="dot", annotation_text="Initial corpus")
            fig.update_layout(margin=dict(l=10, r=10, t=40, b=10), legend=dict(orientation="h", y=-0.2), legend_title_text="")
            st.plotly_chart(fig, use_container_width=True)

        left, right = st.columns(2)
        with left:
            gap_mean = []
            for name, rr in res["results"].items():
                x = rr["annual_results"].groupby("year")["payout_support_gap"].mean().reset_index()
                x["Scenario"] = name
                gap_mean.append(x)
            gap = pd.concat(gap_mean, ignore_index=True)
            fig = px.bar(gap, x="year", y="payout_support_gap", color="Scenario", barmode="group",
                         labels={"payout_support_gap": "Mean support gap ($mm)", "year": ""},
                         title="Institutional funding gap (payout below required support)")
            fig.update_layout(margin=dict(l=10, r=10, t=40, b=10), legend=dict(orientation="h", y=-0.2), legend_title_text="")
            st.plotly_chart(fig, use_container_width=True)
        with right:
            cov = _year_median(res["results"], "liquidity_coverage")
            if not cov.empty:
                fig = px.line(cov, x="year", y="liquidity_coverage", color="Scenario", markers=True,
                              labels={"liquidity_coverage": "Median liquidity coverage (x payout)", "year": ""},
                              title="Liquidity coverage (below 1x = forced sales / payout cuts)")
                fig.add_hline(y=1.0, line_dash="dot", line_color="red", annotation_text="1x")
                fig.update_layout(margin=dict(l=10, r=10, t=40, b=10), legend=dict(orientation="h", y=-0.2),
                                  legend_title_text="")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Liquidity coverage is shown when a scenario has liquidity constraints on (Scenario 2).")

        st.markdown("#### Variable impacts: returns, inflation, expenses, payout, liquidity")
        st.caption("Deterministic path (P4 long-run return and average historical CPI as the baseline) so each shock's "
                   "effect can be read year by year.")
        names = [n for n in res["det_paths"] if n != "Baseline"]
        pick = st.selectbox("Scenario", names, key="r3_impact_pick")
        impact = variable_impact_table(res["det_paths"]["Baseline"], res["det_paths"][pick], years=min(6, horizon))
        st.dataframe(_fmt_impact(impact), use_container_width=True, hide_index=True)

        st.markdown("#### Calibration and empirical grounding")
        cal = res["calibration"]
        cal = cal[cal["Scenario"].isin(res["include"])]
        st.dataframe(cal, use_container_width=True, hide_index=True)
        st.caption("Rows marked 'Assumption (to be confirmed)' are placeholders until R2/D2 deliver institution-level "
                   "liquidity and commitment benchmarks. Sources: "
                   + "; ".join(f"[{t}]({u})" for t, u in R3_EVIDENCE_SOURCES))

        d1, d2, d3 = st.columns(3)
        d1.download_button("Download focus results", focus.to_csv(index=False).encode("utf-8"),
                           "r3_stress_focus_results.csv", "text/csv")
        d2.download_button("Download variable impacts", impact.to_csv(index=False).encode("utf-8"),
                           "r3_variable_impacts.csv", "text/csv")
        d3.download_button("Download calibration table", res["calibration"].to_csv(index=False).encode("utf-8"),
                           "r3_calibration.csv", "text/csv")

    st.divider()
    if st.toggle("Show additional exploratory scenarios and tools (scenario library, custom builder, reverse stress, "
                 "sensitivity grid)", value=False, key="show_exploratory"):
        _render_exploratory(data, cfg, inst, liq, custom_history)
