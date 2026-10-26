"""Endowment planning dashboard."""
from dataclasses import asdict, replace
from io import BytesIO
import hashlib
import json
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from endowment_simulation_model import (SimulationConfig, load_default_data, load_excel_overrides,
    institutional_params_from_data, liquidity_params_from_data, run_monte_carlo, historical_validation)
from portfolio_return_simulation import compare_return_methods, fit_mixture, checked_history
from strategy_analysis import portfolio_from_assets, policy_cases, compare_cases, comparison_row
from stress_testing import stress_cases, mixture_sensitivity
from validation import calibration_diagnostics, holdout_diagnostics, stability_check
from dashboard_ui import apply_style, band_chart, style_figure, risk_table, comparison_display

st.set_page_config(page_title='Endowment Payout Risk Lab',page_icon='📊',layout='wide')
apply_style()
st.title('Endowment Payout Risk Lab')
st.markdown('<p class="intro">Explore how investment and spending choices shape university funding.</p>',unsafe_allow_html=True)
overview,strategies,stress,returns,data_tab,checks=st.tabs(['Overview','Strategies','Stress tests','Return models','Data & downloads','Model checks'])

@st.cache_data
def get_data():
    return load_default_data()

@st.cache_data
def fit_history(values):
    return fit_mixture(np.asarray(values))

@st.cache_data
def diagnostics_for_history(history):
    return calibration_diagnostics(history)

data=get_data()
base=SimulationConfig(return_method='Single Normal',n_sims=1000)
inst=institutional_params_from_data(data)
liq=liquidity_params_from_data(data)
history=data.p4_quarterly
# Optional imports are kept in a secondary tab, away from the main dashboard.
with data_tab:
    with st.expander('Import a workbook'):
        upload=st.file_uploader('Model workbook',type=['xlsx'],help='Use the existing Model Inputs, R1 Inputs and R2 Inputs workbook layout.')
source_key='default' if upload is None else hashlib.sha256(upload.getvalue()).hexdigest()[:12]
if upload is not None:
    try:
        base,inst,liq,hist=load_excel_overrides(upload.getvalue(),data)
        if hist is not None:
            history=checked_history(hist)
    except Exception as exc:
        st.error(f'Unable to import this workbook: {exc}')
        st.stop()

def number(label,value,**kwargs):
    return st.number_input(label,value=float(value),key=source_key+label,**kwargs)

