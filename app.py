import os, io, re, json, base64, datetime as dt
from typing import List, Dict, Any, Optional

import streamlit as st
import pandas as pd
import numpy as np
import fitz  # PyMuPDF
import yaml
from rapidfuzz import fuzz
from spellchecker import SpellChecker

from utils.guidance import build_index_from_folder, build_index_from_zip, search_terms

APP_TITLE = "Seker V2 – AI Design QA"
PASSWORD_ENTRY = "Seker123"
RULES_PASSWORD = "vanB3lkum21"

# ---------- CONSTANTS ----------
SUPPLIERS = [
    "CEG","CTIL","Emfyser","Innov8","Invict","KTL Team (Internal)","Trylon"
]
CLIENTS = ["BTEE","Vodafone","MBNL","H3G","Cornerstone","Cellnex"]
PROJECTS = ["RAN","Power Resilience","East Unwind","Beacon 4"]
DRAWING_TYPES = ["General Arrangement","Detailed Design"]
SITE_TYPES = ["Greenfield","Rooftop","Streetworks"]
VENDORS = ["Ericsson","Nokia"]
CAB_LOCS = ["Indoor","Outdoor"]
RADIO_LOCS = ["Low Level","High Level","Midway","Unique Coverage"]
SECTORS = [str(i) for i in [1,2,3,4,5,6]]

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
 "(blank)"
]

HISTORY_DIR = "history"
EXPORTS_DIR = os.path.join(HISTORY_DIR, "exports")
GUIDANCE_CACHE = os.path.join(HISTORY_DIR, "guidance_index.json")
RULES_BASE = "rules/base_rules.yaml"
RULES_USER = "rules/user_rules.yaml"
os.makedirs(HISTORY_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)
os.makedirs("rules", exist_ok=True)

# ---------- UTIL ----------
def b64dl(data: bytes, filename: str, label: str):
    b64 = base64.b64encode(data).decode()
    href = f'<a download="{filename}" href="data:application/octet-stream;base64,{b64}">{label}</a>'
    st.markdown(href, unsafe_allow_html=True)

def load_yaml(path: str) -> Dict:
    if not os.path.exists(path):
        return {}
    try:
        return yaml.safe_load(open(path, "r", encoding="utf-8")) or {}
    except Exception:
        return {}

def save_yaml(path: str, data: Dict):
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)

def load_rules() -> Dict:
    base = load_yaml(RULES_BASE)
    user = load_yaml(RULES_USER)
    merged = {"checklist": [], "spelling": {}}
    merged["checklist"] = (base.get("checklist") or []) + (user.get("checklist") or [])
    sp = {}
    sp.update(base.get("spelling") or {})
    # merge allow lists
    allow = set(sp.get("allow_words", []))
    allow |= set((user.get("spelling") or {}).get("allow_words", []))
    sp["allow_words"] = sorted(list(allow))
    merged["spelling"] = sp
    return merged

