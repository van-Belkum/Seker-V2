\
import io, os, re, json, yaml
from datetime import datetime, timezone
from typing import List, Dict, Any

import streamlit as st
import pandas as pd

from utils.guidance_loader import GuidanceIndex, build_index_from_folder, search_terms
from utils.pdf_tools import pdf_text_pages, annotate_pdf_with_comments
from utils.rules_engine import load_yaml, save_yaml, merge_rules, run_rule_engine, context_key
from utils.history import save_history_row, load_history, save_feedback

CONFIG_PATH = "config.yaml"
RULES_BASE = os.path.join("rules","base_rules.yaml")
RULES_CUSTOM = os.path.join("rules","custom_rules.yaml")
RULES_LEARNED = os.path.join("rules","learned_allowlist.yaml")

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def ensure_state():
    if "guidance_root" not in st.session_state:
        st.session_state.guidance_root = ""
    if "g_index" not in st.session_state:
        st.session_state.g_index = None
    if "guidance_loaded_at" not in st.session_state:
        st.session_state.guidance_loaded_at = None
    if "meta" not in st.session_state:
        st.session_state.meta = {}
    if "last_findings" not in st.session_state:
        st.session_state.last_findings = None
    if "last_pdf_bytes" not in st.session_state:
        st.session_state.last_pdf_bytes = None

def gate_entry(cfg):
    pw_cfg = (cfg.get("app",{}).get("entry_password") or "").strip()
    if not pw_cfg:
        return True
    if "entry_ok" in st.session_state and st.session_state.entry_ok:
        return True
    st.title(cfg.get("app",{}).get("title","Seker V2"))
    st.warning("Access protected.")
    pw = st.text_input("Enter access password", type="password")
    if st.button("Enter"):
        if pw.strip() == pw_cfg:
            st.session_state.entry_ok = True
            st.rerun()
        else:
            st.error("Wrong password.")
    return False

def settings_tab(cfg):
    st.header("Settings & Guidance")
    root = st.text_input(
        "Guidance root path (required before audits)",
        value=st.session_state.guidance_root,
        placeholder=r"C:\Mac\Home\Music\Guidance",
        help="Folder with BTEE and Nemesis subfolders, etc."
    )
    if st.button("Reload guidance index", type="primary"):
        if not root or not os.path.isdir(root):
            st.error("Valid path required.")
        else:
            idx = build_index_from_folder(root)
            st.session_state.g_index = idx
            st.session_state.guidance_root = root
            st.session_state.guidance_loaded_at = datetime.now(timezone.utc).isoformat()
            st.success(f"Indexed {idx.count} docs.")

    if st.session_state.g_index:
        st.info(f"Guidance loaded: {st.session_state.g_index.count} docs @ {st.session_state.guidance_loaded_at}")

    st.divider()
    st.subheader("Rules editor (YAML) — admin password: vanB3lkum21")
    pw = st.text_input("Admin password", type="password")
    base_txt = open(RULES_BASE,"r",encoding="utf-8").read() if os.path.exists(RULES_BASE) else "policies: []"
    custom_txt = open(RULES_CUSTOM,"r",encoding="utf-8").read() if os.path.exists(RULES_CUSTOM) else "policies: []"
    c1, c2 = st.columns(2)
    with c1:
        new_base = st.text_area("rules/base_rules.yaml", value=base_txt, height=260)
    with c2:
        new_custom = st.text_area("rules/custom_rules.yaml", value=custom_txt, height=260)
    if st.button("Save rules"):
        if pw.strip() != "vanB3lkum21":
            st.error("Wrong password.")
        else:
            save_yaml(RULES_BASE, yaml.safe_load(new_base) or {"policies":[]})
            save_yaml(RULES_CUSTOM, yaml.safe_load(new_custom) or {"policies":[]})
            st.success("Rules saved.")

