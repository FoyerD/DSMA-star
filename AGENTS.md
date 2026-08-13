# DSMA-star — agent instructions

## Project overview

A research framework for comparing **memory-bounded heuristic search
algorithms** on the **15-puzzle**. The original repo built and benchmarked
SMA* variants (SMA*, Dynamic SMA*-Collapse, Two-Level Dynamic SMA*) and even
a Sokoban domain. All of that was **removed**; the project now contains exactly
five clean, well-understood algorithms:

- **A\*** — standard graph search, full frontier in RAM.
- **ILBFS** — Iterative Linear Best-First Search, iterative RBFS (Collapse/Restore macros), O(b·d) memory.
- **RBFS** — Recursive Best-First Search, recursion-stack RBFS, O(b·d) memory, ~3x faster than ILBFS.
- **mp-bfs** — Multi-Path Best-First: best-first procs multiplexed by a pluggable scheduler (suboptimal solutions possible).
- **mp-rbfs** — Multi-Path RBFS: the same proc architecture, but each proc runs a real iterative RBFS. See `docs/mp_bfs.md` and `docs/mp_rbfs.md`.

## Quick start

```bash
conda activate sai
pip install -r requirements.txt        # psutil, pytest
python main.py --domain puzzle --seeds 0
python -m pytest tests/ -q
```

> Environment notes: `conda run` buffers stdout — use `python -u` and the
> direct python path (`/home/foyer/miniconda3/envs/sai/bin/python`) when you
> need live output. All commands below assume `conda activate sai`.

## Project structure

```
domains/           # SearchProblem subclasses (n_puzzle)
algorithms/        # SearchAlgorithm subclasses (astar, ilbfs, rbfs, mp_bfs, mp_rbfs)
                   #   + shared base/_run_utils + mp_common + mp_schedulers
benchmark/         # Runner, instance generators, metrics, results analysis
scripts/           # One-time precomputation (generate_depths21_40.py, precompute/fill astar nodes) + run_ilbfs_verbose.py
docs/              # Design docs (ilbfs.md, mp_bfs.md, mp_rbfs.md)
instances/         # korfs100.csv, puzzle_amit_depths21_40.csv, puzzle_depths21_40.csv
main.py            # CLI entrypoint
```

**NOTE:** `results/` and `opencode.json` are in `.gitignore`; `AGENTS.md` and
`docs/` are tracked in git.

> **`README.md` used to be stale** (it described the removed SMA*/DSMA*/Two-Level
> algorithms, the Sokoban domain, and ILBFS-as-cost-bound-search). It was
> rewritten to match the current five algorithms — but if it drifts again,
> trust this file and `docs/` over the README.

## CLI flags

| Flag | Default | Note |
|------|---------|------|
| `--domain` | `puzzle` | Only `puzzle` remains (Sokoban removed) |
| `--seeds` | 0 | RNG seeds; one puzzle instance per (depth, seed) pair |
| `--scramble-depths` | 10 20 30 40 50 | For `scramble` source |
| `--puzzle-size` | 4 | 4=15-puzzle, 3=8-puzzle |
| `--puzzle-instance-source` | korf (if CSV exists) else scramble | `korf`, `scramble`, or `amit` |
| `--korf-csv` | `instances/korfs100.csv` | Korf 100 instances |
| `--amit-csv` | `instances/puzzle_amit_depths21_40.csv` | Amit instances (true depths 21–40) |
| `--optimal-depths` | 21..40 | Korf/amit instances by true optimal depth |
| `--algorithms` | astar ilbfs rbfs mp-bfs-best_first mp-rbfs-best_first | Algorithm names; mp variants are `mp-bfs-<sched>` / `mp-rbfs-<sched>` |
| `--num-procs` | 100 | mp-bfs / mp-rbfs: Phase-1 frontier size (number of procs) |
| `--proportional-weight-power` | 1.0 | mp-* proportional scheduler weight `1 / (f+eps)**power` |
| `--max-memory-fraction` | 0.8 | Of total RAM |
| `--max-memory-mb` | None | Absolute MB ceiling override |
| `--max-nodes` | 5000000 | Safety valve against infinite loops |
| `--analyze-only` | off | Re-analyze existing results CSV |

