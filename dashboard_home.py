"""Dashboard summaries and navigation; no simulation runs on card clicks."""
import base64
from html import escape
import streamlit as st
from dashboard_ui import chart_theme


def detail_key(key):
    key='detail_input_'+str(key)
    registry=st.session_state.setdefault('_detail_input_keys',[])
    if key not in registry:
        registry.append(key)
    return key


def keep_detail_inputs():
    # Interrupt Streamlit's cleanup only for explicitly registered input keys.
    for key in st.session_state.get('_detail_input_keys',[]):
        if key in st.session_state:
            st.session_state[key]=st.session_state[key]


def open_detail(view):
    st.session_state['dashboard_view']=view


def _bars(rows, percent=False):
    palette=chart_theme()
    maximum=max([abs(v) for _,v in rows]+[.001])
    height=max(120,30*len(rows))
    parts=[]
    for i,(label,value) in enumerate(rows):
        y=8+30*i
        shown=label if len(label)<23 else label[:21]+'…'
        val=f'{value:.1%}' if percent else f'${value:,.1f}M'
        parts.append(f'<text x="0" y="{y+12}" fill="{palette["text"]}" font-size="11">{escape(shown)}</text>')
        parts.append(f'<rect x="148" y="{y+2}" width="{max(0,90*value/maximum):.2f}" height="13" rx="2" fill="{palette["colors"][0]}"/>')
        parts.append(f'<text x="302" y="{y+12}" fill="{palette["text"]}" font-size="11" text-anchor="end">{escape(val)}</text>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 310 {height}" font-family="Arial">'+''.join(parts)+'</svg>'


def _payout_chart(annual):
    palette=chart_theme()
    f=annual.groupby('year').real_actual_payout.quantile([.1,.5,.9]).unstack()
    low,mid,high=(f[q].tolist() for q in [.1,.5,.9])
    bottom,top=min(low),max(high)
    pad=max((top-bottom)*.12,.1);bottom-=pad;top+=pad
    x=lambda i:42+252*i/max(1,len(mid)-1)
    y=lambda v:113-94*(v-bottom)/(top-bottom)
    path=lambda values:' '.join(f'{x(i):.2f},{y(v):.2f}' for i,v in enumerate(values))
    poly=path(low)+' '+' '.join(f'{x(i):.2f},{y(high[i]):.2f}' for i in range(len(high)-1,-1,-1))
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 310 140" font-family="Arial">'
        f'<text x="2" y="22" fill="{palette["text"]}" font-size="11">${max(high):.1f}M</text>'
        f'<text x="2" y="113" fill="{palette["text"]}" font-size="11">${min(low):.1f}M</text>'
        f'<polygon points="{poly}" fill="{palette["colors"][0]}" opacity=".18"/>'
        f'<polyline points="{path(mid)}" fill="none" stroke="{palette["colors"][0]}" stroke-width="2.5"/>'
        f'<text x="42" y="136" fill="{palette["text"]}" font-size="11">{int(f.index[0])}</text>'
        f'<text x="294" y="136" text-anchor="end" fill="{palette["text"]}" font-size="11">{int(f.index[-1])}</text></svg>')


