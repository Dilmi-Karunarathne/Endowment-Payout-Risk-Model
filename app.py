from r1_model import STRATEGIES, REGIMES
from dashboard_home import detail_key
"""Endowment planning dashboard."""
from dataclasses import asdict, replace
from io import BytesIO
from pathlib import Path
import json
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from endowment_simulation_model import (SimulationConfig, load_default_data,
    institutional_params_from_data, liquidity_params_from_data, run_monte_carlo, historical_validation)
from portfolio_return_simulation import compare_return_methods, fit_mixture, checked_history
from strategy_analysis import policy_cases, compare_cases, comparison_row
from validation import calibration_diagnostics, holdout_diagnostics, stability_check
from dashboard_home import keep_detail_inputs, open_detail
from stress_tab import primary_stress_inputs, primary_stress_signature
from scenario_stress import run_stress_suite
from dashboard_ui import apply_style, band_chart, style_figure, risk_table, comparison_display

st.set_page_config(page_title='Endowment Payout Risk',page_icon="icon/GSU-logo.jpg",layout='wide')
apply_style()
st.title('Endowment Payout Risk Lab')
st.markdown('<p class="intro">Explore how investment and spending choices shape university funding.</p>',unsafe_allow_html=True)

keep_detail_inputs()
if "r2_severity" in st.session_state:
    st.session_state["r2_severity"]=st.session_state["r2_severity"]
view=st.session_state.setdefault('dashboard_view','overview')
if view=='home':
    view=st.session_state['dashboard_view']='overview'
navigation=[('overview','Simulate'),('paths','Paths'),('strategies','Compare'),
            ('stress','Stress tests'),('returns','Return models'),('data','Method'),('checks','Checks')]
for column,(page,label) in zip(st.columns(len(navigation)),navigation):
    column.button(label,key='nav_'+page,type='primary' if view==page else 'secondary',
                  on_click=open_detail,args=(page,),use_container_width=True)

@st.cache_data
def get_data(institution="Private", allocation="High Inflation", strategy="HRP"):
    return load_default_data(institution_type=institution, allocation=allocation,strategy=strategy)

@st.cache_data
def fit_history(values):
    return fit_mixture(np.asarray(values))

@st.cache_data
def diagnostics_for_history(history):
    return calibration_diagnostics(history)

data=get_data()
base=SimulationConfig(return_method='R1 dynamic asset bootstrap',n_sims=1000)
inst=institutional_params_from_data(data)
liq=liquidity_params_from_data(data)
history=data.portfolio_quarterly
source_key='default'
allocation_matrix=None

def number(label,value,**kwargs):
    return st.number_input(label,value=float(value),key=detail_key(kwargs.pop('input_key',source_key+label)),**kwargs)

