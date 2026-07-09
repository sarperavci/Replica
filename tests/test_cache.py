import time

from replica.cache import Cache


def test_cache_hit_and_expiry():
    c = Cache()
    c.put("k", "v", ttl=100)
    assert c.get("k") == "v"


def test_cache_expired_returns_none(monkeypatch):
    c = Cache()
    base = [1000.0]
    monkeypatch.setattr("replica.cache.time.monotonic", lambda: base[0])
    c.put("k", "v", ttl=10)
    base[0] = 1005.0
    assert c.get("k") == "v"
    base[0] = 1011.0
    assert c.get("k") is None


def test_cache_zero_or_negative_ttl_not_stored():
    c = Cache()
    c.put("a", "v", ttl=0)
    c.put("b", "v", ttl=-5)
    assert c.get("a") is None
    assert c.get("b") is None


def test_cache_bounded_evicts_oldest():
    c = Cache(max_entries=3)
    for i in range(5):
        c.put(f"k{i}", i, ttl=100)
    assert len(c._store) == 3
    assert c.get("k0") is None
    assert c.get("k4") == 4


def test_cache_lru_move_on_access():
    c = Cache(max_entries=3)
    c.put("a", 1, ttl=100)
    c.put("b", 2, ttl=100)
    c.put("c", 3, ttl=100)
    c.get("a")  # touch a so it's most-recently-used
    c.put("d", 4, ttl=100)  # evicts b (oldest untouched)
    assert c.get("a") == 1
    assert c.get("b") is None
    assert c.get("d") == 4
