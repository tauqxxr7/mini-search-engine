"""Seed the local SQLite database with deterministic demo pages."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SearchDatabase
from app.indexer import InvertedIndexer
from app.ranker import PageRanker


PAGES = [
    {
        "url": "https://demo.local/search-infra",
        "title": "Search Infrastructure for Machine Learning",
        "headings": ["Machine Learning Search Systems"],
        "content": "Machine learning search systems combine crawling, indexing, BM25 ranking, PageRank, and freshness signals.",
    },
    {
        "url": "https://demo.local/bm25",
        "title": "BM25 Ranking Explained",
        "headings": ["Ranking Engine"],
        "content": "BM25 improves search relevance by balancing term frequency, inverse document frequency, and document length.",
    },
    {
        "url": "https://demo.local/crawler",
        "title": "Polite Web Crawler",
        "headings": ["Crawler Pipeline"],
        "content": "A polite crawler respects robots.txt, parses sitemap files, normalizes URLs, and avoids duplicate pages.",
    },
    {
        "url": "https://demo.local/scaling",
        "title": "Scaling a Search Engine",
        "headings": ["Distributed Index"],
        "content": "Distributed search engines shard the inverted index, fan out queries, merge top results, and cache hot queries.",
    },
]


def main() -> None:
    db = SearchDatabase()
    db.clear_all()
    for page in PAGES:
        content_hash = sha256(page["content"].encode("utf-8")).hexdigest()
        db.upsert_page(
            url=page["url"],
            title=page["title"],
            headings=page["headings"],
            content=page["content"],
            metadata={"description": page["content"][:120]},
            content_hash=content_hash,
            status_code=200,
        )
    db.add_links("https://demo.local/search-infra", ["https://demo.local/bm25", "https://demo.local/scaling"])
    db.add_links("https://demo.local/crawler", ["https://demo.local/search-infra"])
    db.add_links("https://demo.local/scaling", ["https://demo.local/search-infra", "https://demo.local/bm25"])
    InvertedIndexer(db).rebuild()
    PageRanker(db).compute()
    db.record_crawl_metric("https://demo.local", 412.0, len(PAGES))
    db.close()
    print(f"Seeded {len(PAGES)} demo pages.")


if __name__ == "__main__":
    main()