with st.sidebar:
    st.subheader('Your endowment')
    basic=st.container()
    advanced=st.expander('Advanced options')
    with basic:
        institution_type=st.selectbox('Institution',['Private','Public'],index=['Private','Public'].index(inst.institution_type),key=detail_key('institution_'+source_key))
    with basic:
        strategy=st.selectbox('Portfolio strategy',STRATEGIES,index=STRATEGIES.index('HRP'),key=detail_key('r1_strategy'))
        allocation=st.selectbox('Starting allocation regime',REGIMES,index=2,key=detail_key('r1_start'),help='High Inflation is R1’s August 2026 handoff state, not a forecast for 2027.')
    data=get_data(institution_type,allocation,strategy)
    history=data.portfolio_quarterly
    liq=liquidity_params_from_data(data)
    scenario='Base'
    inst=institutional_params_from_data(data,institution_type,scenario)
    source_key+=institution_type+scenario
    with basic:
        initial=number('Starting endowment ($M)',base.initial_endowment,min_value=1.,step=5.,format='%.1f')
        rule=st.selectbox('Spending rule',['Trailing average','Current assets'],format_func=lambda x:'Three-year average' if x=='Trailing average' else 'Beginning-of-year value',key=detail_key('app.py:78:selectbox'))
        spending=number('Annual spending rate (%)',inst.effective_spending_rate*100,min_value=0.,max_value=100.,step=.1,format='%.2f')/100
        years=st.slider('Projection horizon (years)',1,30,5,key=detail_key('app.py:80:slider'))
        run=st.button('Run analysis',type='primary',use_container_width=True)
    with advanced:
        st.markdown('**Simulation**')
        n=st.select_slider('Simulation paths',options=[100,500,1000,2000,5000,10000],value=1000,key=detail_key('app.py:84:select_slider'))
        seed=st.number_input('Random seed',min_value=0,value=42,step=1,key=detail_key('app.py:85:number_input'))
        start=st.number_input('Start year',min_value=2000,max_value=2100,value=2027,step=1,key=detail_key('app.py:86:number_input'))
        method='R1 dynamic asset bootstrap'
        st.caption('Joint asset and inflation bootstrap · quarterly dynamic allocations')
        block=st.slider('Bootstrap block (quarters)',1,min(8,len(history)),4,disabled=False,key=detail_key('app.py:88:slider'))
        alpha=st.slider('Risk confidence level',.90,.99,.95,.01,key=detail_key('app.py:89:slider'))
        threshold=st.slider('Principal threshold (% of starting value)',50,100,100,key=detail_key('app.py:90:slider'))/100
        st.markdown('**Inflation and returns**')
        fixed=st.checkbox('Use fixed inflation',value=False,key=detail_key('app.py:92:checkbox'))
        inflation=st.number_input('Annual inflation (%)',value=2.5,min_value=-5.,max_value=30.,step=.1,disabled=not fixed,key=detail_key('app.py:93:number_input'))/100
        shift=st.number_input('Annual mean-return adjustment (pp)',value=0.,min_value=-20.,max_value=20.,step=.5,key=detail_key('app.py:94:number_input'))/100
        vol=st.number_input('Volatility multiplier',value=1.,min_value=.1,max_value=3.,step=.1,key=detail_key('app.py:95:number_input'))
        p=adverse_mean=adverse_std=None
        if 'mixture' in method.lower():
            fitted=fit_history(tuple(history.portfolio_return.astype(float)))
            override=st.checkbox('Customize adverse-return assumptions',key=detail_key('app.py:99:checkbox'))
            if override:
                p=st.number_input('Adverse-quarter probability (%)',value=float(fitted['adverse_probability']*100),min_value=0.,max_value=100.,key=detail_key('app.py:101:number_input'))/100
                adverse_mean=st.number_input('Adverse quarterly mean (%)',value=float(fitted['adverse_mean']*100),min_value=-50.,max_value=30.,key=detail_key('app.py:102:number_input'))/100
                adverse_std=st.number_input('Adverse quarterly volatility (%)',value=float(fitted['adverse_std']*100),min_value=.01,max_value=50.,key=detail_key('app.py:103:number_input'))/100
        st.markdown('**Spending details**')
        st.caption('R2 payout collar: 3%–5% of beginning endowment. Annual growth limits below are optional additional rules.')
        use_prior=st.checkbox('Use past endowment values',value=False,key=detail_key('past_'+source_key))
        prior2=prior1=initial
        if use_prior:
            prior2=number('Endowment two years earlier ($M)',base.prior_endowment_2y,min_value=1.)
            prior1=number('Endowment one year earlier ($M)',base.prior_endowment_1y,min_value=1.)
        smoothing=3
        collar=st.checkbox('Limit annual payout changes',key=detail_key('app.py:111:checkbox'))
        floor=cap=None
        if collar:
            floor=st.number_input('Minimum annual payout change (%)',value=-5.,min_value=-100.,key=detail_key('app.py:114:number_input'))/100
            cap=st.number_input('Maximum annual payout change (%)',value=5.,min_value=-100.,key=detail_key('app.py:115:number_input'))/100
        with st.expander('Enrollment and tuition assumptions'):
            enrollment_override=st.number_input('Annual enrollment growth (%)',value=float(inst.enrollment_growth*100),min_value=-99.,key='enrollment_'+source_key)/100
            discount_override=st.number_input('Annual tuition discount increase (percentage points)',value=float(inst.tuition_discount_change*100),key='discount_'+source_key)/100
            inst=replace(inst,enrollment_growth_override=enrollment_override,tuition_discount_change_override=discount_override)
        gifts=number('Annual gifts (% of beginning assets)',inst.gift_rate*100,min_value=0.)/100
        changes=number('Other endowment changes (%)',inst.other_changes_rate*100)/100
        expenses=number('Expenses / initial endowment',inst.expenses_to_endowment_ratio,min_value=0.)
        expense_growth=number('Annual expense growth (%)',inst.annual_expense_growth*100,min_value=-100.)/100
        support=number('Required endowment support (% of expenses)',inst.support_ratio*100,min_value=0.)/100
        st.markdown('**Liquidity monitoring**')
        st.caption('Minimum liquid share: 40%. Liquid assets should cover 3 years of payout. Breaches do not automatically reduce payouts.')
        other=number('Other annual cash needs ($M)',liq.other_annual_cash_need,min_value=0.)
        liq=replace(liq,other_annual_cash_need=other)
        st.caption('Near breach: within 10% above either threshold; this warning margin is provisional.')


