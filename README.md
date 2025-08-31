# Seker V2 — AI Design Quality Auditor (Starter)

**What’s inside**
- `app.py`: Streamlit app with Audit / Guidance / Analytics / Settings.
- `utils/`:
  - `guidance_loader.py` — loads DOCX/PPTX/PDF/TXT from your local guidance folder.
  - `rules_engine.py` — core checks (easy to extend).
  - `pdf_utils.py` — adds page notes to PDFs.
  - `storage.py` — persists history in `data/history.csv`.
- `config.yaml` — edit paths, dropdowns (edit Suppliers here or in Settings).
- `requirements.txt`

**First run**
1. Put `logo.png` next to `app.py` (optional).
2. Edit `config.yaml` and set your guidance root (use single quotes or forward slashes on Windows).
3. Install requirements: `pip install -r requirements.txt`
4. Run: `streamlit run app.py`
5. Go to **Guidance** tab → “Scan guidance now” (mandatory before audits if enabled).

**Suppliers**
Editable in **Settings** (saved to `config.yaml`).

**Passwords**
- Entry: `Seker123`
- Rules (reserved): `vanB3lkum21`
