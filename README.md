
# Seker V2 — AI Design Quality Auditor

## How to run
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Configure local Guidance
- Put all guidance inside your local folder (default):
  `C:\Mac\Home\Music\Guidance`
  - `BTEE/` contains PDFs, DOCX, PPTX
  - `Nemesis/` contains `KTL_Site_Nemesis_Data_*.xlsx` (latest file used)

- Or set environment variable before launching:
  ```bash
  set GUIDANCE_ROOT=C:\Mac\Home\Music\Guidance
  ```

## Passwords
- Entry: `Seker123`
- Rules edit: `vanB3lkum21`

## What it does
- Extracts PDF text
- Runs YAML checklist and AI guidance policies
- Annotates PDF with rectangles + sticky notes at exact matches
- Saves Excel + annotated PDF to `history/files/`
- Analytics with filters + exclude flag
- Training tab to ingest audited reports and append quick rules
