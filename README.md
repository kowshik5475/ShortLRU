# ShortLRU

ShortLRU is a small, educational command-line URL shortener designed to demonstrate four core software-engineering concepts:

- **Hashing** with SHA-256
- **Base62 encoding** for compact short codes
- **LRU caching** using a hash map plus a doubly linked list
- **Object-oriented design** with separate cache, store, service, and CLI responsibilities

It deliberately does **not** use Flask, FastAPI, a web UI, or an external database.

## Project overview

A URL shortener turns a long URL such as:

```text
https://example.com/articles/learning-data-structures
```

into a shorter identifier such as:

```text
Ab3xYz1
```

The identifier is not the URL itself. It is a key that lets the application look up the original URL.

ShortLRU has two important layers:

1. `URLStore`: the backing mapping of short code <-> original URL.
2. `LRUCache`: a fast temporary copy of recently used mappings.

`URLShortener` coordinates both.

## Features

- Custom O(1) LRU cache
- Python dictionary for direct key lookup
- Doubly linked list for recency ordering
- Configurable cache capacity, default `3`
- Hit, miss, eviction, and hit-rate statistics
- SHA-256 URL hashing
- Base62 short-code generation
- Idempotent shortening
- Collision detection with progressively longer codes
- Cache-aside URL resolution
- Simple command-line interface
- Interactive one-process LRU demonstration
- Pytest test suite
- No runtime dependencies outside the Python standard library

## Architecture

```text
                  +------------------+
                  |       CLI        |
                  +--------+---------+
                           |
                           v
                  +------------------+
                  |   URLShortener   |
                  +--------+---------+
                           |
                +----------+----------+
                |                     |
                v                     v
         +-------------+       +-------------+
         |  LRUCache   |       |  URLStore   |
         +-------------+       +-------------+
         | dict + DLL  |       | two dicts   |
         +-------------+       +-------------+
```

### Responsibilities

**`LRUCache`**

Stores recently used `short_code -> URL` values. It is optimized for fast reads and automatically removes the least recently used entry when full.

**`URLStore`**

Acts like a database abstraction. It maintains:

```text
short_code -> original_url
original_url -> short_code
```

This project uses dictionaries for simplicity. A later version could replace the implementation with SQLite, PostgreSQL, Redis, or another persistent store.

**`URLShortener`**

Coordinates hashing, code generation, collision detection, the backing store, and the cache.

**`cli.py`**

Provides command-line commands without changing the core classes.

## Project structure

```text
ShortLRU/
├── shortlru/
│   ├── __init__.py
│   ├── cache.py
│   ├── admission.py
│   ├── workloads.py
│   ├── store.py
│   ├── shortener.py
│   ├── dataset.py
│   └── cli.py
├── tests/
│   ├── test_cache.py
│   ├── test_shortener.py
│   ├── test_dataset.py
│   ├── test_benchmark.py
│   ├── test_workloads.py
│   ├── test_admission.py
│   ├── test_benchmark_experiment.py
│   └── test_report.py
├── data/
├── results/
├── benchmark.py
├── report.py
├── demo.py
├── pyproject.toml
├── README.md
├── ENGINEERING_REPORT.md
└── .gitignore
```

## How the LRU cache works

LRU means **Least Recently Used**.

With capacity 3, suppose the cache contains:

```text
MRU -> LRU

C -> B -> A
```

If `A` is accessed, it becomes most recent:

```text
A -> C -> B
```

If `D` is inserted, the cache is full, so `B` is removed:

```text
D -> A -> C
```

### Why a dictionary?

A dictionary gives average O(1) lookup:

```python
node = self._items.get(key)
```

Without it, finding a particular node by scanning the linked list would be O(n).

### Why a doubly linked list?

The dictionary tells us **which node** belongs to a key. It does not tell us the order in which nodes were recently used.

The doubly linked list maintains:

```text
head <-> most recent ... least recent <-> tail
```

Because each node has both `previous` and `next` references, a node can be detached and inserted at the front in O(1).

### Why both together?

The combination gives:

```text
Dictionary:
key -> exact linked-list node

Linked list:
MRU -> ... -> LRU
```

Therefore:

- `get`: dictionary lookup + move node = O(1)
- `put`: dictionary lookup/insertion + list update = O(1)
- promotion: pointer changes = O(1)
- eviction: remove tail-adjacent node = O(1)

The hash map and linked list solve different parts of the problem.

## How hashing works

ShortLRU uses SHA-256:

```python
digest = hashlib.sha256(url.encode("utf-8")).digest()
number = int.from_bytes(digest, byteorder="big")
```

SHA-256 produces a deterministic 256-bit digest.

The same input URL produces the same digest:

```text
URL
 |
 v
SHA-256
 |
 v
256-bit digest
 |
 v
integer
```

This makes a deterministic candidate short code possible.

Hashing is not the same thing as encryption. SHA-256 is a one-way cryptographic hash function; the project uses it as a deterministic source of bits for code generation.

## How Base62 works

A raw SHA-256 digest is not convenient as a short URL identifier. We convert its integer representation to Base62.

Base62 uses:

```text
0-9
a-z
A-Z
```

That is 62 symbols.

For example, conceptually:

```text
decimal number -> repeated division by 62 -> Base62 digits
```

Base62 is useful because each character carries more information than a decimal digit.

The project initially uses the first 7 characters of the Base62-encoded hash:

```text
ABCDEFGH...
^^^^^^^
7-character candidate
```

## URL shortening algorithm

`URLShortener.shorten(url)` follows these steps:

1. Reject an empty URL.
2. Check `URLStore`'s reverse map.
3. If the URL already exists, return its existing code.
4. Compute SHA-256.
5. Convert the digest integer to Base62.
6. Start with a 7-character code.
7. Check whether that code is already assigned.
8. If there is a collision, include one more Base62 character.
9. Continue until a unique code is found.
10. Save both directions in the store.
11. Put the mapping into the cache.

### Why the reverse map is needed

Hashing makes the candidate deterministic, but a shortened URL is required to be **idempotent**:

```text
shorten("https://example.com")
       |
       v
      abc1234

shorten("https://example.com")
       |
       v
      abc1234
```

The reverse map:

```text
original_url -> short_code
```

guarantees that the application can directly answer:

> Have we already shortened this exact URL?

It also prevents a code collision from accidentally replacing an existing mapping.

## Collision handling

The initial code uses 7 Base62 characters.

Suppose two different URLs produce:

```text
URL A -> ABCDEFGH...
URL B -> ABCDEFGZ...
```

The first candidates are both:

```text
ABCDEFG
```

That is a collision.

The implementation detects that `ABCDEFG` already belongs to another URL and tries the next length:

```text
ABCDEFGH
```

Now the second URL can use:

```text
ABCDEFGZ
```

The key idea is:

```text
7 chars -> collision
8 chars -> try again
9 chars -> try again
...
```

A full SHA-256 collision would be extraordinarily unlikely. The progressive-prefix logic is primarily an educational demonstration of collision handling.

## Cache-aside resolution

`resolve(code)` uses the cache-aside pattern:

```text
resolve(code)
      |
      v
Check LRU cache
      |
      +---- HIT ----> return URL
      |
      +---- MISS
             |
             v
       Check URLStore
             |
             +---- Found ----> put into cache ----> return URL
             |
             +---- Not found ----> return None
```

The cache does not have to contain every stored URL.

On a miss, the application checks the backing store and then populates the cache.

This is called **cache-aside** because the application code explicitly reads from and writes to the cache around the backing store.

## Dry-run: capacity 3

Use these three URLs:

```text
URL A
URL B
URL C
```

After inserting all three, the most recent order is:

```text
C -> B -> A
```

Now access URL A.

A cache hit promotes A:

```text
A -> C -> B
```

Now add URL D.

D becomes most recent:

```text
D -> A -> C -> B
```

But capacity is 3, so the least recent item, B, is evicted:

```text
D -> A -> C
```

Now resolve B.

The cache does not contain B:

```text
Cache miss
    |
    v
URLStore lookup
    |
    v
B found
    |
    v
Insert B into cache
```

Before inserting B:

```text
D -> A -> C
```

After B is inserted:

```text
B -> D -> A
```

C is now the least recently used and is evicted.

This demonstrates an important property: **evicting from the cache does not delete the URL from the backing store.**

## Complexity analysis

| Operation | Complexity |
| --- | --- |
| LRU `get` | O(1) average |
| LRU `put` | O(1) average |
| LRU promotion | O(1) |
| LRU eviction | O(1) |
| Store lookup | O(1) average |
| Store save | O(1) average |
| URL hashing | O(n) |
| Base62 conversion | O(k), where k is encoded hash length |
| URL shortening | O(n) average, excluding unusual collision retries |
| URL resolution, cache hit | O(1) average |
| URL resolution, cache miss | O(1) average after hash-map store lookup |

Here, `n` is the URL length. `k` is bounded by the fixed SHA-256 digest size, so Base62 conversion is effectively bounded for a given hash algorithm.

### Space complexity

The LRU cache uses O(capacity) space.

The URL store uses O(m) space for `m` stored URL mappings.

The linked-list nodes and dictionary entries are both proportional to the cache capacity.

## Installation

Use Python 3.10 or newer.

From the `ShortLRU` directory:

```bash
python -m venv .venv
```

Activate it.

Linux/macOS:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install the project and test dependency:

```bash
python -m pip install -e ".[test]"
```

There are no runtime third-party dependencies.

## CLI usage

### Shorten

```bash
python -m shortlru.cli shorten https://example.com
```

Example:

```text
Short code: 8zQx2aB
```

The exact code depends on the SHA-256 result.

### Resolve

```bash
python -m shortlru.cli resolve 8zQx2aB
```

Example:

```text
URL: https://example.com
```

### Statistics

```bash
python -m shortlru.cli stats
```

Example:

```text
Cache capacity: 3
Cache size:     0
Hits:           0
Misses:         0
Evictions:      0
Hit rate:       0.00%
```

### Custom capacity

Put the global option before the subcommand:

```bash
python -m shortlru.cli --capacity 5 shorten https://example.com
```

or:

```bash
python -m shortlru.cli --capacity 5 stats
```

## Important CLI limitation

The educational CLI creates a new `URLShortener` every time the command starts.

Therefore:

```bash
python -m shortlru.cli shorten https://example.com
```

and then:

```bash
python -m shortlru.cli resolve <code>
```

are separate Python processes.

Because `URLStore` currently uses in-memory dictionaries, they do **not** share state.

This is intentional: the project focuses on data structures rather than persistence.

A persistent database would solve this by storing the mappings outside the Python process. SQLite would be a natural first upgrade because it requires no database server.

The `demo.py` program is different: all operations happen in one process, so its cache and store state are shared throughout the demonstration.

## Interactive demo

Run:

```bash
python demo.py
```

It demonstrates:

1. Create a cache with capacity 3.
2. Insert A, B, C.
3. Resolve A and create a cache hit.
4. Insert D.
5. Observe B being evicted.
6. Resolve B.
7. Observe the cache miss and store lookup.
8. Observe B being repopulated into the cache.
9. Print final statistics.

## Testing

Run all tests:

```bash
pytest
```

or:

```bash
python -m pytest
```

The tests cover:

- insertion
- lookup
- misses
- LRU promotion
- LRU eviction
- capacity
- hits
- misses
- evictions
- hit rate
- invalid capacity
- URL shortening
- idempotent shortening
- resolution
- cache hits
- backing-store lookup after a miss
- cache repopulation
- collision handling

