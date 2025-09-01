from pathlib import Path
import re, zipfile, hashlib, shutil, time
import pandas as pd

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()

def docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read('word/document.xml').decode('utf-8', errors='ignore')
        return re.sub(r'<[^>]+>', '', xml)
    except Exception:
        return ""

def pdf_text(path: Path) -> str:
    try:
        import fitz
        doc = fitz.open(path)
        out = []
        for p in doc:
            out.append(p.get_text('text'))
        doc.close()
        return "\n".join(out)
    except Exception:
        return ""

def series_from_name(name: str) -> str:
    if re.search(r'\bTDEE4\d{3,}\b', name): return "TDEE 4000"
    if re.search(r'\bTDEE5\d{3,}\b', name): return "TDEE 5000"
    if re.search(r'\bTDEE8\d{3,}\b', name): return "TDEE 8000"
    if re.search(r'\bTDEE9\d{3,}\b', name): return "TDEE 9000"
    if re.search(r'\bTN\d+', name, re.I): return "Tech Notes (TN)"
    if re.search(r'\bRAN\d+', name, re.I): return "RAN"
    if re.search(r'Broadcast', name, re.I): return "Broadcast"
    if re.search(r'\bRDA\b', name): return "RDA"
    return "Unsorted"

def extract_version(name_or_text: str) -> str:
    m = re.search(r'\bv(?:ersion)?\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)*)', name_or_text, re.I)
    return m.group(1) if m else ""

def extract_key(name: str) -> str:
    # e.g., TDEE40501 ... -> TDEE40501
    m = re.search(r'\b(TDEE\d{5}|TN\d+|RAN\d+)\b', name, re.I)
    return m.group(1).upper() if m else Path(name).stem.upper()

def index_folder(root: Path, out_csv: Path, mode: str="append", supersede: bool=True) -> Path:
    rows = []
    for p in root.rglob('*'):
        if not p.is_file() or p.suffix.lower() not in {'.pdf','.docx'}:
            continue
        ext = p.suffix.lower()
        preview = (docx_text(p) if ext=='.docx' else pdf_text(p))[:20000]
        series = series_from_name(p.name)
        version = extract_version(p.name + " " + preview)
        key = extract_key(p.name)
        rows.append({
            "file": str(p.relative_to(root)),
            "series": series,
            "key": key,
            "version": version,
            "sha256": sha256_file(p),
            "size_bytes": p.stat().st_size,
            "title_guess": p.stem[:200],
            "active": True,
            "indexed_at": int(time.time())
        })
    df_new = pd.DataFrame(rows)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    if mode == "overwrite" or not out_csv.exists():
        df = df_new
    else:
        df_old = pd.read_csv(out_csv) if out_csv.exists() else pd.DataFrame(columns=df_new.columns)
        df = pd.concat([df_old, df_new], ignore_index=True)
        # drop exact duplicates (by file + sha)
        df = df.drop_duplicates(subset=["file","sha256"], keep="last")

    if supersede and not df.empty:
        # For each key, mark only the highest version as active (simple numeric compare)
        def ver_tuple(v):
            try:
                return tuple(int(x) for x in v.split("."))
            except:
                return (0,)
        df["version_tuple"] = df["version"].fillna("").apply(ver_tuple)
        df = df.sort_values(["key","version_tuple"])
        # mark active = True only for max version per key
        df["active"] = False
        idx = df.groupby("key")["version_tuple"].transform(lambda x: x==x.max())
        df.loc[idx, "active"] = True
        df = df.drop(columns=["version_tuple"])

    df.to_csv(out_csv, index=False)
    return out_csv

def save_uploads(files, target_root: Path, overwrite_same_name: bool=False) -> list[Path]:
    saved = []
    target_root.mkdir(parents=True, exist_ok=True)
    for f in files:
        p = target_root / f.name
        if p.exists() and not overwrite_same_name:
            # make unique
            p = target_root / f"__{int(time.time())}__{f.name}"
        with open(p, "wb") as out:
            out.write(f.read())
        saved.append(p)
    return saved
