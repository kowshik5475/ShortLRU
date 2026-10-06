"""Generate benchmark CSV data and PNG charts for ShortLRU."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt


def read_results(path: Path) -> list[dict[str, float]]:
    """Read benchmark result rows from CSV."""
    with path.open("r", newline="", encoding="utf-8") as file:
        return [
            {
                "capacity": float(row["capacity"]),
                "hit_rate_percent": float(row["hit_rate_percent"]),
                "hits": float(row["hits"]),
                "misses": float(row["misses"]),
                "evictions": float(row["evictions"]),
                "time_ms": float(row["time_ms"]),
            }
            for row in csv.DictReader(file)
        ]


def make_charts(csv_path: Path, output_dir: Path) -> None:
    """Create hit-rate and eviction charts."""
    results = read_results(csv_path)
    if not results:
        raise ValueError("benchmark CSV contains no results")

    output_dir.mkdir(parents=True, exist_ok=True)

    capacities = [row["capacity"] for row in results]
    hit_rates = [row["hit_rate_percent"] for row in results]
    evictions = [row["evictions"] for row in results]

    plt.figure()
    plt.plot(capacities, hit_rates, marker="o")
    plt.xlabel("Cache Capacity")
    plt.ylabel("Hit Rate (%)")
    plt.title("ShortLRU: Cache Capacity vs Hit Rate")
    plt.grid(True, alpha=0.25)
    plt.tight_layout()
    hit_rate_path = output_dir / "cache_capacity_vs_hit_rate.png"
    plt.savefig(hit_rate_path, dpi=160)
    plt.close()

    plt.figure()
    plt.plot(capacities, evictions, marker="o")
    plt.xlabel("Cache Capacity")
    plt.ylabel("Evictions")
    plt.title("ShortLRU: Cache Capacity vs Evictions")
    plt.grid(True, alpha=0.25)
    plt.tight_layout()
    eviction_path = output_dir / "cache_capacity_vs_evictions.png"
    plt.savefig(eviction_path, dpi=160)
    plt.close()

    print(f"Created: {hit_rate_path}")
    print(f"Created: {eviction_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate charts from ShortLRU benchmark results."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("results/benchmark.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results"),
    )
    args = parser.parse_args()

    make_charts(args.input, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
