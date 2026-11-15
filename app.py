"""Simple endowment dashboard. Run with: python -m streamlit run app.py"""
from dataclasses import asdict
from io import BytesIO
from html import escape
from pathlib import Path
import json
import zipfile
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Give a deployment instruction rather than a redacted ImportError if GitHub mixes
# an older dashboard contract with the current interface.
try:
    from dashboard_contract import RESULT_SCHEMA_VERSION, validate_result_schema, validate_comparison_schema
except ImportError:
    st.set_page_config(page_title='Endowment Planning & Risk', page_icon='🎓', layout='wide')
    st.error('Incomplete deployment: app.py and dashboard_contract.py are from different versions. '
             'Upload every file inside the v12 Endowment_Final_Model folder to the GitHub repository '
             'root, commit the changes, and reboot the Streamlit app.')
    st.stop()
from investment_model import STRATEGIES
from simple_analysis import BaselineOptions, COMPARISON_STRATEGIES, strategy_cash_requirements
from scenario_analysis import (Scenario, STRATEGY_LABELS, stress_library, what_if_library,
    run_suite, assumption_table, settings_json, validate_scenario,
    policy_response_library, comparison_row)

st.set_page_config(page_title='Endowment Planning & Risk', page_icon='🎓', layout='wide',
                   initial_sidebar_state='expanded')

# Appearance is deliberately excluded from the simulation signature: changing the
# color scheme must NEVER change calculations, invalidate results or rerun MC paths.
appearance=st.session_state.get('appearance','Light')
IS_DARK = appearance == 'Dark'
PALETTE = ({
    'bg':'#09182C', 'surface':'#14243C','sidebar':'#0C1A30',
    'text':'#F0F5FC', 'muted':'#ABBDD1','border':'#314966',
    'accent':'#70B5FF','teal':'#3FD5C0','warning':'#F7C462','red':'#FF8090',
    'fill':'rgba(118,181,245,0.13)', 'grid':'rgba(150,171,198,0.15)'
} if IS_DARK else {
    'bg':'#F7F9FC', 'surface':'#FFFFFF','sidebar':'#EFF4FB',
    'text':'#142E50','muted':'#5D7089','border':'#DDE7F1',
    'accent':'#256EB5','teal':'#069887','warning':'#AE761A','red':'#B94B56',
    'fill':'rgba(39,102,168,0.11)', 'grid':'rgba(70,98,135,0.14)'
})

# CSS is presentation-only; no financial model input or output is modified.
st.markdown(f"""<style>
:root {{
 --m-bg:{PALETTE['bg']};--m-card:{PALETTE['surface']};--m-side:{PALETTE['sidebar']};
 --m-ink:{PALETTE['text']};--m-muted:{PALETTE['muted']};--m-border:{PALETTE['border']};
 --m-blue:{PALETTE['accent']};--m-teal:{PALETTE['teal']};--m-amber:{PALETTE['warning']};
}}
.stApp,[data-testid='stAppViewContainer'] {{background:var(--m-bg);color:var(--m-ink);}}
[data-testid='stHeader'] {{background:var(--m-bg);}}
[data-testid='stSidebar'] {{background:var(--m-side);border-right:1px solid var(--m-border);}}
[data-testid='stSidebar'] * {{color:var(--m-ink);}}
[data-testid='stSidebar'] .stMarkdown p {{font-size:.93rem;}}
[data-testid='stSidebar'] [data-testid='stRadio'] [role='radiogroup'] label {{
 padding:9px 12px;border-radius:10px;transition:background .15s ease;
}}
[data-testid='stSidebar'] [data-testid='stRadio'] [role='radiogroup'] label:has(input:checked) {{
 background:linear-gradient(115deg,#2869BA,#1E508C);}}
[data-testid='stSidebar'] [data-testid='stRadio'] [role='radiogroup'] label:has(input:checked) p {{color:#FFFFFF!important;font-weight:700;}}
[data-testid='stSidebar'] [data-testid='stRadio'] [role='radiogroup'] label:has(input:checked) input {{accent-color:#fff;}}
[data-baseweb='select'] > div,[data-baseweb='input'] > div,[data-baseweb='textarea'] > div {{
 background:var(--m-card)!important;border-color:var(--m-border)!important;color:var(--m-ink)!important;
 border-radius:9px!important;}}
[data-baseweb='select'] input,[data-baseweb='input'] input,[data-baseweb='select'] span,
[data-baseweb='select'] div[role='combobox'],[data-testid='stNumberInput'] input {{color:var(--m-ink)!important;}}
[data-testid='stNumberInput'] input {{background:var(--m-card)!important;}}
[data-testid='stWidgetLabel'] p {{font-weight:650;font-size:.83rem;}}
[data-testid='stExpander'] {{background:var(--m-card);border-radius:12px;border-color:var(--m-border)!important;}}
[data-testid='stTabs'] button[role='tab'][aria-selected='true'] {{color:var(--m-blue)!important;}}
.block-container {{max-width:1640px;padding:1.85rem 2.3rem 4rem;}}
h1,h2,h3,h4,p,.stMarkdown {{color:var(--m-ink);}}
h1,h2,h3 {{letter-spacing:-.025em;}}
[data-testid='stCaptionContainer'],[data-testid='stCaptionContainer'] p {{color:var(--m-muted)!important;}}
[data-testid='stMetric'] {{background:var(--m-card);border:1px solid var(--m-border);border-radius:14px;
 padding:17px 18px;}}
[data-testid='stMetricLabel'] p {{color:var(--m-muted)!important;font-size:.82rem!important;}}
[data-testid='stMetricValue'] div {{color:var(--m-ink)!important;font-weight:760;}}
[data-testid='stDataFrame'],[data-testid='stPlotlyChart'] {{background:var(--m-card);
 border-radius:12px;border:1px solid var(--m-border);padding:6px;}}
[data-testid='stVerticalBlockBorderWrapper'] > div {{border-color:var(--m-border)!important;
 background:var(--m-card);border-radius:13px;}}
[data-testid='stBaseButton-primary'] {{background:#2470C7!important;border-radius:9px;
 border:1px solid #2470C7!important;font-weight:720;color:#FFF!important;min-height:2.45rem;}}
[data-testid='stBaseButton-primary']:hover {{background:#1B5EAA!important;}}
[data-testid='stSidebar'] hr {{border-color:var(--m-border);}}
.model-brand {{font-size:1.32rem;font-weight:780;line-height:1.17;letter-spacing:-.03em;
 border-left:4px solid #328EF2;padding:6px 0 6px 13px;margin:8px 0 10px;}}
.model-brand-subtitle {{font-size:.8rem;color:var(--m-muted);line-height:1.5;margin:2px 0 20px;}}
.model-page-title {{font-size:2.30rem;font-weight:800;letter-spacing:-.045em;line-height:1.12;
 color:var(--m-ink);margin:2px 0 9px;}}
.model-page-subtitle {{font-size:.96rem;color:var(--m-muted);line-height:1.55;margin-bottom:20px;}}
.model-section-caption {{font-size:.82rem;color:var(--m-muted);margin:9px 0;}}
.model-fixed-control {{border:1px solid var(--m-border);background:var(--m-bg);border-radius:9px;
 padding:11px 10px;min-height:42px;line-height:1.22;font-size:.84rem;color:var(--m-ink);}}
.model-fixed-label {{font-size:.79rem;font-weight:650;margin:0 0 8px;color:var(--m-ink);}}
.model-kpi {{background:linear-gradient(115deg,var(--m-card),var(--kpi-tint));border:1px solid var(--m-border);border-radius:15px;
 padding:18px 17px;min-height:147px;position:relative;overflow:hidden;
 box-shadow:0px 6px 16px rgba(21,52,87,.035);}}
.model-kpi::before {{content:'';position:absolute;top:0;bottom:0;left:0;width:4px;background:var(--kpi-color);}}
.model-kpi-top {{display:flex;align-items:center;gap:9px;min-height:29px;}}
.model-kpi-icon {{display:flex;align-items:center;justify-content:center;flex:0 0 29px;
 height:29px;border-radius:8px;background:var(--kpi-tint);color:var(--kpi-color);
 font-size:1.05rem;font-weight:750;}}
.model-kpi-label {{font-size:.80rem;line-height:1.25;font-weight:800;letter-spacing:.009em;}}
.model-kpi-value {{font-size:clamp(1.5rem,2.4vw,2.18rem);line-height:1.17;
 font-weight:790;letter-spacing:-.04em;margin:12px 0 7px;white-space:nowrap;}}
.model-kpi-detail {{font-size:.75rem;line-height:1.4;color:var(--m-muted);}}
.model-read-guide {{border:1px solid var(--m-border);border-radius:14px;background:var(--m-card);
 padding:20px 22px;min-height:385px;}}
.model-guide-title {{font-size:1.17rem;font-weight:760;letter-spacing:-.02em;margin-bottom:17px;}}
.model-guide-entry {{display:flex;gap:12px;padding:12px 0;
 border-bottom:1px solid var(--m-border);}}
.model-guide-entry:last-child {{border-bottom:0;}}
.model-guide-number {{background:{'#244A79' if IS_DARK else '#DCEBFA'};
 color:{'#B6DCFF' if IS_DARK else '#165D9A'};width:28px;height:28px;border-radius:9px;
 text-align:center;line-height:28px;flex:0 0 28px;font-weight:800;}}
.model-guide-body {{font-size:.84rem;line-height:1.47;color:var(--m-muted);}}
.model-guide-body strong {{color:var(--m-ink);}}
.model-takeaway {{background:var(--m-side);border:1px solid var(--m-border);border-radius:12px;
 padding:14px 17px;margin:15px 0;}}
.model-takeaway strong {{color:var(--m-ink);}}
.model-takeaway p {{font-size:.83rem!important;margin:5px 0!important;
 color:var(--m-muted)!important;}}
.model-about {{border:1px solid var(--m-border);border-radius:11px;padding:13px 14px;
 background:var(--m-card);color:var(--m-muted);font-size:.78rem;line-height:1.55;}}
.model-about strong {{color:var(--m-ink);}}
@media(max-width:950px) {{
 .block-container {{padding:1rem .8rem 2rem;}}
 .model-page-title {{font-size:1.72rem;}}
 .model-kpi {{min-height:130px;}}
 .model-kpi-value {{font-size:1.55rem;}}
}}
</style>""", unsafe_allow_html=True)

