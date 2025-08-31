import os, io, base64, datetime as dt, yaml
import streamlit as st
import pandas as pd
from pypdf import PdfReader
import fitz  # PyMuPDF

from utils.index_loader import GuidanceIndex
from utils.checks import (
    site_address_in_title, power_resilience_hides_mimo,
    gps_eltek_note, spelling_findings, apply_learning_overrides
)

APP_TITLE = "Seker V2 – AI Design Quality Auditor"

def load_config():
    with open("config.yaml","r",encoding="utf-8") as f:
        return yaml.safe_load(f)

cfg = load_config()

HIST_DIR = cfg.get("history_dir","history")
os.makedirs(HIST_DIR, exist_ok=True)
LEARN_FILE = cfg.get("learning_store","learning.csv")
ALLOW_FILE = cfg.get("allow_words_file","allow_words.txt")

def load_learning():
    if os.path.exists(LEARN_FILE):
        return pd.read_csv(LEARN_FILE)
    return pd.DataFrame(columns=["timestamp","rule","snippet","verdict","client","project","site_type","vendor"])

def save_learning(df):
    df.to_csv(LEARN_FILE, index=False)

def read_allow_words():
    if os.path.exists(ALLOW_FILE):
        with open(ALLOW_FILE,"r",encoding="utf-8") as f:
            return {w.strip().lower() for w in f if w.strip()}
    return set()

