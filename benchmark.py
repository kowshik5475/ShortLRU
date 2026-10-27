"""Benchmark ShortLRU with a repeatable access workload."""

from __future__ import annotations

import argparse
import csv
import random
import time
from pathlib import Path

from shortlru import URLShortener, URLStore
from shortlru.admission import CacheAsideResolver, SecondAccessAdmission
from shortlru.workloads import WORKLOADS, build_workload
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




EXPERIMENT_FIELDS = [
    "row_type", "workload", "phase", "strategy", "capacity", "seed", "trial",
    "requests", "hits", "misses", "hit_rate_percent", "evictions", "store_lookups",
    "admissions", "bypasses", "elapsed_ms", "window_size",
]


def _make_trace(name: str, capacity: int, seed: int, requests: int, url_count: int,
                alpha: float, hot_set_size: int, scan_factor: float):
    if name == "zipf":
        from shortlru.workloads import zipf_hotset
        return zipf_hotset(url_count=url_count, requests=requests, alpha=alpha, seed=seed)
    if name == "hot_scan":
        from shortlru.workloads import hot_scan
        return hot_scan(capacity=capacity, hot_set_size=hot_set_size, scan_factor=scan_factor,
                        hot_requests=requests // 2, seed=seed)
    from shortlru.workloads import popularity_shift
    return popularity_shift(hot_set_size=hot_set_size, requests_per_phase=requests // 2,
                            alpha=alpha, seed=seed)


def _counter_snapshot(resolver: CacheAsideResolver) -> dict[str, int]:
    stats = resolver.stats()
    return {key: int(stats[key]) for key in
            ("hits", "misses", "evictions", "store_lookups", "admissions", "bypasses")}


def run_experiments(
    workloads: list[str], capacities: list[int], seeds: list[int], repetitions: int,
    strategies: list[str], window_size: int = 20, requests: int = 4000,
    url_count: int = 64, alpha: float = 1.2, hot_set_size: int = 8,
    scan_factor: float = 3.0,
) -> list[dict[str, int | float | str]]:
    """Run fair strategy comparisons over identical traces and validate every response."""
    if not capacities or any(c <= 0 for c in capacities):
        raise ValueError("capacities must all be positive")
    if repetitions <= 0 or not seeds or not strategies or not workloads:
        raise ValueError("workloads, strategies, seeds and positive repetitions are required")
    if window_size <= 0:
        raise ValueError("window_size must be positive")
    rows: list[dict[str, int | float | str]] = []
    for workload_name in workloads:
        for capacity in capacities:
            for seed in seeds:
                trace = _make_trace(workload_name, capacity, seed, requests, url_count,
                                    alpha, hot_set_size, scan_factor)
                # Every code in a trace has a deterministic backing-store URL.
                expected = {code: f"https://shortlru.invalid/{code}" for code in set(trace.codes)}
                for repetition in range(1, repetitions + 1):
                    for strategy in strategies:
                        store = URLStore()
                        for code, url in expected.items():
                            store.save(code, url)
                        before = dict(expected)
                        admission = SecondAccessAdmission(window_size) if strategy == "second_access" else None
                        resolver = CacheAsideResolver(store, capacity, admission)
                        elapsed_by_phase: dict[str, float] = {}
                        phase_counts: dict[str, dict[str, int]] = {}
                        start_all = time.perf_counter()
                        cursor = 0
                        for phase in trace.phases:
                            phase_start = time.perf_counter()
                            for code in trace.codes[phase.start:phase.end]:
                                got = resolver.resolve(code)
                                if got != expected[code]:
                                    raise AssertionError(f"wrong URL for {code!r}: {got!r}")
                            elapsed_by_phase[phase.name] = (time.perf_counter() - phase_start) * 1000
                            after = _counter_snapshot(resolver)
                            before_phase = phase_counts.get("_previous", {k: 0 for k in after})
                            phase_counts[phase.name] = {k: after[k] - before_phase[k] for k in after}
                            phase_counts["_previous"] = after
                            cursor = phase.end
                        elapsed_all = (time.perf_counter() - start_all) * 1000
                        if len(store) != len(before) or any(store.get_url(k) != v for k, v in before.items()):
                            raise AssertionError("backing-store mappings changed during cache benchmark")
                        total = _counter_snapshot(resolver)
                        if total["hits"] + total["misses"] != len(trace):
                            raise AssertionError("cache hit/miss counters do not match request count")
                        overall = {
                            "row_type": "overall", "workload": workload_name, "phase": "all",
                            "strategy": strategy, "capacity": capacity, "seed": seed, "trial": repetition,
                            "requests": len(trace), "hits": total["hits"], "misses": total["misses"],
                            "hit_rate_percent": 100.0 * total["hits"] / len(trace) if trace else 0.0,
                            "evictions": total["evictions"], "store_lookups": total["store_lookups"],
                            "admissions": total["admissions"], "bypasses": total["bypasses"],
                            "elapsed_ms": elapsed_all, "window_size": window_size if admission else 0,
                        }
                        rows.append(overall)
                        for phase in trace.phases:
                            pc = phase_counts[phase.name]
                            phase_requests = phase.length
                            rows.append({
                                **overall, "row_type": "phase", "phase": phase.name,
                                "requests": phase_requests, "hits": pc["hits"], "misses": pc["misses"],
                                "hit_rate_percent": 100.0 * pc["hits"] / phase_requests if phase_requests else 0.0,
                                "evictions": pc["evictions"], "store_lookups": pc["store_lookups"],
                                "admissions": pc["admissions"], "bypasses": pc["bypasses"],
                                "elapsed_ms": elapsed_by_phase[phase.name],
                            })
    return rows


def write_experiment_csv(rows: list[dict[str, int | float | str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=EXPERIMENT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def print_experiment_summary(rows: list[dict[str, int | float | str]]) -> None:
    overall = [r for r in rows if r["row_type"] == "overall"]
    grouped: dict[tuple[str, int, str], list[float]] = {}
    for row in overall:
        grouped.setdefault((str(row["workload"]), int(row["capacity"]), str(row["strategy"])), []).append(
            float(row["hit_rate_percent"]))
    print("Median hit-rate summary (%)")
    print(f"{'Workload':<20}{'Capacity':<10}{'Strategy':<16}{'Median hit %':>12}")
    for (workload, capacity, strategy), values in sorted(grouped.items()):
        values.sort()
        mid = len(values) // 2
        median = values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2
        print(f"{workload:<20}{capacity:<10}{strategy:<16}{median:>12.2f}")


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
    parser.add_argument("--workloads", nargs="+", choices=sorted(WORKLOADS), default=None,
                        help="run the experimental strategy comparison instead of the legacy benchmark")
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 7, 2026])
    parser.add_argument("--strategies", nargs="+", choices=["lru", "second_access"], default=["lru", "second_access"])
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--window-size", type=int, default=20)
    parser.add_argument("--requests", type=int, default=4000,
                        help="request count for each experimental workload (hot_scan uses half per hot phase)")
    parser.add_argument("--url-count", type=int, default=64)
    parser.add_argument("--alpha", type=float, default=1.2)
    parser.add_argument("--hot-set-size", type=int, default=8)
    parser.add_argument("--scan-factor", type=float, default=3.0)
    parser.add_argument("--overwrite", action="store_true",
                        help="allow replacing an existing experimental output file")
    args = parser.parse_args()

    if args.workloads:
        if args.repetitions <= 0 or not args.seeds:
            parser.error("--repetitions must be positive and --seeds must not be empty")
        if args.window_size <= 0 or args.requests < 0:
            parser.error("--window-size must be positive and --requests non-negative")
        output = args.output or Path("results/admission_benchmark.csv")
        if output.exists() and not args.overwrite:
            parser.error(f"output already exists: {output} (pass --overwrite to replace it)")
        try:
            rows = run_experiments(
                workloads=args.workloads, capacities=args.capacities, seeds=args.seeds,
                repetitions=args.repetitions, strategies=args.strategies,
                window_size=args.window_size, requests=args.requests, url_count=args.url_count,
                alpha=args.alpha, hot_set_size=args.hot_set_size, scan_factor=args.scan_factor,
            )
            write_experiment_csv(rows, output)
        except (FileNotFoundError, ValueError) as exc:
            parser.error(str(exc))
        print(f"Experimental rows: {len(rows)}")
        print(f"Saved results to: {output}")
        print_experiment_summary(rows)
        return 0

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
