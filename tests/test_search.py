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

    response = SearchService(db).search("search")

    assert response.results
    assert response.results[0].url == "https://example.com/a"
    assert response.results[0].final_score > 0
    db.close()


def test_phrase_search_requires_exact_phrase(tmp_path):
    db = SearchDatabase(tmp_path / "test.db")
    db.upsert_page(
        url="https://example.com/a",
        title="Machine Learning",
        headings=[],
        content="Machine learning systems rank documents",
        metadata={},
        status_code=200,
    )
    db.upsert_page(
        url="https://example.com/b",
        title="Separated Terms",
        headings=[],
        content="Machine tools can support learning goals",
        metadata={},
        status_code=200,
    )
    InvertedIndexer(db).rebuild()

    response = SearchService(db).search('"machine learning"')

    assert [result.url for result in response.results] == ["https://example.com/a"]
    db.close()


def test_boolean_search_supports_and_or_not(tmp_path):
    db = SearchDatabase(tmp_path / "test.db")
    db.upsert_page(url="https://example.com/a", title="Python AI", headings=[], content="python ai", metadata={}, status_code=200)
    db.upsert_page(url="https://example.com/b", title="Python Cooking", headings=[], content="python cooking", metadata={}, status_code=200)
    db.upsert_page(url="https://example.com/c", title="Cooking", headings=[], content="cooking", metadata={}, status_code=200)
    InvertedIndexer(db).rebuild()
    service = SearchService(db)

    assert [result.url for result in service.search("python AND ai").results] == ["https://example.com/a"]
    assert {result.url for result in service.search("ai OR cooking").results} == {
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    }
    assert [result.url for result in service.search("python NOT cooking").results] == ["https://example.com/a"]
    db.close()


def test_field_search_matches_title(tmp_path):
    db = SearchDatabase(tmp_path / "test.db")
    db.upsert_page(url="https://example.com/a", title="AI Guide", headings=[], content="systems", metadata={}, status_code=200)
    db.upsert_page(url="https://example.com/b", title="Systems", headings=[], content="ai guide", metadata={}, status_code=200)
    InvertedIndexer(db).rebuild()

    response = SearchService(db).search("title:AI")

    assert [result.url for result in response.results] == ["https://example.com/a"]
    db.close()


def test_autocomplete_uses_prefix_trie(tmp_path):
    db = SearchDatabase(tmp_path / "test.db")
    db.upsert_page(url="https://example.com/a", title="Search", headings=[], content="search searching service", metadata={}, status_code=200)
    InvertedIndexer(db).rebuild()

    suggestions = SearchService(db).autocomplete("sea")

    assert "search" in suggestions
    assert "searching" in suggestions
    db.close()