## Example test output

A typical run looks like:

```text
...........................                                      [100%]
27 passed
```

The exact count may change if more tests are added.

## Important methods: small internal examples

### `LRUCache.get("A")`

Suppose:

```text
Dictionary:
A -> NodeA

List:
C <-> B <-> A
```

The dictionary finds `NodeA` directly.

Then `_move_to_front(NodeA)` changes the pointers:

```text
A <-> C <-> B
```

No scan is required.

### `LRUCache.put("D", "URL-D")`

If the cache is:

```text
A -> C -> B
```

and capacity is 3:

```text
D -> A -> C -> B
```

The cache is now too large, so the node immediately before the tail sentinel (`B`) is removed:

```text
D -> A -> C
```

### `URLStore.save(code, url)`

The store updates both indexes:

```text
_code_to_url[code] = url
_url_to_code[url] = code
```

This supports both directions efficiently.

### `URLShortener.resolve(code)`

First:

```python
cached_url = self.cache.get(code)
```

If it exists, return immediately.

Otherwise:

```python
stored_url = self.store.get_url(code)
```

If the store finds it:

```python
self.cache.put(code, stored_url)
```

Then return the URL.

## Beginner-friendly walkthrough

### 1. What problem does this solve?

We want to turn a long URL into a short identifier while still being able to recover the original URL.

The core mapping is:

```text
short code -> original URL
```

### 2. Why do URL shorteners need a mapping?

A code such as:

```text
Ab12Cd3
```

does not contain the full original URL. It is an identifier.

Therefore the application needs a lookup structure:

```text
Ab12Cd3 -> https://example.com/some/very/long/path
```

### 3. Why is a cache useful?

Popular URLs may be resolved repeatedly.

Instead of going to the backing store every time, the application keeps recently used mappings in memory:

```text
cache -> fast
store -> authoritative
```

### 4. What does LRU mean?

LRU means Least Recently Used.

When the cache is full, remove the item that has gone unused for the longest time.

This keeps recently useful entries while discarding colder entries.

### 5. Why is a hash map alone insufficient?

A dictionary can answer:

```text
Where is code A?
```

quickly.

But it does not naturally maintain:

```text
Which entry was used least recently?
```

You need an ordering structure for that.

### 6. Why a doubly linked list?

A doubly linked list lets a node point both directions:

```text
previous <-> node <-> next
```

That makes removal and insertion possible with a small number of pointer assignments.

### 7. How do the two structures work together?

The dictionary points to the exact list node:

```text
items["A"] -> NodeA
```

The list records recency:

```text
head -> A -> C -> B -> tail
         MRU       LRU
```

This combination avoids scanning.

### 8. `LRUCache` walkthrough

The constructor validates capacity and creates:

```python
self._items = {}
```

for direct lookup.

It then creates two sentinel nodes:

```python
self._head
self._tail
```

The real nodes live between them:

```text
head <-> real nodes <-> tail
```

The sentinels are not cache entries. They simplify edge cases.

`_remove(node)` reconnects the node's neighbors:

```text
previous <-> node <-> next

becomes

previous <-> next
```

`_add_to_front(node)` inserts a node immediately after `head`.

`_move_to_front(node)` does:

```text
remove
add to front
```

`_remove_least_recently_used()` selects:

```python
self._tail.previous
```

because the node directly before the tail is the least recent real node.

`get()`:

1. looks in the dictionary;
2. records a miss if absent;
3. records a hit if present;
4. promotes the node;
5. returns its value.

`put()`:

1. updates and promotes an existing node, or
2. creates a new node;
3. inserts it at the front;
4. evicts the tail-side node if capacity is exceeded.

`stats()` calculates:

```text
hit rate = hits / (hits + misses)
```

with 0.0 used when there have been no lookups.

