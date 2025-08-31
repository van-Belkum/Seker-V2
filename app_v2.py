import os, io, json, time, base64, hashlib, datetime as dt
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

import streamlit as st
import pandas as pd
import yaml

from rules_engine import load_active_rules_for_meta, run_rule_checks, merge_feedback_into_rules, RULES_DIR, HISTORY_DIR
from guidance_ingest import secure_store_guidance, list_guidance_versions, supersede_guidance, parse_guidance_to_rules
from annotator import annotate_pdf_with_findings

# ----------------------- Config -----------------------
APP_TITLE = "Seker V2 – AI Design Quality Auditor"
ENTRY_PASSWORD = os.environ.get("SEKER_ENTRY_PW", "Seker123")         # gate for all users
ADMIN_PASSWORD = os.environ.get("SEKER_ADMIN_PW", "vanB3lkum21")      # admin only features

DATA_DIR = "data"
EXPORT_DIR = os.path.join(DATA_DIR, "exports")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(EXPORT_DIR, exist_ok=True)

SUPPLIERS_LIST = [
    "KTL","Telent","F&L","Mono","Dawnus","WB Power","Mitie","Nokia Services","Ericsson Services","BAI/BT","BT TSO",
    "Speedy","T-Mobile Build","Cellnex Build","Cornerstone Build","MBNL Build","H3G Build","Vodafone Build"
]

CLIENTS = ["BTEE","Vodafone","MBNL","H3G","Cornerstone","Cellnex"]
PROJECTS = ["RAN","Power Resilience","East Unwind","Beacon 4"]
SITE_TYPES = ["Greenfield","Rooftop","Streetworks"]
VENDORS = ["Ericsson","Nokia"]
CAB_LOC = ["Indoor","Outdoor"]
RADIO_LOC = ["Low Level","Midway","High Level","Unique Coverage"]
SECTOR_QTY = [1,2,3,4,5,6]

MIMO_CHOICES = [
    "18 @2x2","18 @2x2; 26 @4x4","18 @2x2; 70\\80 @2x2","18 @2x2; 80 @2x2",
    "18\\21 @2x2","18\\21 @2x2; 26 @4x4","18\\21 @2x2; 3500 @32x32","18\\21 @2x2; 70\\80 @2x2","18\\21 @2x2; 80 @2x2",
    "18\\21 @4x4","18\\21 @4x4; 3500 @32x32","18\\21 @4x4; 70 @2x4","18\\21 @4x4; 70\\80 @2x2",
    "18\\21 @4x4; 70\\80 @2x2; 3500 @32x32","18\\21 @4x4; 70\\80 @2x4","18\\21 @4x4; 70\\80 @2x4; 3500 @32x32",
    "18\\21 @4x4; 70\\80 @2x4; 3500 @8x8","18\\21@4x4; 70\\80 @2x2","18\\21@4x4; 70\\80 @2x4",
    "18\\21\\26 @2x2","18\\21\\26 @2x2; 3500 @32x32","18\\21\\26 @2x2; 3500 @8X8",
    "18\\21\\26 @2x2; 70\\80 @2x2","18\\21\\26 @2x2; 70\\80 @2x2; 3500 @32x32",
    "18\\21\\26 @2x2; 70\\80 @2x2; 3500 @8x8","18\\21\\26 @2x2; 70\\80 @2x4; 3500 @32x32",
    "18\\21\\26 @2x2; 80 @2x2","18\\21\\26 @2x2; 80 @2x2; 3500 @8x8",
    "18\\21\\26 @4x4","18\\21\\26 @4x4; 3500 @32x32","18\\21\\26 @4x4; 3500 @8x8",
    "18\\21\\26 @4x4; 70 @2x4; 3500 @8x8","18\\21\\26 @4x4; 70\\80 @2x2",
    "18\\21\\26 @4x4; 70\\80 @2x2; 3500 @32x32","18\\21\\26 @4x4; 70\\80 @2x2; 3500 @8x8",
    "18\\21\\26 @4x4; 70\\80 @2x4","18\\21\\26 @4x4; 70\\80 @2x4; 3500 @32x32",
    "18\\21\\26 @4x4; 70\\80 @2x4; 3500 @8x8","18\\21\\26 @4x4; 80 @2x2",
    "18\\21\\26 @4x4; 80 @2x2; 3500 @32x32","18\\21\\26 @4x4; 80 @2x4",
    "18\\21\\26 @4x4; 80 @2x4; 3500 @8x8","18\\26 @2x2","18\\26 @4x4; 21 @2x2; 80 @2x2"
]

