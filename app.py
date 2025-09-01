
import io
from pathlib import Path
import json
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

from modules import audit as audit_mod
from modules import rules as rules_mod
from modules import training as training_mod
from modules import analytics as analytics_mod
from modules import pdf_tools
from modules.utils import save_history_row

    st.set_page_config(page_title="Seker V2 — AI Design Quality Auditor", layout="wide", page_icon="🛰️")
    with st.sidebar:
        st.image("assets/logo.png", width=120)
        st.markdown("### Seker V2")
        st.caption("AI Design Quality Auditor")

    tabs = st.tabs(["Audit", "Train", "Analytics", "Settings"])
    ruleset = rules_mod.load_ruleset()

    # --- AUDIT TAB ---
    with tabs[0]:
        st.header("Audit")
        with st.form("audit_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                project = st.selectbox("Project", ["Upgrade", "Power Resilience", "Other"], index=0)
                site_address = st.text_input("Site Address *")
                radio_location = st.selectbox("Radio Location", ruleset.get("settings", {}).get("radio_locations", []))
            with col2:
                supplier = st.text_input("Supplier (analytics only)")
                drawing_title = st.text_input("Drawing Title *")
                template = st.selectbox("Template", ["GA","DD","MSV","Access","MS6"])
            with col3:
                # MIMO controls
                hide_mimo_for = ruleset.get("settings", {}).get("hide_mimo_if_project_equals", "Power Resilience")
                show_mimo = project != hide_mimo_for
                use_s1_for_all = False
                mimo_vals = {}
                if show_mimo:
                    st.markdown("**Per-Sector MIMO**")
                    use_s1_for_all = st.checkbox("Use S1 for all sectors")
                    mimo_s1 = st.selectbox("MIMO S1", ["1x1","2x2","4x4","8x8","Custom"], index=1)
                    mimo_vals["mimo_S1"] = mimo_s1
                    if use_s1_for_all:
                        mimo_vals.update({f"mimo_{s}": mimo_s1 for s in ["S2","S3","S4"]})
                    else:
                        for s in ["S2","S3","S4"]:
                            mimo_vals[f"mimo_{s}"] = st.selectbox(f"MIMO {s}", ["1x1","2x2","4x4","8x8","Custom"], index=1)
                else:
                    st.info(f"MIMO selections hidden for project '{hide_mimo_for}'.")

            st.divider()
            st.subheader("Inputs")
            checklist_file = st.file_uploader("Checklist (Excel)", type=["xlsx","xls","csv"])
            pdfs = st.file_uploader("Design PDFs (optional, for annotation bundle)", type=["pdf"], accept_multiple_files=True)
            exclude_analytics = st.checkbox("Exclude this run from analytics", value=False)
            submitted = st.form_submit_button("Run Audit")

        if submitted:
            # Mandatory metadata
            if not site_address or not drawing_title:
                st.error("Please complete required fields: Site Address and Drawing Title.")
            else:
                # Load checklist
                if checklist_file is None:
                    st.warning("No checklist provided — using templates/checklist_template.xlsx")
                    checklist_path = Path("templates/checklist_template.xlsx")
                    checklist_df = pd.read_excel(checklist_path) if checklist_path.exists() else pd.read_csv("templates/checklist_template.csv")
                else:
                    if checklist_file.name.lower().endswith(".csv"):
                        checklist_df = pd.read_csv(checklist_file)
                    else:
                        checklist_df = pd.read_excel(checklist_file)

                metadata = {
                    "project": project,
                    "supplier": supplier,
                    "site_address": site_address,
                    "drawing_title": drawing_title,
                    "radio_location": radio_location,
                    "template": template,
                    **mimo_vals
                }

                result = audit_mod.run_audit(metadata, checklist_df, ruleset)
                st.success("Audit complete.")
                st.dataframe(result["errors"], use_container_width=True)

                # Provide Excel download
                with open(result["excel_path"], "rb") as f:
                    st.download_button("Download Rejection Report (Excel)", data=f, file_name=Path(result["excel_path"]).name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

                # PDF annotation bundle (single combined notes file)
                notes = result.get("notes", [])
                if notes:
                    pdf_path = pdf_tools.create_annotation_bundle("audit_notes", notes, Path("reports"))
                    with open(pdf_path, "rb") as f:
                        st.download_button("Download Annotated PDF (notes bundle)", data=f, file_name=Path(pdf_path).name, mime="application/pdf")
                else:
                    st.info("No notes to annotate.")

                # Save history row (unless excluded)
                history_payload = {
                    "When": pd.Timestamp.now().isoformat(timespec="seconds"),
                    "Project": project,
                    "Supplier": supplier,
                    "Site Address": site_address,
                    "Drawing Title": drawing_title,
                    "Template": template,
                    "Errors": int(len(result["errors"])),
                    "Excluded": bool(exclude_analytics),
                    "Status": "Rejected" if len(result["errors"]) else "Accepted"
                }
                hp = save_history_row(history_payload, exclude=exclude_analytics)
                st.caption(f"Saved run summary → {hp.name}")

    # --- TRAIN TAB ---
    with tabs[1]:
        st.header("Train")
        st.write("Bulk re-upload Excel (Valid/Not-Valid labels) to attach training labels to each rule.")
        up = st.file_uploader("Training Excel", type=["xlsx"])
        if st.button("Apply Training", disabled=up is None):
            training_mod.apply_training(up)
            st.success("Training labels applied to ruleset.")

        st.subheader("Quick add one rule")
        with st.form("quick_rule"):
            r_id = st.text_input("Rule ID *")
            r_type = st.text_input("Type *", value="string_match")
            r_desc = st.text_input("Description *")
            r_sev = st.selectbox("Severity", ["minor","major","critical"], index=0)
            ok = st.form_submit_button("Add Rule")
        if ok and r_id and r_type and r_desc:
            training_mod.quick_add_rule(r_id, r_type, r_desc, r_sev)
            st.success(f"Rule '{r_id}' added.")

        st.subheader("Edit YAML (optional)")
        data = rules_mod.load_ruleset()
        yaml_str = st.text_area("Ruleset YAML", value=json.dumps(data, indent=2).replace("{", "{
").replace("}", "
}"), height=300, help="For convenience this shows JSON. Use Settings to edit YAML.")
        st.caption("Tip: For full YAML editing, go to Settings tab.")

    # --- ANALYTICS TAB ---
    with tabs[2]:
        st.header("Analytics")
        df = analytics_mod.load_history(Path("history"))
        if df.empty:
            st.info("No history yet.")
        else:
            st.dataframe(df.tail(200), use_container_width=True)
            st.subheader("Trend — Errors per run")
            fig, ax = plt.subplots()
            df["Errors"].plot(kind="line", ax=ax)
            ax.set_xlabel("Run index")
            ax.set_ylabel("Errors")
            st.pyplot(fig)

    # --- SETTINGS TAB ---
    with tabs[3]:
        st.header("Settings")
        st.write("Edit the YAML ruleset and download templates.")
        # Show YAML text area
        import yaml
        rs = rules_mod.load_ruleset()
        yaml_text = st.text_area("default_rules.yaml", value=yaml.safe_dump(rs, sort_keys=False, allow_unicode=True), height=400)
        if st.button("Save Ruleset"):
            try:
                new_rs = yaml.safe_load(yaml_text)
                rules_mod.save_ruleset(new_rs)
                st.success("Ruleset saved.")
            except Exception as e:
                st.error(f"Failed to parse YAML: {e}")

        with open("templates/checklist_template.xlsx", "rb") as f:
            st.download_button("Download Checklist Template (Excel)", data=f, file_name="checklist_template.xlsx")
        with open("templates/training_template.xlsx", "rb") as f:
            st.download_button("Download Training Template (Excel)", data=f, file_name="training_template.xlsx")
