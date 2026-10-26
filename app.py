"""Streamlit interface for the Fall endowment payout-risk research model."""
from dataclasses import asdict, replace
from io import BytesIO
import hashlib
import json
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from endowment_simulation_model import (SimulationConfig, load_default_data, load_excel_overrides,
    institutional_params_from_data, liquidity_params_from_data, run_monte_carlo,
    historical_validation, percentile_path)
from portfolio_return_simulation import compare_return_methods, fit_mixture, checked_history
from strategy_analysis import portfolio_from_assets, policy_cases, compare_cases, comparison_row
from stress_testing import stress_cases, mixture_sensitivity
from stress_tab import render_stress_results
from validation import calibration_diagnostics, holdout_diagnostics, stability_check

st.set_page_config(page_title='Endowment Payout Risk', page_icon='📊', layout='wide')
@st.cache_data
def get_data():
    return load_default_data()

@st.cache_data
def fit_history(values):
    return fit_mixture(np.asarray(values))

data = get_data()
st.title('Endowment payout risk')
st.caption('Fall research framework · v2.1 · $101M–$250M anchor cohort · R1 P4 remains an interim portfolio')
base = SimulationConfig(return_method='Single Normal', n_sims=1000)
inst = institutional_params_from_data(data)
liq = liquidity_params_from_data(data)
history = data.p4_quarterly
upload = st.sidebar.file_uploader('Optional clean Excel calibration', type=['xlsx'])
source_key = 'default' if upload is None else hashlib.sha256(upload.getvalue()).hexdigest()[:12]
# New workbook values must replace previous widget values, including valid zero inputs.
def number(label, value, **kwargs):
    return st.sidebar.number_input(label, value=float(value), key=source_key+label, **kwargs)
if upload is not None:
    try:
        base, inst, liq, hist = load_excel_overrides(upload.getvalue(), data)
        if hist is not None:
            history = checked_history(hist)
        st.sidebar.success('Workbook values loaded; review the controls below.')
    except Exception as exc:
        st.error(f'Workbook could not be loaded: {exc}')
        st.stop()

with st.sidebar:
    st.header('Simulation')
    institution_type = st.selectbox('Institution type', ['Private','Public'], index=['Private','Public'].index(inst.institution_type))
    scenario = st.selectbox('R2 scenario', ['Low','Base','High'], index=['Low','Base','High'].index(inst.scenario))
if upload is None or (institution_type,scenario)!=(inst.institution_type,inst.scenario):
    inst = institutional_params_from_data(data,institution_type,scenario)
    if upload is not None:
        st.sidebar.info('Selected R2 cohort replaces the workbook institutional values.')
source_key += institution_type + scenario
initial = number('Initial endowment ($M)',base.initial_endowment,min_value=1.,step=5.)
prior2 = number('Endowment two years before start ($M)',base.prior_endowment_2y,min_value=1.,step=5.)
prior1 = number('Endowment one year before start ($M)',base.prior_endowment_1y,min_value=1.,step=5.)
years = st.sidebar.slider('Horizon (years)',1,30,10)
n = st.sidebar.select_slider('Simulation paths',options=[100,500,1000,2000,5000,10000],value=1000)
seed = st.sidebar.number_input('Seed',min_value=0,value=42,step=1)
start = st.sidebar.number_input('Start year',min_value=2000,max_value=2100,value=2027,step=1)
method = st.sidebar.selectbox('Return model',['Single Normal','Two-component Normal mixture','Quarterly block bootstrap','Regime-switching bootstrap'])
block = st.sidebar.slider('Bootstrap block (quarters)',1,min(8,len(history)),4)
alpha = st.sidebar.slider('VaR / ES confidence',.90,.99,.95,.01)
threshold = st.sidebar.slider('Real corpus erosion threshold (% of initial)',50,100,100)/100
with st.sidebar.expander('Return and inflation assumptions'):
    shift = st.number_input('Annual arithmetic mean shift (pp)',value=0.,min_value=-20.,max_value=20.,step=.5)/100
    vol = st.number_input('Volatility multiplier',value=1.,min_value=.1,max_value=3.,step=.1)
    fixed = st.checkbox('Fixed annual inflation',value=True)
    inflation = st.number_input('Annual inflation (%)',value=2.5,min_value=-5.,max_value=30.,step=.1)/100
    st.caption('Normal models otherwise use mean historical CPI. Bootstrap pairs returns and CPI; regime sampling is condition-based.')
