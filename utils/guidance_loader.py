\
import os
from dataclasses import dataclass
from typing import List, Tuple

from rapidfuzz.fuzz import token_set_ratio
from docx import Document as DocxDocument
from pptx import Presentation
import fitz  # PyMuPDF

@dataclass
class IndexedDoc:
    path: str
    name: str
    text: str

@dataclass
class GuidanceIndex:
    root: str
    docs: List[IndexedDoc]

    @property
    def count(self) -> int:
        return len(self.docs)

def _text_from_docx(path: str) -> str:
    doc = DocxDocument(path)
    return "\n".join(p.text for p in doc.paragraphs)

def _text_from_pptx(path: str) -> str:
    prs = Presentation(path)
    out = []
    for slide in prs.slides:
        for shp in slide.shapes:
            if hasattr(shp, "text"):
                out.append(shp.text)
    return "\n".join(out)

def _text_from_pdf(path: str) -> str:
    try:
        doc = fitz.open(path)
        out = []
        for page in doc:
            out.append(page.get_text("text"))
        return "\n".join(out)
    except Exception:
        return ""

def _extract_text(path: str) -> str:
    p = path.lower()
    if p.endswith(".docx"):
        return _text_from_docx(path)
    if p.endswith(".pptx"):
        return _text_from_pptx(path)
    if p.endswith(".pdf"):
        return _text_from_pdf(path)
    return ""

def build_index_from_folder(root: str) -> GuidanceIndex:
    exts = (".docx",".pptx",".pdf")
    docs: List[IndexedDoc] = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if fn.lower().endswith(exts):
                full = os.path.join(dirpath, fn)
                try:
                    txt = _extract_text(full)
                    if txt.strip():
                        docs.append(IndexedDoc(path=full, name=fn, text=txt))
                except Exception:
                    pass
    return GuidanceIndex(root=root, docs=docs)

def search_terms(idx: GuidanceIndex, terms: List[str], topk: int = 5) -> List[Tuple[float, IndexedDoc]]:
    if not idx or not idx.docs or not terms:
        return []
    results: List[Tuple[float, IndexedDoc]] = []
    for doc in idx.docs:
        best = 0.0
        # cap for speed
        text = doc.text[:300000]
        for t in terms:
            s = token_set_ratio(t, text)
            best = max(best, s)
        if best > 70:
            results.append((best, doc))
    results.sort(key=lambda x: x[0], reverse=True)
    return results[:topk]
