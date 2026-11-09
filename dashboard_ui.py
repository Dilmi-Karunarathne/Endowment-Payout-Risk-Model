"""Presentation helpers. All charts use current simulation results."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

TEAL = '#59C9BE'
AMBER = '#E3B46D'


def apply_style():
    st.markdown("""<style>
    .stApp {background:#F5F7FA;color:#19212B;}
    .block-container {padding-top:1.5rem;padding-bottom:2.5rem;max-width:1600px;}
    h1 {font-size:1.8rem !important;font-weight:700 !important;letter-spacing:-.05rem;}
    h2 {font-size:1.2rem !important;letter-spacing:-.02rem;}
    h3 {font-size:1.03rem !important;}
    p,li {line-height:1.5;}
    [data-testid="stSidebar"] {background:#FFFFFF;border-right:1px solid #DFE4EB;}
    [data-testid="stSidebar"] h3 {font-size:.82rem !important;letter-spacing:.07em;text-transform:uppercase;}
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {font-size:.86rem;}
    [data-testid="stMetric"] {background:#FFF;border:1px solid #DFE4EB;border-radius:12px;padding:18px 20px;min-height:120px;}
    [data-testid="stMetricValue"] {font-size:2rem;font-weight:650;color:#19212B;}
    [data-testid="stMetricLabel"] {color:#626D7C;font-size:.8rem;}
    [data-testid="stButton"] button {border-radius:8px;font-weight:500;}
    [data-testid="stButton"] button[kind="primary"] {background:#2663AD;border-color:#2663AD;color:white;}
    [data-testid="stExpander"], [data-testid="stVerticalBlockBorderWrapper"]>div {border-radius:12px;}
    [data-testid="stVerticalBlockBorderWrapper"]>div {background:#FFF;}
    [data-testid="stCaptionContainer"] {color:#697587;}
    .intro {color:#657083;font-size:.94rem;max-width:780px;margin-top:-.5rem;margin-bottom:.9rem;}
    .context-strip {padding:11px 15px;border:1px solid #DFE4EB;border-radius:9px;background:#FFF;font-size:.85rem;color:#606B7A;margin:14px 0 18px;}
    .context-strip b {color:#202A38;font-weight:600;}
    .empty-state {border:1px solid #DCE4EF;border-radius:12px;padding:38px;background:#FFF;margin-top:1rem;}
    .empty-state p {color:#657083;}
    .selection {color:#657083;font-size:.85rem;margin-bottom:16px;}
    [class*="st-key-open_"] button {min-height:38px;width:100%;font-size:.82rem;background:#FFF;border:1px solid #DFE4EB;padding:7px 9px;}
    [class*="st-key-open_"] button:hover {border-color:#2663AD;color:#2663AD;}
    @media (max-width:800px) {.block-container{padding:1rem;} h1{font-size:1.5rem !important;} [data-testid="stMetricValue"]{font-size:1.6rem;}}
    </style>""",unsafe_allow_html=True)


def chart_theme():
    return {'dark':False,'colors':['#2663AD','#D29A38','#398B79','#8868AF'],
            'text':'#566273','grid':'#E6EAF0'}


def chart_band_fill():
    color=chart_theme()['colors'][0].lstrip('#')
    if len(color)!=6:return 'rgba(0,104,201,.16)'
    return 'rgba('+','.join(str(int(color[i:i+2],16)) for i in (0,2,4))+',.16)'


def style_figure(fig, y_title=None, height=330, recolor=True):
    theme=chart_theme()
    fig.update_layout(template='plotly_dark' if theme['dark'] else 'plotly_white',paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Arial, sans-serif',color=theme['text'],size=12),height=height,
        margin=dict(l=12,r=20,t=20,b=14),
        legend=dict(orientation='h',yanchor='bottom',y=1.02,x=0,font=dict(size=11)),
        hovermode='x unified',colorway=theme['colors'])
    fig.update_xaxes(showgrid=False,zeroline=False,title='Projection year')
    fig.update_yaxes(gridcolor=theme['grid'],zeroline=False,title=y_title)
    if recolor:
        for index,trace in enumerate(fig.data):
            color=theme['colors'][index%len(theme['colors'])]
            if trace.type in ['bar','histogram']:trace.update(marker_color=color)
            elif trace.type=='scatter':trace.update(line_color=color,marker_color=color)
    return fig


def band_chart(annual, column, initial_value, start_year, line_label, reference_label):
    frame=annual.groupby('year')[column].quantile([.05,.25,.5,.75,.95]).unstack()
    x=[0]+[int(y-start_year+1) for y in frame.index]
    series=lambda q:[initial_value]+frame[q].tolist()
    fig=go.Figure()
    for lower,upper,color,label in [(.05,.95,'rgba(141,184,238,.32)','5th–95th percentile'),(.25,.75,'rgba(83,145,223,.45)','25th–75th percentile')]:
        fig.add_trace(go.Scatter(x=x,y=series(lower),mode='lines',line=dict(width=0),showlegend=False,hoverinfo='skip'))
        fig.add_trace(go.Scatter(x=x,y=series(upper),mode='lines',line=dict(width=0),fill='tonexty',fillcolor=color,name=label,hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=x,y=series(.5),mode='lines',name=line_label,
        line=dict(color='#2663AD',width=2.5),hovertemplate='$%{y:,.2f}M<extra></extra>'))
    fig.add_trace(go.Scatter(x=[0,x[-1]],y=[initial_value]*2,mode='lines',name=reference_label,
        line=dict(color='#8993A0',width=1.3,dash='dash'),hoverinfo='skip'))
    style_figure(fig,None,height=330,recolor=False)
    fig.update_layout(legend=dict(y=-.20,yanchor='top',font=dict(size=10)),margin=dict(l=12,r=12,t=12,b=65))
    fig.update_xaxes(dtick=max(1,int(np.ceil(x[-1]/5))),title='Projection year')
    fig.update_yaxes(tickprefix='$',ticksuffix='M')
    return fig


def risk_table(metrics):
    percent = [
        ('Years with returns below planned payout','annual_coverage_shortfall_probability'),
        ('Chance total wealth cannot fund planned payout','probability_at_least_one_shortfall'),
        ('Chance of any liquidity constraint breach','probability_liquidity_breach'),
        ('Chance of a real payout cut greater than 5%','probability_real_payout_cut'),
        ('Median annual real payout-growth volatility','median_payout_volatility'),
        ('Years with a payout funding shortfall','annual_shortfall_probability'),
        ('Average funding gap when a shortfall occurs','average_relative_shortfall_depth'),
        ('Chance of principal falling below the selected threshold','probability_real_corpus_erosion'),
        ('Terminal real-principal loss: Value at Risk','var_terminal_real_corpus_loss'),
        ('Terminal real-principal loss: Expected Shortfall','expected_shortfall_terminal_real_corpus_loss'),
        ('Chance of an institutional support gap','probability_any_support_gap'),
    ]
    rows=[{'Measure':label,'Result':f'{metrics[key]:.1%}'} for label,key in percent]
    for label,key in [('Median longest return-coverage shortfall','median_longest_coverage_spell'),
                      ('Median longest payout funding shortfall','median_longest_funding_spell'),
                      ('Median time below principal threshold','median_erosion_years')]:
        rows.append({'Measure':label,'Result':f'{metrics[key]:g} years'})
    return pd.DataFrame(rows)


def comparison_display(table):
    renamed=table.rename(columns={
        'Scenario':'Option',
        'Pr(liquidity constraint breach)':'Liquidity breach risk',
        'Pr(real payout cut >5%)':'Real payout-cut risk (>5%)',
        'Median minimum liquid share':'Minimum liquid share (median)',
        'Pr(any payout funding shortfall)':'Total-wealth payout shortfall',
        'Annual return-coverage shortfall':'Years with uncovered payouts',
        'Annual payout funding shortfall':'Years with funding shortfalls',
        'Conditional funding depth':'Average funding gap',
        'Pr(real corpus erosion)':'Principal erosion risk',
        'Median terminal real corpus ($M)':'Ending real endowment ($M)',
        'Median cumulative real payouts ($M)':'Total real payouts ($M)',
        'Terminal real-corpus ES':'Expected Shortfall',
        'Pr(unpaid other obligation)':'Other unpaid obligation risk',
    }).copy()
    for key in ['Total-wealth payout shortfall','Years with uncovered payouts','Years with funding shortfalls',
                'Average funding gap','Principal erosion risk','Expected Shortfall','Other unpaid obligation risk',
                'Liquidity breach risk','Real payout-cut risk (>5%)','Minimum liquid share (median)']:
        if key in renamed:
            renamed[key]=renamed[key].map(lambda value:f'{value:.1%}')
    for key in ['Ending real endowment ($M)','Total real payouts ($M)']:
        if key in renamed:
            renamed[key]=renamed[key].map(lambda value:f'{value:,.2f}')
    return renamed
