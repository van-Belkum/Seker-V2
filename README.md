# Seker V2 – AI Design Quality Auditor

## Quick Start
```bash
pip install -r requirements.txt
streamlit run app_v2.py
```

### Passwords
- Entry (all users): `Seker123`
- Admin (guidance/rules): `vanB3lkum21`

## Flow
1. **Admin > Upload Guidance**: upload DOCX/PPTX/PDF, choose client/project/site types. The app stores the file privately and auto-parses it into rules, updating `rules/mapping.yaml`.
2. **Audit**: select metadata (supplier is analytics only), upload one design PDF, Run Audit.
3. **Download**: get annotated PDF with comments at the error location + Excel report.
4. **Train**:
   - Per finding: mark **Valid / Not Valid**, optionally add a new rule sentence (e.g., “X must equal Y per TDEE43001 §3.8.1”). Click **Apply Training Updates**.
   - Or **Training** page: upload a reviewed Excel with columns `verdict` and optional `rule_update`.
5. **Analytics**: 2-week view with filters, RFT%, pass/fail counts. Reviews marked “exclude” are hidden from analytics.

## Rule Structure
See `rules/schema.yaml`. The parser creates simple rules from guidance; refine in `rules/custom.yaml` via Training.
