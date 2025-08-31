\
import os, re, io, glob, zipfile
from typing import Dict, List, Tuple
from docx import Document
from pptx import Presentation

def _text_from_docx(path:str)->str:
    doc = Document(path)
    return "\n".join([p.text for p in doc.paragraphs])

def _text_from_pptx(path:str)->str:
    prs = Presentation(path)
    out = []
    for s in prs.slides:
        for shp in s.shapes:
            if hasattr(shp, "text"):
                out.append(shp.text)
    return "\n".join(out)

def _text_from_pdf(path:str)->str:
    # light-weight text extractor using PyMuPDF
    import fitz
    out = []
    with fitz.open(path) as doc:
        for p in doc:
            out.append(p.get_text("text"))
    return "\n".join(out)

EXT_HANDLERS = {
    ".docx": _text_from_docx,
    ".pptx": _text_from_pptx,
    ".pdf": _text_from_pdf,
    ".txt": lambda p: open(p, "r", encoding="utf-8", errors="ignore").read(),
}

def build_index_from_folder(root:str)->Dict[str,str]:
    """
    Walk folder, read docx/pptx/pdf/txt and build {filepath: text}.
    """
    index = {}
    for dirpath, _, files in os.walk(root):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in EXT_HANDLERS:
                fp = os.path.join(dirpath, f)
                try:
                    index[fp] = EXT_HANDLERS[ext](fp)
                except Exception:
                    # unreadable file -> skip
                    pass
    return index

def search_terms(index:Dict[str,str], terms:List[str], window:int=240)->List[Tuple[str,str]]:
    """
    Return snippets (file, text_snippet) for any term occurrences.
    """
    hits = []
    for fp, txt in index.items():
        low = txt.lower()
        for t in terms:
            t0 = t.lower()
            pos = low.find(t0)
            if pos >= 0:
                s = max(0, pos-window//2); e = min(len(txt), pos+window//2)
                hits.append((fp, txt[s:e].replace("\n"," ")))
    return hits