def _meta_ui(cfg):
    dd = cfg.get("dropdowns", {})
    mimo_opts = cfg.get("mimo_options", [])
    c1,c2,c3,c4 = st.columns(4)
    with c1:
        client = st.selectbox("Client", dd.get("clients",[]))
    with c2:
        project = st.selectbox("Project", dd.get("projects",[]))
    with c3:
        site_type = st.selectbox("Site Type", dd.get("site_types",[]))
    with c4:
        vendor = st.selectbox("Vendor", dd.get("vendors",[]))

    c5,c6,c7,c8 = st.columns(4)
    with c5:
        cabinet = st.selectbox("Cabinet Location", dd.get("cabinet_locations",[]))
    with c6:
        radio = st.selectbox("Radio Location", dd.get("radio_locations",[]))
    with c7:
        sectors = st.selectbox("Qty of Sectors", ["1","2","3","4","5","6"])
    with c8:
        site_address = st.text_input("Site Address")

    # MIMO per sector
    st.write("Proposed MIMO Config")
    apply_all = st.checkbox("Use S1 config for all sectors", value=True, help="If ticked, S1 selection copied to all sectors.")
    s_configs = {}
    for i in range(1, int(sectors)+1):
        lab = f"S{i}"
        if i == 1 or not apply_all:
            s_configs[lab] = st.selectbox(lab, mimo_opts, key=f"mimo_{lab}")
        else:
            s_configs[lab] = s_configs["S1"]

    return {
        "client": client, "project": project, "site_type": site_type, "vendor": vendor,
        "cabinet": cabinet, "radio": radio, "sectors": sectors, "site_address": site_address,
        "mimo": s_configs
    }

def audit_tab(cfg):
    st.header("Audit")
    if not st.session_state.g_index:
        st.warning("Load guidance in Settings before running audits.")
        return

    meta = _meta_ui(cfg)
    st.session_state.meta = meta

    up = st.file_uploader("Upload PDF design", type=["pdf"])
    run = st.button("Run audit", type="primary")

    if up and run:
        raw = up.read()
        pages = pdf_text_pages(raw)

        # Load rules (merged)
        base = load_yaml(RULES_BASE)
        custom = load_yaml(RULES_CUSTOM)
        learned = load_yaml(RULES_LEARNED)
        rules_merged = merge_rules(base, custom)

        findings = run_rule_engine(pages, meta, rules_merged, st.session_state.g_index, learned)

        # Attach guidance evidence where possible
        for f in findings:
            if f.get("type") == "require_any":
                terms = f.get("required_terms", [])
                hits = search_terms(st.session_state.g_index, terms, topk=3)
                if hits:
                    f["guidance_evidence"] = [ {"score": float(s), "doc": d.name} for s,d in hits ]

        status = "Rejected" if findings else "Pass"
        st.session_state.last_findings = findings
        st.session_state.last_pdf_bytes = raw

        st.subheader(f"Results — {status}")
        if findings:
            df = pd.DataFrame(findings)
            st.dataframe(df, use_container_width=True)

            # Live accept / reject
            st.markdown("### Validate findings")
            fb = []
            for i, f in enumerate(findings):
                cols = st.columns([3,2,2])
                with cols[0]:
                    st.write(f"**{f.get('message','Issue')}**")
                with cols[1]:
                    mark = st.selectbox("Mark as", ["Keep","False positive"], key=f"mark_{i}")
                with cols[2]:
                    reason = st.text_input("Reason/Note", key=f"note_{i}")
                fb.append({"finding": f, "mark": mark, "note": reason})

            if st.button("Apply feedback (learn)"):
                # Persist training snapshot
                recs = []
                for r in fb:
                    entry = {
                        "context": meta,
                        "finding": r["finding"],
                        "mark": r["mark"],
                        "note": r["note"]
                    }
                    recs.append(entry)
                fn = save_feedback(recs)
                # Update learned allowlist for spelling and ignore_phrases
                learned = load_yaml(RULES_LEARNED) or {}
                learned.setdefault("context_keys", ["client","project","vendor","site_type"])
                key = context_key(meta, learned["context_keys"])
                learned.setdefault("allow_words", {})
                learned.setdefault("ignore_phrases", {})
                for r in fb:
                    f = r["finding"]
                    if r["mark"] == "False positive":
                        if f.get("type") == "spelling":
                            w = (f.get("evidence_text") or "").lower()
                            if w:
                                learned["allow_words"].setdefault(key, [])
                                if w not in learned["allow_words"][key]:
                                    learned["allow_words"][key].append(w)
                        elif f.get("type") in ("require_any","regex"):
                            phrase = (f.get("evidence_text") or "")
                            if not phrase and f.get("required_terms"):
                                # store the first required term as ignored
                                phrase = f["required_terms"][0]
                            if phrase:
                                learned["ignore_phrases"].setdefault(key, [])
                                if phrase not in learned["ignore_phrases"][key]:
                                    learned["ignore_phrases"][key].append(phrase)
                save_yaml(RULES_LEARNED, learned)
                st.success(f"Feedback saved ({fn}). Future audits will remember spelling and ignored phrases for this context.")

        else:
            st.success("No findings.")

        # Exports stay visible
        st.markdown("### Exports")
        df = pd.DataFrame(findings) if findings else pd.DataFrame(columns=["severity","message","page"])
        mem = io.BytesIO()
        with pd.ExcelWriter(mem, engine="xlsxwriter") as xw:
            df.to_excel(xw, index=False, sheet_name="Findings")
            pd.DataFrame([meta]).to_excel(xw, index=False, sheet_name="Meta")
        excel_bytes = mem.getvalue()
        annot = annotate_pdf_with_comments(raw, df.to_dict("records")) if len(df) else raw
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("Download Excel", excel_bytes, file_name=f"{os.path.splitext(up.name)[0]}_{status}_{datetime.now().strftime('%Y%m%d')}.xlsx")
        with c2:
            st.download_button("Download annotated PDF", annot, file_name=f"{os.path.splitext(up.name)[0]}_{status}_{datetime.now().strftime('%Y%m%d')}.pdf", mime="application/pdf")

        save_history_row({
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "client": meta["client"], "project": meta["project"], "site_type": meta["site_type"], "vendor": meta["vendor"],
            "cabinet": meta["cabinet"], "radio": meta["radio"], "sectors": meta["sectors"],
            "status": status, "pdf_name": up.name, "findings": len(findings)
        })

