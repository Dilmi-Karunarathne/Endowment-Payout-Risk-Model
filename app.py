"""Simple endowment dashboard. Run with: python -m streamlit run app.py"""
from dataclasses import asdict
from io import BytesIO
from pathlib import Path
import json
import zipfile
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard_contract import RESULT_SCHEMA_VERSION, validate_result_schema
from investment_model import STRATEGIES
from simple_analysis import BaselineOptions, COMPARISON_STRATEGIES, strategy_cash_requirements
from scenario_analysis import (Scenario, STRATEGY_LABELS, stress_library, what_if_library,
    run_suite, assumption_table, settings_json, validate_scenario)

st.set_page_config(page_title='Endowment Planning & Risk',page_icon='🎓',layout='wide')
st.markdown('''<style>
.block-container {max-width:1260px;padding-top:2rem;padding-bottom:3rem;}
h1,h2,h3 {letter-spacing:-.025em;}
[data-testid="stMetric"] {background:#f2f6fa;border:1px solid #dbe4ed;border-radius:12px;padding:16px;}
[data-testid="stMetricLabel"] {color:#486078;}
[data-testid="stMetricValue"] {color:#102e4a;}
[data-testid="stSidebar"] {background:#f2f6fa;}
</style>''',unsafe_allow_html=True)

MODES=['Baseline & strategies','Stress testing','What-if scenarios','Model guide']
with st.sidebar:
    st.markdown('### Endowment Planning')
    mode=st.radio('Explore',MODES,label_visibility='collapsed',key='navigation')
    st.divider()
    institution=st.selectbox('Institution type',['Private','Public'])
    profile=st.selectbox('Institutional profile',['Low','Base','High'],index=1,
        help='Supplied benchmark assumptions. Low and High combine parameter percentiles; they do not mean worst and best outcomes.')
    strategy=st.selectbox('Investment strategy',STRATEGIES,index=STRATEGIES.index('HRP'),
        format_func=lambda key:STRATEGY_LABELS[key])
    compare=st.checkbox('Compare the three main strategies',
        help='Run Hierarchical Risk Parity, Minimum Variance and Mean–Conditional Value at Risk on identical market draws.')
    initial=st.number_input('Starting endowment ($ millions)',min_value=1.,max_value=10000.,value=150.,step=10.)
    paths=st.selectbox('Simulation paths per case',[5000,10000],format_func=lambda x:f'{x:,}')
    st.caption('Five years · 2027–2031\n\nAll monetary results are in US dollars. Seed 42 makes runs reproducible.')

st.title('Endowment Planning & Risk')
st.caption('Explore investment performance, reliable payouts and long-term purchasing power.')
options=BaselineOptions(institution,profile,strategy,float(initial),int(paths))
strategies=COMPARISON_STRATEGIES if compare else (strategy,)


def market_description(s):
    lines=[]
    replay=len(s.replay_quarters)
    if replay:
        lines.append(f'Historical replay: {s.replay_quarters[0]} to {s.replay_quarters[-1]} in the first {replay} projected quarters. Later quarters resume the matched sampled path.')
    if s.regime:
        lines.append(f'{s.regime} observations and allocation targets for the first {s.regime_quarters} quarters.')
    if s.asset_shocks:
        lines.append('The supplied asset shocks multiply the first-quarter gross returns once; these are hypothetical instantaneous shocks.')
    if s.annual_return_shift:
        lines.append(f'Return adjustment: {s.annual_return_shift*100:+.1f} percentage points per year, implemented as {s.annual_return_shift*25:+.2f} points per quarter for {s.return_shift_years} years'+(' after the replay.' if replay else ' from the start.'))
    if s.inflation_add:
        lines.append(f'Inflation adjustment: {s.inflation_add*100:+.1f} percentage points to annualized quarterly inflation for {s.inflation_years} years'+(' after the replay.' if replay else ' from the start.'))
    if not lines:lines.append('Market returns and inflation use the unchanged joint historical bootstrap.')
    return lines


