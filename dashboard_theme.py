"""Dashboard palette. Edit theme.json and rerun the app."""
import json
from pathlib import Path
import streamlit as st

def palette():
    return json.loads(Path(__file__).with_name("theme.json").read_text())

def apply_theme():
    c = palette()
    variables = ";".join("--"+k.replace("_","-")+":"+v for k,v in c.items() if isinstance(v,str))
    css = """
:root {VARIABLES}
[data-testid="stAppViewContainer"], .stApp {background:var(--background);color:var(--text)}
[data-testid="stHeader"] {background:var(--header)}
[data-testid="stSidebar"] {background:var(--sidebar)}
[data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"], label, [data-testid="stMetricValue"] {color:var(--text)!important}
h1,h2,h3,h4 {color:var(--heading)!important}
[data-testid="stCaptionContainer"], .intro,.selection,[data-testid="stMetricLabel"] {color:var(--muted)!important}
[data-testid="stMetric"],.empty-state,[data-testid="stVerticalBlockBorderWrapper"]>div {background:var(--card);border-color:var(--border)!important}
.empty-state h2 {color:var(--heading)}
.empty-state p {color:var(--muted)}
[data-baseweb="input"],[data-baseweb="input"]>div,[data-baseweb="textarea"],[data-baseweb="select"]>div,
[data-testid="stNumberInput"] input, input, textarea {background:var(--input-background)!important;color:var(--input-text)!important;border-color:var(--border)!important}
[data-baseweb="select"] span,[data-baseweb="select"] input {color:var(--input-text)!important}
[data-baseweb="select"] svg {fill:var(--input-text)!important}
[data-baseweb="popover"],[role="listbox"],[role="option"],[data-baseweb="menu"] {background:var(--dropdown-background)!important;color:var(--dropdown-text)!important}
[role="option"]:hover,[role="option"][aria-selected="true"] {background:var(--dropdown-hover)!important}
[data-testid="stButton"] button,[data-testid="stDownloadButton"] button {background:var(--button-background);color:var(--button-text);border-color:var(--border)}
[data-testid="stButton"] button p,[data-testid="stDownloadButton"] button p {color:inherit!important}
[data-testid="stButton"] button[kind="primary"] {background:var(--primary)!important;color:var(--primary-text)!important;border-color:var(--primary)!important}
[data-testid="stButton"] button:hover {border-color:var(--primary)!important}
[data-testid="stExpander"] details,[data-testid="stExpander"] summary {background:var(--card)!important;color:var(--text)!important;border-color:var(--border)!important}
[data-testid="stSlider"] [data-baseweb="slider"]>div>div {background:var(--slider-track)!important}
[data-testid="stSlider"] [data-baseweb="slider"]>div>div>div {background:var(--slider-fill)!important}
[data-testid="stSlider"] [role="slider"] {background:var(--slider-thumb)!important}
[data-testid="stSlider"] [data-testid="stThumbValue"] {color:var(--slider-fill)!important}
input[type="checkbox"],input[type="radio"] {accent-color:var(--primary)}
[data-baseweb="checkbox"]:has(input:checked)>span,[data-baseweb="radio"]:has(input:checked)>div {background-color:var(--primary)!important;border-color:var(--primary)!important}
[data-testid="stNumberInput"] button {background:var(--input-background)!important;color:var(--input-text)!important}
[data-testid="stTooltipContent"] {background:var(--card)!important;color:var(--text)!important}
[data-baseweb="tag"] {background:var(--dropdown-hover)!important;color:var(--dropdown-text)!important}
a {color:var(--primary)}

[data-testid="stCheckbox"] label>span,[data-testid="stToggle"] label>div {border-color:var(--primary)}
[data-testid="stAlert"] [data-testid="stMarkdownContainer"] {color:inherit!important}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {background:var(--success-background)!important;color:var(--success-text)!important}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {background:var(--warning-background)!important;color:var(--warning-text)!important}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {background:var(--error-background)!important;color:var(--error-text)!important}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {background:var(--info-background)!important;color:var(--info-text)!important}
[data-testid="stTabs"] [aria-selected="true"] {color:var(--primary)!important}
[data-testid="stProgress"] [role="progressbar"]>div {background:var(--primary)!important}
"""
    st.markdown("<style>"+css.replace("VARIABLES",variables)+"</style>", unsafe_allow_html=True)
