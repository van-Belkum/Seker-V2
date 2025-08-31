import pickle
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

class GuidanceIndex:
    def __init__(self, index, meta, model_name="sentence-transformers/all-MiniLM-L6-v2"):
        self.index = index
        self.meta = meta
        self.model = SentenceTransformer(model_name)

    @staticmethod
    def load(path_base: str):
        index = faiss.read_index(f"{path_base}.faiss")
        with open(f"{path_base}.pkl", "rb") as f:
            meta = pickle.load(f)
        return GuidanceIndex(index, meta)

    def embed(self, texts):
        if isinstance(texts, str):
            texts = [texts]
        return np.array(self.model.encode(texts, normalize_embeddings=True), dtype="float32")

    def search(self, query: str, k: int = 8):
        qv = self.embed(query)
        D, I = self.index.search(qv, k)
        out = []
        for score, idx in zip(D[0], I[0]):
            if idx < 0:
                continue
            m = self.meta[idx]
            out.append({"score": float(score), **m})
        return out
