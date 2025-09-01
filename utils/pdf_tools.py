from __future__ import annotations
import io, fitz
from typing import List, Dict

def annotate_pdf(pdf_bytes: bytes, findings: List[Dict]) -> bytes:
    # findings: [{page:int|None, text:str, comment:str}]
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for f in findings:
        comment = f.get("comment","Finding")
        text = f.get("text","")
        tgt_page = f.get("page")
        pages = range(len(doc)) if tgt_page is None else [min(max(int(tgt_page),0), len(doc)-1)]
        placed=False
        for pno in pages:
            page = doc[pno]
            if text:
                rects = page.search_for(text, quads=False)
            else:
                rects = []
            if rects:
                r = rects[0]
                ann = page.add_rect_annot(r)
                ann.set_colors(stroke=(1,0,0))
                ann.set_border(width=1)
                ann.update()
                page.add_note(r.tl, contents=comment)
                placed=True
                break
        if not placed:
            # fallback: a sticky at top-left of chosen page
            page = doc[pages[0]]
            page.add_note(page.rect.tl + (20,20), contents=comment)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()
