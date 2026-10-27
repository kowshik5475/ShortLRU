"""Second-access cache admission and cache-aside resolution."""
from __future__ import annotations

from collections import deque
from typing import Any

from .cache import LRUCache
from .store import URLStore


class SecondAccessAdmission:
    """Admit a key after a second cache miss within a request-count window.

    An observation at sequence s is eligible at s+1 through s+window_size,
    inclusive. Every call to observe_request advances the global request clock.
    Only valid backing-store misses are recorded as observations. At most
    window_size + 1 live request-sequence observations can be retained.
    """

    def __init__(self, window_size: int = 20) -> None:
        if window_size <= 0:
            raise ValueError("window_size must be greater than 0")
        self.window_size = window_size
        self.sequence = 0
        self._observed: dict[str, int] = {}
        self._fifo: deque[tuple[int, str]] = deque()
        self.admissions = 0
        self.bypasses = 0

    def observe_request(self, code: str | None, eligible_miss: bool) -> bool:
        """Advance the request window and return whether this miss is eligible."""
        self.sequence += 1
        while self._fifo and self.sequence - self._fifo[0][0] > self.window_size:
            stamp, old_code = self._fifo.popleft()
            if self._observed.get(old_code) == stamp:
                del self._observed[old_code]
        if not code or not eligible_miss:
            return False
        previous = self._observed.get(code)
        if previous is not None and self.sequence - previous <= self.window_size:
            self.admissions += 1
            return True
        self._observed[code] = self.sequence
        self._fifo.append((self.sequence, code))
        self.bypasses += 1
        return False

    @property
    def tracked_observations(self) -> int:
        return len(self._observed)


class CacheAsideResolver:
    """Resolve codes through LRU + backing store, optionally gating admission."""

    def __init__(self, store: URLStore, capacity: int = 3,
                 admission: SecondAccessAdmission | None = None) -> None:
        self.store = store
        self.cache = LRUCache(capacity)
        self.admission = admission
        self.store_lookups = 0
        self.successful_admissions = 0
        self.admission_bypasses = 0

    def resolve(self, code: str) -> str | None:
        cached = self.cache.get(code)
        if cached is not None:
            if self.admission is not None:
                self.admission.observe_request(code, False)
            return cached
        self.store_lookups += 1
        value = self.store.get_url(code) if code else None
        if self.admission is None:
            if value is not None:
                self.cache.put(code, value)
            return value
        should_admit = self.admission.observe_request(code, value is not None)
        if value is not None and should_admit:
            self.cache.put(code, value)
            self.successful_admissions += 1
        elif value is not None:
            self.admission_bypasses += 1
        return value

    def stats(self) -> dict[str, int | float]:
        result: dict[str, int | float] = dict(self.cache.stats())
        result.update({
            "store_lookups": self.store_lookups,
            "admissions": self.successful_admissions,
            "bypasses": self.admission_bypasses,
        })
        return result
