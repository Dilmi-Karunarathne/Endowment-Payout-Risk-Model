"""Simple baseline-only Endowment Payout Risk dashboard. Run: streamlit run app.py"""
import json
from dataclasses import asdict

import plotly.graph_objects as go
import streamlit as st

from r1_model import STRATEGIES
from simple_analysis import (
    BaselineOptions, HORIZON, SEED, BLOCK_QUARTERS,
    INITIAL_REGIME, PAYOUT_DEADLINE_MONTHS, run_baseline,
)

st.set_page_config(page_title="Endowment Payout Risk | Simple", page_icon="🎓", layout="wide")
st.markdown("""
<style>
.block-container { max-width: 1200px; padding-top: 2rem; }
h1 {color: #14345e; letter-spacing: -0.02em;}
[data-testid="stSidebar"] { background-color: #f4f7fb; }
[data-testid="stMetric"] { border: 1px solid #d8e4f0; padding: 12px 15px; border-radius: 12px; }
</style>""", unsafe_allow_html=True)

st.title("Endowment Payout Risk")
st.caption("Simple five-year baseline simulation · R1 investment portfolios + R2 institutional benchmarks · v11 cash-first funding")

with st.sidebar:
    st.header("1. Choose your inputs")
    with st.form("one_simulation"):
        institution = st.selectbox("Institution", ["Private", "Public"], index=0)
        profile = st.selectbox("R2 benchmark profile", ["Low", "Base", "High"], index=1,
            help="R2 Low/Base/High are marginal percentiles, not coherent worst/best cases.")
        strategy = st.selectbox("R1 portfolio", STRATEGIES, index=STRATEGIES.index("HRP"))
        initial = st.number_input("Starting endowment ($ million)", min_value=1.0, max_value=10000.0,
                                  value=150.0, step=10.0)
        paths = st.selectbox("Monte Carlo paths", [100, 500, 1000, 5000], index=2,
            format_func=lambda x: f"{x:,}")
        submitted = st.form_submit_button("Run one simulation", type="primary", use_container_width=True)
    st.caption("The projection is fixed at 5 years (2027–2031). No stress tests or strategy comparisons.")
    with st.expander("Fixed assumptions (read-only)"):
        st.markdown(f"""- Initial R1 allocation regime: **{INITIAL_REGIME}**
- Historical return method: **joint R1 asset/inflation bootstrap**
- Historical block: **{BLOCK_QUARTERS} quarters**; random seed **{SEED}**
- Spending rule: **R2 three-year average, 3%–5% collar**
- Payout funding: **cash first, then eligible asset sales**
- Asset-sale deadline: **{PAYOUT_DEADLINE_MONTHS} months**
- Gifts: **assumed liquid and unrestricted**
- Extra reserves, cash needs and capital calls: **zero**
- Confidence for purchasing-power ES: **95%**
- R1 40% / R2 3× liquidity tests: **monitoring only**
""")

if submitted:
    settings = BaselineOptions(institution, profile, strategy, float(initial), int(paths))
    with st.spinner(f"Running {paths:,} five-year paths. This may take a little while…"):
        try:
            st.session_state.simple_result = run_baseline(settings)
        except Exception as exc:
            st.session_state.pop('simple_result', None)
            st.error(f"The simulation could not finish: {exc}")

if 'simple_result' not in st.session_state:
    st.info("Choose your institution, portfolio and number of paths, then click **Run one simulation**.")
    st.markdown("""
**What this model does**

1. Simulates returns for the selected R1 portfolio using historical asset-market blocks.
2. Adds R2 endowment gifts and calculates the planned payout from the spending rule.
3. Checks real cash funding using cash and only assets saleable within three months, net of sale costs.
4. Shows investment returns, the funded payouts, liquidity, and the endowment's purchasing power.

**No stress controls, scenario comparisons, advanced settings, or extra runs.**
""")
    st.stop()

r = st.session_state.simple_result
opt, inst = r['options'], r['institutional']
m, y, ret = r['metrics'], r['yearly'], r['return_stats']
st.success(f"Simulation complete · {opt.institution}/{opt.profile} · {opt.strategy} · ${opt.initial_endowment_m:,.0f}M · {opt.paths:,} paths")
st.caption(f"R2 annual planned spending rate: {inst.effective_spending_rate:.2%} | R2 annual endowment gift rate: {inst.gift_rate:.2%} | 5-year horizon | Fixed seed 42")
if not 101 <= opt.initial_endowment_m <= 250:
    st.warning("R2 percentages were estimated for $101M–$250M university endowments. The selected starting value extrapolates beyond that cohort.")

st.subheader("2. Main results")
k1,k2,k3,k4,k5 = st.columns(5)
k1.metric("Investment CAGR", f"{ret['median_cagr']:.2%}")
k2.metric("Payout shortfall", f"{m['probability_at_least_one_shortfall']:.1%}")
k3.metric("Principal erosion", f"{m['probability_real_corpus_erosion']:.1%}")
k4.metric("Support gap", f"{m['probability_any_support_gap']:.1%}")
k5.metric("Real ES (95%)", f"{m['purchasing_power_expected_shortfall_pct_initial']:.1%}")
st.caption("Risk frequencies are the percentage of paths with at least one affected year. ES is the average terminal real-principal loss in the worst 5% of paths, as a share of starting assets.")