# ----------------------- Helpers -----------------------
def gate() -> bool:
    st.session_state.setdefault("entry_ok", False)
    if st.session_state["entry_ok"]:
        return True
    pw = st.text_input("Enter access password", type="password")
    if st.button("Enter"):
        st.session_state["entry_ok"] = (pw == ENTRY_PASSWORD)
        if not st.session_state["entry_ok"]:
            st.error("Wrong password.")
        st.experimental_rerun()
    st.stop()

def is_admin() -> bool:
    st.session_state.setdefault("admin_ok", False)
    with st.expander("Admin login", expanded=False):
        if not st.session_state["admin_ok"]:
            apw = st.text_input("Admin password", type="password", key="admin_pw")
            if st.button("Login as Admin"):
                st.session_state["admin_ok"] = (apw == ADMIN_PASSWORD)
                if not st.session_state["admin_ok"]:
                    st.warning("Invalid admin password.")
    return st.session_state["admin_ok"]

def save_history_row(meta: Dict[str, Any], status: str, findings: List[Dict[str, Any]], excel_name: str, pdf_name: str, exclude: bool):
    os.makedirs(HISTORY_DIR, exist_ok=True)
    fn = os.path.join(HISTORY_DIR, "history.csv")
    row = {
        "timestamp_utc": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "supplier": meta.get("supplier",""),
        "client": meta.get("client",""),
        "project": meta.get("project",""),
        "site_type": meta.get("site_type",""),
        "vendor": meta.get("vendor",""),
        "cabinet_location": meta.get("cabinet_location",""),
        "radio_location": meta.get("radio_location",""),
        "sectors": meta.get("sectors",0),
        "mimo_s1": meta.get("mimo_s1",""),
        "mimo_s2": meta.get("mimo_s2",""),
        "mimo_s3": meta.get("mimo_s3",""),
        "mimo_s4": meta.get("mimo_s4",""),
        "mimo_s5": meta.get("mimo_s5",""),
        "mimo_s6": meta.get("mimo_s6",""),
        "site_address": meta.get("site_address",""),
        "status": status,
        "pdf_name": pdf_name,
        "excel_name": excel_name,
        "exclude": bool(exclude),
        "n_findings": len(findings),
    }
    df = pd.DataFrame([row])
    if os.path.exists(fn):
        df.to_csv(fn, mode="a", index=False, header=False)
    else:
        df.to_csv(fn, index=False)

def download_button_bytes(label: str, data: bytes, file_name: str, mime: str):
    st.download_button(label, data=data, file_name=file_name, mime=mime)

