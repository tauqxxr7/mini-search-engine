# Architecture

```text
Seed URL
  |
  v
WebCrawler ---- SitemapParser
  |                |
  v                v
SQLite pages + links
  |
  +--> InvertedIndexer --> terms + postings
  |
  +--> PageRanker ------> pagerank
  |
  v
SearchService --> Flask UI + JSON API
```

The system is deliberately modular so each major search-engine concept can be read, tested, and extended independently.

## Components

- `crawler.py`: Same-domain, depth-limited, page-limited crawler with robots.txt checks and request delay.
- `sitemap_parser.py`: Opportunistically discovers URLs from `/sitemap.xml`.
- `indexer.py`: Tokenizes page content and builds term/posting tables.
- `ranker.py`: Computes PageRank-style authority scores from crawled links.
- `search.py`: Combines TF-IDF and PageRank into ranked results.
- `main.py`: Flask UI and API routes.
- `database.py`: SQLite persistence layer.