cfg=replace(base,initial_endowment=initial,prior_endowment_2y=prior2,prior_endowment_1y=prior1,
    horizon_years=years,start_year=int(start),n_sims=int(n),seed=int(seed),alpha=alpha,return_method=method,
    block_size_quarters=block,annual_return_shift=shift,volatility_multiplier=vol,
    annual_inflation=inflation if fixed else None,adverse_probability=p,adverse_mean=adverse_mean,
    adverse_std=adverse_std,real_corpus_threshold=threshold)
inst=replace(inst,effective_spending_rate=spending,gift_rate=gifts,other_changes_rate=changes,
    expenses_to_endowment_ratio=expenses,annual_expense_growth=expense_growth,support_ratio=support,
    spending_rule=rule,smoothing_years=smoothing,annual_payout_growth_floor=floor,annual_payout_growth_cap=cap)
settings={'config':asdict(cfg),'institution':asdict(inst),'liquidity':asdict(liq),
    'portfolio_source':data.portfolio_metadata}
st.caption(f'Active portfolio: {data.portfolio_label} · {len(history)} complete quarters · R2 median institutional inputs')
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

# Comparison assumptions are shared with the detail widgets, even when the
# detail page has never been opened. All main cards belong to one analysis run.
alt_rate=st.session_state.get('detail_input_app.py:200:number_input',4.)/100
alt_buffer=0.
policy_inputs=(alt_rate,alt_buffer)
if results.get('policy_inputs')!=policy_inputs:
    results.pop('policies',None)
stress_context=(institution_type,strategy,allocation,st.session_state.get('r2_severity','Standard'))
if st.session_state.get('r1_stress_context')!=stress_context:
    for line in [64,65,66,67,68,69,72,73,74,75,76,77,78,79]:
        st.session_state.pop('detail_input_stress_tab.py:'+str(line)+':slider',None)
    private_weight=data.portfolio_weights.loc[data.portfolio_weights.asset.isin(['private_equity','venture_capital']),'weight'].sum()
    st.session_state['r1_calls_default']=(.03 if stress_context[-1]=='Severe' else .02)*private_weight/.128
    w=data.portfolio_weights.set_index('asset').weight
    st.session_state['r1_haircut_default']=float(w[['emerging_markets','investment_grade_corporate_bonds','high_yield_fixed_income']].sum()/liq.liquid_share) if stress_context[-1]=='Severe' else 0.
    st.session_state['r1_stress_context']=stress_context
stress_signature=primary_stress_signature(inst,cfg.n_sims)
if results.get('main_stress_inputs')!=stress_signature:
    results.pop('main_stress',None)
    results.pop('stress',None)

if run:
    selected=primary_stress_inputs(inst)
    jobs=[
        ('baseline','Payout and purchasing power',lambda:run_monte_carlo(data,cfg,inst,liq,portfolio_history=history)),
        ('policies','Spending-policy comparison',lambda:compare_cases(data,policy_cases(cfg,inst,liq,alt_rate,alt_buffer),history,baseline_result=results.get('baseline'))),
        ('main_stress','Stress scenarios',lambda:run_stress_suite(data,cfg,inst,liq,selected,history,baseline_result=results.get('baseline'))),

    ]
    progress=st.progress(0,text='Starting all dashboard analyses…')
    for index,(key,label,fn) in enumerate(jobs):
        progress.progress(index/len(jobs),text=label+'…')
        if key not in results:
            execute(key,fn)
    results['policy_inputs']=policy_inputs
    results['main_stress_inputs']=stress_signature
    if 'main_stress' in results:
        results['stress']=results['main_stress'][0]
    progress.empty()
    failed=[label for key,label,_ in jobs if key not in results]
    if failed:
        st.warning('Some analyses could not be completed: '+', '.join(failed)+'. No previous results are reused.')
    else:
        st.success('Analysis complete. Baseline, policy comparison and primary stress tests are updated.')