with st.sidebar:
    st.subheader('Your endowment')
    basic=st.container()
    advanced=st.expander('Advanced options')
    with basic:
        institution_type=st.selectbox('Institution',['Private','Public'],index=['Private','Public'].index(inst.institution_type),key='institution_'+source_key)
    with advanced:
        scenario=st.selectbox('Institutional assumptions',['Low','Base','High'],index=['Low','Base','High'].index(inst.scenario),key='scenario_'+source_key)
    if upload is None or (institution_type,scenario)!=(inst.institution_type,inst.scenario):
        inst=institutional_params_from_data(data,institution_type,scenario)
    source_key+=institution_type+scenario
    with basic:
        initial=number('Starting endowment ($M)',base.initial_endowment,min_value=1.,step=5.,format='%.1f')
        rule=st.selectbox('Spending rule',['Trailing average','Current assets'],format_func=lambda x:'Three-year average' if x=='Trailing average' else 'Beginning-of-year value')
        spending=number('Annual spending rate (%)',inst.effective_spending_rate*100,min_value=0.,max_value=100.,step=.1,format='%.2f')/100
        years=st.slider('Projection horizon (years)',1,30,10)
        run=st.button('Run analysis',type='primary',use_container_width=True)
    with advanced:
        st.markdown('**Simulation**')
        n=st.select_slider('Simulation paths',options=[100,500,1000,2000,5000,10000],value=1000)
        seed=st.number_input('Random seed',min_value=0,value=42,step=1)
        start=st.number_input('Start year',min_value=2000,max_value=2100,value=2027,step=1)
        method=st.selectbox('Return model',['Single Normal','Two-component Normal mixture','Quarterly block bootstrap','Regime-switching bootstrap'])
        block=st.slider('Bootstrap block (quarters)',1,min(8,len(history)),4,disabled='block' not in method.lower())
        alpha=st.slider('Risk confidence level',.90,.99,.95,.01)
        threshold=st.slider('Principal threshold (% of starting value)',50,100,100)/100
        st.markdown('**Inflation and returns**')
        fixed=st.checkbox('Use fixed inflation',value=True)
        inflation=st.number_input('Annual inflation (%)',value=2.5,min_value=-5.,max_value=30.,step=.1,disabled=not fixed)/100
        shift=st.number_input('Annual mean-return adjustment (pp)',value=0.,min_value=-20.,max_value=20.,step=.5)/100
        vol=st.number_input('Volatility multiplier',value=1.,min_value=.1,max_value=3.,step=.1)
        p=adverse_mean=adverse_std=None
        if 'mixture' in method.lower():
            fitted=fit_history(tuple(history.p4_return.astype(float)))
            override=st.checkbox('Customize adverse-return assumptions')
            if override:
                p=st.number_input('Adverse-quarter probability (%)',value=float(fitted['adverse_probability']*100),min_value=0.,max_value=100.)/100
                adverse_mean=st.number_input('Adverse quarterly mean (%)',value=float(fitted['adverse_mean']*100),min_value=-50.,max_value=30.)/100
                adverse_std=st.number_input('Adverse quarterly volatility (%)',value=float(fitted['adverse_std']*100),min_value=.01,max_value=50.)/100
        st.markdown('**Spending details**')
        use_prior=st.checkbox('Use past endowment values',value=upload is not None,key='past_'+source_key)
        prior2=prior1=initial
        if use_prior:
            prior2=number('Endowment two years earlier ($M)',base.prior_endowment_2y,min_value=1.)
            prior1=number('Endowment one year earlier ($M)',base.prior_endowment_1y,min_value=1.)
        smoothing=3
        collar=st.checkbox('Limit annual payout changes')
        floor=cap=None
        if collar:
            floor=st.number_input('Minimum annual payout change (%)',value=-5.,min_value=-100.)/100
            cap=st.number_input('Maximum annual payout change (%)',value=5.,min_value=-100.)/100
        gifts=number('Annual gifts (% of beginning assets)',inst.gift_rate*100,min_value=0.)/100
        changes=number('Other endowment changes (%)',inst.other_changes_rate*100)/100
        expenses=number('Expenses / initial endowment',inst.expenses_to_endowment_ratio,min_value=0.)
        expense_growth=number('Annual expense growth (%)',inst.annual_expense_growth*100,min_value=-100.)/100
        support=number('Required endowment support (% of expenses)',inst.support_ratio*100,min_value=0.)/100
        st.markdown('**Liquidity**')
        enabled=st.checkbox('Apply liquidity constraints',value=liq.enabled)
        other=number('Other annual cash needs ($M)',liq.other_annual_cash_need,min_value=0.)
        liq=replace(liq,enabled=enabled,other_annual_cash_need=other)
        if enabled:
            liquid=number('Highly liquid assets (%)',liq.liquid_share*100,min_value=0.,max_value=100.)/100
            illiquid=number('Illiquid assets (%)',liq.illiquid_share*100,min_value=0.,max_value=100.)/100
            buffer=number('Reserve (years of planned payout)',liq.liquidity_buffer_years,min_value=0.)
            reserve=number('Minimum cash reserve ($M)',liq.minimum_cash_reserve,min_value=0.)
            discount=number('Forced-sale discount (%)',liq.forced_sale_discount*100,min_value=0.,max_value=95.)/100
            haircut=number('Restricted liquid assets (%)',liq.liquid_share_haircut*100,min_value=0.,max_value=100.)/100
            moderate=number('Annual access to moderately liquid assets (%)',liq.moderately_liquid_access*100,min_value=0.,max_value=100.)/100
            allow=st.checkbox('Allow forced sales',value=liq.allow_forced_sales)
            liq=replace(liq,liquid_share=liquid,illiquid_share=illiquid,liquidity_buffer_years=buffer,
                minimum_cash_reserve=reserve,forced_sale_discount=discount,liquid_share_haircut=haircut,
                moderately_liquid_access=moderate,allow_forced_sales=allow)

