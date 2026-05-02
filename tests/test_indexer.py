from app.database import SearchDatabase
from app.indexer import InvertedIndexer


def test_indexer_builds_document_and_term_frequency(tmp_path):
    db = SearchDatabase(tmp_path / "test.db")
    first_id = db.upsert_page(
        url="https://example.com/a",
        title="Alpha",
        headings=[],
        content="Alpha beta beta search",
        metadata={},
        status_code=200,
    )
    db.upsert_page(
        url="https://example.com/b",
        title="Beta",
        headings=[],
        content="Beta gamma",
        metadata={},
        status_code=200,
    )

    InvertedIndexer(db).rebuild()

    beta = db.conn.execute("SELECT document_frequency FROM terms WHERE term = 'beta'").fetchone()
    posting = db.conn.execute(
        "SELECT term_frequency FROM postings WHERE term = 'beta' AND page_id = ?",
        (first_id,),
    ).fetchone()
    assert beta["document_frequency"] == 2
    assert posting["term_frequency"] == 2
    db.close()


def test_tfidf_returns_zero_for_empty_inputs():
    assert InvertedIndexer.tfidf(0, 1, 2) == 0.0

