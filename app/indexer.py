"""Inverted index, positional postings, and BM25 scoring."""

from __future__ import annotations

import math
import time
from collections import Counter, defaultdict
import json

from .database import SearchDatabase
from .utils import tokenize


class InvertedIndexer:
    """Builds an inverted index from persisted pages."""

    def __init__(self, db: SearchDatabase) -> None:
        self.db = db

    def rebuild(self, *, incremental: bool = False) -> dict[str, float | int]:
        """Recompute terms, document frequencies, and postings from all pages."""
        start = time.perf_counter()
        pages = self.db.get_unindexed_pages() if incremental else self.db.get_pages()
        document_frequencies: dict[str, int] = defaultdict(int)
        postings: list[tuple[str, int, int, str]] = []
        indexed_page_ids: list[int] = []

        for page in pages:
            tokens = tokenize(page["content"])
            counts = Counter(tokens)
            for term, frequency in counts.items():
                document_frequencies[term] += 1
                positions = [index for index, token in enumerate(tokens) if token == term]
                postings.append((term, int(page["id"]), int(frequency), json.dumps(positions)))
            self.db.conn.execute(
                "UPDATE pages SET doc_length = ? WHERE id = ?",
                (len(tokens), int(page["id"])),
            )
            indexed_page_ids.append(int(page["id"]))

        if incremental:
            self.db.upsert_postings(dict(document_frequencies), postings, indexed_page_ids)
        else:
            self.db.replace_terms(dict(document_frequencies), postings)

        elapsed_ms = (time.perf_counter() - start) * 1000
        return {"indexed_pages": len(indexed_page_ids), "indexing_time_ms": elapsed_ms}

    @staticmethod
    def bm25(
        term_frequency: int,
        document_frequency: int,
        total_documents: int,
        document_length: int,
        average_document_length: float,
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> float:
        """Calculate BM25 relevance for one query term and one document."""
        if term_frequency <= 0 or document_frequency <= 0 or total_documents <= 0:
            return 0.0
        average_document_length = max(average_document_length, 1.0)
        idf = math.log(1 + (total_documents - document_frequency + 0.5) / (document_frequency + 0.5))
        denominator = term_frequency + k1 * (1 - b + b * document_length / average_document_length)
        return idf * ((term_frequency * (k1 + 1)) / denominator)

    @staticmethod
    def tfidf(term_frequency: int, document_frequency: int, total_documents: int) -> float:
        """Calculate a smoothed TF-IDF score."""
        if term_frequency <= 0 or document_frequency <= 0 or total_documents <= 0:
            return 0.0
        tf = 1.0 + math.log(term_frequency)
        idf = math.log((1 + total_documents) / (1 + document_frequency)) + 1.0
        return tf * idf
