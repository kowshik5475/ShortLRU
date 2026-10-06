"""Benchmark ShortLRU with a repeatable synthetic access workload."""

from __future__ import annotations

import argparse
import random
import time
from pathlib import Path

from shortlru import URLShortener
from shortlru.dataset import load_urls


def build_access_pattern(
    codes: list[str],
    operations: int,
    hot_fraction: float,
    seed: int,
) -> list[str]:
    """Create a workload with a configurable hot set.

    A hot workload is useful because caches are designed to exploit temporal
    locality: recently/frequently accessed values are more likely to be reused.
    """
    if not codes:
        raise ValueError("at least one URL is required")
    if operations <= 0:
        raise ValueError("operations must be greater than 0")
    if not 0 <= hot_fraction <= 1:
        raise ValueError("hot_fraction must be between 0 and 1")

    rng = random.Random(seed)
    hot_count = max(1, int(len(codes) * hot_fraction))
    hot_codes = codes[:hot_count]

    workload: list[str] = []
    for _ in range(operations):
        if rng.random() < hot_fraction:
            workload.append(rng.choice(hot_codes))
        else:
            workload.append(rng.choice(codes))
    return workload


def run_benchmark(
    dataset_path: Path,
    capacities: list[int],
    operations: int,
    hot_fraction: float,
    seed: int,
) -> None:
    """Run the same workload against multiple cache capacities."""
    records = load_urls(dataset_path)

    # Each URL is shortened once using a large setup cache so the benchmark
    # measures resolution behavior rather than repeated code generation.
    setup = URLShortener(capacity=max(len(records), 1))
    codes = [setup.shorten(record.url) for record in records]

    workload = build_access_pattern(codes, operations, hot_fraction, seed)

    print("=== ShortLRU Benchmark ===")
    print(f"Dataset URLs:       {len(records)}")
    print(f"Operations:         {operations}")
    print(f"Hot-set fraction:   {hot_fraction:.0%}")
    print(f"Random seed:        {seed}")
    print()
    print(f"{'Capacity':<12}{'Hit Rate':<14}{'Hits':<10}{'Misses':<10}{'Evictions':<12}{'Time (ms)':<12}")
    print("-" * 68)

    for capacity in capacities:
        # Use the same store and codes, but a fresh cache, so capacities are
        # compared fairly.
        service = URLShortener(store=setup.store, capacity=capacity)

        start = time.perf_counter()
        for code in workload:
            service.resolve(code)
        elapsed_ms = (time.perf_counter() - start) * 1000

        stats = service.cache.stats()
        print(
            f"{capacity:<12}"
            f"{stats['hit_rate'] * 100:<14.2f}"
            f"{stats['hits']:<10}"
            f"{stats['misses']:<10}"
            f"{stats['evictions']:<12}"
            f"{elapsed_ms:<12.3f}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark ShortLRU cache performance.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("data/urls.csv"),
        help="CSV dataset path (default: data/urls.csv)",
    )
    parser.add_argument(
        "--capacities",
        nargs="+",
        type=int,
        default=[3, 5, 10, 20],
        help="cache capacities to compare",
    )
    parser.add_argument(
        "--operations",
        type=int,
        default=5000,
        help="number of resolve operations",
    )
    parser.add_argument(
        "--hot-fraction",
        type=float,
        default=0.70,
        help="probability of selecting from the hot set",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    try:
        run_benchmark(
            args.dataset,
            args.capacities,
            args.operations,
            args.hot_fraction,
            args.seed,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
