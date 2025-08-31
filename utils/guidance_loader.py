
"""
Loads guidance from a local folder (mandatory) and builds a tiny searchable index.
Supported: .docx, .pptx, .pdf, .txt
"""
import os, re
from typing import Dict, List, Any
from collections import defaultdict

from rapidfuzz.string_metric import levenshtein
from rapidfuzz import fuzz

# Optional imports guarded
try:
    import docx  # python-docx
except Exception:
    docx = None
try:
    from pptx import Presentation  # python-pptx
except Exception:
    Presentation = None
try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

_INDEX: Dict[str, Any] = {
    "loaded": False,
    "root": None,
    "files_indexed": 0,
    "terms_indexed": 0,
    "docs": [],   # list of {path,text}
    "inv": defaultdict(list),  # term -> list[(doc_id, count)]
}

def set_guidance_root(new_root: str=None) -> str:
    if new_root is not None:
        _INDEX["root"] = new_root
    return _INDEX.get("root")

def get_index_status() -> Dict[str,Any]:
    return {k:v for k,v in _INDEX.items() if k in ("loaded","root","files_indexed","terms_indexed")}

def _append_doc(path: str, text: str):
    did = len(_INDEX["docs"])
    _INDEX["docs"].append({"path": path, "text": text})
    # super simple tokenization
    words = re.findall(r"[A-Za-z0-9_+/.-]{3,}", text.lower())
    from collections import Counter
    c = Counter(words)
    for term, cnt in c.items():
        _INDEX["inv"][term].append((did, cnt))

def _read_docx(fp: str) -> str:
    if docx is None:
        return ""
    d = docx.Document(fp)
    return "\n".join(p.text for p in d.paragraphs)

def _read_pptx(fp: str) -> str:
    if Presentation is None:
        return ""
    prs = Presentation(fp)
    out = []
    for i, slide in enumerate(prs.slides, start=1):
        parts = []
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                parts.append(shape.text)
        out.append(f"[Slide {i}]\n" + "\n".join(parts))
    return "\n\n".join(out)

def _read_pdf(fp: str) -> str:
    if fitz is None:
        return ""
    doc = fitz.open(fp)
    parts = []
    for p in doc:
        parts.append(p.get_text("text"))
    doc.close()
    return "\n".join(parts)

def _read_txt(fp: str) -> str:
    try:
        with open(fp, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

def load_guidance_index(root: str) -> Dict[str,Any]:
    _INDEX["loaded"] = False
    _INDEX["files_indexed"] = 0
    _INDEX["terms_indexed"] = 0
    _INDEX["docs"].clear()
    _INDEX["inv"].clear()
    if not root or not os.path.isdir(root):
        return get_index_status()

    for dirpath, _, files in os.walk(root):
        for fn in files:
            fp = os.path.join(dirpath, fn)
            ext = os.path.splitext(fn)[1].lower()
            text = ""
            try:
                if ext in (".docx",):
                    text = _read_docx(fp)
                elif ext in (".pptx",):
                    text = _read_pptx(fp)
                elif ext in (".pdf",):
                    text = _read_pdf(fp)
                elif ext in (".txt",):
                    text = _read_txt(fp)
            except Exception:
                text = ""
            if text.strip():
                _append_doc(fp, text)
                _INDEX["files_indexed"] += 1
    _INDEX["terms_indexed"] = len(_INDEX["inv"])
    _INDEX["loaded"] = _INDEX["files_indexed"] > 0
    return get_index_status()

def search_guidance(query: str, top_k: int=5) -> List[Dict[str,Any]]:
    """Return top docs containing query tokens (OR)."""
    if not _INDEX["loaded"] or not query:
        return []
    q = query.lower().strip()
    # exact term hits first
    hits = []
    # token search
    terms = re.findall(r"[A-Za-z0-9_+/.-]{2,}", q)
    seen = set()
    for t in terms:
        for did, _cnt in _INDEX["inv"].get(t, []):
            if did in seen: 
                continue
            seen.add(did)
            doc = _INDEX["docs"][did]
            # make small snippet
            txt = doc["text"]
            pos = txt.lower().find(t)
            start = max(0, pos-80) if pos>=0 else 0
            end = min(len(txt), start+240)
            hits.append({
                "doc": doc["path"],
                "snippet": txt[start:end].replace("\n"," ") + ("..." if end < len(txt) else ""),
                "score": 1.0,
            })
    # naive fallback: if no token hits, do fuzzy across a few docs
    if not hits:
        for did, doc in enumerate(_INDEX["docs"][:100]):
            score = fuzz.partial_ratio(q, doc["text"][:10000])
            if score > 80:
                hits.append({"doc": doc["path"], "snippet": doc["text"][:240].replace("\n"," "), "score": score/100})
    hits.sort(key=lambda x: x["score"], reverse=True)
    return hits[:top_k]
