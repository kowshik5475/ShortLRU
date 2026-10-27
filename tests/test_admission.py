import pytest
from shortlru.admission import CacheAsideResolver, SecondAccessAdmission
from shortlru.store import URLStore


def make_resolver(window=3, capacity=2):
    store = URLStore()
    for code in ("a", "b", "c", "d"):
        store.save(code, "https://example.test/" + code)
    return store, CacheAsideResolver(store, capacity, SecondAccessAdmission(window))


def test_first_miss_bypasses_second_miss_admits():
    _, resolver = make_resolver()
    assert resolver.resolve("a").endswith("/a")
    assert resolver.cache.keys() == []
    assert resolver.resolve("a").endswith("/a")
    assert resolver.cache.keys() == ["a"]
    assert resolver.stats()["admissions"] == 1


def test_window_boundary_is_inclusive():
    _, resolver = make_resolver(window=2)
    resolver.resolve("a")  # sequence 1
    resolver.resolve("b")  # sequence 2
    resolver.resolve("a")  # sequence 3, diff 2: eligible
    assert resolver.cache.keys() == ["a"]


def test_expired_observation_does_not_admit():
    _, resolver = make_resolver(window=2)
    resolver.resolve("a")
    resolver.resolve("b")
    resolver.resolve("c")
    resolver.resolve("a")
    assert "a" not in resolver.cache.keys()


def test_missing_code_does_not_record_or_admit():
    _, resolver = make_resolver()
    assert resolver.resolve("missing") is None
    assert resolver.stats()["admissions"] == 0
    assert resolver.admission.tracked_observations == 0


def test_store_unchanged_and_tracking_bounded():
    store = URLStore()
    for i in range(5000):
        store.save(f"u{i}", f"https://example.test/u{i}")
    resolver = CacheAsideResolver(store, capacity=2, admission=SecondAccessAdmission(window_size=4))
    before = len(store)
    for i in range(5000):
        assert resolver.resolve(f"u{i}") == f"https://example.test/u{i}"
        assert resolver.admission.tracked_observations <= 5
    assert len(store) == before


def test_invalid_window():
    with pytest.raises(ValueError):
        SecondAccessAdmission(0)


def test_ordinary_lru_mode_admits_first_miss():
    store = URLStore()
    store.save("a", "https://example.test/a")
    resolver = CacheAsideResolver(store, capacity=1)
    resolver.resolve("a")
    assert resolver.cache.keys() == ["a"]


def test_cache_hit_advances_window_without_recording_observation():
    store, resolver = make_resolver(window=2)
    resolver.resolve("a")
    resolver.resolve("a")  # admitted
    assert resolver.cache.keys() == ["a"]
    resolver.resolve("a")  # hit advances sequence
    assert resolver.admission.sequence == 3
    assert resolver.admission.tracked_observations == 1


def test_admission_policy_does_not_modify_store_mappings():
    store, resolver = make_resolver()
    original = {code: store.get_url(code) for code in ("a", "b", "c", "d")}
    resolver.resolve("a")
    resolver.resolve("a")
    assert {code: store.get_url(code) for code in original} == original
    assert len(store) == len(original)


def test_cache_capacity_and_eviction_are_respected():
    _, resolver = make_resolver(window=5, capacity=1)
    resolver.resolve("a")
    resolver.resolve("a")
    resolver.resolve("b")
    resolver.resolve("b")
    assert resolver.cache.keys() == ["b"]
    assert resolver.stats()["evictions"] == 1


def test_empty_code_is_a_miss_but_never_admitted():
    _, resolver = make_resolver()
    assert resolver.resolve("") is None
    stats = resolver.stats()
    assert stats["misses"] == 1
    assert stats["admissions"] == 0
    assert resolver.admission.tracked_observations == 0
