\
from typing import List, Dict, Any, Optional
import io, re
import fitz  # PyMuPDF

def pdf_text_pages(pdf_bytes: bytes) -> List[str]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = [p.get_text("text") for p in doc]
    return pages

def _find_phrase_bbox(page: "fitz.Page", phrase: str) -> Optional[fitz.Rect]:
    if not phrase or not phrase.strip():
        return None
    rects = page.search_for(phrase, quads=False)
    if rects:
        # merge into one rect
        r = rects[0]
        for rr in rects[1:]:
            r |= rr
        return r
    # try case-insensitive by searching words
    text = page.get_text("text")
    # fallback: highlight first matching word
    m = re.search(re.escape(phrase), text, flags=re.IGNORECASE)
    if m:
        # approximate by marking a small area at top-left
        return fitz.Rect(page.rect.x0+36, page.rect.y0+36, page.rect.x0+200, page.rect.y0+80)
    return None

def annotate_pdf_with_comments(pdf_bytes: bytes, findings: List[Dict[str, Any]]) -> bytes:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for f in findings:
        page_idx = int(f.get("page", 1) or 1) - 1
        if page_idx < 0 or page_idx >= len(doc):
            page_idx = 0
        page = doc[page_idx]

        msg = f.get("message","Issue")
        ev = f.get("evidence_text","")
        bbox = None
        if ev:
            bbox = _find_phrase_bbox(page, ev)

        if bbox is None:
            # place a note near top-left
            x, y = page.rect.x0 + 36, page.rect.y0 + 36
            page.add_text_annot((x, y), msg, icon="Comment")
        else:
            # draw rectangle and add note
            page.add_rect_annot(bbox, color=(1,0,0), fill=None)
            page.add_text_annot((bbox.x0, bbox.y0 - 10), msg, icon="Comment")
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()
