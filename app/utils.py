import re
from typing import List, Tuple
import jieba


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text


def chunk_text(text: str, max_chars: int = 800, overlap: int = 120) -> List[str]:
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text]
    chunks: List[str] = []
    buf = ""
    for p in paragraphs:
        if len(buf) + len(p) + 1 <= max_chars:
            buf = f"{buf}\n{p}".strip() if buf else p
        else:
            if buf:
                chunks.append(buf)
            if len(p) <= max_chars:
                buf = p
            else:
                step = max_chars - overlap if max_chars > overlap else max_chars
                i = 0
                while i < len(p):
                    chunks.append(p[i : i + max_chars])
                    i += step
                buf = ""
    if buf:
        chunks.append(buf)
    return chunks


def _ngrams(tokens: List[str], n: int = 2) -> List[str]:
    if n <= 1:
        return tokens
    grams: List[str] = []
    for i in range(len(tokens) - n + 1):
        grams.append("_".join(tokens[i : i + n]).lower())
    return grams


def tokenize(text: str, add_bigrams: bool = True) -> List[str]:
    cn_tokens = list(jieba.cut(text, cut_all=False))
    en_tokens = re.findall(r"[A-Za-z0-9]+", text)
    tokens = [t.lower() for t in cn_tokens + en_tokens if t.strip()]
    if add_bigrams:
        tokens += _ngrams(tokens, 2)
    return tokens


def char_trigrams(text: str) -> List[str]:
    t = clean_text(text)
    grams: List[str] = []
    for i in range(len(t) - 2):
        grams.append(t[i : i + 3].lower())
    return grams