if view=='overview':
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
        d,e,f=st.columns(3)
        d.metric('Liquidity constraint breach',f"{m['probability_liquidity_breach']:.1%}")
        e.metric('Real payout-cut risk (>5%)',f"{m['probability_real_payout_cut']:.1%}")
        f.metric('Real payout growth volatility',f"{m['median_payout_volatility']:.1%}")
        st.caption('Cut risk compares consecutive projected annual real payouts; year 1 has no preceding observed payout. Liquidity risk is monitored separately from payout execution.')
        initial_payout=float(annual.loc[annual.path_id==0,'planned_payout'].iloc[0])
        left,right=st.columns(2)
        with left:
            st.subheader('How much purchasing power remains?')
            st.plotly_chart(band_chart(annual,'real_ending_assets',initial,cfg.start_year,'Median real endowment','Starting principal'),use_container_width=True)
        with right:
            st.subheader('Can the university maintain its annual funding?')
            st.plotly_chart(band_chart(annual,'real_actual_payout',initial_payout,cfg.start_year,'Median real payout','Initial planned payout'),use_container_width=True)
        a,b=st.columns(2)
        a.metric('Median ending real endowment',f"${m['median_terminal_real_assets']:,.1f}M")
        b.metric('Median total real payouts',f"${m['median_cumulative_real_payout']:,.1f}M")
        with st.expander('Liquidity monitoring details'):
            columns=['minimum_liquid_share','minimum_liquidity_coverage','liquidity_breach','liquidity_near_breach','liquidity_deficit']
            st.dataframe(annual.groupby('year')[columns].mean().reset_index(),hide_index=True)
            st.caption('Mean values across paths. Breaches are checked at quarterly start/end and after annual flows. Deficit is measured after annual flows, in $M. No liquidation costs or borrowing are modeled.')
        with st.expander('Explore risk measures'):
            st.dataframe(risk_table(m),hide_index=True,use_container_width=True)
        with st.expander('View individual simulation outcomes'):
            st.dataframe(result['path_summary'],hide_index=True,use_container_width=True)

if view=='paths':
    st.subheader('Individual simulation outcomes')
    if 'baseline' not in results:
        st.info('Select Run analysis to generate simulation paths.')
    else:
        st.dataframe(results['baseline']['path_summary'],hide_index=True,use_container_width=True)
        st.subheader('Annual outcomes by path')
        st.dataframe(results['baseline']['annual_results'],hide_index=True,use_container_width=True)

