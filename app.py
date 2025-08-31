
import io
import os
import base64
import datetime as dt
from typing import List, Dict, Any

import streamlit as st
import pandas as pd

from utils.guidance_loader import (
    set_guidance_root,
    load_guidance_index,
    get_index_status,
    search_guidance,
)
from utils.pdf_tools import (
    extract_text_from_pdf,
    annotate_pdf_with_findings,
)
from utils.semantic import simple_highlight, fuzzy_terms

APP_TITLE = "Seker V2 — AI Design Quality Auditor"
HISTORY_DIR = "history"  # created on first write
RULES_DIR = "rules"
DEFAULT_RULE_FILE = os.path.join(RULES_DIR, "base_rules.yaml")

REQUIRED_PACKAGES = [
    "streamlit","pandas","rapidfuzz","python-docx","python-pptx","PyMuPDF","pyspellchecker","openpyxl","xlsxwriter"
]

def _ensure_dirs():
    os.makedirs(HISTORY_DIR, exist_ok=True)
    os.makedirs(RULES_DIR, exist_ok=True)

def _badge(msg, color="#0ea5e9"):
    st.markdown(f'<div style="display:inline-block;padding:2px 8px;border-radius:6px;background:{color};color:white;font-size:12px;">{msg}</div>', unsafe_allow_html=True)

def gate_guidance_mandatory() -> bool:
    """Block Audit/Training/Analytics until guidance is loaded once in this session."""
    status = get_index_status()
    if not status["loaded"]:
        st.warning("Guidance index is not loaded. Go to **Settings** → set your local Guidance root and click **Reload guidance**.")
        with st.expander("Index status"):
            st.json(status)
        return False
    return True

