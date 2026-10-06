"""Command-line interface for ShortLRU."""

from __future__ import annotations

import argparse

from .shortener import URLShortener


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="shortlru",
        description="Educational command-line URL shortener using SHA-256, Base62, and LRU caching.",
    )
    parser.add_argument(
        "--capacity",
        type=int,
        default=3,
        help="LRU cache capacity (default: 3)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    shorten_parser = subparsers.add_parser("shorten", help="Shorten a URL")
    shorten_parser.add_argument("url", help="URL to shorten")

    resolve_parser = subparsers.add_parser("resolve", help="Resolve a short code")
    resolve_parser.add_argument("code", help="Short code to resolve")

    subparsers.add_parser("stats", help="Show cache statistics")

    return parser


def main() -> int:
    """Run the CLI and return an exit status."""
    parser = build_parser()
    args = parser.parse_args()

    try:
        shortener = URLShortener(capacity=args.capacity)
    except ValueError as exc:
        parser.error(str(exc))

    if args.command == "shorten":
        try:
            code = shortener.shorten(args.url)
        except ValueError as exc:
            parser.error(str(exc))
        print(f"Short code: {code}")
        return 0

    if args.command == "resolve":
        url = shortener.resolve(args.code)
        if url is None:
            print("URL not found")
            return 1
        print(f"URL: {url}")
        return 0

    stats = shortener.cache.stats()
    print(f"Cache capacity: {stats['capacity']}")
    print(f"Cache size:     {stats['size']}")
    print(f"Hits:           {stats['hits']}")
    print(f"Misses:         {stats['misses']}")
    print(f"Evictions:      {stats['evictions']}")
    print(f"Hit rate:       {stats['hit_rate'] * 100:.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
