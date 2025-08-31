import streamlit as st

def training_ui():
    st.write("Upload Excel/JSON for training. Validate findings (Accept/Reject).")
    st.file_uploader("Upload audited record", type=["xlsx","json"])

def analytics_ui():
    st.write("Trend analytics dashboard placeholder.")
