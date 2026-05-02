"""Search service combining TF-IDF and PageRank scores."""

from __future__ import annotations

import json
from dataclasses import dataclass

from .database import SearchDatabase
from .indexer import InvertedIndexer
from .utils import build_snippet, tokenize


@dataclass(frozen=True)
class SearchResult:
    """Ranked search result returned by the UI and API."""

    title: str
    url: str
    snippet: str
    tfidf_score: float
    pagerank_score: float
    final_score: float

    def to_dict(self) -> dict[str, str | float]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "tfidf_score": round(self.tfidf_score, 6),
            "pagerank_score": round(self.pagerank_score, 6),
            "final_score": round(self.final_score, 6),
        }


class SearchService:
    """Keyword search over the persisted inverted index."""

    def __init__(self, db: SearchDatabase) -> None:
        self.db = db

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Return ranked search results for query."""
        terms = tokenize(query)
        if not terms:
            return []

        total_documents = self.db.conn.execute("SELECT COUNT(*) AS count FROM pages").fetchone()["count"]
        if total_documents == 0:
            return []

        page_scores: dict[int, float] = {}
        for term in terms:
            term_row = self.db.conn.execute("SELECT document_frequency FROM terms WHERE term = ?", (term,)).fetchone()
            if term_row is None:
                continue
            postings = self.db.conn.execute(
                "SELECT page_id, term_frequency FROM postings WHERE term = ?",
                (term,),
            ).fetchall()
            for posting in postings:
                score = InvertedIndexer.tfidf(
                    int(posting["term_frequency"]),
                    int(term_row["document_frequency"]),
                    int(total_documents),
                )
                page_scores[int(posting["page_id"])] = page_scores.get(int(posting["page_id"]), 0.0) + score

        if not page_scores:
            return []

        max_tfidf = max(page_scores.values()) or 1.0
        results: list[SearchResult] = []
        for page_id, tfidf_score in page_scores.items():
            page = self.db.conn.execute("SELECT * FROM pages WHERE id = ?", (page_id,)).fetchone()
            rank = self.db.conn.execute("SELECT score FROM pagerank WHERE url = ?", (page["url"],)).fetchone()
            pagerank_score = float(rank["score"]) if rank else 0.0
            normalized_tfidf = tfidf_score / max_tfidf
            final_score = 0.65 * normalized_tfidf + 0.35 * pagerank_score
            headings = json.loads(page["headings"])
            text = " ".join([page["title"], *headings, page["content"]])
            results.append(
                SearchResult(
                    title=page["title"],
                    url=page["url"],
                    snippet=build_snippet(text, terms),
                    tfidf_score=normalized_tfidf,
                    pagerank_score=pagerank_score,
                    final_score=final_score,
                )
            )

        return sorted(results, key=lambda result: result.final_score, reverse=True)[:limit]

