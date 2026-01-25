from typing import List, Dict, Tuple
from rank_bm25 import BM25Okapi
from .utils import tokenize, char_trigrams


def _min_max_norm(scores: List[float]) -> List[float]:
    if not scores:
        return scores
    mn = min(scores)
    mx = max(scores)
    if mx == mn:
        return [1.0 for _ in scores]
    return [(s - mn) / (mx - mn) for s in scores]


class HybridIndex:
    def __init__(self, chunks: List[Dict]):
        # 过滤掉 enabled=False 的 chunks
        self.chunks = [c for c in chunks if c.get("enabled", True) is not False]
        self.corpus_tokens: List[List[str]] = [tokenize(c["text"]) for c in self.chunks]
        self.corpus_trigrams: List[List[str]] = [char_trigrams(c["text"]) for c in self.chunks]
        self.bm25 = BM25Okapi(self.corpus_tokens) if self.corpus_tokens else None

    def _jaccard(self, a: List[str], b: List[str]) -> float:
        sa, sb = set(a), set(b)
        if not sa or not sb:
            return 0.0
        inter = len(sa & sb)
        union = len(sa | sb)
        return inter / union if union else 0.0

    def _trigram_overlap(self, a: List[str], b: List[str]) -> float:
        sa, sb = set(a), set(b)
        if not sa or not sb:
            return 0.0
        inter = len(sa & sb)
        return inter / max(len(sa), len(sb))

    def search(self, query: str, top_k: int = 8) -> List[Tuple[Dict, float]]:
        if not self.chunks:
            return []
        q_tokens = tokenize(query)
        q_trigrams = char_trigrams(query)

        bm_scores: List[float]
        if self.bm25:
            bm_raw = list(self.bm25.get_scores(q_tokens))
            bm_scores = _min_max_norm([float(x) for x in bm_raw])
        else:
            bm_scores = [0.0 for _ in self.chunks]

        jac_scores: List[float] = []
        tri_scores: List[float] = []
        for i in range(len(self.chunks)):
            jac = self._jaccard(q_tokens, self.corpus_tokens[i])
            tri = self._trigram_overlap(q_trigrams, self.corpus_trigrams[i])
            jac_scores.append(jac)
            tri_scores.append(tri)

        # 权重：BM25 0.6 + Jaccard 0.25 + Trigram 0.15
        scores = []
        for i in range(len(self.chunks)):
            s = 0.6 * bm_scores[i] + 0.25 * jac_scores[i] + 0.15 * tri_scores[i]
            scores.append(s)

        ranked = sorted(
            [(self.chunks[i], float(scores[i])) for i in range(len(self.chunks))],
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked[:top_k]
