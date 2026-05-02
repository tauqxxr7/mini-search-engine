"""Synthetic benchmark for indexing and query serving."""

from __future__ import annotations

import argparse
import statistics
import sys
import time
import tracemalloc
from hashlib import sha256
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SearchDatabase
from app.indexer import InvertedIndexer
from app.ranker import PageRanker
from app.search import SearchService


def make_content(index: int) -> str:
    topic = ["search", "crawler", "ranking", "index", "distributed"][index % 5]
    return (
        f"Page {index} covers {topic} systems, BM25 ranking, PageRank authority, "
        f"query latency, inverted indexes, and scalable search infrastructure."
    )


def run_benchmark(pages: int) -> dict[str, float | int]:
    db = SearchDatabase(":memory:")
    tracemalloc.start()
    crawl_start = time.perf_counter()
    for index in range(pages):
        content = make_content(index)
        db.upsert_page(
            url=f"https://benchmark.local/page-{index}",
            title=f"Benchmark Search Page {index}",
            headings=["Search Benchmark"],
            content=content,
            metadata={},
            content_hash=sha256(content.encode("utf-8")).hexdigest(),
            status_code=200,
        )
        if index > 0:
            db.add_links(f"https://benchmark.local/page-{index}", [f"https://benchmark.local/page-{index - 1}"])
    crawl_ms = (time.perf_counter() - crawl_start) * 1000

    index_stats = InvertedIndexer(db).rebuild()
    PageRanker(db).compute()
    service = SearchService(db)
    latencies = []
    for query in ["search", "BM25 ranking", "crawler AND index", "title:Benchmark"] * 10:
        start = time.perf_counter()
        service.search(query)
        latencies.append((time.perf_counter() - start) * 1000)

    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    db.close()
    return {
        "pages": pages,
        "crawl_duration_ms": crawl_ms,
        "indexing_time_ms": float(index_stats["indexing_time_ms"]),
        "avg_query_latency_ms": statistics.mean(latencies),
        "peak_memory_mb": peak / (1024 * 1024),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run synthetic search-engine benchmarks.")
    parser.add_argument("--pages", type=int, nargs="+", default=[100, 500])
    args = parser.parse_args()
    for pages in args.pages:
        result = run_benchmark(pages)
        print(
            "pages={pages} crawl_duration_ms={crawl_duration_ms:.2f} "
            "indexing_time_ms={indexing_time_ms:.2f} avg_query_latency_ms={avg_query_latency_ms:.2f} "
            "peak_memory_mb={peak_memory_mb:.2f}".format(**result)
        )


if __name__ == "__main__":
    main()
