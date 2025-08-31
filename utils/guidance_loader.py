# utils/guidance.py
import os, io, zipfile, json, re
from typing import Dict, List
import fitz  # PyMuPDF

SUPPORTED_DOCS = {".pdf", ".txt"}

def _text_from_pdf_bytes(data: bytes) -> str:
    doc = fitz.open(stream=data, filetype="pdf")
    parts = []
    for p in doc:
        parts.append(p.get_text("text"))
    return "\n".join(parts)

def _text_from_file(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return _text_from_pdf_bytes(open(path, "rb").read())
    if ext == ".txt":
        return open(path, "r", encoding="utf-8", errors="ignore").read()
    return ""

def build_index_from_folder(root: str) -> Dict:
    index = {"docs": []}
    if not root or not os.path.isdir(root):
        return index
    for dirpath, _, files in os.walk(root):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in SUPPORTED_DOCS:
                fp = os.path.join(dirpath, f)
                try:
                    txt = _text_from_file(fp)
                    index["docs"].append({"path": fp, "text": txt})
                except Exception:
                    pass
    index["count"] = len(index["docs"])
    return index

def build_index_from_zip(zip_bytes: bytes) -> Dict:
    index = {"docs": []}
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as z:
            for name in z.namelist():
                ext = os.path.splitext(name)[1].lower()
                if ext in SUPPORTED_DOCS:
                    try:
                        data = z.read(name)
                        txt = _text_from_pdf_bytes(data) if ext == ".pdf" else data.decode("utf-8","ignore")
                        index["docs"].append({"path": name, "text": txt})
                    except Exception:
                        pass
        index["count"] = len(index["docs"])
    except Exception:
        index["count"] = 0
    return index

def search_terms(index: Dict, terms: List[str]) -> List[Dict]:
    """Return matches [{'doc':path,'snippet':...}] if all terms are found in a document."""
    out = []
    if not index or not index.get("docs"):
        return out
    for d in index["docs"]:
        text = d["text"]
        if all(t.lower() in text.lower() for t in terms):
            # cheap snippet
            i = text.lower().find(terms[0].lower())
            snippet = text[max(0,i-60): i+120] if i >= 0 else text[:180]
            out.append({"doc": d["path"], "snippet": snippet})
    return out