cfg=replace(base,initial_endowment=initial,prior_endowment_2y=prior2,prior_endowment_1y=prior1,
    horizon_years=years,start_year=int(start),n_sims=int(n),seed=int(seed),alpha=alpha,return_method=method,
    block_size_quarters=block,annual_return_shift=shift,volatility_multiplier=vol,
    annual_inflation=inflation if fixed else None,adverse_probability=p,adverse_mean=adverse_mean,
    adverse_std=adverse_std,real_corpus_threshold=threshold)
inst=replace(inst,effective_spending_rate=spending,gift_rate=gifts,other_changes_rate=changes,
    expenses_to_endowment_ratio=expenses,annual_expense_growth=expense_growth,support_ratio=support,
    spending_rule=rule,smoothing_years=smoothing,annual_payout_growth_floor=floor,annual_payout_growth_cap=cap)
settings={'config':asdict(cfg),'institution':asdict(inst),'liquidity':asdict(liq)}
signature=repr((settings,history.to_json()))
changed=st.session_state.get('signature') is not None and st.session_state.get('signature')!=signature
if st.session_state.get('signature')!=signature:
    st.session_state['results']={}
    st.session_state['signature']=signature
results=st.session_state.setdefault('results',{})

def execute(key,fn):
    results.pop(key,None)
    try:
        with st.spinner('Calculating your results…'):
            results[key]=fn()
    except Exception as exc:
        st.error(f'Unable to complete this analysis: {exc}')

with overview:
    if run:
        execute('baseline',lambda:run_monte_carlo(data,cfg,inst,liq,p4_history=history))
    if 'baseline' not in results:
        if changed:
            st.info('Settings updated. Select Run analysis to refresh your results.')
        st.markdown('''<div class="empty-state"><h2>See what your endowment can support.</h2><p>Choose your starting value and spending rule, then select <b>Run analysis</b>.<br>Explore future payouts, purchasing power and funding risk in one place.</p></div>''',unsafe_allow_html=True)
    else:
        result=results['baseline'];m=result['metrics'];annual=result['annual_results']
        st.markdown(f'<div class="selection">Starting value: ${initial:,.1f}M &nbsp; · &nbsp; Spending rate: {spending:.2%} &nbsp; · &nbsp; Horizon: {years} years</div>',unsafe_allow_html=True)
        a,b,c=st.columns(3)
        a.metric('Return-coverage shortfall',f"{m['annual_coverage_shortfall_probability']:.1%}",help='Share of simulated years where investment earnings fall below the planned payout.')
        b.metric('Payout funding risk',f"{m['probability_at_least_one_shortfall']:.1%}",help=f'Chance of at least one year where actual payout is below planned payout over {years} years.')
        c.metric('Real principal erosion',f"{m['probability_real_corpus_erosion']:.1%}",help=f'Chance real endowment value falls below {threshold:.0%} of its starting value in any projected year.')
        a.caption('Years with earnings below planned payout')
        b.caption('Any year with payout below plan')
        c.caption(f'Any year below {threshold:.0%} of starting purchasing power')
        initial_payout=float(annual.loc[annual.path_id==0,'planned_payout'].iloc[0])
        with st.container(border=True):
            st.subheader('Can the university maintain its annual funding?')
            st.plotly_chart(band_chart(annual,'real_actual_payout',initial_payout,cfg.start_year,'Median real payout','Initial planned payout'),use_container_width=True)
        with st.container(border=True):
            st.subheader('How much purchasing power remains?')
            st.plotly_chart(band_chart(annual,'real_ending_assets',initial,cfg.start_year,'Median real endowment','Starting principal'),use_container_width=True)
        a,b=st.columns(2)
        a.metric('Median ending real endowment',f"${m['median_terminal_real_assets']:,.1f}M")
        b.metric('Median total real payouts',f"${m['median_cumulative_real_payout']:,.1f}M")
        with st.expander('Explore risk measures'):
            st.dataframe(risk_table(m),hide_index=True,use_container_width=True)
        with st.expander('View individual simulation outcomes'):
            st.dataframe(result['path_summary'],hide_index=True,use_container_width=True)

