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
    </style>''',unsafe_allow_html=True)


def style_figure(fig, y_title=None, height=330):
    fig.update_layout(template='plotly_dark',paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Arial, sans-serif',color='#BBC8D1',size=12),height=height,
        margin=dict(l=12,r=20,t=20,b=14),
        legend=dict(orientation='h',yanchor='bottom',y=1.02,x=0,font=dict(size=11)),
        hovermode='x unified',colorway=[TEAL,AMBER,'#83AEE0','#C3A6E8'])
    fig.update_xaxes(showgrid=False,zeroline=False,title='Projection year')
    fig.update_yaxes(gridcolor='#34434D',zeroline=False,title=y_title)
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
        fillcolor='rgba(89,201,190,.16)',name='10th–90th percentile',hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=x,y=mid,mode='lines',name=line_label,line=dict(color=TEAL,width=3),
        hovertemplate='%{y:,.2f}M<extra></extra>'))
    fig.add_trace(go.Scatter(x=[0,x[-1]],y=[initial_value,initial_value],mode='lines',name=reference_label,
        line=dict(color=AMBER,width=1.5,dash='dash'),hoverinfo='skip'))
    style_figure(fig,'Value in today’s dollars ($M)',height=340)
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
