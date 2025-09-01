from pathlib import Path
import pandas as pd
from .utils import clean_address_title, REPORTS_DIR, timestamp
from .spelling import basic_spelling_issues

def run_audit(metadata: dict, checklist_df: pd.DataFrame, ruleset: dict) -> dict:
    """Return results dict with 'errors' DataFrame and 'notes' list."""
    errors = []
    notes = []

    # 1) Address-title match (ignoring ', 0 ,')
    addr = clean_address_title(metadata.get('site_address', ''))
    title = clean_address_title(metadata.get('drawing_title', ''))
    if addr and addr.lower() not in (title or '').lower():
        errors.append({
            "Category":"Metadata","Code":"ADDR_TITLE_MATCH","Description":"Address must appear in title (ignoring ', 0 ,')",
            "Expected":"Present","Found":"Missing","Status":"Rejected"
        })
        notes.append("Address not found in title (after ignore rule).")

    # 2) MIMO required unless project == Power Resilience
    project = (metadata.get('project') or '').strip()
    if project != ruleset.get("settings", {}).get("hide_mimo_if_project_equals", "Power Resilience"):
        # ensure sectors exist
        for s in ["S1","S2","S3","S4"]:
            val = metadata.get(f"mimo_{s}")
            if not val:
                errors.append({
                    "Category":"MIMO","Code":f"MIMO-{s}","Description":f"MIMO selection missing for {s}",
                    "Expected":"Selected","Found":"Empty","Status":"Rejected"
                })
        if not errors:
            notes.append("All MIMO sectors present.")
    else:
        notes.append("MIMO hidden for Power Resilience project.")

    # 3) Spelling basics over metadata + checklist descriptions
    meta_concat = " ".join([str(v) for v in metadata.values() if isinstance(v, str)])
    descs = " ".join([str(x) for x in checklist_df.get("Description", [])])
    spell = basic_spelling_issues(meta_concat, descs)
    if spell:
        for w, why in spell[:10]:
            errors.append({
                "Category":"Spelling","Code":"SPELL","Description":f"Suspicious token '{w}' ({why})",
                "Expected":"Correct spelling","Found":w,"Status":"Review"
            })
        notes.append(f"Spelling flagged {len(spell)} token(s).")

    # 4) Checklist expected status
    for _, row in checklist_df.iterrows():
        exp = str(row.get("Expected Status","")).strip().lower()
        if exp not in {"accepted","accept","ok"}:
            errors.append({
                "Category":row.get("Category",""),
                "Code":row.get("Code",""),
                "Description":row.get("Description",""),
                "Expected":"Accepted",
                "Found":row.get("Expected Status",""),
                "Status":"Rejected"
            })

    errors_df = pd.DataFrame(errors) if errors else pd.DataFrame(columns=["Category","Code","Description","Expected","Found","Status"])
    # Create Excel rejection report
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_xlsx = REPORTS_DIR / f"rejection_report_{timestamp()}.xlsx"
    with pd.ExcelWriter(out_xlsx, engine="openpyxl") as writer:
        errors_df.to_excel(writer, index=False, sheet_name="Errors")
    return {"errors": errors_df, "notes": notes, "excel_path": out_xlsx}
