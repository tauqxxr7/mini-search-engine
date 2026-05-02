# Design Decisions

## SQLite

SQLite keeps the project easy to run locally while still showing persistence, relational modeling, and queryable intermediate state.

## Bounded Crawling

The crawler defaults to small limits and a polite delay. It only follows same-domain HTTP(S) links and checks robots.txt where possible. This makes the project useful for learning without encouraging aggressive scraping.

## Smoothed TF-IDF

The indexer uses logarithmic term frequency and smoothed inverse document frequency:

```text
tf = 1 + log(term_frequency)
idf = log((1 + total_documents) / (1 + document_frequency)) + 1
```

## Combined Ranking

Search results use a weighted blend:

```text
final_score = 0.65 * tfidf_score + 0.35 * pagerank_score
```

TF-IDF captures query relevance. PageRank adds link authority from the crawled graph.

