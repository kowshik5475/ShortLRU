import pytest

from shortlru import LRUCache


def test_cache_insertion_and_lookup():
    cache = LRUCache(capacity=3)
    cache.put("a", "A")
    assert cache.get("a") == "A"
    assert cache.keys() == ["a"]


def test_cache_miss():
    cache = LRUCache(capacity=3)
    assert cache.get("missing") is None
    assert cache.stats()["misses"] == 1


def test_lru_promotion():
    cache = LRUCache(capacity=3)
    for key in ("a", "b", "c"):
        cache.put(key, key.upper())

    assert cache.keys() == ["c", "b", "a"]
    assert cache.get("a") == "A"
    assert cache.keys() == ["a", "c", "b"]


def test_lru_eviction():
    cache = LRUCache(capacity=3)
    for key in ("a", "b", "c"):
        cache.put(key, key.upper())

    cache.get("a")
    cache.put("d", "D")

    assert cache.keys() == ["d", "a", "c"]
    assert cache.get("b") is None
    assert cache.stats()["evictions"] == 1


def test_cache_capacity():
    cache = LRUCache(capacity=2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    assert cache.stats()["size"] == 2
    assert cache.keys() == ["c", "b"]


def test_hit_count():
    cache = LRUCache(capacity=3)
    cache.put("a", "A")
    assert cache.get("a") == "A"
    assert cache.get("a") == "A"
    assert cache.stats()["hits"] == 2


def test_miss_count():
    cache = LRUCache(capacity=3)
    cache.get("a")
    cache.get("b")
    assert cache.stats()["misses"] == 2


def test_eviction_count():
    cache = LRUCache(capacity=1)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    assert cache.stats()["evictions"] == 2


def test_hit_rate():
    cache = LRUCache(capacity=3)
    cache.put("a", "A")
    cache.get("a")
    cache.get("missing")
    cache.get("a")
    stats = cache.stats()
    assert stats["hits"] == 2
    assert stats["misses"] == 1
    assert stats["hit_rate"] == pytest.approx(2 / 3)


@pytest.mark.parametrize("capacity", [0, -1, -10])
def test_invalid_cache_capacity(capacity):
    with pytest.raises(ValueError, match="greater than 0"):
        LRUCache(capacity=capacity)
