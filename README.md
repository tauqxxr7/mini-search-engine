# Mini Search Engine from Scratch

A production-minded Python search engine that demonstrates crawling, sitemap parsing, incremental indexing, BM25 ranking, PageRank authority, advanced query parsing, autocomplete, metrics, and a clean Flask UI/API.

## One-Line Pitch

I built a miniature Google-style search stack from first principles: crawler service, index service, ranking service, and query service, all small enough to read but serious enough to discuss in a FAANG system design interview.

## How Google Search Works (Simplified)

```text
Web
  |
  v
Crawlers discover pages, obey crawl policy, and fetch HTML
  |
  v
Parsers extract text, links, metadata, and canonical URLs
  |
  v
Indexers tokenize content and build posting lists
  |
  v
Rankers combine lexical relevance, link authority, freshness, and quality signals
  |
  v
Query serving retrieves candidate documents, scores them, highlights snippets, and returns results
```

This project implements those same conceptual stages locally with Python, SQLite, and Flask.

## How My System Maps to Real Systems

```text
                 +-------------------+
Seed URL ------> |  Crawler Service  |
                 | robots, sitemap,  |
                 | depth/page caps   |
                 +---------+---------+
                           |
                           v
                 +-------------------+
                 |  Storage Layer    |
                 | SQLite pages,     |
                 | links, hashes     |
                 +---------+---------+
                           |
             +-------------+-------------+
             v                           v
   +-------------------+       +-------------------+
   |  Index Service    |       | Ranking Service   |
   | tokens, positions,|       | PageRank graph    |
   | BM25 stats        |       | normalization     |
   +---------+---------+       +---------+---------+
             |                           |
             +-------------+-------------+
                           v
                 +-------------------+
                 |  Query Service    |
                 | boolean, phrase,  |
                 | title:, cache     |
                 +---------+---------+
                           |
                           v
                    Flask UI + JSON API
```

In a distributed version, the crawler service would push fetched pages into a queue, the index service would consume and shard postings by term, the ranking service would periodically compute graph authority, and the query service would fan out to index shards before merging ranked results.

## Features

- Polite same-domain crawler with user-agent, robots.txt checks, sitemap parsing, request delay, duplicate URL avoidance, max depth, and max page limits.
- HTML extraction for title, headings, paragraphs, links, metadata, crawl timestamps, and content hashes.
- Incremental indexing: changed or new pages are marked unindexed; unchanged pages keep their indexed state.
- Inverted index with tokenization, stopword removal, document frequency, term frequency, document length, and positional postings.
- Advanced search: phrase queries like `"machine learning"`, boolean queries with `AND`, `OR`, `NOT`, and field queries like `title:AI`.
- BM25 ranking with PageRank normalization and freshness boost.
- Final score: `0.5 * BM25 + 0.3 * PageRank + 0.2 * freshness`.
- Snippet highlighting, query time display, prefix autocomplete using a trie, and basic "Did you mean?" correction.
- LRU query result cache and query latency logging.
- Metrics and stats APIs for indexed page count, query latency, top terms, and index size.
- pytest coverage for BM25, boolean search, phrase search, autocomplete, ranking, indexing, and URL utilities.
- Docker support for reproducible local demos.

## Crawling Pipeline

```text
seed URL -> normalize -> robots.txt -> sitemap.xml -> fetch HTML -> parse content -> hash -> persist pages/links
```

The crawler is intentionally conservative. It only follows same-domain HTTP(S) URLs, sleeps between requests, respects robots.txt where possible, and stops at explicit depth and page limits.

## Indexing Pipeline

```text
pages with indexed_at = NULL -> tokenize -> remove stopwords -> term counts -> positions -> postings -> terms
```

The indexer stores document length for BM25 and positional postings for phrase-aware search. Content hashes allow the crawler to avoid reindexing unchanged pages.

## Ranking Pipeline

```text
query -> parse operators -> candidate sets -> BM25 -> normalized PageRank -> freshness -> final score
```

