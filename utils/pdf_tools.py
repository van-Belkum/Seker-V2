from typing import List, Dict, Any
import io, re
import fitz  # PyMuPDF

def extract_text_pages(pdf_bytes: bytes) -> List[str]:
    pages = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            pages.append(page.get_text("text"))
    return pages

def annotate_pdf_with_findings(pdf_bytes: bytes, pages_text: List[str], findings: List[Dict[str,Any]]) -> bytes:
    # Adds red rectangles or sticky notes near matched anchors; falls back to first page note
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for f in findings:
        term = (f.get("anchor") or "").strip()
        page_no = f.get("page", None)
        placed = False
        if term:
            # try exact match on indicated page first
            if page_no and 1 <= page_no <= doc.page_count:
                page = doc[page_no-1]
                areas = page.search_for(term, quads=False)
                if areas:
                    r = areas[0].inflate(2)
                    note = page.add_note(r.tl, text=f"{f.get('severity')}: {f.get('message')}")
                    placed = True
            # scan all pages if not placed
            if not placed:
                for pi in range(len(pages_text)):
                    page = doc[pi]
                    areas = page.search_for(term, quads=False)
                    if areas:
                        r = areas[0].inflate(2)
                        page.add_note(r.tl, text=f"{f.get('severity')}: {f.get('message')}")
                        placed = True
                        break
        if not placed:
            # drop a note in top-left of first page
            p0 = doc[0]
            p0.add_note((36, 36), text=f"{f.get('severity')}: {f.get('message')}")

    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()