def chart(suite,column,title,ylabel):
    fig=go.Figure()
    for (key,name),result in suite['cases'].items():
        label=(STRATEGY_LABELS[key]+' · ' if len(suite['strategies'])>1 else '')+name
        frame=result['yearly']
        fig.add_trace(go.Scatter(x=frame.year,y=frame[column],mode='lines+markers',name=label,
            line=dict(width=3 if name=='Baseline' else 2,dash='solid' if name=='Baseline' else 'dash')))
    fig.update_layout(title=title,template='plotly_white',height=390,
        margin=dict(l=16,r=16,t=65,b=30),font=dict(color='#24435d'),yaxis_title=ylabel,
        legend=dict(orientation='h',y=-.2),xaxis=dict(dtick=1,title=None))
    st.plotly_chart(fig,width='stretch')


MONEY_COLUMNS={'beginning_assets','investment_gain','endowment_gifts','restricted_gifts_received',
    'gifts_available_for_payout','beginning_spendable_assets','beginning_restricted_gift_assets',
    'spendable_investment_gain','restricted_gift_investment_gain','restricted_gift_assets_end',
    'spendable_assets_end','real_spendable_assets_end','real_restricted_gift_assets_end',
    'planned_payout','actual_payout','payout_shortfall_amount','earnings_gifts_coverage_gap',
    'return_coverage_shortfall_amount','spendable_earnings_coverage_gap','funding_capacity_for_payout',
    'cash_before_sales','actual_net_asset_sale_proceeds','forced_sale_loss','capital_call',
    'capital_call_paid','unpaid_capital_call','reserve_target','reserve_shortfall',
    'other_endowment_changes','other_cash_paid','ending_cash','ending_assets','real_ending_assets',
    'real_actual_payout','operating_expenses','net_tuition','other_operating_revenue',
    'required_support','payout_support_gap','accounting_residual','rebalance_cost'}


def export_frame(frame):
    def label(key):
        if key=='investment_liquidity_breach':return 'Below 40% liquid share (0 or 1)'
        if key=='liquidity_breach_20pct':return 'Below 20% liquid share (0 or 1)'
        name=key.replace('_',' ').capitalize()
        if key in MONEY_COLUMNS:return name+' ($M)'
        if key.endswith('_m'):return name[:-2]+' ($M)'
        if key.endswith('_x'):return name[:-2]+' (times payout)'
        if key in ('portfolio_return','inflation','minimum_liquid_share','post_payout_liquid_asset_share'):
            return name+' (decimal)'
        return name
    return frame.rename(columns=label)


def download_bundle(suite):
    buffer=BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('comparison.csv',suite['comparison'].to_csv(index=False))
        z.writestr('run_settings.json',settings_json(suite))
        z.writestr('READ_ME.txt','All dollar amounts are USD millions. Probability columns in comparison.csv are percentages.\nPath-year returns and inflation are decimals. Events are 0/1.\nStress frequencies are conditional on the chosen scenario, not probabilities that the scenario occurs.\nSee run_settings.json for exact inputs.\n')
        for i,((key,name),result) in enumerate(suite['cases'].items(),1):
            prefix=f'{i:02d}_{key}'
            z.writestr(prefix+'_annual_summary.csv',export_frame(result['yearly']).to_csv(index=False))
            z.writestr(prefix+'_path_years.csv',export_frame(result['annual_detail']).to_csv(index=False))
            z.writestr(prefix+'_assumptions.csv',result['applied_assumptions'].to_csv(index=False))
            z.writestr(prefix+'_scenario.txt',name+'\n'+result['scenario'].description)
    return buffer.getvalue()