```bash
# Korf instances by optimal depth
python main.py --domain puzzle --puzzle-instance-source korf --optimal-depths 40 45 50

# Amit instances (true optimal depths 21-40, A*-verified)
python main.py --domain puzzle --puzzle-instance-source amit

# Re-run analysis on existing results
python main.py --analyze-only
```

## The five algorithms

### A\* (`algorithms/astar.py`)
Classic graph-search A* with a binary heap: `(f, -g, counter, g, state)` — ties
on `f` prefer deeper nodes. `best_g` dict for duplicate detection, `closed`
set. Optimal when `h` is admissible (Manhattan distance is). Keeps every
generated node in RAM — fails on hard instances by exhausting memory.

### ILBFS (`algorithms/ilbfs.py`)
Non-recursive RBFS: one heap + one `nodes` dict (TREE), driving the
Collapse/Restore macros from the pseudocode in `docs/ilbfs.md`. See §"Key
design decisions" and `docs/ilbfs.md` §8 for the two implementation details
that matter (tie-breaking, heap purge).

### RBFS (`algorithms/rbfs.py`)
Recursive RBFS per Korf 1993. `sys.setrecursionlimit(10_000)` during the
search (restored in `finally`). Expands the same nodes as ILBFS **but not
necessarily in the same order** (see Issue #5) and runs ~3x faster because
there is no heap management. Memory is O(d) stack frames + O(b·d) live tree.

### mp-bfs (`algorithms/mp_bfs.py`)
Multi-Path Best-First Search. Phase 1 expands best-first from the root until
the open list has at least `--num-procs` nodes (always completing every
expanded node's full sibling set); each Phase-1 frontier node becomes a
**proc** — an independent best-first search of its own subtree. Procs never
spawn and never backtrack; an exhausted proc terminates. A single-threaded
scheduler (`best_first`, `round_robin`, or `proportional`) picks which proc
runs one expansion at a time. The first goal found terminates the search —
**solutions can be suboptimal** by design. Shared `best_g` dedup table across
all procs. See `docs/mp_bfs.md`.

### mp-rbfs (`algorithms/mp_rbfs.py`)
Same Phase-1/proc/scheduler architecture as mp-bfs, but each proc runs a real
**iterative RBFS** (Collapse/Restore) with its own local tree and F back-up.
Each proc also dedups against the shared `best_g`, and collapsed subtrees are
regenerated by RBFS re-expansion: the dedup rule only rejects *strictly
better* known paths, so a state the proc itself collapsed is re-accepted when
re-generated at the same `g`. Backed-up `F` values distinguish "genuinely
re-expanded" nodes (counted in `reexpansions`) from mere stale heap skips.
`total_collapses` / `max_proc_tree_size` are reported per run — the O(b·d)
memory bound shows up as a tiny live tree even while generating millions of
nodes. See `docs/mp_rbfs.md`.

## Datasets — scramble depth is NOT optimal depth

This is the single most important measurement lesson in this repo:

- **Scramble depth** = number of random moves used to shuffle the goal state.
  Moves cancel out, so scramble depth is *not* the true optimal solution
  length, and instances scrambled to the same depth can have wildly different
  difficulty.
- **Optimal depth** = the true minimum solution length. Only trustworthy when
  verified (by A*, or known from Korf's historical data).

Three instance sources:

| Source | File | Instances | Optimal depth known? |
|--------|------|-----------|----------------------|
| `korf` | `instances/korfs100.csv` | 100 fixed historical | Yes (Korf's exhaustive search), plus IDA*/A* node counts |
| `amit` | `instances/puzzle_amit_depths21_40.csv` | 20 (depths 21–40) | Yes (A*-verified by `scripts/generate_depths21_40.py`) |
| `scramble` | generated at runtime | 1 per (depth, seed) | No — scramble depth only |

`korfs100.csv` columns: `id`, `state`, `estimate`, `optimal_depth`,
`total_nodes_ida`, `total_nodes_a_approx`, `total_nodes_a`,
`total_nodes_a_predicted`.

- `total_nodes_ida`: IDA* search tree size (Korf's original data)
- `total_nodes_a`: actual A* nodes expanded (pre-computed, 50M limit)
- `total_nodes_a_predicted`: True for 13 instances where A* exceeded the limit
  (filled via log-log regression `a = 3.42 * ida^0.77`, R²=0.89, 37% median error)
- `total_nodes_a_approx`: `int(sqrt(total_nodes_ida))` — legacy approximation

## Key design decisions

- **No wall-clock timeout.** A stopwatch favors A* (no memory-management
  overhead). Runs only stop on: solution found, RSS > `--max-memory-mb`, or
  `--max-nodes` safety valve (5M default).
- **Memory ceiling enforced via `psutil`** sampled every 256 limit-checks
  (`algorithms/_run_utils.py:_MEMORY_CHECK_INTERVAL`), not continuously — a
  single large alloc between samples could briefly exceed it. Peak memory
  reported is `max(tracemalloc_peak, sampled_rss)`.
- **ILBFS heap tie-breaking = `(F + collapse_count, -depth, state_key)`**
  (see `docs/ilbfs.md` §8 and Issue #6 below). This was the hardest bug in the
  project: a fixed tie-breaker either oscillates on depth-24 or on depth-28.
  The fix combines depth-first expansion (`-depth`) with a per-node
  oscillation penalty (`collapse_count` incremented each collapse).
- **After each collapse loop, rebuild the heap from the live `nodes` dict**
  to purge stale entries from OPEN (pseudocode line 79: "Delete all children
  of oldbest from OPEN and TREE"). Before this, the heap grew monotonically to
  millions of entries.
- **A\* heap rebuild** was tried and reverted — A* doesn't benefit because
  stale entries are O(1) skipped.
- **Lazy successor generation for A\*** was tried and reverted — for 15-puzzle
  deep optimal search the extra heap ops per node outweigh any benefit.

## Runner output format

```
→ STATUS cost=N optimal=M (T.Xs, NNN MB, N expanded, N frontier)
```

Status is uppercase: `SOLVED`, `MEMORY LIMIT`, `NODE LIMIT`, `FAILED`.
`Stack exhausted` also exists (a real Python `RecursionError`).

## Results pipeline and analysis outputs

`main.py` runs every (algorithm, instance) pair, then writes into
`--output-dir` (default `results/`):

- `benchmark_results.csv` — raw, **lossless**. One column per `SearchResult`
  dataclass field (all mp-* fields included) + `solution_actions`; built
  straight from `dataclasses.fields(SearchResult)` in `benchmark/results.py`.
  This is the single source of truth; the analysis layer re-parses it.
- `benchmark_results.json` — same data as JSON.
- `benchmark_summary.csv/json` — per (domain, difficulty, algorithm) mean/std
  aggregates (`benchmark/metrics.py:AggregateMetrics`): runtime, peak memory,
  expanded/generated, max frontier, **reexpansions, total_collapses,
  max_proc_tree_size, proc_switches**, `avg/std_optimality_gap_vs_known_optimal`.
- `analysis/` — curated reports from `benchmark/analyze.py`:

  | File | Contents |
  |---|---|
  | `algorithm_summary.csv` | per-algorithm aggregates (success rate, runtime, mem, reexp/collapse ratios, optimality gaps) |
  | `domain_algorithm_summary.csv` | same, per (domain, algorithm) |
  | `by_difficulty_summary.csv` | per (difficulty/depth, algorithm) — where each algorithm's success collapses and how memory behaves there |
  | `winners_by_instance.csv` | fastest / lowest-memory / fewest-expansions / best-cost algorithm per instance |
  | `proposed_algorithms_vs_baselines.csv` | curated comparison pairs with ratios and a human-readable `interpretation` |
  | `summary.json` | the curated tables bundled into one JSON (for a paper pipeline) |
  | `human_readable_summary.md` | markdown report: rankings + per-domain and per-difficulty sections |

- Comparison pairs (`analyze.py:_COMPARISON_PAIRS`): `mp-rbfs-best_first` vs
  `{ilbfs, rbfs, mp-bfs-best_first}`, and `mp-bfs-best_first` vs `astar`.
  `PROPOSED_ALGORITHMS = (mp-bfs-best_first, mp-rbfs-best_first)`.

**Design rule:** the raw CSV stays complete; "useless" columns are dropped only
in the analysis layer, never in `benchmark/results.py`. `instance_comparison.csv`
was removed from orchestration (it was a subset of the raw CSV) — the writer
function remains for compatibility. Re-run analysis on existing data with
`python main.py --analyze-only`.

## Assignment submission runs (on another machine)

The repo's default machine is too small for the full benchmark, so the two runs
below are scripted in `run.sh` at the repo root to be executed elsewhere
(`conda activate sai` first). They are kept in separate `--output-dir`s so the
raw CSVs don't overwrite each other.

```bash
# 1. amit suite — all 20 instances, true optimal depths 21–40 (~30–60 min)
python -u main.py --domain puzzle --puzzle-instance-source amit \
  --algorithms astar ilbfs rbfs mp-bfs-best_first mp-rbfs-best_first \
  --output-dir results_amit

# 2. korf sample — depths 41, 47, 55 (ids 55/30/2; all have MEASURED A*
#    reference counts, not regression-predicted) (~10–30 min)
python -u main.py --domain puzzle --puzzle-instance-source korf \
  --optimal-depths 41 47 55 \
  --algorithms astar ilbfs rbfs mp-bfs-best_first mp-rbfs-best_first \
  --output-dir results_korf
```

Expected behavior on the hard end (amit d≥29, korf d55): A* hits the memory
ceiling, RBFS-family algorithms hit the node limit — that is the data point,
not a bug. Memory ceiling defaults to 80% of RAM (`--max-memory-fraction 0.8`);
lower it if the box is shared.

## Testing

```bash
conda activate sai
python -m pytest tests/ -q
```

109 tests, all passing.

## Adding algorithms

Subclass `SearchAlgorithm` (`algorithms/base.py`), implement
`search(problem, limits) -> SearchResult`. Add to the `algorithms` list in
`main.py`. No other files need changes.

## Adding domains

Implement `SearchProblem` (`domains/base.py`): `initial_state`, `is_goal`,
`successors`, `heuristic`. Optionally override `state_key`. Add instance
generation to `benchmark/instance_generators.py` and wire into
`main.py:build_instances()`.

## Known constraints

- 15-puzzle at depths 40+ is extremely hard — A* may exhaust memory;
  ILBFS/RBFS re-expand exponentially and will time out.
- ILBFS re-expands nodes far more than A* (collapsed subtrees are regenerated
  from scratch). At depth 40+ this is 20–60x A*'s node count.

---

# Complete project history — everything we did, every issue found and solved

Written so a fresh reader (or another LLM) can reconstruct the whole journey.
Chronological.

## Timeline

| Date | Commit | What happened |
|------|--------|---------------|
| early | (many) | Built SMA*, Dynamic SMA*-Collapse, Two-Level Dynamic SMA*, ILBFS-as-cost-bound-search, Sokoban domain. **All removed later.** |
| 07-26 | `3561930` | **Removed SMA*/DSMA*/TwoLevel/Sokoban**; re-implemented ILBFS from scratch per Grabovski & Yasur (2024) pseudocode (iterative Collapse/Restore). |
| 07-26 | `1888dce` | Added recursive **RBFS**, measured ~3x faster than ILBFS. |
| 07-26 | `00dfff7` | Added `scripts/generate_depths21_40.py` + `instances/puzzle_depths21_40.csv` (scramble-based, 200 rows). |
| 07-26 | `a3c9693` | Added `docs/` to `.gitignore` (docs never tracked). |
| 07-27 | `f5fc9c4` | Moved `korfs100.csv` → `instances/`; changed default instance source. |
| 07-27 | `da2e786` | Added `instances/puzzle_amit_depths21_40.csv` (the **amit** dataset). |
| 07-27 | `4c735d6` | Changed default `--optimal-depths` to `21..40`. |
| 07-27 | `a679483` | Added `scripts/run_ilbfs_verbose.py` (diagnostics) + first ILBFS fix. |
| 07-27 | `1f0c1b2` | **Final ILBFS fix**: `collapse_count` tie-breaking (Issue #6). |
| 08-13 | (uncommitted) | Fixed Issue #2 (korf test now uses `DEFAULT_KORF_CSV`); **109 tests pass**. |
| 08-13 | (uncommitted) | Analysis overhaul: analyze.py/metrics.py now handle all mp-* fields, added `by_difficulty_summary.csv` + `summary.json`, filled `_COMPARISON_PAIRS`, dropped `instance_comparison.csv` from orchestration. |
| 08-13 | (uncommitted) | Added `run.sh` with the two submission benchmark runs (amit 21–40, korf 41/47/55). |

## Issue log

### Issue #1 — "Amit's 20" was never a real dataset
The user referenced "Amit's 20" instances as if they existed. They didn't. What
was actually wanted: a small set of 15-puzzle instances whose **true optimal
depths** are verified by A* (depths 21–40), so ILBFS/RBFS could be debugged on
instances with known difficulty rather than scramble-depth guesses.

**Solution:** `scripts/generate_depths21_40.py`. For each target depth `d`, it
scrambles from the goal (escalating scramble depth up to 80 if needed), runs
A* to get the true optimal depth, and keeps the first instance that solves to
exactly `d`. Output: `instances/puzzle_amit_depths21_40.csv` — 20 instances,
one per depth 21–40, columns `id,state,optimal_depth,total_nodes_a`. Wired into
the CLI as `--puzzle-instance-source amit`.

### Issue #2 — korfs100.csv location mismatch (test failure)
`tests/test_instance_generators.py` hard-coded the CSV at the repo root, but
it was moved to `instances/`. The test now fails with
`FileNotFoundError: .../korfs100.csv`. **Fixed on 08-13**: the test now uses
`DEFAULT_KORF_CSV` (`instances/korfs100.csv`). No longer a failure.

### Issue #3 — `benchmark/results.py` AttributeError
Referenced phantom fields that no longer existed after the SMA* removal.
**Solution:** removed the stale field references.

### Issue #4 — RBFS bugs fixed during the ILBFS work
Two fixes in `algorithms/rbfs.py`:
1. **Pathmax propagation made conditional** to match the pseudocode
   (`max(F(parent), f(child))` only when `F(parent) > f(parent)`).
2. **Added a transposition table** (the `nodes` dict) so duplicate states
   reached via different paths aren't expanded twice.

### Issue #5 — "RBFS and ILBFS expand the same nodes in the same order" is FALSE
The claim in the old AGENTS.md was wrong. RBFS uses a **local stable sort by F
per node**; ILBFS uses a **global heap**. Ties break differently, so the two
algorithms can visit nodes in a different order (RBFS proved robust on
instances where ILBFS oscillated). Any statement that they're "identical" is
an oversimplification — they're *functionally equivalent* (same search
semantics, both optimal with admissible h), not literally same-order.

### Issue #6 — THE BIG ONE: ILBFS heap tie-breaking oscillation
**Symptom:** ILBFS on 15-puzzle instances would loop forever re-expanding the
same nodes (hitting the 5M node safety valve), or in the worst case oscillate
infinitely.

**Root cause:** after a collapse backs up F values, a sibling node and the
current branch's children often share the same F. The heap pops whichever wins
the tie. If the winner is a sibling (not a child of `oldbest`), popping it
triggers a collapse that deletes the just-expanded children; the collapsed
node is re-pushed with the same F and wins again → infinite oscillation.

**What we tried (in order):**

| Tie-breaker | depth-24 | depth-28 |
|---|---|---|
| `(F, -order, key)` (original, newest wins) | oscillates | — |
| `(F, -depth, key)` (deeper wins) | **works** (2964 exp, 0.55s) | oscillates |
| `(F, depth, key)` (shallower wins) | oscillates | **works** |
| `(F, key)` (deterministic, no depth) | stuck | — |

Pure `-depth` fixes 24 but not 28; pure `depth` fixes 28 but not 24. No static
tie-breaker worked on both.

**Final fix:** combine them — `(F + collapse_count, -depth, state_key)`.
- `-depth`: deeper nodes win ties → search deepens along the current branch
  (efficient, no collapse triggered).
- `collapse_count`: incremented on `_Node` every time its children are deleted
  by collapse; degrades the node's effective priority by 1 per collapse. After
  enough collapses the node loses the tie to siblings, forcing a branch switch
  — breaking the infinite re-expansion loop.

**Result:** depth-24 = 3390 expansions / 0.36s (was 2964 with pure `-depth`,
which fails on 28); depth-28 = 182K expansions / 14s (previously infinite).
The ~14% overhead on 24 is the price of making 28 tractable. Full write-up:
`docs/ilbfs.md` §8.

**Follow-up trap (measured, don't fall in):** moving `-depth` *before* `F`
in the heap tuple — `(-depth, F+cc, key)` — looks much faster (302 vs 3390
expansions on depth-24; 18K vs 182K on depth-28) but makes depth the
**primary** key, turning best-first search into greedy DFS. It returns
garbage: cost **298** where the optimal is 24, and 18030 where it's 28.
`F` (or `F + collapse_count`) MUST remain the primary key; `-depth` is
only ever a tie-breaker among equal F values, which preserves optimality.

### Issue #7 — collapse loop condition
The collapse loop used a `not _is_ancestor()` helper. Replaced with the direct
pseudocode condition `oldbest != best.parent` — correct and simpler
(`algorithms/ilbfs.py:124`).

### Issue #8 — heap grew to millions of entries (memory)
Before the fix, collapsed children's heap entries were never removed — only
skipped lazily at pop time. On a depth-41 Korf instance this produced 5M heap
entries ≈ 3.3 GB vs A*'s 134K entries at 276 MB. **Fix:** after each collapse
loop, rebuild the heap from the live `nodes` dict (`O(b·d)` per collapse).
Documented in `docs/ilbfs.md` §8 "Heap Purge on Collapse".

### Issue #9 — `conda run` swallows stdout
Diagnostics printed nothing. Use `python -u` and the direct python binary
(`/home/foyer/miniconda3/envs/sai/bin/python`) instead of `conda run`.

## Developer workflow tips

- To run the full submission benchmark on a bigger machine: `bash run.sh`
  (amit 21–40 + korf 41/47/55 into `results_amit/` and `results_korf/`).
- To debug ILBFS on a specific depth: `python scripts/run_ilbfs_verbose.py 28`
  (prints expansions, collapse events, paths, F values; takes depth as argv).
- To generate one instance per depth 21–40 with A*-verified optimal depth:
  `python scripts/generate_depths21_40.py`.
- When changing ILBFS/RBFS behavior, first reproduce on amit depths 24 and 28
  — these two depths are the ones that historically exposed oscillation.

---

# Multi-path algorithms: history and design notes

## Timeline

| Date | What happened |
|------|---------------|
| earlier | Agreed design: Phase-1 fork → procs → pluggable single-threaded scheduler, one expansion per quantum, shared transposition table, first goal terminates, suboptimal solutions acceptable by design. |
| 08-13 | Implemented **mp-bfs** (`algorithms/mp_bfs.py`) and **mp-rbfs** (`algorithms/mp_rbfs.py`) sharing `algorithms/mp_common.py` (Phase 1, full `_Node`) and `algorithms/mp_schedulers.py`. mp-rbfs was first (single module with schedulers), then split into mp-bfs + shared common code. |

## Design recap

1. **Phase 1 (fork):** expand best-first from the root until the open list has
   at least `--num-procs` nodes, always completing every expanded node's full
   sibling set ("don't miss anything").
2. **Phase 2 (procs):** each Phase-1 frontier node becomes a **proc**. mp-bfs
   procs run plain best-first; mp-rbfs procs run a real iterative RBFS
   (Collapse/Restore). Procs never spawn and never backtrack; an exhausted
   proc terminates.
3. **Scheduler (pluggable, single-threaded):** picks which proc runs next.
   Each proc exposes `(priority, f)` where `f` is the static `g+h` of the node
   it will expand next and `priority` is a policy score derived from `f` by
   the scheduler (`best_first` / `round_robin` / `proportional`).
4. **Quantum:** one node expansion per scheduling decision.
5. **Shared `best_g` dedup table** across all procs; first goal found
   terminates; **suboptimal solutions are acceptable** by design.

## Measured behavior (amit instances, best_first, num-procs=100)

mp-rbfs is a real RBFS: it re-expands (collapses) and its expansion counts are
an order of magnitude above mp-bfs/ILBFS on harder depths, but memory stays
tiny. Example (`total_collapses` / `max_proc_tree_size` are mp-rbfs-only):

- depth 24: mp-rbfs ≈ 35K expansions / ~2s vs ILBFS 3.4K / 0.2s; solved.
- depth 28: mp-rbfs ≈ 135K expansions / ~8s vs ILBFS ≈ 182K / 14s; solved.
- depth 29: mp-rbfs ≈ 274K expansions then hits the node safety valve
  (capped at 500K in this run); max live tree stayed at 40 nodes (the O(b·d)
  bound) while generating ~500K.

So on the easy half of the amit range mp-rbfs is competitive; from depth ~29
onward it re-expands exponentially (documented ILBFS/RBFS family behavior) and
typically times out or hits the node limit, exactly like ILBFS/RBFS.
