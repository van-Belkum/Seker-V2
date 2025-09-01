# Seker V2 — AI Design Quality Auditor (Starter Package)

A Streamlit app scaffold aligned to your latest spec:
- Tabs: **Audit / Train / Analytics / Settings**
- Logo top-left; professional, simple layout.
- Mandatory metadata before audit.
- Per-sector MIMO dropdowns with **"Use S1 for all"** and hidden MIMO when **Project = Power Resilience**.
- Address–title rule ignores the literal sequence `, 0 ,`.
- Spelling checks enabled (basic implementation; extend in `modules/spelling.py`).
- Suppliers used **only** for analytics (not rule logic).
- Training supports bulk Excel re-upload of Valid/Not-Valid, quick add-one-rule, and optional YAML editing.
- **Exclude-from-analytics** toggle.
- Simultaneous **Excel** + **annotated PDF** downloads (annotation uses ReportLab; falls back gracefully).
- Persistent history and trend analytics.
- Radio locations: **Low Level, Midway, High Level, Unique Coverage**.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
streamlit run app.py
```

## Structure
- `app.py` — Streamlit UI (tabs).
- `modules/` — Logic (audit, rules, training, analytics, utils, PDF, spelling).
- `rulesets/default_rules.yaml` — Initial ruleset aligned to your preferences.
- `templates/` — Excel templates for checklists & training.
- `sample_data/` — Example metadata and placeholder drawings folder.
- `reports/`, `history/` — Outputs and logs.
- `.streamlit/config.toml` — Theme settings.

## Notes
- The PDF annotation is intentionally minimal; swap in your preferred library if needed.
- Extend rules quickly by editing `rulesets/default_rules.yaml` or using the **Train** tab.
