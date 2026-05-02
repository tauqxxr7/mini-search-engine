from app.utils import normalize_url, same_domain, tokenize


def test_normalize_url_removes_fragments_and_sorts_query():
    assert normalize_url("HTTPS://Example.com:443/path/?b=2&a=1#section") == "https://example.com/path?a=1&b=2"


def test_same_domain_requires_exact_hostname():
    assert same_domain("https://example.com/a", "https://example.com/b")
    assert not same_domain("https://blog.example.com/a", "https://example.com/b")


def test_tokenize_removes_stopwords():
    assert tokenize("The quick brown fox and search") == ["quick", "brown", "fox", "search"]