# ----------------------- UI Blocks -----------------------
def sidebar_meta() -> Dict[str, Any]:
    st.subheader("Audit Metadata")
    supplier = st.selectbox("Supplier (analytics only)", SUPPLIERS_LIST, index=0, key="supplier")
    client = st.selectbox("Client", CLIENTS, index=0, key="client")
    project = st.selectbox("Project", PROJECTS, index=0, key="project")
    site_type = st.selectbox("Site Type", SITE_TYPES, index=0, key="site_type")
    vendor = st.selectbox("Proposed Vendor", VENDORS, index=0, key="vendor")
    cabinet_location = st.selectbox("Proposed Cabinet Location", CAB_LOC, index=0, key="cab_loc")
    radio_location = st.selectbox("Proposed Radio Location", RADIO_LOC, index=0, key="radio_loc")
    sectors = st.selectbox("Quantity of Sectors", SECTOR_QTY, index=2, key="sectors")

    hide_mimo = (project == "Power Resilience")
    st.caption("Proposed MIMO Config (hidden when Project = Power Resilience)")
    mimo_s1 = st.selectbox("MIMO S1", MIMO_CHOICES, disabled=hide_mimo, key="mimo_s1")
    copy_all = st.checkbox("Use S1 config for all sectors", value=True, disabled=hide_mimo)
    if copy_all and not hide_mimo:
        mimo_s2=mimo_s1; mimo_s3=mimo_s1; mimo_s4=mimo_s1; mimo_s5=mimo_s1; mimo_s6=mimo_s1
    else:
        mimo_s2 = st.selectbox("MIMO S2", MIMO_CHOICES, disabled=hide_mimo or sectors<2, key="mimo_s2")
        mimo_s3 = st.selectbox("MIMO S3", MIMO_CHOICES, disabled=hide_mimo or sectors<3, key="mimo_s3")
        mimo_s4 = st.selectbox("MIMO S4", MIMO_CHOICES, disabled=hide_mimo or sectors<4, key="mimo_s4")
        mimo_s5 = st.selectbox("MIMO S5", MIMO_CHOICES, disabled=hide_mimo or sectors<5, key="mimo_s5")
        mimo_s6 = st.selectbox("MIMO S6", MIMO_CHOICES, disabled=hide_mimo or sectors<6, key="mimo_s6")

    site_address = st.text_input("Site Address (must match drawing title; ignore if contains ', 0 ,')", key="site_address")

    st.divider()
    do_spell = st.checkbox("Enable spelling checks", value=True)
    exclude_from_analytics = st.checkbox("Exclude this review from analytics", value=False)

    meta = {
        "supplier": supplier,
        "client": client,
        "project": project,
        "site_type": site_type,
        "vendor": vendor,
        "cabinet_location": cabinet_location,
        "radio_location": radio_location,
        "sectors": sectors,
        "mimo_s1": st.session_state.get("mimo_s1","") if not hide_mimo else "",
        "mimo_s2": st.session_state.get("mimo_s2",mimo_s1 if not hide_mimo else ""),
        "mimo_s3": st.session_state.get("mimo_s3",mimo_s1 if not hide_mimo else ""),
        "mimo_s4": st.session_state.get("mimo_s4",mimo_s1 if not hide_mimo else ""),
        "mimo_s5": st.session_state.get("mimo_s5",mimo_s1 if not hide_mimo else ""),
        "mimo_s6": st.session_state.get("mimo_s6",mimo_s1 if not hide_mimo else ""),
        "site_address": site_address,
        "do_spell": do_spell,
        "exclude": exclude_from_analytics,
    }
    return meta

def page_header():
    st.markdown(
        """
        <div style="display:flex;align-items:center;justify-content:space-between;">
          <h2 style="margin:0;">Seker V2 – AI Design Quality Auditor</h2>
          <div style="opacity:0.9;font-size:12px;">v2.0</div>
        </div>
        <hr style="margin-top:4px;margin-bottom:6px;">
        """, unsafe_allow_html=True
    )

