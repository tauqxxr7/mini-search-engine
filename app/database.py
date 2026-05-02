"""SQLite persistence for crawled pages, inverted index, and link graph."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT_DIR / "data" / "search_engine.db"


class SearchDatabase:
    """Small SQLite wrapper with explicit methods for the search pipeline."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.initialize()

    def initialize(self) -> None:
        """Create all tables required by the crawler and searcher."""
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                headings TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                crawled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS links (
                source_url TEXT NOT NULL,
                target_url TEXT NOT NULL,
                UNIQUE(source_url, target_url)
            );

            CREATE TABLE IF NOT EXISTS terms (
                term TEXT PRIMARY KEY,
                document_frequency INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS postings (
                term TEXT NOT NULL,
                page_id INTEGER NOT NULL,
                term_frequency INTEGER NOT NULL,
                PRIMARY KEY(term, page_id),
                FOREIGN KEY(page_id) REFERENCES pages(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS pagerank (
                url TEXT PRIMARY KEY,
                score REAL NOT NULL
            );
            """
        )
        self.conn.commit()

    def clear_index(self) -> None:
        """Remove derived index and rank data while preserving crawled pages."""
        self.conn.executescript("DELETE FROM terms; DELETE FROM postings; DELETE FROM pagerank;")
        self.conn.commit()

    def clear_all(self) -> None:
        """Remove pages, links, index data, and rank data."""
        self.conn.executescript(
            "DELETE FROM links; DELETE FROM postings; DELETE FROM terms; DELETE FROM pagerank; DELETE FROM pages;"
        )
        self.conn.commit()

    def upsert_page(
        self,
        *,
        url: str,
        title: str,
        headings: list[str],
        content: str,
        metadata: dict[str, str],
        status_code: int,
    ) -> int:
        """Insert or update a crawled page and return its page id."""
        self.conn.execute(
            """
            INSERT INTO pages(url, title, headings, content, metadata, status_code)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                title=excluded.title,
                headings=excluded.headings,
                content=excluded.content,
                metadata=excluded.metadata,
                status_code=excluded.status_code,
                crawled_at=CURRENT_TIMESTAMP
            """,
            (url, title, json.dumps(headings), content, json.dumps(metadata), status_code),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT id FROM pages WHERE url = ?", (url,)).fetchone()
        return int(row["id"])

    def add_links(self, source_url: str, target_urls: Iterable[str]) -> None:
        """Persist source-to-target edges for PageRank."""
        self.conn.executemany(
            "INSERT OR IGNORE INTO links(source_url, target_url) VALUES (?, ?)",
            [(source_url, target_url) for target_url in target_urls],
        )
        self.conn.commit()

    def replace_terms(self, document_frequencies: dict[str, int], postings: list[tuple[str, int, int]]) -> None:
        """Replace the inverted index with a newly computed one."""
        self.conn.executescript("DELETE FROM terms; DELETE FROM postings;")
        self.conn.executemany(
            "INSERT INTO terms(term, document_frequency) VALUES (?, ?)",
            sorted(document_frequencies.items()),
        )
        self.conn.executemany(
            "INSERT INTO postings(term, page_id, term_frequency) VALUES (?, ?, ?)",
            postings,
        )
        self.conn.commit()

    def replace_pagerank(self, scores: dict[str, float]) -> None:
        """Replace PageRank scores."""
        self.conn.execute("DELETE FROM pagerank;")
        self.conn.executemany(
            "INSERT INTO pagerank(url, score) VALUES (?, ?)",
            sorted(scores.items()),
        )
        self.conn.commit()

    def get_pages(self) -> list[sqlite3.Row]:
        """Return all indexed pages."""
        return list(self.conn.execute("SELECT * FROM pages ORDER BY id"))

    def get_links(self) -> list[sqlite3.Row]:
        """Return all graph edges."""
        return list(self.conn.execute("SELECT source_url, target_url FROM links"))

    def close(self) -> None:
        """Close the SQLite connection."""
        self.conn.close()