### 9. `URLStore`

The store has two dictionaries:

```text
_code_to_url
_url_to_code
```

The first supports resolution.

The second supports idempotent shortening.

For example:

```text
_code_to_url:
abc1234 -> https://example.com

_url_to_code:
https://example.com -> abc1234
```

### 10. SHA-256

SHA-256 accepts bytes and returns a 256-bit digest.

For example:

```python
hashlib.sha256(url.encode("utf-8")).digest()
```

The result is deterministic.

That means the same URL always starts with the same hash-derived candidate.

### 11. Base62

The SHA-256 digest is interpreted as a large integer.

That integer is repeatedly divided by 62.

Each remainder selects a Base62 character.

The resulting characters are compact enough to make a convenient short code.

### 12. Collision handling

Two different URLs can share a short prefix even though their complete hashes differ.

For example:

```text
URL A -> ABCDEFGH...
URL B -> ABCDEFGZ...
```

Both initially propose:

```text
ABCDEFG
```

The store detects that this code is already owned by URL A.

URL B therefore extends its candidate:

```text
ABCDEFGZ
```

and gets a unique code.

### 13. Idempotent shortening

Before hashing, `shorten()` asks:

```python
existing_code = self.store.get_code(url)
```

If found, it returns that code.

So:

```text
shorten(URL A) -> X
shorten(URL A) -> X
```

This is why the reverse mapping matters.

### 14. `URLShortener.shorten()`

The service first validates the input.

Then it checks the reverse map.

For a new URL:

```text
URL
 |
 v
SHA-256
 |
 v
integer
 |
 v
Base62
 |
 v
7-character candidate
 |
 v
collision check
 |
 v
URLStore
 |
 v
LRUCache
```

### 15. `URLShortener.resolve()`

The flow is:

```text
code
 |
 v
cache.get(code)
 |
 +-- hit --> URL
 |
 +-- miss
       |
       v
  store.get_url(code)
       |
       +-- missing --> None
       |
       +-- found
             |
             v
        cache.put(...)
             |
             v
            URL
```

### 16. Hits and misses

A call to:

```python
cache.get("A")
```

is a hit if A is currently cached.

Otherwise it is a miss.

The counters belong to the cache because they measure cache behavior, not whether the URL exists in the store.

A store lookup after a cache miss does not erase the fact that the cache missed.

### 17. Eviction with capacity 3

Starting with:

```text
C -> B -> A
```

Access A:

```text
A -> C -> B
```

Insert D:

```text
D -> A -> C
```

B was at the back, so B is evicted.

### 18. CLI

`cli.py` uses Python's standard-library `argparse`.

Commands:

```bash
python -m shortlru.cli shorten <url>
python -m shortlru.cli resolve <code>
python -m shortlru.cli stats
```

The global capacity option is:

```bash
python -m shortlru.cli --capacity 3 stats
```

The CLI deliberately does not contain URL-shortening logic. It delegates to `URLShortener`.

### 19. Tests

The tests are separated into:

```text
tests/test_cache.py
tests/test_shortener.py
```

Cache tests focus on data-structure behavior.

Shortener tests focus on service behavior, store interaction, cache-aside resolution, idempotency, and collision handling.

The collision test replaces the hash-to-Base62 method with controlled values so a collision can be demonstrated deterministically without relying on a real SHA-256 collision.

### 20. Time and space complexity

For the LRU:

```text
get       O(1)
put       O(1)
promotion O(1)
eviction  O(1)
```

For the store:

```text
lookup    O(1) average
save      O(1) average
```

Hashing is O(n) in the URL length.

The cache consumes O(capacity) memory.

The store consumes O(number of stored mappings) memory.

### 21. Limitations

This is intentionally an educational implementation.

Important limitations:

- Store data disappears when the Python process ends.
- Separate CLI invocations do not share the in-memory store.
- There is no HTTP API.
- There is no authentication or authorization.
- There is no URL expiration.
- There is no custom alias support.
- SHA-256/Base62 codes are not cryptographic access controls.
- There is no concurrency or distributed-cache coordination.
- The collision strategy is intentionally simple.
- No URL reachability validation is performed; only empty input is rejected.

### 22. Extending to SQLite/PostgreSQL

The core classes already separate storage from service logic.

A database-backed store could implement the same public methods:

```python
save(code, url)
get_url(code)
get_code(url)
contains_code(code)
```

For example:

```text
URLShortener
     |
     v
URLStore interface/contract
     |
     +---- InMemoryURLStore
     |
     +---- SQLiteURLStore
     |
     +---- PostgreSQLURLStore
```

The service would not need to know how rows are stored.

SQLite is a good first upgrade because it can persist data in one local file without a separate server.

### 23. Adding a Flask/FastAPI API later

The core classes should remain independent of the HTTP layer.

A future API could simply call:

```python
shortener.shorten(url)
shortener.resolve(code)
```

For example, conceptually:

```text
HTTP POST /shorten
        |
        v
URLShortener.shorten()
        |
        v
JSON response

HTTP GET /abc1234
        |
        v
URLShortener.resolve()
        |
        v
redirect/JSON response
```

The API layer becomes an adapter around the existing service.

That separation is an important OOP and system-design lesson: business logic does not need to know whether it was called by a CLI, HTTP API, test, or another Python program.

## Possible future improvements

1. Persist mappings with SQLite.
2. Add an abstract store interface.
3. Add URL expiration timestamps.
4. Add custom aliases.
5. Add configurable initial code length.
6. Add a database-backed unique constraint for collision safety.
7. Add thread-safe locking.
8. Add structured logging.
9. Add more property-based tests.
10. Add benchmarks comparing cache hits and store lookups.
11. Add an HTTP adapter without changing the core service.
12. Add metrics such as requests per second and cache utilization.

## Learning goals

After studying this project, you should be able to explain:

- Why dictionaries are useful for hashing and average O(1) lookup.
- Why LRU requires both lookup and ordering.
- How doubly linked lists support O(1) movement.
- How SHA-256 can provide deterministic hash material.
- How integer-to-Base62 conversion creates compact identifiers.
- Why deterministic hashing alone does not guarantee idempotency.
- How reverse indexes help answer the same-URL question.
- How cache-aside works.
- Why cache eviction is different from deleting persistent data.
- How separate classes improve separation of concerns.
- How an in-memory prototype can later be replaced by a persistent backend.


## Dataset and benchmark

The project now includes a small curated CSV dataset:

```text
data/
└── urls.csv
```

The dataset contains URLs and categories such as programming, development,
web, data science, machine learning, cloud, databases, and science.

The dataset is intentionally small and self-contained. It does not require
an internet connection and does not download or scrape websites.

### Dataset format

```csv
url,category
https://www.python.org/,programming
https://github.com/,development
https://pandas.pydata.org/,data-science
```

`shortlru.dataset.load_urls()` reads the file and returns typed `DatasetURL`
records.

### Run the benchmark

From the project root:

```bash
python benchmark.py
```

Example:

```text
=== ShortLRU Benchmark ===
Dataset URLs:       50
Operations:         5000
Hot-set fraction:   70%
Random seed:        42

Capacity    Hit Rate      Hits      Misses    Evictions   Time (ms)
--------------------------------------------------------------------
3           ...
5           ...
10          ...
20          ...
```

The exact numbers depend on the machine running the benchmark.

The benchmark deliberately uses a **hot workload**. Some URLs are selected
more frequently than others. This represents temporal locality, which is the
behavior an LRU cache is designed to exploit.

You can customize it:

```bash
python benchmark.py --capacities 3 10 25 50 --operations 10000
```

Change the workload locality:

```bash
python benchmark.py --hot-fraction 0.90
```