def pdf_pages_text(pdf_bytes: bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages=[]
    for p in reader.pages:
        try:
            pages.append(p.extract_text() or "")
        except Exception:
            pages.append("")
    return pages

def annotate_pdf(raw_bytes: bytes, findings: list[dict]) -> bytes:
    doc = fitz.open(stream=raw_bytes, filetype="pdf")
    for f in findings:
        pidx = max(0, min(len(doc)-1, (f.get("page",1)-1)))
        page = doc[pidx]
        snippet = (f.get("snippet") or "").strip()
        rect = None
        if snippet:
            inst = page.search_for(snippet, hit_max=1)
            if inst:
                rect = inst[0]
        if rect is None:
            rect = fitz.Rect(36, 36, 300, 120)
        shape = page.new_shape()
        shape.draw_rect(rect)
        shape.finish(color=(1,0,0), fill=None, width=1.2)
        shape.commit()
        page.add_text_annot(rect.br, f'{f.get("rule","rule")} – {f.get("comment","")}')
    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()

def make_excel(findings: list[dict], meta: dict, pdf_name: str, status: str) -> bytes:
    import xlsxwriter  # ensure engine available
    df = pd.DataFrame(findings)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as xw:
        (df if not df.empty else pd.DataFrame(columns=["rule","severity","page","snippet","comment"]))             .to_excel(xw, index=False, sheet_name="Findings")
        pd.DataFrame([meta]).to_excel(xw, index=False, sheet_name="Metadata")
        ws = xw.book.add_worksheet("Summary")
        ws.write(0,0,"PDF"); ws.write(0,1,pdf_name)
        ws.write(1,0,"Status"); ws.write(1,1,status)
        ws.write(2,0,"Generated UTC"); ws.write(2,1,dt.datetime.utcnow().isoformat())
    return buf.getvalue()

def force_css_logo_top_left():
    st.markdown("""
    <style>
      .app-logo { position: fixed; top: 10px; left: 10px; z-index: 9999; opacity:0.95; }
    </style>
    """, unsafe_allow_html=True)
    if "logo_b64" in st.session_state:
        st.markdown(f'<img class="app-logo" width="150" src="data:image/png;base64,{st.session_state.logo_b64}" />', unsafe_allow_html=True)

def b64_of_upload(up):
    return base64.b64encode(up.getvalue()).decode()

def entry_gate():
    if "entry_ok" not in st.session_state:
        st.session_state.entry_ok=False
    if st.session_state.entry_ok:
        return True
    pw = st.text_input("Enter access password", type="password")
    if st.button("Enter"):
        if pw == cfg.get("entry_password","Seker123"):
            st.session_state.entry_ok=True
            return True
        else:
            st.error("Wrong password")
    return False

def settings_gate():
    spw = st.text_input("Settings password", type="password", key="set_pw")
    if st.button("Unlock Settings"):
        if spw == cfg.get("settings_password","vanB3lkum21"):
            st.session_state.set_ok=True
        else:
            st.error("Wrong settings password")

def run_all_checks(pages_text, meta, idx: GuidanceIndex|None, allow_words: set, learning_df):
    findings=[]
    findings += site_address_in_title(meta, meta.get("pdf_name",""))
    findings += power_resilience_hides_mimo(meta)
    findings += gps_eltek_note(meta, pages_text)

    findings += spelling_findings(pages_text, allow_words)

    if idx is not None:
        query = f"{meta.get('client','')} {meta.get('project','')} {meta.get('site_type','')} {meta.get('vendor','')} {meta.get('mimo_s1','')}"
        hits = idx.search(query, k=10)
        for h in hits:
            findings.append({
                "rule":"guidance_ref",
                "severity":"Minor",
                "page":1,
                "snippet": h.get("chunk","")[:140],
                "comment": f"Relevant guidance: {os.path.basename(h.get('source',''))} (score {h.get('score'):.2f})"
            })
    findings = apply_learning_overrides(findings, learning_df, meta)
    return findings

def settings_tab():
    st.subheader("Settings")
    st.info("Upload Guidance Index (.faiss + .pkl) then click Load Index.")
    c1, c2 = st.columns(2)
    with c1:
        up_faiss = st.file_uploader("guidance_index.faiss", type=["faiss"], key="faiss_u")
    with c2:
        up_meta = st.file_uploader("guidance_index.pkl", type=["pkl"], key="pkl_u")
    if st.button("Load Index"):
        if not up_faiss or not up_meta:
            st.error("Please upload BOTH files.")
        else:
            base = "uploaded_guidance_index"
            with open(base+".faiss","wb") as f:
                f.write(up_faiss.getvalue())
            with open(base+".pkl","wb") as f:
                f.write(up_meta.getvalue())
            st.session_state.guidance_index_path = base
            st.success("Guidance index loaded and saved.")

    logo = st.file_uploader("Optional: upload logo (png)", type=["png"], key="logo_up")
    if logo:
        st.session_state.logo_b64 = b64_of_upload(logo)
        st.success("Logo loaded.")

    st.markdown("### Allow-list (spelling)")
    allow_up = st.file_uploader("Upload allow_words.txt", type=["txt"], key="allow_up")
    if allow_up:
        with open(cfg.get("allow_words_file","allow_words.txt"),"wb") as f:
            f.write(allow_up.getvalue())
        st.success("Allow-words updated.")

def audit_tab():
    st.subheader("Audit")
    idx = None
    if "guidance_index_path" in st.session_state:
        try:
            idx = GuidanceIndex.load(st.session_state.guidance_index_path)
            st.success("Guidance index ready.")
        except Exception as e:
            st.error(f"Failed to load index: {e}")
    if idx is None:
        st.warning("Load the Guidance Index in Settings before auditing.")
        return

    st.markdown("#### Metadata")
    c1,c2,c3 = st.columns(3)
    with c1:
        supplier = st.selectbox("Supplier", cfg["suppliers"])
        client = st.selectbox("Client", cfg["clients"])
        project = st.selectbox("Project", cfg["projects"])
    with c2:
        site_type = st.selectbox("Site Type", cfg["site_types"])
        vendor = st.selectbox("Vendor", cfg["vendors"])
        cabinet_loc = st.selectbox("Proposed Cabinet Location", cfg["cabinet_locations"])
    with c3:
        radio_loc = st.selectbox("Proposed Radio Location", cfg["radio_locations"])
        sectors = st.selectbox("Quantity of Sectors", cfg["sectors_allowed"])
        site_addr = st.text_input("Site Address")

    st.markdown("#### MIMO per sector")
    mimo_opts = cfg["mimo_options"]
    s_cols = st.columns(sectors)
    mimo_vals=[]
    for i in range(sectors):
        with s_cols[i]:
            mimo_vals.append(st.selectbox(f"S{i+1} MIMO", mimo_opts, key=f"mimo_{i+1}"))
    apply_to_all = st.checkbox("Use S1 MIMO for all sectors")
    if apply_to_all and sectors>0 and mimo_vals:
        mimo_vals = [mimo_vals[0]]*sectors

    up = st.file_uploader("Upload PDF design", type=["pdf"], key="pdf_upload")
    do_spell = st.checkbox("Enable spellcheck")
    exclude = st.checkbox("Exclude this review from analytics", value=False)

    can_audit = all([supplier, client, project, site_type, vendor, cabinet_loc, radio_loc, sectors, site_addr]) and up
    if st.button("Run Audit", disabled=not can_audit):
        raw = up.getvalue()
        pages = pdf_pages_text(raw)
        allow = read_allow_words() if do_spell else set()
        meta = {
            "pdf_name": up.name,
            "supplier": supplier,
            "client": client,
            "project": project,
            "site_type": site_type,
            "vendor": vendor,
            "cabinet_location": cabinet_loc,
            "radio_location": radio_loc,
            "sectors": sectors,
            "site_address": site_addr,
            **{f"mimo_s{i+1}": mimo_vals[i] if i<len(mimo_vals) else "" for i in range(6)}
        }
        st.session_state.last_meta = meta
        learning_df = load_learning()
        findings = run_all_checks(pages, meta, idx, allow, learning_df)
        status = "Pass" if len([f for f in findings if f["severity"]!="Info" and f["severity"]!="Minor"])==0 else "Rejected"
        st.session_state.findings = findings
        st.session_state.status = status
        st.session_state.raw_pdf = raw

    if "findings" in st.session_state:
        st.success(f"Audit complete: **{st.session_state.status}**  | Findings: {len(st.session_state.findings)}")
        df = pd.DataFrame(st.session_state.findings)
        st.dataframe(df, use_container_width=True, height=320)

        st.markdown("#### Validate findings (learning)")
        learn_rows=[]
        if not df.empty:
            for i, row in df.iterrows():
                c1,c2,c3 = st.columns([5,1,1])
                with c1: st.caption(f"Rule: {row['rule']} | Snippet: {row.get('snippet','')[:100]}")
                with c2:
                    if st.button("Valid", key=f"valid_{i}"):
                        learn_rows.append(("Valid", row))
                with c3:
                    if st.button("Invalid", key=f"invalid_{i}"):
                        learn_rows.append(("Invalid", row))
        if learn_rows:
            ldf = load_learning()
            now = dt.datetime.utcnow().isoformat()
            for verdict, r in learn_rows:
                nl = {
                    "timestamp": now,
                    "rule": r["rule"],
                    "snippet": r.get("snippet",""),
                    "verdict": verdict,
                    "client": st.session_state.last_meta.get("client"),
                    "project": st.session_state.last_meta.get("project"),
                    "site_type": st.session_state.last_meta.get("site_type"),
                    "vendor": st.session_state.last_meta.get("vendor"),
                }
                ldf = pd.concat([ldf, pd.DataFrame([nl])], ignore_index=True)
            save_learning(ldf)
            st.success("Learning updated.")

        st.markdown("#### Export")
        excel_bytes = make_excel(st.session_state.findings, st.session_state.last_meta,
                                 st.session_state.last_meta["pdf_name"], st.session_state.status)
        annotated = annotate_pdf(st.session_state.raw_pdf, st.session_state.findings)
        base = os.path.splitext(st.session_state.last_meta["pdf_name"])[0]
        stamp = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        xname = f"{base}_{st.session_state.status}_{stamp}.xlsx"
        pname = f"{base}_{st.session_state.status}_{stamp}.pdf"

        st.download_button("Download Excel", data=excel_bytes, file_name=xname, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.download_button("Download Annotated PDF", data=annotated, file_name=pname, mime="application/pdf")

        hist = {
            "timestamp_utc": dt.datetime.utcnow().isoformat(),
            "supplier": st.session_state.last_meta["supplier"],
            "client": st.session_state.last_meta["client"],
            "project": st.session_state.last_meta["project"],
            "status": st.session_state.status,
            "pdf_name": st.session_state.last_meta["pdf_name"],
            "excel_name": xname,
            "annot_pdf_name": pname,
            "exclude": exclude
        }
        fn = os.path.join(cfg.get("history_dir","history"), f"{stamp}.csv")
        pd.DataFrame([hist]).to_csv(fn, index=False)

def analytics_tab():
    st.subheader("Analytics")
    rows=[]
    for fn in sorted(os.listdir(cfg.get("history_dir","history"))):
        if fn.endswith(".csv"):
            rows.append(pd.read_csv(os.path.join(cfg.get("history_dir","history"),fn)))
    if not rows:
        st.info("No history yet."); return
    df = pd.concat(rows, ignore_index=True)
    c1,c2,c3 = st.columns(3)
    with c1:
        sel_client = st.selectbox("Client", ["(All)"]+sorted(df["client"].dropna().unique().tolist()))
    with c2:
        sel_project = st.selectbox("Project", ["(All)"]+sorted(df["project"].dropna().unique().tolist()))
    with c3:
        sel_supplier = st.selectbox("Supplier", ["(All)"]+sorted(df["supplier"].dropna().unique().tolist()))
    show = df.copy()
    if sel_client!="(All)": show = show[show["client"]==sel_client]
    if sel_project!="(All)": show = show[show["project"]==sel_project]
    if sel_supplier!="(All)": show = show[show["supplier"]==sel_supplier]
    if "exclude" in show.columns: show = show[~show["exclude"].fillna(False)]
    st.dataframe(show[["timestamp_utc","supplier","client","project","status","pdf_name","excel_name","annot_pdf_name"]],
                 use_container_width=True)

def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    force_css_logo_top_left()
    st.title(APP_TITLE)

    if "set_ok" not in st.session_state: st.session_state.set_ok=False
    if "logo_b64" not in st.session_state: st.session_state.logo_b64=None

    if not entry_gate():
        st.stop()

    tab_audit, tab_analytics, tab_settings = st.tabs(["Audit","Analytics","Settings"])
    with tab_settings:
        if not st.session_state.get("set_ok", False):
            settings_gate()
        if st.session_state.get("set_ok", False):
            settings_tab()
    with tab_audit:
        audit_tab()
    with tab_analytics:
        analytics_tab()

if __name__=="__main__":
    main()
