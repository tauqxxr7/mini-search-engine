"""Shared URL and text utilities for crawling and indexing."""

from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

STOPWORDS: set[str] = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "he",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "was",
    "were",
    "will",
    "with",
    "you",
    "your",
}

TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")


def normalize_url(url: str, base_url: str | None = None) -> str:
    """Return a canonical HTTP(S) URL with fragments removed."""
    joined = urljoin(base_url, url) if base_url else url
    parsed = urlparse(joined.strip())
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    if netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    query_pairs = sorted(parse_qsl(parsed.query, keep_blank_values=False))
    query = urlencode(query_pairs, doseq=True)
    return urlunparse((scheme, netloc, path, "", query, ""))


def same_domain(url: str, seed_url: str) -> bool:
    """Return True when url belongs to the same hostname as seed_url."""
    return urlparse(url).netloc.lower() == urlparse(seed_url).netloc.lower()


def is_http_url(url: str) -> bool:
    """Return True for crawlable HTTP and HTTPS URLs."""
    return urlparse(url).scheme.lower() in {"http", "https"}


def tokenize(text: str, *, remove_stopwords: bool = True) -> list[str]:
    """Tokenize free text into normalized terms."""
    tokens = [match.group(0).lower() for match in TOKEN_RE.finditer(text)]
    if remove_stopwords:
        return [token for token in tokens if token not in STOPWORDS and len(token) > 1]
    return tokens


def build_snippet(text: str, query_terms: Iterable[str], size: int = 220) -> str:
    """Build a compact result snippet around the first query term match."""
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) <= size:
        return clean
    lowered = clean.lower()
    positions = [lowered.find(term.lower()) for term in query_terms if lowered.find(term.lower()) >= 0]
    start = max(0, min(positions) - 70) if positions else 0
    end = min(len(clean), start + size)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(clean) else ""
    return f"{prefix}{clean[start:end].strip()}{suffix}"

