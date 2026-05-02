# Mini Search Engine from Scratch

A recruiter-grade Python search engine that crawls a website, builds an inverted index, computes PageRank-style authority, and serves ranked results through a Flask UI and JSON API.

## Problem Statement

Search engines combine crawling, content extraction, indexing, and ranking into one system. This project implements those core ideas in a compact, readable codebase suitable for demonstrating software engineering fundamentals in an internship portfolio.

## Features

- Polite same-domain web crawler with max depth, max pages, user-agent, robots.txt checks, and request delay.
- Sitemap discovery through `/sitemap.xml` when available.
- HTML extraction for title, headings, paragraphs, metadata, and links.
- URL normalization and duplicate avoidance.
- SQLite persistence for pages, links, terms, postings, and PageRank scores.
- Inverted index with stopword removal, term frequency, document frequency, and TF-IDF scoring.
- PageRank-style iterative ranking with damping factor `0.85`.
- Combined score: `0.65 * tfidf_score + 0.35 * pagerank_score`.
- Flask search UI, crawler UI, health check, and JSON API.
- pytest coverage for indexing, ranking, search, and URL utilities.
- Docker support for reproducible local runs.

## Architecture

```text
User
  |
  v
Flask UI/API
  |
  +--> WebCrawler --> SitemapParser
  |       |
  |       v
  |     SQLite pages + links
  |
  +--> InvertedIndexer --> terms + postings
  |
  +--> PageRanker ------> pagerank
  |
  v
SearchService --> ranked results
```

## How the Crawler Works

The crawler starts from a user-provided seed URL, normalizes it, checks robots.txt where possible, and optionally loads URLs from `/sitemap.xml`. It only follows HTTP(S) links on the same domain, tracks visited URLs to avoid duplicates, and stops at the configured depth and page limits. Each fetched HTML page is parsed with BeautifulSoup to extract titles, headings, paragraphs, metadata, and outgoing links.

## How the Inverted Index Works

The indexer tokenizes stored page content, lowercases terms, removes common stopwords, and stores term frequencies in a postings table. It also stores document frequency per term so search can compute TF-IDF:

```text
tf = 1 + log(term_frequency)
idf = log((1 + total_documents) / (1 + document_frequency)) + 1
```

## How PageRank Works

The ranker builds a directed graph from crawled page links and runs iterative PageRank with damping factor `0.85`. Pages with more inbound links from other crawled pages receive more authority. Dangling pages distribute their score evenly across the graph.

## API Examples

Search JSON results:

```bash
curl "http://127.0.0.1:5000/api/search?q=python"
```

Health check:

```bash
curl "http://127.0.0.1:5000/health"
```

Start a crawl from the UI:

```text
Open http://127.0.0.1:5000/crawl
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

Then open:

```text
http://127.0.0.1:5000
```

## Test

```bash
python -m pytest
```

## Docker

```bash
docker compose up --build
```

## Screenshots

Add screenshots here after running a demo:

- Search homepage
- Crawler form
- Ranked result page with TF-IDF, PageRank, and final score

## Sample Demo Flow

1. Run `python -m flask --app app.main run`.
2. Open `http://127.0.0.1:5000/crawl`.
3. Enter a small seed site, set depth to `1`, and max pages to `10`.
4. Submit the crawl and wait for completion.
5. Return to the homepage and search for a word that appears on the crawled site.
6. Explain how the result score combines lexical relevance and link authority.

## Resume Bullet Points

- Built a full-stack mini search engine in Python and Flask with a polite same-domain crawler, sitemap parsing, SQLite persistence, and a clean HTML/CSS search UI.
- Implemented an inverted index with tokenization, stopword removal, term/document frequency storage, and TF-IDF scoring for keyword search.
- Designed a PageRank-style ranking pipeline over crawled link graphs and combined authority with TF-IDF relevance using a weighted scoring model.

## Future Improvements

- Add stemming or lemmatization.
- Support phrase search and field weighting for titles/headings.
- Add asynchronous crawling with stricter per-domain rate limiting.
- Add incremental indexing instead of full rebuilds.
- Add an admin dashboard for crawl history and index statistics.

## Limitations and Ethical Crawling Note

This project is built for learning and portfolio demonstration. It is not an aggressive scraper. Keep `max_pages` small, use reasonable delays, respect robots.txt, avoid crawling sites that prohibit automated access, and do not collect private or sensitive information.

