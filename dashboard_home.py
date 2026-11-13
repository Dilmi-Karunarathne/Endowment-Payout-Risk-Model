"""Navigation and persistent detail-widget state."""
import streamlit as st


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


