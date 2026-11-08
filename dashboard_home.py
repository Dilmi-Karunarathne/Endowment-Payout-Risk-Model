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
    st.subheader('Your endowment at a glance')
    st.caption('R1 portfolio strategies with R2 institutional benchmarks. Review assumptions for remaining provisional choices.')
    st.caption(f'${cfg.initial_endowment:,.1f}M starting assets · {cfg.horizon_years}-year horizon · '
               f'{inst.effective_spending_rate:.2%} spending · {cfg.return_method} · {cfg.n_sims:,} paths')
    if changed and not results:
        st.info('Settings changed. Select Run analysis to refresh all dashboard results.')
    baseline=results.get('baseline')
    if baseline:
        m=baseline['metrics']
        a,b,c=st.columns(3)
        a.metric('Liquidity constraint breach',f"{m['probability_liquidity_breach']:.1%}")
        b.metric('Any-year real principal erosion',f"{m['probability_real_corpus_erosion']:.1%}")
        c.metric('Median ending real assets',f"${m['median_terminal_real_assets']:,.1f}M")
        st.caption('Liquidity breaches are monitoring signals, not predicted missed payouts. Real values are in starting-year dollars.')
    else:
        st.info('Choose inputs in the sidebar and select Run analysis for baseline, policy and primary stress results.')
    st.caption('Click anywhere on a card to open it. Use Back to dashboard to return.')
    cards=[]
    cards.append(('overview','Payout & purchasing power','Real payout: median and 10th–90th percentile range.',
        'Baseline complete' if baseline else 'Awaiting analysis',_payout_chart(baseline['annual_results']) if baseline else None))
    bundle=results.get('main_stress')
    rows=[] if bundle is None else [(name,r['metrics']['probability_any_support_gap']) for name,r in bundle[1].items()]
    cards.append(('stress','Stress tests','Chance of an institutional support gap.',
        f'{len(rows)} scenarios · {cfg.n_sims:,} paths each' if rows else 'Awaiting analysis',_bars(rows,True) if rows else None))
    table=results.get('policies')
    rows=[] if table is None else [(r['Scenario'],r['Median terminal real corpus ($M)']) for _,r in table.iterrows()]
    cards.append(('strategies','Strategies','Ending real assets by policy; open to compare payouts and risks.',
        f'{len(rows)} policy cases compared' if rows else 'Awaiting analysis',_bars(rows) if rows else None))
    bundle=results.get('methods')
    rows=[] if bundle is None else [(name,r['metrics']['expected_shortfall_terminal_real_corpus_loss']) for name,r in bundle[3].items()]
    cards.append(('returns','Return models',f'Terminal real loss Expected Shortfall at {cfg.alpha:.0%} confidence.',
        f'{len(rows)} return models compared' if rows else 'Awaiting analysis',_bars(rows,True) if rows else None))
    inflation=f'{cfg.annual_inflation:.1%} fixed' if cfg.annual_inflation is not None else 'Historical/model-based'
    cards.append(('data','Data & assumptions',f'{len(history)} quarters: {history.quarter.iloc[0]}–{history.quarter.iloc[-1]}',
        f'{data.portfolio_label} · Inflation: {inflation}',None))
    done=[name for key,name in [('historical','Historical reconstruction'),('holdout','Out-of-sample check'),('stability','Simulation stability')] if key in results]
    cards.append(('checks','Model checks',f'{len(done)} of 3 checks run. Running a check does not establish predictive accuracy.',
        ' · '.join(done) if done else 'Awaiting analysis',None))
    for start in (0,3):
        for column,(view,title,subtitle,status,svg) in zip(st.columns(3),cards[start:start+3]):
            with column:
                if svg:
                    encoded=base64.b64encode(svg.encode()).decode()
                    st.markdown(f'<style>.st-key-open_{view} button {{background-image:url("data:image/svg+xml;base64,{encoded}");}}</style>',unsafe_allow_html=True)
                # The native button IS the card. Charts are decorative backgrounds,
                # so there is no iframe, overlay or child element to intercept clicks.
                st.button('Open '+title+' ↗\n\n'+subtitle+'\n\n'+status,key='open_'+view,
                    on_click=open_detail,args=(view,),use_container_width=True)