PLOT_TEMPLATE = 'plotly_dark' if IS_DARK else 'plotly_white'
PLOT_COLORS = ['#438CD6','#0CA99A','#E2A346','#B76BBB','#E36C72','#6B85B7',
               '#F39B72','#8A74C1','#6DB5A1','#989DB1']


def style_figure(fig, title, ylabel, height=340):
    fig.update_layout(title=dict(text=title,font=dict(size=17,color=PALETTE['text'])),
        template=PLOT_TEMPLATE, height=height, paper_bgcolor=PALETTE['surface'],
        plot_bgcolor=PALETTE['surface'],font=dict(color=PALETTE['text'],size=12),
        colorway=PLOT_COLORS,margin=dict(l=18,r=20,t=58,b=67),
        yaxis_title=ylabel, legend=dict(orientation='h',y=-.30,x=0),
        xaxis=dict(showgrid=False), yaxis=dict(gridcolor=PALETTE['grid'],zerolinecolor=PALETTE['grid']))
    return fig

PAGE_TO_MODE = {
    'Overview':'Baseline & strategies',
    'Portfolio analysis':'Baseline & strategies',
    'Payout risk measures':'Baseline & strategies',
    'Stress testing':'Stress testing',
    'Policy responses under stress':'Policy responses under stress',
    'Scenario comparison':'What-if scenarios',
    'Model guide':'Model guide',
}
PAGE_SUBTITLES = {
    'Overview':'Evaluate how investment strategies, spending policies and market conditions affect endowment payouts, liquidity and purchasing power.',
    'Portfolio analysis':'Compare investment returns, payout capacity and inflation-adjusted wealth across the available portfolios.',
    'Payout risk measures':'Understand payout funding failures, liquidity warnings, operating support gaps and purchasing-power losses.',
    'Stress testing':'Measure how adverse markets change payout reliability, portfolio liquidity and endowment sustainability.',
    'Policy responses under stress':'Compare the same market shock under current spending and alternative policies.',
    'Scenario comparison':'Explore how spending, gifts, liquidity constraints and portfolio assumptions affect the results.',
    'Model guide':'Understand the model assumptions, cash-flow mechanics and risk measures in plain language.',
}
with st.sidebar:
    st.markdown('<div class="model-brand">Endowment Planning<br>&amp; Risk Model</div>',unsafe_allow_html=True)
    st.markdown('<div class="model-brand-subtitle">University endowment analytics<br>Investment · Payouts · Liquidity · Risk</div>',unsafe_allow_html=True)
    nav_options=list(PAGE_TO_MODE)
    nav_labels={'Overview':'⌂   Overview','Portfolio analysis':'▥   Portfolio analysis',
      'Payout risk measures':'⬡   Payout risk measures','Stress testing':'ϟ   Stress testing',
      'Policy responses under stress':'↔   Policy responses',
      'Scenario comparison':'▱   Scenario comparison','Model guide':'ⓘ   Model guide'}
    page=st.radio('Navigation',nav_options,index=0,format_func=lambda x:nav_labels[x],
                  label_visibility='collapsed',key='page_v12')
    mode=PAGE_TO_MODE[page]
    st.divider()
    st.markdown('**APPEARANCE**')
    st.radio('Color theme',['Light','Dark'],horizontal=True,
             label_visibility='collapsed',key='appearance',
             help='Switch themes without rerunning the financial model.')
    st.divider()
    st.markdown('<div class="model-about"><strong>About this model</strong><p>A five-year Monte Carlo model that connects investment performance, annual payout obligations, operating support, and liquidity risk.</p><span>All outputs are scenario estimates, not investment forecasts.</span></div>',unsafe_allow_html=True)

