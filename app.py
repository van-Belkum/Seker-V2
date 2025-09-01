# v3_app.py — V1-style UI + AI guidance digester (keeps your V1 app separate)
from pathlib import Path
import pandas as pd
import streamlit as st
import yaml
from PIL import Image
import io
from streamlit_drawable_canvas import st_canvas

# local modules (you’ll add them in step 2)
from modules.auth import is_admin, get_settings
from modules.ingest import index_folder
from modules.doc_rules import load_ruleset, run_doc_checks
from modules.pdf_annotate import render_page_image, annotate_points, annotate_text_matches
from modules.rule_mining import mine_rules_from_file
from modules.analytics import load_history
from modules.utils import save_history_row

st.set_page_config(page_title="Seker V3 — V1 + AI Guidance", layout="wide", page_icon="🛰️")

with st.sidebar:
    st.image("assets/logo.png", width=120)
    st.markdown("### Seker V3")
    token = st.text_input("Admin Passphrase", type="password")
    st.caption("Role: " + ("Admit" if is_admin(token) else "Viewer"))

tabs = st.tabs(["Audit", "Train (Admin)", "Analytics", "Settings"])

settings = get_settings()
ruleset = load_ruleset()
g_root = Path(settings.get("guidance",{}).get("root_path","guidance"))
index_file = Path(settings.get("guidance",{}).get("index_file","guidance_index.csv"))
privacy_hide = settings.get("privacy",{}).get("hide_guidance_for_non_admin", True)