def load_guidance_index() -> Dict:
    if os.path.exists(GUIDANCE_CACHE):
        try:
            return json.load(open(GUIDANCE_CACHE,"r",encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_guidance_index(index: Dict):
    json.dump(index, open(GUIDANCE_CACHE,"w",encoding="utf-8"))

def pdf_text_pages(pdf_bytes: bytes) -> List[str]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    return [p.get_text("text") for p in doc]

def search_on_page(page: fitz.Page, term: str) -> List[fitz.Rect]:
    rects = []
    if not term.strip():
        return rects
    for inst in page.search_for(term, hit_max=32):  # returns list of rects
        rects.append(inst)
    return rects

def annotate_pdf(pdf_bytes: bytes, findings: List[Dict[str, Any]]) -> bytes:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for f in findings:
        term = f.get("match") or ""
        page_no = f.get("page", None)
        note = f.get("message", "")
        target_pages = range(doc.page_count) if page_no is None else [page_no]
        for pn in target_pages:
            page = doc[pn]
            boxes = search_on_page(page, term) if term else []
            if not boxes:
                continue
            for r in boxes:
                # rectangle highlight + popup
                page.add_rect_annot(r, color=(1,0,0))
                center = fitz.Point(r.x1, r.y0)  # edge for sticky note
                page.add_text_annot(center, note)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()

def make_excel(findings: List[Dict], meta: Dict, original_name: str, status: str) -> bytes:
    now = dt.datetime.utcnow().isoformat(timespec="seconds")
    df = pd.DataFrame(findings) if findings else pd.DataFrame(columns=["severity","message","page","match"])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as xw:
        df.to_excel(xw, index=False, sheet_name="Findings")
        pd.DataFrame([meta]).to_excel(xw, index=False, sheet_name="Metadata")
        ws = xw.book.add_worksheet("Summary")
        ws.write(0,0,"Original file"); ws.write(0,1, original_name)
        ws.write(1,0,"Status"); ws.write(1,1, status)
        ws.write(2,0,"UTC"); ws.write(2,1, now)
    return buf.getvalue()

def append_history(row: Dict):
    fn = os.path.join(HISTORY_DIR, "history.csv")
    df = pd.DataFrame([row])
    if os.path.exists(fn):
        df.to_csv(fn, mode="a", header=False, index=False)
    else:
        df.to_csv(fn, index=False)

# ---------- RULE EXEC ----------
def address_in_title(title_line: str, address: str) -> bool:
    if not title_line or not address:
        return False
    norm = lambda s: re.sub(r"[^A-Za-z0-9]+","", s).lower()
    cand = norm(title_line)
    addr = norm(address.replace(", 0 ,", ","))
    return addr in cand

def run_checklist(pages: List[str], rules: Dict, meta: Dict, guidance: Dict) -> List[Dict]:
    findings = []
    full_text = "\n".join(pages)

    # If we can, try to guess title line as first page first 10 lines
    title_line = "\n".join(pages[0].splitlines()[:10]) if pages else ""

    for r in rules.get("checklist", []):
        scope = r.get("scope", {})
        # scope filter
        ok = True
        for k in ["project","client","site_type","vendor"]:
            if scope.get(k):
                sel = meta.get(k) or ""
                ok = ok and (sel in scope[k])
        if not ok: 
            continue

        # special meta rules
        if r.get("rule") == "address_in_title":
            addr = meta.get(r.get("meta_key") or "", "")
            if addr.strip():
                if not address_in_title(title_line, addr):
                    findings.append({
                        "severity": r.get("severity","minor"),
                        "message": f"Site address not found in drawing title (expected: {addr}).",
                        "page": 0,
                        "match": addr
                    })
            continue

        must = r.get("must_contain", []) or []
        bad = r.get("reject_if_present", []) or []
        missing = [t for t in must if t.lower() not in full_text.lower()]
        present_bad = [t for t in bad if t.lower() in full_text.lower()]

        if missing:
            findings.append({
                "severity": r.get("severity","minor"),
                "message": f"Missing required term(s): {', '.join(missing)}",
                "page": None,
                "match": missing[0]
            })
        if present_bad:
            findings.append({
                "severity": r.get("severity","major"),
                "message": f"Forbidden term(s) present: {', '.join(present_bad)}",
                "page": None,
                "match": present_bad[0]
            })

        # If rule has must_contain and we have guidance index, try to confirm presence within guidance
        if guidance and must:
            hits = search_terms(guidance, must)
            if not hits:
                # Could be fine, but surface as info
                findings.append({
                    "severity":"minor",
                    "message": f"Guidance cross-ref: could not find all terms {must} in loaded guidance.",
                    "page": None,
                    "match": must[0]
                })
    return findings

def spelling_findings(pages: List[str], allow_words: List[str]) -> List[Dict]:
    sp = SpellChecker(distance=1)
    if allow_words:
        sp.word_frequency.load_words([w.lower() for w in allow_words])
    words = re.findall(r"[A-Za-z]{3,}", "\n".join(pages))
    findings = []
    # Limit to first 1200 unique words to keep performance snappy
    for w in list(dict.fromkeys(words))[:1200]:
        wl = w.lower()
        if wl in [a.lower() for a in allow_words]:
            continue
        if wl not in sp:
            sug = next(iter(sp.candidates(wl)), None)
            findings.append({
                "severity":"minor",
                "message": f"Possible spelling: '{w}'" + (f" → '{sug}'" if sug else ""),
                "page": None,
                "match": w
            })
    return findings

# ---------- UI HELPERS ----------
def gate():
    st.session_state.setdefault("authed", False)
    if st.session_state["authed"]:
        return True
    with st.form("gate"):
        st.subheader("Enter access password")
        pw = st.text_input("Password", type="password")
        ok = st.form_submit_button("Enter")
    if ok:
        if pw == PASSWORD_ENTRY:
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("Wrong password")
    return False

def status_strip(rules_loaded: int, guidance_count: int, spelling_on: bool):
    st.caption(
        f"Rules: **{rules_loaded}** | Guidance index: "
        + ("✅ loaded" if guidance_count>0 else "❌ not loaded")
        + f" ({guidance_count}) | Spelling: {'ON' if spelling_on else 'OFF'}"
    )

def load_history_df() -> pd.DataFrame:
    fn = os.path.join(HISTORY_DIR, "history.csv")
    if not os.path.exists(fn):
        cols = ["timestamp_utc","supplier","client","project","status","pdf_name","excel_name","exclude"]
        return pd.DataFrame(columns=cols)
    df = pd.read_csv(fn)
    # normalize exclude
    if "exclude" not in df.columns:
        df["exclude"] = False
    df["exclude"] = df["exclude"].fillna(False).astype(bool)
    return df

# ---------- PAGES ----------
def audit_tab():
    st.header("Audit")

    rules = load_rules()
    gindex = load_guidance_index()
    spelling_default = (rules.get("spelling") or {}).get("enabled_default", True)
    allow_words = (rules.get("spelling") or {}).get("allow_words", [])

    status_strip(len(rules.get("checklist", [])), gindex.get("count",0), spelling_default)

    with st.expander("Audit metadata (required)", expanded=True):
        col = st.columns(4)
        meta = {}
        meta["supplier"] = col[0].selectbox("Supplier", SUPPLIERS)
        meta["drawing_type"] = col[1].selectbox("Drawing Type", DRAWING_TYPES)
        meta["client"] = col[2].selectbox("Client", CLIENTS)
        meta["project"] = col[3].selectbox("Project", PROJECTS)

        col2 = st.columns(4)
        meta["site_type"] = col2[0].selectbox("Site Type", SITE_TYPES)
        meta["vendor"] = col2[1].selectbox("Proposed Vendor", VENDORS)
        meta["cab_loc"] = col2[2].selectbox("Proposed Cabinet Location", CAB_LOCS)
        meta["radio_loc"] = col2[3].selectbox("Proposed Radio Location", RADIO_LOCS)

        col3 = st.columns(2)
        qty = col3[0].selectbox("Quantity of Sectors", SECTORS, index=0)
        meta["sectors"] = int(qty)
        meta["site_address"] = col3[1].text_input("Site Address", placeholder="MANBY ROAD , 0 , ...")

    st.subheader("Proposed MIMO Config")
    use_s1 = st.checkbox("Use S1 value for all sectors", value=True)
    mimo_vals = {}
    for i in range(1, meta["sectors"]+1):
        if i == 1 or not use_s1:
            mimo_vals[f"S{i}"] = st.selectbox(f"MIMO S{i}", MIMO_OPTIONS, key=f"mimo_{i}")
        else:
            mimo_vals[f"S{i}"] = mimo_vals["S1"]
    meta["mimo"] = mimo_vals

    do_spell = st.checkbox("Enable spelling", value=spelling_default)
    up = st.file_uploader("Upload PDF design", type=["pdf"])
    exclude = st.checkbox("Exclude this audit from analytics", value=False)
    run_btn = st.button("Run Audit")

    if run_btn and not up:
        st.warning("Please upload a PDF.")
        return

    if run_btn and up:
        raw = up.read()
        pages = pdf_text_pages(raw)

        with st.status("Running checks...", expanded=True) as status:
            findings = run_checklist(pages, rules, meta, gindex)
            if do_spell:
                findings.extend(spelling_findings(pages, allow_words))
            status.update(label="Annotating PDF…")
            annotated = annotate_pdf(raw, findings) if findings else raw
            status.update(label="Preparing exports…")

        status_str = "Rejected" if any(f["severity"]=="major" for f in findings) else "Pass"
        now = dt.datetime.utcnow().strftime("%Y-%m-%dT%H_%M_%S")
        base = os.path.splitext(up.name)[0]
        pdf_name = f"{base}_{status_str}_{now}.pdf"
        xlsx_name = f"{base}_{status_str}_{now}.xlsx"

        xls_bytes = make_excel(findings, meta, up.name, status_str)

        # Persist
        open(os.path.join(EXPORTS_DIR, pdf_name), "wb").write(annotated)
        open(os.path.join(EXPORTS_DIR, xlsx_name), "wb").write(xls_bytes)

        append_history({
            "timestamp_utc": dt.datetime.utcnow().isoformat(timespec="seconds"),
            "supplier": meta["supplier"], "client": meta["client"], "project": meta["project"],
            "status": status_str, "pdf_name": pdf_name, "excel_name": xlsx_name,
            "exclude": exclude
        })

        st.success(f"Audit complete: **{status_str}** – {len(findings)} finding(s).")
        st.download_button("Download annotated PDF", annotated, file_name=pdf_name)
        st.download_button("Download Excel report", xls_bytes, file_name=xlsx_name)

        with st.expander("Findings"):
            st.dataframe(pd.DataFrame(findings))

        with st.expander("Files saved"):
            st.code(os.path.join(EXPORTS_DIR, pdf_name))
            st.code(os.path.join(EXPORTS_DIR, xlsx_name))

    st.divider()
    st.caption("Guidance quick controls")
    cols = st.columns(3)
    if cols[0].button("Rebuild guidance index (from local path)"):
        root = st.session_state.get("guidance_root", "")
        idx = build_index_from_folder(root)
        save_guidance_index(idx)
        st.toast(f"Indexed {idx.get('count',0)} document(s) from {root}")
    zip_up = cols[1].file_uploader("Upload guidance .zip", type=["zip"], key="zip_up")
    if zip_up and cols[2].button("Index uploaded zip"):
        idx = build_index_from_zip(zip_up.read())
        save_guidance_index(idx)
        st.toast(f"Indexed {idx.get('count',0)} document(s) from zip")

def analytics_tab():
    st.header("Analytics")
    df = load_history_df()
    if df.empty:
        st.info("No audits yet.")
        return

    c = st.columns(4)
    fil_sup = c[0].selectbox("Supplier", ["(All)"]+SUPPLIERS)
    fil_cli = c[1].selectbox("Client", ["(All)"]+CLIENTS)
    fil_prj = c[2].selectbox("Project", ["(All)"]+PROJECTS)
    hide_excl = c[3].checkbox("Hide excluded", value=True)

    show = df.copy()
    if fil_sup != "(All)":
        show = show[show["supplier"]==fil_sup]
    if fil_cli != "(All)":
        show = show[show["client"]==fil_cli]
    if fil_prj != "(All)":
        show = show[show["project"]==fil_prj]
    if hide_excl:
        show = show[~show["exclude"]]

    st.metric("Total audits", len(show))
    st.metric("Right-first-time %", f"{(show['status'].eq('Pass').mean()*100 if len(show) else 0):.1f}%")
    st.dataframe(show[["timestamp_utc","supplier","client","project","status","pdf_name","excel_name","exclude"]], use_container_width=True)

def training_tab():
    st.header("Training")
    st.caption("Upload audited reports (Excel/JSON) or append quick rules (password required).")

    col = st.columns(2)
    up = col[0].file_uploader("Upload Excel/JSON training record", type=["xlsx","xls","json"])
    decision = col[0].selectbox("This audit decision is…", ["Valid","Not Valid"])

    if col[0].button("Ingest training record") and up:
        # We simply archive them for now; a nightly job could learn from these.
        ts = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        fn = f"train_{ts}_{up.name}"
        open(os.path.join(HISTORY_DIR, fn),"wb").write(up.read())
        st.success("Saved for offline learning.")

    st.subheader("Add a quick rule")
    name = col[1].text_input("Rule name", placeholder="e.g., Power Resilience note present")
    sev = col[1].selectbox("Severity", ["minor","major"])
    must = col[1].text_input("Must contain (comma-separated)", placeholder="IMPORTANT NOTE, ELTEK PSU")
    forb = col[1].text_input("Reject if present (comma-separated)")
    pw = col[1].text_input("Rules password", type="password", placeholder="vanB3lkum21")

    if col[1].button("Append rule"):
        if pw != RULES_PASSWORD:
            st.error("Wrong password.")
        else:
            y = load_yaml(RULES_USER)
            y.setdefault("checklist", [])
            y["checklist"].append({
                "name": name or "Quick rule",
                "severity": sev,
                "must_contain": [s.strip() for s in must.split(",") if s.strip()],
                "reject_if_present": [s.strip() for s in forb.split(",") if s.strip()]
            })
            save_yaml(RULES_USER, y)
            st.success("Rule appended to rules/user_rules.yaml")
    st.divider()
    st.caption("Current quick rules")
    st.code(yaml.safe_dump(load_yaml(RULES_USER), sort_keys=False, allow_unicode=True))

def settings_tab():
    st.header("Settings")
    rules = load_rules()
    st.caption("These settings are local to the app.")

    # Guidance path
    st.subheader("Guidance")
    root = st.text_input("Guidance root folder (local path)", value=st.session_state.get("guidance_root",""))
    if st.button("Save root"):
        st.session_state["guidance_root"] = root
        st.success("Saved.")
    cols = st.columns(3)
    if cols[0].button("Rebuild from root now"):
        idx = build_index_from_folder(st.session_state.get("guidance_root",""))
        save_guidance_index(idx)
        st.success(f"Indexed {idx.get('count',0)} document(s).")
    zipu = cols[1].file_uploader("Upload guidance .zip", type=["zip"], key="zipset")
    if zipu and cols[2].button("Index uploaded zip"):
        idx = build_index_from_zip(zipu.read())
        save_guidance_index(idx)
        st.success(f"Indexed {idx.get('count',0)} document(s).")

    st.subheader("Rules (read-only quick view)")
    st.code(yaml.safe_dump(rules, sort_keys=False, allow_unicode=True)[:4000])

def main():
    st.set_page_config(APP_TITLE, layout="wide")
    st.title(APP_TITLE)

    if not gate():
        return

    tabs = st.tabs(["Audit","Analytics","Training","Settings"])
    with tabs[0]:
        audit_tab()
    with tabs[1]:
        analytics_tab()
    with tabs[2]:
        training_tab()
    with tabs[3]:
        settings_tab()

if __name__ == "__main__":
    main()
