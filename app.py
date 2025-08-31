\
import os, io, base64, textwrap, yaml, datetime as dt
from typing import List, Dict, Any
import streamlit as st
import pandas as pd

from utils.guidance_loader import build_index_from_folder, search_terms
from utils.rules_engine import run_core_checks
from utils.pdf_utils import annotate_pdf
from utils import storage

# ---------- CONFIG LOADER ----------
SAFE_DEFAULTS = {
    "security":{"entry_password_enabled":True,"entry_password":"Seker123","rules_password":"vanB3lkum21"},
    "guidance":{"root":"C:/Mac/Home/Music/Guidance",
                "nemesis":{"folder":"C:/Mac/Home/Music/Guidance/Nemesis","patterns":["AntennaHeights*.csv","MHA_Models*.csv","Bearings*.csv"]}},
    "ui":{"logo":"logo.png","theme":"light"},
    "metadata":{
        "clients":["BTEE","Vodafone","MBNL","H3G","Cornerstone","Cellnex"],
        "projects":["RAN","Power Resilience","East Unwind","Beacon 4"],
        "site_types":["Greenfield","Rooftop","Streetworks"],
        "vendors":["Ericsson","Nokia"],
        "suppliers":[],
        "radio_locations":["Low Level","High Level","Unique Coverage","Midway"],
        "cabinet_locations":["Indoor","Outdoor"],
        "sectors":[1,2,3,4,5,6],
        "mimo_configs":["18 @2x2","(blank)"],
    },
    "features":{"spelling":True,"pdf_annotation":True,"analytics":True,"require_guidance_loaded":True},
}

def load_config(path="config.yaml"):
    try:
        with open(path,"r",encoding="utf-8") as f:
            return yaml.safe_load(f) or SAFE_DEFAULTS
    except Exception:
        return SAFE_DEFAULTS

CFG = load_config()

