from pathlib import Path
import os, yaml, io
import pandas as pd
import streamlit as st
from PIL import Image
from streamlit_drawable_canvas import st_canvas

from modules.auth import is_admin, get_settings
from modules.utils import save_history_row
from modules.ingest import ensure_guidance_from_zip, index_folder
from modules.doc_rules import load_ruleset, run_doc_checks
from modules.pdf_annotate import render_page_image, annotate_points, annotate_text_matches
from modules.rule_mining import mine_rules_from_file
from modules.analytics import load_history

st.set_page_config(page_title="AI Design Auditor V3", layout="wide", page_icon="🛰️")

# Sidebar
with st.sidebar:
    st.image("assets/logo.png", width=120)
    st.markdown("### AI Design Auditor — V3")
    token = st.text_input("Admin Passphrase", type="password")
    st.caption("Role: " + ("Admit" if is_admin(token) else "Viewer"))

tabs = st.tabs(["Audit", "Train (Admin)", "Analytics", "Settings"])

settings = get_settings()
ruleset = load_ruleset()
g_root = Path(settings.get("guidance",{}).get("root_path","guidance"))
index_file = Path(settings.get("guidance",{}).get("index_file","guidance_index.csv"))
privacy_hide = settings.get("privacy",{}).get("hide_guidance_for_non_admin", True)

# Auto-ingest guidance ZIP if present
zip_path = g_root / "Guidance.zip"
if zip_path.exists():
    ensure_guidance_from_zip(zip_path, g_root)
    # build index on start if not exists
    if not index_file.exists():
        index_folder(g_root, index_file, mode="overwrite", supersede=True)