# -------- Audit
with tabs[0]:
    st.header("Audit")
    sub = st.tabs(["Design (PDF)", "Documents (DOCX/PDF)"])

    # Design
    with sub[0]:
        ui = settings.get("ui",{})
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            supplier = st.selectbox("Supplier", ui.get("suppliers",[]))
            client   = st.selectbox("Client", ui.get("clients",[]))
        with col2:
            project  = st.selectbox("Project", ui.get("projects",[]))
            site_type= st.selectbox("Site Type", ui.get("site_types",[]))
        with col3:
            vendor   = st.selectbox("Vendor", ui.get("vendors",[]))
            cab_loc  = st.selectbox("Cabinet Location", ui.get("cabinet_locations",[]))
        with col4:
            radio_loc= st.selectbox("Radio Location", ui.get("radio_locations",[]))
            sectors  = st.selectbox("Sectors", [1,2,3,4], index=2)

        st.markdown("**MIMO per sector**")
        mimo_opts = ui.get("mimo_options",["2x2","4x4"])
        hide_mimo_for = settings.get("logic",{}).get("hide_mimo_if_project_equals","Power Resilience")
        if project != hide_mimo_for:
            use_all = st.checkbox("Use S1 for all sectors", value=True)
            s1 = st.selectbox("S1", mimo_opts, index=min(1, len(mimo_opts)-1))
            mimo = {"S1": s1}
            for s in ["S2","S3","S4"]:
                mimo[s] = s1 if use_all else st.selectbox(s, mimo_opts, index=min(1, len(mimo_opts)-1))
        else:
            st.info(f"MIMO selections hidden for project '{hide_mimo_for}'.")

        st.divider()
        site_address = st.text_input("Site Address * (', 0 ,' ignored in title check)")
        drawing_title= st.text_input("Drawing Title *")
        design_pdf   = st.file_uploader("Design PDF (for auto markers & annotation)", type=["pdf"])
        exclude_analytics = st.checkbox("Exclude this run from analytics", value=False)
        if st.button("Run Design Audit"):
            if not site_address or not drawing_title:
                st.error("Please fill Site Address and Drawing Title.")
            else:
                # simple address-in-title check
                clean = lambda s: (s or "").replace(", 0 ,", ",").strip().lower()
                errs = []
                if clean(site_address) not in clean(drawing_title):
                    errs.append({"Category":"Metadata","Code":"ADDR_TITLE_MATCH","Description":"Address must appear in title (ignoring ', 0 ,')","Status":"Rejected"})
                # auto-annotate markers
                if design_pdf is not None:
                    p = Path("reports")/design_pdf.name; p.write_bytes(design_pdf.read())
                    matches = []
                    for r in ruleset.get("rules", []):
                        if r.get("type")=="pdf_text_presence":
                            for t in r.get("options",{}).get("any",[]):
                                matches.append({"page":1,"text":t,"note":f"{r.get('id')}: {t}"})
                    if matches:
                        outp = Path("reports")/f"annotated_{p.stem}.pdf"
                        annotate_text_matches(p, outp, matches)
                        with open(outp,"rb") as f:
                            st.download_button("Download Auto-Annotated PDF", data=f, file_name=outp.name, mime="application/pdf")
                st.success("Design audit completed.")
                if errs: st.dataframe(pd.DataFrame(errs), use_container_width=True)
                # save history
                payload = {"Project": project, "Client": client, "Supplier": supplier, "Vendor": vendor,
                           "Site Address": site_address, "Drawing Title": drawing_title,
                           "Errors": len(errs), "Status": "Rejected" if errs else "Accepted"}
                hp = save_history_row(payload, exclude=exclude_analytics)
                st.caption(f"Saved → {hp.name}")

        st.subheader("Manual click-to-pin")
        pdf2 = st.file_uploader("Upload PDF to annotate", type=["pdf"], key="pdf2")
        if pdf2:
            p2 = Path("reports")/pdf2.name; p2.write_bytes(pdf2.read())
            import fitz; d = fitz.open(str(p2)); n = len(d); d.close()
            page = st.number_input("Page", min_value=1, max_value=n, value=1, step=1)
            img = render_page_image(p2, page, zoom=2.0)
            note = st.text_input("Note", value="Issue")
            canvas = st_canvas(background_image=Image.open(io.BytesIO(img)), drawing_mode="point", stroke_width=2, key="manual_canvas")
            pins = []
            if canvas.json_data is not None:
                for obj in canvas.json_data["objects"]:
                    if obj.get("type")=="circle":
                        x = float(obj.get("left",0)) + float(obj.get("radius",0))
                        y = float(obj.get("top",0)) + float(obj.get("radius",0))
                        pins.append({"page": page, "x": x/2.0, "y": y/2.0, "note": note})
            if st.button("Apply Pins", disabled=len(pins)==0):
                outp = Path("reports")/f"manual_{p2.stem}.pdf"
                annotate_points(p2, outp, pins)
                with open(outp,"rb") as f:
                    st.download_button("Download Annotated", data=f, file_name=outp.name, mime="application/pdf")

    # Documents (guidance or uploads)
    with sub[1]:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**From Guidance Library (Admin)**")
            if (not privacy_hide) or is_admin(token):
                if index_file.exists():
                    idx = pd.read_csv(index_file)
                    st.dataframe(idx[["series","key","version","file","active"]], use_container_width=True, height=240)
                    pick = st.selectbox("Choose document", [""] + idx.loc[idx["active"]==True,"file"].tolist())
                    if st.button("Run Audit (Selected)") and pick:
                        dp = g_root / pick
                        out = run_doc_checks(dp, ruleset)
                        st.success(f"Audit complete: {len(out)} finding(s).")
                        st.dataframe(out, use_container_width=True)
                        x = Path("reports")/f"doc_audit_{dp.stem}.xlsx"
                        with pd.ExcelWriter(x, engine="openpyxl") as w: out.to_excel(w, index=False)
                        with open(x, "rb") as f: st.download_button("Download Findings (Excel)", data=f, file_name=x.name)
                else:
                    st.info("No index yet. Use Train → Save & Index.")
            else:
                st.info("Guidance hidden for non-admins.")
        with col2:
            st.markdown("**Ad-hoc Upload**")
            up = st.file_uploader("Upload DOCX or PDF", type=["docx","pdf"])
            if st.button("Run Audit (Upload)", disabled=up is None):
                p = Path("reports")/up.name; p.write_bytes(up.read())
                out = run_doc_checks(p, ruleset)
                st.success(f"Audit complete: {len(out)} finding(s).")
                st.dataframe(out, use_container_width=True)
                x = Path("reports")/f"doc_audit_{p.stem}.xlsx"
                with pd.ExcelWriter(x, engine="openpyxl") as w: out.to_excel(w, index=False)
                with open(x, "rb") as f: st.download_button("Download Findings (Excel)", data=f, file_name=x.name)