with strategies:
    st.subheader('Find a spending policy that fits your goals')
    left,right=st.columns(2)
    alt_rate=left.number_input('Compare spending rate (%)',value=4.,min_value=0.,max_value=100.)/100
    alt_buffer=right.number_input('Compare reserve (years of payout)',value=.5,min_value=0.)
    if results.get('policy_inputs')!=(alt_rate,alt_buffer):
        results.pop('policies',None)
    if st.button('Compare policies',type='primary'):
        execute('policies',lambda:compare_cases(data,policy_cases(cfg,inst,liq,alt_rate,alt_buffer),history))
        results['policy_inputs']=(alt_rate,alt_buffer)
    if 'policies' in results:
        table=results['policies']
        chart=table.copy();chart['Payout reliability (%)']=100*(1-chart['Pr(any payout funding shortfall)'])
        fig=px.scatter(chart,x='Payout reliability (%)',y='Median terminal real corpus ($M)',color='Scenario',
            hover_data=['Median cumulative real payouts ($M)'],size_max=16)
        style_figure(fig,'Ending real endowment ($M)');fig.update_xaxes(title='Payout reliability (%)');fig.update_traces(marker_size=14)
        st.plotly_chart(fig,use_container_width=True)
        st.dataframe(comparison_display(table),hide_index=True,use_container_width=True)
    with st.expander('Compare investment allocations'):
        asset_file=st.file_uploader('Quarterly asset returns',type='csv',help='CSV: quarter, followed by named asset columns. Enter returns as decimals.')
        weights_file=st.file_uploader('Alternative allocation',type='csv',help='CSV columns: asset, weight, liquidity_class. Weights must sum to 1.')
        allocation_signature=repr((asset_file.getvalue() if asset_file else None,weights_file.getvalue() if weights_file else None))
        if results.get('allocation_signature')!=allocation_signature:
            results.pop('allocations',None)
        if st.button('Compare allocations',disabled=not(asset_file and weights_file)):
            def allocation_run():
                assets=pd.read_csv(BytesIO(asset_file.getvalue()));weights=pd.read_csv(BytesIO(weights_file.getvalue()))
                anchor_h,al,ai=portfolio_from_assets(assets,data.p4_weights,data.condition_history)
                alt_h,bl,bi=portfolio_from_assets(assets,weights,data.condition_history)
                rows=[]
                for label,h,l,i in [('Current allocation',anchor_h,al,ai),('Alternative allocation',alt_h,bl,bi)]:
                    rows.append(comparison_row(label,run_monte_carlo(data,cfg,inst,replace(liq,liquid_share=l,illiquid_share=i),p4_history=h,keep_paths=False)))
                return pd.DataFrame(rows)
            execute('allocations',allocation_run);results['allocation_signature']=allocation_signature
        if 'allocations' in results:
            st.dataframe(comparison_display(results['allocations']),hide_index=True,use_container_width=True)

with stress:
    st.subheader('Explore tougher market conditions')
    with st.expander('Adjust stress scenarios'):
        a=st.number_input('Annual return adjustment (pp)',value=-4.,min_value=-20.,max_value=20.)/100
        b=st.number_input('Stress inflation (%)',value=6.,min_value=-5.,max_value=30.)/100
        c=st.number_input('Spending increase (pp)',value=1.,min_value=0.,max_value=20.)/100
        d=st.slider('Restricted liquid assets in stress (%)',0,100,50)/100
        e=st.slider('Forced-sale discount in stress (%)',0,95,30)/100
    stress_signature=(a,b,c,d,e)
    if results.get('stress_inputs')!=stress_signature:
        results.pop('stress',None)
    if st.button('Run stress tests',type='primary'):
        execute('stress',lambda:compare_cases(data,stress_cases(cfg,inst,liq,a,b,c,d,e),history))
        results['stress_inputs']=stress_signature
    if 'stress' in results:
        table=results['stress']
        fig=px.bar(table,x='Scenario',y='Median terminal real corpus ($M)',color_discrete_sequence=['#59C9BE'])
        style_figure(fig,'Ending real endowment ($M)');fig.update_xaxes(title=None)
        st.plotly_chart(fig,use_container_width=True)
        st.dataframe(comparison_display(table),hide_index=True,use_container_width=True)
    with st.expander('Explore adverse-return sensitivity'):
        if st.button('Run sensitivity analysis'):
            execute('sensitivity',lambda:mixture_sensitivity(data,cfg,inst,liq,history))
        if 'sensitivity' in results:
            st.dataframe(comparison_display(results['sensitivity']),hide_index=True,use_container_width=True)

