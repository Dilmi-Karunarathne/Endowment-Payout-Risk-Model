"""Single-run, baseline-only endowment payout risk dashboard (gift growth + 5,000–10,000 paths v7).
Run: python -m streamlit run app.py
All monetary quantities are in USD millions.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from r1_model import STRATEGIES
from dashboard_contract import validate_result_schema
from simple_analysis import (
    BaselineOptions, HORIZON, SEED, BLOCK_QUARTERS,
    INITIAL_REGIME, PAYOUT_DEADLINE_MONTHS, run_baseline, strategy_cash_requirements,
)

st.set_page_config(page_title="Endowment Payout Risk | Simple", page_icon="🎓", layout="wide")
st.markdown("""
<style>
.block-container {max-width: 1250px; padding-top: 1.5rem; padding-bottom: 2rem;}
h1, h2, h3 {letter-spacing: -.025em;}
[data-testid="stMetric"] {border:1px solid #314764; border-radius:12px; padding:15px; background:#182a41;}
[data-testid="stMetricLabel"] {color:#d4e2f7;}
[data-testid="stMetricValue"] {color:#ffffff; font-weight:750;}
[data-testid="stSidebar"] {background:#111d30;}
[data-testid="stExpander"] {border-color:#344965; border-radius:12px;}
hr {border-color:#344965;}
</style>
""", unsafe_allow_html=True)

CHART_BG = '#15243a'
FIG_FONT = '#e6eefb'
NAVY_BLUE = '#76b8ff'
RED = '#ff858b'
TEAL = '#69d5bd'
ORANGE = '#f7ae62'


def finalize_fig(fig, *, title=None, ylabel=None, height=355):
    fig.update_layout(
        title=title, template='plotly_dark', paper_bgcolor=CHART_BG,
        plot_bgcolor=CHART_BG, font=dict(color=FIG_FONT),
        height=height, margin=dict(l=18, r=18, t=65, b=36),
        legend=dict(orientation='h', y=1.12),
        xaxis=dict(gridcolor='#2e4460', zerolinecolor='#6a819e'),
        yaxis=dict(title=ylabel, gridcolor='#2e4460', zerolinecolor='#6a819e'),
    )
    return fig


st.title('Endowment Payout Risk Model')
st.caption('One five-year simulation · R1 investment returns · R2 spending policy · Cash-first payouts · New gifts ring-fenced')

# Streamlit Cloud can retain st.session_state when the source changes versions.
# The v4 result does not contain v5 asset-pool summary columns; do not render it.
if 'sim_result' in st.session_state:
    valid, reason = validate_result_schema(st.session_state['sim_result'])
    if not valid:
        st.session_state.pop('sim_result', None)
        st.session_state['schema_reset_reason'] = reason
if 'schema_reset_reason' in st.session_state:
    st.warning(st.session_state.pop('schema_reset_reason'))

with st.sidebar:
    st.header('Run a simulation')
    with st.form('run_baseline'):
        institution = st.selectbox('Institution', ['Private', 'Public'])
        profile = st.selectbox('R2 benchmark profile', ['Low', 'Base', 'High'], index=1,
            help='The R2 profiles combine separate parameter percentiles; Low and High do not necessarily mean worst or best.')
        strategy = st.selectbox('R1 investment strategy', STRATEGIES, index=STRATEGIES.index('HRP'))
        initial = st.number_input('Starting endowment ($M)', min_value=1.0, max_value=10000.0,
            value=150.0, step=10.0)
        paths = st.selectbox('Monte Carlo paths', [5000, 10000], index=0,
            format_func=lambda v: f'{v:,}')
        submitted = st.form_submit_button('Run simulation', type='primary', use_container_width=True)
    st.caption('Fixed horizon: 2027–2031. Choose 5,000 or 10,000 paths; no stress or batch runs.')
    r1_policy_preview = strategy_cash_requirements(strategy)
    st.caption(f"R1 cash inputs for {strategy}: "
        f"{r1_policy_preview['annual_capital_call_rate']:.2%} annual calls (2027–2029); "
        f"{r1_policy_preview['reserve_years_of_planned_payout']:.2f} years of payout held as reserve.")
    with st.expander('Fixed assumptions'):
        st.markdown(f'''- Initial allocation regime: **{INITIAL_REGIME}**
- Joint asset/inflation block bootstrap: **{BLOCK_QUARTERS} quarters**
- Random seed: **{SEED}**
- R2 three-year-average spending rule, **3% floor / 5% ceiling**
- Cash-first funding: cash then eligible R1 asset sales within **{PAYOUT_DEADLINE_MONTHS} months**
- **100% of new endowment gifts are nonspendable** during this projection (conservative assumption, not established by R2)
- **Gift investment growth:** gifts are added at **year-end**, and earn asset-level R1 investment returns from the **following year**; those returns remain in the restricted gift pool. Neither the gifts nor their investment earnings can fund payouts
- Endowment results distinguish **total assets**, **existing payout-eligible pool** (subject to liquidity), and **restricted gift pool**
- Initial pre-existing endowment holdings are treated as eligible subject to R1 sale restrictions
- **R1 strategy-specific capital-call proxy:** {r1_policy_preview['annual_capital_call_rate']:.2%} of beginning total endowment assets per year in 2027–2029 (R1 scenario proxy, **not verified normal-year commitments**)
- **R1 payout cash reserve:** {r1_policy_preview['reserve_years_of_planned_payout']:.2f} years of the current planned payout (protected when funding; R2 must confirm actual policy)
- **No extra public-market restriction** beyond R1's sale timings and normal/stressed costs
- Other annual endowment cash obligations: **none specified**; no borrowing, extra flat forced-sale haircut, or separate private-investment distributions modeled
- 95% Expected Shortfall uses the **worst 5% of terminal real-asset losses**
- Management fees, intra-year cash timing and donor-specific restrictions are not fully modeled.
''')

if submitted:
    options = BaselineOptions(institution, profile, strategy, float(initial), int(paths))
    with st.spinner(f'Running {paths:,} five-year Monte Carlo paths…'):
        try:
            new_result = run_baseline(options)
            valid, reason = validate_result_schema(new_result)
            if not valid:
                raise RuntimeError(reason)
            st.session_state.sim_result = new_result
        except Exception as exc:
            st.session_state.pop('sim_result', None)
            st.error(f'The simulation did not finish: {exc}')

if 'sim_result' not in st.session_state:
    st.info('Choose the five inputs on the left and select **Run simulation** to see the payout risk measures.')
    st.markdown('''The report contains exactly four headline payout risk measures, a **payout shortfall deviation chart**, the **existing real purchasing-power chart**, and **year-by-year gap tables**. Investment returns and full calculation exports remain available below the main report.''')
    st.stop()

r = st.session_state.sim_result
opt, inst, m, annual, returns = (r['options'], r['institutional'], r['metrics'],
                                  r['yearly'], r['return_stats'])

st.caption(f'**{opt.institution} / {opt.profile}** · {opt.strategy} · '
           f'${opt.initial_endowment_m:,.0f}M beginning assets · '
           f'{opt.paths:,} paths × {HORIZON} years · '
           f'R2 spending rate {inst.effective_spending_rate:.2%} · '
           f'gift rate {inst.gift_rate:.2%} · '
           f'R1 capital-call proxy {r["r1_cash_policy"]["annual_capital_call_rate"]:.2%} (first 3y) · '
           f'payout reserve {r["r1_cash_policy"]["reserve_years_of_planned_payout"]:.2f}y')
if not 101 <= opt.initial_endowment_m <= 250:
    st.warning('R2 rates were estimated for the $101M–$250M endowment cohort. Your starting amount extrapolates beyond that range.')

st.subheader('Payout risk · Four headline measures')
c1,c2,c3,c4 = st.columns(4)
c1.metric('Frequency of payout shortfall', f"{m['probability_at_least_one_shortfall']:.1%}",
          help='Share of complete five-year paths with at least one year where actual payout < planned payout.')
c2.metric('Real principal erosion risk', f"{m['probability_real_corpus_erosion']:.1%}",
          help='Share of paths where inflation-adjusted assets drop below the initial real endowment at least once.')
c3.metric('Institutional support gap risk', f"{m['probability_any_support_gap']:.1%}",
          help='Share of paths with at least one year actual payout is below R2 benchmark required support.')
c4.metric('Purchasing-power ES (95%)', f"{m['purchasing_power_expected_shortfall_pct_initial']:.1%}",
          help='Average positive terminal real-asset loss in the worst 5% of paths, divided by initial endowment.')
st.caption('The real principal erosion headline uses **total endowment wealth**, including restricted gifts. '
           'Spendable-only erosion is shown separately below. '
           'All three probabilities are **path-level risks over five years**. '
           'ES is the average **terminal inflation-adjusted endowment loss** in the worst 5% of paths, '
           'expressed as a fraction of the initial endowment; it is not a shortfall in the annual payout.')

st.subheader('Payout funding and purchasing power')
left, right = st.columns(2)

with left:
    # Deviations are signed: actual - planned <= 0; any unpaid payout plots below zero.
    dev = go.Figure()
    dev.add_trace(go.Bar(x=annual['year'], y=annual['mean_shortfall_deviation_m'],
        marker_color=RED, name='Mean payout deviation',
        hovertemplate='%{x}: %{y:.3f} $M<extra>Mean (actual − planned)</extra>'))
    dev.add_trace(go.Scatter(x=annual['year'], y=annual['worst_shortfall_deviation_m'],
        mode='markers+lines', marker=dict(size=8, color=ORANGE),
        line=dict(color=ORANGE, dash='dot'),
        name='Worst path deviation',
        hovertemplate='%{x}: %{y:.3f} $M<extra>Worst path</extra>'))
    dev.add_hline(y=0, line_dash='dash', line_color='#aebfd2')
    if abs(annual['worst_shortfall_deviation_m'].min()) < 1e-10:
        dev.add_annotation(text='No unpaid payouts in sampled paths', x=.5, y=.52,
            xref='paper', yref='paper', showarrow=False, font=dict(color=TEAL, size=14))
        dev.update_yaxes(range=[-.10, .06])
    finalize_fig(dev, title='Payout-funding shortfall deviation',
        ylabel='Actual − planned payout ($M)')
    dev.update_xaxes(title_text='Projection year', dtick=1)
    st.plotly_chart(dev, use_container_width=True)
    st.caption('A negative deviation means a portion of the scheduled payout went unpaid. '
               'Mean and worst-path deviations are shown by year; **$0M means fully funded**.')

with right:
    years = [0]+list(range(1,HORIZON+1))
    original = opt.initial_endowment_m
    lower = [original]+annual['real_endowment_p10_m'].tolist()
    upper = [original]+annual['real_endowment_p90_m'].tolist()
    mid = [original]+annual['median_real_endowment_m'].tolist()
    purchasing = go.Figure()
    purchasing.add_trace(go.Scatter(x=years,y=upper,mode='lines',line=dict(width=0),
        showlegend=False,hoverinfo='skip'))
    purchasing.add_trace(go.Scatter(x=years,y=lower,mode='lines',line=dict(width=0),
        fill='tonexty',fillcolor='rgba(118,184,255,.22)',name='10th–90th percentile',hoverinfo='skip'))
    purchasing.add_trace(go.Scatter(x=years,y=mid,mode='lines+markers',
        line=dict(color=NAVY_BLUE,width=3),name='Median real endowment'))
    purchasing.add_hline(y=original,line=dict(color=ORANGE,dash='dash'),
        annotation_text='Initial purchasing power',annotation_position='top left')
    finalize_fig(purchasing,title='Endowment purchasing power',ylabel='Real assets ($M)')
    purchasing.update_xaxes(title_text='Projection year',dtick=1)
    st.plotly_chart(purchasing,use_container_width=True)
    st.caption('Median and 10th–90th percentile real endowment value after investment returns, gifts and payouts. '
               'The orange line marks the initial endowment in starting-year dollars.')

st.subheader('Where is the endowment wealth?')
st.caption('Total endowment = **payout-eligible existing-asset pool + restricted gift pool**. '
    'The existing-asset pool is *eligible subject to sale restrictions*; it is not all immediately available cash. '
    'Under this conservative baseline, newly received gifts and their future investment gains remain restricted for all five years.')
ending = annual.iloc[-1]
col_total, col_spend, col_gift = st.columns(3)
col_total.metric('Total endowment · year 5', f"${ending['mean_total_assets_m']:,.1f}M",
    help='Mean nominal total endowment across paths at the end of year 5.')
col_spend.metric('Existing / payout-eligible pool · year 5', f"${ending['mean_spendable_assets_m']:,.1f}M",
    help='Mean nominal existing-asset pool; sales still require R1 liquidity eligibility and execution costs.')
col_gift.metric('Restricted gift pool · year 5', f"${ending['mean_restricted_gift_assets_m']:,.1f}M",
    help='Mean nominal gifts plus their investment performance, ring-fenced from payouts throughout the projection.')
st.caption('These three year-5 amounts are **means**, not medians, so the two components add exactly to total. '
    'They are nominal dollars; the graph and table below also show inflation-adjusted values.')

b = go.Figure()
years = [0] + list(range(1, HORIZON+1))
b.add_trace(go.Scatter(x=years, y=[opt.initial_endowment_m]+annual['mean_real_total_assets_m'].tolist(),
    mode='lines+markers', line=dict(color=NAVY_BLUE, width=3), name='Total endowment'))
b.add_trace(go.Scatter(x=years, y=[opt.initial_endowment_m]+annual['mean_real_spendable_assets_m'].tolist(),
    mode='lines+markers', line=dict(color=TEAL, width=3), name='Existing / payout-eligible pool'))
b.add_trace(go.Scatter(x=years, y=[0.0]+annual['mean_real_restricted_gift_assets_m'].tolist(),
    mode='lines+markers', line=dict(color=ORANGE, width=3), name='Restricted gifts + their returns'))
b.add_hline(y=opt.initial_endowment_m, line_dash='dot', line_color='#b9c1ce')
finalize_fig(b, title='Mean real endowment by asset pool', ylabel='Purchasing power ($M)', height=395)
b.update_xaxes(title_text='Projection year', dtick=1)
st.plotly_chart(b, use_container_width=True)
st.caption('This **mean-value decomposition** reconciles each year: total = existing asset pool + restricted gift pool. '
    'The earlier purchasing-power chart shows the *median* total and its 10th–90th percentile range; '
    'separately calculated medians of components do not necessarily add to the median total.')

st.info(f"**Spendable-asset purchasing-power erosion:** {r['probability_spendable_real_erosion']:.1%} "
    'of paths fall below the initial $'
    f"{opt.initial_endowment_m:,.0f}M in **real existing-asset value** at least once. "
    'Compare with the total-wealth real principal erosion headline above; restricted gifts can mask '
    'a declining pool that is actually eligible for payouts.')

pool_table = annual[[
    'year', 'mean_total_assets_m', 'mean_spendable_assets_m', 'mean_restricted_gift_assets_m',
    'mean_real_total_assets_m', 'mean_real_spendable_assets_m', 'mean_real_restricted_gift_assets_m'
]].copy()
pool_table.columns = [
    'Year', 'Total nominal ($M)', 'Existing pool nominal ($M)', 'Gift pool nominal ($M)',
    'Total real ($M)', 'Existing pool real ($M)', 'Gift pool real ($M)'
]
st.dataframe(pool_table.style.format({c: '${:,.2f}' for c in pool_table.columns if '($M)' in c}),
    hide_index=True, use_container_width=True)

st.caption('**Gift investment income:** the *Gift-pool investment gain* in the table below is earned on '
    'the opening restricted gift balance. New gifts are credited after the annual return; '
    'therefore gifts received in 2027 earn investment returns beginning in 2028.')

with st.expander('How each pool changes · investment gains, restricted gifts and asset sales'):
    rtable=annual[[
        'year', 'mean_spendable_investment_gain_m','mean_restricted_gift_investment_gain_m',
        'mean_gifts_m','mean_actual_payout_m', 'mean_net_asset_sales_m', 'mean_asset_sale_cost_m'
    ]].copy()
    rtable.columns=['Year','Existing-pool investment gain ($M)','Gift-pool investment gain ($M)',
        'New restricted gifts ($M)','Actual payout ($M)','Net eligible asset sales ($M)',
        'Liquidation costs ($M)']
    st.dataframe(rtable.style.format({c: '${:,.3f}' for c in rtable.columns if '($M)' in c}),
        hide_index=True,use_container_width=True)
    st.markdown('**Yearly accounting:** Existing pool ends at opening existing assets + existing-pool '
        'investment gain + other changes − actual payout − other endowment cash spending − liquidation cost. '
        'Restricted gift pool ends at opening gift pool + its investment gain + new gifts. '
        '**Sales convert investments into cash; sales proceeds are not additional investment income** and '
        'should not be deducted again from the endowment.')
    st.latex(r'E_t^{total}=E_t^{existing}+E_t^{restricted}')
    st.latex(r'G_{t}^{end}=G_{t}^{begin}(1+r_{t}^{G,net})+NewGifts_t')
    st.caption('Gift timing: gifts received in 2027 join the restricted pool at the end of 2027; '
               'they earn their first investment return in 2028. Here r_G,net is the actual '
               'return on the segregated gift holdings after modeled rebalancing costs; '
               'gift income is reinvested, not available for payouts.')
    st.latex(r'E_t^{existing}=E_{t-1}^{existing}+R_t^{existing}-P_t^{actual}-C_t^{liquidation}')
    st.caption('The existing-pool formula above omits other endowment changes and other obligations, '
        'both fixed at zero for this simple baseline; R denotes dollar investment gain net of rebalancing.')

with st.expander('R1 cash reserve and private-asset capital calls · annual funding detail', expanded=False):
    st.markdown('**R1 provides strategy-scaled modeling proxies**, not audited commitments or an institution-specific reserve policy. '
        'The cash reserve is protected when raising funds, and capital calls receive priority before the annual payout. '
        'Capital calls transfer money into existing PE/VC investments; they are **not an expense or loss of total endowment wealth**. '
        'R1 recommended base capital-call amounts for a three-year period as part of liquidity scenarios; '
        'we use these proxies in this single research baseline at your request.')
    funding_table = annual[[
        'year', 'mean_r1_capital_call_requested_m', 'mean_r1_capital_call_paid_m',
        'mean_r1_capital_call_unpaid_m', 'mean_r1_reserve_target_m',
        'mean_r1_reserve_shortfall_m', 'mean_net_asset_sales_m',
        'mean_asset_sale_cost_m', 'mean_unpaid_payout_m'
    ]].copy()
    funding_table.columns = [
        'Year', 'Capital calls requested ($M)', 'Capital calls funded ($M)',
        'Unfunded capital calls ($M)', 'Protected cash reserve target ($M)',
        'Reserve shortfall ($M)', 'Net asset sales ($M)',
        'Liquidation costs ($M)', 'Unpaid payout ($M)'
    ]
    st.dataframe(funding_table.style.format({c: '${:,.3f}' for c in funding_table.columns if '($M)' in c}),
        hide_index=True, use_container_width=True)
    st.caption('Amounts are annual averages across paths. The reserve is a cash earmark, not a separate cash expense. '
        'R2 3×-payout liquidity is a separate monitored benchmark, not another cash deduction.')

st.subheader('Investment earnings, gifts and institutional support')
st.caption('USD millions. The **existing-pool earnings gap** uses investment gains from assets '
           'that may fund payouts, subject to R1 sale limits. The **total earnings-only gap** '
           'and **earnings + gifts gap** are broader economic benchmarks, not immediate cash. '
           'Averages include zero-gap paths unless marked “when >0”.')

gap_view = annual[[
    'year', 'mean_spendable_earnings_gap_m', 'mean_spendable_earnings_gap_when_positive_m',
    'mean_earnings_only_gap_m', 'mean_earnings_gifts_gap_m',
    'mean_support_gap_when_positive_m'
]].copy()
gap_view.columns = [
    'Year', 'Existing-pool earnings gap — mean ($M)', 'Existing-pool gap — when >0 ($M)',
    'Total earnings gap — mean ($M)', 'Earnings + gifts gap — mean ($M) [context]',
    'Support gap — when >0 ($M)'
]
a = r['annual_detail']
eg = a['earnings_gifts_coverage_gap']
earn_only = a['return_coverage_shortfall_amount']
spendable_gap = a['spendable_earnings_coverage_gap']
support = a['payout_support_gap']
positive_spendable = spendable_gap[spendable_gap > 1e-10]
positive_support = support[support > 1e-10]
gap_view['Year'] = gap_view['Year'].astype(str)
overall_gap = pd.DataFrame([{
    'Year': 'All years',
    'Existing-pool earnings gap — mean ($M)': float(spendable_gap.mean()),
    'Existing-pool gap — when >0 ($M)': float(positive_spendable.mean()) if len(positive_spendable) else 0.0,
    'Total earnings gap — mean ($M)': float(earn_only.mean()),
    'Earnings + gifts gap — mean ($M) [context]': float(eg.mean()),
    'Support gap — when >0 ($M)': float(positive_support.mean()) if len(positive_support) else 0.0,
}])
gap_view = pd.concat([gap_view, overall_gap], ignore_index=True)
st.dataframe(gap_view.style.format({c: '${:,.3f}' for c in gap_view.columns if '($M)' in c}),
    hide_index=True, use_container_width=True)

with st.expander('Interpretation and formulas', expanded=False):
    st.markdown('**Gift restriction:** Each new gift and all investment gains on the separate gift pool '
                'remain nonspendable throughout the five years. This is a conservative research assumption, '
                'not a donor-specific classification supplied by R2. Investment gains may also be unrealized.')
    st.latex(r'G_t^{eligible\ earnings}=\max(0, P_t^{planned}-InvestmentGain_t^{existing})')
    st.latex(r'G_t^{E}=\max(0, P_t^{planned}-InvestmentGain_t)')
    st.latex(r'G_t^{E+G}=\max(0, P_t^{planned}-InvestmentGain_t-EndowmentGifts_t)')
    st.caption('Total earnings includes returns on restricted gifts. Both total earnings and earnings + gifts '
               'are economic comparisons only; gift dollars and their earnings cannot fund payouts.')
    st.latex(r'P_t^{actual}=\min(P_t^{planned},\;\max(0,Cash_{eligible,t}+NetSales_{eligible,t}-Reserve_t-Calls_t-OtherNeed_t))')
    st.latex(r'S_t^{fund}=\max(0, P_t^{planned}-P_t^{actual})')
    st.latex(r'S_t^{support}=\max(0, RequiredSupport_t-P_t^{actual})')
    st.latex(r'L_j=\max\left(0, 1-\frac{E_{j,5}^{real}}{E_0}\right)')
    st.markdown('**ES (95%)** = mean of the highest 5% of the path-level terminal real losses, each relative to initial assets. '
                'Zero losses remain zero; this is **not** a payout-funding ES or the average loss during every bad year.')
    st.markdown('**Institutional support** = R2 operating expenses × R2 required-support ratio. '
                'The benchmark can exceed the spending-rule payout even if the university operating budget is balanced.')

with st.expander('Investment returns and full five-year calculations'):
    st.markdown(f"**Median five-year annualized investment return:** {returns['median_cagr']:.2%}  "
                f"| **Mean:** {returns['mean_cagr']:.2%}  "
                f"| **P5–P95:** {returns['p05_cagr']:.2%} to {returns['p95_cagr']:.2%}")
    view = annual[[
        'year','mean_investment_return','mean_gifts_m','mean_planned_payout_m',
        'mean_actual_payout_m','mean_unpaid_payout_m','median_real_endowment_m'
    ]].copy()
    view.columns = ['Year','Mean investment return','Mean gifts ($M)','Mean planned payout ($M)',
                    'Mean actual payout ($M)','Mean unpaid payout ($M)','Median real assets ($M)']
    st.dataframe(view.style.format({'Mean investment return':'{:.2%}',
        **{name:'${:,.3f}' for name in view.columns if '($M)' in name}}),
        hide_index=True,use_container_width=True)
    st.caption('Investment returns exclude gifts and payouts. Dollar columns are means except real assets, which are medians.')

st.subheader('Download the calculations')
risk_export = pd.DataFrame([
    {'Measure': 'Frequency of payout shortfall',
     'Value': m['probability_at_least_one_shortfall'], 'Unit': 'probability over 5 years'},
    {'Measure': 'Real principal erosion risk',
     'Value': m['probability_real_corpus_erosion'], 'Unit': 'probability over 5 years'},
    {'Measure': 'Existing-asset real erosion risk (excludes new gifts)',
     'Value': r['probability_spendable_real_erosion'], 'Unit': 'probability over 5 years'},
    {'Measure': 'Institutional support gap risk',
     'Value': m['probability_any_support_gap'], 'Unit': 'probability over 5 years'},
    {'Measure': 'Purchasing-power expected shortfall (95%)',
     'Value': m['purchasing_power_expected_shortfall_pct_initial'],
     'Unit': 'fraction of initial endowment'},
    {'Measure': 'Average support gap when positive',
     'Value': float(positive_support.mean()) if len(positive_support) else 0.0,
     'Unit': '$ million per positive-gap year'},
    {'Measure': 'Average existing-pool earnings gap (primary)',
     'Value': float(spendable_gap.mean()), 'Unit': '$ million per simulated year'},
    {'Measure': 'Average total-earnings gap (context)',
     'Value': float(earn_only.mean()), 'Unit': '$ million per simulated year'},
    {'Measure': 'Average earnings + gifts gap (diagnostic)',
     'Value': float(eg.mean()), 'Unit': '$ million per simulated year'},
    {'Measure': 'R1 strategy-specific annual capital call rate (years 1-3)',
     'Value': r['r1_cash_policy']['annual_capital_call_rate'], 'Unit': 'fraction of beginning total endowment'},
    {'Measure': 'R1 cash reserve target (years of planned payout)',
     'Value': r['r1_cash_policy']['reserve_years_of_planned_payout'], 'Unit': 'payout years'},
    {'Measure': 'Mean annual capital calls requested in 2027',
     'Value': float(a[a.year == a.year.min()].capital_call.mean()), 'Unit': '$ million'},
    {'Measure': 'Mean restricted gift assets at horizon end',
     'Value': float(a[a.year == a.year.max()].restricted_gift_assets_end.mean()),
     'Unit': '$ million'},
])
a,b,c,d = st.columns(4)
with a:
    st.download_button('Risk summary (CSV)', risk_export.to_csv(index=False).encode(),
        file_name='payout_risk_headlines.csv',mime='text/csv', use_container_width=True)
with b:
    st.download_button('Annual summary (CSV)', annual.to_csv(index=False).encode(),
        file_name='payout_risk_annual_summary.csv',mime='text/csv', use_container_width=True)
with c:
    st.download_button('Investment returns (CSV)', r['return_by_path'].to_csv(index=False).encode(),
        file_name='investment_returns_by_path.csv',mime='text/csv',use_container_width=True)
with d:
    st.download_button('All path-years (CSV)', r['annual_detail'].to_csv(index=False).encode(),
        file_name='path_year_calculations.csv',mime='text/csv',use_container_width=True)

st.caption('Baseline research model. Total/endowment balances shown above include all assets; new gifts and returns on their segregated holdings are locked from payout for all five years; '
           'existing opening assets are treated as eligible subject to R1 liquidation restrictions. Donor contracts, '
           'annual sale timing, and investment fees remain simplified. No stress scenarios are applied.')
