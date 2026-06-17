from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Iterable, List, Set

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .models import SearchChunk, SearchMatch


SPANISH_STOPWORDS = {
    "a",
    "al",
    "algo",
    "ante",
    "antes",
    "como",
    "con",
    "contra",
    "cual",
    "cuando",
    "de",
    "del",
    "desde",
    "donde",
    "durante",
    "e",
    "el",
    "ella",
    "ellas",
    "ellos",
    "en",
    "entre",
    "era",
    "eran",
    "eres",
    "es",
    "esa",
    "esas",
    "ese",
    "eso",
    "esos",
    "esta",
    "estaba",
    "estado",
    "estan",
    "estar",
    "este",
    "esto",
    "estos",
    "fue",
    "fueron",
    "ha",
    "han",
    "hasta",
    "hay",
    "la",
    "las",
    "le",
    "les",
    "lo",
    "los",
    "mas",
    "me",
    "mi",
    "mis",
    "no",
    "nos",
    "o",
    "para",
    "pero",
    "por",
    "porque",
    "que",
    "se",
    "ser",
    "si",
    "sin",
    "sobre",
    "su",
    "sus",
    "tambien",
    "te",
    "tiene",
    "tienen",
    "tu",
    "un",
    "una",
    "uno",
    "unos",
    "y",
    "ya",
}


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", without_accents).strip()


def tokenize(text: str) -> Set[str]:
    return {token for token in normalize_text(text).split() if token and token not in SPANISH_STOPWORDS}


def token_similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0
    if len(left) >= 4 and len(right) >= 4 and (left in right or right in left):
        return 0.88
    return SequenceMatcher(None, left, right).ratio()


def fuzzy_threshold(token: str) -> float:
    return 0.45 if len(token) <= 4 else 0.72


def token_best_score(token: str, text_tokens: Set[str]) -> float:
    if not text_tokens:
        return 0.0
    best = max(token_similarity(token, text_token) for text_token in text_tokens)
    return best if best >= fuzzy_threshold(token) else 0.0


def build_query_token_weights(query_tokens: Set[str], chunk_token_sets: List[Set[str]]) -> dict[str, float]:
    weights: dict[str, float] = {}
    total_chunks = max(1, len(chunk_token_sets))
    for token in query_tokens:
        document_frequency = sum(
            1
            for chunk_tokens in chunk_token_sets
            if token_best_score(token, chunk_tokens) > 0
        )
        weights[token] = float(np.log((total_chunks + 1) / (document_frequency + 1)) + 1)
    return weights


def fuzzy_keyword_coverage_score(
    query_tokens: Set[str],
    text_tokens: Set[str],
    token_weights: dict[str, float],
) -> float:
    if not query_tokens:
        return 0.0

    if not text_tokens:
        return 0.0

    weighted_total = sum(token_weights.get(token, 1.0) for token in query_tokens)
    if weighted_total <= 0:
        return 0.0

    weighted_score = 0.0
    for token in query_tokens:
        weighted_score += token_weights.get(token, 1.0) * token_best_score(token, text_tokens)

    return weighted_score / weighted_total


class TfidfSearchEngine:
    def search(
        self,
        chunks: Iterable[SearchChunk],
        query: str,
        top_k: int,
        min_score: float,
    ) -> List[SearchMatch]:
        indexed_chunks = [chunk for chunk in chunks if chunk.text.strip()]
        if not indexed_chunks:
            return []

        try:
            word_vectorizer = TfidfVectorizer(
                lowercase=True,
                strip_accents="unicode",
                ngram_range=(1, 2),
                stop_words=list(SPANISH_STOPWORDS),
            )
            char_vectorizer = TfidfVectorizer(
                lowercase=True,
                strip_accents="unicode",
                analyzer="char_wb",
                ngram_range=(3, 5),
            )
            texts = [chunk.text for chunk in indexed_chunks]
            chunk_token_sets = [tokenize(text) for text in texts]
            query_tokens = tokenize(query)
            query_token_weights = build_query_token_weights(query_tokens, chunk_token_sets)

            word_matrix = word_vectorizer.fit_transform(texts)
            char_matrix = char_vectorizer.fit_transform(texts)
            word_scores = cosine_similarity(word_vectorizer.transform([query]), word_matrix).ravel()
            char_scores = cosine_similarity(char_vectorizer.transform([query]), char_matrix).ravel()
            coverage_scores = np.array(
                [
                    fuzzy_keyword_coverage_score(query_tokens, chunk_tokens, query_token_weights)
                    for chunk_tokens in chunk_token_sets
                ],
                dtype=float,
            )
            scores = (word_scores * 0.25) + (char_scores * 0.15) + (coverage_scores * 0.60)
        except ValueError:
            return []

        ranked = sorted(
            enumerate(scores),
            key=lambda item: item[1],
            reverse=True,
        )

        matches: List[SearchMatch] = []
        for index, score in ranked:
            if len(matches) >= top_k:
                break
            if score < min_score:
                continue
            chunk = indexed_chunks[index]
            chunk_data = chunk.model_dump() if hasattr(chunk, "model_dump") else chunk.dict()
            matches.append(SearchMatch(**chunk_data, score=round(float(score), 6)))

        return matches
