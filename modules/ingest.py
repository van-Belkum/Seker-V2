from pathlib import Path
import re, zipfile, hashlib, time, pandas as pd
def sha256_file(path: Path) -> str:
    h = hashlib.sha256(); 
    with open(path,'rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()
def docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as z: xml = z.read('word/document.xml').decode('utf-8', errors='ignore')
        return re.sub(r'<[^>]+>', '', xml)
    except Exception: return ""
def pdf_text(path: Path) -> str:
    try:
        import fitz; doc = fitz.open(path); out = [p.get_text('text') for p in doc]; doc.close(); return "\n".join(out)
    except Exception: return ""
def index_folder(root: Path, csv_path: Path, mode="append", supersede=True) -> Path:
    rows = []
    for p in root.rglob('*'):
        if not p.is_file() or p.suffix.lower() not in {'.pdf','.docx'}: continue
        text = (docx_text(p) if p.suffix.lower()=='.docx' else pdf_text(p))[:20000]
        m_key = re.search(r'\b(TDEE\d{5}|TN\d+|RAN\d+)\b', p.name, re.I)
        key = m_key.group(1).upper() if m_key else p.stem.upper()
        m_ver = re.search(r'\bv(?:ersion)?\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)*)', p.name + " " + text, re.I)
        version = m_ver.group(1) if m_ver else ""
        if   re.search(r'\bTDEE4\d{3,}\b', p.name): series="TDEE 4000"
        elif re.search(r'\bTDEE5\d{3,}\b', p.name): series="TDEE 5000"
        elif re.search(r'\bTDEE8\d{3,}\b', p.name): series="TDEE 8000"
        elif re.search(r'\bTDEE9\d{3,}\b', p.name): series="TDEE 9000"
        elif re.search(r'\bTN\d+', p.name, re.I):   series="Tech Notes (TN)"
        elif re.search(r'\bRAN\d+', p.name, re.I):  series="RAN"
        elif re.search(r'Broadcast', p.name, re.I): series="Broadcast"
        elif re.search(r'\bRDA\b', p.name, re.I):   series="RDA"
        else:                                       series="Unsorted"
        rows.append({"file": str(p.relative_to(root)),"key": key,"series": series,"version": version,
                     "sha256": sha256_file(p), "size_bytes": p.stat().st_size, "active": True, "indexed_at": int(time.time())})
    df_new = pd.DataFrame(rows)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    if mode=="overwrite" or not csv_path.exists():
        df = df_new
    else:
        df_old = pd.read_csv(csv_path) if csv_path.exists() else pd.DataFrame(columns=df_new.columns)
        df = pd.concat([df_old, df_new], ignore_index=True).drop_duplicates(subset=["file","sha256"], keep="last")
    if supersede and not df.empty:
        def vt(v): 
            try: return tuple(int(x) for x in (v or "0").split("."))
            except: return (0,)
        df["__v"] = df["version"].fillna("").apply(vt)
        df = df.sort_values(["key","__v"]); df["active"] = df.groupby("key")["__v"].transform(lambda s: s==s.max())
        df = df.drop(columns="__v")
    df.to_csv(csv_path, index=False); return csv_path
