"""Dark one-screen Streamlit dashboard for the v11 cash-first baseline simulation.

Run with: streamlit run app.py
Only a single baseline simulation is supported. No stress tabs or batch runs.
"""
import html
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from r1_model import STRATEGIES
from simple_analysis import (
    BaselineOptions, HORIZON, SEED, BLOCK_QUARTERS,
    INITIAL_REGIME, PAYOUT_DEADLINE_MONTHS, run_baseline,
)

st.set_page_config(
    page_title="Endowment Payout Risk | Simple Dashboard",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Matching the reference image: dark navy background, muted-blue panels,
# strong text contrast, restrained cyan/orange accents.
BG = "#09111e"
PANEL = "#152238"
PANEL2 = "#112039"
BORDER = "#314765"
FG = "#eef5ff"
MUTED = "#acbfd9"
BLUE = "#66a7ed"
TEAL = "#46d1ba"
ORANGE = "#ffb566"

st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background: #09111e !important;
    color: #eef5ff !important;
}
[data-testid="stHeader"] { background-color: rgba(9,17,30,.95) !important; }
[data-testid="stSidebar"] { background: #0e1b30 !important; border-right: 1px solid #314765; }
[data-testid="stSidebar"] * { color: #e9f4ff; }
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] {color: #c4d6eb !important;}
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-baseweb="input"] > div {
    background: #15263e !important;
    color: #eef5ff !important;
    border: 1px solid #355273 !important;
}
.block-container { max-width: 1190px; padding-top: 1.2rem !important; padding-bottom: 2.5rem !important; }
h1, h2, h3, p, label { color: #eef5ff; }
[data-testid="stCaptionContainer"] { color: #acbfd9 !important; }
[data-testid="stExpander"] { background: #152238; border: 1px solid #314765; border-radius: 11px; }
[data-testid="stExpander"] summary { color: #f0f6ff; font-weight: 650; }
[data-testid="stVerticalBlockBorderWrapper"] > div { border-color: #314765 !important; }
[data-testid="stDataFrame"], [data-testid="stTable"] { border-radius: 8px; overflow: hidden; }
[data-testid="stForm"] { border: none !important; padding: 0 !important; }
[data-testid="stDownloadButton"] button {border: 1px solid #426386; background: #182b47; color: #e7f2ff;}
[data-testid="stDownloadButton"] button:hover {border-color: #78aeec; background: #203b60;}
.dashboard-header {
    border: 1px solid #355274; border-radius: 12px 12px 8px 8px;
    background: linear-gradient(115deg, #183659, #132844 65%, #12223b);
    padding: 18px 22px 17px; margin-bottom: 16px;
}
.dashboard-header .eyebrow {font-size: 12px; color: #c5d9f0; letter-spacing: .08em; text-transform: uppercase;}
.dashboard-header h1 {font-size: clamp(22px, 2.4vw, 33px); color: #ffffff; margin: 4px 0; line-height:1.1;}
.dashboard-header p { color: #bfd3e9; font-size: 13px; margin: 7px 0 0;}
.section-label {font-size: 18px; font-weight: 750; color:#f2f7ff; margin: 6px 0 10px;}
.small-line {font-size: 12px; color: #bed0e6; padding-bottom: 10px;}
.stat-card {
    min-height: 121px; padding: 15px 15px 13px;
    border: 1px solid #344e70; border-radius: 10px;
    background: linear-gradient(165deg, #192d49, #142239);
    margin-bottom: 10px;
}
.stat-label {font-size: 13px; line-height:1.3; color:#dbe9fb; font-weight:650;}
.stat-number {font-size: clamp(23px, 2.4vw, 37px); font-weight:780; letter-spacing:-.035em; line-height: 1.25; margin: 6px 0 3px;}
.stat-sub {font-size: 11.5px; line-height:1.45; color:#aabfda;}
.notes-strip { padding: 10px 13px; background:#14253c; border:1px solid #304967; border-radius:8px; color:#d1e2f5; font-size:12px; margin: 6px 0 16px; }
.chart-caption { color: #b0c1d5; font-size: 11px; margin:-6px 2px 12px; line-height:1.4; }
.small-legend { font-size:11px; color:#aec2da; }
.footnote { border-top:1px solid #304967; padding-top:11px; margin-top:14px; font-size:11.5px; color:#9eb4cd; }
@media (max-width: 800px) { .stat-card {min-height:112px;} .block-container {padding-left:.7rem;padding-right:.7rem;} }
</style>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False, max_entries=4)
def cached_baseline(settings: BaselineOptions):
    return run_baseline(settings)


with st.sidebar:
    st.markdown("### 🎓 Your endowment")
    st.caption("One baseline simulation · five inputs")
    with st.form("single_run"):
        institution = st.selectbox("Institution", ["Private", "Public"], index=0)
        profile = st.selectbox("R2 benchmark profile", ["Low", "Base", "High"], index=1,
                               help="R2 Low/Base/High are marginal percentiles, not worst/best cases.")
        strategy = st.selectbox("Portfolio strategy (R1)", STRATEGIES, index=STRATEGIES.index("HRP"))
        starting = st.number_input("Starting endowment ($M)", min_value=1.0, max_value=10000.0,
                                   value=150.0, step=10.0)
        paths = st.selectbox("Simulation paths", [100, 500, 1000, 5000], index=2,
                             format_func=lambda x: f"{x:,}")
        run = st.form_submit_button("▶ Run simulation", type="primary", use_container_width=True)
    st.caption("Fixed: 5 years, 2027–2031 · HRP-style return method for selected portfolio · cash-first payout")
    with st.expander("Model assumptions", expanded=False):
        st.markdown(f"""- R1 initial regime: **{INITIAL_REGIME}**
- R1 joint asset/inflation bootstrap: **{BLOCK_QUARTERS} quarters**
- Seed **{SEED}**, 0 pp return shift, 1× volatility
- R2 three-year payout average; **3%–5%** floor/ceiling
- Cash-first funding, eligible net asset sales within **{PAYOUT_DEADLINE_MONTHS} months**
- Gifts assumed liquid and unrestricted; no extra reserves, capital calls, borrowing or stress overlays
- R1 40% and R2 3× liquidity thresholds monitored separately
- Investment-management fees not comprehensively deducted
""")

st.markdown("""
<div class="dashboard-header">
 <div class="eyebrow">Research 3 · R1 assets + R2 benchmarks</div>
 <h1>Endowment Payout Risk Model</h1>
 <p>Baseline Monte Carlo simulation · Investment returns, cash-funded payouts, liquidity, and purchasing power</p>
</div>
""", unsafe_allow_html=True)

if run:
    opts = BaselineOptions(institution, profile, strategy, float(starting), int(paths))
    with st.spinner(f"Running {paths:,} simulated 5-year paths…"):
        try:
            st.session_state.baseline_dashboard = cached_baseline(opts)
        except Exception as exc:
            st.session_state.pop("baseline_dashboard", None)
            st.error(f"Could not complete simulation: {exc}")

if "baseline_dashboard" not in st.session_state:
    st.markdown("<div class='section-label'>Simulate</div>", unsafe_allow_html=True)
    st.info("Choose your five inputs on the left and click **Run simulation** to generate live charts and risk measures. Nothing shown here is a fabricated example result.")
    st.markdown("""**Results shown after running:** four headline risk measures, planned vs. actual payout, purchasing power, funding coverage, unpaid payout by year, investment-return distribution, detailed risk measures, and CSV exports.""")
    st.stop()

r = st.session_state.baseline_dashboard
opt, inst = r["options"], r["institutional"]
m, y, ret, a = r["metrics"], r["yearly"], r["return_stats"], r["annual_detail"]


def pct(x):
    return f"{100*x:.1f}%"


def money(x):
    return f"${x:,.2f}M"


def stat_card(title, number, description, accent=BLUE):
    # All values are derived from completed simulation results.
    st.markdown(f"""
    <div class="stat-card">
     <div class="stat-label">{html.escape(title)}</div>
     <div class="stat-number" style="color:{accent}">{html.escape(number)}</div>
     <div class="stat-sub">{html.escape(description)}</div>
    </div>""", unsafe_allow_html=True)


def plot_layout(fig, title, subtitle="", y_label=None, x_label="Projection year"):
    fig.update_layout(
        title=dict(text=title, x=.03, font=dict(size=16, color=FG)),
        paper_bgcolor=PANEL, plot_bgcolor=PANEL,
        font=dict(family="Arial, sans-serif", color=FG, size=11),
        height=322, margin=dict(l=12, r=15, b=28, t=68),
        xaxis=dict(title=x_label, showgrid=False, tickfont=dict(color=MUTED),
                   title_font=dict(color=MUTED), linecolor=BORDER, zeroline=False),
        yaxis=dict(title=y_label, gridcolor="#273a56", gridwidth=.65,
                   tickfont=dict(color=MUTED), title_font=dict(color=MUTED), zeroline=False),
        legend=dict(orientation="h", x=0, y=1.13, bgcolor="rgba(0,0,0,0)",
                    font=dict(size=10, color="#d4e2f2")),
        hovermode="x unified",
    )
    return fig


st.markdown("<div class='section-label'>Simulate</div>", unsafe_allow_html=True)
st.markdown(
    f"<div class='small-line'><strong>{opt.institution} / {opt.profile}</strong> · {opt.strategy} · "
    f"${opt.initial_endowment_m:,.0f}M opening endowment · {opt.paths:,} paths · "
    f"2027–2031 · R2 spending {inst.effective_spending_rate:.2%} · "
    f"Median 5-year annualized investment return <strong style='color:#86bdf6'>{ret['median_cagr']:.2%}</strong> "
    f"· Purchasing-power ES (95%) <strong style='color:#86bdf6'>{pct(m['purchasing_power_expected_shortfall_pct_initial'])}</strong></div>",
    unsafe_allow_html=True,
)

if not 101 <= opt.initial_endowment_m <= 250:
    st.warning("R2 benchmarks come from $101M–$250M endowment institutions; this selection extrapolates outside that cohort.")

k1, k2, k3, k4 = st.columns(4, gap="small")
with k1:
    stat_card("Payout funding risk", pct(m["probability_at_least_one_shortfall"]),
              "Chance of at least one unpaid scheduled payout")
with k2:
    cov = m["median_minimum_payout_liquidity_coverage_ratio"]
    stat_card("Funding coverage", f"{cov:.2f}×" if math.isfinite(cov) else "N/A",
              "Median minimum cash-funding capacity ÷ planned payout", TEAL)
with k3:
    stat_card("Real principal erosion", pct(m["probability_real_corpus_erosion"]),
              "Chance real assets fall below opening purchasing power", ORANGE)
with k4:
    stat_card("Institutional support gap", pct(m["probability_any_support_gap"]),
              "Chance of any payout gap versus R2 support target")

st.markdown(
    "<div class='notes-strip'>"
    "<b>How to read this:</b> A positive earnings + gifts gap does <b>not</b> automatically mean an unpaid payout. "
    "Funding coverage of <b>1×</b> is enough for that year's planned payout in this model. "
    "R2's separate <b>3× liquid-assets policy</b> is monitored independently."
    "</div>", unsafe_allow_html=True,
)

# Pick a genuine simulation path for the payout deviation illustration.
path_shortfalls = a.groupby("path_id", sort=True)["payout_shortfall_amount"].sum()
if (path_shortfalls > 1e-9).any():
    selected_path_id = int(path_shortfalls.idxmax())
    path_description = f"Actual simulated path {selected_path_id}: largest total unpaid payout"
else:
    by_path = r["return_by_path"]
    pos = (by_path["five_year_cagr"] - ret["median_cagr"]).abs().idxmin()
    selected_path_id = int(by_path.loc[pos, "path_id"])
    path_description = f"Representative simulated path {selected_path_id} (no unpaid payouts)"
path = a[a.path_id == selected_path_id].sort_values("year")

# Main charts — precisely the four topics in the user's reference screenshot.
left, right = st.columns(2, gap="medium")
with left:
    payout = go.Figure()
    payout.add_trace(go.Scatter(x=path.year, y=path.planned_payout,
                                name="Planned payout", mode="lines+markers",
                                line=dict(color=BLUE, width=2.5)))
    payout.add_trace(go.Scatter(x=path.year, y=path.actual_payout,
                                name="Actual payout", mode="lines+markers",
                                fill="tonexty", fillcolor="rgba(255,181,102,.22)",
                                line=dict(color=TEAL, width=2.8)))
    plot_layout(payout, "Planned vs. actual payout", y_label="Annual payout ($M)")
    st.plotly_chart(payout, use_container_width=True, key="payout_chart", config={"displaylogo": False})
    st.markdown(f"<div class='chart-caption'>{html.escape(path_description)}. Shaded difference represents unpaid payout in this path.</div>", unsafe_allow_html=True)

with right:
    # Include Year 0 so the principal reference is visually meaningful.
    years = [2026] + y.year.astype(int).tolist()
    real = go.Figure()
    real.add_trace(go.Scatter(x=years, y=[opt.initial_endowment_m]+y.real_endowment_p90_m.tolist(),
                              mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
    real.add_trace(go.Scatter(x=years, y=[opt.initial_endowment_m]+y.real_endowment_p10_m.tolist(),
                              mode="lines", fill="tonexty", fillcolor="rgba(102,167,237,.16)",
                              line=dict(width=0), name="10th–90th percentile", hoverinfo="skip"))
    real.add_trace(go.Scatter(x=years, y=[opt.initial_endowment_m]+y.median_real_endowment_m.tolist(),
                              mode="lines+markers", line=dict(color=BLUE, width=2.7), name="Median real wealth"))
    real.add_hline(y=opt.initial_endowment_m, line=dict(dash="dash", color=ORANGE, width=1.4))
    plot_layout(real, "Endowment purchasing power", y_label="Real endowment ($M)")
    st.plotly_chart(real, use_container_width=True, key="wealth_chart", config={"displaylogo": False})
    st.markdown("<div class='chart-caption'>Inflation-adjusted endowment value. The dashed reference is the initial real principal.</div>", unsafe_allow_html=True)

left, right = st.columns(2, gap="medium")
with left:
    # Funding-capacity coverage is different from R2 eligible-liquid-assets coverage.
    coverage_data = a.groupby("year")["payout_liquidity_coverage_ratio"]
    med = coverage_data.median()
    p10 = coverage_data.quantile(.10)
    liq = go.Figure()
    liq.add_trace(go.Scatter(x=med.index, y=med.to_numpy(), name="Median",
                             mode="lines+markers", line=dict(color=BLUE, width=2.7)))
    liq.add_trace(go.Scatter(x=p10.index, y=p10.to_numpy(), name="10th percentile",
                             mode="lines+markers", line=dict(color=TEAL, width=2.1)))
    liq.add_hline(y=1.0, line=dict(color=ORANGE, dash="dash", width=1.5))
    plot_layout(liq, "Payout funding coverage over time", y_label="Funding capacity / payout (×)")
    st.plotly_chart(liq, use_container_width=True, key="coverage_chart", config={"displaylogo": False})
    st.markdown("<div class='chart-caption'>Funding capacity ÷ planned payout at each annual deadline. Orange 1× line means enough cash can be raised to pay in full.</div>", unsafe_allow_html=True)

with right:
    short = go.Figure()
    short.add_trace(go.Bar(x=y.year, y=y.mean_unpaid_payout_m,
                           name="Mean unpaid payout", marker_color=BLUE,
                           hovertemplate="%{x}: $%{y:.3f}M<extra></extra>"))
    ymax = max(.1, float(y.mean_unpaid_payout_m.max()) * 1.25)
    plot_layout(short, "Unpaid payout across all paths", y_label="Average annual shortfall ($M)")
    short.update_yaxes(range=[0, ymax])
    st.plotly_chart(short, use_container_width=True, key="short_chart", config={"displaylogo": False})
    st.markdown("<div class='chart-caption'>Average unpaid amount across all simulation paths, including zero-shortfall paths.</div>", unsafe_allow_html=True)

# Requested detail area; avoid duplicating the earnings-plus-gifts ratio measure.
with st.expander("▾ Explore risk measures", expanded=False):
    eg = a["earnings_gifts_coverage_gap"]
    eo = a["return_coverage_shortfall_amount"]
    positive_eg = eg[eg > 1e-10]
    positive_eo = eo[eo > 1e-10]
    positive_short = a.loc[a.payout_shortfall_amount > 1e-10, "payout_shortfall_amount"]
    positive_support = a.loc[a.payout_support_gap > 1e-10, "payout_support_gap"]
    table = pd.DataFrame([
        ["Earnings + gifts gap — when one occurs", money(positive_eg.mean()) if len(positive_eg) else "$0.00M", "Planned spending exceeds current-year investment gain + new gifts"],
        ["Earnings-only gap — when one occurs", money(positive_eo.mean()) if len(positive_eo) else "$0.00M", "Planned spending exceeds investment gain alone"],
        ["Years with earnings + gifts gap", pct((eg > 1e-10).mean()), "Share of all path-years with an earnings-and-gifts coverage gap"],
        ["Payout-funding shortfall — when one occurs", money(positive_short.mean()) if len(positive_short) else "None observed", "Average unpaid distribution, conditional on a shortfall"],
        ["Years with unpaid payout", pct((a.payout_shortfall_amount > 1e-10).mean()), "Share of simulated years with any unmet scheduled payout"],
        ["Funding coverage — minimum path median", f"{cov:.2f}×", "Median across paths of the lowest yearly funding capacity / planned payout"],
        ["Support gap — when one occurs", money(positive_support.mean()) if len(positive_support) else "None observed", "Amount by which the payout falls below the R2 benchmark support need"],
        ["Real payout cut greater than 5%", pct(m["probability_real_payout_cut"]), "Chance of at least one year-over-year real payout decline exceeding 5%"],
        ["Purchasing-power Expected Shortfall (95%)", pct(m["purchasing_power_expected_shortfall_pct_initial"]), "Mean terminal real-principal loss in worst 5% of paths, relative to starting assets"],
    ], columns=["Measure", "Result", "Meaning"])
    st.dataframe(table, use_container_width=True, hide_index=True, height=354)
    st.caption("Earnings-only and earnings-plus-gifts gaps are accounting sustainability diagnostics, not funding failures. Investment gains can be unrealized; cash funding is assessed separately.")

with st.expander("▾ Investment returns and annual calculation details", expanded=False):
    st.markdown(f"**Five-year investment CAGR:** median **{ret['median_cagr']:.2%}**, mean **{ret['mean_cagr']:.2%}**, 5th–95th percentile **{ret['p05_cagr']:.2%} to {ret['p95_cagr']:.2%}**")
    fig_ret = go.Figure(go.Histogram(x=r["return_by_path"].five_year_cagr*100, nbinsx=42,
                                     marker_color=BLUE, name="Simulated paths"))
    fig_ret.add_vline(x=100*ret["median_cagr"], line=dict(color=ORANGE, dash="dash"))
    plot_layout(fig_ret, "Distribution of annualized five-year investment returns",
                y_label="Number of paths", x_label="Annualized investment return (%)")
    st.plotly_chart(fig_ret, use_container_width=True, key="return_hist", config={"displaylogo": False})
    annual_view = y[["year", "mean_investment_return", "mean_gifts_m", "mean_planned_payout_m",
                     "mean_actual_payout_m", "mean_unpaid_payout_m", "mean_earnings_gifts_gap_m",
                     "median_liquidity_coverage_x", "median_real_endowment_m"]].copy()
    annual_view.columns = ["Year", "Mean return", "Mean gifts ($M)", "Planned ($M)",
                           "Actual ($M)", "Unpaid ($M)", "E + G gap ($M)",
                           "Median funding (×)", "Median real assets ($M)"]
    st.dataframe(annual_view.style.format({
        "Mean return": "{:.2%}",
        **{c: "{:,.2f}" for c in annual_view.columns if "($M)" in c or "(×)" in c},
    }), hide_index=True, use_container_width=True)
    st.caption("Mean returns are simple averages across paths for each year. Five-year CAGR is compounded within each path before aggregating.")

with st.expander("▾ Method, formulas, and assumptions", expanded=False):
    st.markdown("**Planned payout — R2 spending rule**")
    st.latex(r"P_t^{plan}=\min\left(0.05E_t,\max\left(0.03E_t,\,s\,\frac{E_t+E_{t-1}+E_{t-2}}{3}\right)\right)")
    st.markdown("**Cash-funding capacity and actual payout**")
    st.latex(r"F_t=\max\left(0,\text{cash at payout date}+\text{net eligible sales}-\text{reserves}-\text{priority obligations}\right)")
    st.latex(r"P_t^{actual}=\min(P_t^{plan},F_t)")
    st.markdown("**Earnings + gifts coverage (diagnostic, not cash)**")
    st.latex(r"Gap_t^{E+G}=\max(0,P_t^{plan}-InvestmentGain_t-Gifts_t)")
    st.caption("Gifts are already credited into cash in the funding model: never add them twice. Net eligible sales have costs deducted. The baseline assumes annual payment timing, unrestricted gifts, no capital calls, no protected reserves, and no borrowing. The 40% R1 and 3× R2 checks are monitoring thresholds, not a cap applied to payouts.")

st.markdown("<div class='section-label'>Download calculation results</div>", unsafe_allow_html=True)
d1, d2, d3 = st.columns(3, gap="small")
with d1:
    st.download_button("Five-year summary (CSV)", y.to_csv(index=False).encode("utf-8"),
                       file_name="endowment_simple_annual_summary.csv", mime="text/csv", use_container_width=True)
with d2:
    st.download_button("Path investment returns (CSV)", r["return_by_path"].to_csv(index=False).encode("utf-8"),
                       file_name="endowment_simple_path_returns.csv", mime="text/csv", use_container_width=True)
with d3:
    st.download_button("Path-year calculations (CSV)", a.to_csv(index=False).encode("utf-8"),
                       file_name="endowment_simple_path_year.csv", mime="text/csv", use_container_width=True)

st.markdown("""
<div class="footnote">Baseline research model: the results depend on R1 historical asset data, R2 benchmark assumptions,
annual cash-funding approximations, and modeled asset sale eligibility. A 0% simulated shortfall rate is not proof of zero real-world risk.</div>
""", unsafe_allow_html=True)
