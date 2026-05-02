"""Inverted index and TF-IDF scoring."""

from __future__ import annotations

import math
from collections import Counter, defaultdict

from .database import SearchDatabase
from .utils import tokenize


class InvertedIndexer:
    """Builds an inverted index from persisted pages."""

    def __init__(self, db: SearchDatabase) -> None:
        self.db = db

    def rebuild(self) -> None:
        """Recompute terms, document frequencies, and postings from all pages."""
        pages = self.db.get_pages()
        document_frequencies: dict[str, int] = defaultdict(int)
        postings: list[tuple[str, int, int]] = []

        for page in pages:
            counts = Counter(tokenize(page["content"]))
            for term, frequency in counts.items():
                document_frequencies[term] += 1
                postings.append((term, int(page["id"]), int(frequency)))

        self.db.replace_terms(dict(document_frequencies), postings)

    @staticmethod
    def tfidf(term_frequency: int, document_frequency: int, total_documents: int) -> float:
        """Calculate a smoothed TF-IDF score."""
        if term_frequency <= 0 or document_frequency <= 0 or total_documents <= 0:
            return 0.0
        tf = 1.0 + math.log(term_frequency)
        idf = math.log((1 + total_documents) / (1 + document_frequency)) + 1.0
        return tf * idf

