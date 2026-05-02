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
                content_hash TEXT NOT NULL DEFAULT '',
                doc_length INTEGER NOT NULL DEFAULT 0,
                status_code INTEGER NOT NULL,
                crawled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                indexed_at TEXT
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
                positions TEXT NOT NULL DEFAULT '[]',
                PRIMARY KEY(term, page_id),
                FOREIGN KEY(page_id) REFERENCES pages(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS pagerank (
                url TEXT PRIMARY KEY,
                score REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS query_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                latency_ms REAL NOT NULL,
                result_count INTEGER NOT NULL,
                searched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        """Add columns for users upgrading from an older local database."""
        table_columns = {
            row["name"] for row in self.conn.execute("PRAGMA table_info(pages)").fetchall()
        }
        if "content_hash" not in table_columns:
            self.conn.execute("ALTER TABLE pages ADD COLUMN content_hash TEXT NOT NULL DEFAULT ''")
        if "doc_length" not in table_columns:
            self.conn.execute("ALTER TABLE pages ADD COLUMN doc_length INTEGER NOT NULL DEFAULT 0")
        if "indexed_at" not in table_columns:
            self.conn.execute("ALTER TABLE pages ADD COLUMN indexed_at TEXT")
        posting_columns = {
            row["name"] for row in self.conn.execute("PRAGMA table_info(postings)").fetchall()
        }
        if "positions" not in posting_columns:
            self.conn.execute("ALTER TABLE postings ADD COLUMN positions TEXT NOT NULL DEFAULT '[]'")

    def clear_index(self) -> None:
        """Remove derived index and rank data while preserving crawled pages."""
        self.conn.executescript("DELETE FROM terms; DELETE FROM postings; DELETE FROM pagerank; UPDATE pages SET indexed_at = NULL;")
        self.conn.commit()

    def clear_all(self) -> None:
        """Remove pages, links, index data, and rank data."""
        self.conn.executescript(
            "DELETE FROM links; DELETE FROM postings; DELETE FROM terms; DELETE FROM pagerank; DELETE FROM query_metrics; DELETE FROM pages;"
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
        content_hash: str = "",
        status_code: int,
    ) -> int:
        """Insert or update a crawled page and return its page id."""
        existing = self.conn.execute("SELECT content_hash FROM pages WHERE url = ?", (url,)).fetchone()
        indexed_at_sql = "indexed_at" if existing and existing["content_hash"] == content_hash else "NULL"
        self.conn.execute(
            f"""
            INSERT INTO pages(url, title, headings, content, metadata, content_hash, status_code, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
            ON CONFLICT(url) DO UPDATE SET
                title=excluded.title,
                headings=excluded.headings,
                content=excluded.content,
                metadata=excluded.metadata,
                content_hash=excluded.content_hash,
                status_code=excluded.status_code,
                crawled_at=CURRENT_TIMESTAMP,
                indexed_at={indexed_at_sql}
            """,
            (url, title, json.dumps(headings), content, json.dumps(metadata), content_hash, status_code),
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

    def replace_terms(self, document_frequencies: dict[str, int], postings: list[tuple[str, int, int, str]]) -> None:
        """Replace the inverted index with a newly computed one."""
        self.conn.executescript("DELETE FROM terms; DELETE FROM postings;")
        self.conn.executemany(
            "INSERT INTO terms(term, document_frequency) VALUES (?, ?)",
            sorted(document_frequencies.items()),
        )
        self.conn.executemany(
            "INSERT INTO postings(term, page_id, term_frequency, positions) VALUES (?, ?, ?, ?)",
            postings,
        )
        self.conn.execute(
            "UPDATE pages SET indexed_at = CURRENT_TIMESTAMP WHERE id IN (SELECT DISTINCT page_id FROM postings)"
        )
        self.conn.commit()

    def upsert_postings(
        self,
        document_frequency_deltas: dict[str, int],
        postings: list[tuple[str, int, int, str]],
        indexed_page_ids: Iterable[int],
    ) -> None:
        """Incrementally add postings and update document frequencies."""
        for term, delta in document_frequency_deltas.items():
            self.conn.execute(
                """
                INSERT INTO terms(term, document_frequency) VALUES (?, ?)
                ON CONFLICT(term) DO UPDATE SET
                    document_frequency = document_frequency + excluded.document_frequency
                """,
                (term, delta),
            )
        self.conn.executemany(
            """
            INSERT INTO postings(term, page_id, term_frequency, positions) VALUES (?, ?, ?, ?)
            ON CONFLICT(term, page_id) DO UPDATE SET
                term_frequency=excluded.term_frequency,
                positions=excluded.positions
            """,
            postings,
        )
        self.conn.executemany(
            "UPDATE pages SET indexed_at = CURRENT_TIMESTAMP WHERE id = ?",
            [(page_id,) for page_id in indexed_page_ids],
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

    def get_unindexed_pages(self) -> list[sqlite3.Row]:
        """Return pages that need incremental indexing."""
        return list(self.conn.execute("SELECT * FROM pages WHERE indexed_at IS NULL ORDER BY id"))

    def get_links(self) -> list[sqlite3.Row]:
        """Return all graph edges."""
        return list(self.conn.execute("SELECT source_url, target_url FROM links"))

    def record_query_metric(self, query: str, latency_ms: float, result_count: int) -> None:
        """Store query latency for the metrics API."""
        self.conn.execute(
            "INSERT INTO query_metrics(query, latency_ms, result_count) VALUES (?, ?, ?)",
            (query, latency_ms, result_count),
        )
        self.conn.commit()

    def get_metrics(self) -> dict[str, float | int]:
        """Return operational metrics for the API."""
        row = self.conn.execute(
            """
            SELECT
                COUNT(*) AS query_count,
                COALESCE(AVG(latency_ms), 0) AS avg_latency_ms,
                COALESCE(MAX(latency_ms), 0) AS max_latency_ms
            FROM query_metrics
            """
        ).fetchone()
        pages = self.conn.execute("SELECT COUNT(*) AS count FROM pages").fetchone()["count"]
        indexed = self.conn.execute("SELECT COUNT(*) AS count FROM pages WHERE indexed_at IS NOT NULL").fetchone()["count"]
        return {
            "indexed_pages": int(indexed),
            "total_pages": int(pages),
            "query_count": int(row["query_count"]),
            "avg_latency_ms": float(row["avg_latency_ms"]),
            "max_latency_ms": float(row["max_latency_ms"]),
        }

    def get_stats(self, limit: int = 10) -> dict[str, object]:
        """Return index statistics for the API."""
        top_terms = [
            {"term": row["term"], "document_frequency": int(row["document_frequency"])}
            for row in self.conn.execute(
                "SELECT term, document_frequency FROM terms ORDER BY document_frequency DESC, term LIMIT ?",
                (limit,),
            )
        ]
        index_size = self.conn.execute("SELECT COUNT(*) AS count FROM postings").fetchone()["count"]
        return {"top_terms": top_terms, "index_size": int(index_size)}

    def close(self) -> None:
        """Close the SQLite connection."""
        self.conn.close()
