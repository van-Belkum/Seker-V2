# Seker V2 – AI QA Auditor

A fresh, modular V2 of your design QA tool. It combines rule-based checks, a local RAG over your guidance PDFs, training/learning, and rich analytics.

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py
```

**Passwords**
- Entry: `Seker123`
- Rules Studio / Training edits: `vanB3lkum21`

## Tabs

- **Audit**: Fill metadata, upload a design PDF, run checks. Download findings (Excel) + annotated PDF.
- **Library**: Upload guidance PDFs (TDEE53201 etc.). Click "Rebuild index now".
- **Training**: Upload audited Excel/JSON and label Valid/Not Valid to update allow/forbid lists. Append quick rules.
- **Rule Studio**: Full YAML editor for `rules_v2.yaml` (with password).
- **Analytics**: Filters, RFT %, and exclude control.

## Rules

`rules_v2.yaml` supports:
- `type: keyword` with `must_contain` and/or `forbid` (regex)
- `type: rag` with `trigger` and `require` phrases – missing requirement will cite the best guidance pages.

`scope` can target by client/project/vendor/drawing_type/site_type, etc.

## Guidance RAG

All PDFs in `./library` are indexed per page using TF‑IDF. The app runs locally; no external API is required.

## Exports

- **Excel** (Findings + Metadata) via `xlsxwriter`
- **Annotated PDF** (boxes/sticky notes)

## Persistence

- `./history/audit_history.csv` – runs log (used by Analytics)
- `./history/allowlist.json` and `forbidlist.json` – training artifacts
- `./history/vector_store.pkl` – RAG index