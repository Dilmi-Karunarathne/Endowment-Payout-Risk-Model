"""Streamlit UI for the stress-testing lab (rendered inside the 'Stress testing' tab of app.py)."""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from stress_testing import (
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


def render_stress_tab(data, cfg, inst, liq, custom_history=None):
    st.subheader("Stress testing: market scenarios and endowment shocks")
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
