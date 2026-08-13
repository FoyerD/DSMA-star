# Multi-Path Best-First (mp-bfs): Design and Implementation Guide

## 1. What mp-bfs is

Multi-Path Best-First runs **several independent best-first searches at the
same time** — one per "path" — and multiplexes them with a pluggable
**scheduler** instead of committing to a single global heap like A*.

mp-bfs shares almost all of its machinery with **mp-rbfs**: the Phase-1 fork,
the proc model, the scheduler contract, and the shared `best_g` dedup table.
The one difference is the proc's inner loop — mp-bfs procs run plain
best-first (expand the best node in their own heap), while mp-rbfs procs run a
real iterative RBFS with collapse/back-up. See `docs/mp_rbfs.md` for the
shared design rationale; this document focuses on what is specific to mp-bfs.

- **Implementation**: `algorithms/mp_bfs.py` (procs), `algorithms/mp_common.py`
  (Phase 1, `_Node`, reconstruction), `algorithms/mp_schedulers.py` (policies).
- **CLI**: `python main.py ... --algorithms mp-bfs-<sched>` with `--num-procs`.

## 2. Why have a best-first variant at all

mp-rbfs is a *real* RBFS: it collapses subtrees and re-expands them, so on
hard instances its expansion count is an order of magnitude above a plain
best-first search. mp-bfs is the control group that shows what the RBFS
collapse machinery buys (bounded live tree) and costs (re-expansion). It is
also the useful baseline for the multi-path idea itself: even with plain
best-first procs, the multi-path architecture changes behavior vs. a single
A* run — the shared `best_g` across procs plus first-goal-wins scheduling can
find suboptimal solutions faster than a single search.

## 3. Phase 1 — the fork

Identical to mp-rbfs (see `docs/mp_rbfs.md` §2). Expand best-first from the
root until the open list has at least `--num-procs` nodes, always completing
every expanded node's full sibling set. Every generated state goes into the
shared `best_g` dict (state → best `g`).

## 4. Procs — plain best-first

Each Phase-1 frontier node becomes a **proc**:

```python
@dataclass(slots=True)
class _Proc:
    proc_id: int
    heap: List[Tuple[float, float, Any]]     # (f, -depth, key)
    root: _Node
    expansions: int = 0
    stale_skips: int = 0                     # popped entries superseded in best_g
    active: bool = True
```

When scheduled, `expand_one` pops the best node in the proc's own heap
(lowest `f`, ties to deeper nodes via `-depth`), and pushes each child that is
not dominated by the shared `best_g` (and not already in the heap at an equal
or better `g`). An exhausted proc (heap drains to empty) terminates. **Procs
never spawn and never backtrack** — the scheduler provides the interleaving.

There is no collapse, no F back-up, and no per-proc tree: each proc holds only
its heap, and every generated node lives in the shared `best_g` dict.

## 5. Scheduling

The scheduler contract is identical to mp-rbfs: each proc exposes
`(priority, f)` via `peek()`, and the scheduler picks one proc per quantum.
Policies (`algorithms/mp_schedulers.py`): `best_first` (priority = f),
`round_robin`, `proportional` (`1/(f+eps)**power`).

With `best_first`, mp-bfs on an instance where Phase 1 produces a small
frontier is effectively a global best-first search and behaves much like
ILBFS/A* modulo the shared-dict re-expansion policy. With `round_robin` or
`proportional`, behavior diverges deliberately.

## 6. Termination and limits

- First goal found terminates the run (**suboptimal by design**).
- All procs exhausted → `FAILED`.
- `--max-nodes` / `--max-memory-mb` ceilings enforced via the shared
  `RunTracker`, same as mp-rbfs.

## 7. Memory model

Unlike mp-rbfs there is no per-proc live tree to bound — the memory consumer
is the shared `best_g` dict (every generated state), exactly like A* but
without a closed set. `max_frontier_size` (the largest number of live frontier
nodes across all procs) is reported per run as the memory proxy.

## 8. Tests

`tests/test_mp_bfs.py` covers the shared infrastructure used by both mp
algorithms — Phase-1 sibling-completeness and early-stop, the shared-`best_g`
dedup contract, the best-first proc loop, exhaustion handling, all three
scheduler policies, and the suboptimal-result scenario. mp-rbfs-specific
collapse/back-up behavior is tested separately in `tests/test_mp_rbfs.py`.