fitted = fit_history(tuple(history.p4_return.astype(float)))
p = adverse_mean = adverse_std = None
with st.sidebar.expander('Mixture assumptions'):
    override = st.checkbox('Override fitted mixture components',value=False)
    probability = st.number_input('Adverse-quarter probability (%)',value=float(fitted['adverse_probability']*100),min_value=0.,max_value=100.)/100
    mean = st.number_input('Adverse quarterly mean (%)',value=float(fitted['adverse_mean']*100),min_value=-50.,max_value=30.)/100
    std = st.number_input('Adverse quarterly volatility (%)',value=float(fitted['adverse_std']*100),min_value=.01,max_value=50.)/100
    if override:
        p,adverse_mean,adverse_std=probability,mean,std
    st.caption('Statistical mixture components are independent quarterly draws, not economic regimes.')
with st.sidebar.expander('Spending and R2 assumptions'):
    rule = st.selectbox('Spending policy',['Trailing average','Current assets'])
    smoothing = st.slider('Trailing averaging years',1,3,3)
    spending = number('Spending rate (%)',inst.effective_spending_rate*100,min_value=0.,max_value=100.)/100
    gifts = number('Unrestricted gifts (% beginning assets)',inst.gift_rate*100,min_value=0.)/100
    changes = number('Other endowment changes (%)',inst.other_changes_rate*100)/100
    expenses = number('Expenses / initial endowment',inst.expenses_to_endowment_ratio,min_value=0.)
    expense_growth = number('Annual expense growth (%)',inst.annual_expense_growth*100,min_value=-100.)/100
    support = number('Required support / expenses (%)',inst.support_ratio*100,min_value=0.)/100
    collar = st.checkbox('Apply payout growth collar')
    floor = st.number_input('Annual payout growth floor (%)',value=-5.,min_value=-100.)/100
    cap = st.number_input('Annual payout growth cap (%)',value=5.,min_value=-100.)/100
with st.sidebar.expander('Liquidity and cash priorities'):
    enabled=st.checkbox('Enable liquidity constraints',value=liq.enabled)
    liquid=number('Initially highly liquid share (%)',liq.liquid_share*100,min_value=0.,max_value=100.)/100
    illiquid=number('Initially illiquid share (%)',liq.illiquid_share*100,min_value=0.,max_value=100.)/100
    buffer=number('Reserve (years of planned payout)',liq.liquidity_buffer_years,min_value=0.)
    reserve=number('Minimum cash reserve ($M)',liq.minimum_cash_reserve,min_value=0.)
    other=number('Other endowment-funded annual cash need ($M)',liq.other_annual_cash_need,min_value=0.)
    discount=number('Forced-sale discount (%)',liq.forced_sale_discount*100,min_value=0.,max_value=95.)/100
    haircut=number('Highly liquid access haircut (%)',liq.liquid_share_haircut*100,min_value=0.,max_value=100.)/100
    moderate=number('Moderate bucket annual access (%)',liq.moderately_liquid_access*100,min_value=0.,max_value=100.)/100
    allow=st.checkbox('Allow forced sales',value=liq.allow_forced_sales)
    st.caption('Reserve first, then other obligations, then payouts. Holdings persist between years; no automatic reserve refill from unavailable assets.')
cfg = replace(base,initial_endowment=initial,prior_endowment_2y=prior2,prior_endowment_1y=prior1,horizon_years=years,
    start_year=int(start),n_sims=int(n),seed=int(seed),alpha=alpha,return_method=method,block_size_quarters=block,
    annual_return_shift=shift,volatility_multiplier=vol,annual_inflation=inflation if fixed else None,
    adverse_probability=p,adverse_mean=adverse_mean,adverse_std=adverse_std,real_corpus_threshold=threshold)
inst=replace(inst,effective_spending_rate=spending,gift_rate=gifts,other_changes_rate=changes,
    expenses_to_endowment_ratio=expenses,annual_expense_growth=expense_growth,support_ratio=support,
    spending_rule=rule,smoothing_years=smoothing,annual_payout_growth_floor=floor if collar else None,annual_payout_growth_cap=cap if collar else None)
liq=replace(liq,enabled=enabled,liquid_share=liquid,illiquid_share=illiquid,liquidity_buffer_years=buffer,
    minimum_cash_reserve=reserve,other_annual_cash_need=other,forced_sale_discount=discount,
    liquid_share_haircut=haircut,moderately_liquid_access=moderate,allow_forced_sales=allow)
settings={'config':asdict(cfg),'institution':asdict(inst),'liquidity':asdict(liq)}
signature=repr((settings,history.to_json()))
if st.session_state.get('signature') != signature:
    st.session_state['results']={}
    st.session_state['signature']=signature
results=st.session_state.setdefault('results',{})
st.info(f'{institution_type} / {scenario} · {initial:,.0f}M initial assets · {years} years · {n:,} paths · {method}')
if not 101 <= initial <= 250:
    st.warning('Selected assets are outside the anchor $101M–$250M band. Institutional calibration is not automatically changed to another size cohort.')
