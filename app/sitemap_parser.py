"""Sitemap discovery and parsing."""

from __future__ import annotations

from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .utils import is_http_url, normalize_url, same_domain


class SitemapParser:
    """Fetch and parse sitemap.xml files for a seed domain."""

    def __init__(self, session: requests.Session | None = None, timeout: float = 10.0) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout

    def discover(self, seed_url: str, limit: int = 100) -> list[str]:
        """Return same-domain URLs from the seed domain's sitemap.xml, if present."""
        sitemap_url = urljoin(seed_url, "/sitemap.xml")
        try:
            response = self.session.get(sitemap_url, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException:
            return []

        soup = BeautifulSoup(response.text, "xml")
        urls: list[str] = []
        for loc in soup.find_all("loc"):
            if not loc.text:
                continue
            normalized = normalize_url(loc.text)
            if is_http_url(normalized) and same_domain(normalized, seed_url):
                urls.append(normalized)
            if len(urls) >= limit:
                break
        return list(dict.fromkeys(urls))

