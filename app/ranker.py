"""PageRank-style graph ranking."""

from __future__ import annotations

from collections import defaultdict

from .database import SearchDatabase


class PageRanker:
    """Iterative PageRank implementation with damping."""

    def __init__(self, db: SearchDatabase, damping: float = 0.85, iterations: int = 30) -> None:
        self.db = db
        self.damping = damping
        self.iterations = iterations

    def compute(self) -> dict[str, float]:
        """Compute PageRank from persisted pages and links, then store scores."""
        pages = [row["url"] for row in self.db.get_pages()]
        if not pages:
            self.db.replace_pagerank({})
            return {}

        scores = self.compute_from_graph(pages, [(row["source_url"], row["target_url"]) for row in self.db.get_links()])
        self.db.replace_pagerank(scores)
        return scores

    def compute_from_graph(self, pages: list[str], links: list[tuple[str, str]]) -> dict[str, float]:
        """Compute PageRank for a graph represented as URL nodes and directed edges."""
        page_set = set(pages)
        n = len(page_set)
        if n == 0:
            return {}

        outgoing: dict[str, set[str]] = defaultdict(set)
        for source, target in links:
            if source in page_set and target in page_set and source != target:
                outgoing[source].add(target)

        scores = {url: 1.0 / n for url in page_set}
        base = (1.0 - self.damping) / n

        for _ in range(self.iterations):
            new_scores = {url: base for url in page_set}
            dangling_total = sum(scores[url] for url in page_set if not outgoing.get(url))
            dangling_share = self.damping * dangling_total / n
            for url in page_set:
                new_scores[url] += dangling_share
            for source, targets in outgoing.items():
                if not targets:
                    continue
                share = self.damping * scores[source] / len(targets)
                for target in targets:
                    new_scores[target] += share
            scores = new_scores

        total = sum(scores.values())
        return {url: score / total for url, score in scores.items()} if total else scores
