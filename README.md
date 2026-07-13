# Search Benchmark

A research/experimental Python framework for comparing heuristic search
algorithms — including two of our own proposed memory-bounded variants —
across two non-trivial problem domains (15-puzzle and Sokoban-lite).

## Install

Requires Python 3.9+. The benchmark uses the standard library plus `psutil`
(for the real-memory ceiling, see **No timeout** below); `pytest` is needed
only to run the test suite.

```bash
pip install -r requirements.txt
```

## Run

```bash
python main.py --domain all --seeds 0 1 2 3 4
```

This runs all five algorithms on both domains. For the n-puzzle domain, one
instance is generated per `(scramble depth, seed)` pair, so every algorithm is
evaluated across all of `--seeds` at each scramble depth. It prints summary
tables grouped by domain/difficulty/algorithm — with the seed-varying metrics
(runtime, memory, nodes expanded/generated) shown as `mean(±std)`, using the
sample standard deviation across seeds — writes detailed per-run results to
`results/benchmark_results.csv`/`.json`, writes the aggregated mean/std
summary to `results/benchmark_summary.csv`/`.json`, and then automatically
analyzes the per-run results into `results/analysis/` (see **Results
analysis** below).

### No timeout

There is intentionally no wall-clock timeout. A shared stopwatch structurally
favors A* — it has no memory-management overhead per node, so it's always
fastest by that measure — which defeats the point of comparing
memory-bounded algorithms. Instead, every run goes until it **solves the
problem** or hits a **real resource ceiling**:

- **Memory**: actual process RSS (sampled periodically via `psutil`, not
  `tracemalloc`-only) crossing `--max-memory-fraction` of this machine's
  total RAM (default `0.8`), or an absolute `--max-memory-mb` override.
- **Call stack**: ILBFS's recursive DFS raising a real Python
  `RecursionError` (recursion limit is raised generously for the duration of
  the search, then restored).
- **`--max-nodes`** (default `5,000,000`) remains only as a generous safety
  valve against a genuine infinite-loop bug — it is not meant to be the
  binding constraint in normal use.

Because of this, **a "hard" run can legitimately take a long time** —
there's nothing artificially cutting it short anymore. On a shared or
resource-limited machine, lower `--max-memory-fraction` (or set an absolute
`--max-memory-mb`) so a hard instance fails fast via the memory ceiling
instead of consuming the whole machine's RAM.

More examples:

```bash
# 15-puzzle only, a handful of scramble depths, three seeds per depth, for a quick look
python main.py --domain puzzle --seeds 0 1 2 --puzzle-size 4 --scramble-depths 10 20 30

# Sokoban only (always runs the 3 handcrafted easy/medium/hard levels);
# cap real memory at 2 GB so a run that can't be solved fails fast
python main.py --domain sokoban --max-memory-mb 2048

# Stress the memory-bounded algorithms with a small RAM budget
python main.py --domain puzzle --sma-memory 500 --dynamic-initial-ram 300 --dynamic-min-ram 100 --two-level-initial-ram 300 --two-level-total-limit 5000

# Keep Two-Level Dynamic SMA*'s SQLite cache files for inspection
python main.py --domain sokoban --keep-disk

# Re-analyze an existing results/benchmark_results.csv without re-running the benchmark
python main.py --analyze-only --output-dir results

# Or run the analysis module directly against any CSV
python -m benchmark.analyze --input results/benchmark_results.csv --output-dir results/analysis
```

### CLI arguments

