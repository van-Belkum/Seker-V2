import fitz

def annotate_pdf(pdf_bytes, findings):
    doc = fitz.open("pdf", pdf_bytes)
    for f in findings:
        kw = f.get("term", "")
        for page in doc:
            rects = page.search_for(kw)
            for r in rects:
                annot = page.add_rect_annot(r)
                annot.set_colors(stroke=(1,0,0))
                annot.update()
                page.add_text_annot(r.tl, f.get("comment","Issue"))
    return doc.write()
