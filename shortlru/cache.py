"""An O(1) LRU cache implemented with a hash map and doubly linked list."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class _Node:
    """A node in the cache's doubly linked list."""

    key: str
    value: Any
    previous: _Node | None = None
    next: _Node | None = None


class LRUCache:
    """Least Recently Used cache with O(1) average operations.

    A dictionary maps keys directly to linked-list nodes. The linked list
    stores recency order: most recent at the front and least recent at the
    back. Sentinel head/tail nodes keep pointer operations simple.
    """

    def __init__(self, capacity: int = 3) -> None:
        """Create a cache with a positive maximum capacity."""
        if capacity <= 0:
            raise ValueError("capacity must be greater than 0")

        self.capacity = capacity
        self._items: dict[str, _Node] = {}

        self._head = _Node("", None)
        self._tail = _Node("", None)
        self._head.next = self._tail
        self._tail.previous = self._head

        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def _remove(self, node: _Node) -> None:
        """Remove a node from the linked list."""
        previous = node.previous
        next_node = node.next

        if previous is None or next_node is None:
            raise RuntimeError("cannot remove a detached node")

        previous.next = next_node
        next_node.previous = previous

    def _add_to_front(self, node: _Node) -> None:
        """Insert a node immediately after the head sentinel."""
        first = self._head.next
        if first is None:
            raise RuntimeError("cache list is not initialized")

        node.previous = self._head
        node.next = first
        self._head.next = node
        first.previous = node

    def _move_to_front(self, node: _Node) -> None:
        """Promote an existing node to most-recent position."""
        self._remove(node)
        self._add_to_front(node)

    def _remove_least_recently_used(self) -> _Node:
        """Remove and return the least recently used real node."""
        node = self._tail.previous
        if node is None or node is self._head:
            raise RuntimeError("cannot evict from an empty cache")

        self._remove(node)
        del self._items[node.key]
        self.evictions += 1
        return node

    def get(self, key: str) -> Any | None:
        """Return a value and promote it, or return None on a cache miss."""
        node = self._items.get(key)
        if node is None:
            self.misses += 1
            return None

        self.hits += 1
        self._move_to_front(node)
        return node.value

    def put(self, key: str, value: Any) -> None:
        """Insert/update a value and make it the most recently used item."""
        existing = self._items.get(key)

        if existing is not None:
            existing.value = value
            self._move_to_front(existing)
            return

        node = _Node(key, value)
        self._items[key] = node
        self._add_to_front(node)

        if len(self._items) > self.capacity:
            self._remove_least_recently_used()

    def stats(self) -> dict[str, int | float]:
        """Return cache counters and current state."""
        total_lookups = self.hits + self.misses
        hit_rate = self.hits / total_lookups if total_lookups else 0.0

        return {
            "capacity": self.capacity,
            "size": len(self._items),
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "hit_rate": hit_rate,
        }

    def keys(self) -> list[str]:
        """Return keys from most-recently-used to least-recently-used.

        This helper is intentionally exposed for demos and tests.
        """
        result: list[str] = []
        current = self._head.next
        while current is not None and current is not self._tail:
            result.append(current.key)
            current = current.next
        return result
