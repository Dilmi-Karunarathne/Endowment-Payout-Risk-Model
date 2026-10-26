"""Streamlit renderer; scenarios are implemented in stress_testing.py."""
import streamlit as st
import plotly.express as px


def render_stress_results(table, sensitivity=None):
    st.caption('Illustrative scenarios. All cases call the same payout and accounting engine.')
    st.dataframe(table, use_container_width=True)
    st.plotly_chart(px.bar(table, x='Scenario', y='Median terminal real corpus ($M)'), use_container_width=True)
    if sensitivity is not None:
        st.subheader('Mixture probability and severity sensitivity')
        st.caption('One factor at a time; severity shifts are quarterly percentage points. Fixed inflation isolates the return effect.')
        st.dataframe(sensitivity, use_container_width=True)
