import streamlit as st
import pandas as pd
import os
from utils import guidance, pdf_tools

HISTORY_FILE = "history.csv"

def main():
    st.title("Seker V2 — AI Design Quality Auditor")

    tab = st.sidebar.radio("Navigation", ["Audit", "Training", "Analytics", "Settings"])

    if tab == "Audit":
        st.header("Audit")
        st.write("Upload a PDF and run quality checks against rules and guidance.")
    elif tab == "Training":
        st.header("Training")
        st.write("Upload audited reports or append quick rules here.")
    elif tab == "Analytics":
        st.header("Analytics")
        st.write("View history of audits and filter by project/supplier.")
    elif tab == "Settings":
        st.header("Settings & Guidance")
        root = st.text_input("Guidance root path", value="C:\\Mac\\Home\\Music\\Guidance")
        if st.button("Reload guidance"):
            st.session_state['guidance'] = guidance.build_index_from_folder(root)
        st.write("Rules editor and YAML configs below...")

if __name__ == "__main__":
    main()
