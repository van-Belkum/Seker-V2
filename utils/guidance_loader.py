
import os, re, glob, io
from typing import List, Dict, Any
import fitz  # PyMuPDF
try:
    import docx  # python-docx
except Exception:
    docx = None
try:
    from pptx import Presentation
except Exception:
    Presentation = None

import pandas as pd

def guidance_default_root():
    # Windows default provided by user
    return r"C:\Mac\Home\Music\Guidance"

def read_file_text(path: str) -> str:
    ext = os.path.splitext(path.lower())[1]
    if ext==".pdf":
        try:
            with fitz.open(stream=open(path,"rb").read(), filetype="pdf") as doc:
                return "\n".join(page.get_text("text") for page in doc)
        except Exception:
            return ""
    if ext in (".docx",):
        if not docx: return ""
        try:
            d = docx.Document(path)
            return "\n".join([p.text for p in d.paragraphs])
        except Exception:
            return ""
    if ext in (".pptx",):
        if not Presentation: return ""
        try:
            prs = Presentation(path)
            parts=[]
            for s in prs.slides:
                for shp in s.shapes:
                    if hasattr(shp, "text"):
                        parts.append(shp.text)
            return "\n".join(parts)
        except Exception:
            return ""
    if ext in (".txt",".md"):
        try:
            return open(path,"r",encoding="utf-8",errors="ignore").read()
        except Exception:
            return ""
    return ""

def load_guidance_corpus() -> List[Dict[str,Any]]:
    root = os.environ.get("GUIDANCE_ROOT", guidance_default_root())
    corpus=[]
    if not os.path.isdir(root):
        return corpus
    # BTEE and other orgs
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in (".pdf",".docx",".pptx",".txt",".md"):
                full = os.path.join(dirpath, fn)
                text = read_file_text(full)
                if text:
                    corpus.append({"id": full, "source": os.path.relpath(full, root), "text": text})
    return corpus

def load_latest_nemesis() -> pd.DataFrame:
    root = os.environ.get("GUIDANCE_ROOT", guidance_default_root())
    nroot = os.path.join(root, "Nemesis")
    if not os.path.isdir(nroot):
        return pd.DataFrame()
    # pick latest by modified time matching KTL_Site_Nemesis_Data_*.xls*
    files = glob.glob(os.path.join(nroot, "KTL_Site_Nemesis_Data_*.xls*"))
    if not files:
        return pd.DataFrame()
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    latest = files[0]
    try:
        return pd.read_excel(latest)
    except Exception:
        try:
            return pd.read_excel(latest, engine="openpyxl")
        except Exception:
            return pd.DataFrame()
