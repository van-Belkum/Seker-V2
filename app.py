
# Seker V2 - Design Quality Auditor (AI-enabled)
# ------------------------------------------------
# Streamlit app with: Audit, Training, Analytics, Settings
# - Loads local Guidance folder (docx/pdf/pptx) & Nemesis Excel
# - Optional semantic guidance matching (falls back to TF-IDF if ST not available)
# - Annotates PDFs with sticky notes at exact matched locations
# - Exports Excel + annotated PDF, saves both to history + allows excluding entries
#
# Entry password: Seker123
# Rules edit password: vanB3lkum21

import os, io, re, json, base64, time, datetime as dt
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
import streamlit as st
import yaml

import fitz  # PyMuPDF

# Local utils
from utils.guidance_loader import load_guidance_corpus, load_latest_nemesis, guidance_default_root
from utils.semantic import SemanticIndex
from utils.pdf_tools import extract_pdf_text, find_keyword_boxes, annotate_pdf_with_findings

APP_TITLE = "Seker V2 — AI Design Quality Auditor"
ENTRY_PASSWORD = "Seker123"
RULES_PASSWORD = "vanB3lkum21"

HISTORY_CSV = "history/history.csv"
FILES_DIR = "history/files"
RULES_FILE = "rules/base_rules.yaml"

SUPPLIERS = ["CEG","CTIL","Emfyser","Innov8","Invict","KTL Team (Internal)","Trylon"]
CLIENTS   = ["BTEE","Vodafone","MBNL","H3G","Cornerstone","Cellnex"]
PROJECTS  = ["RAN","Power Resilience","East Unwind","Beacon 4"]
SITE_TYPES = ["Greenfield","Rooftop","Streetworks"]
VENDORS = ["Ericsson","Nokia"]
CAB_LOCS = ["Indoor","Outdoor"]
RADIO_LOCS = ["Low Level","High Level","Unique Coverage","Midway"]
DRAW_TYPES = ["General Arrangement","Detailed Design"]
SECTOR_QTY = [1,2,3,4,5,6]

MIMO_OPTIONS = [
"18 @2x2",
"18 @2x2; 26 @4x4",
"18 @2x2; 70\\80 @2x2",
"18 @2x2; 80 @2x2",
"18\\21 @2x2",
"18\\21 @2x2; 26 @4x4",
"18\\21 @2x2; 3500 @32x32",
"18\\21 @2x2; 70\\80 @2x2",
"18\\21 @2x2; 80 @2x2",
"18\\21 @4x4",
"18\\21 @4x4; 3500 @32x32",
"18\\21 @4x4; 70 @2x4",
"18\\21 @4x4; 70\\80 @2x2",
"18\\21 @4x4; 70\\80 @2x2; 3500 @32x32",
"18\\21 @4x4; 70\\80 @2x4",
"18\\21 @4x4; 70\\80 @2x4; 3500 @32x32",
"18\\21 @4x4; 70\\80 @2x4; 3500 @8x8",
"18\\21@4x4; 70\\80 @2x2",
"18\\21@4x4; 70\\80 @2x4",
"18\\21\\26 @2x2",
"18\\21\\26 @2x2; 3500 @32x32",
"18\\21\\26 @2x2; 3500 @8X8",
"18\\21\\26 @2x2; 70\\80 @2x2",
"18\\21\\26 @2x2; 70\\80 @2x2; 3500 @32x32",
"18\\21\\26 @2x2; 70\\80 @2x2; 3500 @8x8",
"18\\21\\26 @2x2; 70\\80 @2x4; 3500 @32x32",
"18\\21\\26 @2x2; 80 @2x2",
"18\\21\\26 @2x2; 80 @2x2; 3500 @8x8",
"18\\21\\26 @4x4",
"18\\21\\26 @4x4; 3500 @32x32",
"18\\21\\26 @4x4; 3500 @8x8",
"18\\21\\26 @4x4; 70 @2x4; 3500 @8x8",
"18\\21\\26 @4x4; 70\\80 @2x2",
"18\\21\\26 @4x4; 70\\80 @2x2; 3500 @32x32",
"18\\21\\26 @4x4; 70\\80 @2x2; 3500 @8x8",
"18\\21\\26 @4x4; 70\\80 @2x4",
"18\\21\\26 @4x4; 70\\80 @2x4; 3500 @32x32",
"18\\21\\26 @4x4; 70\\80 @2x4; 3500 @8x8",
"18\\21\\26 @4x4; 80 @2x2",
"18\\21\\26 @4x4; 80 @2x2; 3500 @32x32",
"18\\21\\26 @4x4; 80 @2x4",
"18\\21\\26 @4x4; 80 @2x4; 3500 @8x8",
"18\\26 @2x2",
"18\\26 @4x4; 21 @2x2; 80 @2x2",
]
MIMO_OPTIONS += ["(blank)"]

