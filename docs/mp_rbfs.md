# Multi-Path RBFS (mp-rbfs): Design and Implementation Guide

## 1. What mp-rbfs is

Multi-Path RBFS runs **several independent RBFS searches at the same time** —
one per "path" — and multiplexes them with a pluggable **scheduler** instead of
committing to a single tree like A* or a single recursion like RBFS.

The name comes from the two things it combines:

- **RBFS**: each unit of work (a **proc**) is a real iterative RBFS
  (Collapse/Restore) of its own subtree.
- **Multi-path**: the scheduler chooses *which* proc runs next. Different
  scheduling policies produce different overall search behavior.

mp-rbfs is implemented in `algorithms/mp_rbfs.py` (with `algorithms/mp_common.py`
for Phase 1 and `algorithms/mp_schedulers.py` for the policies). Its sibling
**mp-bfs** (`algorithms/mp_bfs.py`) shares that infrastructure but its procs
run plain best-first instead of RBFS; see `docs/mp_bfs.md`.

### Why this is interesting

A* and RBFS sit at opposite ends of a spectrum:

| | A* | RBFS | mp-rbfs |
|---|---|---|---|
| Trees searched | one | one | many (one per proc) |
| Memory | every generated node (O(b^d) worst) | O(b*d) recursion | n * O(b*d) live trees |
| Scheduling | none (heap order) | none (recursion order) | **pluggable** |
| Optimality | guaranteed | guaranteed | policy-dependent (suboptimal OK) |

The insight: once you have a frontier of N promising nodes, each one is the
root of a subtree worth exploring *in its own right*. Rather than forcing one
global search to alternate between them (the RBFS collapse/restore dance) or
keeping all of them in one giant heap (A*), give each subtree a "proc" and let
a scheduler interleave them. Each proc keeps its own live tree to O(b·d), so
the whole run stays memory-bounded even while generating millions of nodes.

---

## 2. The two phases

### Phase 1 — the fork: build an initial frontier of at least `n` nodes

Expand best-first from the problem root, exactly like A*, **until the open
list has at least `n` nodes**.

One rule is mandatory: **finish generating all siblings.** If the expansion
that crosses `n` happens in the middle of a node's children, you must generate
*all* of that node's children before stopping.

> Why: "don't miss anything". If you stop mid-expansion, the frontier would
> contain a *partial* sibling set. A proc rooted at one of the generated
> children would commit to a path while its ungenerated siblings are never
> considered — a lost opportunity that can miss the solution entirely.

Phase 1 uses the **static** cost `f = g + h` (no pathmax/F back-up). The
frontier nodes are ordinary `_Node`s with a `g` value, `state`, and a parent
chain back to the root. Every generated state is recorded in the shared
`best_g` dict (state → best `g` found so far) so no state is ever expanded
twice across the whole run.

### Phase 2 — the procs: one RBFS search per path

Each Phase-1 frontier node becomes the root of one **proc**. A proc is:

> an independent, full RBFS search of the subtree rooted at its frontier node.

Key behaviors:

- The proc has **its own open heap** and **its own local tree** of live nodes.
- When the scheduler selects the proc, the proc performs **one** outer-loop
  iteration of the iterative RBFS algorithm (pop best, expand, back up F,
  collapse if the best node is not a child of the last expanded node).
- **No proc spawning.** The proc count is fixed at the number of Phase-1
  frontier nodes. A proc that finds a goal terminates the whole run; a proc
  whose heap drains to empty terminates forever.
- **Shared `best_g` dedup.** Every child a proc generates is checked against
  the shared `best_g` table first. If another proc (or Phase 1) already found
  the state cheaper, the child is skipped — this is the only cross-proc
  communication.

---

## 3. What a proc exposes to the scheduler

Every proc publishes two values the scheduler uses to decide whom to run:

1. **`f`** — the f-value of the node that will be chosen next (the top of the
   proc's own open heap). This is what makes scheduling meaningful: the
   scheduler can see how promising each proc's next move is.
2. **`priority`** — a scheduler-policy score *derived from `f`* by the
   scheduler's policy (e.g. best-first uses `priority = f`; round-robin
   ignores `f` entirely; proportional converts `f` into a weight
   `1 / (f + eps)**power`). The proc does not compute priority; the policy
   lives in the scheduler so it can be swapped without touching the proc.

If a proc's heap is empty, it reports `f = +inf` (and matching priority) so
the scheduler never picks it and eventually drops it.

---

## 4. The scheduling loop

```
procs = build_procs(phase1)                # Phase 1 + one _Proc per frontier node
scheduler = build_scheduler(policy, procs) # pluggable

while True:
    tracker.check_limits()                 # node / memory ceilings
    proc = scheduler.select_next()         # uses proc.peek() -> (priority, f)
    if proc is None:
        break                              # no proc can make progress

    outcome = proc.expand_one(problem, best_g, tracker, counter, state_key)
    if outcome is None:
        continue                           # proc exhausted; scheduler drops it
    if outcome.is_goal:
        return reconstruct(outcome.node)   # terminate immediately, first goal wins
```

- **One expansion per schedule.** When a proc is picked it performs exactly one
  outer RBFS iteration (which may expand one node and back up / collapse) and
  yields back to the scheduler. This is the finest practical grain and gives
  the closest approximation of a globally best-first search.
- **First goal wins.** When any proc expands a goal node, the search stops
  immediately and the solution is reconstructed. Optimality is *not*
  guaranteed (suboptimal solutions are acceptable by design).

---

## 5. Data structures

All of these live in `algorithms/mp_rbfs.py` / `algorithms/mp_common.py`.

### 5.1 `_Node` (shared with mp-bfs, `algorithms/mp_common.py`)

A full search-tree node:

```python
@dataclass(slots=True)
class _Node:
    state: PuzzleState
    g: float
    h: float
    parent: Optional["_Node"] = None
    move: Optional[Any] = None
    f: float = 0.0            # static g + h
    F: float = 0.0            # backed-up RBFS value (mp-rbfs)
    children: dict = field(default_factory=dict)  # state_key -> _Node
    oldbest: Optional["_Node"] = None             # last expanded node (mp-rbfs)
    order: int = 0            # generation counter (heap tie-breaking)
```

Phase 1 reuses this full node type, so Phase-1 frontier nodes carry the same
metadata and their parent chains reach the root — solution reconstruction is a
single parent-pointer walk.

### 5.2 `_Proc` (mp-rbfs)

```python
@dataclass(slots=True)
class _Proc:
    proc_id: int
    heap: List[Tuple[float, float, Any]]     # own OPEN: (F + collapse_count, -depth, key)
    tree: Dict[Any, _Node]                   # own live subtree (O(b·d))
    root: _Node
    oldbest: Optional[_Node] = None          # last expanded node
    expansions: int = 0
    stale_skips: int = 0
    reexpansions: int = 0                    # genuine F>f re-expansions
    collapses: int = 0                       # collapse-loop iterations
    active: bool = True

    def peek(self) -> Tuple[float, float]:
        """Return (priority, f) for the scheduler, or (inf, inf) if drained."""
    def expand_one(self, problem, best_g, tracker, counter, state_key):
        """One outer-loop iteration of iterative RBFS; returns an outcome."""
```

### 5.3 Schedulers (`algorithms/mp_schedulers.py`)

Three policies are implemented: `best_first`, `round_robin`, and
`proportional`. Each is a `Scheduler` subclass; the only thing they read about
a proc is `(priority, f)` — that contract is what makes policies swappable.
`build_scheduler(name, procs)` is the factory `main.py` uses.

### 5.4 Memory model

- The **shared `best_g` dict** (state → best `g`) is the transposition table.
  Any state ever generated by any proc is recorded there, so no state is
  expanded twice across the whole run.
