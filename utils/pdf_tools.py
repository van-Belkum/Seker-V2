
from typing import List, Dict, Any
import fitz  # PyMuPDF

def extract_text_from_pdf(pdf_bytes: bytes) -> List[str]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for p in doc:
        pages.append(p.get_text("text"))
    doc.close()
    return pages

def annotate_pdf_with_findings(pdf_bytes: bytes, findings: List[Dict[str,Any]]) -> bytes:
    """
    Lightweight annotation: for each finding with 'text' we search the first page it appears on
    and draw a red rectangle with a small popup note.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for f in findings:
        term = str(f.get("text","")).strip()
        if not term:
            continue
        # if page given, search there first; else scan pages
        pages_to_scan = range(doc.page_count) if not f.get("page") else [max(0, int(f["page"])-1)]
        hit = False
        for pno in pages_to_scan:
            page = doc[pno]
            rects = page.search_for(term, quads=False)
            if rects:
                r = rects[0]  # first hit
                # rectangle
                page.add_rect_annot(r)
                # text note just above
                note = f"{f.get('rule','')}: {term} — {f.get('suggestion','')}"
                page.add_text_annot((r.x0, max(0,r.y0-10)), note)
                hit = True
                break
        if not hit and doc.page_count>0:
            # fallback: stick a note on page 1
            page = doc[0]
            page.add_text_annot((36, 36), f"{f.get('rule','')}: {term}")
    out = doc.tobytes()
    doc.close()
    return out