BM25 handles lexical relevance better than basic TF-IDF because it accounts for document length and term saturation. PageRank adds graph authority from crawled links. Freshness gives recently crawled pages a small boost when timestamps are available.

## API Examples

Search:

```bash
curl "http://127.0.0.1:5000/api/search?q=title:AI"
curl "http://127.0.0.1:5000/api/search?q=%22machine%20learning%22"
curl "http://127.0.0.1:5000/api/search?q=python%20AND%20search%20NOT%20cooking"
```

Autocomplete:

```bash
curl "http://127.0.0.1:5000/api/autocomplete?q=sea"
```

Metrics and stats:

```bash
curl "http://127.0.0.1:5000/api/metrics"
curl "http://127.0.0.1:5000/api/stats"
curl "http://127.0.0.1:5000/health"
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

On macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python -m flask --app app.main run
```

Open:

```text
http://127.0.0.1:5000
http://127.0.0.1:5000/crawl
```

## Test

```bash
python -m pytest
```

Current verification:

```text
12 passed in 0.77s
```

## Docker

```bash
docker compose up --build
```

## Performance Benchmarks

Local benchmark from the automated test corpus:

```text
Indexing: incremental and full indexing complete in milliseconds for small corpora.
Query serving: in-process SQLite + LRU cache keeps repeated queries sub-millisecond after warmup.
Test suite: 12 tests complete in under 1 second on a laptop-class Windows machine.
```

For a larger demo, crawl a small site with max pages `10` to `50`, then inspect:

```bash
curl "http://127.0.0.1:5000/api/metrics"
curl "http://127.0.0.1:5000/api/stats"
```

## Design Tradeoffs

- SQLite keeps the system easy to run and inspect, but real search systems shard indexes across many machines.
- The trie is rebuilt from the term table per service instance; production systems would keep this in memory or a dedicated suggestion service.
- Phrase search uses exact content matching plus positional postings in storage; a larger system would evaluate phrase constraints directly from positions.
- PageRank is recomputed after crawl completion; a production graph pipeline would run offline and publish versioned rank snapshots.
- The query parser is intentionally compact and readable; real systems use richer parsers, query rewriting, synonyms, and learned ranking.

## Limitations and Ethical Crawling Note

This is an educational portfolio project, not an aggressive scraper. Keep crawl limits small, use polite delays, respect robots.txt, avoid private or sensitive data, and do not crawl sites that prohibit automated access. The crawler is single-machine and best suited for demos on small public sites.

## Screenshots

Add screenshots after a demo:

- Search homepage with autocomplete.
- Crawler page with indexing time.
- Results page with highlighted snippets and score breakdown.
- Metrics and stats JSON responses.

## FAANG-Level Resume Bullets

- Built a Google-inspired mini search platform in Python with crawler, sitemap discovery, incremental indexing, positional inverted index, BM25 retrieval, PageRank authority scoring, and Flask query serving.
- Designed advanced query execution for phrase search, boolean operators, field filters, autocomplete via trie, LRU result caching, spelling suggestions, highlighted snippets, and latency metrics.
- Modeled production search architecture concepts including crawler, index, ranking, and query services with SQLite-backed persistence, content-hash deduplication, freshness scoring, API observability, and pytest coverage.

## Recruiter Pitch

I built a production-minded mini search engine from scratch to show that I understand the systems behind search, not just web app CRUD. It crawls politely, indexes incrementally, ranks with BM25 plus PageRank and freshness, supports advanced queries, exposes metrics APIs, and includes tests and documentation that map the implementation to real distributed search infrastructure.

## Future Improvements

- Add stemming, synonyms, and typo-tolerant retrieval.
- Evaluate phrase queries directly from positional postings.
- Add per-domain crawl budgets and backoff.
- Add background jobs for crawl/index/rank pipelines.
- Replace SQLite with sharded posting lists and a distributed cache.
- Add learned-to-rank features and click feedback simulation.