inputs,baseline,strategies,returns,stress,validation=st.tabs(['Inputs & assumptions','Baseline results','Strategy comparison','Return-model comparison','Stress & sensitivity','Validation & downloads'])

def execute(key, fn):
    results.pop(key, None)
    try:
        with st.spinner('Running simulations…'):
            results[key]=fn()
    except Exception as exc:
        st.error(str(exc))

with inputs:
    st.warning('P4 is provisional. Liquidity policies, stress values and alternative spending rates are scenario assumptions until confirmed by R1/R2.')
    st.dataframe(data.p4_weights,use_container_width=True)
    st.json(settings,expanded=False)
    st.write(f'Calibration: {history.quarter.iloc[0]} to {history.quarter.iloc[-1]} ({len(history)} quarters).')
    st.markdown('See **METHODOLOGY.md** and **PENDING_INPUTS.md** in the package for definitions, sources and remaining decisions. Institutional support-gap outputs are not a complete operating-budget projection.')
    st.download_button('Download run settings',json.dumps(settings,indent=2),'run_settings.json','application/json')
    st.download_button('Download active calibration',history.to_csv(index=False),'active_calibration.csv','text/csv')
with baseline:
    if st.button('Run baseline',type='primary'):
        execute('baseline',lambda:run_monte_carlo(data,cfg,inst,liq,p4_history=history))
    if 'baseline' in results:
        result=results['baseline'];m=result['metrics']
        columns=st.columns(3)
        for k,(label,key) in enumerate([
            ('Annual return-coverage shortfall','annual_coverage_shortfall_probability'),
            ('Pr(any funding shortfall)','probability_at_least_one_shortfall'),
            ('Pr(real corpus erosion)','probability_real_corpus_erosion')]):
            columns[k].metric(label,f'{m[key]:.1%}')
        st.caption('Annual frequency uses all simulated years. “Any” probabilities use simulated paths. Coverage means investment earnings below planned payout; funding means actual payout below planned payout.')
        frame=percentile_path(result['annual_results'])
        st.plotly_chart(px.line(frame,x='year',y=['p05','p50','p95'],labels={'value':'Real corpus ($M)'}),use_container_width=True)
        payouts=result['annual_results'].groupby('year')[['planned_payout','actual_payout','real_actual_payout']].median().reset_index()
        st.plotly_chart(px.line(payouts,x='year',y=['planned_payout','actual_payout','real_actual_payout'],labels={'value':'Payout ($M)'}),use_container_width=True)
        st.dataframe(pd.DataFrame({'Metric':list(m),'Value':list(m.values())}),use_container_width=True)
        st.dataframe(result['path_summary'].head(20),use_container_width=True)
with strategies:
    st.caption('Policy alternatives use the same return calibration and seed. Reserve policies can protect retained assets while increasing current payout shortfalls; inspect cumulative real payouts as well as terminal corpus.')
    alt_rate=st.number_input('Alternative spending rate (%)',value=4.,min_value=0.,max_value=100.)/100
    alt_buffer=st.number_input('Alternative reserve (years payout)',value=.5,min_value=0.)
    if results.get('policy_inputs') != (alt_rate,alt_buffer):
        results.pop('policies',None)
    if st.button('Compare spending and buffer policies'):
        execute('policies',lambda:compare_cases(data,policy_cases(cfg,inst,liq,alt_rate,alt_buffer),history))
        results['policy_inputs']=(alt_rate,alt_buffer)
    if 'policies' in results and results.get('policy_inputs')==(alt_rate,alt_buffer):
        table=results['policies'];st.dataframe(table,use_container_width=True)
        chart=table.copy();chart['Payout reliability (%)']=100*(1-chart['Pr(any payout funding shortfall)'])
        st.plotly_chart(px.scatter(chart,x='Payout reliability (%)',y='Median terminal real corpus ($M)',color='Scenario',
            hover_data=['Median cumulative real payouts ($M)','Annual return-coverage shortfall']),use_container_width=True)
    st.subheader('Data-backed allocation comparison')
    st.caption('Upload quarterly asset returns and alternate weights. The anchor and alternative are rebuilt from the same asset-return history. No distribution is reused after changing weights.')
    asset_file=st.file_uploader('Quarterly asset returns CSV (quarter + named asset columns)',type='csv')
    weights_file=st.file_uploader('Alternative weights CSV (asset, weight, liquidity_class)',type='csv')
    allocation_signature=repr((asset_file.getvalue() if asset_file else None,weights_file.getvalue() if weights_file else None))
    if results.get('allocation_signature') != allocation_signature:
        results.pop('allocations',None)
    if st.button('Compare allocations',disabled=not(asset_file and weights_file)):
        def allocation_run():
            assets=pd.read_csv(BytesIO(asset_file.getvalue()));weights=pd.read_csv(BytesIO(weights_file.getvalue()))
            anchor_h,al,ai=portfolio_from_assets(assets,data.p4_weights,data.condition_history)
            alt_h,bl,bi=portfolio_from_assets(assets,weights,data.condition_history)
            rows=[]
            for label,h,l,i in [('Rebuilt P4 anchor',anchor_h,al,ai),('Uploaded allocation',alt_h,bl,bi)]:
                rows.append(comparison_row(label,run_monte_carlo(data,cfg,inst,replace(liq,liquid_share=l,illiquid_share=i),p4_history=h,keep_paths=False)))
            return pd.DataFrame(rows)
        execute('allocations',allocation_run)
        results['allocation_signature']=allocation_signature
    if 'allocations' in results and results.get('allocation_signature')==allocation_signature:
        st.dataframe(results['allocations'],use_container_width=True)
