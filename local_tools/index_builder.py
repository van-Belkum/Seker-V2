import argparse, os, pickle, faiss, numpy as np
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from utils.text_extract import extract_text_from_docx, extract_text_from_pptx, extract_text_from_pdf

EXT_MAP = {
    ".docx": extract_text_from_docx,
    ".pptx": extract_text_from_pptx,
    ".pdf":  extract_text_from_pdf,
}

def iter_files(root):
    for dirpath, _, files in os.walk(root):
        for fn in files:
            ext = os.path.splitext(fn)[1].lower()
            if ext in EXT_MAP:
                yield os.path.join(dirpath, fn), ext

def chunk_text(text, chunk_size=1200, overlap=200):
    if not text:
        return []
    words = text.split()
    out=[]
    i=0
    while i < len(words):
        seg = " ".join(words[i:i+chunk_size])
        out.append(seg)
        i += (chunk_size - overlap)
    return out

def main():
    import sys
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True, help="path base, no extension")
    args = ap.parse_args()

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    meta=[]
    vecs=[]
    files = list(iter_files(args.root))
    if not files:
        print("No input files found under", args.root); sys.exit(1)

    for path, ext in tqdm(files, desc="Indexing"):
        try:
            text = EXT_MAP[ext](path)
        except Exception as e:
            print("SKIP", path, e); continue
        chunks = chunk_text(text)
        for ch in chunks:
            meta.append({"source": path, "chunk": ch})
            vecs.append(model.encode(ch, normalize_embeddings=True))

    if not vecs:
        print("No text extracted."); sys.exit(1)

    X = np.array(vecs, dtype="float32")
    dim = X.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(X)

    faiss.write_index(index, f"{args.out}.faiss")
    with open(f"{args.out}.pkl", "wb") as f:
        pickle.dump(meta, f)

    print("Wrote:", f"{args.out}.faiss", f"{args.out}.pkl")

if __name__ == "__main__":
    main()
