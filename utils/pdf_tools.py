
import fitz
from typing import List, Dict, Any

def extract_pdf_text(pdf_bytes: bytes) -> str:
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        return "\n".join(page.get_text("text") for page in doc)

def find_keyword_boxes(pdf_bytes: bytes, keyword: str):
    if not keyword:
        return []
    boxes=[]
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for pno, page in enumerate(doc):
            # search_for supports case-insensitive via flags
            try:
                rects = page.search_for(keyword, quads=False, flags=fitz.TEXT_IGNORECASE)
            except Exception:
                rects = page.search_for(keyword)
            for r in rects:
                boxes.append((pno, r))
    return boxes

def annotate_pdf_with_findings(pdf_bytes: bytes, findings: List[Dict[str,Any]]) -> bytes:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for f in findings:
        kw = f.get("keyword")
        msg = f.get("message","")
        severity = f.get("severity","minor")
        color = (1,0,0) if severity=="major" else (1,0.6,0)
        boxes = find_keyword_boxes(pdf_bytes, kw) if kw else []
        if boxes:
            # draw box + sticky note for the first match
            for pno, rect in boxes[:2]:  # up to 2 per finding
                page = doc[pno]
                # highlight rectangle
                annot = page.add_rect_annot(rect)
                annot.set_colors(stroke=color)
                annot.update()
                # sticky note slightly above the rect
                note_pt = fitz.Point(rect.x0, max(0, rect.y0-10))
                page.add_text_annot(note_pt, msg)
        else:
            # drop a note at top-left of first page
            page = doc[0]
            page.add_text_annot(fitz.Point(40, 60), f"{kw or 'Finding'}: {msg}")
    out = doc.tobytes()
    doc.close()
    return out