A larger hot fraction generally makes caching more effective because a small
set of URLs is reused frequently.

### What the benchmark teaches

The benchmark lets you experimentally observe the relationship between:

```text
Cache capacity
      |
      v
Number of cache hits
      |
      v
Hit rate
      |
      v
Number of evictions
```

For example, a very small cache may repeatedly evict URLs that are needed
again soon. Increasing the capacity can reduce those evictions.

This turns the project from only a code demonstration into a small
data-structures experiment.

### Dataset architecture

```text
data/urls.csv
      |
      v
load_urls()
      |
      v
DatasetURL records
      |
      v
URLShortener
      |
      +----------------+
      |                |
      v                v
  URLStore         LRUCache
```

The dataset is **test/benchmark input**, not a database. The URLStore remains
the application's backing-store abstraction.

### Why a dataset is useful here

A URL shortener does not require a machine-learning dataset. The important
data structure is the URL-to-code mapping.

However, a dataset makes the project more realistic because it allows us to:

- process many URLs;
- generate repeatable workloads;
- compare different cache capacities;
- measure cache hit rates;
- measure evictions;
- discuss temporal locality;
- produce quantitative results for a portfolio report.

The benchmark is therefore an experiment around the data structures rather
than an artificial requirement for the application itself.


## Benchmark reports and visualization

For a portfolio project, benchmark results are more useful when they can be
saved and visualized.

Save benchmark results as CSV:

```bash
python benchmark.py --output results/benchmark.csv
```

Install the optional reporting dependency:

```bash
python -m pip install -e ".[report]"
```

Then generate charts:

```bash
python report.py
```

This creates:

```text
results/
├── benchmark.csv
├── cache_capacity_vs_hit_rate.png
└── cache_capacity_vs_evictions.png
```

### What the charts mean

**Cache capacity vs hit rate**

A larger cache can retain more recently used URLs. When the workload has
temporal locality, this generally increases the chance that a requested URL
is already cached.

**Cache capacity vs evictions**

A larger cache generally needs to evict entries less frequently because more
entries can remain resident at the same time.

These graphs make the relationship between the LRU algorithm and measurable
system behavior easier to explain during a project presentation.

### Recommended experiment

Run:

```bash
python benchmark.py --capacities 3 5 10 20 30 40 --operations 10000 --output results/benchmark.csv
python report.py
```

Then include the generated charts in your project report or presentation.

The benchmark uses a fixed random seed by default, making the workload
reproducible. Change `--seed` if you want to experiment with a different
access pattern.


## Experimental extension: scan-resistant cache admission

ShortLRU includes an experimental second-access admission policy alongside ordinary LRU. The existing `LRUCache` implementation and default `URLShortener` behavior remain unchanged.

### Policy

`SecondAccessAdmission` records a cache-miss observation and admits a known URL on a subsequent cache miss if it occurs within a configurable request-count window. The observation at sequence `s` remains eligible through `s + window_size` (inclusive). Every cache access advances the global request sequence, including cache hits and misses for unknown codes. Wall-clock time is not used. A FIFO queue expires stale observations so tracking retains at most `window_size + 1` live request-sequence observations rather than every URL ever seen.

The `CacheAsideResolver` supplies an isolated cache-aside integration. Passing no admission policy gives ordinary LRU; passing `SecondAccessAdmission(window_size=20)` enables the experimental policy. Admission affects only cache population, not URL-store mappings.

### Synthetic workloads

- **Zipf:** skewed popularity across a configurable URL pool.
- **Hot scan:** repeated requests to a hot set, a scan of unique URLs, and a second hot phase.
- **Popularity shift:** Zipf-like requests transition from hot set A to disjoint hot set B.

Each workload uses a private seeded random generator. The same seed and parameters produce the same trace. These are synthetic workload models, not production traffic. Hot-scan traces are parameterized by cache capacity, so traces differ across capacities; both strategies always receive the exact same trace within a configuration.