| Flag | Default | Description |
|---|---|---|
| `--domain` | `all` | `puzzle`, `sokoban`, or `all` |
| `--seeds` | `0` | List of RNG seeds; one n-puzzle instance is generated per (scramble depth, seed) pair, and results are aggregated as mean/std across seeds (Sokoban always runs its 3 fixed handcrafted levels, seed-independent) |
| `--output-dir` | `results` | Where CSV/JSON results (and the disk-cache dir) are written |
| `--puzzle-size` | `4` | N-puzzle board size (`4` = 15-puzzle, `3` = 8-puzzle) |
| `--scramble-depths` | `10 20 30 40 50` | Scramble depths; every depth is run with every seed in `--seeds` |
| `--max-nodes` | `5000000` | Generous infinite-loop safety valve; not the binding constraint in normal use |
| `--max-memory-fraction` | `0.8` | Real memory ceiling as a fraction of this machine's total RAM (checked against actual process RSS) |
| `--max-memory-mb` | none | Override `--max-memory-fraction` with an absolute MB ceiling instead |
| `--sma-memory` | `5000` | Max nodes SMA* may keep resident at once |
| `--dynamic-initial-ram` / `--dynamic-min-ram` / `--dynamic-max-ram` | `2000` / `500` / `10000` | Dynamic SMA*-Collapse's adaptive RAM bound and its floor/ceiling |
| `--two-level-initial-ram` / `--two-level-min-ram` / `--two-level-max-ram` | `2000` / `500` / `10000` | Two-Level Dynamic SMA*'s adaptive RAM bound and its floor/ceiling |
| `--two-level-total-limit` | `50000` | Two-Level Dynamic SMA*'s total (RAM + disk) frontier bound before it must collapse |
| `--epoch-generated-nodes` | `1000` | How many generated nodes make up one adaptation "epoch" for both dynamic algorithms |
| `--keep-disk` | off | Keep Two-Level Dynamic SMA*'s SQLite cache file instead of deleting it after each run |
| `--analyze-only` | off | Skip running the benchmark; just (re-)analyze `<output-dir>/benchmark_results.csv` |

## Algorithms implemented

- **A\*** (`algorithms/astar.py`) — standard graph-search A* using a binary
  heap with priority `(f, -g, counter)` (ties on `f` prefer deeper nodes) and
  a `best_g` dictionary for duplicate detection. Optimal whenever the
  heuristic is admissible (both bundled heuristics are, modulo the Sokoban
  caveat noted below).
- **SMA\*** (`algorithms/sma_star.py`) — simplified memory-bounded A* with a
  *fixed* memory bound (`--sma-memory`). When memory is exceeded it collapses
  the worst frontier leaf and backs up its f-value to the parent. See
  **Limitations** below and the module docstring for the exact
  simplifications.
- **ILBFS** (`algorithms/ilbfs.py`) — "Iterative Lengthening Best-First
  Search", implemented here as iterative cost-bound search in the spirit of
  IDA*: each pass does a depth-first search pruning nodes with `f > bound`,
  then raises `bound` to the smallest f-value that exceeded the previous
  bound. ILBFS has no single standard definition, so this interpretation is
  documented explicitly in the module docstring and isolated behind the
  `ILBFS` class so it can be swapped out later.
- **Dynamic SMA\*-Collapse** (`algorithms/dynamic_sma_collapse.py`) — *our
  first proposed algorithm*. SMA* with a RAM bound (`B_ram`) that adapts
  every `--epoch-generated-nodes` generated nodes based on how often nodes
  had to be collapsed (`collapse_ratio`): heavy collapsing (`> 50%`) doubles
  `B_ram` (up to `--dynamic-max-ram`); light collapsing (`< 10%`) halves it
  (down to `--dynamic-min-ram`) and immediately re-enforces the smaller
  bound. See **What Dynamic SMA*-Collapse does** below.
- **Two-Level Dynamic SMA\*** (`algorithms/two_level_dynamic_sma.py`) — *our
  second proposed algorithm*. Adds a SQLite-backed disk frontier between the
  RAM frontier and true collapse, so demoting a node out of RAM (a "spill")
  no longer means forgetting it. See **What Two-Level Dynamic SMA\* does**
  and **Spill vs. collapse** below.

## Domains implemented

- **15-puzzle** (`domains/n_puzzle.py`) — generalized N-puzzle; the benchmark
  defaults to the 4x4 (15-puzzle) board, but `size=3` gives the classic
  8-puzzle. State is a flat tuple (`0` = blank), actions slide the blank
  up/down/left/right at cost 1, heuristic is the sum of per-tile Manhattan
  distances (no linear-conflict refinement — see **Limitations**).
- **Sokoban-lite** (`domains/sokoban.py`) — state is `(player_position,
  boxes)`; actions move the player, pushing at most one box per step at cost
  1. Heuristic is the sum of each box's distance to its *nearest* goal, plus
  simple corner-deadlock pruning (a non-goal cell boxed in by two
  perpendicular walls is treated as unreachable). Three handcrafted levels
  (`easy`, `medium`, `hard`) are bundled — see **Instance generation**.