# -------------- AUDIT --------------
with tabs[0]:
    st.header("Audit")
    sub = st.tabs(["Design (PDF)", "Documents (DOCX/PDF)"])

    # Design
    with sub[0]:
        st.subheader("Design Audit")
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
            s1 = st.selectbox("S1", mimo_opts, index=min(1,len(mimo_opts)-1))
            mimo = {"S1": s1}
            for s in ["S2","S3","S4"]:
                mimo[s] = s1 if use_all else st.selectbox(s, mimo_opts, index=min(1,len(mimo_opts)-1))
        else:
            st.info(f"MIMO selections hidden for project '{hide_mimo_for}'.")

        st.divider()
        site_address = st.text_input("Site Address * (', 0 ,' ignored in title check)")
        drawing_title= st.text_input("Drawing Title *")

        design_pdf   = st.file_uploader("Design PDF", type=["pdf"])
        auto_annot = st.checkbox("Auto-annotate rule markers", value=True)
        exclude_analytics = st.checkbox("Exclude this run from analytics", value=False)
        run = st.button("Run Design Audit", disabled=design_pdf is None)

        if run and design_pdf:
            p = Path("reports")/design_pdf.name
            p.write_bytes(design_pdf.read())

            # Construct findings: look for every 'pdf_text_presence' rule
            matches = []
            rejections = []
            for r in ruleset.get("rules", []):
                if r.get("type")!="pdf_text_presence": continue
                for t in r.get("options",{}).get("any",[]):
                    matches.append({"page":1,"text":t,"note":f"{r.get('id')}: {t}"})
                    # For now, we check existence by adding an annotation pass;
                    # Missing items will get a [Missing] note in the output PDF
                    # And we also record a rejection row for admin validation
                    rejections.append({
                        "RuleID": r.get("id"),
                        "Description": r.get("description",""),
                        "Anchor": t,
                        "Severity": r.get("severity","minor"),
                        "Decision": "",  # admin will mark
                        "Source": "pdf_text_presence"
                    })

            out_annot = None
            if auto_annot and matches:
                out_annot = Path("reports")/f"annotated_{p.stem}.pdf"
                annotate_text_matches(p, out_annot, matches)
                with open(out_annot, "rb") as f:
                    st.download_button("Download Auto-Annotated PDF", data=f, file_name=out_annot.name, mime="application/pdf")

            st.success("Design audit completed. Review rejections below (admin can confirm).")
            rej_df = pd.DataFrame(rejections).drop_duplicates(subset=["RuleID","Anchor"])
            st.dataframe(rej_df, use_container_width=True)

            if is_admin(token) and not rej_df.empty:
                st.markdown("#### Admin: Confirm rejections as new rules")
                to_add = st.multiselect("Select rows to mark as Valid (will be appended to guidance_mined.yaml)",
                                        rej_df.index.tolist(), format_func=lambda i: f"{rej_df.loc[i,'RuleID']} — {rej_df.loc[i,'Anchor']}")
                if st.button("Append selected to ruleset", disabled=len(to_add)==0):
                    with open("rulesets/guidance_mined.yaml","r",encoding="utf-8") as f:
                        y = yaml.safe_load(f) or {"rules":[]}
                    for i in to_add:
                        r = rej_df.loc[i]
                        y.setdefault("rules", []).append({
                            "id": f"AUTO_{r['RuleID']}_{abs(hash(r['Anchor']))%10**6}",
                            "type": "pdf_text_presence",
                            "severity": r["Severity"],
                            "description": r["Description"] or f"Presence of '{r['Anchor']}' in design PDF.",
                            "options": {"any": [r["Anchor"]]},
                            "context": {"project": project, "site_type": site_type, "vendor": vendor, "radio": radio_loc}
                        })
                    with open("rulesets/guidance_mined.yaml","w",encoding="utf-8") as f:
                        yaml.safe_dump(y, f, sort_keys=False, allow_unicode=True)
                    st.success("Appended. Rerun audit to apply.")

            # history
            payload = {"Project": project, "Client": client, "Supplier": supplier, "Vendor": vendor,
                       "Site Address": site_address, "Drawing Title": drawing_title,
                       "Design File": design_pdf.name, "Status": "Completed"}
            save_history_row(payload, exclude=exclude_analytics)

        st.divider()
        st.subheader("Manual click-to-pin")
        pdf2 = st.file_uploader("Upload PDF to annotate", type=["pdf"], key="pdf2")
        if pdf2:
            temp_pdf = Path("reports")/pdf2.name
            temp_pdf.write_bytes(pdf2.read())
            import fitz
            d = fitz.open(str(temp_pdf)); n = len(d); d.close()
            page = st.number_input("Page", min_value=1, max_value=n, value=1, step=1)
            img = render_page_image(temp_pdf, page, zoom=2.0)
            note = st.text_input("Note", value="Issue")
            canvas = st_canvas(background_image=Image.open(io.BytesIO(img)), drawing_mode="point", stroke_width=2, key="canvas_pdf")
            pins = []
            if canvas.json_data is not None:
                for obj in canvas.json_data["objects"]:
                    if obj.get("type")=="circle":
                        x = float(obj.get("left",0)) + float(obj.get("radius",0))
                        y = float(obj.get("top",0)) + float(obj.get("radius",0))
                        pins.append({"page": page, "x": x/2.0, "y": y/2.0, "note": note})
            if st.button("Apply Pins", disabled=len(pins)==0):
                outp = Path("reports")/f"manual_{temp_pdf.stem}.pdf"
                annotate_points(temp_pdf, outp, pins)
                with open(outp, "rb") as f:
                    st.download_button("Download Annotated", data=f, file_name=outp.name, mime="application/pdf")

    # Document audit
    with sub[1]:
        st.subheader("Guidance/Document Audit")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**From Guidance Library (Admin)**")
            if (not privacy_hide) or is_admin(token):
                if index_file.exists():
                    idx = pd.read_csv(index_file)
                    st.dataframe(idx[["series","key","version","file","active"]], use_container_width=True, height=240)
                    pick = st.selectbox("Choose document", [""] + idx.loc[idx["active"]==True,"file"].tolist())
                    if st.button("Run Audit (Selected)") and pick:
                        p = g_root / pick
                        df = run_doc_checks(p, ruleset)
                        st.success(f"Audit complete: {len(df)} finding(s).")
                        st.dataframe(df, use_container_width=True)
                        out = Path("reports") / f"doc_audit_{Path(pick).stem}.xlsx"
                        with pd.ExcelWriter(out, engine="openpyxl") as w: df.to_excel(w, index=False, sheet_name="Findings")
                        with open(out, "rb") as f: st.download_button("Download Findings (Excel)", data=f, file_name=out.name)
                else:
                    st.info("Index not built. Use Train → Guidance to index.")
            else:
                st.info("Guidance hidden for non-admins.")
        with col2:
            st.markdown("**Ad-hoc Upload**")
            up = st.file_uploader("Upload DOCX/PDF", type=["docx","pdf"])
            if st.button("Run Audit (Upload)", disabled=up is None):
                p = Path("reports") / up.name; p.write_bytes(up.read())
                df = run_doc_checks(p, ruleset)
                st.success(f"Audit complete: {len(df)} finding(s).")
                st.dataframe(df, use_container_width=True)
                out = Path("reports") / f"doc_audit_{p.stem}.xlsx"
                with pd.ExcelWriter(out, engine="openpyxl") as w: df.to_excel(w, index=False, sheet_name="Findings")
                with open(out, "rb") as f: st.download_button("Download Findings (Excel)", data=f, file_name=out.name)

