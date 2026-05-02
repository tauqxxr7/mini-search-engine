"""Advanced query service with BM25, boolean search, phrases, and autocomplete."""

from __future__ import annotations

import html
import json
import logging
import re
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import get_close_matches

from .database import SearchDatabase
from .indexer import InvertedIndexer
from .utils import build_snippet, tokenize

LOGGER = logging.getLogger(__name__)
QUERY_CACHE: OrderedDict[tuple[str, int, int], tuple[list["SearchResult"], float, str | None]] = OrderedDict()
CACHE_SIZE = 128


@dataclass(frozen=True)
class SearchResult:
    """Ranked search result returned by the UI and API."""

    title: str
    url: str
    snippet: str
    bm25_score: float
    pagerank_score: float
    freshness_score: float
    final_score: float

    def to_dict(self) -> dict[str, str | float]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "bm25_score": round(self.bm25_score, 6),
            "pagerank_score": round(self.pagerank_score, 6),
            "freshness_score": round(self.freshness_score, 6),
            "final_score": round(self.final_score, 6),
        }


@dataclass(frozen=True)
class SearchResponse:
    """Search response plus query diagnostics."""

    results: list[SearchResult]
    query_time_ms: float
    did_you_mean: str | None = None


class TrieNode:
    """Node for prefix autocomplete."""

    def __init__(self) -> None:
        self.children: dict[str, TrieNode] = {}
        self.is_term = False


class AutocompleteTrie:
    """Small in-memory trie built from indexed vocabulary."""

    def __init__(self, terms: list[str]) -> None:
        self.root = TrieNode()
        for term in terms:
            self.insert(term)

    def insert(self, term: str) -> None:
        node = self.root
        for char in term:
            node = node.children.setdefault(char, TrieNode())
        node.is_term = True

    def suggest(self, prefix: str, limit: int = 8) -> list[str]:
        node = self.root
        for char in prefix.lower():
            if char not in node.children:
                return []
            node = node.children[char]
        suggestions: list[str] = []
        self._collect(node, prefix.lower(), suggestions, limit)
        return suggestions

    def _collect(self, node: TrieNode, prefix: str, suggestions: list[str], limit: int) -> None:
        if len(suggestions) >= limit:
            return
        if node.is_term:
            suggestions.append(prefix)
        for char in sorted(node.children):
            self._collect(node.children[char], prefix + char, suggestions, limit)