Both domains implement the shared `SearchProblem` interface
(`domains/base.py`: `initial_state`, `is_goal`, `successors`, `heuristic`,
`state_key`), and every algorithm depends only on that interface, never on a
concrete domain.

### Instance generation

- **15-puzzle**: solvable instances are generated by random-walking away from
  the goal state for a configured scramble depth (`--scramble-depths`,
  default `10 20 30 40 50`), labeled by depth for reporting. Deeper scrambles
  are *not* guaranteed hard or easy in wall-clock terms — random-walk depth
  doesn't always correlate tightly with true solution length, since moves
  can cancel out — but as a rule of thumb, expect A* to comfortably solve
  shallow/moderate depths quickly; deeper instances are increasingly likely
  to exhaust real memory (especially A* itself, since it keeps every
  generated node) or the `--max-nodes` safety valve, especially for the
  slower memory-bounded algorithms.
- **Sokoban**: three fixed handcrafted levels (parsed from ASCII art in
  `benchmark/instance_generators.py`) of increasing size/box-count: `easy`
  (one box, one push, trivially solved by everyone), `medium` (two boxes, a
  short multi-step solution, comfortably solved by everyone), and `hard`
  (four boxes in a larger room). In local testing, `hard` exhausted real
  memory or the node-count safety valve for *every* algorithm under a tight
  `--max-memory-mb` — exactly the scenario meant to showcase differing memory
  behavior under sustained pressure. **We do not guarantee any algorithm
  solves it** — the benchmark is designed to report
  success/failure/memory-limit/node-limit honestly either way, and that
  contrast (who fails how) is itself the interesting result.

## Metrics collected

Per run (`algorithms/base.py: SearchResult`): `success`, `solution_cost`,
`solution_actions` (and derived `solution_depth`), `runtime_seconds`,
`peak_memory_mb` (real process RSS, sampled via `psutil`, vs. the `tracemalloc`
Python-object peak — whichever is larger), `nodes_expanded`, `nodes_generated`,
`max_frontier_size`, `max_depth_reached`, `reexpansions`, `node_limit_reached`,
`memory_limit_reached`, `stack_exhausted` (ILBFS hit a real `RecursionError`),
`error_message`, plus algorithm-specific extras: `nodes_collapsed`,
`nodes_spilled_to_disk`, `nodes_loaded_from_disk`, `disk_batches_loaded`,
`disk_peak_nodes`, `disk_read_count`, `disk_write_count`,
`disk_io_time_seconds`, `ram_capacity_initial/final/peak/min`,
`number_of_ram_increases/decreases`, `number_of_total_collapses`,
`stale_disk_nodes_skipped`, `duplicate_nodes_skipped`.

Aggregated per (domain, difficulty, algorithm) (`benchmark/metrics.py`):
success rate, node-limit/memory-limit/stack-exhausted rates, average runtime
*on solved instances*, average peak memory, average nodes expanded/generated,
average max frontier size, average solution cost/depth, **optimality gap**
(`(cost - A*_cost) / A*_cost`, averaged where A* also succeeded on the same
instance), and totals for collapsed/spilled/loaded nodes plus average disk
I/O time and peak disk size.

## Results analysis

`benchmark/analyze.py` post-processes `results/benchmark_results.csv` (the
detailed per-run CSV) into a set of higher-level summary/comparison files in
`results/analysis/`. It runs automatically at the end of `python main.py`,
or standalone via `--analyze-only` or `python -m benchmark.analyze --input
... --output-dir ...` (see **Run** above for examples). Output files:

- **`algorithm_summary.csv`** — one row per algorithm, aggregated across all
  domains/instances (success/memory-limit/node-limit/stack-exhausted rates,
  runtime and memory stats, node counts, optimality gap, and totals for
  collapsed/spilled/loaded nodes and RAM-capacity adjustments).
- **`domain_algorithm_summary.csv`** — the same kind of aggregation, but
  broken out per (domain, algorithm).
- **`instance_comparison.csv`** — one row per (instance, algorithm): a
  flattened, analysis-friendly view of the raw results plus the computed
  `optimality_gap_vs_astar`.
