# ShortLRU Scan-Resistant Caching — Engineering Report

## Release summary

This release adds a separate experimental second-access admission policy and reproducible workload benchmarks while preserving the original URL-shortening and `LRUCache` implementation. The project remains an educational, single-process in-memory prototype.

## Baseline and preservation

- The supplied ZIP contained the original CLI URL shortener, SHA-256/Base62 code generation, in-memory `URLStore`, custom dictionary + doubly linked list `LRUCache`, original tests, legacy benchmark, and historical charts/CSV.
- Existing implementation files for the cache, store, URL shortener, CLI, dataset loader, demo, project configuration, original test modules, source dataset, and historical `results/benchmark.csv` were preserved. The public package exports were extended additively.
- The legacy command `python benchmark.py` was run after the changes. It still reports 49 dataset URLs, 5,000 operations, seed 42, and hit rates of 7.48%, 12.76%, 25.58%, and 49.58% for capacities 3, 5, 10, and 20.
- The original report mode was run against `results/benchmark.csv` and successfully produced the two legacy charts.

## Added and modified files

### Added
- `shortlru/workloads.py`: seeded Zipf-like, hot-scan, and popularity-shift trace generators; phase metadata; workload registry.
- `shortlru/admission.py`: `SecondAccessAdmission` plus `CacheAsideResolver`, isolated from LRU linked-list internals.
- `tests/test_workloads.py`: workload determinism, phase structure, disjoint sets and invalid-input tests.
- `tests/test_admission.py`: policy, expiry boundary, missing/empty codes, bounded tracking, store integrity, eviction and ordinary-LRU behavior.
- `tests/test_benchmark_experiment.py`: strategy comparison, counter consistency, phase rows and CSV writing.
- `tests/test_report.py`: experiment chart generation.
- `.gitignore`: Python bytecode, test caches, virtual environments, build artifacts and common editor/OS files.

### Modified
- `benchmark.py`: kept legacy functions and CLI path, added experimental workload/strategy flags, same-trace comparisons, per-phase records, output CSV schema, correctness checks and median summaries.
- `report.py`: kept legacy report support and added schema auto-detection plus five experiment charts using the actual CSV.
- `shortlru/__init__.py`: exported the two new classes.
- `README.md`: documented the policy, workloads, commands, measured results, trade-offs and limitations.

## Design

### Workloads
1. **Zipf:** seeded skewed access over a URL pool.
2. **Hot scan:** repeated accesses to a hot set, a one-time scan of unique codes, then a post-scan hot phase.
3. **Popularity shift:** accesses transition from one disjoint hot set to another.

Each generator uses a private seeded random generator. Identical parameters and seeds produce identical traces. Hot-scan trace length depends on the capacity being tested; for each capacity, both strategies receive the identical trace and backing-store mapping.

### Admission policy
`SecondAccessAdmission` records first observations on valid cache misses. A URL is eligible on a subsequent cache miss within the request-count window. An observation at sequence `s` is eligible through `s + window_size`, inclusive. All cache requests advance the global sequence, including cache hits and invalid/missing codes, but only valid backing-store misses are recorded. FIFO expiry bounds live tracking to at most `window_size + 1` observations. The policy does not change store mappings or the underlying LRU implementation.

`CacheAsideResolver` defaults to ordinary LRU when no admission object is supplied. This is separate from `URLShortener`, whose default behavior remains unchanged.

## Validation performed

Environment used for this run:
- Python 3.13.5
- pytest 9.0.2
- Matplotlib 3.10.8
- setuptools 82.0.1
- pip 25.1.1

Commands and outcomes:
- `python -m pip install -e ".[test,report]"`: the isolated build-dependency setup could not complete in this execution environment.
- `python -m pip install -e ".[test,report]" --no-build-isolation`: **passed**, editable package built and installed; required pytest and Matplotlib dependencies were already available.
- `python -m pytest -q`: **42 tests passed, 0 failed** (25 original tests plus 17 new tests).
- Repeatability smoke check: two identical seeded experiment runs produced identical logical rows after excluding elapsed-time measurements (36 rows compared).
- `python benchmark.py`: **passed**, legacy hit/miss/eviction outcomes matched the preserved baseline.
- `python report.py --input results/benchmark.csv --output-dir /tmp/shortlru-legacy-report-final`: **passed**, generated both legacy charts.
- Full experimental benchmark: **passed**, with 3 workloads × 4 capacities × 3 seeds × 5 repetitions × 2 strategies; 1,080 CSV rows including overall and phase-level records.
- `python report.py --input results/admission_benchmark.csv --output-dir results`: **passed**, generated five experiment charts.

