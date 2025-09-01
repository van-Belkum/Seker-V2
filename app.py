\
import io, os, json, datetime as dt, re, yaml, zipfile
import streamlit as st
import pandas as pd
from spellchecker import SpellChecker

from utils.guidance_loader import build_guidance_index_from_zip
from utils.pdf_tools import annotate_pdf
from utils.semantic import fuzzy_contains

APP_TITLE = "Seker V2 - AI Design Quality Auditor"
ENTRY_PASSWORD = "Seker123"
RULES_PASSWORD = "vanB3lkum21"

SUPPLIERS = [
    "CEG","CTIL","Emfyser","Innov8","Invict","KTL Team (Internal)","Trylon"
]

MIMO_OPTIONS = [
    "18 @2x2",
    "18 @2x2; 26 @4x4",
    "18 @2x2; 70\\80 @2x2",
    "18\\21 @2x2",
    "18\\21 @4x4; 70\\80 @2x2; 3500 @32x32",
]

HISTORY_DIR = "history"
os.makedirs(HISTORY_DIR, exist_ok=True)
TRAIN_FILE = os.path.join(HISTORY_DIR, "training.jsonl")
GUIDANCE_FILE = os.path.join(HISTORY_DIR, "guidance_index.json")

def save_training(record: dict):
    with open(TRAIN_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def load_training():
    out = []
    if not os.path.exists(TRAIN_FILE): return out
    with open(TRAIN_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try: out.append(json.loads(line))
            except: pass
    return out

def gate():
    if "ok" not in st.session_state:
        st.session_state.ok = False
    if st.session_state.ok: 
        return True
    pw = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Enter") and pw == ENTRY_PASSWORD:
        st.session_state.ok = True
    if not st.session_state.ok:
        st.stop()
    return True

def layout_header():
    st.markdown(f"# {APP_TITLE}")
    st.caption("Guidance-driven checks, live learning, annotated PDFs & Excel output.")

def guidance_tab():
    st.subheader("Guidance")
    st.write("Upload a **ZIP** containing DOCX/PPTX/PDF guidance. The app extracts key lines (MUST/SHALL/REQUIRED/NOTE) as candidate rules.")
    zup = st.file_uploader("Upload guidance ZIP", type=["zip"], key="gzu")
    if zup and st.button("Load ZIP"):
        data = zup.read()
        idx = build_guidance_index_from_zip(data)
        with open(GUIDANCE_FILE, "w", encoding="utf-8") as f:
            json.dump(idx, f, ensure_ascii=False, indent=2)
        st.success(f"Guidance loaded. {len(idx.get('rules',[]))} rule lines extracted from {len(idx.get('stats',{}))} files.")
        with st.expander("Preview extracted lines"):
            st.json(idx.get("rules",[])[:50])

def _load_guidance():
    if not os.path.exists(GUIDANCE_FILE): 
        return {"rules": [], "stats": {}}
    with open(GUIDANCE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _scoped_key(meta: dict) -> str:
    return "|".join([
        meta.get("client",""),
        meta.get("project",""),
        meta.get("supplier",""),
        meta.get("site_type",""),
        meta.get("vendor",""),
        meta.get("mimo",""),
    ])

def _scoped_rules(meta: dict) -> list[dict]:
    key = _scoped_key(meta)
    out = []
    for r in load_training():
        if r.get("scope") == key and r.get("decision") == "accept":
            out.append({"text": r.get("text",""), "source": r.get("source","training")})
    return out

def audit_tab():
    st.subheader("Run Audit")
    col1, col2, col3 = st.columns(3)
    with col1:
        supplier = st.selectbox("Supplier", SUPPLIERS)
        client = st.selectbox("Client", ["BTEE","Vodafone","MBNL","H3G","Cornerstone","Cellnex"])
    with col2:
        project = st.selectbox("Project", ["RAN","Power Resilience","East Unwind","Beacon 4"])
        site_type = st.selectbox("Site Type", ["Greenfield","Rooftop","Streetworks"])
    with col3:
        vendor = st.selectbox("Proposed Vendor", ["Ericsson","Nokia"])
        mimo = st.selectbox("Proposed MIMO Config", MIMO_OPTIONS)

    meta = {"supplier":supplier,"client":client,"project":project,"site_type":site_type,"vendor":vendor,"mimo":mimo}

    up = st.file_uploader("Upload PDF design", type=["pdf"], key="pdfup")
    if st.button("Run Audit"):

        # Ensure guidance exists
        g = _load_guidance()
        if not g.get("rules"):
            st.error("No guidance loaded. Go to Guidance tab first and upload a ZIP.")
            st.stop()

        if not up:
            st.error("Please upload a PDF.")
            st.stop()

        pdf_bytes = up.read()
        # Combine rules: guidance + accepted training for this scope
        rules = [{"text": r["text"], "source": r["source"]} for r in g.get("rules",[])]
        rules.extend(_scoped_rules(meta))

        # Spellchecker toggle
        do_spell = st.checkbox("Enable spelling checks (experimental)", value=False)
        sp = SpellChecker() if do_spell else None

        # Search each guidance line in PDF text with fuzzy match
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        all_text = "\\n".join(page.get_text("text") for page in doc)

        findings = []
        for r in rules[:2000]:  # cap for speed
            t = r["text"]
            if fuzzy_contains(all_text, t, threshold=80):
                # mark as INFO (found) so we can track; we only *reject* on negative rules you add via Training
                findings.append({"severity":"info","text":t,"source":r["source"],"comment":f"Guidance line present: {t[:120]}"})
            else:
                findings.append({"severity":"major","text":t,"source":r["source"],"comment":f"Guidance line NOT found: {t[:120]}"})

        # Spelling (very light)
        if sp is not None:
            words = re.findall(r"[A-Za-z]{4,}", all_text)
            unknown = [w for w in words if w.lower() not in sp]
            for w in unknown[:200]:
                sug = next(iter(sp.candidates(w)), None)
                findings.append({"severity":"minor","text":w,"source":"spell","comment":f"Possible spelling issue: {w} → {sug}"})
        
        df = pd.DataFrame(findings)
        st.success(f"{len(df)} findings.")
        st.dataframe(df.head(1000), use_container_width=True)

        # Validation UI
        st.markdown("### Validate")
        rule_txt = st.text_area("Rule text to save (copy from a row, or type a new one)")
        decision = st.selectbox("Decision", ["accept","reject"])
        if st.button("Save to Training Log"):
            rec = {"ts": dt.datetime.utcnow().isoformat(), "scope": _scoped_key(meta), "decision": decision, "text": rule_txt, "source":"manual"}
            save_training(rec)
            st.success("Saved. Re-run audit to apply.")

        # Downloads
        from io import BytesIO
        # Excel
        xls = BytesIO()
        with pd.ExcelWriter(xls, engine="openpyxl") as xw:
            df.to_excel(xw, index=False, sheet_name="Findings")
        st.download_button("Download Excel", data=xls.getvalue(), file_name=f"{os.path.splitext(up.name)[0]}_findings.xlsx")

        # Annotated PDF (only pin comments for 'major' items)
        majors = [f for f in findings if f["severity"]=="major"]
        annot_items = [{"page":None, "text":f.get("text","")[:120], "comment":f.get("comment","")} for f in majors[:80]]
        pdf_a = annotate_pdf(pdf_bytes, annot_items)
        st.download_button("Download annotated PDF", data=pdf_a, file_name=f"{os.path.splitext(up.name)[0]}_annotated.pdf", mime="application/pdf")

def training_tab():
    st.subheader("Training Log")
    data = load_training()
    if not data:
        st.info("No training items yet.")
        return
    df = pd.DataFrame(data)
    st.dataframe(df.sort_values("ts", ascending=False), use_container_width=True)

def analytics_tab():
    st.subheader("Analytics (light)")
    data = load_training()
    if not data:
        st.info("No data yet.")
        return
    df = pd.DataFrame(data)
    st.bar_chart(df["decision"].value_counts())

def settings_tab():
    st.subheader("Settings")
    pw = st.text_input("Settings password", type="password")
    if pw != RULES_PASSWORD:
        st.info("Enter password to unlock settings.")
        st.stop()
    st.success("Unlocked.")

    if st.button("Clear guidance & training"):
        for p in [GUIDANCE_FILE, TRAIN_FILE]:
            if os.path.exists(p): os.remove(p)
        st.success("Cleared.")

def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    gate()
    layout_header()
    tabs = st.sidebar.radio("Navigation", ["Audit","Training","Analytics","Guidance","Settings"])
    if tabs == "Guidance":
        guidance_tab()
    elif tabs == "Training":
        training_tab()
    elif tabs == "Analytics":
        analytics_tab()
    elif tabs == "Settings":
        settings_tab()
    else:
        audit_tab()

if __name__ == "__main__":
    main()