st.markdown(f'<h1 class="model-page-title">{ "Model overview" if page == "Overview" else page }</h1>'
            f'<div class="model-page-subtitle">{PAGE_SUBTITLES[page]}</div>', unsafe_allow_html=True)
with st.container(border=True):
    # These are real controls tied to the simulation. The spending rule and
    # horizon are presented as fixed labels, not fake interactive dropdowns.
    controls=st.columns([1.10,1.08,2.05,1.12,1.10,1.0,1.3],gap='small',vertical_alignment='bottom')
    with controls[0]:
        institution=st.selectbox('Institution type',['Private','Public'],key='institution_v12')
    with controls[1]:
        profile=st.selectbox('Institutional profile',['Low','Base','High'],index=1,
            key='institution_profile_v12',help='The Base profile uses benchmark median institutional assumptions.')
    with controls[2]:
        strategy=st.selectbox('Investment strategy',STRATEGIES,index=STRATEGIES.index('HRP_Dynamic'),
            format_func=lambda key:STRATEGY_LABELS[key],key='strategy_v12')
    with controls[3]:
        initial=st.number_input('Endowment ($M)',min_value=1.,max_value=10000.,value=150.,step=10.,
                                key='initial_v12')
    with controls[4]:
        paths=st.selectbox('Simulations',[5000,10000],format_func=lambda x:f'{x:,}',key='paths_v12')
    with controls[5]:
        st.markdown('<div class="model-fixed-label">Spending rule</div><div class="model-fixed-control" title="Fixed original three-year spending rule, with 3–5% limits">3-year average</div>',unsafe_allow_html=True)
    with controls[6]:
        run_clicked=st.button('▶ Run analysis',type='primary',use_container_width=True,key='run_v12')
    options_caption=st.columns([2.8,2.5,1.1],gap='small')
    with options_caption[0]:
        compare=st.checkbox('Compare three representative dynamic portfolios',
            key='compare_v12',help='Run HRP Dynamic, Mean-CVaR Dynamic, and Equal-Weight Dynamic on matched market paths.')
    with options_caption[1]:
        st.caption('Fixed horizon: 2027–2031 · 5 years · 3%–5% spending constraints')
    with options_caption[2]:
        st.caption('Seed 42 · USD millions')
options=BaselineOptions(institution,profile,strategy,float(initial),int(paths))
strategies=COMPARISON_STRATEGIES if compare else (strategy,)


def render_risk_card(label,value,detail,icon,color,tint):
    """Display values calculated by the model, never numbers from the mockups."""
    st.markdown(f'<div class="model-kpi" style="--kpi-color:{color};--kpi-tint:{tint}">'
                f'<div class="model-kpi-top"><span class="model-kpi-icon">{escape(icon)}</span>'
                f'<span class="model-kpi-label">{escape(label)}</span></div>'
                f'<div class="model-kpi-value">{escape(value)}</div>'
                f'<div class="model-kpi-detail">{escape(detail)}</div></div>',
                unsafe_allow_html=True)


def overview_wealth_figure(suite, selected_key, initial_amount):
    """Compare actual portfolio results on the same scenario or show a single-path band."""
    matching=[(key,result) for key,result in suite['cases'].items()
              if key[1] == selected_key[1]]
    if not matching:
        matching=[(selected_key,suite['cases'][selected_key])]
    fig=go.Figure()
    multi=len(matching)>1
    for i,(key,result) in enumerate(matching):
        yearly=result['yearly'];xs=['Today']+[str(int(y)) for y in yearly['year']]
        median=[float(initial_amount)]+yearly['median_real_endowment_m'].astype(float).tolist()
        if not multi:
            lo=[float(initial_amount)]+yearly['real_endowment_p10_m'].astype(float).tolist()
            hi=[float(initial_amount)]+yearly['real_endowment_p90_m'].astype(float).tolist()
            fig.add_trace(go.Scatter(x=xs,y=hi,mode='lines',line=dict(width=0),
                                     hoverinfo='skip',showlegend=False))
            fig.add_trace(go.Scatter(x=xs,y=lo,mode='lines',line=dict(width=0),
                  fill='tonexty',fillcolor=PALETTE['fill'],name='Middle 80% of outcomes'))
        color=PLOT_COLORS[i % len(PLOT_COLORS)] if multi else PALETTE['accent']
        fig.add_trace(go.Scatter(x=xs,y=median,mode='lines+markers',
            name=STRATEGY_LABELS[key[0]] if multi else 'Median real endowment',
            line=dict(color=color,width=3),marker=dict(size=7),
            hovertemplate='%{x}: $%{y:,.1f}M<extra>%{fullData.name}</extra>'))
    style_figure(fig,'Real endowment · portfolio comparison' if multi else
                 'Real endowment · range of outcomes',
                 'Inflation-adjusted endowment ($M)',height=395)
    fig.update_layout(legend=dict(orientation='h',y=-.28,x=0),
        margin=dict(l=10,r=12,t=59,b=70),hovermode='x unified')
    fig.update_xaxes(categoryorder='array',categoryarray=['Today','2027','2028','2029','2030','2031'])
    return fig


