"""Generate legacy or experiment charts from ShortLRU benchmark CSV files."""
from __future__ import annotations

import argparse
import csv
import statistics
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def read_results(path: Path) -> list[dict[str, float]]:
    """Read the legacy benchmark CSV schema."""
    with path.open("r", newline="", encoding="utf-8") as file:
        return [
            {"capacity": float(row["capacity"]), "hit_rate_percent": float(row["hit_rate_percent"]),
             "hits": float(row["hits"]), "misses": float(row["misses"]),
             "evictions": float(row["evictions"]), "time_ms": float(row["time_ms"])}
            for row in csv.DictReader(file)
        ]


def _read_experiment(path: Path) -> list[dict[str, str | float]]:
    with path.open("r", newline="", encoding="utf-8") as file:
        return [{**row, "capacity": float(row["capacity"]),
                 "hit_rate_percent": float(row["hit_rate_percent"]),
                 "store_lookups": float(row["store_lookups"]),
                 "evictions": float(row["evictions"]), "elapsed_ms": float(row["elapsed_ms"])}
                for row in csv.DictReader(file)]


def make_charts(csv_path: Path, output_dir: Path) -> None:
    """Detect the CSV schema and produce matching charts."""
    with csv_path.open("r", newline="", encoding="utf-8") as file:
        fieldnames = next(csv.reader(file), [])
    if "row_type" in fieldnames:
        make_experiment_charts(csv_path, output_dir)
        return
    results = read_results(csv_path)
    if not results:
        raise ValueError("benchmark CSV contains no results")
    output_dir.mkdir(parents=True, exist_ok=True)
    capacities = [row["capacity"] for row in results]
    for metric, label, title, filename in [
        ("hit_rate_percent", "Hit Rate (%)", "ShortLRU: Cache Capacity vs Hit Rate", "cache_capacity_vs_hit_rate.png"),
        ("evictions", "Evictions", "ShortLRU: Cache Capacity vs Evictions", "cache_capacity_vs_evictions.png"),
    ]:
        plt.figure()
        plt.plot(capacities, [r[metric] for r in results], marker="o")
        plt.xlabel("Cache Capacity"); plt.ylabel(label); plt.title(title)
        plt.grid(True, alpha=0.25); plt.tight_layout()
        target = output_dir / filename; plt.savefig(target, dpi=160); plt.close()
        print(f"Created: {target}")


def make_experiment_charts(csv_path: Path, output_dir: Path) -> None:
    rows = [r for r in _read_experiment(csv_path) if r["row_type"] == "overall"]
    if not rows:
        raise ValueError("experiment CSV contains no overall rows")
    output_dir.mkdir(parents=True, exist_ok=True)
    groups = sorted({(str(r["workload"]), str(r["strategy"])) for r in rows})
    for metric, ylabel, title, filename in [
        ("hit_rate_percent", "Hit rate (%)", "Hit rate by capacity", "hit_rate_by_capacity.png"),
        ("store_lookups", "Backing-store lookups", "Backing-store lookups by capacity", "store_lookups_by_workload_strategy.png"),
        ("evictions", "Evictions", "Evictions by capacity", "evictions_by_capacity.png"),
        ("elapsed_ms", "Median elapsed time (ms)", "Median elapsed time by capacity", "median_elapsed_ms.png"),
    ]:
        plt.figure()
        for workload, strategy in groups:
            selected = [r for r in rows if r["workload"] == workload and r["strategy"] == strategy]
            by_capacity: dict[float, list[float]] = {}
            for row in selected:
                value = float(row["elapsed_ms"] if metric == "elapsed_ms" else row[metric])
                by_capacity.setdefault(float(row["capacity"]), []).append(value)
            xs = sorted(by_capacity)
            ys = [statistics.median(by_capacity[x]) for x in xs]
            lows = [min(by_capacity[x]) for x in xs]
            highs = [max(by_capacity[x]) for x in xs]
            plt.plot(xs, ys, marker="o", label=f"{workload} / {strategy}")
            if metric == "elapsed_ms":
                plt.vlines(xs, lows, highs, alpha=0.35)
        plt.xlabel("Cache capacity"); plt.ylabel(ylabel); plt.title(title)
        plt.grid(True, alpha=0.25); plt.legend(fontsize="small"); plt.tight_layout()
        target = output_dir / filename; plt.savefig(target, dpi=160); plt.close()
        print(f"Created: {target}")
    phase_rows = [r for r in _read_experiment(csv_path) if r["row_type"] == "phase" and r["workload"] == "hot_scan" and r["phase"] == "post_scan_hot"]
    if phase_rows:
        plt.figure()
        for strategy in sorted({str(r["strategy"]) for r in phase_rows}):
            selected = [r for r in phase_rows if r["strategy"] == strategy]
            by_capacity: dict[float, list[float]] = {}
            for row in selected:
                by_capacity.setdefault(float(row["capacity"]), []).append(float(row["hit_rate_percent"]))
            xs = sorted(by_capacity)
            plt.plot(xs, [statistics.median(by_capacity[x]) for x in xs], marker="o", label=strategy)
        plt.xlabel("Cache capacity"); plt.ylabel("Post-scan hot-phase hit rate (%)")
        plt.title("Hot-set hit rate after a one-time scan"); plt.grid(True, alpha=0.25)
        plt.legend(); plt.tight_layout()
        target = output_dir / "post_scan_hit_rate.png"; plt.savefig(target, dpi=160); plt.close()
        print(f"Created: {target}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate charts from ShortLRU benchmark results.")
    parser.add_argument("--input", type=Path, default=Path("results/benchmark.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    args = parser.parse_args()
    make_charts(args.input, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