with returns:
    st.caption('Single Normal, two-component Normal mixture and block bootstrap share the same institutional settings and fixed inflation. If inflation is historical, the comparison fixes it at the sample mean.')
    if st.button('Compare three return models'):
        execute('methods',lambda:compare_return_methods(data,cfg,inst,liq,p4_history=history))
    if 'methods' in results:
        table,parameters,cpi,detail=results['methods']
        st.write(f'Shared annual inflation: {cpi:.2%}')
        st.dataframe(table,use_container_width=True)
        distributions=pd.concat([r['annual_results'][['portfolio_return']].assign(Model=name) for name,r in detail.items()],ignore_index=True)
        st.plotly_chart(px.histogram(distributions,x='portfolio_return',color='Model',histnorm='probability density',barmode='overlay',opacity=.45,nbins=60,title='Simulated annual portfolio returns'),use_container_width=True)
        st.dataframe(pd.DataFrame([comparison_row(name,r) for name,r in detail.items()]),use_container_width=True)
    diagnostics,parameters=calibration_diagnostics(history)
    st.dataframe(diagnostics,use_container_width=True)
    st.json(parameters)
with stress:
    st.caption('Change scenario severities below. These are sensitivity assumptions, not forecasts.')
    a=st.number_input('Annual return shift in stress (pp)',value=-4.,min_value=-20.,max_value=20.)/100
    b=st.number_input('Stress inflation (%)',value=6.,min_value=-5.,max_value=30.)/100
    c=st.number_input('Spending increase (pp)',value=1.,min_value=0.,max_value=20.)/100
    d=st.slider('Stress liquid-access haircut',0.,1.,.5)
    e=st.slider('Stress forced-sale discount',0.,.95,.3)
    stress_signature=(a,b,c,d,e)
    if results.get('stress_inputs') != stress_signature:
        results.pop('stress',None)
    if st.button('Run stress comparison'):
        execute('stress',lambda:compare_cases(data,stress_cases(cfg,inst,liq,a,b,c,d,e),history))
        results['stress_inputs']=stress_signature
    if st.button('Run mixture probability / severity sensitivity'):
        execute('sensitivity',lambda:mixture_sensitivity(data,cfg,inst,liq,history))
    if 'stress' in results and results.get('stress_inputs')==stress_signature:
        render_stress_results(results['stress'],results.get('sensitivity'))
    elif 'sensitivity' in results:
        st.dataframe(results['sensitivity'],use_container_width=True)
with validation:
    st.caption('Historical reconstruction checks mechanics. Chronological holdout scores assess return distributions only; they do not validate institutional forecasts. Tail estimates require larger runs and seed stability.')
    if st.button('Run historical mechanics reconstruction'):
        execute('historical',lambda:historical_validation(data,replace(cfg,horizon_years=10,start_year=2013),inst,liq))
    if 'historical' in results:
        h=results['historical'];st.dataframe(h,use_container_width=True)
        st.write(f'Maximum absolute accounting residual ($M): {h.accounting_residual.abs().max():.3g}')
    if st.button('Run chronological holdout diagnostics'):
        execute('holdout',lambda:holdout_diagnostics(history))
    if 'holdout' in results:
        st.dataframe(results['holdout'],use_container_width=True)
    if st.button('Run seed and path-count stability check'):
        execute('stability',lambda:stability_check(data,cfg,inst,liq,history))
    if 'stability' in results:
        st.dataframe(results['stability'],use_container_width=True)
    if 'baseline' in results:
        r=results['baseline']
        for label,table in [('annual_results',r['annual_results']),('path_summary',r['path_summary']),('metrics',pd.DataFrame([r['metrics']]))]:
            st.download_button(f'Download {label}',table.to_csv(index=False),f'{label}.csv','text/csv')
    for key in ['policies','allocations','stress','sensitivity','stability','holdout']:
        if key in results:
            st.download_button(f'Download {key}',results[key].to_csv(index=False),f'{key}.csv','text/csv')