def render_metric_guide():
    definitions=[
      ('Ending real endowment','Median total endowment after five years, in starting-year dollars. Includes restricted new gifts.'),
      ('Unpaid payout risk','Chance that at least one scheduled annual distribution cannot be fully funded.'),
      ('Minimum liquidity buffer','Median of each path’s lowest stressed one-month liquid assets ÷ annual planned payout. Capital calls affect liquidity, but are not added to the denominator.'),
      ('Expected Shortfall (95%)','Average loss of terminal inflation-adjusted endowment value in the worst 5% of simulated paths, as a share of starting value.'),
    ]
    entries=''.join(
      f'<div class="model-guide-entry"><span class="model-guide-number">{i}</span>'
      f'<div class="model-guide-body"><strong>{escape(title)}</strong> — {escape(description)}</div></div>'
      for i,(title,description) in enumerate(definitions,1))
    st.markdown('<div class="model-read-guide"><div class="model-guide-title">ⓘ &nbsp; How to read these results</div>'
                +entries+'</div>',unsafe_allow_html=True)


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


def chart(suite, column, title, ylabel):
    fig=go.Figure()
    for i,((key,name),result) in enumerate(suite['cases'].items()):
        label=(STRATEGY_LABELS[key]+' · ' if len(suite['strategies'])>1 else '')+name
        frame=result['yearly']
        fig.add_trace(go.Scatter(x=frame.year,y=frame[column],mode='lines+markers',name=label,
            line=dict(width=3 if name=='Baseline' else 2,
                      color=PLOT_COLORS[i%len(PLOT_COLORS)],
                      dash='solid' if name=='Baseline' else 'dash')))
    style_figure(fig,title,ylabel,height=365)
    fig.update_xaxes(dtick=1)
    st.plotly_chart(fig,width='stretch')


def single_case_figure(result, kind):
    """Real calculations only. No preview or mock data in the app."""
    annual=result['yearly'];x=annual['year']
    fig=go.Figure()
    if kind == 'wealth':
        low,med,high=[annual[k].to_numpy() for k in
            ('real_endowment_p10_m','median_real_endowment_m','real_endowment_p90_m')]
        fig.add_trace(go.Scatter(x=x,y=high,mode='lines',line=dict(width=0),
                                 hoverinfo='skip',showlegend=False))
        fig.add_trace(go.Scatter(x=x,y=low,mode='lines',line=dict(width=0),
                                 fill='tonexty',fillcolor=PALETTE['fill'],
                                 name='10th–90th percentile band'))
        fig.add_trace(go.Scatter(x=x,y=med,mode='lines+markers',
            name='Median real endowment',line=dict(color=PALETTE['accent'],width=3)))
        style_figure(fig,'Real endowment value · typical and downside outcomes',
                     'Inflation-adjusted endowment ($M)')
    elif kind == 'payout':
        for field,label,color,dash in [
            ('mean_planned_payout_m','Mean planned payout',PALETTE['accent'],'dot'),
            ('mean_actual_payout_m','Mean payout delivered',PALETTE['teal'],'solid')]:
            fig.add_trace(go.Scatter(x=x,y=annual[field],mode='lines+markers',name=label,
                line=dict(color=color,width=3,dash=dash)))
        style_figure(fig,'Annual distribution · scheduled versus delivered',
                     'Annual payout ($M)')
    elif kind == 'liquidity':
        fig.add_trace(go.Scatter(x=x,y=annual['median_liquidity_buffer_x'],
           mode='lines+markers',name='Median liquidity buffer',
           line=dict(color=PALETTE['teal'],width=3)))
        fig.add_hline(y=3,line=dict(color=PALETTE['warning'],dash='dash',width=2),
            annotation_text='3× reference',annotation_position='top left')
        style_figure(fig,'Liquidity buffer after annual distribution',
                     'Eligible liquid assets / planned payout (×)')
    elif kind == 'support':
        fig.add_trace(go.Bar(x=x,y=annual['mean_support_gap_m'],name='Mean support gap',
                 marker_color=PALETTE['warning']))
        style_figure(fig,'University funding support gap',
                     'Average annual support gap ($M)')
    return fig


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
        z.writestr('stress_diagnostics.csv',suite['comparison'].to_csv(index=False))
        z.writestr('run_settings.json',settings_json(suite))
        z.writestr('READ_ME.txt','All dollar amounts are USD millions. Probability columns in comparison.csv are percentages.\nPath-year returns and inflation are decimals. Events are 0/1.\nStress frequencies are conditional on the chosen scenario, not probabilities that the scenario occurs.\nSee run_settings.json for exact inputs.\n')
        for i,((key,name),result) in enumerate(suite['cases'].items(),1):
            prefix=f'{i:02d}_{key}'
            z.writestr(prefix+'_annual_summary.csv',export_frame(result['yearly']).to_csv(index=False))
            z.writestr(prefix+'_path_years.csv',export_frame(result['annual_detail']).to_csv(index=False))
            z.writestr(prefix+'_assumptions.csv',result['applied_assumptions'].to_csv(index=False))
            z.writestr(prefix+'_scenario.txt',name+'\n'+result['scenario'].description+'\nSource: '+result['scenario'].source+'\n')
    return buffer.getvalue()


