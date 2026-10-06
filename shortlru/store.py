"""Educational backing store for shortened URLs."""

from __future__ import annotations


class URLStore:
    """A database-like abstraction backed by in-memory dictionaries.

    One dictionary supports code -> URL lookups and another supports
    URL -> code reverse lookups. Both are O(1) average-case operations.
    A real implementation could replace these dictionaries with SQLite,
    PostgreSQL, Redis, or another persistent storage system.
    """

    def __init__(self) -> None:
        self._code_to_url: dict[str, str] = {}
        self._url_to_code: dict[str, str] = {}

    def save(self, code: str, url: str) -> None:
        """Save a code/URL pair in both directions.

        Raises ValueError if the code already belongs to a different URL.
        """
        existing_url = self._code_to_url.get(code)
        if existing_url is not None and existing_url != url:
            raise ValueError(f"short code collision: {code!r}")

        existing_code = self._url_to_code.get(url)
        if existing_code is not None and existing_code != code:
            raise ValueError(
                f"URL already has a different short code: {existing_code!r}"
            )

        self._code_to_url[code] = url
        self._url_to_code[url] = code

    def get_url(self, code: str) -> str | None:
        """Return the original URL for a short code, if it exists."""
        return self._code_to_url.get(code)

    def get_code(self, url: str) -> str | None:
        """Return the existing short code for a URL, if it exists."""
        return self._url_to_code.get(url)

    def contains_code(self, code: str) -> bool:
        """Return whether the short code exists."""
        return code in self._code_to_url

    def __len__(self) -> int:
        """Return the number of stored URL mappings."""
        return len(self._code_to_url)