if mode=='Model guide':
    st.subheader('How the model works')
    st.markdown('''1. **Select an institution and portfolio.** The existing benchmark profile sets spending, gifts and operating assumptions.
2. **Generate matched markets.** Four-quarter blocks preserve the joint historical asset and inflation observations. Every strategy and scenario starts from the same sampled paths.
3. **Apply a scenario.** Historical replays replace specified quarters. Other scenarios adjust explicit market, gift, spending or liquidity inputs.
4. **Invest and fund payouts.** Quarterly holdings follow the existing allocation rules. At year-end, cash and eligible asset sales fund capital calls and the planned payout, with the selected reserve protected.
5. **Compare outcomes.** The dashboard separates investment returns, unpaid payouts, liquidity and inflation-adjusted wealth.''')
    st.markdown('#### Read the results')
    st.dataframe(pd.DataFrame([
        ['Unpaid payout probability','Share of paths with at least one planned payout not fully paid.'],
        ['Liquidity buffer','Stressed one-month liquid assets eligible for payouts ÷ planned annual payout.'],
        ['40% / 20% liquid-share breach','Share of paths where eligible liquid assets ÷ total wealth falls below the threshold. Quarterly and post-payout checks are included.'],
        ['Purchasing-power expected shortfall (95%)','Average nonnegative loss of ending real wealth, as a percentage of starting wealth, in the worst 5% of paths.'],
        ['Institutional support gap','Required institutional support exceeds the actual payout. It differs from an unpaid planned payout.'],
        ['Change from baseline','Same strategy and matched market paths; probability changes are percentage points.'],
    ],columns=['Measure','Meaning']),hide_index=True,width='stretch')
    st.markdown('#### Policies retained from the simplified model')
    st.markdown('''- Spending uses a three-year trailing average, with annual limits of 3%–5% of opening total endowment. Two prior values equal the starting endowment.
- New gifts arrive at year-end. They and their subsequent earnings remain restricted throughout the projection. They still enter total wealth and future spending calculations, as in the original framework.
- Capital calls move eligible cash into private investments. They reduce liquidity without automatically reducing wealth. Calls are proxies for net cash requirements; no separate private distributions are added.
- Payouts use cash first, then eligible sales within three months, after costs. The reserve remains protected. Unpaid capital calls are reported separately; no borrowing or overdue-call carry-forward is modeled.
- Annual investment returns exclude direct gifts and payouts, include modeled rebalancing costs, and precede payout-sale costs and full investment-management fees. Sale costs reduce endowment wealth separately.''')
    st.info('Historical replays reuse asset returns and inflation with today’s modeled portfolios. They do not reproduce an actual university’s historical performance. Scenario frequencies are conditional outcomes, not the chance that a crisis happens.')
    st.caption('The 70/30 benchmark remains deferred until comparable return data are provided. Low and High institutional profiles are assumption bundles. Asset proxies, transaction-size limits, annual cash timing and incomplete fees remain model limitations.')
    st.caption('Quarterly target trades are limited by actual liquid holdings and transaction costs. When a target trade cannot be financed, it is scaled down or deferred; annual payout funding is evaluated separately.')
    st.download_button('Download model guide',Path(__file__).with_name('MODEL_GUIDE.md').read_text(),file_name='MODEL_GUIDE.md')
    st.stop()

selected=[]
severity='Standard'
if mode=='Baseline & strategies':
    st.subheader('Start with the current assumptions')
    st.write('Run one portfolio or compare the three main strategies. Use these results as the reference for stress and policy decisions.')
elif mode=='Stress testing':
    st.subheader('How resilient is the endowment?')
    st.write('Choose adverse conditions and compare each result with the unchanged baseline.')
    severity=st.radio('Stress severity',['Standard','Severe'],horizontal=True,
        help='Severity changes the two main tests, stagflation, lower gifts, liquidity pressure and the sudden shock. Historical replay data, the six-quarter recession test and the five-year weak-return assumption stay fixed.')
    library=stress_library(institution,severity)
    names=st.multiselect('Stress tests',list(library),default=list(library)[:2],max_selections=4,help='Choose up to four tests per run to keep the comparison readable.')
    selected=[library[n] for n in names]
    st.caption('The two main tests combine supplied research assumptions. Additional tests isolate individual risks. Baseline is always included.')
