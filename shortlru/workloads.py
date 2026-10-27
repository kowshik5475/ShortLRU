"""Deterministic synthetic request workloads for cache experiments.

These traces are synthetic models, not claims about production traffic.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Callable


@dataclass(frozen=True, slots=True)
class Phase:
    name: str
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass(frozen=True, slots=True)
class WorkloadTrace:
    name: str
    codes: tuple[str, ...]
    phases: tuple[Phase, ...]
    metadata: dict[str, int | float | str]

    def __len__(self) -> int:
        return len(self.codes)


def make_code(prefix: str, index: int) -> str:
    if index < 0:
        raise ValueError("index must be non-negative")
    return f"{prefix}{index:08x}"


def _validate(count: int, requests: int) -> None:
    if count <= 0:
        raise ValueError("url_count must be greater than 0")
    if requests < 0:
        raise ValueError("requests must be non-negative")


def _zipf_sample(rng: random.Random, count: int, alpha: float) -> int:
    weights = [1.0 / (rank ** alpha) for rank in range(1, count + 1)]
    total = sum(weights)
    target = rng.random() * total
    running = 0.0
    for i, weight in enumerate(weights):
        running += weight
        if running >= target:
            return i
    return count - 1


def zipf_hotset(url_count: int = 64, requests: int = 4000, alpha: float = 1.2, seed: int = 42) -> WorkloadTrace:
    """Generate a Zipf-like trace using a private seeded RNG."""
    _validate(url_count, requests)
    if not math.isfinite(alpha) or alpha < 0:
        raise ValueError("alpha must be finite and non-negative")
    rng = random.Random(seed)
    pool = [make_code("z", i) for i in range(url_count)]
    trace = tuple(pool[_zipf_sample(rng, url_count, alpha)] for _ in range(requests))
    return WorkloadTrace("zipf", trace, (Phase("all", 0, len(trace)),),
                         {"url_count": url_count, "requests": requests, "alpha": alpha, "seed": seed})


def hot_scan(capacity: int = 8, hot_set_size: int = 8, scan_factor: float = 3.0,
             hot_requests: int = 1000, seed: int = 42) -> WorkloadTrace:
    """Hot accesses, a one-time scan of unique codes, then hot accesses again."""
    if capacity <= 0 or hot_set_size <= 0:
        raise ValueError("capacity and hot_set_size must be greater than 0")
    if not math.isfinite(scan_factor) or scan_factor <= 0:
        raise ValueError("scan_factor must be finite and greater than 0")
    if hot_requests < 0:
        raise ValueError("hot_requests must be non-negative")
    rng = random.Random(seed)
    hot = [make_code("h", i) for i in range(hot_set_size)]
    scan_count = max(1, math.ceil(capacity * scan_factor))
    scan = [make_code("s", i) for i in range(scan_count)]
    first = tuple(rng.choice(hot) for _ in range(hot_requests))
    scan_phase = tuple(scan)
    last = tuple(rng.choice(hot) for _ in range(hot_requests))
    codes = first + scan_phase + last
    a = len(first); b = a + len(scan_phase)
    return WorkloadTrace("hot_scan", codes,
        (Phase("pre_scan_hot", 0, a), Phase("scan", a, b), Phase("post_scan_hot", b, len(codes))),
        {"capacity": capacity, "hot_set_size": hot_set_size, "scan_factor": scan_factor,
         "scan_count": scan_count, "hot_requests_per_phase": hot_requests, "seed": seed})


def popularity_shift(hot_set_size: int = 8, requests_per_phase: int = 2000,
                     alpha: float = 1.2, seed: int = 42) -> WorkloadTrace:
    """Generate Zipf-weighted requests whose popular set changes halfway."""
    if hot_set_size <= 0 or requests_per_phase < 0:
        raise ValueError("hot_set_size must be positive and requests_per_phase non-negative")
    if not math.isfinite(alpha) or alpha < 0:
        raise ValueError("alpha must be finite and non-negative")
    rng = random.Random(seed)
    set_a = [make_code("a", i) for i in range(hot_set_size)]
    set_b = [make_code("b", i) for i in range(hot_set_size)]
    first = tuple(set_a[_zipf_sample(rng, hot_set_size, alpha)] for _ in range(requests_per_phase))
    second = tuple(set_b[_zipf_sample(rng, hot_set_size, alpha)] for _ in range(requests_per_phase))
    return WorkloadTrace("popularity_shift", first + second,
        (Phase("hot_set_a", 0, len(first)), Phase("hot_set_b", len(first), len(first) + len(second))),
        {"hot_set_size": hot_set_size, "requests_per_phase": requests_per_phase, "alpha": alpha, "seed": seed})


WORKLOADS: dict[str, Callable[..., WorkloadTrace]] = {
    "zipf": zipf_hotset, "hot_scan": hot_scan, "popularity_shift": popularity_shift
}


def build_workload(name: str, *, seed: int = 42, capacity: int = 8, requests: int = 4000) -> WorkloadTrace:
    """Build a workload by registry name with consistent default parameters."""
    if name == "zipf":
        return zipf_hotset(requests=requests, seed=seed)
    if name == "hot_scan":
        return hot_scan(capacity=capacity, hot_requests=requests // 2, seed=seed)
    if name == "popularity_shift":
        return popularity_shift(requests_per_phase=requests // 2, seed=seed)
    raise ValueError(f"unknown workload: {name}")