def ensure_history():
    os.makedirs(os.path.dirname(HISTORY_CSV), exist_ok=True)
    if not os.path.exists(HISTORY_CSV):
        cols = ["timestamp_utc","supplier","client","project","site_type","vendor",
                "cabinet_location","radio_location","drawing_type","sectors",
                "mimo_s1","mimo_s2","mimo_s3","mimo_s4","mimo_s5","mimo_s6",
                "site_address","status","pdf_name","excel_name",
                "exclude","notes"]
        pd.DataFrame(columns=cols).to_csv(HISTORY_CSV, index=False)

def load_history() -> pd.DataFrame:
    ensure_history()
    try:
        return pd.read_csv(HISTORY_CSV)
    except Exception:
        return pd.read_csv(HISTORY_CSV, on_bad_lines="skip")

def save_history_row(row: Dict[str, Any]):
    df = load_history()
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(HISTORY_CSV, index=False)

def load_rules(path=RULES_FILE) -> Dict[str, Any]:
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(DEFAULT_RULES_YAML)
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data

def save_rules(data: Dict[str,Any], path=RULES_FILE):
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)

DEFAULT_RULES_YAML = """
checklist:
  - name: Title block present
    severity: major
    must_contain: ["TITLE"]
    reject_if_present: []
  - name: Scale shown
    severity: minor
    must_contain: ["SCALE"]
    reject_if_present: []
policies:
  - name: Power Resilience — Eltek PSU note
    trigger:
      project: ["Power Resilience"]
    search_any: ["ELTEK PSU","IMPORTANT NOTE"]
    guidance_hint: "See TDEE43001 section 3.8.1"
"""

def password_gate() -> bool:
    if "gated" not in st.session_state:
        st.session_state.gated = False
    if st.session_state.gated:
        return True
    with st.form("entry"):
        pw = st.text_input("Enter access password", type="password")
        ok = st.form_submit_button("Enter")
        if ok:
            if pw == ENTRY_PASSWORD:
                st.session_state.gated = True
                st.experimental_set_query_params(ready="1")
                st.rerun()
            else:
                st.error("Wrong password")
    return False

def meta_block():
    st.subheader("Audit Metadata")
    c1,c2,c3,c4 = st.columns(4)
    supplier = c1.selectbox("Supplier", SUPPLIERS, index=0, key="supplier")
    drawtype = c2.selectbox("Drawing Type", DRAW_TYPES, index=0, key="drawtype")
    client   = c3.selectbox("Client", CLIENTS, index=0, key="client")
    project  = c4.selectbox("Project", PROJECTS, index=0, key="project")

    c5,c6,c7,c8 = st.columns(4)
    site_type = c5.selectbox("Site Type", SITE_TYPES, key="site_type")
    vendor    = c6.selectbox("Proposed Vendor", VENDORS, key="vendor")
    cab_loc   = c7.selectbox("Proposed Cabinet Location", CAB_LOCS, key="cab_loc")
    radio_loc = c8.selectbox("Proposed Radio Location", RADIO_LOCS, key="radio_loc")

    c9,c10 = st.columns(2)
    sectors = c9.selectbox("Quantity of Sectors", SECTOR_QTY, key="sectors")
    site_address = c10.text_input("Site Address", key="site_address", placeholder="MANBY ROAD , 0 , IMMINGHAM , IMMINGHAM , DN40 2LQ")

    st.markdown("**Proposed MIMO Config**")
    use_all = st.checkbox("Use S1 for all sectors", value=True, key="mimo_all")
    def mimo(label, key):
        return st.selectbox(label, MIMO_OPTIONS, index=0, key=key)
    mimo_s1 = mimo("MIMO S1", "mimo_s1")
    mimos = [mimo_s1]
    for i in range(2, sectors+1):
        if use_all:
            st.text_input(f"MIMO S{i}", value=mimo_s1, key=f"mimo_s{i}", disabled=True)
            mimos.append(mimo_s1)
        else:
            mimos.append(mimo(f"MIMO S{i}", f"mimo_s{i}"))
    # fill missing up to 6
    while len(mimos) < 6:
        mimos.append("(blank)")
        st.text_input(f"MIMO S{len(mimos)}", value="(blank)", key=f"mimo_s{len(mimos)}", disabled=True)

    meta = dict(supplier=supplier, drawing_type=drawtype, client=client, project=project,
                site_type=site_type, vendor=vendor, cabinet_location=cab_loc, radio_location=radio_loc,
                sectors=sectors, site_address=site_address,
                mimo_s1=mimos[0], mimo_s2=mimos[1], mimo_s3=mimos[2],
                mimo_s4=mimos[3], mimo_s5=mimos[4], mimo_s6=mimos[5])
    return meta

