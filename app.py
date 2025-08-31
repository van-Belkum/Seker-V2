# Seker-V2 — AI Design Auditor (Guidance ZIP support)
# Run: streamlit run app.py

import os, io, re, json, pickle, hashlib, datetime as dt
from pathlib import Path

import streamlit as st
import pandas as pd

from utils.guidance_loader import (
    build_index_from_folder,
    build_index_from_zipfile,
    index_stats,
    search_guidance_for_terms,
    save_index,
    load_index,
)

from utils.pdf_tools import (
    extract_text_pages,
    annotate_pdf_with_findings,
)

# ---------------- Config & constants ----------------

APP_TITLE = "Seker-V2 — AI Design Auditor"
HISTORY_CSV = "history.csv"
GUIDANCE_CACHE_DIR = ".guidance_cache"
INDEX_PKL = os.path.join(GUIDANCE_CACHE_DIR, "guidance_index.pkl")

DEFAULT_SUPPLIERS = [
    "Cellnex",
    "KTL",
    "Obelisk",
    "Telent",
    "Waldon",
    "WFS",
    "Syscomm",
    "MJ Quinn",
    "MNO Projects",
    "Wireless Infrastructure Group",
    "Waldon Telecom",
]

DEFAULT_CLIENTS = ["BTEE", "Vodafone", "MBNL", "H3G", "Cornerstone", "Cellnex"]
DEFAULT_PROJECTS = ["RAN", "Power Resilience", "East Unwind", "Beacon 4"]
DEFAULT_SITE_TYPES = ["Greenfield", "Rooftop", "Streetworks"]
DEFAULT_VENDORS = ["Ericsson", "Nokia"]
DEFAULT_CAB_LOC = ["Indoor", "Outdoor"]
DEFAULT_RADIO_LOC = ["Low Level", "High Level", "Unique Coverage", "Midway"]
DEFAULT_SECTORS = [1,2,3,4,5,6]
DEFAULT_MIMO = [
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


def app_password_gate():
    # You can change the passwords in Settings; these are fallbacks
    cfg = st.session_state.get("cfg", {})
    entry_pw = cfg.get("entry_password", "Seker123")  # as requested earlier
    st.session_state.setdefault("authed", False)
    if st.session_state["authed"]:
        return True

    st.title(APP_TITLE)
    pw = st.text_input("Enter access password", type="password")
    if st.button("Enter"):
        if pw == entry_pw:
            st.session_state["authed"] = True
            st.success("Welcome.")
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()


def load_or_init_cfg():
    cfg_path = Path("config.yaml")
    if cfg_path.exists():
        try:
            import yaml
            with cfg_path.open("r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}
    return {}


def save_cfg(cfg: dict):
    import yaml
    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)


def ensure_dirs():
    Path(GUIDANCE_CACHE_DIR).mkdir(exist_ok=True)


def set_page():
    st.set_page_config(page_title=APP_TITLE, layout="wide")


def topbar():
    cols = st.columns([1,6,1])
    with cols[0]:
        logo_path = Path("logo.png")
        if logo_path.exists():
            st.image(str(logo_path), use_container_width=True)
    with cols[1]:
        st.markdown(f"### {APP_TITLE}")
    with cols[2]:
        st.markdown("")


def guidance_tab():
    st.subheader("Guidance (Mandatory)")

    idx_loaded = st.session_state.get("guidance_index") is not None
    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("**Option A — Upload guidance ZIP (recommended, works on Cloud):**")
        zip_file = st.file_uploader("Upload a .zip containing DOCX/PPTX/PDF/TXT guidance", type=["zip"], key="zip_up")
        if st.button("Build index from ZIP", type="primary", disabled=zip_file is None):
            try:
                bytes_data = zip_file.read()
                index = build_index_from_zipfile(bytes_data)
                st.session_state["guidance_index"] = index
                save_index(index, INDEX_PKL)
                st.success(f"Indexed {index_stats(index)} from ZIP.")
            except Exception as e:
                st.error(f"Failed to build index from ZIP: {e}")

    with col2:
        st.markdown("**Option B — Scan server folder (local dev only):**")
        p = st.text_input("Server folder path (must be accessible to the server)", st.session_state.get("guidance_path",""))
        scan_btn = st.button("Scan folder")
        if scan_btn:
            try:
                if not p or not os.path.isdir(p):
                    st.error("Path not accessible on the server. If you're on Streamlit Cloud, use the ZIP option.")
                else:
                    index = build_index_from_folder(p)
                    st.session_state["guidance_index"] = index
                    st.session_state["guidance_path"] = p
                    save_index(index, INDEX_PKL)
                    st.success(f"Indexed {index_stats(index)} from folder.")
            except Exception as e:
                st.error(f"Failed to scan folder: {e}")

    if idx_loaded:
        st.info(f"Guidance index is loaded: {index_stats(st.session_state['guidance_index'])}")
        if st.button("Clear loaded index"):
            st.session_state["guidance_index"] = None
            try:
                os.remove(INDEX_PKL)
            except FileNotFoundError:
                pass
            st.success("Cleared index.")
            st.rerun()

    with st.expander("Debug / Reload saved index"):
        if os.path.exists(INDEX_PKL) and st.button("Load saved index.pkl"):
            try:
                st.session_state["guidance_index"] = load_index(INDEX_PKL)
                st.success("Loaded saved index from disk.")
            except Exception as e:
                st.error(f"Load failed: {e}")


def audit_tab():
    st.subheader("Audit")
    # enforce guidance loaded
    if st.session_state.get("guidance_index") is None:
        st.warning("Load guidance first in the Guidance tab (ZIP upload recommended).")
        st.stop()

    # Metadata
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        suppliers = st.session_state.get("suppliers", DEFAULT_SUPPLIERS)
        client = c1.selectbox("Client", DEFAULT_CLIENTS, index=0, key="client")
        project = c2.selectbox("Project", DEFAULT_PROJECTS, index=0, key="project")
        supplier = c3.selectbox("Supplier", suppliers, index=0, key="supplier")
        site_type = c4.selectbox("Site Type", DEFAULT_SITE_TYPES, index=0, key="site_type")

        c5, c6, c7, c8 = st.columns(4)
        vendor = c5.selectbox("Proposed Vendor", DEFAULT_VENDORS, index=0, key="vendor")
        cab_loc = c6.selectbox("Proposed Cabinet Location", DEFAULT_CAB_LOC, index=0, key="cab_loc")
        radio_loc = c7.selectbox("Proposed Radio Location", DEFAULT_RADIO_LOC, index=0, key="radio_loc")
        sectors = c8.selectbox("Quantity of Sectors", DEFAULT_SECTORS, index=2, key="sectors")

        # sector MIMO – replicate if "Use S1 for all"
        st.markdown("##### MIMO Config per Sector")
        s_cols = st.columns(6)
        mimo_vals = {}
        for i in range(6):
            key = f"mimo_s{i+1}"
            disabled = i >= sectors
            mimo_vals[key] = s_cols[i].selectbox(
                f"S{i+1}", DEFAULT_MIMO + ["(blank)"], index=0, key=key, disabled=disabled
            )
        if st.toggle("Use S1 for all active sectors", value=True):
            for i in range(1, sectors):
                st.session_state[f"mimo_s{i+1}"] = st.session_state["mimo_s1"]

        site_address = st.text_input("Site Address (must match PDF title; ignore if contains ', 0 ,')", key="site_address")

    # Upload PDF
    up = st.file_uploader("Upload a design PDF", type=["pdf"], key="pdf_up")
    allow_spell = st.toggle("Enable spelling check", value=True)
    run_btn = st.button("Run Audit", type="primary", disabled=up is None)

    if run_btn and up:
        raw = up.read()
        pages = extract_text_pages(raw)  # list of strings

        # Baseline checks (address match)
        findings = []
        title_text = pages[0][:500].replace("\n", " ") if pages else ""
        addr = site_address.strip()
        if addr and ", 0 ," not in addr:
            if addr.lower() not in title_text.lower():
                findings.append({
                    "severity": "Major",
                    "rule_id": "ADDR_TITLE_MISMATCH",
                    "message": "Site Address does not appear in the PDF title area.",
                    "page": 1,
                    "snippet": title_text[:200],
                    "anchor": addr,
                })

        # Guidance cross-reference: use key phrases assembled from metadata
        key_terms = [client, project, site_type, vendor, radio_loc] + [
            st.session_state[f"mimo_s{i+1}"] for i in range(sectors)
        ]
        g_hits = search_guidance_for_terms(st.session_state["guidance_index"], key_terms)
        # Any explicit rules derived from guidance? We record hits as Info
        for hit in g_hits[:50]:  # cap
            findings.append({
                "severity": "Info",
                "rule_id": "GUIDE_HIT",
                "message": f"Guidance match: {hit['title']} – “{hit['term']}”",
                "page": hit.get("page", None),
                "snippet": hit.get("context","")[:200],
                "anchor": hit.get("term"),
            })

        # Simple spelling check
        if allow_spell:
            try:
                from spellchecker import SpellChecker
                sp = SpellChecker(distance=1)
                for pi, txt in enumerate(pages, start=1):
                    words = re.findall(r"[A-Za-z]{4,}", txt)
                    miss = sp.unknown([w.lower() for w in words])
                    for w in list(miss)[:10]:  # cap per page
                        sug = next(iter(sp.candidates(w)), None)
                        findings.append({
                            "severity": "Minor",
                            "rule_id": "SPELL",
                            "message": f"Possible typo “{w}”" + (f" → {sug}" if sug else ""),
                            "page": pi,
                            "snippet": "",
                            "anchor": w,
                        })
            except Exception as e:
                st.warning(f"Spelling check unavailable: {e}")

        # Determine status
        maj = any(f["severity"] == "Major" for f in findings)
        status = "Rejected" if maj else "Pass" if findings else "Pass"
        now = dt.datetime.utcnow().strftime("%Y-%m-%dT%H_%M_%S")
        base = Path(up.name).stem
        pdf_name = f"{base}_{status}_{now}.pdf"
        xls_name = f"{base}_{status}_{now}.xlsx"

        # Annotate and export
        try:
            annotated = annotate_pdf_with_findings(raw, pages, findings)
        except Exception as e:
            st.warning(f"PDF annotation failed: {e}")
            annotated = raw

        # Excel
        excel_bytes = build_excel(findings, {
            "client": client, "project": project, "supplier": supplier, "site_type": site_type,
            "vendor": vendor, "cab_loc": cab_loc, "radio_loc": radio_loc, "sectors": sectors,
            "site_address": site_address
        }, up.name, status)

        # Buttons (keep visible)
        c1, c2 = st.columns(2)
        c1.download_button("Download Annotated PDF", data=annotated, file_name=pdf_name, mime="application/pdf")
        c2.download_button("Download Excel Report", data=excel_bytes, file_name=xls_name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # Save to history
        save_history({
            "timestamp_utc": dt.datetime.utcnow().isoformat(),
            "client": client, "project": project, "supplier": supplier, "site_type": site_type,
            "vendor": vendor, "cabinet_location": cab_loc, "radio_location": radio_loc,
            "sectors": sectors, "site_address": site_address,
            "status": status, "findings": len(findings),
            "pdf_name": pdf_name, "excel_name": xls_name,
        })

        # Show findings
        st.markdown("#### Findings")
        if findings:
            st.dataframe(pd.DataFrame(findings), use_container_width=True)
        else:
            st.success("No findings.")

def analytics_tab():
    st.subheader("Analytics")
    df = load_history()
    if df.empty:
        st.info("No history yet.")
        return
    # Filters
    c1, c2, c3 = st.columns(3)
    clients = ["(All)"] + sorted([x for x in df["client"].dropna().unique()])
    projects = ["(All)"] + sorted([x for x in df["project"].dropna().unique()])
    suppliers = ["(All)"] + sorted([x for x in df["supplier"].dropna().unique()])
    fc = c1.selectbox("Client", clients, index=0)
    fp = c2.selectbox("Project", projects, index=0)
    fs = c3.selectbox("Supplier", suppliers, index=0)

    show = df.copy()
    if fc != "(All)":
        show = show[show["client"] == fc]
    if fp != "(All)":
        show = show[show["project"] == fp]
    if fs != "(All)":
        show = show[show["supplier"] == fs]

    st.metric("Total Audits", len(show))
    st.metric("Right First Time %", round((show["status"].eq("Pass").mean()*100.0) if not show.empty else 0, 1))

    st.dataframe(show[["timestamp_utc","supplier","client","project","status","pdf_name","excel_name"]], use_container_width=True)

def settings_tab():
    st.subheader("Settings")
    cfg = st.session_state.get("cfg", {})

    with st.expander("Passwords"):
        entry = st.text_input("Entry password", value=cfg.get("entry_password", "Seker123"))
        cfg["entry_password"] = entry

    with st.expander("Suppliers list (one per line)"):
        sup_str = "\n".join(cfg.get("suppliers", DEFAULT_SUPPLIERS))
        new_sup_str = st.text_area("Suppliers", value=sup_str, height=160)
        cfg["suppliers"] = [s.strip() for s in new_sup_str.splitlines() if s.strip()]

    if st.button("Save settings", type="primary"):
        st.session_state["cfg"] = cfg
        save_cfg(cfg)
        st.success("Saved.")

def build_excel(findings, meta, original_name, status):
    import pandas as pd
    from io import BytesIO
    mem = BytesIO()
    with pd.ExcelWriter(mem, engine="xlsxwriter") as xw:
        pd.DataFrame(findings).to_excel(xw, index=False, sheet_name="Findings")
        pd.DataFrame([meta]).assign(original_file=original_name, status=status)\
            .to_excel(xw, index=False, sheet_name="Meta")
    mem.seek(0)
    return mem.getvalue()

def save_history(row: dict):
    try:
        if os.path.exists(HISTORY_CSV):
            df = pd.read_csv(HISTORY_CSV)
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        else:
            df = pd.DataFrame([row])
        df.to_csv(HISTORY_CSV, index=False)
    except Exception as e:
        st.warning(f"Could not write history: {e}")

def load_history() -> pd.DataFrame:
    try:
        if os.path.exists(HISTORY_CSV):
            return pd.read_csv(HISTORY_CSV)
    except Exception:
        pass
    return pd.DataFrame()

# ---------------- Main ----------------

def main():
    set_page()
    ensure_dirs()
    st.session_state.setdefault("cfg", load_or_init_cfg())
    topbar()
    app_password_gate()

    tabs = st.tabs(["Audit", "Guidance", "Analytics", "Settings"])
    with tabs[1]:
        guidance_tab()
    with tabs[0]:
        audit_tab()
    with tabs[2]:
        analytics_tab()
    with tabs[3]:
        settings_tab()

if __name__ == "__main__":
    main()
