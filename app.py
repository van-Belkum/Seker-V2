import streamlit as st
import pandas as pd
import yaml
import os
from utils.guidance_loader import load_guidance, search_guidance
from utils.pdf_tools import extract_text_from_pdf, annotate_pdf
from utils.training_manager import add_rule, validate_rule

def main():
    st.title("Seker V2 - AI Design Quality Auditor")

    menu = ["Audit", "Training", "Analytics", "Settings"]
    choice = st.sidebar.radio("Navigation", menu)

    if choice == "Audit":
        st.header("Run Audit")
        st.info("Upload PDF and run audit against loaded guidance")
        # TODO: Add metadata, audit, PDF + Excel export

    elif choice == "Training":
        st.header("Training")
        st.info("Accept/Reject findings, bulk upload, or add rules")

    elif choice == "Analytics":
        st.header("Analytics")
        st.info("Supplier, Client, Project filters + trendline")

    elif choice == "Settings":
        st.header("Settings")
        st.info("Upload guidance ZIP and manage rules")

if __name__ == "__main__":
    main()
