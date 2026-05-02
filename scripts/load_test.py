"""Run a small local query load test against the Flask API."""

from __future__ import annotations

import argparse
import statistics
import time
from urllib.parse import urlencode
from urllib.request import urlopen


QUERIES = [
    "search",
    "machine learning",
    '"machine learning"',
    "title:BM25",
    "crawler AND sitemap",
    "ranking OR PageRank",
    "search NOT cooking",
    "distributed index",
]


def request(url: str) -> float:
    start = time.perf_counter()
    with urlopen(url, timeout=10) as response:
        response.read()
    return (time.perf_counter() - start) * 1000


def main() -> None:
    parser = argparse.ArgumentParser(description="Load test the Mini Search Engine query API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000")
    parser.add_argument("--queries", type=int, default=100)
    args = parser.parse_args()

    latencies = []
    for index in range(args.queries):
        query = QUERIES[index % len(QUERIES)]
        url = f"{args.base_url}/api/search?{urlencode({'q': query})}"
        latencies.append(request(url))

    print(f"queries={len(latencies)}")
    print(f"avg_latency_ms={statistics.mean(latencies):.2f}")
    print(f"p95_latency_ms={statistics.quantiles(latencies, n=20)[18]:.2f}")
    print(f"min_latency_ms={min(latencies):.2f}")
    print(f"max_latency_ms={max(latencies):.2f}")


if __name__ == "__main__":
    main()

