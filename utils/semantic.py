
from typing import List, Dict, Any, Optional
import math

# We try to use sentence-transformers if available; else fall back to TF-IDF cosine.
class SemanticIndex:
    def __init__(self):
        self.backend = None
        self.items: List[Dict[str,Any]] = []
        self.emb = None
        self.vectorizer = None

    def build(self, items: List[Dict[str,Any]]):
        self.items = items
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np
            self.backend = "st"
            self.model = SentenceTransformer("all-MiniLM-L6-v2")
            self.emb = self.model.encode([x["text"] for x in items], show_progress_bar=False, normalize_embeddings=True)
        except Exception:
            # TF-IDF fallback
            from sklearn.feature_extraction.text import TfidfVectorizer
            self.backend = "tfidf"
            self.vectorizer = TfidfVectorizer(stop_words="english", max_features=20000)
            self.emb = self.vectorizer.fit_transform([x["text"] for x in items])

    def query(self, q: str, k: int=3) -> List[Dict[str,Any]]:
        if not self.items:
            return []
        if self.backend == "st":
            import numpy as np
            qv = self.model.encode([q], normalize_embeddings=True)
            sims = (self.emb @ qv[0]).tolist()
            idx = sorted(range(len(sims)), key=lambda i: sims[i], reverse=True)[:k]
            return [dict(source=self.items[i]["source"], snippet=self.items[i]["text"][:200].replace("\\n"," "), score=float(sims[i])) for i in idx]
        else:
            # TF-IDF cosine
            from sklearn.metrics.pairwise import cosine_similarity
            qv = self.vectorizer.transform([q])
            sims = cosine_similarity(self.emb, qv).ravel()
            idx = sims.argsort()[::-1][:k]
            return [dict(source=self.items[i]["source"], snippet=self.items[i]["text"][:200].replace("\\n"," "), score=float(sims[i])) for i in idx]