class SearchService:
    """Keyword, phrase, boolean, and field search over the persisted index."""

    FIELD_RE = re.compile(r"^(title):(.+)$", re.IGNORECASE)
    TOKEN_RE = re.compile(r'"[^"]+"|\bAND\b|\bOR\b|\bNOT\b|[^\s]+', re.IGNORECASE)

    def __init__(self, db: SearchDatabase) -> None:
        self.db = db

    def search(self, query: str, limit: int = 10) -> SearchResponse:
        """Return ranked results and query latency diagnostics."""
        start = time.perf_counter()
        cache_key = (query.strip().lower(), limit, self._index_version())
        if cache_key in QUERY_CACHE:
            results, cached_ms, suggestion = QUERY_CACHE[cache_key]
            QUERY_CACHE.move_to_end(cache_key)
            return SearchResponse(results=results, query_time_ms=cached_ms, did_you_mean=suggestion)

        results = self._search_uncached(query, limit)
        query_time_ms = (time.perf_counter() - start) * 1000
        suggestion = self.did_you_mean(query) if not results else None
        QUERY_CACHE[cache_key] = (results, query_time_ms, suggestion)
        if len(QUERY_CACHE) > CACHE_SIZE:
            QUERY_CACHE.popitem(last=False)

        self.db.record_query_metric(query, query_time_ms, len(results))
        LOGGER.info("query=%r latency_ms=%.2f results=%s", query, query_time_ms, len(results))
        return SearchResponse(results=results, query_time_ms=query_time_ms, did_you_mean=suggestion)

    def autocomplete(self, prefix: str, limit: int = 8) -> list[str]:
        """Return prefix suggestions from the indexed term dictionary."""
        terms = [row["term"] for row in self.db.conn.execute("SELECT term FROM terms ORDER BY term")]
        return AutocompleteTrie(terms).suggest(prefix, limit)

    def did_you_mean(self, query: str) -> str | None:
        """Return a basic spelling correction for a single-term query."""
        terms = [row["term"] for row in self.db.conn.execute("SELECT term FROM terms")]
        query_terms = tokenize(query)
        if len(query_terms) != 1:
            return None
        matches = get_close_matches(query_terms[0], terms, n=1, cutoff=0.74)
        return matches[0] if matches else None

    def _search_uncached(self, query: str, limit: int) -> list[SearchResult]:
        parsed = self._parse_query(query)
        query_terms = parsed["terms"]
        phrases = parsed["phrases"]
        field_terms = parsed["field_terms"]
        if not query_terms and not phrases and not field_terms:
            return []

        total_documents = self.db.conn.execute("SELECT COUNT(*) AS count FROM pages").fetchone()["count"]
        if total_documents == 0:
            return []
        average_length = self.db.conn.execute("SELECT COALESCE(AVG(doc_length), 1) AS avg_len FROM pages").fetchone()[
            "avg_len"
        ]

        candidate_ids = self._candidate_pages(parsed)
        if not candidate_ids:
            return []

        raw_scores: dict[int, float] = {}
        for term in set(query_terms + [term for _, term in field_terms]):
            term_row = self.db.conn.execute("SELECT document_frequency FROM terms WHERE term = ?", (term,)).fetchone()
            if term_row is None:
                continue
            postings = self.db.conn.execute(
                "SELECT page_id, term_frequency FROM postings WHERE term = ?",
                (term,),
            ).fetchall()
            for posting in postings:
                page_id = int(posting["page_id"])
                if page_id not in candidate_ids:
                    continue
                page = self.db.conn.execute("SELECT doc_length FROM pages WHERE id = ?", (page_id,)).fetchone()
                score = InvertedIndexer.bm25(
                    int(posting["term_frequency"]),
                    int(term_row["document_frequency"]),
                    int(total_documents),
                    int(page["doc_length"]),
                    float(average_length),
                )
                raw_scores[page_id] = raw_scores.get(page_id, 0.0) + score

        for phrase in phrases:
            for page_id in list(candidate_ids):
                page = self.db.conn.execute("SELECT content FROM pages WHERE id = ?", (page_id,)).fetchone()
                if phrase.lower() in page["content"].lower():
                    raw_scores[page_id] = raw_scores.get(page_id, 0.0) + 1.5

        for field, term in field_terms:
            if field != "title":
                continue
            for page_id in self._pages_for_title_term(term) & candidate_ids:
                raw_scores[page_id] = raw_scores.get(page_id, 0.0) + 2.0

        if not raw_scores:
            return []

        max_bm25 = max(raw_scores.values()) or 1.0
        max_rank = self.db.conn.execute("SELECT COALESCE(MAX(score), 0) AS score FROM pagerank").fetchone()["score"] or 1.0
        results: list[SearchResult] = []
        highlight_terms = query_terms + [term for _, term in field_terms] + [term for phrase in phrases for term in tokenize(phrase)]
        for page_id, bm25_score in raw_scores.items():
            page = self.db.conn.execute("SELECT * FROM pages WHERE id = ?", (page_id,)).fetchone()
            rank = self.db.conn.execute("SELECT score FROM pagerank WHERE url = ?", (page["url"],)).fetchone()
            pagerank_score = (float(rank["score"]) / float(max_rank)) if rank and max_rank else 0.0
            normalized_bm25 = bm25_score / max_bm25
            freshness = self._freshness_score(page["crawled_at"])
            final_score = 0.5 * normalized_bm25 + 0.3 * pagerank_score + 0.2 * freshness
            headings = json.loads(page["headings"])
            text = " ".join([page["title"], *headings, page["content"]])
            snippet = self._highlight(build_snippet(text, highlight_terms), highlight_terms)
            results.append(
                SearchResult(
                    title=page["title"],
                    url=page["url"],
                    snippet=snippet,
                    bm25_score=normalized_bm25,
                    pagerank_score=pagerank_score,
                    freshness_score=freshness,
                    final_score=final_score,
                )
            )

        return sorted(results, key=lambda result: result.final_score, reverse=True)[:limit]

    def _candidate_pages(self, parsed: dict[str, list]) -> set[int]:
        all_ids = {int(row["id"]) for row in self.db.conn.execute("SELECT id FROM pages")}
        positive_sets: list[set[int]] = []
        or_sets: list[set[int]] = []
        excluded: set[int] = set()

        for term in parsed["terms"]:
            ids = self._pages_for_term(term)
            if parsed["has_or"]:
                or_sets.append(ids)
            else:
                positive_sets.append(ids)
        for phrase in parsed["phrases"]:
            positive_sets.append(self._pages_for_phrase(phrase))
        for field, term in parsed["field_terms"]:
            if field == "title":
                positive_sets.append(self._pages_for_title_term(term))
        for term in parsed["not_terms"]:
            excluded.update(self._pages_for_term(term))

        candidates = set.union(*or_sets) if or_sets else all_ids
        for ids in positive_sets:
            candidates &= ids
        return candidates - excluded

    def _parse_query(self, query: str) -> dict[str, list]:
        tokens = self.TOKEN_RE.findall(query)
        terms: list[str] = []
        phrases: list[str] = []
        field_terms: list[tuple[str, str]] = []
        not_terms: list[str] = []
        or_terms: list[str] = []
        mode = "AND"
        has_or = any(token.upper() == "OR" for token in tokens)

        for token in tokens:
            upper = token.upper()
            if upper in {"AND", "OR", "NOT"}:
                mode = upper
                continue
            if token.startswith('"') and token.endswith('"'):
                phrases.append(token.strip('"'))
                mode = "AND"
                continue
            field_match = self.FIELD_RE.match(token)
            parsed_terms = tokenize(field_match.group(2) if field_match else token)
            for term in parsed_terms:
                if field_match:
                    field_terms.append((field_match.group(1).lower(), term))
                elif mode == "NOT":
                    not_terms.append(term)
                elif mode == "OR":
                    terms.append(term)
                    or_terms.append(term)
                else:
                    terms.append(term)
            mode = "AND"

        return {
            "terms": terms,
            "phrases": phrases,
            "field_terms": field_terms,
            "not_terms": not_terms,
            "or_terms": or_terms,
            "has_or": has_or,
        }

    def _pages_for_term(self, term: str) -> set[int]:
        return {
            int(row["page_id"])
            for row in self.db.conn.execute("SELECT page_id FROM postings WHERE term = ?", (term,))
        }

    def _pages_for_phrase(self, phrase: str) -> set[int]:
        lowered = phrase.lower()
        return {
            int(row["id"])
            for row in self.db.conn.execute("SELECT id, content FROM pages")
            if lowered in row["content"].lower()
        }

    def _pages_for_title_term(self, term: str) -> set[int]:
        return {
            int(row["id"])
            for row in self.db.conn.execute("SELECT id, title FROM pages")
            if term in tokenize(row["title"])
        }

    def _freshness_score(self, crawled_at: str) -> float:
        try:
            crawled = datetime.fromisoformat(crawled_at.replace("Z", "+00:00"))
            if crawled.tzinfo is None:
                crawled = crawled.replace(tzinfo=timezone.utc)
        except ValueError:
            return 0.5
        age_days = max((datetime.now(timezone.utc) - crawled.astimezone(timezone.utc)).days, 0)
        return 1.0 / (1.0 + age_days / 30.0)

    def _highlight(self, snippet: str, terms: list[str]) -> str:
        escaped = html.escape(snippet)
        for term in sorted(set(terms), key=len, reverse=True):
            escaped = re.sub(
                rf"({re.escape(html.escape(term))})",
                r"<strong>\1</strong>",
                escaped,
                flags=re.IGNORECASE,
            )
        return escaped

    def _index_version(self) -> int:
        row = self.db.conn.execute("SELECT COUNT(*) AS count FROM postings").fetchone()
        return int(row["count"])
