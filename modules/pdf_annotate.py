from pathlib import Path

def annotate_text_matches(pdf_path: Path, out_path: Path, matches: list[dict]):
    import fitz
    doc = fitz.open(pdf_path)
    for m in matches:
        page_no = int(m.get("page",1))-1
        text = m.get("text","")
        note = m.get("note", text)
        try:
            page = doc[page_no]
        except Exception:
            continue
        rects = page.search_for(text, quads=False, hit_max=16)
        if rects:
            for r in rects:
                page.add_text_annot(r.br, note)
        else:
            page.add_text_annot((36,36), f"[Missing] {note}")
    doc.save(out_path)

def render_page_image(pdf_path: Path, page: int, zoom: float=2.0) -> bytes:
    import fitz
    doc = fitz.open(pdf_path)
    p = doc[page-1]
    mat = fitz.Matrix(zoom, zoom)
    pix = p.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    doc.close()
    return img_bytes

def annotate_points(pdf_path: Path, out_path: Path, points: list[dict]):
    import fitz
    doc = fitz.open(pdf_path)
    for p in points:
        page_no = int(p.get("page",1))-1
        x, y = float(p.get("x",72)), float(p.get("y",72))
        note = p.get("note","Issue")
        try:
            page = doc[page_no]
        except Exception:
            continue
        page.add_text_annot((x,y), note)
    doc.save(out_path)
