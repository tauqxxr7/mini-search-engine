"""Flask entrypoint for the Mini Search Engine."""

from __future__ import annotations

from flask import Flask, jsonify, redirect, render_template, request, url_for

from .crawler import WebCrawler
from .database import SearchDatabase
from .indexer import InvertedIndexer
from .ranker import PageRanker
from .search import SearchService

app = Flask(__name__)


def get_db() -> SearchDatabase:
    """Create a database handle for the current request."""
    return SearchDatabase()


@app.get("/")
def index() -> str:
    """Render the search homepage."""
    return render_template("index.html")


@app.get("/crawl")
def crawl_form() -> str:
    """Render the crawler form."""
    return render_template("crawl.html")


@app.post("/crawl")
def crawl_site():
    """Crawl a submitted website, then rebuild index and ranking data."""
    seed_url = request.form.get("seed_url", "").strip()
    max_depth = int(request.form.get("max_depth", 1))
    max_pages = int(request.form.get("max_pages", 20))
    if not seed_url:
        return render_template("crawl.html", error="Please enter a seed URL."), 400

    db = get_db()
    try:
        crawler = WebCrawler(db)
        stats = crawler.crawl(seed_url, max_depth=max_depth, max_pages=max_pages)
        InvertedIndexer(db).rebuild()
        PageRanker(db).compute()
        return render_template("crawl.html", stats=stats)
    except ValueError as exc:
        return render_template("crawl.html", error=str(exc)), 400
    finally:
        db.close()


@app.get("/search")
def search_page() -> str:
    """Render HTML search results."""
    query = request.args.get("q", "")
    db = get_db()
    try:
        results = SearchService(db).search(query)
        return render_template("results.html", query=query, results=results)
    finally:
        db.close()


@app.get("/api/search")
def api_search():
    """Return JSON search results."""
    query = request.args.get("q", "")
    db = get_db()
    try:
        results = [result.to_dict() for result in SearchService(db).search(query)]
        return jsonify({"query": query, "count": len(results), "results": results})
    finally:
        db.close()


@app.get("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


@app.post("/reset")
def reset():
    """Clear local demo data."""
    db = get_db()
    try:
        db.clear_all()
    finally:
        db.close()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)

