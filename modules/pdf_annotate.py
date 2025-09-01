from pathlib import Path
import fitz  # PyMuPDF

def render_page_image(pdf_path: Path, page: int, zoom: float=2.0) -> bytes:
    doc = fitz.open(pdf_path)
    p = doc[page-1]
    mat = fitz.Matrix(zoom, zoom)
    pix = p.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    doc.close()
    return img_bytes

def annotate_points(pdf_path: Path, out_path: Path, points: list[dict]):
    doc = fitz.open(pdf_path)
    for p in points:
        page_no = int(p.get("page",1)) - 1
        x, y = float(p.get("x",72)), float(p.get("y",72))
        note = p.get("note","Issue")
        try:
            page = doc[page_no]
        except Exception:
            continue
        page.add_text_annot((x,y), note)
    doc.save(out_path)
