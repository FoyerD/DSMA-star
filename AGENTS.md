# DSMA-star — agent instructions

## Project overview

A research framework for comparing **memory-bounded heuristic search
algorithms** on the **15-puzzle**. The original repo built and benchmarked
SMA* variants (SMA*, Dynamic SMA*-Collapse, Two-Level Dynamic SMA*) and even
a Sokoban domain. All of that was **removed**; the project now contains exactly
three clean, well-understood algorithms:

- **A\*** — standard graph search, full frontier in RAM.
- **ILBFS** — Iterative Linear Best-First Search, iterative RBFS (Collapse/Restore macros), O(b·d) memory.
- **RBFS** — Recursive Best-First Search, recursion-stack RBFS, O(b·d) memory, ~3x faster than ILBFS.

The next step (design written, not implemented) is **mp-rbfs** — Multi-Path
RBFS: many independent RBFS "procs" (one per initial frontier path) multiplexed
by a pluggable scheduler. See `docs/mp_rbfs.md`.

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
algorithms/        # SearchAlgorithm subclasses (astar, ilbfs, rbfs) + shared base/_run_utils
benchmark/         # Runner, instance generators, metrics, results analysis
scripts/           # One-time precomputation (generate_depths21_40.py, precompute/fill astar nodes) + run_ilbfs_verbose.py
docs/              # Design docs (ilbfs.md, mp_rbfs.md, multi_process_search.md)  [GITIGNORED]
instances/         # korfs100.csv, puzzle_amit_depths21_40.csv, puzzle_depths21_40.csv
main.py            # CLI entrypoint
```

**IMPORTANT:** `AGENTS.md`, `docs/`, `results/`, `opencode.json` are all in
`.gitignore`. They exist only on disk and will never appear in `git status`.

> **`README.md` is stale.** It still describes the removed SMA*/DSMA*/Two-Level
> algorithms, the Sokoban domain, and ILBFS-as-cost-bound-search. Everything it
> says about those is wrong for the current codebase. Trust this file and
> `docs/` over the README; the README needs a rewrite that hasn't happened yet.

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

## The three algorithms

### A\* (`algorithms/astar.py`)
Classic graph-search A* with a binary heap: `(f, -g, counter, g, state)` — ties
on `f` prefer deeper nodes. `best_g` dict for duplicate detection, `closed`
set. Optimal when `h` is admissible (Manhattan distance is). Keeps every
generated node in RAM — fails on hard instances by exhausting memory.

### ILBFS (`algorithms/ilbfs.py`)
Non-recursive RBFS: one heap (OPEN) + one `nodes` dict (TREE), driving the
Collapse/Restore macros from the pseudocode in `docs/ilbfs.md`. See §"Key
design decisions" and `docs/ilbfs.md` §8 for the two implementation details
that matter (tie-breaking, heap purge).

### RBFS (`algorithms/rbfs.py`)
Recursive RBFS per Korf 1993. `sys.setrecursionlimit(10_000)` during the
search (restored in `finally`). Expands the same nodes as ILBFS **but not
necessarily in the same order** (see Issue #5) and runs ~3x faster because
there is no heap management. Memory is O(d) stack frames + O(b·d) live tree.

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

## Testing

```bash
conda activate sai
python -m pytest tests/ -q
```

48 tests, one pre-existing failure:
`test_bundled_korfs100_csv_loads_skipping_known_bad_rows` expects the CSV at
the repo root, but it now lives in `instances/`. **47 pass / 1 fail** is the
known-good state — don't be surprised by it.

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
`FileNotFoundError: .../korfs100.csv`. Purely a test-constant bug; **left as
the one known pre-existing failure** (47/48 pass).

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

- To debug ILBFS on a specific depth: `python scripts/run_ilbfs_verbose.py 28`
  (prints expansions, collapse events, paths, F values; takes depth as argv).
- To generate one instance per depth 21–40 with A*-verified optimal depth:
  `python scripts/generate_depths21_40.py`.
- When changing ILBFS/RBFS behavior, first reproduce on amit depths 24 and 28
  — these two depths are the ones that historically exposed oscillation.

---

# Future direction: mp-rbfs (Multi-Path RBFS)

**Not yet implemented.** Full design: `docs/mp_rbfs.md`.

Summary of the agreed design:
1. **Phase 1 (fork):** expand best-first from the root until the open list has
   at least `n` nodes, always completing every expanded node's full sibling
   set ("don't miss anything").
2. **Phase 2 (procs):** each Phase-1 frontier node becomes a **proc** — a full
   RBFS search of its own subtree, with its own open list. Procs never spawn
   and never backtrack; an exhausted proc terminates.
3. **Scheduler (pluggable, single-threaded):** picks which proc runs next.
   Each proc exposes `(priority, f)` where `f` is the static `g+h` of the node
   it will expand next and `priority` is a policy score derived from `f` by
   the scheduler (best-first / round-robin / proportional / lottery).
4. **Quantum:** one node expansion per scheduling decision.
5. **Shared global tree** (transposition table) across all procs; first goal
   found terminates; **suboptimal solutions are acceptable** by design.

Reuse for implementation: `algorithms/base.py` interface, `_run_utils.py`
limits, RBFS/ILBFS pathmax + the `(f, -depth, key)` tie-break lesson, and the
amit dataset (depths 21–40) as the test bed.
