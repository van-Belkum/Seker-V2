from typing import List, Dict, Any
import fitz  # PyMuPDF

def annotate_pdf_with_findings(pdf_bytes: bytes, findings: List[Dict[str,Any]]) -> bytes:
    """
    If finding has bbox=[x0,y0,x1,y1], draw a rectangle.
    Otherwise, search the page text for a small snippet and place a sticky note.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for f in findings:
        page_i = max(0, int(f.get("page",1))-1)
        if page_i >= len(doc): continue
        page = doc[page_i]
        text = f.get("reason","")
        bbox = f.get("bbox")
        if bbox and isinstance(bbox,(list,tuple)) and len(bbox)==4:
            rect = fitz.Rect(*bbox)
            annot = page.add_rect_annot(rect)
            annot.set_info(title=f.get("title","Finding"), content=text)
            annot.update()
        else:
            snippet = f.get("snippet") or f.get("title","")
            if snippet:
                areas = page.search_for(str(snippet)[:80], quads=False)
                if areas:
                    rect = areas[0]
                    annot = page.add_text_annot(rect.br, f"{f.get('title','Finding')}\n{text}")
                    annot.update()
                else:
                    annot = page.add_text_annot(fitz.Point(36,36), f"{f.get('title','Finding')}\n{text}")
                    annot.update()
    out = doc.tobytes()
    doc.close()
    return out