def render_home(results,cfg,inst,liq,history,data,changed=False):
    import pandas as pd
    import plotly.express as px
    from dashboard_ui import band_chart, style_figure, risk_table, comparison_display
    baseline=results.get('baseline')
    if changed and not baseline:
        st.info('Inputs changed. Run the analysis to refresh the results.')
    st.caption('Liquidity and stress assumptions are provisional. See the assumptions panel for current values and sources.')
    left,right=st.columns([.8,2.1],gap='large')
    with left:
        st.subheader('Inputs behind this run')
        with st.expander('Portfolio · R1',expanded=True):
            st.write(data.portfolio_label)
            w=data.portfolio_weights[['asset_name','weight']].rename(columns={'asset_name':'Asset','weight':'Weight'})
            st.dataframe(w.style.format({'Weight':'{:.1%}'}),hide_index=True,use_container_width=True,height=490)
        with st.expander('Institution · R2'):
            st.metric('Annual expense growth',f'{inst.annual_expense_growth:.2%}')
            st.metric('Gifts / beginning assets',f'{inst.gift_rate:.2%}')
            st.metric('Endowment support / expenses',f'{inst.support_ratio:.2%}')
            st.caption('Base cohort medians. Edit values in Advanced options above.')
        with st.expander('Spending & liquidity'):
            st.write(f'{inst.effective_spending_rate:.2%} of '+('beginning assets' if inst.spending_rule=='Current assets' else 'the trailing three-year average'))
            st.write(f'{liq.time_to_cash_months} months to raise cash. Cash first, then eligible asset sales.')
            st.caption('No additional cash reserve. Private and hedge fund sales are excluded pending confirmed access terms.')
        st.markdown('**Explore the model**')
        for view,label in [('stress','Stress testing'),('strategies','Spending comparisons'),('returns','Return assumptions'),('checks','Model checks'),('data','Data & downloads')]:
            st.button(label+' →',key='open_'+view,on_click=open_detail,args=(view,),use_container_width=True)
    with right:
        with st.expander('Assumptions behind this run'):
            st.write(f'{cfg.n_sims:,} simulations · {cfg.horizon_years} years from {cfg.start_year} · {cfg.return_method}')
            st.write(f'Inflation: {cfg.annual_inflation:.1%} annually' if cfg.annual_inflation is not None else 'Inflation sampled from historical conditions.')
            st.caption('Annual funding model; aggregate returns are applied to all liquidity groups. Matrix discounts are illustrative, not sourced estimates. No full institutional revenue budget is modeled.')
        if not baseline:
            st.info('Run analysis to populate the funding, purchasing-power and liquidity results. No illustrative results are shown.')
            return
        ar=baseline['annual_results'];m=baseline['metrics']
        last=ar[ar.year==ar.year.max()]
        first=ar[ar.year==ar.year.min()]
        initial_payout=float(first.planned_payout.iloc[0])
        terminal=last.real_actual_payout.median()
        st.markdown('### What the results mean')
        st.write(f"The median final-year payout is **${terminal:,.1f}M in starting-year dollars**, compared with an initial planned payout of **${initial_payout:,.1f}M**. "
            f"In **{m['probability_at_least_one_shortfall']:.1%}** of simulated paths, at least one planned payout cannot be fully funded.")
        st.markdown('### Will the payout hold?')
        a,b,c=st.columns(3)
        a.metric('Any unpaid payout',f"{m['probability_at_least_one_shortfall']:.1%}",help='At least one year with actual payout below plan. This is not real payout-cut probability.')
        b.metric('Final-year real payout',f'${terminal:,.1f}M')
        c.metric('Downside real payout',f'${last.real_actual_payout.quantile(.05):,.1f}M',help='5th percentile in the final year.')
        st.markdown('### Will purchasing power remain?')
        a,b,c=st.columns(3)
        a.metric('Any-year principal erosion',f"{m['probability_real_corpus_erosion']:.1%}",help='Real assets below the selected fraction of starting assets at any year end.')
        b.metric('Final real endowment',f"${m['median_terminal_real_assets']:,.1f}M")
        c.metric('Institutional support gap',f"{m['probability_any_support_gap']:.1%}",help='Any year with payout below expenses times the support ratio; not a full budget-deficit measure.')
        st.markdown('### Can cash needs be met?')
        a,b,c=st.columns(3)
        a.metric('Paths needing asset sales',f"{ar.groupby('path_id').forced_sale.sum().gt(1e-10).mean():.1%}")
        b.metric('Mean total sale cost',f"${ar.groupby('path_id').forced_sale_loss.sum().mean():,.3f}M")
        c.metric('Median ending cash',f'${last.ending_cash.median():,.1f}M')
        st.caption('Asset sales include public securities; a sale is not automatically a payout shortfall.')
        for col,title,initial,label,ref in [('real_actual_payout','Annual payout in today’s dollars',initial_payout,'Median real payout','Initial planned payout'),
            ('real_ending_assets','Endowment purchasing power',cfg.initial_endowment,'Median real endowment','Starting principal')]:
            with st.container(border=True):
                st.subheader(title)
                st.plotly_chart(band_chart(ar,col,initial,cfg.start_year,label,ref),use_container_width=True,key='home_'+col)
        with st.container(border=True):
            st.subheader('Planned versus funded payout')
            funding=ar.groupby('year')[['planned_payout','actual_payout']].mean().reset_index()
            fig=px.line(funding,x='year',y=['planned_payout','actual_payout'],labels={'value':'Payout ($M)','variable':'Payout'})
            style_figure(fig,'Mean nominal payout ($M)')
            st.plotly_chart(fig,use_container_width=True,key='home_funding')
            st.caption('Mean nominal amounts across simulations. The gap is the unpaid portion.')
        with st.expander('For the analyst · risk measures and definitions'):
            st.dataframe(risk_table(m),hide_index=True,use_container_width=True)
        if 'stress' in results:
            st.subheader('Stress tests compared')
            st.dataframe(comparison_display(results['stress']),hide_index=True,use_container_width=True)
        if 'policies' in results:
            with st.expander('Spending policies compared'):
                st.dataframe(comparison_display(results['policies']),hide_index=True,use_container_width=True)