if view=='strategies':
    st.subheader('Compare portfolio strategies')
    st.caption('Same market draws, starting regime and institutional assumptions across all nine strategies.')
    if st.button('Compare all nine portfolios',type='primary'):
        def compare_r1():
            rows=[]
            for name in STRATEGIES:
                d=get_data(institution_type,allocation,name)
                l=replace(liquidity_params_from_data(d),other_annual_cash_need=liq.other_annual_cash_need)
                result=run_monte_carlo(d,cfg,inst,l,keep_paths=False)
                rows.append(comparison_row(name,result))
            return pd.DataFrame(rows)
        execute('r1_comparison',compare_r1)
    if 'r1_comparison' in results:
        st.dataframe(comparison_display(results['r1_comparison']),hide_index=True,use_container_width=True)
        st.download_button('Download portfolio comparison',results['r1_comparison'].to_csv(index=False),'r1_comparison.csv','text/csv')
    st.subheader('Compare spending policies')
    left,right=st.columns(2)
    alt_rate=left.number_input('Compare spending rate (%)',value=4.,min_value=0.,max_value=100.,key=detail_key('app.py:200:number_input'))/100
    alt_buffer=0.
    if results.get('policy_inputs')!=(alt_rate,alt_buffer):
        results.pop('policies',None)
    if st.button('Compare policies',type='primary'):
        execute('policies',lambda:compare_cases(data,policy_cases(cfg,inst,liq,alt_rate,alt_buffer),history,baseline_result=results.get('baseline')))
        results['policy_inputs']=(alt_rate,alt_buffer)
    if 'policies' in results:
        table=results['policies']
        chart=table.copy();chart['Payout reliability (%)']=100*(1-chart['Pr(any payout funding shortfall)'])
        fig=px.scatter(chart,x='Payout reliability (%)',y='Median terminal real corpus ($M)',color='Scenario',
            hover_data=['Median cumulative real payouts ($M)'],size_max=16)
        style_figure(fig,'Ending real endowment ($M)');fig.update_xaxes(title='Payout reliability (%)');fig.update_traces(marker_size=14)
        st.plotly_chart(fig,use_container_width=True)
        st.dataframe(comparison_display(table),hide_index=True,use_container_width=True)
    with st.expander('R2 input sensitivity (P25 / median / P75)'):
        fields={'Gift rate':'gift_rate','Spending rate':'effective_spending_rate',
                'Required support / expenses':'support_ratio','Expenses / endowment':'expenses_to_endowment_ratio',
                'Expense growth':'annual_expense_growth'}
        field_label=st.selectbox('Vary one institutional input',list(fields),key=detail_key('r2_sensitivity_field'))
        field=fields[field_label]
        st.caption('Only the selected input changes; all other settings and the chosen portfolio are held fixed. Percentiles are sensitivity values, not university cohorts.')
        if results.get('r2_sensitivity_field')!=field:
            results.pop('r2_sensitivity',None)
        if st.button('Run input sensitivity'):
            def sensitivity_run():
                rows=[]
                for level,label in [('Low','P25'),('Base','Median'),('High','P75')]:
                    value=getattr(institutional_params_from_data(data,institution_type,level),field)
                    result=run_monte_carlo(data,cfg,replace(inst,**{field:value}),liq,portfolio_history=history,keep_paths=False)
                    row=comparison_row(label,result)
                    row['Input value']=value
                    row['Pr(any support gap)']=result['metrics']['probability_any_support_gap']
                    rows.append(row)
                return pd.DataFrame(rows)
            execute('r2_sensitivity',sensitivity_run)
            results['r2_sensitivity_field']=field
        if 'r2_sensitivity' in results:
            st.dataframe(comparison_display(results['r2_sensitivity']),hide_index=True,use_container_width=True)

if view=='stress':
    from stress_tab import render_stress_panel
    render_stress_panel(data,cfg,inst,liq,history,results,execute)

if view=='returns':
    st.subheader('Historical return-model diagnostics')
    st.caption('These simplified portfolio-return models use R1’s historical strategy series. They do not reproduce the dynamic asset engine and are diagnostic comparisons only.')
    if st.button('Compare return models',type='primary'):
        execute('methods',lambda:compare_return_methods(data,cfg,inst,liq,portfolio_history=history))
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

if view=='data':
    st.subheader('R1 portfolio strategies')
    st.caption('Nine strategies · 13 assets · four economic regimes. Public MeanCVaR uses Private targets provisionally.')
    selection=data.portfolio_weights
    st.dataframe(data.r1_targets.T.style.format('{:.2%}'),use_container_width=True)
    st.download_button('Download forward targets',Path(__file__).with_name('data').joinpath('r1/forward_weights_by_regime.csv').read_bytes(),'r1_forward_targets.csv','text/csv')
    with st.expander('Selected portfolio used in simulations'):
        weights=data.portfolio_weights[['asset_name','weight','liquidity_class']].rename(columns={'asset_name':'Asset','weight':'Allocation','liquidity_class':'Liquidity'}).copy()
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
    for key in ['policies','stress','sensitivity','r2_sensitivity','stability','holdout']:
        if key in results:
            st.download_button(f'Download {key}',results[key].to_csv(index=False),f'{key}.csv','text/csv')

if view=='checks':
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

if view == 'overview' and 'baseline' in results:
    baseline_result=results['baseline']
    if isinstance(baseline_result,dict) and 'annual_results' in baseline_result:
        with st.expander('University operating budget'):
            st.caption('Revenue grows at normal R2 rates during expense stress pending clarification. Deficits do not trigger automatic extra endowment withdrawals.')
            st.dataframe(baseline_result['annual_results'].groupby('year')[['net_tuition','other_operating_revenue','actual_payout','operating_expenses','operating_balance']].median(),use_container_width=True)