The normal pip-install attempt failed because build isolation could not complete dependency setup in this environment; the no-build-isolation editable install succeeded. This is disclosed rather than hidden.

## Experimental configuration

- Workloads: `zipf`, `hot_scan`, `popularity_shift`
- Capacities: 4, 8, 16, 32
- Seeds: 42, 7, 2026
- Repetitions: 5 per seed/configuration
- Admission window: 20 requests
- Requested workload size: 4,000; hot-scan and popularity-shift split the hot requests between phases, with hot-scan additionally inserting its capacity-scaled scan.
- Strategies: ordinary `lru` and `second_access`
- Metrics: requests, hits, misses, hit rate, evictions, explicit backing-store lookups, admissions, first-observation bypasses and elapsed milliseconds.
- Every valid request was checked against the expected URL, and store mappings were checked for integrity after each trial.

## Measured results

The table gives median hit rate across 15 runs (three seeds × five repetitions) for each workload/capacity/strategy.

| Workload / phase | Capacity | Ordinary LRU | Second-access |
|---|---:|---:|---:|
| Zipf, overall | 4 | 37.52% | 47.05% |
| Zipf, overall | 8 | 54.95% | 63.35% |
| Zipf, overall | 16 | 71.53% | 76.12% |
| Zipf, overall | 32 | 86.17% | 86.62% |
| Hot scan, post-scan hot phase | 4 | 49.45% | 50.10% |
| Hot scan, post-scan hot phase | 8 | 99.60% | 100.00% |
| Hot scan, post-scan hot phase | 16 | 99.60% | 100.00% |
| Hot scan, post-scan hot phase | 32 | 99.60% | 100.00% |
| Popularity shift, overall | 4 | 71.80% | 74.45% |
| Popularity shift, overall | 8 | 99.60% | 99.08% |
| Popularity shift, overall | 16 | 99.60% | 99.08% |
| Popularity shift, overall | 32 | 99.60% | 99.08% |

Selected median backing-store lookups:
- Zipf, capacity 8: 1,802 for LRU vs 1,466 for second-access.
- Zipf, capacity 4: 2,499 for LRU vs 2,118 for second-access.
- Popularity shift, capacity 8: 16 for LRU vs 37 for second-access.

Across all overall rows, median elapsed time was approximately 1.57 ms for LRU and 1.92 ms for second-access in this environment. This pooled summary is only a local timing observation, not a controlled universal speed comparison.

## Interpretation and trade-offs

- Second-access admission improves hit rate in the tested Zipf traces, especially when capacity is scarce.
- It reaches a 100% post-scan hit rate in the tested hot-scan traces for capacities 8, 16 and 32, indicating that the hot set survived that scan in this setup.
- It can slightly reduce hit rate and increase backing-store lookups during popularity shifts, where admission warm-up delays caching of the new hot set.
- It adds bookkeeping overhead and was slower in pooled elapsed-time medians in this run.
- These results are from synthetic workloads. They do not establish a universal performance advantage or prove behavior on production traffic.

## Limitations

- In-memory store; no persistence, network service or multi-process coordination.
- Synthetic traces, not real production traffic.
- Hot-scan trace differs by capacity because scan length scales with capacity; the two strategies share each individual trace.
- Local timings are affected by system load and Python runtime noise.
- One admission window (20) was evaluated; no window-size sweep or statistical hypothesis test was performed.
- The second-access idea belongs to an established family of cache-admission policies. The project contribution is the specific implementation, integration, reproducible experiments and evaluation, not a claim to invent admission control.

## Release status

**Ready for an educational GitHub release and LinkedIn showcase**, with the above scope and limitations stated accurately. The ZIP should contain source, tests, the source dataset, historical results, the experiment CSV, and generated charts; transient Python caches and package metadata are excluded.