- Each proc keeps its **own live tree** of the nodes it is actively searching.
  When the proc collapses, the lost nodes are deleted from the tree (and their
  heap entries lazily skipped later), keeping each proc's live tree to O(b·d)
  — the Principal Branch Invariant. `total_collapses` and
  `max_proc_tree_size` are reported per run to verify this: on amit depth 29
  the max live tree stayed at 40 nodes while generating ~500K.

Worst-case memory is therefore `n * O(b*d)` (the proc trees) plus `O(total
distinct states generated)` for the shared dict.

---

## 6. The proc's internal search (real iterative RBFS)

Each proc runs the iterative RBFS (Collapse/Restore) loop from
`docs/ilbfs.md`, scoped to its own subtree, with two additions:

1. **Heap tie-breaking.** The proc's open heap is keyed by
   `(F + collapse_count, -depth, state_key)` — the same tuple that fixed the
   ILBFS oscillation bug (see `docs/ilbfs.md` §8). Deeper nodes win ties
   (`-depth`) and every collapse degrades a node's effective priority by 1
   (`collapse_count`), forcing a branch switch instead of an infinite
   re-expansion loop. `F` (not `-depth`) stays the *primary* key so the search
   remains best-first and doesn't degrade into greedy DFS.

2. **Re-expansion after collapse.** The dedup rule in the successor loop only
   rejects a child when the shared `best_g` knows a *strictly better* path
   (`best_g[key] < new_g`). A state the proc itself generated and later
   collapsed is therefore re-accepted when the parent is re-expanded at the
   same `g` — that is RBFS's re-expansion, and it is what lets a proc find a
   goal after a bound backs up. There is no explicit re-insertion pass; the
   re-discovery falls out of the equal-`g` acceptance rule.

The proc also dedups every generated child against the shared `best_g` table
before adding it to its own tree.

**Bookkeeping distinction.** Backed-up `F` values let mp-rbfs tell "genuinely
re-expanded" nodes from "stale heap skips": a node popped with `F > f` is a
real re-expansion (`reexpansions += 1`, and `F` is clamped up via pathmax);
a node whose `tree` entry is gone or superseded by a better `best_g` is a
stale skip (`stale_skips += 1`). Collapsed subtrees are regenerated from
scratch — the documented ILBFS/RBFS family behavior — which is why mp-rbfs
expansion counts are an order of magnitude above mp-bfs/ILBFS on hard depths.

---

## 7. Scheduling policies

| Policy | `priority` used | Effect |
|---|---|---|
| **best_first** | `priority = f` | Always runs the proc whose next node has the lowest f. Closest to a single global A*/RBFS order. |
| **round_robin** | none (cycles) | Gives every proc equal attention; very fair, slow to deep-search any one path. |
| **proportional** | `1 / (f + eps) ** power` (`--proportional-weight-power`, default 1.0) | Lower-f procs are picked more often; a probabilistic blend of best-first and fairness. |

Because the proc exposes only `(priority, f)`, adding a policy means adding one
`Scheduler` subclass in `algorithms/mp_schedulers.py` and one name in
`main.py` — nothing in the proc or the search loop changes.

### Optimality note

Suboptimal solutions are accepted by design. Best-first scheduling
reproduces a global best-first expansion order modulo the per-proc isolation,
but any policy stops at the first goal found even if another proc would have
found a cheaper one. Do not claim optimality for the general case.

---

## 8. Termination and resource limits

- **Success**: any proc expands a goal node → terminate immediately.
- **Exhaustion**: all procs are exhausted (all heaps empty) → return `FAILED`.
- **Node ceiling**: counted across all procs with the shared `RunTracker`
  (`--max-nodes`, default 5M).
- **Memory ceiling**: `RunTracker`'s psutil-sampled RSS check
  (`algorithms/_run_utils.py`). The shared `best_g` dict is the main memory
  consumer.

---

## 9. Solution reconstruction

