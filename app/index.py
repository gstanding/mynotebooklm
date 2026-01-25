from typing import List, Dict, Tuple
from rank_bm25 import BM25Okapi
from .utils import tokenize


class Index:
    def __init__(self, chunks: List[Dict]):
        self.chunks = chunks
        self.corpus_tokens: List[List[str]] = [tokenize(c["text"]) for c in chunks]
        self.bm25 = BM25Okapi(self.corpus_tokens) if self.corpus_tokens else None

    def search(self, query: str, top_k: int = 6) -> List[Tuple[Dict, float]]:
        if not self.bm25 or not self.corpus_tokens:
            return []
        q_tokens = tokenize(query)
        scores = self.bm25.get_scores(q_tokens)
        ranked = sorted(
            [(self.chunks[i], float(scores[i])) for i in range(len(self.chunks))],
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked[:top_k]
