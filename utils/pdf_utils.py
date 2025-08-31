\
from typing import List, Dict, Any
import io, fitz

def annotate_pdf(pdf_bytes: bytes, findings: List[Dict[str,Any]]) -> bytes:
    """
    Place sticky-note annotations near best-guess text matches or page heads.
    If bbox exists => draw a rectangle + note. Otherwise put note at (36,72).
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for f in findings:
        page_no = int(f.get("page", 1)) - 1
        page_no = min(max(page_no, 0), len(doc)-1)
        page = doc[page_no]
        note = f"[{f.get('severity','INFO')}] {f.get('rule_id','-')}: {f.get('message','')}"
        bbox = f.get("bbox")
        if bbox and isinstance(bbox, (list,tuple)) and len(bbox)==4:
            r = fitz.Rect(*bbox)
            page.add_rect_annot(r)
            # place a text annotation near the rectangle
            pt = fitz.Point(r.x1+6, r.y0+6)
            page.add_text_annot(pt, note)
        else:
            # header-left corner note
            page.add_text_annot(fitz.Point(36,72), note)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()
