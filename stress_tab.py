"""Focused stress-testing workflow with optional advanced tools."""
from dataclasses import asdict,replace
import json
import pandas as pd
import plotly.express as px
import streamlit as st
from dashboard_ui import style_figure,comparison_display
from scenario_stress import (InflationStress,LiquidityStress,framework_scenarios,scenario_library,
    StressScenario,MarketShock,EndowmentShock,run_stress_suite,reverse_stress_test,
    sensitivity_grid,asset_shock_table,EQUITY_CRASH_SHOCKS,market_portfolio_shock,replay_cumulative_return)


def invalidate(results,key,signature,outputs):
    if results.get(key)!=signature:
        for item in outputs:results.pop(item,None)
    results[key]=signature


def show_results(bundle,prefix):
    table,detail=bundle
    focus=[]
    for name,r in detail.items():
        m=r['metrics']
        focus.append({'Scenario':name,'Ending real ($M)':m['median_terminal_real_assets'],
            'Real payouts ($M)':m['median_total_real_payout'],
            'Unpaid payout risk':f"{m['probability_at_least_one_shortfall']:.1%}",
            'Support-gap risk':f"{m['probability_any_support_gap']:.1%}",
            'Mean sale loss ($M)':m['mean_forced_sale_loss']})
    st.dataframe(pd.DataFrame(focus).style.format({'Ending real ($M)':'{:.2f}','Real payouts ($M)':'{:.2f}','Mean sale loss ($M)':'{:.2f}'}),hide_index=True,use_container_width=True)
    measure=st.selectbox('Compare over time',['Annual real payout','Real endowment value'],key=prefix+'_chart')
    col='real_actual_payout' if measure=='Annual real payout' else 'real_ending_assets'
    paths=pd.concat([r['annual_results'].groupby('year')[col].median().reset_index().assign(Scenario=name)
        for name,r in detail.items()],ignore_index=True)
    fig=px.line(paths,x='year',y=col,color='Scenario',color_discrete_sequence=['#59C9BE','#E3B46D','#83AEE0','#C3A6E8'])
    style_figure(fig,measure+' ($M)');fig.update_xaxes(title='Year')
    st.plotly_chart(fig,use_container_width=True,key=prefix+'_plot')
    with st.expander('Results and downloads'):
        view=comparison_display(table)
        for col in ['Pr(forced sale)','Pr(unfunded capital call)','Pr(institutional support gap)']:
            if col in view:view[col]=view[col].map(lambda x:f'{x:.1%}')
        st.dataframe(view,hide_index=True,use_container_width=True)
        name=st.selectbox('Scenario details',list(detail),key=prefix+'_details')
        r=detail[name]
        columns=['actual_payout','real_actual_payout','real_ending_assets','operating_expenses',
            'payout_support_gap','forced_sale_loss','capital_call_paid','unpaid_capital_call']
        annual=r['annual_results'].groupby('year')[columns].median().reset_index()
        annual=annual.rename(columns={'year':'Year','actual_payout':'Payout ($M)','real_actual_payout':'Real payout ($M)',
            'real_ending_assets':'Real assets ($M)','operating_expenses':'Expenses ($M)',
            'payout_support_gap':'Support gap ($M)','forced_sale_loss':'Sale losses ($M)',
            'capital_call_paid':'Funded calls ($M)','unpaid_capital_call':'Unfunded calls ($M)'})
        st.dataframe(annual,hide_index=True,use_container_width=True)
        st.download_button('Download comparison',table.to_csv(index=False),prefix+'_comparison.csv','text/csv',key=prefix+'_comparison_download')
        st.download_button('Download annual paths',r['annual_results'].to_csv(index=False),prefix+'_annual_paths.csv','text/csv',key=prefix+'_paths_download')
        st.download_button('Download assumptions',json.dumps({n:asdict(v['scenario']) for n,v in detail.items()},indent=2),prefix+'_assumptions.json','application/json',key=prefix+'_settings_download')


