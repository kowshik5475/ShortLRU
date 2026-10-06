"""Benchmark ShortLRU with a repeatable access workload."""

from __future__ import annotations

import argparse
import csv
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
    """Create a workload with temporal locality."""
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
) -> list[dict[str, int | float]]:
    """Run the same workload against each cache capacity."""
    if any(capacity <= 0 for capacity in capacities):
        raise ValueError("all cache capacities must be greater than 0")

    records = load_urls(dataset_path)

    setup = URLShortener(capacity=max(len(records), 1))
    codes = [setup.shorten(record.url) for record in records]
    workload = build_access_pattern(codes, operations, hot_fraction, seed)

    results: list[dict[str, int | float]] = []

    for capacity in capacities:
        service = URLShortener(store=setup.store, capacity=capacity)

        start = time.perf_counter()
        for code in workload:
            service.resolve(code)
        elapsed_ms = (time.perf_counter() - start) * 1000

        stats = service.cache.stats()
        results.append(
            {
                "capacity": capacity,
                "hit_rate_percent": float(stats["hit_rate"]) * 100,
                "hits": int(stats["hits"]),
                "misses": int(stats["misses"]),
                "evictions": int(stats["evictions"]),
                "time_ms": elapsed_ms,
            }
        )

    return results


def print_results(
    results: list[dict[str, int | float]],
    dataset_count: int,
    operations: int,
    hot_fraction: float,
    seed: int,
) -> None:
    """Print benchmark metadata and results."""
    print("=== ShortLRU Benchmark ===")
    print(f"Dataset URLs:       {dataset_count}")
    print(f"Operations:         {operations}")
    print(f"Hot-set fraction:   {hot_fraction:.0%}")
    print(f"Random seed:        {seed}")
    print()
    print(
        f"{'Capacity':<12}{'Hit Rate':<14}{'Hits':<10}"
        f"{'Misses':<10}{'Evictions':<12}{'Time (ms)':<12}"
    )
    print("-" * 68)

    for result in results:
        print(
            f"{int(result['capacity']):<12}"
            f"{float(result['hit_rate_percent']):<14.2f}"
            f"{int(result['hits']):<10}"
            f"{int(result['misses']):<10}"
            f"{int(result['evictions']):<12}"
            f"{float(result['time_ms']):<12.3f}"
        )


def write_csv(results: list[dict[str, int | float]], path: Path) -> None:
    """Write benchmark results to CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "capacity",
        "hit_rate_percent",
        "hits",
        "misses",
        "evictions",
        "time_ms",
    ]

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark ShortLRU.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("data/urls.csv"),
    )
    parser.add_argument(
        "--capacities",
        nargs="+",
        type=int,
        default=[3, 5, 10, 20],
    )
    parser.add_argument("--operations", type=int, default=5000)
    parser.add_argument("--hot-fraction", type=float, default=0.70)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="optional CSV output path",
    )
    args = parser.parse_args()

    try:
        records = load_urls(args.dataset)
        results = run_benchmark(
            args.dataset,
            args.capacities,
            args.operations,
            args.hot_fraction,
            args.seed,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    print_results(
        results,
        len(records),
        args.operations,
        args.hot_fraction,
        args.seed,
    )

    if args.output:
        write_csv(results, args.output)
        print(f"\nSaved results to: {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
