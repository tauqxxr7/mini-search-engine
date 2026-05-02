"""Polite same-domain web crawler."""

from __future__ import annotations

import time
from hashlib import sha256
from collections import deque
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from .database import SearchDatabase
from .sitemap_parser import SitemapParser
from .utils import is_http_url, normalize_url, same_domain


@dataclass(frozen=True)
class CrawlStats:
    """Summary of a crawl run."""

    seed_url: str
    pages_crawled: int
    pages_seen: int
    errors: list[str]


class WebCrawler:
    """Bounded crawler that respects robots.txt where possible."""

    def __init__(
        self,
        db: SearchDatabase,
        *,
        user_agent: str = "MiniSearchEngineBot/1.0 (+educational project)",
        delay_seconds: float = 1.0,
        timeout: float = 10.0,
    ) -> None:
        self.db = db
        self.user_agent = user_agent
        self.delay_seconds = delay_seconds
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

    def crawl(self, seed_url: str, *, max_depth: int = 1, max_pages: int = 20, use_sitemap: bool = True) -> CrawlStats:
        """Crawl from seed_url and persist pages plus link graph edges."""
        seed = normalize_url(seed_url)
        if not is_http_url(seed):
            raise ValueError("Seed URL must use http or https.")

        robots = self._load_robots(seed)
        queue: deque[tuple[str, int]] = deque([(seed, 0)])
        if use_sitemap:
            for sitemap_url in SitemapParser(self.session, self.timeout).discover(seed, limit=max_pages):
                queue.append((sitemap_url, 0))

        visited: set[str] = set()
        errors: list[str] = []
        pages_crawled = 0

        while queue and pages_crawled < max_pages:
            url, depth = queue.popleft()
            if url in visited or depth > max_depth:
                continue
            visited.add(url)

            if not self._allowed_by_robots(robots, url):
                errors.append(f"Blocked by robots.txt: {url}")
                continue

            try:
                page = self._fetch_and_extract(url)
            except requests.RequestException as exc:
                errors.append(f"{url}: {exc}")
                continue

            if page is None:
                continue

            self.db.upsert_page(
                url=url,
                title=page["title"],
                headings=page["headings"],
                content=page["content"],
                metadata=page["metadata"],
                content_hash=page["content_hash"],
                status_code=page["status_code"],
            )
            self.db.add_links(url, page["links"])
            pages_crawled += 1

            if depth < max_depth:
                for link in page["links"]:
                    if link not in visited:
                        queue.append((link, depth + 1))

            time.sleep(self.delay_seconds)

        return CrawlStats(seed_url=seed, pages_crawled=pages_crawled, pages_seen=len(visited), errors=errors)

    def _load_robots(self, seed_url: str) -> RobotFileParser:
        robots = RobotFileParser()
        robots.set_url(urljoin(seed_url, "/robots.txt"))
        try:
            robots.read()
        except Exception:
            pass
        return robots

    def _allowed_by_robots(self, robots: RobotFileParser, url: str) -> bool:
        try:
            return robots.can_fetch(self.user_agent, url)
        except Exception:
            return True

    def _fetch_and_extract(self, url: str) -> dict[str, object] | None:
        response = self.session.get(url, timeout=self.timeout)
        if response.status_code >= 400:
            return None
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type.lower():
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        title = soup.title.string.strip() if soup.title and soup.title.string else url
        headings = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"]) if h.get_text(strip=True)]
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
        metadata = self._extract_metadata(soup)
        content = " ".join([title, *headings, *paragraphs]).strip()
        content_hash = sha256(content.encode("utf-8")).hexdigest()
        links = self._extract_links(soup.find_all("a", href=True), url)

        return {
            "title": title,
            "headings": headings,
            "content": content,
            "metadata": metadata,
            "content_hash": content_hash,
            "links": links,
            "status_code": response.status_code,
        }

    def _extract_metadata(self, soup: BeautifulSoup) -> dict[str, str]:
        metadata: dict[str, str] = {}
        for meta in soup.find_all("meta"):
            key = meta.get("name") or meta.get("property")
            value = meta.get("content")
            if key and value:
                metadata[str(key)] = str(value)
        return metadata

    def _extract_links(self, anchors: Iterable[object], source_url: str) -> list[str]:
        links: list[str] = []
        for anchor in anchors:
            href = anchor.get("href")  # type: ignore[attr-defined]
            if not href:
                continue
            normalized = normalize_url(str(href), source_url)
            if is_http_url(normalized) and same_domain(normalized, source_url):
                links.append(normalized)
        return list(dict.fromkeys(links))