def simple_title_matches_address(pdf_text: str, address: str) -> Tuple[bool,str]:
    if not address:
        return True, ""
    addr_clean = re.sub(r"\\s*,\\s*0\\s*,\\s*"," , ", address, flags=re.I)
    head = pdf_text[:1500]
    ok = addr_clean.split(",")[0].strip().lower() in head.lower()
    if ok:
        return True, ""
    else:
        return False, f"Title/address mismatch: expected '{addr_clean.split(',')[0].strip()}' in title area"

def run_checklist(checklist: List[Dict[str,Any]], pdf_text: str) -> List[Dict[str,Any]]:
    findings = []
    for rule in checklist:
        name = rule.get("name","Unnamed rule")
        must = rule.get("must_contain",[]) or []
        rej   = rule.get("reject_if_present",[]) or []
        severity = rule.get("severity","minor")
        ok_all = all(x.lower() in pdf_text.lower() for x in must) if must else True
        rej_any = any(x.lower() in pdf_text.lower() for x in rej) if rej else False
        if not ok_all or rej_any:
            findings.append(dict(rule=name, severity=severity,
                                 message=f"Rule failed. must_contain={must}, reject_if_present={rej}",
                                 keyword=(must[0] if must else rej[0] if rej else None)))
    return findings

def run_policies(policies: List[Dict[str,Any]], meta: Dict[str,Any], pdf_text: str, sem: Optional[SemanticIndex]) -> List[Dict[str,Any]]:
    out=[]
    for pol in policies:
        trig = pol.get("trigger",{})
        hit=True
        for k,v in trig.items():
            val = meta.get(k)
            if isinstance(v,list):
                if val not in v: hit=False; break
            else:
                if val!=v: hit=False; break
        if not hit: 
            continue
        # If there are explicit search words, ensure at least one is in text; otherwise we rely purely on semantics.
        search_any = pol.get("search_any",[])
        guidance_hint = pol.get("guidance_hint","")
        matched = any(s.lower() in pdf_text.lower() for s in search_any) if search_any else False
        evidence=""
        if sem is not None:
            # semantic search using the policy name + search terms
            q = pol.get("name","") + " " + " ".join(search_any)
            top = sem.query(q, k=1)
            if top:
                evidence = f"Guidance: {top[0]['source']} — '{top[0]['snippet']}'"
                # weak threshold: if cosine > 0.3 treat as evidence requirement present
                matched = matched or (top[0].get('score',0) >= 0.30)
        if not matched:
            out.append(dict(rule=pol.get("name","policy"), severity="major",
                            message=f"Policy not evidenced in design. {guidance_hint}. {evidence}".strip(),
                            keyword=(search_any[0] if search_any else None)))
    return out

def make_excel(findings: List[Dict[str,Any]], meta: Dict[str,Any], orig_pdf_name: str, status: str) -> bytes:
    df = pd.DataFrame(findings) if findings else pd.DataFrame(columns=["rule","severity","message","keyword"])
    mem = io.BytesIO()
    with pd.ExcelWriter(mem, engine="xlsxwriter") as xw:
        meta_df = pd.DataFrame([meta])
        meta_df.to_excel(xw, sheet_name="Meta", index=False)
        df.to_excel(xw, sheet_name="Findings", index=False)
        summ = pd.DataFrame([{"status":status, "total_findings": len(df)}])
        summ.to_excel(xw, sheet_name="Summary", index=False)
    mem.seek(0)
    return mem.read()