### Install, test, and reproduce

```bash
python -m pip install -e ".[test,report]"
python -m pytest
python benchmark.py
python benchmark.py --workloads zipf hot_scan popularity_shift \
  --capacities 4 8 16 32 --seeds 42 7 2026 --repetitions 5 \
  --window-size 20 --requests 4000 \
  --output results/admission_benchmark.csv --overwrite
python report.py --input results/admission_benchmark.csv --output-dir results
```

The legacy `python benchmark.py` command and its original CSV schema remain supported. Experimental output includes overall and per-phase rows. It records hits, misses, hit rate, evictions, explicit backing-store lookups, admissions, first-observation bypasses, elapsed time, strategy, seed, trial, workload and capacity. The report script auto-detects the schema and preserves the original legacy charts.

### Measured findings from this release

The included `results/admission_benchmark.csv` was generated with three workloads, capacities 4/8/16/32, seeds 42/7/2026, five repetitions per seed/capacity/strategy, a 20-request admission window, and 4,000 requested operations (hot-scan and popularity-shift split requests across phases). The table below reports median hit rates across the 15 trials per workload/capacity/strategy.

| Workload | Capacity | Ordinary LRU | Second-access | Interpretation |
|---|---:|---:|---:|---|
| Zipf | 4 | 37.52% | 47.05% | Admission policy improves hit rate under scarce capacity |
| Zipf | 8 | 54.95% | 63.35% | Admission policy improves hit rate |
| Zipf | 32 | 86.17% | 86.62% | Small improvement when capacity is larger |
| Hot scan, post-scan phase | 8 | 99.60% | 100.00% | Admission policy preserves the hot set in this trace |
| Hot scan, post-scan phase | 16 | 99.60% | 100.00% | Same observed benefit in this trace |
| Popularity shift | 4 | 71.80% | 74.45% | Admission policy improves hit rate in this small-capacity case |
| Popularity shift | 8 | 99.60% | 99.08% | Admission warm-up slightly hurts when the hot set fits |

At Zipf capacity 8, median backing-store lookups decreased from 1,802 to 1,466. At popularity-shift capacity 8, they increased from 16 to 37, illustrating that admission control is workload-dependent. In these local runs, second-access bookkeeping also added elapsed-time overhead; timing is environment-sensitive and should not be interpreted as a universal performance result. See `results/median_elapsed_ms.png` and the CSV for the recorded measurements.

### Complexity and trade-offs

- The existing LRU cache retains average O(1) lookup, promotion and eviction.
- Admission bookkeeping uses a dictionary and FIFO expiry queue; each observation is added and expired once, with amortized O(1) bookkeeping per request. The queue and live observation map retain at most `window_size + 1` live observations.
- The policy can reduce cache pollution from one-time scans but may add CPU and memory overhead, delay useful cache admission, or hurt rapidly shifting workloads.
- The backing store is an in-memory dictionary and the experiment is single-threaded. This is an educational prototype, not a deployed or persistent URL-shortening service.
- The benchmarks use synthetic traces and local timing measurements. No production workload, statistically universal speedup, or novel invention of admission control is claimed.

## Release engineering report

- Preserved the original cache, store, URL shortener, CLI, dataset, demo, project configuration, original tests, and historical benchmark artifacts.
- Added deterministic workload generators, the separate admission policy/resolver, experiment runner and CSV schema, schema-aware report generation, tests, and repository ignore rules.
- The legacy benchmark command was executed successfully and retained its recorded logical results: 49 URLs, 5,000 operations, seed 42, and hit rates 7.48%, 12.76%, 25.58%, and 49.58% for capacities 3, 5, 10, and 20.
- Validation for this release: see the accompanying `ENGINEERING_REPORT.md` for actual test counts, benchmark configuration, generated charts, and remaining limitations.