def load_rules_text() -> str:
    try:
        with open(DEFAULT_RULE_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "policies: []\n"

def save_rules_text(txt: str):
    with open(DEFAULT_RULE_FILE, "w", encoding="utf-8") as f:
        f.write(txt)

def run_spelling_checks(pages: List[str], allow: List[str]) -> List[Dict[str,Any]]:
    findings = []
    try:
        from spellchecker import SpellChecker
        sp = SpellChecker(distance=1)
        sp.word_frequency.load_words(allow)
        for i, page in enumerate(pages, start=1):
            words = [w.strip(".,:;()[]{}").lower() for w in page.split()]
            for w in words:
                if not w or w.isnumeric() or len(w) < 3: 
                    continue
                if w in allow: 
                    continue
                # use candidates() defensively
                try:
                    candidates = sp.candidates(w)
                except Exception:
                    candidates = set()
                sug = next(iter(candidates), None)
                if w not in sp:  # likely misspelt
                    findings.append({
                        "type":"spelling",
                        "page": i,
                        "text": w,
                        "suggestion": sug,
                        "severity": "minor",
                        "rule": "Spelling check",
                    })
    except Exception as e:
        st.info(f"Spelling disabled: {e}")
    return findings

def apply_rules(pages: List[str], meta: Dict[str,str]) -> List[Dict[str,Any]]:
    """Very light rule runner: search each policy's search_any terms across PDF text & guidance snippets."""
    import yaml
    all_txt = "\n\n".join(pages)
    rules_yaml = load_rules_text()
    try:
        cfg = yaml.safe_load(rules_yaml) or {}
    except yaml.YAMLError as e:
        st.error(f"YAML error in rules: {e}")
        return []
    findings = []
    for pol in (cfg.get("policies") or []):
        trig = pol.get("trigger", {})
        # Check trigger (project/client/vendor etc.) must match when provided
        triggered = True
        for k,v in trig.items():
            if not v: 
                continue
            if str(meta.get(k,"")).strip().lower() != str(v).strip().lower():
                triggered = False
                break
        if not triggered:
            continue
        terms = pol.get("search_any") or []
        if not terms:
            continue
        hit_pdf = any(t.lower() in all_txt.lower() for t in terms)
        hit_guidance = False
        snippets = []
        # search guidance index for each term
        for t in terms:
            res = search_guidance(t, top_k=3)
            if res:
                hit_guidance = True
                snippets.extend(r.get("snippet","") for r in res)
        if hit_pdf and hit_guidance:
            # Rule is satisfied (found). Many checks are actually "must be present"; if you want reject_if_missing flip logic.
            pass
        else:
            findings.append({
                "type":"rule",
                "page": None,
                "text": ", ".join(terms),
                "suggestion": pol.get("guidance_hint","See guidance"),
                "severity": pol.get("severity","major"),
                "rule": pol.get("name","Unnamed"),
            })
    return findings

def audit_tab():
    st.header("Audit")
    st.caption("Upload a PDF and run quality checks against rules and guidance.")
    if not gate_guidance_mandatory():
        return

    with st.form("audit_form"):
        up = st.file_uploader("Upload PDF design", type=["pdf"])
        col1, col2, col3 = st.columns(3)
        with col1:
            client = st.selectbox("Client", ["BTEE","Vodafone","MBNL","H3G","Cornerstone","Cellnex"])
        with col2:
            project = st.selectbox("Project", ["RAN","Power Resilience","East Unwind","Beacon 4"])
        with col3:
            vendor = st.selectbox("Vendor", ["Ericsson","Nokia"])
        site_addr = st.text_input("Site address")
        do_spell = st.checkbox("Enable spelling checks", True)
        allow_words = st.text_area("Allowed words (one per line)", "Ay,AYGD,AYGE,AHEGG\n", height=80)
        submit = st.form_submit_button("Run audit")

    if not submit or not up:
        return

    meta = {
        "client": client,
        "project": project,
        "vendor": vendor,
        "site_address": site_addr,
    }

    raw = up.read()
    st.info("Extracting PDF text…")
    pages = extract_text_from_pdf(raw)
    st.success(f"Extracted {len(pages)} pages.")

    findings: List[Dict[str,Any]] = []
    if do_spell:
        findings.extend(run_spelling_checks(pages, [w.strip() for w in allow_words.splitlines() if w.strip()]))
    findings.extend(apply_rules(pages, meta))

    status = "Pass" if not findings else "Rejected"
    _badge(status, "#16a34a" if status=="Pass" else "#ef4444")
    st.write(f"**Findings:** {len(findings)}")

    if findings:
        df = pd.DataFrame(findings)
        st.dataframe(df, use_container_width=True)
    else:
        st.success("No findings.")

    st.info("Annotating PDF…")
    annotated = annotate_pdf_with_findings(raw, findings)
    st.download_button("Download annotated PDF", data=annotated, file_name=f"{os.path.splitext(up.name)[0]}_{status}_{dt.datetime.utcnow().isoformat(timespec='seconds')}.pdf", mime="application/pdf")

    # Excel export
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as xw:
        (pd.DataFrame(findings) if findings else pd.DataFrame([{"status":"Pass"}])).to_excel(xw, index=False, sheet_name="Findings")
        pd.DataFrame([meta]).to_excel(xw, index=False, sheet_name="Meta")
    st.download_button("Download report (Excel)", data=out.getvalue(), file_name=f"{os.path.splitext(up.name)[0]}_{status}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

def training_tab():
    st.header("Training")
    if not gate_guidance_mandatory():
        return
    st.caption("Upload a prior audit Excel (the 'Findings' sheet) to mark decisions Valid / Not-Valid and we’ll record them for analytics.")
    up = st.file_uploader("Upload audit Excel", type=["xlsx","xlsm"])
    decision = st.selectbox("Decision", ["Valid","Not-Valid"])
    if st.button("Record training decision"):
        if not up:
            st.error("Upload an Excel first.")
            return
        df = pd.read_excel(up, sheet_name="Findings")
        when = dt.datetime.utcnow().isoformat()
        out = os.path.join(HISTORY_DIR, f"training_{when}.csv")
        df.assign(decision=decision, timestamp_utc=when).to_csv(out, index=False)
        st.success(f"Saved {out}")

def analytics_tab():
    st.header("Analytics")
    files = [f for f in os.listdir(HISTORY_DIR)] if os.path.isdir(HISTORY_DIR) else []
    if not files:
        st.info("No history yet.")
        return
    rows = []
    for fn in files:
        if fn.endswith(".csv"):
            try:
                rows.append(pd.read_csv(os.path.join(HISTORY_DIR, fn)))
            except Exception:
                pass
    if not rows:
        st.info("No readable history yet.")
        return
    df = pd.concat(rows, ignore_index=True)
    st.metric("Records", len(df))
    st.dataframe(df.tail(200), use_container_width=True)

def settings_tab():
    st.header("Settings & Guidance")
    st.caption("Set Guidance root; the app will index subfolders like BTEE/ and Nemesis/. Audits are blocked until guidance is loaded.")
    root = st.text_input("Guidance root path", value=set_guidance_root() or "")
    if st.button("Reload guidance"):
        if not root:
            st.error("Enter a path first.")
        else:
            set_guidance_root(root)
            status = load_guidance_index(root)
            if status["loaded"]:
                st.success(f"Loaded {status['files_indexed']} files. Terms in index: {status['terms_indexed']}")
            else:
                st.error("Failed to load guidance. See logs below.")
    with st.expander("Current index status"):
        st.json(get_index_status())

    # Rules editor
    st.subheader("Edit rules (YAML)")
    pw = st.text_input("Rules password", type="password", help="Enter your secret to save rules")
    txt = st.text_area(os.path.basename(DEFAULT_RULE_FILE), value=load_rules_text(), height=320)
    cols = st.columns(2)
    with cols[0]:
        if st.button("Save rules"):
            if pw.strip() != "vanB3lkum21":
                st.error("Wrong password")
            else:
                save_rules_text(txt)
                st.success("Saved.")
    with cols[1]:
        if st.button("Reload from disk"):
            st.experimental_rerun()

def main():
    _ensure_dirs()
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)
    tabs = st.tabs(["Audit","Training","Analytics","Settings"])
    with tabs[0]: audit_tab()
    with tabs[1]: training_tab()
    with tabs[2]: analytics_tab()
    with tabs[3]: settings_tab()

if __name__ == "__main__":
    main()
