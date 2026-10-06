"""URL shortening service coordinating hashing, storage, and caching."""

from __future__ import annotations

import hashlib

from .cache import LRUCache
from .store import URLStore


_BASE62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_INITIAL_CODE_LENGTH = 7


def _to_base62(number: int) -> str:
    """Convert a non-negative integer to a compact Base62 string."""
    if number < 0:
        raise ValueError("number must be non-negative")

    if number == 0:
        return "0"

    digits: list[str] = []
    while number:
        number, remainder = divmod(number, 62)
        digits.append(_BASE62_ALPHABET[remainder])

    return "".join(reversed(digits))


class URLShortener:
    """Application service for shortening and resolving URLs."""

    def __init__(self, store: URLStore | None = None, capacity: int = 3) -> None:
        self.store = store if store is not None else URLStore()
        self.cache = LRUCache(capacity)

    @staticmethod
    def _hash_to_base62(url: str) -> str:
        """Hash a URL with SHA-256 and encode the resulting integer as Base62."""
        digest = hashlib.sha256(url.encode("utf-8")).digest()
        number = int.from_bytes(digest, byteorder="big")
        return _to_base62(number)

    def _generate_code(self, url: str) -> str:
        """Generate a unique deterministic code, extending it on collision.

        The first candidate uses seven Base62 characters. If that prefix is
        already assigned to another URL, one additional hash-derived
        character is included at a time until a unique code is found.
        """
        encoded_hash = self._hash_to_base62(url)

        for length in range(_INITIAL_CODE_LENGTH, len(encoded_hash) + 1):
            candidate = encoded_hash[:length]
            existing_url = self.store.get_url(candidate)

            if existing_url is None or existing_url == url:
                return candidate

        # Reaching here would require a full SHA-256/Base62 collision.
        raise RuntimeError("unable to generate a unique short code")

    def shorten(self, url: str) -> str:
        """Return an idempotent short code for a non-empty URL."""
        if not url or not url.strip():
            raise ValueError("URL must not be empty")

        existing_code = self.store.get_code(url)
        if existing_code is not None:
            # Refreshing the cache is useful if this mapping was evicted.
            self.cache.put(existing_code, url)
            return existing_code

        code = self._generate_code(url)
        self.store.save(code, url)
        self.cache.put(code, url)
        return code

    def resolve(self, code: str) -> str | None:
        """Resolve a short code using cache-aside lookup."""
        if not code:
            return None

        cached_url = self.cache.get(code)
        if cached_url is not None:
            return cached_url

        stored_url = self.store.get_url(code)
        if stored_url is None:
            return None

        self.cache.put(code, stored_url)
        return stored_url
