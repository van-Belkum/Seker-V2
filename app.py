from pathlib import Path
import pandas as pd
import streamlit as st
import yaml
from modules.auth import is_admin, get_settings
from modules.ingest import index_folder, save_uploads
from modules.doc_rules import load_ruleset, run_doc_checks
from modules.pdf_annotate import render_page_image, annotate_points
from streamlit_drawable_canvas import st_canvas
import io

st.set_page_config(page_title="Seker V2.3 — Guidance Auditor", layout="wide", page_icon="🛰️")

with st.sidebar:
    st.image("assets/logo.png", width=120)
    st.markdown("### Seker V2.3")
    token = st.text_input("Admin Passphrase", type="password")
    role = "Admit" if is_admin(token) else "Viewer"
    st.caption(f"Role: {role}")

tabs = st.tabs(["Audit (Docs)", "Annotate PDF", "Guidance Library", "Settings"])

settings = get_settings()
ruleset = load_ruleset()
privacy_hide = settings.get("privacy", {}).get("hide_guidance_for_non_admin", True)
g_root = Path(settings.get("guidance", {}).get("root_path","guidance"))
index_file = Path(settings.get("guidance", {}).get("index_file","guidance_index.csv"))
g_root.mkdir(parents=True, exist_ok=True)

# --- AUDIT DOCS
with tabs[0]:
    st.header("Audit Guidance / Design Documents")
    colA, colB = st.columns(2)

    with colA:
        st.subheader("From Library")
        if (not privacy_hide) or is_admin(token):
            if index_file.exists():
                idx = pd.read_csv(index_file)
                st.dataframe(idx[["series","key","version","file","active"]], use_container_width=True, height=260)
                pick = st.selectbox("Choose a document to audit", [""] + idx.loc[idx["active"]==True, "file"].tolist())
                if st.button("Run Audit on Selected") and pick:
                    path = g_root / pick
                    df = run_doc_checks(path, ruleset)
                    st.success(f"Audit complete: {len(df)} finding(s).")
                    st.dataframe(df, use_container_width=True)
                    out = Path("reports") / f"doc_audit_{Path(pick).stem}.xlsx"
                    with pd.ExcelWriter(out, engine="openpyxl") as w:
                        df.to_excel(w, index=False, sheet_name="Findings")
                    with open(out, "rb") as f:
                        st.download_button("Download Findings (Excel)", data=f, file_name=out.name)
            else:
                st.info("Index not built yet. Go to Guidance Library to index.")
        else:
            st.info("Guidance library is hidden for non-admin users.")

    with colB:
        st.subheader("Ad-hoc Upload")
        up = st.file_uploader("Upload a DOCX or PDF to audit", type=["docx","pdf"])
        if st.button("Run Audit on Upload", disabled=up is None):
            p = Path("reports") / up.name
            p.write_bytes(up.read())
            df = run_doc_checks(p, ruleset)
            st.success(f"Audit complete: {len(df)} finding(s).")
            st.dataframe(df, use_container_width=True)
            out = Path("reports") / f"doc_audit_{p.stem}.xlsx"
            with pd.ExcelWriter(out, engine="openpyxl") as w:
                df.to_excel(w, index=False, sheet_name="Findings")
            with open(out, "rb") as f:
                st.download_button("Download Findings (Excel)", data=f, file_name=out.name)

# --- ANNOTATE PDF (click-to-pin)
with tabs[1]:
    st.header("Annotate PDF (Click to Pin)")
    pdf = st.file_uploader("Upload a PDF to annotate", type=["pdf"])
    if pdf:
        temp_pdf = Path("reports") / pdf.name
        temp_pdf.write_bytes(pdf.read())
        from pymupdf import fitz  # ensure installed

        import fitz as _fitz  # alias to use methods
        doc = _fitz.open(str(temp_pdf))
        num_pages = len(doc)
        page_num = st.number_input("Page", min_value=1, max_value=num_pages, value=1, step=1)
        doc.close()

        img_bytes = render_page_image(temp_pdf, page_num, zoom=2.0)
        st.caption("Click to drop pins. Add a short note for the next pin, then click on the canvas.")
        note_text = st.text_input("Note for next pin", value="Issue")
        canvas_result = st_canvas(
            fill_color="rgba(255, 0, 0, 0.3)",
            stroke_width=2,
            background_image=Image.open(io.BytesIO(img_bytes)),
            height=None,
            drawing_mode="point",
            key="canvas"
        )
        pins = []
        if canvas_result.json_data is not None:
            for obj in canvas_result.json_data["objects"]:
                if obj.get("type") == "circle":
                    # st_canvas returns center x/y
                    x = float(obj.get("left", 0)) + float(obj.get("radius", 0))
                    y = float(obj.get("top", 0)) + float(obj.get("radius", 0))
                    pins.append({"page": page_num, "x": x/2.0, "y": y/2.0, "note": note_text})  # divide by zoom

        if st.button("Apply Annotations", disabled=len(pins)==0):
            outp = Path("reports") / f"annotated_{temp_pdf.stem}.pdf"
            annotate_points(temp_pdf, outp, pins)
            with open(outp, "rb") as f:
                st.download_button("Download Annotated PDF", data=f, file_name=outp.name, mime="application/pdf")

# --- GUIDANCE LIBRARY (Admin only)
with tabs[2]:
    st.header("Guidance Library")
    if not is_admin(token):
        st.warning("Admin only. Guidance listing and management are hidden.")
    else:
        st.code(f"Root: {g_root.resolve()}\nIndex: {index_file.resolve()}")
        st.subheader("Upload new guidance")
        files = st.file_uploader("Upload DOCX/PDF (multiple)", type=["docx","pdf"], accept_multiple_files=True)
        colx, coly, colz = st.columns(3)
        with colx:
            overwrite = st.checkbox("Overwrite files with same name", value=False, help="If checked, replace existing files with same filename.")
        with coly:
            supersede = st.checkbox("Supersede older versions by key", value=True, help="Keep only highest version active per key.")
        with colz:
            mode = st.selectbox("Index mode", ["append","overwrite"], index=0)
        if st.button("Save & Index"):
            saved = []
            if files:
                from modules.ingest import save_uploads
                saved = save_uploads(files, g_root, overwrite_same_name=overwrite)
            out = index_folder(g_root, index_file, mode=mode, supersede=supersede)
            st.success(f"Saved {len(saved)} file(s). Indexed → {out}")
        if index_file.exists():
            idx = pd.read_csv(index_file)
            st.metric("Docs", len(idx))
            st.dataframe(idx.sort_values(["series","key","version","active"], ascending=[True,True,False,False]), use_container_width=True, height=300)

# --- SETTINGS
with tabs[3]:
    st.header("Settings")
    st.write("Ruleset YAML (left), App settings (right).")
    col1, col2 = st.columns(2)
    with col1:
        rs = load_ruleset()
        rs_yaml = yaml.safe_dump(rs, sort_keys=False, allow_unicode=True)
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