if mode=='Model guide':
    st.subheader('How the model works')
    st.markdown('''1. **Select an institution and portfolio.** The institutional benchmark profile sets spending, gifts and operating assumptions. The investment dropdown contains the ten November 2026 investment-research portfolios.
2. **Generate matched markets.** Four-quarter blocks preserve the joint historical asset and inflation observations. Every strategy and scenario starts from the same sampled paths.
3. **Apply a scenario.** Historical replays replace specified quarters. Other scenarios adjust explicit market, gift, spending or liquidity inputs.
4. **Invest and fund payouts.** Quarterly holdings follow the existing allocation rules. At year-end, cash and eligible asset sales fund capital calls and the planned payout, with the selected reserve protected.
5. **Compare outcomes.** The dashboard separates investment returns, unpaid payouts, liquidity and inflation-adjusted wealth.''')
    st.markdown('#### Payout Risk Measures tab')
    st.markdown('The four headline measures are unpaid payout probability, real erosion of assets supporting payouts, institutional support-gap probability and 95% purchasing-power Expected Shortfall. A deviation chart and annual gap table are displayed in the dedicated Payout Risk Measures tab for every run.')
    st.markdown('#### Read the results')
    st.markdown('**New portfolio handoff (15 Nov 2026):** Five final investment methods, each Dynamic and Static, replace the earlier nine strategies. Dynamic portfolios use Calm/Turbulent targets; static versions maintain their fixed target allocations. The 20% crisis-asset rule uses post-crash *g* weights, not the one-month *h* liquidity monitor. Capital calls are illustrative scaled proxies, not observed institutional commitments.')
    st.dataframe(pd.DataFrame([
        ['Unpaid payout probability','Share of paths with at least one planned payout not fully paid.'],
        ['Liquidity buffer','Stressed one-month liquid assets eligible for payouts ÷ planned annual payout.'],
        ['40% / 20% liquid-share breach','Share of paths where eligible liquid assets ÷ total wealth falls below the threshold. Quarterly and post-payout checks are included.'],
        ['Purchasing-power expected shortfall (95%)','Average nonnegative loss of ending real wealth, as a percentage of starting wealth, in the worst 5% of paths.'],
        ['Institutional support gap','Required institutional support exceeds the actual payout. It differs from an unpaid planned payout.'],
        ['Change from baseline','Same strategy and matched market paths; probability changes are percentage points.'],
    ],columns=['Measure','Meaning']),hide_index=True,width='stretch')
    st.markdown('#### Understand stress and policy results')
    st.markdown('''- **Baseline versus stress:** Each scenario uses the same path-specific market draws as its own baseline. Differences in return are percentage points; differences in liquidity buffers are multiples of planned annual payout.
- **Policy under stress:** Select a downturn, inflation shock or stagflation. Compare **baseline → unchanged stress → same stress with an alternative spending or reserve policy**. The policy response is fixed at the start of the experiment: it is not automatically triggered by a live liquidity warning.
- **Payout reliability:** Insufficient investment earnings do **not** imply a cash-funding failure. Report unpaid payouts, their dollar size, and duration separately from earnings insufficiency.
- **Funding versus liquidity:** Liquidity monitoring uses stressed one-month sale eligibility; actual payout cash can use qualifying three-month asset sales. A breached policy indicator does not necessarily cause an unpaid payout.
- **Stress probabilities:** These are probabilities *conditional on the specified shock* and its assumptions, not probabilities that the economic crisis itself will happen.''')
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
    st.caption('Two core stresses: 2022-style inflation/rates and 2008-style downturn with liquidity pressure. Additional tests isolate risks. Baseline is always included. Outcomes are CONDITIONAL on the selected shock.')
elif mode=='Policy responses under stress':
    st.subheader('Can a spending or reserve decision improve resilience during a shock?')
    st.write('Compare **baseline**, the **unchanged adverse market scenario**, and **exactly the same stress with one policy response**. Shared return and inflation paths isolate the effect of the policy change.')
    severity=st.radio('Stress severity',['Standard','Severe'],index=1,horizontal=True,
        help='Severe stresses use the assumptions supplied in the existing project scenario table.')
    stress_choice=st.selectbox('Adverse market environment',
        ['Prolonged downturn & liquidity pressure','High inflation & elevated rates','Stagflation'])
    policies=policy_response_library(institution,severity,stress_choice)
    policy_name=st.selectbox('Alternative policy during the same stress',list(policies),index=0,
        help='A fixed illustrative policy, not an automatic response to a threshold breach.')
    unchanged=stress_library(institution,severity)[stress_choice]
    selected=[unchanged,policies[policy_name]]
    st.caption(f'For this {institution} example, the policy experiment uses the SAME {stress_choice.lower()} shock, gift assumptions, capital-call schedule and matched sampled market paths. The only new assumption is the selected spending rate or protected cash reserve.')
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
if count>=9:
    st.warning('This analysis includes at least nine full Monte Carlo cases. For a faster first check, uncheck Compare the three representative dynamic portfolios and run one portfolio before expanding the comparison.')
signature=json.dumps({'mode':mode,'options':asdict(options),'strategies':strategies,
    'scenarios':[asdict(s) for s in selected],'severity':severity,'schema':RESULT_SCHEMA_VERSION},sort_keys=True)
if run_clicked:
    bar=st.progress(0,text='Preparing matched market paths…')
    try:
        result=run_suite(options,selected,strategies,
            progress=lambda fraction,label:bar.progress(min(1.,fraction),text=f'{fraction:.0%} · {label}'))
        for r in result['cases'].values():
            valid,message=validate_result_schema(r)
            if not valid:raise ValueError(message)
        valid,message=validate_comparison_schema(result['comparison'])
        if not valid: raise ValueError(message)
        st.session_state['analysis']=(signature,result)
        st.session_state.pop('download_data',None)
        bar.empty()
        st.success('Analysis complete. All cases passed the asset and payout reconciliation checks.')
    except Exception as exc:
        bar.empty()
        st.error(f'Analysis could not finish: {exc}')
        st.stop()

saved=st.session_state.get('analysis')
if saved is None or saved[0] != signature:
    message=('Your settings have changed. Select Run analysis to update the results.'
             if saved is not None else
             'Choose your assumptions and select Run analysis to calculate the dashboard. No example figures are displayed.')
    st.info(message)
    if page == 'Overview':
        blank=st.columns(4,gap='small')
        empty_cards=[('ENDING REAL ENDOWMENT','▤','#2F7BC9','rgba(47,123,201,.12)'),
                     ('UNPAID PAYOUT RISK','⬡','#C18D28','rgba(193,141,40,.14)'),
                     ('MINIMUM LIQUIDITY BUFFER','◈','#13A28E','rgba(19,162,142,.13)'),
                     ('EXPECTED SHORTFALL (95%)','▥','#7E69D1','rgba(126,105,209,.12)')]
        for box,(label,icon,color,tint) in zip(blank,empty_cards):
            with box:render_risk_card(label,'—','Run analysis to calculate',icon,color,tint)
        left,right=st.columns([1.77,1],gap='medium')
        with left:
            with st.container(border=True):
                st.markdown('#### Real endowment · portfolio comparison')
                st.caption('After running, this chart displays the actual median simulated endowment values. '
                           'Select a three-portfolio comparison above to display multiple strategies.')
                st.info('Waiting for model results. No sample financial data are shown.')
        with right:render_metric_guide()
    st.stop()
suite=saved[1]
valid,message=validate_comparison_schema(suite.get('comparison'))
if not valid:
    st.warning(message)
    st.stop()
st.markdown('#### Simulation results')
st.caption(f"{suite['options'].institution} institution · {suite['options'].profile} profile · "
           f"{suite['options'].paths:,} simulated market paths per case · Five years, 2027–2031")