else:
    st.subheader('What changes when the assumptions change?')
    library=what_if_library()
    names=st.multiselect('What-if comparisons',list(library),default=['Spending rate: 4%','No new gifts'],max_selections=4)
    selected=[library[n] for n in names]
    custom=st.checkbox('Add a custom scenario')
    if custom:
        with st.container(border=True):
            st.markdown('**Custom scenario** — adjustments begin in the first year.')
            left,right=st.columns(2)
            with left:
                duration=st.slider('Shock duration (years)',1,5,3)
                return_shift=st.slider('Annual return adjustment (percentage points)',-10.,5.,0.,.5)
                inflation=st.slider('Additional annualized inflation (percentage points)',0.,5.,0.,.25)
                gift_change=st.slider('Change in gift rate (%)',-100,100,0,5)
            with right:
                change_spend=st.checkbox('Set a different spending rate')
                spending=st.slider('Spending rate (%)',3.,5.,4.5,.1,disabled=not change_spend)
                change_reserve=st.checkbox('Set a different cash reserve')
                default_reserve=1. if compare else strategy_cash_requirements(strategy)['reserve_years_of_planned_payout']
                reserve=st.slider('Protected cash reserve (annual payouts)',0.,2.,default_reserve,.25,disabled=not change_reserve)
                calls=st.slider('Capital-call multiplier (scheduled years)',0.,2.,1.,.25)
                freeze=st.checkbox('Freeze emerging-market and high-yield sales')
            st.caption('Duration applies to returns, inflation, gifts, spending and any sales freeze. The reserve applies throughout; the call multiplier applies to the original three-year call schedule.')
            selected.append(Scenario('Custom scenario','Custom',
                'User-defined adjustments; all other simplified-model policies are retained.',
                'Values entered in this dashboard',annual_return_shift=return_shift/100,return_shift_years=duration,
                inflation_add=inflation/100,inflation_years=duration,
                gift_multiplier=1+gift_change/100,gift_years=duration,
                spending_rate=spending/100 if change_spend else None,spending_years=duration if change_spend else 0,
                reserve_years=reserve if change_reserve else None,capital_call_multiplier=calls,
                freeze_public_years=duration if freeze else 0,
                liquidity_stress_years=duration if freeze else 0))

with st.expander('Review assumptions before running',expanded=False):
    st.caption('All cases retain the same payout framework. Values are assumptions for illustration, not calibrated forecasts. Monetary units: $ millions.')
    for s in [Scenario()]+selected:
        st.markdown('**'+s.name+'**')
        st.write(s.description)
        for line in market_description(s):st.caption(line)
        if s.asset_shocks:
            st.dataframe(pd.DataFrame({'Asset':[a.replace('_',' ').title() for a in s.asset_shocks],
                'First-quarter overlay (%)':[100*v for v in s.asset_shocks.values()]}),hide_index=True)
        for key in strategies:
            from dataclasses import replace
            o=replace(options,strategy=key,profile=s.profile_override or options.profile)
            st.caption(STRATEGY_LABELS[key]+' · '+o.profile+' profile')
            st.dataframe(assumption_table(o,s).round(3),hide_index=True,width='stretch')
        st.caption('Source: '+s.source)

count=(1+len(selected))*len(strategies)
st.caption(f'{count} cases × {paths:,} matched paths · {institution} / {profile} · ${initial:,.0f}M starting endowment. Large comparisons can take several minutes.')
signature=json.dumps({'mode':mode,'options':asdict(options),'strategies':strategies,
    'scenarios':[asdict(s) for s in selected],'severity':severity,'schema':RESULT_SCHEMA_VERSION},sort_keys=True)
if st.button('Run analysis',type='primary',width='content'):
    bar=st.progress(0,text='Preparing matched market paths…')
    try:
        result=run_suite(options,selected,strategies,
            progress=lambda fraction,label:bar.progress(min(1.,fraction),text=f'{fraction:.0%} · {label}'))
        for r in result['cases'].values():
            valid,message=validate_result_schema(r)
            if not valid:raise ValueError(message)
        st.session_state['analysis']=(signature,result)
        st.session_state.pop('download_data',None)
        bar.empty()
        st.success('Analysis complete. All cases passed the asset and payout reconciliation checks.')
    except Exception as exc:
        bar.empty()
        st.error(f'Analysis could not finish: {exc}')
        st.stop()