# -------- Train (Admin)
with tabs[1]:
    st.header("Train (Admin)")
    if not is_admin(token):
        st.warning("Enter admin passphrase to unlock this tab.")
    else:
        st.subheader("Guidance Upload & Index")
        files = st.file_uploader("Upload DOCX/PDF (multiple)", type=["docx","pdf"], accept_multiple_files=True)
        c1, c2, c3 = st.columns(3)
        with c1: overwrite = st.checkbox("Overwrite same filename", value=False)
        with c2: supersede = st.checkbox("Supersede older versions by key", value=True)
        with c3: mode = st.selectbox("Index mode", ["append","overwrite"], index=0)
        if st.button("Save & Index"):
            g_root.mkdir(parents=True, exist_ok=True)
            saved = 0
            for f in files or []:
                dest = g_root / f.name
                if dest.exists() and not overwrite:
                    dest = g_root / f"__{int(Path().stat().st_mtime)}__{f.name}"
                dest.write_bytes(f.read()); saved += 1
            out = index_folder(g_root, index_file, mode=mode, supersede=supersede)
            st.success(f"Saved {saved} file(s). Indexed → {out}")

        st.divider()
        st.subheader("AI Rule Miner (from guidance)")
        if index_file.exists():
            idx = pd.read_csv(index_file)
            pick = st.selectbox("Pick a guidance file", [""] + idx["file"].tolist())
            if pick:
                path = g_root / pick
                mined = mine_rules_from_file(path, max_items=100)
                if mined.empty:
                    st.info("No strong 'shall/must/required/shall not/ensure' sentences found.")
                else:
                    st.dataframe(mined[["id","severity","description","source"]], use_container_width=True, height=260)
                    if st.button("Append top 20 to ruleset"):
                        rs = load_ruleset()
                        for _, r in mined.head(20).iterrows():
                            rs.setdefault("rules", []).append({
                                "id": r["id"], "type": r["type"], "severity": r["severity"],
                                "description": r["description"],
                                "options": {"any": [r["options"]["any"][0]], "any_regex": [r["options"]["any_regex"][0]]}
                            })
                        with open("rulesets/default_rules.yaml","w",encoding="utf-8") as f:
                            yaml.safe_dump(rs, f, sort_keys=False, allow_unicode=True)
                        st.success("Appended. Review in Settings.")

# -------- Analytics
with tabs[2]:
    st.header("Analytics")
    dfh = load_history(Path("history"))
    if dfh.empty:
        st.info("No audit history yet.")
    else:
        st.dataframe(dfh.tail(200), use_container_width=True)

# -------- Settings
with tabs[3]:
    st.header("Settings")
    col1, col2 = st.columns(2)
    with col1:
        rs_yaml = yaml.safe_dump(ruleset, sort_keys=False, allow_unicode=True)
        new_yaml = st.text_area("Ruleset YAML", value=rs_yaml, height=360)
        if st.button("Save Ruleset"):
            try:
                obj = yaml.safe_load(new_yaml)
                with open("rulesets/default_rules.yaml","w",encoding="utf-8") as f:
                    yaml.safe_dump(obj, f, sort_keys=False, allow_unicode=True)
                st.success("Ruleset saved.")
            except Exception as e:
                st.error(f"YAML error: {e}")
    with col2:
        st.json(get_settings())