primary_key=next((k for k in suite['cases'] if k[1]=='Baseline'),next(iter(suite['cases'])))
if len(suite['cases']) > 1:
    choices=list(suite['cases'])
    default_index=next((i for i,k in enumerate(choices) if k[1] != 'Baseline'),0) if page in (
        'Stress testing','Scenario comparison','Policy responses under stress') else choices.index(primary_key)
    primary_key=st.selectbox('Focus portfolio and market scenario',choices,index=default_index,
        format_func=lambda k:STRATEGY_LABELS[k[0]]+' · '+k[1],key='overview_case_v12',
        help='Headline metrics use this case. Comparison tables retain every investment strategy and scenario.')
primary=suite['cases'][primary_key]
pm=primary['metrics']
terminal=primary['annual_detail']
terminal=terminal[terminal['year']==terminal['year'].max()]
median_real=float(terminal['real_ending_assets'].median())
table=suite['comparison']
changes_percent=(median_real/initial-1)*100 if initial>0 else 0
kpi_cols=st.columns(4,gap='small')
with kpi_cols[0]:
    render_risk_card('ENDING REAL ENDOWMENT',f'${median_real:,.1f}M',
        f'{changes_percent:+.1f}% vs. starting value · includes restricted gifts',
        '▤','#2F7BC9', 'rgba(47,123,201,.12)')
with kpi_cols[1]:
    render_risk_card('UNPAID PAYOUT RISK',f"{pm['probability_at_least_one_shortfall']:.1%}",
        'Chance of any scheduled payout not being fully funded',
        '⬡','#C18D28','rgba(193,141,40,.14)')
with kpi_cols[2]:
    render_risk_card('MINIMUM LIQUIDITY BUFFER',f"{pm['median_minimum_liquidity_buffer_x']:.2f}×",
        'Median of path-minimum liquid assets ÷ planned annual payout',
        '◈','#13A28E','rgba(19,162,142,.13)')
with kpi_cols[3]:
    render_risk_card('EXPECTED SHORTFALL (95%)',
        f"{pm['purchasing_power_expected_shortfall_pct_initial']:.1%}",
        'Mean purchasing-power loss in the worst 5% of outcomes',
        '▥','#7E69D1','rgba(126,105,209,.12)')

if page == 'Overview':
    left,right=st.columns([1.77,1],gap='medium',vertical_alignment='top')
    with left:
        with st.container(border=True):
            st.plotly_chart(overview_wealth_figure(suite,primary_key,initial),
                            use_container_width=True)
            st.caption('All lines are cross-path medians, not individual simulated paths. '
                       'If only one strategy is selected, the shaded area is the 10th–90th percentile range.')
    with right:
        render_metric_guide()
    findings=[]
    if pm['probability_at_least_one_shortfall'] < .01:
        findings.append('The model funds nearly all scheduled annual payouts, but this does not prove the assets preserve purchasing power.')
    else:
        findings.append(f"Scheduled payout shortfalls occur in {pm['probability_at_least_one_shortfall']:.1%} of simulated paths.")
    findings.append(f"Typical minimum one-month liquidity coverage is {pm['median_minimum_liquidity_buffer_x']:.2f}× annual planned payout.")
    findings.append(f"The median inflation-adjusted ending fund is ${median_real:,.1f}M; downside outcomes can differ materially.")
    st.markdown('<div class="model-takeaway"><strong>Key takeaways</strong>'+''.join(
        '<p>• '+escape(item)+'</p>' for item in findings)+'</div>',unsafe_allow_html=True)
    with st.expander('Explore payout, liquidity and budget charts',expanded=False):
        ca,cb=st.columns(2)
        with ca:
            st.plotly_chart(single_case_figure(primary,'payout'),use_container_width=True)
            st.plotly_chart(single_case_figure(primary,'liquidity'),use_container_width=True)
        with cb:
            st.plotly_chart(single_case_figure(primary,'support'),use_container_width=True)
            st.plotly_chart(single_case_figure(primary,'wealth'),use_container_width=True)
    if len(table)>1:
        with st.expander('View portfolio and scenario comparison table',expanded=False):
            st.dataframe(table[['Strategy','Scenario','Median annualized return (%)',
              'Unpaid payout probability (%)','Median minimum liquidity buffer (×)',
              'Median ending real endowment ($M)']].round(2),hide_index=True,use_container_width=True)
    st.caption('Figures are calculated using the November 2026 portfolio handoff and the selected institutional assumptions. '
               'Reference screenshots contain illustrative values and are not sources for these results.')

if page in ('Portfolio analysis','Stress testing','Scenario comparison','Policy responses under stress'):
    st.markdown('### Compare simulated investment and spending outcomes')
    core=['Strategy','Scenario','Median annualized return (%)','Unpaid payout probability (%)',
        'Median minimum liquidity buffer (×)','Median ending real endowment ($M)']
    st.dataframe(table[core].round(2),hide_index=True,use_container_width=True)
    if selected:
        with st.expander('How much did stress change the results?',expanded=True):
            columns=['Strategy','Scenario',
                'Change in annualized return (pp)','Change in unpaid payout risk (pp)',
                'Change in minimum liquidity buffer (×)',
                'Change in purchasing-power ES 95% (pp)',
                'Change in median real payout-eligible assets ($M)',
                'Change in mean cumulative real payouts ($M)']
            st.dataframe(table.loc[table.Scenario!='Baseline',columns].round(2),
                         hide_index=True,use_container_width=True)
            st.caption('pp = percentage points. Comparisons use the same market-path draws.')
        if table['Policy reference'].astype(bool).any():
            with st.expander('Policy impact under the identical adverse markets',expanded=True):
                policy_rows=table.loc[table['Policy reference'].astype(bool)]
                columns=['Strategy','Scenario',
                    'Policy vs same stress: Change in annualized return (pp)',
                    'Policy vs same stress: Change in unpaid payout risk (pp)',
                    'Policy vs same stress: Change in minimum liquidity buffer (×)',
                    'Policy vs same stress: Change in median real payout-eligible assets ($M)',
                    'Policy vs same stress: Change in mean cumulative real payouts ($M)']
                st.dataframe(policy_rows[columns].round(2),hide_index=True,use_container_width=True)
    with st.expander('Downside and liquidity-policy comparisons'):
        st.dataframe(table[['Strategy','Scenario','Below 40% liquid-share probability (%)',
            'Below 20% liquid-share probability (%)',
            'Portfolio crisis-value 20% breach probability (%)',
            'Purchasing-power expected shortfall 95% (%)',
            'Unpaid capital-call probability (%)']].round(2),hide_index=True,use_container_width=True)
        st.caption('The one-month liquidity-share warnings and the portfolio crisis-sale-value rule are different measures.')
    with st.expander('Duration and severity of payout-funding gaps'):
        st.dataframe(table[['Strategy','Scenario',
            'Mean total unpaid payout per path ($M)',
            'Mean total unpaid payout when at least one occurs ($M)',
            'Probability of 2+ consecutive unpaid-payout years (%)',
            'Probability of 2+ consecutive earnings gaps (%)',
            'Probability of any eligible-earnings gap (%)']].round(2),hide_index=True,use_container_width=True)
        st.caption('Insufficient investment earnings do not necessarily mean an unpaid scheduled distribution.')