def audit_tab(sem: Optional[SemanticIndex]):
    st.header("Audit")
    meta = meta_block()
    up = st.file_uploader("Upload PDF Design", type=["pdf"], accept_multiple_files=False)
    do_spell = st.checkbox("Enable spelling scan", value=False, help="Can be slow")
    if st.button("Run audit", disabled=(up is None)):
        if up is None:
            st.warning("Please upload a PDF")
            return
        raw = up.read()
        with st.spinner("Extracting text..."):
            text = extract_pdf_text(raw)
        # Basic checks
        rules = load_rules()
        findings = []
        ok_addr, msg = simple_title_matches_address(text, meta.get("site_address",""))
        if not ok_addr:
            findings.append(dict(rule="Title vs Address", severity="major", message=msg, keyword=meta.get("site_address","").split(",")[0]))
        findings += run_checklist(rules.get("checklist",[]), text)
        findings += run_policies(rules.get("policies",[]), meta, text, sem)
        if do_spell:
            try:
                from spellchecker import SpellChecker
                sp = SpellChecker()
                words = set(re.findall(r"[A-Za-z]{4,}", text))
                bad = sp.unknown(words)
                allow = set(["BTEE","ELTEK","AYGE","AYGD","GPS","RAN","BoB","BoBs","SAMI","Flexi"])
                for w in list(bad)[:200]:
                    if w.upper() in allow: continue
                    sug = None
                    try:
                        cand = sp.candidates(w)
                        sug = next(iter(cand)) if cand else None
                    except Exception:
                        sug = None
                    findings.append(dict(rule="Spelling", severity="minor",
                                        message=f"Possible misspelling '{w}'" + (f" → '{sug}'" if sug else ""),
                                        keyword=w))
            except Exception as e:
                st.info(f"Spelling not available: {e}")

        status = "Rejected" if any(f.get("severity","minor")=="major" for f in findings) else "Pass"
        st.subheader(f"Result: {status}")
        st.dataframe(pd.DataFrame(findings), use_container_width=True)

        # Annotate PDF
        with st.spinner("Annotating PDF..."):
            pdf_annot = annotate_pdf_with_findings(raw, findings)

        # Save files
        ts = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        safe = os.path.splitext(os.path.basename(up.name))[0]
        pdf_name = f"{safe}_{status}_{ts}.pdf"
        xlsx_bytes = make_excel(findings, meta, up.name, status)
        excel_name = f"{safe}_{status}_{ts}.xlsx"
        os.makedirs(FILES_DIR, exist_ok=True)
        pdf_path = os.path.join(FILES_DIR, pdf_name)
        xlsx_path = os.path.join(FILES_DIR, excel_name)
        with open(pdf_path, "wb") as f: f.write(pdf_annot)
        with open(xlsx_path, "wb") as f: f.write(xlsx_bytes)

        save_history_row({
            "timestamp_utc": ts,
            "supplier": meta["supplier"],
            "client": meta["client"],
            "project": meta["project"],
            "site_type": meta["site_type"],
            "vendor": meta["vendor"],
            "cabinet_location": meta["cabinet_location"],
            "radio_location": meta["radio_location"],
            "drawing_type": meta["drawing_type"],
            "sectors": meta["sectors"],
            "mimo_s1": meta["mimo_s1"],"mimo_s2": meta["mimo_s2"],"mimo_s3": meta["mimo_s3"],
            "mimo_s4": meta["mimo_s4"],"mimo_s5": meta["mimo_s5"],"mimo_s6": meta["mimo_s6"],
            "site_address": meta["site_address"],
            "status": status,
            "pdf_name": pdf_name,
            "excel_name": excel_name,
            "exclude": False,
            "notes": ""
        })

        c1,c2 = st.columns(2)
        with c1:
            st.download_button("⬇️ Download annotated PDF", data=pdf_annot, file_name=pdf_name, mime="application/pdf")
        with c2:
            st.download_button("⬇️ Download Excel report", data=xlsx_bytes, file_name=excel_name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.success("Saved to local history. You can find the files in history/files/.")

def training_tab():
    st.header("Training")
    st.caption("Upload audited Excel/JSON to record Valid/Not-Valid and quickly add rules.")
    tfile = st.file_uploader("Upload Excel/JSON training record", type=["xlsx","xls","json"])
    decision = st.selectbox("This audit decision is…", ["Valid","Not-Valid"])
    if st.button("Ingest training record", disabled=(tfile is None)):
        # we simply store the file into history/files and record meta tag in CSV
        ts = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        os.makedirs(FILES_DIR, exist_ok=True)
        outname = f"TRAIN_{decision}_{ts}_{tfile.name}"
        with open(os.path.join(FILES_DIR, outname), "wb") as f: f.write(tfile.read())
        st.success("Stored training artefact. Use Settings → Edit rules to update policies as needed.")

    st.divider()
    st.subheader("Add a quick rule (appends to YAML instantly)")
    name = st.text_input("Rule name", placeholder="e.g., Power Resilience note present")
    severity = st.selectbox("Severity", ["major","minor"], index=0)
    must = st.text_input("Must contain (comma-separated)", placeholder="IMPORTANT NOTE, ELTEK PSU")
    rej = st.text_input("Reject if present (comma-separated)", placeholder="")
    pw = st.text_input("Rules password", type="password", placeholder="vanB3lkum21")
    if st.button("Append rule"):
        if pw != RULES_PASSWORD:
            st.error("Wrong password")
        else:
            data = load_rules()
            data.setdefault("checklist", []).append({
                "name": name or "Quick rule",
                "severity": severity,
                "must_contain": [x.strip() for x in must.split(",") if x.strip()],
                "reject_if_present": [x.strip() for x in rej.split(",") if x.strip()],
            })
            save_rules(data)
            st.success("Rule appended.")

def analytics_tab():
    st.header("Analytics")
    df = load_history()
    if df.empty:
        st.info("No history yet.")
        return
    c1,c2,c3 = st.columns(3)
    sel_client = c1.multiselect("Client", sorted(df["client"].dropna().unique().tolist()), default=None)
    sel_project = c2.multiselect("Project", sorted(df["project"].dropna().unique().tolist()), default=None)
    sel_supplier = c3.multiselect("Supplier", sorted(df["supplier"].dropna().unique().tolist()), default=None)

    show = df.copy()
    if sel_client: show = show[show["client"].isin(sel_client)]
    if sel_project: show = show[show["project"].isin(sel_project)]
    if sel_supplier: show = show[show["supplier"].isin(sel_supplier)]
    # Exclude flagged
    if "exclude" in show.columns:
        show = show[~show["exclude"].astype(bool)]
    st.dataframe(show[["timestamp_utc","supplier","client","project","status","pdf_name","excel_name"]], use_container_width=True)

    # Quick KPIs
    total = len(show)
    pass_rate = (show["status"].eq("Pass").mean()*100.0) if total else 0.0
    major_cnt = (show["status"].eq("Rejected").sum())
    c1,c2,c3 = st.columns(3)
    c1.metric("Audits", total)
    c2.metric("Right First Time %", f"{pass_rate:.1f}%")
    c3.metric("Rejections", int(major_cnt))

    # Mark exclude
    st.subheader("Exclude entries")
    idx_to_exclude = st.multiselect("Select timestamps to exclude/include", show["timestamp_utc"].tolist())
    if st.button("Toggle exclude on selected"):
        df2 = load_history()
        df2["exclude"] = df2.apply(lambda r: (not r.get("exclude", False)) if r["timestamp_utc"] in idx_to_exclude else r.get("exclude", False), axis=1)
        df2.to_csv(HISTORY_CSV, index=False)
        st.success("Toggled exclude flag.")
        st.rerun()

def settings_tab(sem: Optional[SemanticIndex]):
    st.header("Settings & Guidance")
    st.caption("Set Guidance root; the app scans subfolders like BTEE/ and Nemesis/ automatically.")
    default_root = guidance_default_root()
    root = st.text_input("Guidance root path", value=os.environ.get("GUIDANCE_ROOT", default_root))
    if st.button("Reload guidance"):
        os.environ["GUIDANCE_ROOT"] = root
        st.cache_data.clear()
        st.cache_resource.clear()
        st.success("Cleared caches — guidance will reload on next run.")
    st.divider()
    st.subheader("Edit rules (YAML)")
    p = st.text_input("Rules password", type="password")
    data = load_rules()
    txt = st.text_area(os.path.basename(RULES_FILE), value=yaml.safe_dump(data, sort_keys=False, allow_unicode=True), height=280)
    c1,c2 = st.columns(2)
    if c1.button("Save rules"):
        if p != RULES_PASSWORD:
            st.error("Wrong password")
        else:
            try:
                newdata = yaml.safe_load(txt) or {}
                save_rules(newdata)
                st.success("Rules saved.")
            except Exception as e:
                st.error(f"YAML error: {e}")
    if c2.button("Reload from disk"):
        st.rerun()

def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.markdown("<style>.block-container{padding-top:1.2rem;}</style>", unsafe_allow_html=True)
    st.title(APP_TITLE)

    if not password_gate():
        return

    # Build semantic index (cached) from local guidance
    @st.cache_resource(show_spinner=True)
    def build_semantic_index() -> Optional[SemanticIndex]:
        try:
            corpus = load_guidance_corpus()
            if not corpus:
                return None
            sem = SemanticIndex()
            sem.build(corpus)
            return sem
        except Exception as e:
            st.info(f"Semantic index disabled: {e}")
            return None

    sem = build_semantic_index()

    tab1, tab2, tab3, tab4 = st.tabs(["Audit","Training","Analytics","Settings"])
    with tab1:
        audit_tab(sem)
    with tab2:
        training_tab()
    with tab3:
        analytics_tab()
    with tab4:
        settings_tab(sem)

if __name__ == "__main__":
    main()
