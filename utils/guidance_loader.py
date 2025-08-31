# app.py (near the top)
try:
    from utils.guidance_loader import (
        build_index_from_folder,
        build_index_from_zip,
        search_terms,
        GuidanceIndex,
    )
except Exception as e:
    # Fallback: import the module and reference via module to avoid name errors
    import importlib, traceback, sys
    gl = importlib.import_module("utils.guidance_loader")
    build_index_from_folder = getattr(gl, "build_index_from_folder")
    build_index_from_zip     = getattr(gl, "build_index_from_zip", lambda _b: gl.GuidanceIndex(root="(zip)", docs=[]))
    search_terms             = getattr(gl, "search_terms")
    GuidanceIndex            = getattr(gl, "GuidanceIndex")
    print("Guidance import fallback used:", e, file=sys.stderr)
    traceback.print_exc()

# ---- Robust fuzzy helpers ----------------------------------------------------
try:
    # Stable, supported API
    from rapidfuzz import fuzz
    def _ratio(a: str, b: str) -> float:
        return float(fuzz.ratio(a, b))
    def _partial_ratio(a: str, b: str) -> float:
        return float(fuzz.partial_ratio(a, b))
except Exception:
    # Fallback if RapidFuzz isn't available
    import difflib
    def _ratio(a: str, b: str) -> float:
        return difflib.SequenceMatcher(None, a, b).ratio() * 100.0
    def _partial_ratio(a: str, b: str) -> float:
        return _ratio(a, b)

# ---- Document loaders --------------------------------------------------------
import fitz  # PyMuPDF
from docx import Document as DocxDocument
from pptx import Presentation

SUPPORTED_EXT = {".pdf", ".docx", ".pptx", ".txt"}

def _read_pdf(path: str) -> str:
    try:
        doc = fitz.open(path)
        parts = []
        for p in doc:
            parts.append(p.get_text("text") or "")
        return "\n".join(parts)
    except Exception:
        return ""

def _read_docx(path: str) -> str:
    try:
        d = DocxDocument(path)
        return "\n".join(p.text for p in d.paragraphs)
    except Exception:
        return ""

def _read_pptx(path: str) -> str:
    try:
        prs = Presentation(path)
        buf: List[str] = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    buf.append(shape.text)
        return "\n".join(buf)
    except Exception:
        return ""

def _read_txt(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""

READERS = {
    ".pdf": _read_pdf,
    ".docx": _read_docx,
    ".pptx": _read_pptx,
    ".txt": _read_txt,
}

# ---- Index structures --------------------------------------------------------
@dataclass
class IndexedDoc:
    rel_path: str
    title: str
    text: str

@dataclass
class GuidanceIndex:
    root: str
    docs: List[IndexedDoc]

    @property
    def count(self) -> int:
        return len(self.docs)

# ---- Build & search ----------------------------------------------------------
def build_index_from_folder(root: str) -> GuidanceIndex:
    docs: List[IndexedDoc] = []
    if not root or not os.path.isdir(root):
        return GuidanceIndex(root=root, docs=[])

    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in SUPPORTED_EXT:
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, root)
            reader = READERS.get(ext)
            text = reader(path) if reader else ""
            if text.strip():
                docs.append(IndexedDoc(rel_path=rel, title=fn, text=text))
    return GuidanceIndex(root=root, docs=docs)

def build_index_from_zip(_bytes: bytes) -> GuidanceIndex:
    # Not used at the moment in your flow; kept for API compatibility
    return GuidanceIndex(root="(zip)", docs=[])

def search_terms(index: GuidanceIndex, queries: Iterable[str], topk: int = 10) -> List[Tuple[float, IndexedDoc]]:
    """
    Very simple semantic-lite search:
    - Score = max(fuzzy partial ratio over lines, fuzzy ratio over title)
    - Returns topK matches across docs.
    """
    q_list = [q.strip() for q in queries if q and q.strip()]
    if not q_list or not index.docs:
        return []

    scored: List[Tuple[float, IndexedDoc]] = []
    for doc in index.docs:
        score_doc = 0.0
        # Title score
        for q in q_list:
            score_doc = max(score_doc, _ratio(q.lower(), doc.title.lower()))
        # Body score (sampled by lines, partial ratio)
        lines = doc.text.splitlines()
        # Downsample long docs for speed
        if len(lines) > 1200:
            step = max(1, len(lines) // 1200)
            lines = lines[::step]

        local_best = 0.0
        for ln in lines:
            lnl = ln.lower()
            for q in q_list:
                local_best = max(local_best, _partial_ratio(q.lower(), lnl))
            if local_best >= 99.0:
                break  # good enough

        score_doc = max(score_doc, local_best)
        if score_doc > 0:
            scored.append((score_doc, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:topk]