def analytics_tab():
    st.header("Analytics")
    df = load_history()
    if df.empty:
        st.info("No history yet.")
        return
    with st.expander("Filters", expanded=True):
        c1,c2,c3 = st.columns(3)
        with c1:
            clients = st.multiselect("Client", sorted(df["client"].dropna().unique().tolist()))
        with c2:
            projects = st.multiselect("Project", sorted(df["project"].dropna().unique().tolist()))
        with c3:
            vendors = st.multiselect("Vendor", sorted(df["vendor"].dropna().unique().tolist()))
    mask = pd.Series(True, index=df.index)
    if clients: mask &= df["client"].isin(clients)
    if projects: mask &= df["project"].isin(projects)
    if vendors: mask &= df["vendor"].isin(vendors)
    show = df[mask].copy()
    st.dataframe(show.sort_values("timestamp_utc", ascending=False), use_container_width=True)

def training_tab():
    st.header("Training — Quick Rule Builder")
    st.write("Create a simple policy that requires any of the phrases to be found in the PDF text under a trigger context.")
    with st.form("builder"):
        name = st.text_input("Rule name")
        severity = st.selectbox("Severity", ["minor","major"])
        client = st.text_input("Client filter (optional)")
        project = st.text_input("Project filter (optional)")
        vendor = st.text_input("Vendor filter (optional)")
        phrases = st.text_area("Required phrases (one per line)")
        submitted = st.form_submit_button("Add rule")
    if submitted:
        pol = {
            "name": name or "Custom rule",
            "severity": severity,
            "trigger": {},
            "require_any_pdf_text": [p.strip() for p in phrases.splitlines() if p.strip()]
        }
        if client.strip(): pol["trigger"]["client"] = [client.strip()]
        if project.strip(): pol["trigger"]["project"] = [project.strip()]
        if vendor.strip(): pol["trigger"]["vendor"] = [vendor.strip()]
        custom = load_yaml(RULES_CUSTOM) or {"policies":[]}
        custom["policies"].append(pol)
        save_yaml(RULES_CUSTOM, custom)
        st.success("Rule added to rules/custom_rules.yaml")

def main():
    cfg = load_config()
    st.set_page_config(page_title=cfg.get("app",{}).get("title","Seker V2"), layout="wide")
    ensure_state()
    if not gate_entry(cfg):
        return

    st.title(cfg.get("app",{}).get("title","Seker V2"))
    tab = st.sidebar.radio("Navigation", ["Audit","Training","Analytics","Settings"])

    if tab == "Settings":
        settings_tab(cfg)
    elif tab == "Audit":
        audit_tab(cfg)
    elif tab == "Analytics":
        analytics_tab()
    else:
        training_tab()

if __name__ == "__main__":
    main()
