"""Presentation helpers. All charts use current simulation results."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

TEAL = '#59C9BE'
AMBER = '#E3B46D'


def apply_style():
    st.markdown('''<style>
    .block-container {padding-top:2.2rem;padding-bottom:2rem;max-width:1500px;}
    h1 {font-size:2.4rem !important;font-weight:650 !important;letter-spacing:-.055rem;}
    h2 {font-size:1.3rem !important;letter-spacing:-.02rem;}
    h3 {font-size:1.1rem !important;}
    [data-testid="stSidebar"] .block-container {padding-top:1.6rem;}
    [data-testid="stMetric"] {background:#1C2932;border:1px solid #31424D;border-radius:14px;padding:20px 22px;min-height:128px;}
    [data-testid="stMetricValue"] {font-size:2.35rem;font-weight:600;}
    [data-testid="stMetricLabel"] {color:#BDC9D1;}
    [data-testid="stTabs"] [data-baseweb="tab-list"] {gap:1.3rem;border-bottom:1px solid #31424D;}
    [data-testid="stTabs"] [data-baseweb="tab"] {padding-bottom:12px;}
    [data-testid="stButton"] button {border-radius:9px;}
    [data-testid="stExpander"] {border-radius:10px;}
    .intro {color:#AABAC5;font-size:1.08rem;margin-top:-.5rem;margin-bottom:1.7rem;}
    .empty-state {border:1px solid #31424D;border-radius:16px;padding:48px 32px;background:#1C2932;margin-top:1.4rem;}
    .empty-state h2 {margin:0 0 10px 0;color:#EDF2F5;}
    .empty-state p {color:#AABAC5;margin:0;line-height:1.7;}
    .selection {color:#AABAC5;font-size:.9rem;margin:0 0 18px 0;}
    @media (max-width:700px) {.block-container {padding:1rem;} h1 {font-size:1.8rem !important;} [data-testid="stMetricValue"] {font-size:1.9rem;}}
    /* Card layout only: colors and theme remain the original app defaults. */
    [class*="st-key-open_"] button {width:100%;min-height:350px;align-items:flex-start;justify-content:flex-start;text-align:left;padding:20px 18px 180px;background-size:calc(100% - 32px) 150px;background-repeat:no-repeat;background-position:center bottom 16px;}
    [class*="st-key-open_"] button p {white-space:pre-line;text-align:left;}
    </style>''',unsafe_allow_html=True)


def chart_theme():
    """Read chart appearance without changing the app's active theme."""
    def option(key):
        try:return st.get_option(key)
        except (KeyError,RuntimeError):return None
    try:
        dark=st.context.theme.type=='dark'
    except (AttributeError,KeyError):
        dark=option('theme.base')=='dark'
    configured=option('theme.chartCategoricalColors')
    colors=list(configured) if configured else (['#83C9FF','#FFABAB','#7DEFA1','#BDA6FF'] if dark else ['#0068C9','#C55A11','#16834B','#8055AD'])
    if len(colors)<2:colors+=['#C55A11','#16834B']
    primary=option('theme.primaryColor')
    if primary:colors=[primary]+[color for color in colors if color!=primary]
    return {'dark':dark,'colors':colors,'text':option('theme.textColor') or ('#FAFAFA' if dark else '#262730'),
        'grid':'#34434D' if dark else '#E5E7EB'}


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
    frame=annual.groupby('year')[column].quantile([.1,.5,.9]).unstack()
    x=[0]+[int(y-start_year+1) for y in frame.index]
    low=[initial_value]+frame[.1].tolist()
    mid=[initial_value]+frame[.5].tolist()
    high=[initial_value]+frame[.9].tolist()
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=x,y=low,mode='lines',line=dict(width=0),showlegend=False,hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=x,y=high,mode='lines',line=dict(width=0),fill='tonexty',
        fillcolor=chart_band_fill(),name='10th–90th percentile',hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=x,y=mid,mode='lines',name=line_label,line=dict(color=chart_theme()['colors'][0],width=3),
        hovertemplate='%{y:,.2f}M<extra></extra>'))
    fig.add_trace(go.Scatter(x=[0,x[-1]],y=[initial_value,initial_value],mode='lines',name=reference_label,
        line=dict(color=chart_theme()['colors'][1],width=1.5,dash='dash'),hoverinfo='skip'))
    style_figure(fig,'Value in today’s dollars ($M)',height=340,recolor=False)
    fig.update_xaxes(dtick=max(1,int(np.ceil(x[-1]/5))))
    fig.update_yaxes(tickprefix='$',ticksuffix='M')
    return fig


def risk_table(metrics):
    percent = [
        ('Years with returns below planned payout','annual_coverage_shortfall_probability'),
        ('Chance of any payout funding shortfall','probability_at_least_one_shortfall'),
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
        'Pr(any payout funding shortfall)':'Funding shortfall risk',
        'Annual return-coverage shortfall':'Years with uncovered payouts',
        'Annual payout funding shortfall':'Years with funding shortfalls',
        'Conditional funding depth':'Average funding gap',
        'Pr(real corpus erosion)':'Principal erosion risk',
        'Median terminal real corpus ($M)':'Ending real endowment ($M)',
        'Median cumulative real payouts ($M)':'Total real payouts ($M)',
        'Terminal real-corpus ES':'Expected Shortfall',
        'Pr(unpaid other obligation)':'Other unpaid obligation risk',
    }).copy()
    for key in ['Funding shortfall risk','Years with uncovered payouts','Years with funding shortfalls',
                'Average funding gap','Principal erosion risk','Expected Shortfall','Other unpaid obligation risk']:
        if key in renamed:
            renamed[key]=renamed[key].map(lambda value:f'{value:.1%}')
    for key in ['Ending real endowment ($M)','Total real payouts ($M)']:
        if key in renamed:
            renamed[key]=renamed[key].map(lambda value:f'{value:,.2f}')
    return renamed
