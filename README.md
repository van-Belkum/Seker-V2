# Seker V2 — AI Design Quality Auditor (Guidance-driven)

**Quick start**
1. `pip install -r requirements.txt`
2. `streamlit run app.py`
3. Go to **Guidance** → upload a ZIP containing DOCX/PPTX/PDF design guidance.
4. Go to **Audit** → upload a site PDF, fill metadata, Run Audit.
5. Validate findings (Accept/Reject) → Save to training log; Download Excel & Annotated PDF.

**Passwords**
- Entry: `Seker123`
- Settings/Rules: `vanB3lkum21`

**What it does**
- Ingests guidance (DOCX/PPTX/PDF) and extracts candidate rules (lines with *MUST/SHALL/REQUIRED/NOTE*).
- Runs fuzzy checks on uploaded drawings against extracted rules + your accepted training rules.
- Annotates PDFs with comments at matched text (fallback to cover page note when no box found).
- Saves training decisions per-scope (Client/Project/Supplier/SiteType/Vendor/MIMO).
