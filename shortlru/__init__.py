"""ShortLRU: an educational URL shortener demonstrating hashing, LRU caching, and OOP."""

from .cache import LRUCache
from .dataset import DatasetURL, load_urls
from .store import URLStore
from .shortener import URLShortener

__all__ = ["LRUCache", "URLStore", "URLShortener", "DatasetURL", "load_urls"]
__version__ = "1.1.0"