# -------------- TRAIN (ADMIN) --------------
with tabs[1]:
    st.header("Train (Admin) — Guidance & Rule Miner")
    if not is_admin(token):
        st.warning("Enter admin passphrase to unlock this tab.")
    else:
        st.subheader("Guidance ZIP & Index")
        overwrite = st.checkbox("Overwrite index", value=False)
        supersede = st.checkbox("Supersede older versions by key", value=True)
        if st.button("Build/Refresh Index"):
            out = index_folder(g_root, index_file, mode=("overwrite" if overwrite else "append"), supersede=supersede)
            st.success(f"Indexed → {out}")

        st.divider()
        st.subheader("Mine rules from a guidance file")
        if index_file.exists():
            idx = pd.read_csv(index_file)
            pick = st.selectbox("Pick a guidance file", [""] + idx["file"].tolist())
            if pick:
                path = g_root / pick
                mined = mine_rules_from_file(path, max_items=120)
                if mined.empty:
                    st.info("No strong 'shall/must' statements found.")
                else:
                    st.dataframe(mined[["id","severity","description","source"]], use_container_width=True, height=260)
                    if st.button("Append top 20 to ruleset"):
                        with open("rulesets/guidance_mined.yaml","r",encoding="utf-8") as f:
                            y = yaml.safe_load(f) or {"rules":[]}
                        for _, r in mined.head(20).iterrows():
                            y.setdefault("rules", []).append({
                                "id": r["id"], "type": r["type"], "severity": r["severity"],
                                "description": r["description"],
                                "options": {"any": [r["options"]["any"][0]], "any_regex": [r["options"]["any_regex"][0]]}
                            })
                        with open("rulesets/guidance_mined.yaml","w",encoding="utf-8") as f:
                            yaml.safe_dump(y, f, sort_keys=False, allow_unicode=True)
                        st.success("Appended mined rules.")

# -------------- ANALYTICS --------------
with tabs[2]:
    st.header("Analytics")
    dfh = load_history(Path("history"))
    if dfh.empty:
        st.info("No audit history yet.")
    else:
        st.dataframe(dfh.tail(200), use_container_width=True)

# -------------- SETTINGS --------------
with tabs[3]:
    st.header("Settings")
    col1, col2 = st.columns(2)
    with col1:
        # show merged ruleset yaml for editing
        with open("rulesets/guidance_mined.yaml","r",encoding="utf-8") as f:
            mined = yaml.safe_load(f) or {"rules":[]}
        base_yaml = open("rulesets/default_rules.yaml","r",encoding="utf-8").read()
        mined_yaml = yaml.safe_dump(mined, sort_keys=False, allow_unicode=True)
        st.markdown("**Base Ruleset (read-only here)**")
        st.code(base_yaml, language="yaml")
        st.markdown("**Guidance Mined Rules (editable)**")
        new_yaml = st.text_area("guidance_mined.yaml", value=mined_yaml, height=320)
        if st.button("Save guidance_mined.yaml"):
            try:
                obj = yaml.safe_load(new_yaml)
                with open("rulesets/guidance_mined.yaml","w",encoding="utf-8") as f:
                    yaml.safe_dump(obj, f, sort_keys=False, allow_unicode=True)
                st.success("Saved.")
            except Exception as e:
                st.error(f"YAML error: {e}")
    with col2:
        st.json(settings)