- **`winners_by_instance.csv`** — one row per instance, naming the fastest /
  lowest-memory / fewest-expansions / best-solution-cost algorithm (among
  those that succeeded on that instance), whether A*, Dynamic SMA*-Collapse,
  and Two-Level Dynamic SMA* each solved it, and short machine-readable
  `notes` (e.g. `"A* failed; Two-Level Dynamic SMA* solved"`, `"All
  algorithms failed"`, `"Two-Level used disk"`, `"Dynamic collapse had many
  collapses"` — the latter triggers when more than 30% of a run's generated
  nodes were collapsed, see `_HEAVY_COLLAPSE_RATIO` in `analyze.py`).
- **`proposed_algorithms_vs_baselines.csv`** — head-to-head comparisons of
  our two proposed algorithms against A*/SMA*/ILBFS (and against each
  other), computed once across all domains and once per domain, with
  success-rate/runtime/memory/node-expansion deltas and ratios plus a
  rule-based `interpretation` sentence (see `_interpret()` in `analyze.py`
  for the exact decision rules).
- **`human_readable_summary.md`** — a Markdown report: rankings by success
  rate / runtime / memory, per-domain observations, whether A* failed on
  hard Sokoban, whether each proposed algorithm improved on its predecessor,
  a tradeoff discussion (runtime/RAM/disk/collapses/solution quality), and a
  short conclusion section.

All parsing from the CSV is defensive (blank/missing fields never crash the
analysis — see `_to_bool`/`_to_optional_float`/`_to_count` in `analyze.py`),
ratios use safe division (a zero or missing denominator yields an empty
cell, never a `ZeroDivisionError`), and every CSV is written with a header
row even when there are zero matching runs (e.g. an algorithm that wasn't
run, or an empty input file).

## What Dynamic SMA*-Collapse does

It's SMA* (fixed-bound collapse-on-overflow) with one change: the memory
bound `B_ram` is not fixed. Every `epoch_generated_nodes` generated nodes, it
looks at `collapse_ratio = collapsed_this_epoch / generated_this_epoch`:

- `collapse_ratio > 0.50` → memory pressure is high relative to the problem
  → double `B_ram` (capped at `dynamic_max_ram_nodes`).
- `collapse_ratio < 0.10` → there's slack → halve `B_ram` (floored at
  `dynamic_min_ram_nodes`) and immediately collapse down to the new, smaller
  bound if needed.

This lets a single run spend less memory on easy instances and more on hard
ones, instead of committing to one fixed bound up front.

## What Two-Level Dynamic SMA* does

It generalizes Dynamic SMA*-Collapse by inserting a second tier between "in
RAM" and "forgotten forever": a SQLite-backed disk frontier
(`algorithms/_disk_store.py`). There are now two bounds:

- `B_ram` — as before, but exceeding it **spills** the worst RAM nodes to
  disk (full state/g/h/f preserved, fully recoverable) instead of collapsing
  them.
- `B_total` (`--two-level-total-limit`) — the combined RAM+disk frontier
  size. Only exceeding *this* triggers a true SMA*-style collapse of the
  worst disk (or, if disk is empty, RAM) node.

Before every expansion, the algorithm compares the best RAM node against the
best disk node; if disk has something better-or-equal, it loads a batch
(`B_ram / 4` nodes) back into RAM before proceeding — this is the invariant
that the algorithm must never expand a RAM node while a better disk node
exists. `B_ram` itself adapts on *spill/load pressure* rather than collapse
pressure: heavy spilling or any loading pushes it up; very light spilling
with zero loading pushes it down.

### Spill vs. collapse

This distinction is the core idea behind Two-Level Dynamic SMA*:

- **Spill** = move a RAM node to disk. The node is not forgotten — its full
  record is preserved and can come back into RAM later if it becomes
  competitive. Triggered by RAM pressure (`len(RAM) > B_ram`).
- **Collapse** = true SMA* deletion: the node (and the chance to ever revisit
  it) is gone. Triggered only by *total* pressure (`len(RAM) + len(disk) >
  B_total`).

### Why Two-Level Dynamic SMA* is still SMA*-based

Because collapse is deferred as long as possible — a node is only ever
truly forgotten once the *entire* RAM+disk frontier is full, not just RAM —
but when collapse does happen, it always evicts the globally worst
(highest-f) resident node, which is exactly SMA*'s eviction policy. The disk
tier changes *when* SMA*-style forgetting kicks in, not the policy itself.

## Adding a new domain

