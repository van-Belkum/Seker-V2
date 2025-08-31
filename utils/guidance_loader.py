import os, io, re, zipfile, pickle
from pathlib import Path
from typing import Dict, Any, List

from utils.text_extractors import extract_text_from_file

def build_index_from_folder(folder: str) -> Dict[str, Any]:
    folder = Path(folder)
    docs = []
    for p in folder.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".pdf",".docx",".pptx",".txt"}:
            try:
                text_pages = extract_text_from_file(str(p))
                docs.append({"title": p.name, "path": str(p), "pages": text_pages})
            except Exception as e:
                # skip bad files
                pass
    return {"docs": docs}

def build_index_from_zipfile(zip_bytes: bytes) -> Dict[str, Any]:
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    docs = []
    for name in zf.namelist():
        lower = name.lower()
        if lower.endswith((".pdf",".docx",".pptx",".txt")) and not name.endswith("/"):
            try:
                with zf.open(name) as f:
                    raw = f.read()
                text_pages = extract_text_from_file(name, raw_content=raw)
                docs.append({"title": os.path.basename(name), "path": name, "pages": text_pages})
            except Exception:
                pass
    return {"docs": docs}

def index_stats(index: Dict[str,Any]) -> str:
    n_docs = len(index.get("docs", []))
    n_pages = sum(len(d.get("pages", [])) for d in index.get("docs", []))
    return f"{n_docs} documents / {n_pages} pages"

def search_guidance_for_terms(index: Dict[str,Any], terms: List[str]) -> List[Dict[str,Any]]:
    hits = []
    terms = [t for t in terms if isinstance(t, str) and t and t != "(blank)"]
    for d in index.get("docs", []):
        for pi, page in enumerate(d.get("pages", []), start=1):
            low = page.lower()
            for t in terms:
                if t.lower() in low:
                    # capture small context
                    i = low.find(t.lower())
                    ctx = page[max(0, i-60): i+60]
                    hits.append({"title": d["title"], "page": pi, "term": t, "context": ctx})
    return hits

def save_index(index: Dict[str,Any], path: str):
    with open(path, "wb") as f:
        pickle.dump(index, f)

def load_index(path: str) -> Dict[str,Any]:
    with open(path, "rb") as f:
        return pickle.load(f)