Every `_Node` has a `parent` pointer, and Phase-1 frontier nodes are ordinary
nodes with their own parent chain back to the problem root. Walking
`goal_node.parent` up to `None` (`_reconstruct` in `algorithms/mp_common.py`)
yields the full root→goal action list in one pass — no splicing needed.

---

## 10. Implementation status

Implemented (08-13), in `algorithms/mp_bfs.py` + `algorithms/mp_rbfs.py` +
`algorithms/mp_common.py` + `algorithms/mp_schedulers.py`:

- [x] Phase 1 fork (best-first, sibling-complete frontier, shared `best_g`)
- [x] `_Proc` with `peek()`/`expand_one()` — one RBFS iteration per quantum
- [x] Collapse/Restore with the `(F + collapse_count, -depth, key)` tie-break
- [x] Re-expansion at equal `g` (collapsed subtrees regenerated by RBFS)
- [x] Schedulers: `best_first`, `round_robin`, `proportional`
- [x] Wired into `main.py` as `mp-rbfs-<sched>` (`--num-procs`,
      `--proportional-weight-power`)
- [x] Result instrumentation: `phase1_expanded`, `phase2_expanded`,
      `actual_num_procs`, `proc_switches`, `total_collapses`,
      `max_proc_tree_size`
- [x] Tests in `tests/test_mp_rbfs.py` (proc RBFS internals) plus the shared
      Phase-1 / scheduler / `best_g` coverage in `tests/test_mp_bfs.py`

Measured behavior (amit instances, `best_first`, `num-procs=100`):

- depth 24: ≈ 35K expansions / ~2s vs ILBFS 3.4K / 0.2s; solved.
- depth 28: ≈ 135K expansions / ~8s vs ILBFS ≈ 182K / 14s; solved.
- depth 29: ≈ 274K expansions then node limit; max live tree stayed at 40
  nodes (the O(b·d) bound) while generating ~500K.

On the easy half of the amit range mp-rbfs is competitive with ILBFS; from
depth ~29 onward it re-expands exponentially and typically hits the node limit
or times out, exactly like ILBFS/RBFS.

---

## 11. Open questions / design knobs

- **What is a good `n` (frontier size)?** Fixed (default 100)? Proportional to
  branching factor? This is the main free parameter.
- **Shared-dict memory ceiling.** The shared `best_g` dict dominates memory.
  Should there be a cap (evicting like SMA*), or is the global memory ceiling
  enough?
- **Re-expansion policy.** Collapsed subtrees are regenerated from scratch
  whenever their parents are re-expanded (the equal-`g` acceptance rule).
  An explicit re-insertion pass — pushing a still-useful collapsed node back
  into the shared open list as a fresh proc — is a plausible alternative worth
  measuring; the current code does not do it.
- **Bound per proc.** Procs use `F` back-up from their subtree's own expansion;
  a global cost cap would let procs self-terminate when their next node is
  worse than the cap.
- **Goal ordering.** First-goal-wins is by design, but it would be easy to add
  a global best-goal tracking later if a bounded-suboptimal mode is wanted.

---

## 12. Relation to existing code and docs

- **Reuses** `algorithms/base.py` (`SearchAlgorithm`, `SearchLimits`,
  `SearchResult`), `algorithms/_run_utils.py` (`RunTracker` limits),
  `algorithms/mp_common.py` (Phase 1, full `_Node`), and
  `docs/ilbfs.md` §8 (the heap tie-breaking lesson: `(F + collapse_count,
  -depth, key)` — directly applied to each proc's open heap).
- **Sibling algorithm**: mp-bfs (`docs/mp_bfs.md`) shares Phase 1, the
  scheduler contract, and the shared `best_g`, but its procs run plain
  best-first — the control group that shows what the RBFS collapse machinery
  costs and buys.
- **Test domain**: 15-puzzle (Manhattan heuristic). Datasets: `korf`
  (Korf's 100, true optimal depths), `amit`
  (`instances/puzzle_amit_depths21_40.csv`, true optimal depths 21–40,
  A*-verified), `scramble` (random walks, scramble depth ≠ optimal depth).
