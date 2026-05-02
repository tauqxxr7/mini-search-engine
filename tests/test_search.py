from app.database import SearchDatabase
from app.indexer import InvertedIndexer
from app.ranker import PageRanker
from app.search import SearchService


def test_search_combines_tfidf_and_pagerank(tmp_path):
    db = SearchDatabase(tmp_path / "test.db")
    db.upsert_page(
        url="https://example.com/a",
        title="Python Search",
        headings=["Search systems"],
        content="Python search search indexing",
        metadata={},
        status_code=200,
    )
    db.upsert_page(
        url="https://example.com/b",
        title="Cooking",
        headings=[],
        content="Recipes and kitchen notes",
        metadata={},
        status_code=200,
    )
    db.add_links("https://example.com/b", ["https://example.com/a"])
    InvertedIndexer(db).rebuild()
    PageRanker(db).compute()

    results = SearchService(db).search("search")

    assert results
    assert results[0].url == "https://example.com/a"
    assert results[0].final_score > 0
    db.close()

