# Search Benchmark

A small, extensible Python project for comparing search algorithms across
multiple problem domains.

## Install

Requires Python 3.9+. The benchmark itself uses only the standard library;
`pytest` is needed only to run the test suite.

```bash
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

This runs all four algorithms on both domains, prints summary tables, and
writes detailed per-run results to `results/benchmark_results.csv` and
`results/benchmark_results.json`.

### CLI arguments

| Flag | Default | Description |
|---|---|---|
| `--domain` | `all` | `grid`, `puzzle`, or `all` |
| `--instances` | `5` | Number of instances generated per domain |
| `--timeout` | `10.0` | Per-run timeout in seconds |
| `--grid-size` | `10 10` | Grid `WIDTH HEIGHT` |
| `--obstacle-prob` | `0.2` | Probability a grid cell is an obstacle |
| `--scramble-depths` | `5 10 15 20` | Scramble depths cycled through for puzzle instances |
| `--seed` | `42` | RNG seed for reproducible instance generation |
| `--output-dir` | `results` | Where the CSV/JSON results are written |
| `--max-nodes` | `200000` | Node-generation budget per run |
| `--max-memory-mb` | `512.0` | Peak-memory budget per run (tracked via `tracemalloc`) |
| `--sma-memory-limit-nodes` | `2000` | Max nodes SMA* may keep in memory at once |

Example:

```bash
python main.py --domain puzzle --instances 10 --scramble-depths 10 20 30 --timeout 5
```

## Algorithms implemented

- **A\*** (`algorithms/astar.py`) — classic `heapq`-based A* with a best-`g`
  dictionary; optimal whenever the heuristic is admissible (both bundled
  heuristics are).
- **SMA\*** (`algorithms/sma_star.py`) — simplified memory-bounded A*. Keeps a
  bounded tree of nodes in memory; when the bound is exceeded it prunes the
  worst leaf and backs up its f-value to the parent. See the limitations
  section below and the module docstring for the exact simplifications made.
- **ILBFS** (`algorithms/ilbfs.py`) — "Iterative Lengthening Best-First
  Search", implemented here as iterative cost-bound search in the spirit of
  IDA*: each pass does a depth-first search pruning nodes with `f > bound`,
  then raises `bound` to the smallest f-value that exceeded the previous
  bound. ILBFS has no single standard definition, so this interpretation is
  documented explicitly in the module docstring, and the implementation is
  isolated behind the `ILBFS` class so it can be swapped for a different
  interpretation later without touching the rest of the codebase.
- **CustomAlgorithm** (`algorithms/custom_algorithm.py`) — placeholder with
  the same `SearchAlgorithm` interface as the others. Currently delegates to
  A*. There is a `TODO` marking where our proposed algorithm should be
  implemented.

## Domains implemented

- **Grid pathfinding** (`domains/grid.py`) — 2D grid with obstacles, 4-connected
  moves (up/down/left/right), cost 1 per move, Manhattan-distance heuristic.
- **Sliding puzzle / 8-puzzle** (`domains/sliding_puzzle.py`) — 3x3 board as a
  flat 9-tuple, blank-tile moves, cost 1 per move, sum-of-Manhattan-distances
  heuristic.

Both domains implement the shared `SearchProblem` interface
(`domains/base.py`), and all algorithms depend only on that interface — never
on a concrete domain. Adding a new domain means implementing
`initial_state`, `is_goal`, `successors`, and `heuristic`; no algorithm code
needs to change.

## Metrics collected

Per run (`algorithms/base.py: SearchResult`):
`success`, `solution_cost`, `solution_actions` (and derived `solution_depth`),
`runtime_seconds`, `peak_memory_mb` (via `tracemalloc`), `nodes_expanded`,
`nodes_generated`, `max_frontier_size`, `max_depth_reached`, `reexpansions`,
`timeout`, `memory_limit_reached`, `error_message`.

Aggregated per (domain, algorithm) (`benchmark/metrics.py`):
success rate, timeout rate, memory-limit-failure rate, average runtime,
average peak memory, average nodes expanded/generated, average max frontier
size, average solution cost, and **optimality gap** — `(cost - A*_cost) /
A*_cost` averaged over instances where A* succeeded, computed against A*'s
solution cost on the same instance.

## Adding our new algorithm later

1. Implement a class in `algorithms/custom_algorithm.py` (or a new file)
   that subclasses `SearchAlgorithm` and implements
   `search(self, problem: SearchProblem, limits: SearchLimits) -> SearchResult`.
2. Populate every field of `SearchResult` that's meaningful for the
   algorithm — the benchmark runner and metrics code make no assumptions
   beyond that interface.
3. Swap it into the `algorithms` list in `main.py` (it's already wired in as
   `CustomAlgorithm`, just replace the body of `CustomAlgorithm.search`, or
   point `main.py` at a new class).
4. No changes are needed to `benchmark/`, `domains/`, or the CLI.

## Limitations

### SMA*

This is a teaching-grade simplification, not a textbook-perfect SMA*:

- Each state occupies at most one node (keyed by `state_hash`) rather than a
  pure tree search that can hold multiple nodes for the same state under
  different ancestors. If a state is rediscovered while already present in
  memory, the new edge is simply dropped rather than reparented onto a
  cheaper path.
- When a node's children are pruned to free memory, only a single scalar
  "forgotten f-value" is backed up to the parent (no subtree shape is
  preserved). Re-expansion regenerates successors from scratch via
  `problem.successors`, which is correct for deterministic domains (both
  bundled domains are) but would be unsound for non-deterministic ones.
- Node deletion picks the worst (highest f) leaf, breaking ties by most
  recently generated; the root is never deleted. If memory is exhausted down
  to a single node, the run is reported as `memory_limit_reached` instead of
  looping forever.

### ILBFS

"ILBFS" has no single standard definition. This implementation treats it as
**iterative lengthening / cost-bound search**, structurally identical to
IDA*: repeated bounded depth-first passes over the f-cost, with the bound
raised each pass to the smallest f-value that exceeded the previous bound.
The "BFS" in the name reflects exploring in increasing f-cost layers, not a
literal FIFO breadth-first queue. The implementation is isolated in
`algorithms/ilbfs.py` behind the `ILBFS` class specifically so this
interpretation can be swapped out later without touching the rest of the
codebase.

## Tests

```bash
python -m pytest tests/ -q
```

Covers: grid successor generation, sliding-puzzle move generation, A* solving
a tiny grid and an easy 8-puzzle, and the benchmark runner producing results
without crashing.
