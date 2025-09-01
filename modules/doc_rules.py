import re
from pathlib import Path
import yaml
import pandas as pd
from .ingest import docx_text, pdf_text

def load_ruleset(path: Path = Path("rulesets/default_rules.yaml")):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def extract_text(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        return docx_text(path)
    elif path.suffix.lower() == ".pdf":
        return pdf_text(path)
    return ""

def run_doc_checks(doc_path: Path, rules: dict) -> pd.DataFrame:
    text = extract_text(doc_path) or ""
    findings = []
    link_like = re.findall(r'https?://\S+|\b\w+\.\w{2,}\b', text, flags=re.I)

    def recentish(dtstr: str):
        import datetime as dt
        for fmt in ("%d/%m/%Y","%d/%m/%y","%d-%m-%Y","%d-%m-%y","%Y-%m-%d"):
            try:
                d = dt.datetime.strptime(dtstr, fmt)
                return (dt.datetime.now() - d).days
            except:
                pass
        return None

    for r in rules.get("rules", []):
        rtype = r.get("type")
        rid = r.get("id")
        desc = r.get("description","")
        sev = r.get("severity","minor")
        ok = True
        detail = ""

        if rtype == "doc_text_presence":
            opts = r.get("options", {})
            any_terms = [t.lower() for t in opts.get("any", [])]
            all_terms = [t.lower() for t in opts.get("all", [])]
            any_regex = opts.get("any_regex", [])
            ok_any = True if not any_terms else any(t in text.lower() for t in any_terms)
            ok_all = True if not all_terms else all(t in text.lower() for t in all_terms)
            ok_rgx = True if not any_regex else any(re.search(pat, text, re.I) for pat in any_regex)
            ok = ok_any and ok_all and ok_rgx
            if not ok:
                detail = f"Missing terms: any={any_terms} all={all_terms} regex={any_regex}"
        elif rtype == "doc_date_recency":
            ds = re.findall(r'\b(\d{1,2}[\/-]\d{1,2}[\/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b', text)
            if not ds:
                ok = False
                detail = "No date string found."
            else:
                ages = [recentish(d) for d in ds]
                ages = [a for a in ages if a is not None]
                if ages and min(ages) > 365*2:
                    ok = False
                    detail = "Latest date appears older than 2 years."
        elif rtype == "doc_link_presence":
            ok = bool(link_like)
            if not ok: detail = "No link-like strings found."
        else:
            continue

        if not ok:
            findings.append({"Rule": rid, "Description": desc, "Severity": sev, "Detail": detail})
    return pd.DataFrame(findings)
