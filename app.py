
# Seker V2 – AI-Assisted Design QA Auditor
# -------------------------------------------------
# Streamlit app that audits PDFs with rule-based checks + local RAG over guidance PDFs.
# Password gate: "Seker123"
# Rules admin password (Rule Studio/Training): "vanB3lkum21"
#
# Folders created at runtime:
#   ./library  -> drop / upload guidance PDFs (RAG)
#   ./history  -> audit_history.csv, allowlist.json, forbidlist.json, vector_store.json
#
# Exports: Excel (Findings.xlsx) and Annotated PDF
#
# -------------------------------------------------

import os, re, io, json, time, base64, textwrap, pickle, hashlib, datetime as dt
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple

import streamlit as st
import pandas as pd
import numpy as np
import yaml
import fitz  # PyMuPDF

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

APP_TITLE = "Seker V2 – AI QA Auditor"
APP_SUB = "Fast, scoped rule checks + on-device RAG over your guidance PDFs, with continuous learning."
PASSWORD = "Seker123"
RULES_ADMIN_PASSWORD = "vanB3lkum21"

LIB_DIR = "library"
HIST_DIR = "history"
RULES_FILE = "rules_v2.yaml"
HIST_CSV = os.path.join(HIST_DIR, "audit_history.csv")
ALLOWLIST = os.path.join(HIST_DIR, "allowlist.json")
FORBIDLIST = os.path.join(HIST_DIR, "forbidlist.json")
VSTORE = os.path.join(HIST_DIR, "vector_store.pkl")

os.makedirs(LIB_DIR, exist_ok=True)
os.makedirs(HIST_DIR, exist_ok=True)

SUPPLIERS = ["CEG","CTIL","Emfyser","Innov8","Invict","KTL Team (Internal)","Trylon"]
CLIENTS   = ["BTEE","Vodafone","MBNL","H3G","Cornerstone","Cellnex"]
PROJECTS  = ["RAN","Power Resilience","East Unwind","Beacon 4"]
DRAWING_TYPES = ["General Arrangement","Detailed Design"]
SITE_TYPES = ["Greenfield","Rooftop","Streetworks"]
VENDORS = ["Ericsson","Nokia"]
CAB_LOCATIONS = ["Indoor","Outdoor"]
RADIO_LOCATIONS = ["Low Level","High Level","Unique Coverage","Midway"]
SECTORS = [1,2,3,4,5,6]

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

# ---------------------- Utilities ----------------------

def load_yaml(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"rules":[]}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"rules":[]}

def save_yaml(path: str, data: Dict[str, Any]):
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)

def read_json(path: str, fallback):
    if not os.path.exists(path):
        return fallback
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def now_utc_iso():
    return dt.datetime.utcnow().replace(microsecond=0).isoformat()+"Z"

