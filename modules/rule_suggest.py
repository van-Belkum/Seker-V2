from pathlib import Path
import re, zipfile
import pandas as pd
from .ingest import docx_text, pdf_text

HINT_PAT = re.compile(r'\b(shall|must|required|do not|shall not|prohibit|forbidden|ensure|shall be)\b', re.I)

def extract_sentences(text: str):
    # naive sentence split
    parts = re.split(r'(?<=[\.!?])\s+', text)
    return [p.strip() for p in parts if len(p.strip())>0]

def suggest_rules_for_file(path: Path, max_rules: int = 100):
    if path.suffix.lower()==".docx":
        text = docx_text(path)
    else:
        text = pdf_text(path)
    sentences = extract_sentences(text or "")
    candidates = [s for s in sentences if HINT_PAT.search(s)]
    rows = []
    for s in candidates[:max_rules]:
        # choose regex-friendly key bits
        snippet = s[:120]
        regex = re.escape(snippet[:40])
        rows.append({
            "proposed_id": f"R_{abs(hash(s))%10**8}",
            "type": "doc_text_presence",
            "severity": "major" if re.search(r'\bmust|shall|shall not|required\b', s, re.I) else "minor",
            "description": snippet,
            "options_any": [snippet],
            "options_any_regex": [regex]
        })
    return pd.DataFrame(rows)
