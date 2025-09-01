from pathlib import Path
from reportlab.pdfgen import canvas

def annotate_stub(output_path: Path, header: str, notes: list[str]):
    c = canvas.Canvas(str(output_path))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(72, 800, header)
    c.setFont("Helvetica", 10)
    y = 780
    for n in notes[:50]:
        c.drawString(72, y, f"- {n}")
        y -= 14
        if y < 72:
            c.showPage()
            y = 800
    c.save()

def create_annotation_bundle(basename: str, notes: list[str], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / f"{basename}_annotated.pdf"
    annotate_stub(pdf_path, f"Audit Notes — {basename}", notes)
    return pdf_path
