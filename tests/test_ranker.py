from app.database import SearchDatabase
from app.ranker import PageRanker


def test_pagerank_rewards_inbound_links(tmp_path):
    db = SearchDatabase(tmp_path / "test.db")
    ranker = PageRanker(db, iterations=50)
    scores = ranker.compute_from_graph(
        ["a", "b", "c"],
        [("a", "b"), ("c", "b")],
    )
    assert round(sum(scores.values()), 6) == 1.0
    assert scores["b"] > scores["a"]
    assert scores["b"] > scores["c"]
    db.close()

