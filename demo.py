"""Interactive one-process demonstration of ShortLRU's LRU behavior."""

from shortlru import URLShortener


def print_cache(shortener: URLShortener, label: str) -> None:
    """Print cache order and statistics."""
    print(f"\n{label}")
    print("MRU -> LRU:", " -> ".join(shortener.cache.keys()) or "(empty)")
    print("Stats:", shortener.cache.stats())


def main() -> None:
    shortener = URLShortener(capacity=3)

    urls = [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
        "https://example.com/d",
    ]

    print("=== ShortLRU LRU demonstration ===")
    print("Cache capacity = 3")

    codes = {}
    for label, url in zip(("A", "B", "C"), urls[:3]):
        codes[label] = shortener.shorten(url)
        print(f"Shortened URL {label}: {codes[label]} -> {url}")

    print_cache(shortener, "After inserting A, B, C:")

    print(f"\nResolve A ({codes['A']}) to create a cache hit:")
    print("Result:", shortener.resolve(codes["A"]))
    print_cache(shortener, "After accessing A (A is now most recent):")

    codes["D"] = shortener.shorten(urls[3])
    print(f"\nShortened URL D: {codes['D']} -> {urls[3]}")
    print_cache(shortener, "After inserting D (B should be evicted):")

    print(f"\nResolve B ({codes['B']}) after eviction:")
    print("Result:", shortener.resolve(codes["B"]))
    print_cache(shortener, "After resolving B (miss -> store -> cache):")

    print("\nNotice that the store still knows B even though the cache evicted it.")


if __name__ == "__main__":
    main()
