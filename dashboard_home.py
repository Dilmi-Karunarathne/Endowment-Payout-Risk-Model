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
    from dashboard_ui import band_chart, style_figure, risk_table
    st.markdown(f'<div class="context-strip"><b>${cfg.initial_endowment:,.0f}M</b> endowment &nbsp; · &nbsp; <b>{escape(inst.institution_type)}</b> institution &nbsp; · &nbsp; <b>{escape(data.portfolio_metadata["strategy"])}</b> portfolio &nbsp; · &nbsp; <b>{inst.effective_spending_rate:.2%}</b> spending &nbsp; · &nbsp; {cfg.horizon_years} years · {cfg.n_sims:,} paths</div>',unsafe_allow_html=True)
    baseline=results.get('baseline')
    if not baseline:
        if changed: st.info('Inputs changed. Run analysis to refresh your results.')
        st.markdown('<div class="empty-state"><h2>Explore what your endowment can support.</h2><p>Choose an institution, portfolio and spending policy on the left, then select <b>Run analysis</b>.</p><p>Compare funding needs, purchasing power and liquidity across simulated outcomes.</p></div>',unsafe_allow_html=True)
        a,b,c=st.columns(3)
        a.metric('Return-coverage shortfall','—')
        b.metric('Liquidity constraint breach','—')
        c.metric('Real principal erosion','—')
        return
    m=baseline['metrics'];annual=baseline['annual_results'];summary=baseline['path_summary']
    a,b,c=st.columns(3)
    a.metric('Return-coverage shortfall',f"{m['annual_coverage_shortfall_probability']:.1%}",help='Share of simulated years when investment gains are below the planned payout. This is not a missed-payout probability.')
    a.caption('Years when investment gains do not cover planned payout')
    b.metric('Liquidity constraint breach',f"{m['probability_liquidity_breach']:.1%}",help='Chance of breaching either 40% liquid assets or three years of planned payout at least once.')
    b.caption('Paths breaching either liquidity threshold at least once')
    terminal=float((summary.terminal_real_assets<cfg.initial_endowment).mean())
    c.metric('Ending real principal erosion',f'{terminal:.1%}',help='Share of paths ending below starting purchasing power; distinct from any-year erosion.')
    c.caption(f'Paths ending below starting purchasing power in year {cfg.horizon_years}')
    left,right=st.columns([1.2,1])
    with left,st.container(border=True):
        st.subheader('Endowment value after inflation')
        st.caption('Range of simulated outcomes, in today’s dollars')
        st.plotly_chart(band_chart(annual,'real_ending_assets',cfg.initial_endowment,cfg.start_year,'Median','Starting value'),use_container_width=True,key='home_endowment')
    initial_payout=float(annual.loc[annual.path_id==0,'planned_payout'].iloc[0])
    with right,st.container(border=True):
        st.subheader('Modeled annual payout after inflation')
        st.caption('Assumes funding is available; liquidity breaches are reported separately')
        st.plotly_chart(band_chart(annual,'real_actual_payout',initial_payout,cfg.start_year,'Median','Initial planned payout'),use_container_width=True,key='home_payout')
    with st.container(border=True):
        st.subheader('Chance of falling below starting purchasing power')
        erosion=annual.assign(eroded=annual.real_ending_assets<cfg.initial_endowment).groupby('year').eroded.mean().reset_index()
        fig=px.line(erosion,x='year',y='eroded',markers=True)
        style_figure(fig,None,height=230);fig.update_yaxes(tickformat='.0%',rangemode='tozero');fig.update_xaxes(title='Year')
        st.plotly_chart(fig,use_container_width=True,key='home_erosion')
    a,b,c=st.columns(3)
    a.metric('Real payout-cut risk',f"{m['probability_real_payout_cut']:.1%}",help='At least one decline greater than 5% between consecutive projected annual real payouts.')
    b.metric('Median ending real value',f"${m['median_terminal_real_assets']:,.1f}M")
    c.metric('Median total real payouts',f"${m['median_cumulative_real_payout']:,.1f}M")
    with st.expander('All risk measures'):
        st.dataframe(risk_table(m),hide_index=True,use_container_width=True)
    st.caption('Payouts are modeled from total endowment wealth. This is not an asset-sale execution or borrowing model.')