def sha1_bytes(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()

# ---------------------- PDF Text & Search ----------------------

def extract_pages_text(pdf_bytes: bytes) -> List[Dict[str, Any]]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    out = []
    for i, page in enumerate(doc):
        out.append({
            "page": i+1,
            "text": page.get_text("text"),
        })
    return out

def find_text_boxes(page: fitz.Page, keyword: str) -> List[fitz.Rect]:
    flags = fitz.TEXT_IGNORECASE | fitz.TEXT_DEHYPHENATE
    rects = page.search_for(keyword, flags=flags)
    # also try collapsing spaces
    if not rects and " " in keyword:
        rects = page.search_for(" ".join(keyword.split()), flags=flags)
    return rects

def annotate_pdf(pdf_bytes: bytes, findings: List[Dict[str, Any]]) -> bytes:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for f in findings:
        kw = f.get("evidence") or ""
        msg = f.get("message") or ""
        page_no = f.get("page")
        target_pages = [page_no] if isinstance(page_no, int) else list(range(1, len(doc)+1))
        added = False
        for pnum in target_pages:
            p = doc[pnum-1]
            boxes = find_text_boxes(p, kw) if kw else []
            if boxes:
                for r in boxes:
                    p.add_rect_annot(r, color=(1,0,0))
                    p.add_text_annot(r.tl, msg)
                added = True
                break
        if not added:
            # fallback: page 1 sticky
            p = doc[0]
            p.add_text_annot(fitz.Point(50, 50), msg)
    return doc.tobytes()

# ---------------------- RAG over library PDFs ----------------------

@dataclass
class Passage:
    doc_id: str
    page: int
    text: str

def build_vector_store() -> Dict[str, Any]:
    """Index all PDFs in ./library into per-page passages with TFIDF."""
    pdfs = [f for f in os.listdir(LIB_DIR) if f.lower().endswith(".pdf")]
    passages: List[Passage] = []
    for name in pdfs:
        path = os.path.join(LIB_DIR, name)
        try:
            d = fitz.open(path)
            for i, page in enumerate(d):
                t = page.get_text("text")
                t = re.sub(r"\s+", " ", t).strip()
                if t:
                    passages.append(Passage(doc_id=name, page=i+1, text=t))
        except Exception as e:
            print("Failed indexing", name, e)
    if not passages:
        return {}
    texts = [p.text for p in passages]
    vec = TfidfVectorizer(ngram_range=(1,2), min_df=1, max_features=50000)
    X = vec.fit_transform(texts)
    store = {
        "vectorizer": vec,
        "matrix": X,
        "passages": passages,
        "built_at": now_utc_iso(),
    }
    with open(VSTORE, "wb") as f:
        pickle.dump(store, f)
    return store

def load_vector_store() -> Dict[str, Any]:
    if not os.path.exists(VSTORE):
        return build_vector_store()
    with open(VSTORE, "rb") as f:
        return pickle.load(f)

def rag_lookup(query: str, k: int = 2) -> List[Dict[str, Any]]:
    store = load_vector_store()
    if not store:
        return []
    vec = store["vectorizer"]
    X = store["matrix"]
    q = vec.transform([query])
    sims = cosine_similarity(q, X)[0]
    top_idx = sims.argsort()[::-1][:k]
    out = []
    for i in top_idx:
        p: Passage = store["passages"][i]
        out.append({
            "doc": p.doc_id,
            "page": p.page,
            "snippet": p.text[:600],
            "score": float(sims[i])
        })
    return out

# ---------------------- Rules & Checks ----------------------

def scope_match(meta: Dict[str, Any], scope: Dict[str, Any]) -> bool:
    """Return True if the rule scope matches the current metadata."""
    for key, allowed in scope.items():
        val = meta.get(key)
        if isinstance(allowed, list):
            if val not in allowed:
                return False
        else:
            if val != allowed:
                return False
    return True

def file_site_address_check(filename: str, site_address: str) -> Optional[str]:
    """Reject if site address doesn't appear in filename. Ignore ', 0 ,' noise."""
    if not filename or not site_address:
        return None
    addr = site_address.replace(", 0 ,", ",").strip()
    clean = re.sub(r"[^A-Za-z0-9]+", " ", addr).upper()
    clean_file = re.sub(r"[^A-Za-z0-9]+", " ", filename).upper()
    if clean and clean not in clean_file:
        return f"Site address '{site_address}' does not appear in file name '{filename}'."
    return None

def keyword_checks(pages: List[Dict[str, Any]], rule: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Simple must_contain/forbid regex checks across entire doc text."""
    doc_text = "\n".join(p["text"] for p in pages)
    out = []
    severity = rule.get("severity","minor")
    name = rule.get("name","Rule")
    must = rule.get("must_contain", [])
    forbid = rule.get("forbid", [])
    for m in must:
        if re.search(m, doc_text, flags=re.I) is None:
            out.append({
                "type":"missing",
                "severity":severity,
                "rule": name,
                "message": f"Required pattern not found: {m}",
                "evidence": m,
                "page": None
            })
    for f in forbid:
        if re.search(f, doc_text, flags=re.I):
            out.append({
                "type":"forbidden",
                "severity":severity,
                "rule": name,
                "message": f"Forbidden pattern present: {f}",
                "evidence": f,
                "page": None
            })
    return out

def rag_rule_check(pages: List[Dict[str, Any]], rule: Dict[str, Any]) -> List[Dict[str, Any]]:
    """RAG-backed check: if 'trigger' matches doc, ensure 'require' phrase exists; cite guidance."""
    doc_text = "\n".join(p["text"] for p in pages)
    trig = rule.get("trigger")
    require = rule.get("require")
    name = rule.get("name","RAG rule")
    severity = rule.get("severity","major")
    out = []
    if trig and re.search(trig, doc_text, flags=re.I):
        if require and re.search(require, doc_text, flags=re.I) is None:
            cites = rag_lookup(require, k=2)
            cite_txt = "; ".join([f"{c['doc']} p.{c['page']}" for c in cites]) if cites else "no guidance found"
            out.append({
                "type":"missing",
                "severity":severity,
                "rule": name,
                "message": f"Trigger '{trig}' present, but requirement not found: '{require}'. Guidance: {cite_txt}.",
                "evidence": require,
                "page": None
            })
    return out

def spelling_findings(pages: List[Dict[str, Any]], allow_words: List[str]) -> List[Dict[str, Any]]:
    """Very lightweight spell-ish: flag ALLCAPS 3+ letters that are not in allowlist."""
    text = "\n".join(p["text"] for p in pages)
    candidates = sorted(set(re.findall(r"\b[A-Z]{3,}\b", text)))
    out = []
    for wl in candidates:
        if wl not in allow_words and not wl.isdigit():
            out.append({
                "type":"spelling",
                "severity":"minor",
                "rule":"spelling",
                "message": f"Unknown acronym/term: {wl} (not in allowlist)",
                "evidence": wl,
                "page": None
            })
    return out

def run_all_checks(pages: List[Dict[str, Any]], meta: Dict[str, Any], rules: Dict[str, Any], filename: str, do_spell: bool, allow_words: List[str]) -> List[Dict[str, Any]]:
    out = []
    # filename v site address
    msg = file_site_address_check(filename, meta.get("site_address","").strip())
    if msg:
        out.append({
            "type":"filename_site",
            "severity":"major",
            "rule":"Filename matches site address",
            "message": msg,
            "evidence": meta.get("site_address",""),
            "page": None
        })
    # rules
    for r in rules.get("rules", []):
        scope = r.get("scope", {})
        if scope and not scope_match(meta, scope):
            continue
        rtype = r.get("type","keyword")
        if rtype == "keyword":
            out.extend(keyword_checks(pages, r))
        elif rtype == "rag":
            out.extend(rag_rule_check(pages, r))
    # spelling
    if do_spell:
        out.extend(spelling_findings(pages, allow_words))
    return out

# ---------------------- Exports & History ----------------------

def to_excel(findings: List[Dict[str, Any]], meta: Dict[str, Any]) -> bytes:
    df = pd.DataFrame(findings)
    m = pd.DataFrame([meta])
    mem = io.BytesIO()
    with pd.ExcelWriter(mem, engine="xlsxwriter") as xw:
        df.to_excel(xw, index=False, sheet_name="Findings")
        m.to_excel(xw, index=False, sheet_name="Metadata")
    mem.seek(0)
    return mem.read()

def push_history(row: Dict[str, Any]):
    cols = ["timestamp_utc","supplier","client","project","drawing_type","site_type","vendor","cab_loc","radio_loc","sectors","mimos","site_address","pdf_name","excel_name","status","exclude"]
    df = pd.DataFrame([row], columns=cols)
    if os.path.exists(HIST_CSV):
        df0 = pd.read_csv(HIST_CSV)
        df = pd.concat([df0, df], ignore_index=True)
    df.to_csv(HIST_CSV, index=False)

def load_history_df() -> pd.DataFrame:
    if os.path.exists(HIST_CSV):
        try:
            return pd.read_csv(HIST_CSV)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

# ---------------------- UI Helpers ----------------------

def gate() -> bool:
    st.session_state.setdefault("authed", False)
    if st.session_state["authed"]:
        return True
    st.title(APP_TITLE)
    st.caption(APP_SUB)
    pw = st.text_input("Enter access password", type="password")
    if st.button("Enter"):
        if pw == PASSWORD:
            st.session_state["authed"] = True
            st.success("Unlocked.")
            st.experimental_set_query_params(authed="1")
            st.experimental_rerun()
        else:
            st.error("Incorrect password.")
    st.stop()

def meta_form() -> Tuple[Dict[str, Any], int, List[str]]:
    st.subheader("Audit Metadata")
    c1,c2,c3 = st.columns(3)
    supplier = c1.selectbox("Supplier", SUPPLIERS)
    dtype = c2.selectbox("Drawing Type", DRAWING_TYPES)
    client = c3.selectbox("Client", CLIENTS)

    c4,c5,c6 = st.columns(3)
    project = c4.selectbox("Project", PROJECTS)
    site_type = c5.selectbox("Site Type", SITE_TYPES)
    vendor = c6.selectbox("Proposed Vendor", VENDORS)

    c7,c8,c9 = st.columns(3)
    cab = c7.selectbox("Proposed Cabinet Location", CAB_LOCATIONS)
    radio = c8.selectbox("Proposed Radio Location", RADIO_LOCATIONS)
    sectors = c9.selectbox("Quantity of Sectors", SECTORS, index=0)

    site_address = st.text_input("Site Address")

    st.markdown("### Proposed MIMO Config")
    use_s1 = st.checkbox("Use S1 for all sectors", value=True)

    mimo = []
    s1 = st.selectbox("MIMO S1", MIMO_OPTIONS, index=0, key="mimo_s1")
    mimo.append(s1)
    for i in range(2, sectors+1):
        if use_s1:
            mimo.append(s1)
        else:
            mimo.append(st.selectbox(f"MIMO S{i}", MIMO_OPTIONS, index=0, key=f"mimo_s{i}"))

    meta = {
        "supplier": supplier,
        "drawing_type": dtype,
        "client": client,
        "project": project,
        "site_type": site_type,
        "vendor": vendor,
        "cab_loc": cab,
        "radio_loc": radio,
        "sectors": sectors,
        "mimos": mimo,
        "site_address": site_address,
    }
    return meta, sectors, mimo

def audit_tab():
    st.header("🔎 Audit")
    meta, sectors, mimos = meta_form()

    rules = load_yaml(RULES_FILE)
    allow = read_json(ALLOWLIST, [])
    forbid = read_json(FORBIDLIST, [])

    do_spell = st.checkbox("Enable spelling/acronym scan", value=True)

    up = st.file_uploader("Upload design PDF", type=["pdf"])
    if up and st.button("Run audit"):
        raw = up.read()
        pages = extract_pages_text(raw)
        # augment rules with forbidlist quick rules
        if forbid:
            rules.setdefault("rules", []).append({
                "name":"User-forbid list",
                "severity":"major",
                "type":"keyword",
                "forbid": forbid,
                "scope": {}
            })
        findings = run_all_checks(pages, meta, rules, up.name, do_spell, allow)

        status = "Pass" if not [f for f in findings if f["severity"]=="major"] else "Rejected"

        # exports
        excel_bytes = to_excel(findings, {**meta, "status":status})
        annotated = annotate_pdf(raw, findings)

        today = dt.datetime.utcnow().strftime("%Y%m%d")
        base = os.path.splitext(up.name)[0]
        excel_name = f"{base} - {status} - {today}.xlsx"
        pdf_name = f"{base} - {status} - {today} - ANNOTATED.pdf"

        st.download_button("⬇️ Download Excel", data=excel_bytes, file_name=excel_name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.download_button("⬇️ Download Annotated PDF", data=annotated, file_name=pdf_name, mime="application/pdf")

        # push to history
        push_history({
            "timestamp_utc": now_utc_iso(),
            "supplier": meta["supplier"],
            "client": meta["client"],
            "project": meta["project"],
            "drawing_type": meta["drawing_type"],
            "site_type": meta["site_type"],
            "vendor": meta["vendor"],
            "cab_loc": meta["cab_loc"],
            "radio_loc": meta["radio_loc"],
            "sectors": meta["sectors"],
            "mimos": "|".join(meta["mimos"]),
            "site_address": meta["site_address"],
            "pdf_name": pdf_name,
            "excel_name": excel_name,
            "status": status,
            "exclude": False
        })

        st.markdown("#### Findings")
        if findings:
            st.dataframe(pd.DataFrame(findings), use_container_width=True)
        else:
            st.success("No findings — great job!")

def library_tab():
    st.header("📚 Guidance Library (RAG)")
    st.caption("Upload your guidance PDFs (e.g., TDEE53201). The app will index them for citation.")
    ups = st.file_uploader("Upload PDFs", type=["pdf"], accept_multiple_files=True)
    if ups:
        for f in ups:
            with open(os.path.join(LIB_DIR, f.name), "wb") as w:
                w.write(f.read())
        st.success(f"Uploaded {len(ups)} files.")
        if st.button("Rebuild index now"):
            build_vector_store()
            st.info("Index rebuilt.")

    if st.button("Show indexed files"):
        st.write([f for f in os.listdir(LIB_DIR) if f.lower().endswith(".pdf")])

def training_tab():
    st.header("🧪 Training")
    st.caption("Upload *audited* Excel/JSON to accept findings (add to allowlist) or create forbid rules quickly.")
    decision = st.selectbox("This audit decision is…", ["Valid","Not Valid"])
    up = st.file_uploader("Upload Excel or JSON", type=["xlsx","json"])
    if st.button("Ingest training record") and up:
        allow = read_json(ALLOWLIST, [])
        forbid = read_json(FORBIDLIST, [])
        try:
            if up.name.lower().endswith(".xlsx"):
                df = pd.read_excel(up, sheet_name="Findings")
            else:
                df = pd.read_json(up)
            # heuristics: take 'evidence' field
            evid = [e for e in df.get("evidence", []) if isinstance(e, str) and e.strip()]
            if decision=="Valid":
                # add to allowlist
                new = sorted(set(allow + evid))
                write_json(ALLOWLIST, new)
                st.success(f"Added {len(evid)} phrases to allowlist.")
            else:
                # add to forbidlist
                new = sorted(set(forbid + evid))
                write_json(FORBIDLIST, new)
                st.success(f"Added {len(evid)} phrases to forbidlist.")
        except Exception as e:
            st.error(f"Could not ingest: {e}")

    st.divider()
    st.subheader("Quick rule append (YAML)")
    name = st.text_input("Rule name", placeholder="e.g., Power Resilience note present")
    sev = st.selectbox("Severity", ["major","minor"])
    must = st.text_input("Must contain (comma-separated)", placeholder="IMPORTANT NOTE, ELTEK PSU")
    forb = st.text_input("Reject if present (comma-separated)", placeholder="AYGD\\b")
    pw = st.text_input("Rules password", type="password")
    if st.button("Append rule"):
        if pw != RULES_ADMIN_PASSWORD:
            st.error("Wrong password.")
        else:
            data = load_yaml(RULES_FILE)
            data.setdefault("rules", []).append({
                "name": name or "Quick rule",
                "severity": sev,
                "type": "keyword",
                "must_contain": [s.strip() for s in must.split(",") if s.strip()] if must.strip() else [],
                "forbid": [s.strip() for s in forb.split(",") if s.strip()] if forb.strip() else [],
                "scope": {}
            })
            save_yaml(RULES_FILE, data)
            st.success("Rule appended.")

def rule_studio_tab():
    st.header("🧩 Rule Studio")
    pw = st.text_input("Rules password", type="password")
    if pw != RULES_ADMIN_PASSWORD:
        st.info("Enter password to edit rules.")
        return
    st.success("Unlocked.")
    curr = load_yaml(RULES_FILE)
    txt = st.text_area(RULES_FILE, value=yaml.safe_dump(curr, sort_keys=False, allow_unicode=True), height=350)
    c1, c2 = st.columns(2)
    if c1.button("Save rules"):
        try:
            data = yaml.safe_load(txt) or {"rules":[]}
            save_yaml(RULES_FILE, data)
            st.success("Saved.")
        except Exception as e:
            st.error(f"Invalid YAML: {e}")
    if c2.button("Reload from disk"):
        st.experimental_rerun()

def analytics_tab():
    st.header("📈 Analytics")
    dfh = load_history_df()
    if dfh.empty:
        st.info("No history yet.")
        return
    # ensure exclude exists
    if "exclude" not in dfh.columns:
        dfh["exclude"] = False
    c1,c2,c3 = st.columns(3)
    f_client = c1.multiselect("Client", sorted(dfh["client"].dropna().unique().tolist()))
    f_project = c2.multiselect("Project", sorted(dfh["project"].dropna().unique().tolist()))
    f_supplier = c3.multiselect("Supplier", sorted(dfh["supplier"].dropna().unique().tolist()))
    show = dfh.copy()
    if f_client: show = show[show["client"].isin(f_client)]
    if f_project: show = show[show["project"].isin(f_project)]
    if f_supplier: show = show[show["supplier"].isin(f_supplier)]
    show = show[~show["exclude"]]

    rft = (show["status"].eq("Pass").mean()*100) if not show.empty else 0.0
    st.metric("Right first time %", f"{rft:.1f}%")

    if not show.empty:
        st.dataframe(show[[
            "timestamp_utc","supplier","client","project","status","pdf_name","excel_name"
        ]], use_container_width=True)

    st.divider()
    st.subheader("Exclude an entry from analytics")
    if not dfh.empty:
        idx = st.selectbox("Choose row index", list(dfh.index))
        val = st.checkbox("Exclude", value=bool(dfh.loc[idx,"exclude"]) if "exclude" in dfh.columns else False)
        if st.button("Update row"):
            dfh.loc[idx,"exclude"] = val
            dfh.to_csv(HIST_CSV, index=False)
            st.success("Updated.")

def main():
    # sidebar
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.sidebar.title("Seker V2")
    st.sidebar.caption("AI QA Auditor")

    # gate
    if not st.session_state.get("authed", False):
        gate()

    tab = st.sidebar.radio("Navigate", ["Audit","Library","Training","Rule Studio","Analytics"], index=0)

    if tab=="Audit":
        audit_tab()
    elif tab=="Library":
        library_tab()
    elif tab=="Training":
        training_tab()
    elif tab=="Rule Studio":
        rule_studio_tab()
    else:
        analytics_tab()

if __name__ == "__main__":
    main()