Implement `SearchProblem` (`domains/base.py`): `initial_state`, `is_goal`,
`successors`, `heuristic`, and optionally override `state_key` (defaults to
the state itself, fine for any hashable state). No algorithm code needs to
change — add instance-generation helpers in `benchmark/instance_generators.py`
and wire them into `main.py`'s `build_instances`.

## Adding a new algorithm

Subclass `SearchAlgorithm` (`algorithms/base.py`) and implement
`search(self, problem, limits) -> SearchResult`, populating whichever
`SearchResult` fields are meaningful. Add it to the `algorithms` list in
`main.py`. No changes are needed to `benchmark/` or `domains/`.

## Known limitations

- **No wall-clock timeout means a hard run can take a genuinely long time.**
  This is by design (see **No timeout** above), but on a shared machine,
  pick a `--max-memory-mb`/`--max-memory-fraction` that fails fast rather
  than letting the process consume all available RAM.
- **The memory ceiling is sampled, not continuous** (`_MEMORY_CHECK_INTERVAL`
  in `algorithms/_run_utils.py`, every 256 checks) to keep the `psutil` call
  cheap — a single very large allocation between samples could transiently
  exceed the ceiling before it's caught.
- **SMA\* is simplified**, not textbook-perfect (applies to `sma_star.py`,
  `dynamic_sma_collapse.py`, and partially `two_level_dynamic_sma.py`): each
  state occupies at most one frontier node (global duplicate suppression via
  `best_g`/`nodes` dict) rather than a pure tree search that can hold the
  same state under different ancestors; there is no reopening when a cheaper
  path to an already-seen state is found later (first-discovered g wins);
  and forgotten nodes back up only a scalar f-value, not subtree shape (fine
  since both domains are deterministic — successors regenerate identically).
- **Two-Level Dynamic SMA\* does not revive a parent after all its children
  are collapsed** (the one piece of classic SMA* backup it skips, to keep
  disk-paging logic tractable — see the module docstring for the full
  rationale). Because of this and the no-reopening rule above, a disk node
  can never become stale, so `stale_disk_nodes_skipped` is always 0 in this
  implementation.
- **`best_g` / duplicate detection and the parent-pointer `node_store` are
  kept fully in RAM** even in Two-Level Dynamic SMA*. Only the heavier
  per-node (state, g, h, f) frontier records are paged to disk; RAM usage
  still grows slowly with total nodes generated, just not with frontier
  size.
- **The SQLite disk layer is experimental**: one database file per run in a
  temp/cache directory, deleted afterward unless `--keep-disk` is passed.
  It is not tuned for throughput (no WAL mode, no connection pooling) —
  expect `disk_io_time_seconds` to be a non-trivial fraction of runtime once
  spilling is frequent.
- **Hard Sokoban instances may not be solved by any algorithm** under a
  tight `--max-memory-mb`/`--max-memory-fraction` — this is intentional (see
  **Instance generation**), and the benchmark reports
  success/memory-limit/node-limit honestly rather than forcing a result.
- **A* is only expected to reliably solve easy/moderate 15-puzzle
  instances** before exhausting real memory (it keeps every generated node
  resident, with no bound); deeper scrambles may run for a long time and/or
  exhaust `--max-memory-mb` or the `--max-nodes` safety valve (see
  **Instance generation**).
- The Sokoban heuristic (sum of each box's distance to its nearest goal) is
  a common practical choice but is not strictly admissible in general
  (two boxes can be assigned the same "nearest" goal, undercounting the true
  cost) — it can occasionally cause A* to return a slightly suboptimal
  solution rather than guaranteeing optimality.

## Tests

```bash
python -m pytest tests/ -q
```

Covers: 15-puzzle successor legality and zero-heuristic-at-goal, Sokoban
successor generation (moves and pushes) and A* solving a tiny instance, A*
solving an easy 15-puzzle instance, Dynamic SMA*-Collapse running without
crashing across several instances, Two-Level Dynamic SMA* running without
crashing and correctly creating/cleaning up (or keeping, when asked) its
SQLite disk cache, and the benchmark runner producing CSV/JSON output for
all five algorithms. `tests/test_analyze.py` additionally covers the
results-analysis module against a small hand-built fake CSV: safe parsing of
booleans/numbers/blanks, optimality-gap computation, every summary/comparison
CSV (including the header-only/empty-input and zero-denominator-ratio edge
cases), the winners/notes logic, and an end-to-end `analyze_results()` run
that checks all six output files are produced.