if page == 'Payout risk measures':
    st.markdown('### Payout Risk Measures')
    st.caption('Select an investment strategy and scenario to interpret four payout and sustainability risks. '
               'All probabilities refer to at least one event within the five-year simulated horizon, '
               'except Expected Shortfall, which concerns terminal wealth.')
    risk_choices=list(suite['cases'])
    selected_risk=st.selectbox('Portfolio and scenario for risk measures',risk_choices,
        format_func=lambda k:STRATEGY_LABELS[k[0]]+' · '+k[1],key='payout_risk_case')
    risk_case=suite['cases'][selected_risk]
    rm= risk_case['metrics']
    ra= risk_case['annual_detail']
    rr= risk_case['yearly']
    rc1,rc2,rc3,rc4=st.columns(4)
    rc1.metric('Any unpaid planned payout',f"{rm['probability_at_least_one_shortfall']:.1%}",
        help='Share of paths where actual annual payout is below the planned amount at least once.')
    rc2.metric('Real payout-eligible principal erosion',f"{risk_case['probability_spendable_real_erosion']:.1%}",
        help='Share of paths where inflation-adjusted assets eligible to support payouts are below the starting endowment in any year.')
    rc3.metric('Any institutional support gap',f"{rm['probability_any_support_gap']:.1%}",
        help='Any year actual payout is below the separate institutional operating-support target. It is not the same as an unpaid planned payout.')
    rc4.metric('Purchasing-power Expected Shortfall (95%)',f"{rm['purchasing_power_expected_shortfall_pct_initial']:.1%}",
        help='Average terminal real endowment loss versus starting value in the worst 5% of paths, as percentage of initial endowment.')
    rcols=st.columns(3)
    rcols[0].metric('Average unpaid amount when a payout fails',f"${rm['average_shortfall_amount']:.2f}M")
    rcols[1].metric('Average institutional support gap when positive',f"${rm['conditional_average_support_gap_m']:.2f}M")
    rcols[2].metric('Total-asset real principal erosion (any year)',f"{risk_case['probability_total_real_erosion']:.1%}")
    deviation=go.Figure()
    deviation.add_trace(go.Bar(x=rr.year,y=rr.mean_shortfall_deviation_m,
        name='Mean actual − planned payout',marker_color=PALETTE['accent']))
    deviation.add_trace(go.Scatter(x=rr.year,y=rr.worst_shortfall_deviation_m,
        name='Worst-path deviation',mode='lines+markers',line=dict(color=PALETTE['red'],width=2)))
    deviation.add_hline(y=0,line=dict(color=PALETTE['muted'],dash='dot'))
    style_figure(deviation,'Payout-funding shortfall deviation by year',
        'Actual payout − planned payout ($M)',height=350)
    st.plotly_chart(deviation,width='stretch')
    st.caption('Zero means the scheduled distribution was funded. Negative values are unpaid amounts, '
               'not losses of investment return. The worst line is the worst sampled path in that year.')
    st.markdown('#### Annual gaps, liquidity and endowment support')
    annual_risk_fields={
        'year':'Year',
        'mean_unpaid_payout_m':'Mean unpaid payout ($M)',
        'mean_spendable_earnings_gap_m':'Earnings gap of payout-eligible assets ($M)',
        'mean_earnings_only_gap_m':'Total investment earnings-only coverage gap ($M)',
        'mean_support_gap_when_positive_m':'Mean support gap when positive ($M)',
        'median_liquidity_buffer_x':'Median post-payout liquidity buffer (×)',
        'liquid_share_40pct_breach_frequency':'40% one-month liquidity breach share',
        'liquid_share_20pct_breach_frequency':'20% one-month liquidity breach share',
        'research1_crisis_20pct_breach_frequency':'Portfolio crisis-value 20% breach share',
    }
    st.dataframe(rr[list(annual_risk_fields)].rename(columns=annual_risk_fields).round(3),
                 hide_index=True,width='stretch')
    st.info('**How to read coverage gaps:** Newly received gifts and their returns are restricted from funding payouts '
        'in this model. Therefore the **payout-eligible earnings gap** is the more relevant earnings-only diagnostic. '
        'The separate earnings-plus-gifts metric in raw exports is not a measure of legally available cash.')
    st.caption('New portfolio-construction rule: at each allocation decision, crisis-value sellable assets >= 4 × 5% annual payout '
               '(20% of assets). That metric uses crisis-value factor **g** after a known worst fall and sale cost. '
               'Professor Joe’s 40% and 20% monitoring tests instead use the one-month access factor **h**. '
               'These are not interchangeable measures and their breach probabilities need not be ordered across definitions.')

if page == 'Portfolio analysis':
    chart_suite=suite
    if len(suite['strategies'])>1 and len(suite['scenarios'])>1:
        chart_strategy=st.selectbox('Portfolio shown in comparison charts',suite['strategies'],
            format_func=lambda k:STRATEGY_LABELS[k])
        chart_suite={**suite,'cases':{k:v for k,v in suite['cases'].items()
                     if k[0]==chart_strategy},'strategies':(chart_strategy,)}
    st.markdown('### Compare portfolios across the five-year horizon')
    a,b=st.columns(2)
    with a:
        chart(chart_suite,'median_real_endowment_m',
              'Endowment purchasing power','Real total endowment ($M)')
        chart(chart_suite,'median_liquidity_buffer_x',
              'Liquidity buffer after annual payout','Liquid assets / planned payout (×)')
    with b:
        chart(chart_suite,'median_real_spendable_assets_m',
              'Assets eligible for future payouts','Real payout-eligible assets ($M)')
        chart(chart_suite,'mean_actual_payout_m',
              'Average annual payout delivered','Annual payout ($M)')
    st.caption('Each line is a cross-path statistic by year, not an individual investment path. Restricted gifts can increase total endowment wealth without being immediately available for distributions.')

