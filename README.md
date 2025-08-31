# Seker-V2 — AI Design Auditor (ZIP guidance)

## Setup
```bash
pip install -r requirements.txt
streamlit run app.py
```

## How Guidance Works
- Go to the **Guidance** tab.
- **Upload a ZIP** containing your DOCX, PPTX, PDF and TXT guidance files.
- Click **Build index from ZIP** (mandatory before audits).
- The index is saved to `.guidance_cache/guidance_index.pkl` so you don't need to re-upload every time on the same machine.

## Audit
- Fill in metadata (client, project, supplier, etc.).
- Upload a **design PDF**.
- Click **Run Audit**. You'll get:
  - Annotated PDF (notes near matches or first page fallback).
  - Excel report of findings and metadata.
  - History entry that feeds **Analytics**.

## Settings
- Change entry password.
- Edit the suppliers list (one per line). Save to persist in `config.yaml`.
