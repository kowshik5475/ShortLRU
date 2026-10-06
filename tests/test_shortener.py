import pytest

from shortlru import LRUCache, URLShortener, URLStore


def test_url_shortening():
    shortener = URLShortener()
    code = shortener.shorten("https://example.com")
    assert code
    assert shortener.store.get_url(code) == "https://example.com"


def test_idempotent_shortening():
    shortener = URLShortener()
    url = "https://example.com/same"
    first = shortener.shorten(url)
    second = shortener.shorten(url)
    assert first == second


def test_url_resolution():
    shortener = URLShortener()
    url = "https://example.com/resolve"
    code = shortener.shorten(url)
    assert shortener.resolve(code) == url


def test_cache_hit_during_resolution():
    shortener = URLShortener()
    code = shortener.shorten("https://example.com/hit")

    # shorten() populated the cache; resolving immediately should hit it.
    assert shortener.resolve(code) is not None
    assert shortener.cache.stats()["hits"] == 1
    assert shortener.cache.stats()["misses"] == 0


def test_cache_miss_followed_by_store_lookup():
    store = URLStore()
    shortener = URLShortener(store=store, capacity=3)
    code = shortener.shorten("https://example.com/miss")

    # Remove only the cache entry while keeping the backing store mapping.
    shortener.cache = LRUCache(capacity=3)

    assert shortener.resolve(code) == "https://example.com/miss"
    assert shortener.cache.stats()["misses"] == 1
    assert shortener.cache.get(code) == "https://example.com/miss"
    # The explicit get above is a hit.
    assert shortener.cache.stats()["hits"] == 1


def test_cache_repopulation_after_miss():
    shortener = URLShortener(capacity=1)
    code_a = shortener.shorten("https://example.com/a")
    code_b = shortener.shorten("https://example.com/b")

    # A was evicted; resolving it must reload it from the store.
    assert shortener.cache.get(code_a) is None
    assert shortener.resolve(code_a) == "https://example.com/a"
    assert shortener.cache.get(code_a) == "https://example.com/a"


def test_invalid_empty_url():
    shortener = URLShortener()
    with pytest.raises(ValueError, match="must not be empty"):
        shortener.shorten("")
    with pytest.raises(ValueError, match="must not be empty"):
        shortener.shorten("   ")


def test_store_collision_rejected():
    store = URLStore()
    store.save("abc", "https://example.com/a")
    with pytest.raises(ValueError, match="collision"):
        store.save("abc", "https://example.com/b")


def test_hash_collision_handling(monkeypatch):
    shortener = URLShortener()

    # Both URLs share the first seven hash-derived characters, but differ
    # at the eighth character. The second URL therefore needs a longer code.
    candidates = {
        "https://example.com/first": "ABCDEFGH",
        "https://example.com/second": "ABCDEFGZ",
    }

    monkeypatch.setattr(
        shortener,
        "_hash_to_base62",
        lambda url: candidates[url],
    )

    first = shortener.shorten("https://example.com/first")
    second = shortener.shorten("https://example.com/second")

    assert first == "ABCDEFG"
    assert second == "ABCDEFGZ"
    assert first != second
    assert shortener.resolve(first) == "https://example.com/first"
    assert shortener.resolve(second) == "https://example.com/second"