def render_stress_panel(data,cfg,inst,liq,history,results,execute):
    st.subheader('Stress testing')
    left,right=st.columns(2)
    use_inflation=left.checkbox('High inflation & elevated rates',value=True)
    use_downturn=right.checkbox('Prolonged downturn & liquidity squeeze',value=True)
    with st.expander('Inflation and rates — settings'):
        a,b=st.columns(2)
        q=a.slider('Inflation stress duration (quarters)',4,24,16,help='Includes the initial four-quarter 2022 replay.')
        cpi=a.slider('Extra inflation after replay (percentage points)',0.,5.,1.4,.1)/100
        drag=a.slider('Return drag after replay (%)',-10.,0.,0.,.5)/100
        growth=b.slider('Annual expense growth during stress (%)',0.,15.,4.6,.1)/100
        ey=b.slider('Expense stress duration (years)',0,10,2)
        dy=b.slider('Return drag duration (years)',0,10,0)
    with st.expander('Downturn and liquidity — settings'):
        a,b=st.columns(2)
        rd=a.slider('Recovery return drag (%)',-10.,0.,-3.,.5)/100
        ry=a.slider('Recovery duration (years)',0,10,2)
        calls=a.slider('Annual capital calls (% of beginning assets)',0.,15.,2.,.5,help='Funded calls move cash into illiquid assets; this is a liquidity-pressure proxy, not an explicit delayed-distribution schedule.')/100
        cy=a.slider('Capital-call duration (years)',0,10,3)
        haircut=a.slider('Restricted liquid assets (%)',0.,100.,50.,5.)/100
        hy=a.slider('Liquidity restriction duration (years)',0,10,2)
        gifts=b.slider('Gifts as a share of normal (%)',0.,100.,88.,1.)/100
        gy=b.slider('Gift reduction duration (years)',0,10,2)
        reserve=b.slider('Cash reserve (years of payout)',0.,3.,1.,.25)
        discount=b.slider('Forced-sale discount (%)',0.,90.,30.,5.)/100
        sales=b.checkbox('Allow forced sales',value=True,key='stress_allow_sales')
    p1=InflationStress(q,cpi,growth,ey,drag,dy)
    p2=LiquidityStress(rd,ry,gifts,gy,calls,cy,haircut,hy,reserve,discount,sales)
    scenarios=framework_scenarios(inst,p1,p2)
    selected=[sc for sc,enabled in zip(scenarios,[use_inflation,use_downturn]) if enabled]
    n=st.selectbox('Paths per scenario',[100,500,1000,2000,5000],index=1,key='main_stress_paths')
    scfg=replace(cfg,n_sims=n)
    signature=(repr([asdict(s) for s in selected]),n)
    invalidate(results,'main_stress_inputs',signature,['main_stress','stress'])
    if st.button('Run stress tests',type='primary'):
        results.pop('stress',None)
        if selected:
            execute('main_stress',lambda:run_stress_suite(data,scfg,inst,liq,selected,history))
            if 'main_stress' in results:results['stress']=results['main_stress'][0]
        else:st.info('Select at least one stress scenario.')
    if 'main_stress' in results:show_results(results['main_stress'],'main_stress')

    st.divider()
    if not st.toggle('Additional scenarios and tools',value=False):return
    library=scenario_library()
    with st.expander('Scenario library'):
        rows=[]
        for name,sc in library.items():
            instant=market_portfolio_shock(data,sc.market)
            replay=None
            if sc.market.replay_quarters:
                try:replay=replay_cumulative_return(data,sc.market.replay_quarters,history)
                except (KeyError,ValueError):pass
            rows.append({'Scenario':name,'Type':sc.category,'Initial shock':f'{instant:.1%}' if instant else '—',
                'Replay return':f'{replay:.1%}' if replay is not None else '—'})
        st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
    with st.expander('Asset shock contributions'):
        asset=asset_shock_table(data,EQUITY_CRASH_SHOCKS)
        st.dataframe(asset.style.format({'weight':'{:.1%}','shock':'{:.1%}','contribution':'{:.2%}'}),hide_index=True,use_container_width=True)
    with st.expander('Custom scenario'):
        a,b=st.columns(2)
        loss=a.slider('Initial portfolio loss (%)',0.,90.,20.,5.)/100
        duration=a.slider('Custom duration (years)',1,10,3)
        cd=a.slider('Custom annual return drag (%)',-10.,0.,-3.,.5)/100
        ci=b.slider('Custom inflation increase (percentage points)',0.,10.,2.,.5)/100
        spend=b.slider('Additional spending (percentage points)',0.,5.,0.,.25)/100
        gift=b.slider('Custom gift reduction (%)',0.,100.,0.,5.)/100
        library['Custom scenario']=StressScenario('Custom scenario','Custom','Custom market and funding assumptions.',
            MarketShock(portfolio_shock=-loss,return_drag_annual=cd,drag_years=duration,inflation_add=ci,inflation_years=duration),
            EndowmentShock(spending_rate_add=spend,spending_years=duration,gift_multiplier=1-gift,gift_years=duration))
    names=st.multiselect('Additional scenarios',[x for x in library if x!='Baseline'],default=['GFC replay (2008Q1-2009Q2)','Equity crash (asset-class shock)'])
    extra=[library[x] for x in names]
    en=st.selectbox('Paths per additional scenario',[100,500,1000,2000,5000],index=1)
    invalidate(results,'extra_stress_inputs',(repr([asdict(s) for s in extra]),en),['extra_stress'])
    if st.button('Run additional scenarios'):
        if extra:execute('extra_stress',lambda:run_stress_suite(data,replace(cfg,n_sims=en),inst,liq,extra,history))
        else:st.info('Select at least one scenario.')
    if 'extra_stress' in results:show_results(results['extra_stress'],'extra_stress')
    with st.expander('Reverse stress test'):
        base_name=st.selectbox('Starting scenario',list(library))
        target=st.slider('Minimum ending real value (% of starting endowment)',10,100,80)/100
        sig=(repr(asdict(library[base_name])),target)
        invalidate(results,'reverse_inputs',sig,['reverse_stress'])
        if st.button('Find breaking point'):
            execute('reverse_stress',lambda:reverse_stress_test(data,cfg,inst,liq,target,library[base_name],history))
        if 'reverse_stress' in results:
            r=results['reverse_stress'];v=r['breaking_shock']
            if pd.isna(v):st.write('No breach found up to an additional 95% initial loss.')
            elif v==0:st.write('The target is already breached without an additional loss.')
            else:st.metric('Additional initial loss to breach target',f'{abs(v):.1%}')
            st.caption('Deterministic estimate; not a probability.')
            if not r.get('monotone_scan',True):st.caption('Non-monotone results: the first grid-detected breach is shown.')
    with st.expander('Market loss × spending rate'):
        if st.button('Run spending sensitivity'):
            execute('stress_grid',lambda:sensitivity_grid(data,cfg,inst,liq,p4_history=history))
        if 'stress_grid' in results:
            grid=results['stress_grid'];v=grid.copy();v.index=[f'{x:.0%}' for x in v.index];v.columns=[f'{x:.2%}' for x in v.columns]
            st.dataframe(v.style.format('{:.1%}'),use_container_width=True)
            st.caption('Deterministic ending real value as a percentage of starting endowment.')
            st.download_button('Download sensitivity',grid.to_csv(),'spending_sensitivity.csv','text/csv')