with returns:
    st.subheader('Compare ways to model investment returns')
    if st.button('Compare return models',type='primary'):
        execute('methods',lambda:compare_return_methods(data,cfg,inst,liq,p4_history=history))
    if 'methods' in results:
        table,parameters,cpi,detail=results['methods']
        distributions=pd.concat([r['annual_results'][['portfolio_return']].assign(Model=name) for name,r in detail.items()],ignore_index=True)
        fig=px.histogram(distributions,x='portfolio_return',color='Model',histnorm='probability density',barmode='overlay',opacity=.45,nbins=60)
        style_figure(fig,'Density');fig.update_xaxes(title='Annual portfolio return',tickformat='.0%')
        st.plotly_chart(fig,use_container_width=True)
        st.dataframe(comparison_display(pd.DataFrame([comparison_row(name,r) for name,r in detail.items()])),hide_index=True,use_container_width=True)
        with st.expander('View detailed comparison'):
            st.caption(f'Common annual inflation: {cpi:.2%}')
            st.dataframe(table,use_container_width=True)
    with st.expander('View distribution fit'):
        diagnostics,parameters=diagnostics_for_history(history)
        st.dataframe(diagnostics,hide_index=True,use_container_width=True)
        st.dataframe(pd.DataFrame({'Parameter':[key.replace('_',' ').capitalize() for key in parameters],
                                   'Value':[f'{value:.2%}' for value in parameters.values()]}),hide_index=True,use_container_width=True)

with data_tab:
    with st.expander('Current portfolio and assumptions'):
        weights=data.p4_weights.rename(columns={'asset':'Asset','weight':'Allocation','liquidity_class':'Liquidity'}).copy()
        weights['Allocation']=weights.Allocation.map(lambda x:f'{x:.2%}')
        st.dataframe(weights,hide_index=True,use_container_width=True)
        st.caption(f'Return history: {history.quarter.iloc[0]}–{history.quarter.iloc[-1]} · {len(history)} quarters')
        st.json(settings,expanded=False)
    st.subheader('Save your analysis')
    a,b=st.columns(2)
    a.download_button('Download settings',json.dumps(settings,indent=2),'run_settings.json','application/json')
    b.download_button('Download return history',history.to_csv(index=False),'active_calibration.csv','text/csv')
    if 'baseline' in results:
        r=results['baseline']
        for label,filename,table in [('Annual results','annual_results',r['annual_results']),('Simulation outcomes','path_summary',r['path_summary']),('Risk measures','metrics',pd.DataFrame([r['metrics']]))]:
            st.download_button(f'Download {label.lower()}',table.to_csv(index=False),f'{filename}.csv','text/csv')
    for key in ['policies','allocations','stress','sensitivity','stability','holdout']:
        if key in results:
            st.download_button(f'Download {key}',results[key].to_csv(index=False),f'{key}.csv','text/csv')

with checks:
    st.subheader('Review the analysis')
    with st.expander('Historical reconstruction'):
        if st.button('Run historical check'):
            execute('historical',lambda:historical_validation(data,replace(cfg,horizon_years=10,start_year=2013),inst,liq))
        if 'historical' in results:
            h=results['historical'];st.dataframe(h,hide_index=True,use_container_width=True)
            st.caption(f'Maximum accounting difference: {h.accounting_residual.abs().max():.3g}M')
    with st.expander('Out-of-sample return check'):
        if st.button('Run holdout check'):
            execute('holdout',lambda:holdout_diagnostics(history))
        if 'holdout' in results:
            st.dataframe(results['holdout'],hide_index=True,use_container_width=True)
    with st.expander('Simulation stability'):
        if st.button('Check simulation stability'):
            execute('stability',lambda:stability_check(data,cfg,inst,liq,history))
        if 'stability' in results:
            st.dataframe(results['stability'],hide_index=True,use_container_width=True)