if page in ('Stress testing','Policy responses under stress','Scenario comparison'):
    if not selected:
        st.info('Run a Stress testing or Policy responses under stress analysis to view conditional impacts and cash-flow diagnostics.')
    else:
        diag_strategy=st.selectbox('Investment strategy to inspect',suite['strategies'],format_func=lambda x:STRATEGY_LABELS[x],key='diag_strategy')
        available=[s.name for s in suite['scenarios'] if s.name!='Baseline']
        diag_case=st.selectbox('Scenario to inspect',available,key='diag_scenario')
        stressed=suite['cases'][(diag_strategy,diag_case)]
        original=suite['cases'][(diag_strategy,'Baseline')]
        diag_row=table.loc[(table.Strategy==STRATEGY_LABELS[diag_strategy])&(table.Scenario==diag_case)].iloc[0]
        st.markdown('#### Change relative to unchanged baseline')
        c1,c2,c3,c4=st.columns(4)
        c1.metric('Annualized return (pp)',f"{diag_row['Change in annualized return (pp)']:+.2f}")
        c2.metric('Unpaid payout risk (pp)',f"{diag_row['Change in unpaid payout risk (pp)']:+.2f}")
        c3.metric('Minimum liquidity buffer (×)',f"{diag_row['Change in minimum liquidity buffer (×)']:+.2f}")
        c4.metric('Purchasing-power ES95 (pp)',f"{diag_row['Change in purchasing-power ES 95% (pp)']:+.2f}")
        st.caption('Expected Shortfall is loss of terminal real wealth in the worst 5% of paths; it is not the annual payout shortfall.')
        def paired_figure(key,title,ylabel,scale=1,percent=False):
            f=go.Figure()
            for label,result,dash in [('Baseline',original,'solid'),(diag_case,stressed,'dash')]:
                y=result['yearly'][key]*scale
                f.add_trace(go.Scatter(x=result['yearly'].year,y=y,name=label,
                    mode='lines+markers',line=dict(width=3 if label=='Baseline' else 2,dash=dash)))
            return style_figure(f,title,ylabel,height=345)
        col1,col2=st.columns(2)
        with col1:
            st.plotly_chart(paired_figure('mean_unpaid_payout_m',
                'Average unpaid distribution by year','Amount unpaid ($M)'),width='stretch')
            st.plotly_chart(paired_figure('median_real_spendable_assets_m',
                'Real assets eligible to fund payouts','Real eligible assets ($M)'),width='stretch')
        with col2:
            st.plotly_chart(paired_figure('funding_shortfall_year_frequency',
                'Probability a payout is not fully paid in each year','Probability (%)',scale=100),width='stretch')
            buffer_fig=paired_figure('median_liquidity_buffer_x',
                'Post-payout liquidity buffer','Annual planned payouts (×)')
            buffer_fig.add_hline(y=3,line=dict(color='#b7802a',dash='dot'),
                annotation_text='3× reference',annotation_position='top left')
            st.plotly_chart(buffer_fig,width='stretch')
        col1,col2=st.columns(2)
        with col1:
            planned_actual=go.Figure()
            for col,label,color in [('mean_planned_payout_m','Scheduled distribution','#4263a9'),
                                    ('mean_actual_payout_m','Actual funded distribution','#1c956f')]:
                planned_actual.add_trace(go.Scatter(x=stressed['yearly'].year,
                    y=stressed['yearly'][col],mode='lines+markers',name=label,
                    line=dict(color=color,width=2.5)))
            style_figure(planned_actual,'Planned versus actual distributions under stress',
                'Annual payout ($M)',height=345)
            st.plotly_chart(planned_actual,width='stretch')
        with col2:
            st.plotly_chart(paired_figure('mean_investment_return',
                'Mean investment return by year','Return (%)',scale=100),width='stretch')
        st.markdown('#### Cash-flow and funding diagnostics')
        audit_fields={
            'mean_planned_payout_m':'Mean planned payout ($M)',
            'mean_actual_payout_m':'Mean actual payout ($M)',
            'mean_unpaid_payout_m':'Mean unpaid payout ($M)',
            'mean_net_asset_sales_m':'Mean net asset sales ($M)',
            'mean_asset_sale_cost_m':'Mean liquidation costs ($M)',
            'mean_investment_capital_call_paid_m':'Mean paid capital calls ($M)',
            'mean_investment_capital_call_unpaid_m':'Mean unpaid capital calls ($M)',
            'mean_investment_reserve_target_m':'Mean protected reserve ($M)',
            'mean_support_gap_m':'Mean institutional support gap ($M)',
            'median_liquidity_buffer_x':'Median post-payout liquidity buffer (×)',
            'median_real_endowment_m':'Median real endowment ($M)',
        }
        audit=[]
        for label,result in [('Baseline',original),(diag_case,stressed)]:
            df=result['yearly'][['year',*audit_fields]].rename(columns=audit_fields).copy()
            df.insert(0,'Scenario',label)
            audit.append(df)
        st.dataframe(pd.concat(audit,ignore_index=True).round(3),hide_index=True,width='stretch')
        info=comparison_row(stressed)
        first=info['Median first unpaid-payout year, when any']
        if pd.isna(first):
            st.caption('No path has an unpaid planned payout in this sample; there is therefore no first-failure year.')
        else:
            st.caption(f'Median first unpaid-payout year among paths that fail at least once: {first:.0f}.')
        st.caption(f"Chance of two or more consecutive eligible-earnings gaps: {info['Probability of 2+ consecutive earnings gaps (%)']:.1f}%. This is distinct from consecutive UNPAID payouts, which occur in {info['Probability of 2+ consecutive unpaid-payout years (%)']:.1f}% of paths.")
        if stressed['scenario'].policy_reference:
            st.info('This is a policy response under the SAME sampled stress. The scenario is a hypothetical fixed spending or reserve choice, not an automatic emergency policy.')
        st.caption('An expense increase affects the institutional support target, not automatically the planned endowment payout. Lower new gifts reduce restricted asset growth, not current payout cash. Unpaid private capital calls are not carried forward as future obligations.')

if page in ('Portfolio analysis','Payout risk measures','Stress testing','Policy responses under stress','Scenario comparison'):
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