st.subheader("3. Five-year results")
view = y[[
    'year','mean_investment_return','mean_gifts_m','mean_planned_payout_m',
    'mean_actual_payout_m','mean_unpaid_payout_m','mean_earnings_gifts_gap_m',
    'median_liquidity_coverage_x','median_real_endowment_m'
]].copy()
view.columns = ['Year','Mean investment return','Mean gifts ($M)','Mean planned payout ($M)',
    'Mean actual payout ($M)','Mean unpaid payout ($M)','Mean earnings + gifts gap ($M)',
    'Median liquidity coverage (×)','Median real endowment ($M)']
st.dataframe(view.style.format({
    'Mean investment return': '{:.2%}',
    **{col: '{:,.2f}' for col in view.columns if '($M)' in col or '(×)' in col}
}), hide_index=True, use_container_width=True)
st.caption("Mean dollar gaps are averaged across *all* paths, including those with zero gap. A positive earnings-and-gifts gap is not necessarily an unpaid payout.")


def draw_band(data, name, lo, hi, title, reference=None):
    fig = go.Figure()
    x = data['year'].tolist()
    fig.add_trace(go.Scatter(x=x, y=data[hi], mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=x, y=data[lo], mode='lines', fill='tonexty',
        fillcolor='rgba(60,119,190,.15)', line=dict(width=0),
        name='10th–90th percentile', hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=x, y=data[name], mode='lines+markers', name='Median',
        line=dict(color='#245e9b', width=3)))
    if reference is not None:
        fig.add_hline(y=reference, line=dict(color='#bb8134', dash='dash'),
                      annotation_text='Starting principal', annotation_position='top left')
    fig.update_layout(title=title, template='plotly_white', height=320,
        yaxis_title='$ million (starting-year purchasing power)',
        xaxis_title='Year', legend=dict(orientation='h', y=1.14), margin=dict(l=10,r=10,b=10,t=58))
    return fig

st.subheader("4. What happens over five years?")
left,right=st.columns(2)
with left:
    st.plotly_chart(draw_band(y, 'median_real_endowment_m','real_endowment_p10_m',
        'real_endowment_p90_m','Endowment purchasing power', opt.initial_endowment_m),use_container_width=True)
with right:
    st.plotly_chart(draw_band(y,'median_real_payout_m','real_payout_p10_m',
        'real_payout_p90_m','Annual payout purchasing power'),use_container_width=True)

st.subheader("5. Payout funding and investment returns")
left,right = st.columns(2)
with left:
    bar=go.Figure()
    bar.add_trace(go.Bar(x=y.year, y=y.mean_planned_payout_m,name='Planned',marker_color='#7098c6'))
    bar.add_trace(go.Bar(x=y.year, y=y.mean_actual_payout_m,name='Actual',marker_color='#2a816d'))
    bar.update_layout(title='Planned vs actual annual payout', barmode='group',template='plotly_white',height=310,yaxis_title='$ million',xaxis_title='Year')
    st.plotly_chart(bar, use_container_width=True)
    st.caption(f"Payout funding gap: average annual unpaid payout ${y.mean_unpaid_payout_m.mean():.3f}M. The actual payout is constrained by eligible cash and sales.")
with right:
    hist=go.Figure(go.Histogram(x=r['return_by_path'].five_year_cagr*100, nbinsx=40,
        marker_color='#4978a8', name='Paths'))
    hist.add_vline(x=ret['median_cagr']*100,line=dict(dash='dash',color='#b77723'))
    hist.update_layout(title='Five-year annualized investment returns',template='plotly_white',height=310,
        xaxis_title='Annualized return (%)', yaxis_title='Number of paths')
    st.plotly_chart(hist,use_container_width=True)
    st.caption(f"Median {ret['median_cagr']:.2%} | 5th–95th percentile {ret['p05_cagr']:.2%} to {ret['p95_cagr']:.2%}. Investment returns exclude gifts and payouts.")

with st.expander('View the payout-funding calculation and important limits'):
    st.latex(r'P_t^{planned}=\min(0.05E_t,\max(0.03E_t,s(E_t+E_{t-1}+E_{t-2})/3))')
    st.latex(r'F_t=\max(0,\text{cash at payout date}+\text{net eligible sale capacity}-\text{reserves}-\text{senior obligations})')
    st.latex(r'P_t^{actual}=\min(P_t^{planned},F_t)')
    st.latex(r'G_t^{E+G}=\max(0,P_t^{planned}-I_t-G_t)')
    st.markdown("""**Important:** Market gains on securities are not immediately treated as cash. Gifts enter the cash sleeve once, and only assets that can be sold within the three-month payout deadline are eligible for sale. Estimated sale costs are deducted once.

This is a baseline research model, not a real institution's cash forecast. It assumes unrestricted gifts, annual payout timing, no separate management-fee schedule, and no capital calls or protected reserve. R2 Low/High are marginal percentiles, not coherent worst/best-case institutions. Zero simulated failures does not imply no real-world funding risk.""")

st.subheader('6. Download your results')
a,b,c = st.columns(3)
with a:
    st.download_button('Five-year summary (CSV)', y.to_csv(index=False).encode(),
                       file_name='simple_annual_summary.csv',mime='text/csv',use_container_width=True)
with b:
    st.download_button('Investment returns by path (CSV)',
        r['return_by_path'].to_csv(index=False).encode(),file_name='simple_path_returns.csv',
        mime='text/csv',use_container_width=True)
with c:
    st.download_button('All path-year calculations (CSV)',
        r['annual_detail'].to_csv(index=False).encode(),file_name='simple_path_year_detail.csv',
        mime='text/csv',use_container_width=True)

st.caption('Built from the uploaded v11 model. The underlying R1 investment and liquidity methods and R2 benchmark dataset have not been replaced.')