saved=st.session_state.get('analysis')
if saved is None:
    st.info('Choose your settings, then select Run analysis. Each stress or what-if case includes its own matched baseline.')
    st.stop()
if saved[0]!=signature:
    st.info('Your settings have changed. Select Run analysis to update the results.')
    st.stop()
suite=saved[1]
st.divider()
st.subheader('Results')
st.caption(f"{suite['options'].institution} / {suite['options'].profile} · {suite['options'].paths:,} paths per case · 2027–2031. Stress probabilities are conditional on each scenario.")
overview,charts,details=st.tabs(['Comparison','Charts','Details & downloads'])
with overview:
    table=suite['comparison']
    core=['Strategy','Scenario','Median annualized return (%)','Unpaid payout probability (%)',
        'Median minimum liquidity buffer (×)','Median ending real endowment ($M)']
    st.dataframe(table[core].round(2),hide_index=True,width='stretch')
    if selected:
        st.markdown('**Change from baseline**')
        st.dataframe(table.loc[table.Scenario!='Baseline',['Strategy','Scenario',
            'Change in unpaid payout risk (pp)','Change in median real endowment ($M)',
            'Mean paired change in real endowment ($M)']].round(2),hide_index=True,width='stretch')
        st.caption('A percentage-point change subtracts the baseline probability. The paired wealth change averages each path’s change; it differs from the change in medians.')
    st.markdown('**Downside and liquidity**')
    st.dataframe(table[['Strategy','Scenario','Below 40% liquid-share probability (%)',
        'Below 20% liquid-share probability (%)','Purchasing-power expected shortfall 95% (%)',
        'Unpaid capital-call probability (%)']].round(2),hide_index=True,width='stretch')
    st.caption('A liquidity-policy breach is distinct from an unpaid payout. Cash-funding capacity uses a three-month deadline; the liquidity monitor uses stressed one-month weights.')
with charts:
    chart_suite=suite
    if len(suite['strategies'])>1 and len(suite['scenarios'])>1:
        chart_strategy=st.selectbox('Portfolio shown in charts',suite['strategies'],format_func=lambda k:STRATEGY_LABELS[k])
        chart_suite={**suite,'cases':{k:v for k,v in suite['cases'].items() if k[0]==chart_strategy},'strategies':(chart_strategy,)}
    chart(chart_suite,'median_real_endowment_m','Median endowment after inflation','Real total endowment ($M)')
    chart(chart_suite,'median_real_spendable_assets_m','Assets that support payouts','Real payout-eligible assets ($M)')
    chart(chart_suite,'median_liquidity_buffer_x','Liquidity remaining after the annual payout','Liquid assets / planned payout (×)')
    chart(chart_suite,'mean_actual_payout_m','Mean annual payout delivered','Annual payout ($M)')
    st.caption('Lines are annual cross-path summaries; a line is not one simulated path. Restricted gifts may increase total wealth without increasing the assets available for payouts.')
with details:
    choices=list(suite['cases'])
    key=st.selectbox('Inspect a case',choices,format_func=lambda k:STRATEGY_LABELS[k[0]]+' · '+k[1])
    r=suite['cases'][key]
    st.dataframe(export_frame(r['yearly']).round(4),hide_index=True,width='stretch')
    st.markdown('**Applied annual assumptions**')
    st.dataframe(r['applied_assumptions'].round(3),hide_index=True,width='stretch')
    st.caption('Investment returns include modeled rebalancing costs; payout-sale costs are charged separately to wealth. Full management fees are not included.')
    c1,c2=st.columns(2)
    with c1:
        st.download_button('Download comparison CSV',table.to_csv(index=False),file_name='endowment_comparison.csv',mime='text/csv')
    with c2:
        st.download_button('Download run settings',settings_json(suite),file_name='run_settings.json',mime='application/json')
    if st.button('Prepare full calculation download'):
        st.session_state['download_data']=download_bundle(suite)
    if 'download_data' in st.session_state:
        st.download_button('Download all calculations (ZIP)',st.session_state['download_data'],
            file_name='endowment_analysis_results.zip',mime='application/zip')