# ----------------------- Pages -----------------------
def page_audit():
    st.info("Fill all metadata in the sidebar, upload a single PDF, then click **Run Audit**.")
    up = st.file_uploader("Upload design PDF", type=["pdf"], accept_multiple_files=False)
    meta = sidebar_meta()

    if st.button("Run Audit", type="primary", use_container_width=True, disabled=(up is None)):
        if not up:
            st.warning("Please upload a PDF.")
            st.stop()
        raw_pdf = up.read()
        # load rules for this metadata
        rules = load_active_rules_for_meta(meta)
        # run checker pipeline
        meta["__pdf_bytes"] = raw_pdf
        pages_text = rules.get("__extracted_text", [])
        findings = run_rule_checks(pages_text, meta, rules)

        # status
        major_cnt = sum(1 for f in findings if f.get("severity","minor")=="major")
        status = "PASS" if major_cnt==0 and len(findings)==0 else "REJECTED"
        st.subheader(f"Result: {status}")
        st.write(f"Findings: {len(findings)}")

        # annotated PDF
        anno_pdf = annotate_pdf_with_findings(raw_pdf, findings)
        dt_tag = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        base = os.path.splitext(up.name)[0]
        pdf_name = f"{base}__{status}__{dt_tag}.annotated.pdf"
        excel_name = f"{base}__{status}__{dt_tag}.xlsx"

        # excel
        df = pd.DataFrame(findings)
        mem = io.BytesIO()
        with pd.ExcelWriter(mem, engine="xlsxwriter") as xw:
            df.to_excel(xw, index=False, sheet_name="Findings")
            meta_df = pd.DataFrame([meta])
            meta_df.to_excel(xw, index=False, sheet_name="Metadata")
        mem.seek(0)
        excel_bytes = mem.getvalue()

        # show & download
        st.download_button("⬇️ Download Annotated PDF", data=anno_pdf, file_name=pdf_name, mime="application/pdf", use_container_width=True)
        st.download_button("⬇️ Download Excel Report", data=excel_bytes, file_name=excel_name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

        # persist for analytics & 2-week retention
        save_history_row(meta, status, findings, excel_name, pdf_name, meta.get("exclude", False))

        st.divider()
        st.subheader("Training (per finding)")
        st.caption("Mark each finding Valid/Not Valid and optionally attach a rule update.")
        if len(findings)==0:
            st.success("No findings to train. 🎉")
        else:
            fb_payload = []
            for i, f in enumerate(findings):
                with st.expander(f"[{i+1}] {f.get('title','Finding')} — {f.get('reason','')[:90]}"):
                    st.json(f)
                    col1,col2 = st.columns(2)
                    verdict = col1.selectbox("Your verdict", ["Valid","Not Valid"], key=f"verdict_{i}")
                    rule_update = col2.text_input("New/updated rule (optional): e.g., 'X must equal Y per TDEE43001 §3.8.1'", key=f"upd_{i}")
                    fb_payload.append({"finding":f, "verdict":verdict, "rule_update":rule_update})
            if st.button("Apply Training Updates", type="primary"):
                n_upd = merge_feedback_into_rules(meta, fb_payload)
                st.success(f"Applied {n_upd} training updates to rulesets.")

def page_training():
    st.subheader("Bulk Training – Upload reviewed Excel to ingest Valid/Not Valid + new rules")
    st.caption("Upload an exported Excel review that you’ve annotated with Valid/Not Valid in a column named `verdict`, optional `rule_update` column.")
    up = st.file_uploader("Upload reviewed Excel", type=["xlsx"])
    if up:
        df = pd.read_excel(up)
        added = merge_feedback_into_rules({}, [{"finding": row.to_dict(), "verdict": row.get("verdict",""), "rule_update": row.get("rule_update","")} for _,row in df.iterrows()])
        st.success(f"Merged {added} updates from Excel.")

def page_analytics():
    st.subheader("Analytics")
    fn = os.path.join(HISTORY_DIR, "history.csv")
    if not os.path.exists(fn):
        st.info("No history yet.")
        return
    df = pd.read_csv(fn)

    # 2-week retention for UI view
    cutoff = (dt.datetime.utcnow() - dt.timedelta(days=14))
    if "timestamp_utc" in df.columns:
        ts = pd.to_datetime(df["timestamp_utc"], errors="coerce")
        df = df[ts >= cutoff]

    if "exclude" in df.columns:
        df = df[df["exclude"] != True]

    # filters
    c1,c2,c3 = st.columns(3)
    f_client = c1.multiselect("Client", sorted(df["client"].dropna().unique().tolist()), [])
    f_project = c2.multiselect("Project", sorted(df["project"].dropna().unique().tolist()), [])
    f_supplier = c3.multiselect("Supplier", sorted(df["supplier"].dropna().unique().tolist()), [])
    if f_client: df = df[df["client"].isin(f_client)]
    if f_project: df = df[df["project"].isin(f_project)]
    if f_supplier: df = df[df["supplier"].isin(f_supplier)]

    show_cols = [c for c in ["timestamp_utc","supplier","client","project","status","pdf_name","excel_name","n_findings"] if c in df.columns]
    st.dataframe(df[show_cols].sort_values("timestamp_utc", ascending=False), use_container_width=True)

    # KPIs
    total = len(df)
    pass_count = (df["status"]=="PASS").sum() if "status" in df else 0
    rft = (pass_count/total*100) if total else 0
    c1,c2,c3 = st.columns(3)
    c1.metric("Audits", total)
    c2.metric("Pass", pass_count)
    c3.metric("Right First Time %", f"{rft:0.1f}%")

def page_admin():
    st.subheader("Admin – Guidance & Mappings")
    if not is_admin():
        st.info("Admin-only area. Enter admin password in the expander above.")
        return

    tab1, tab2, tab3 = st.tabs(["Upload Guidance","Mappings","Versions"])
    with tab1:
        st.write("Upload DOCX/PPTX/PDF guidance. Only admins can see/store these. They’re parsed into rules automatically and mapped by criteria.")
        up = st.file_uploader("Upload guidance", type=["docx","pptx","pdf"], accept_multiple_files=False, key="guid_up")
        client = st.selectbox("Guidance Client", CLIENTS, key="g_client")
        projects = st.multiselect("Applicable Projects", PROJECTS, key="g_projects")
        site_types = st.multiselect("Applicable Site Types", SITE_TYPES, key="g_site_types")
        tags_in = st.text_input("Tags (comma)", value="")
        tags = [t.strip() for t in tags_in.split(",") if t.strip()]
        if up and st.button("Ingest guidance"):
            raw = up.read()
            gid = secure_store_guidance(up.name, raw, visibility="private")  # private blob store
            rules_path = parse_guidance_to_rules(up.name, raw)               # YAML in rules/parsed/<hash>.yaml
            # update mapping
            map_fn = os.path.join("rules","mapping.yaml")
            os.makedirs("rules", exist_ok=True)
            mapping = {"mappings":[]}
            if os.path.exists(map_fn):
                mapping = yaml.safe_load(open(map_fn,"r")) or {"mappings":[]}
            mapping["mappings"].append({
                "guidance_id": gid,
                "rules_file": rules_path,
                "client": client,
                "projects": projects,
                "site_types": site_types,
                "tags": tags
            })
            with open(map_fn,"w") as f:
                yaml.safe_dump(mapping, f, sort_keys=False)
            st.success(f"Ingested and mapped: {up.name}")

    with tab2:
        st.write("Download & edit `rules/mapping.yaml` if needed.")
        map_fn = os.path.join("rules","mapping.yaml")
        if os.path.exists(map_fn):
            st.code(open(map_fn,"r").read(), language="yaml")
            st.download_button("Download mapping.yaml", data=open(map_fn,"rb").read(), file_name="mapping.yaml")
        else:
            st.info("No mapping yet.")

    with tab3:
        st.write("Guidance versions (admin only).")
        df = pd.DataFrame(list_guidance_versions())
        st.dataframe(df, use_container_width=True)
        target = st.text_input("Guidance ID to supersede")
        if st.button("Supersede"):
            ok = supersede_guidance(target)
            if ok:
                st.success("Superseded.")
            else:
                st.error("ID not found.")

# ----------------------- App -----------------------
def main():
    page_header()
    gate()

    pg = st.sidebar.radio("Navigation", ["Audit","Training","Analytics","Admin"], index=0)
    if pg=="Audit":
        page_audit()
    elif pg=="Training":
        page_training()
    elif pg=="Analytics":
        page_analytics()
    else:
        page_admin()

if __name__ == "__main__":
    main()
