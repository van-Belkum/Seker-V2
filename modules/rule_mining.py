from pathlib import Path
import re, pandas as pd
from .ingest import docx_text, pdf_text

HINT = re.compile(r'\b(shall|must|required|shall not|do not|ensure|prohibit|forbidden)\b', re.I)

def sentences(text: str):
    parts = re.split(r'(?<=[\.!?])\s+', text or "")
    return [p.strip() for p in parts if len(p.strip())>0]

def mine_rules_from_file(path: Path, max_items: int = 120):
    text = (docx_text(path) if path.suffix.lower()==".docx" else pdf_text(path)) or ""
    cands = [s for s in sentences(text) if HINT.search(s)]
    rows = []
    for s in cands[:max_items]:
        desc = s[:200]
        # Regex: take a strong keyword span
        tokens = re.findall(r'[A-Za-z0-9\-]{3,}', s)[:8]
        pattern = '\\b' + '\\s+'.join([re.escape(t) for t in tokens[:4]]) + '\\b' if tokens else re.escape(desc[:30])
        rows.append({
            "id": f"R_{abs(hash(s))%10**8}",
            "type": "doc_text_presence",
            "severity": "major" if re.search(r'\b(shall|must|required|shall not)\b', s, re.I) else "minor",
            "description": desc,
            "options": {"any": [desc[:120]], "any_regex": [pattern]},
            "source": str(path.name)
        })
    return pd.DataFrame(rows)