# ---------- PAGE CONFIG & LOGO ----------
st.set_page_config(page_title="Seker V2 — AI Auditor", layout="wide")
logo_path = CFG.get("ui",{}).get("logo")
if logo_path and os.path.exists(logo_path):
    with open(logo_path,"rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    st.markdown(f"""
    <style>.top-left-logo{{position:fixed; left:12px; top:10px; width:140px; z-index:1000;}}</style>
    <img class="top-left-logo" src="data:image/png;base64,{b64}" />
    """, unsafe_allow_html=True)

# ---------- PASSWORD GATE ----------
def gate()->bool:
    sec = CFG.get("security",{})
    if not sec.get("entry_password_enabled", True):
        return True
    if "auth_ok" not in st.session_state:
        st.session_state.auth_ok = False
    if st.session_state.auth_ok:
        return True
    pw = st.text_input("Enter access password", type="password")
    if st.button("Unlock"):
        if pw == sec.get("entry_password","Seker123"):
            st.session_state.auth_ok = True
            return True
        else:
            st.error("Wrong password.")
    st.stop()

# ---------- UTIL ----------
def read_pdf_bytes(uploaded)->bytes:
    return uploaded.getvalue()

def pdf_text_pages(pdf_bytes:bytes)->List[str]:
    import fitz
    out = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for p in doc:
            out.append(p.get_text("text"))
    return out

def make_excel(findings:List[Dict[str,Any]], meta:Dict[str,Any], original_name:str, status:str)->bytes:
    df = pd.DataFrame(findings) if findings else pd.DataFrame(columns=["rule_id","severity","message","page"])
    mem = io.BytesIO()
    with pd.ExcelWriter(mem, engine="openpyxl") as xw:
        df.to_excel(xw, index=False, sheet_name="Findings")
        pd.DataFrame([meta]).to_excel(xw, index=False, sheet_name="Metadata")
    mem.seek(0)
    return mem.read()

# ---------- STATE ----------
if "guidance" not in st.session_state:
    st.session_state.guidance = {"loaded": False, "index": {}}

# ---------- TABS ----------
def tab_audit():
    st.header("Audit")
    if CFG.get("features",{}).get("require_guidance_loaded", True) and not st.session_state.guidance["loaded"]:
        st.warning("Load guidance in the **Guidance** tab before running audits.")
        return

    meta = {}

    c1,c2,c3 = st.columns(3)
    with c1:
        meta["client"] = st.selectbox("Client", CFG["metadata"]["clients"])
        meta["project"] = st.selectbox("Project", CFG["metadata"]["projects"])
        meta["site_type"] = st.selectbox("Site Type", CFG["metadata"]["site_types"])
    with c2:
        meta["vendor"] = st.selectbox("Proposed Vendor", CFG["metadata"]["vendors"])
        # Suppliers are editable in Settings – if empty, show a textbox to avoid blocking you
        suppliers = CFG["metadata"].get("suppliers") or []
        if suppliers:
            meta["supplier"] = st.selectbox("Supplier", suppliers)
        else:
            meta["supplier"] = st.text_input("Supplier (enter; configure proper list in Settings)", "")
        meta["cabinet_location"] = st.selectbox("Proposed Cabinet Location", CFG["metadata"]["cabinet_locations"])
    with c3:
        meta["radio_location"] = st.selectbox("Proposed Radio Location", CFG["metadata"]["radio_locations"])
        meta["sectors"] = st.selectbox("Quantity of Sectors", CFG["metadata"]["sectors"])
        meta["site_address"] = st.text_input("Site Address")

    # MIMO per sector
    mimo_opts = CFG["metadata"]["mimo_configs"]
    st.markdown("**Proposed MIMO Config (S1…S6)**  \n*(Optional for Power Resilience; otherwise S1 required)*")
    cols = st.columns(6)
    for i in range(6):
        key = f"mimo_s{i+1}"
        if i < meta["sectors"]:
            meta[key] = cols[i].selectbox(f"S{i+1}", mimo_opts, index=0)
        else:
            meta[key] = ""

    st.divider()
    up = st.file_uploader("Upload PDF design", type=["pdf"])

    do_spell = st.toggle("Enable spelling check", value=CFG.get("features",{}).get("spelling", True))

    run = st.button("Run Audit", type="primary", use_container_width=True)

    if run and up is not None:
        raw = read_pdf_bytes(up)
        pages = pdf_text_pages(raw)

        # Core checks
        findings = run_core_checks(pages, meta)

        # Spelling (simple)
        if do_spell:
            try:
                from spellchecker import SpellChecker
                sp = SpellChecker(distance=1)
                words = set()
                for t in pages:
                    words.update([w for w in t.replace("\n"," ").split() if w.isalpha() and len(w)>3])
                unknown = sp.unknown(words)
                # allow common telecom tokens
                allow = {"LTE","GSM","UMTS","AYGE","AYGD","AHEGG","TRX","BTS"}
                bad = [w for w in unknown if w.upper() not in allow]
                for w in sorted(list(bad))[:50]:
                    sug = next(iter(sp.candidates(w)), None)
                    findings.append(dict(rule_id="SPELL", severity="MINOR",
                                         message=f"Possible spelling: '{w}' -> '{sug}'" if sug else f"Possible spelling: '{w}'",
                                         page=1))
            except Exception as e:
                st.info(f"Spelling disabled ({e}). Install pyspellchecker.")

        # Guidance keyword ping (very light ‘is it relevant’ signal)
        index = st.session_state.guidance["index"]
        terms = [meta["client"], meta["project"], meta["site_type"], meta["vendor"]]
        hits = search_terms(index, [t for t in terms if t])
        for fp, snip in hits[:10]:
            findings.append(dict(rule_id="GUIDANCE_HIT", severity="INFO",
                                 message=f"Guidance match in {os.path.basename(fp)}: …{snip}…", page=1))

        status = "Pass" if not any(f.get("severity") in ("MAJOR","REJECT") for f in findings) else "Rejected"

        # Exclude toggle for analytics
        exclude = st.checkbox("Exclude this review from analytics")

        # Exports
        now = dt.datetime.utcnow().strftime("%Y-%m-%dT%H_%M_%S")
        base_name = os.path.splitext(up.name)[0]
        excel_name = f"{base_name}_{status}_{now}.xlsx"
        pdf_name = f"{base_name}_{status}_{now}.pdf"

        # Excel
        excel_bytes = make_excel(findings, meta, up.name, status)
        st.download_button("Download Excel report", data=excel_bytes, file_name=excel_name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # Annotated PDF (notes near page headers; exact coordinates require OCR/layout)
        pdf_bytes = annotate_pdf(raw, findings) if CFG["features"].get("pdf_annotation", True) else raw
        st.download_button("Download annotated PDF", data=pdf_bytes, file_name=pdf_name, mime="application/pdf")

        # Persist minimal history
        storage.append_history(dict(
            status=status, client=meta["client"], project=meta["project"], site_type=meta["site_type"],
            vendor=meta["vendor"], supplier=meta["supplier"], cabinet_location=meta["cabinet_location"],
            radio_location=meta["radio_location"], sectors=meta["sectors"], site_address=meta["site_address"],
            pdf_name=pdf_name, excel_name=excel_name, excluded=exclude, notes=""
        ))

        # Show findings table
        st.subheader(f"Findings ({len(findings)})")
        st.dataframe(pd.DataFrame(findings), use_container_width=True)

def tab_guidance():
    st.header("Guidance")
    root = CFG.get("guidance",{}).get("root","")
    st.write(f"Configured guidance root: `{root}`")

    if st.button("Scan guidance now", type="primary"):
        if not os.path.exists(root):
            st.error("Guidance root path does not exist. Update it in Settings.")
        else:
            idx = build_index_from_folder(root)
            st.session_state.guidance = {"loaded": True, "index": idx}
            st.success(f"Loaded {len(idx)} guidance documents.")

    if st.session_state.guidance["loaded"]:
        st.success(f"Guidance is loaded ({len(st.session_state.guidance['index'])} docs).")

def tab_analytics():
    st.header("Analytics")
    dfh = storage.load_history()
    if dfh.empty:
        st.info("No history yet.")
        return
    # Filters
    c1,c2,c3 = st.columns(3)
    with c1:
        f_client = st.multiselect("Client", sorted(dfh["client"].dropna().unique().tolist()))
    with c2:
        f_project = st.multiselect("Project", sorted(dfh["project"].dropna().unique().tolist()))
    with c3:
        f_supplier = st.multiselect("Supplier", sorted(dfh["supplier"].dropna().unique().tolist()))
    show = dfh.copy()
    if f_client: show = show[show["client"].isin(f_client)]
    if f_project: show = show[show["project"].isin(f_project)]
    if f_supplier: show = show[show["supplier"].isin(f_supplier)]
    show = show[~show["excluded"].fillna(False)]

    st.dataframe(show[["timestamp_utc","supplier","client","project","status","pdf_name","excel_name"]], use_container_width=True)

    # simple KPI
    total = len(show)
    rft = (show["status"]=="Pass").mean()*100 if total else 0
    st.metric("Right First Time %", f"{rft:0.1f}%")
    st.metric("Audits", total)

def tab_settings():
    st.header("Settings")
    st.caption("Passwords, dropdowns, and paths are persisted to config.yaml")
    # Paths
    guidance_root = st.text_input("Guidance Root Path", CFG["guidance"]["root"])
    nem_folder = st.text_input("Nemesis Folder", CFG["guidance"]["nemesis"]["folder"])

    # Suppliers editor (multi-line, one per line)
    suppliers_text = "\n".join(CFG["metadata"].get("suppliers") or [])
    suppliers_text = st.text_area("Suppliers (one per line)", suppliers_text, height=200)

    if st.button("Save settings"):
        CFG["guidance"]["root"] = guidance_root
        CFG["guidance"]["nemesis"]["folder"] = nem_folder
        CFG["metadata"]["suppliers"] = [s.strip() for s in suppliers_text.splitlines() if s.strip()]
        with open("config.yaml","w",encoding="utf-8") as f:
            yaml.safe_dump(CFG, f, sort_keys=False, allow_unicode=True)
        st.success("Saved to config.yaml.")

def main():
    if not gate():
        return
    st.title("Seker V2 — AI Design Quality Auditor")

    tabs = st.tabs(["🔍 Audit","📚 Guidance","📈 Analytics","⚙️ Settings"])
    with tabs[0]: tab_audit()
    with tabs[1]: tab_guidance()
    with tabs[2]: tab_analytics()
    with tabs[3]: tab_settings()

if __name__ == "__main__":
    main()
