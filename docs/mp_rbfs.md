# Multi-Path RBFS (mp-rbfs): Design and Implementation Guide

## 1. What mp-rbfs is

Multi-Path RBFS is a new search algorithm that runs **several independent
RBFS searches at the same time** — one per "path" — and multiplexes them with
a pluggable **scheduler** instead of committing to a single tree like A* or a
single recursion like RBFS.

The name comes from the two things it combines:

- **RBFS**: each unit of work (a **proc**) is a full RBFS search of its own
  subtree, selecting nodes by best-first order inside its own open list.
- **Multi-path**: the scheduler chooses *which* proc runs next. Different
  scheduling policies produce different overall search behavior.

### Why this is interesting

A* and RBFS sit at opposite ends of a spectrum:

| | A* | RBFS | mp-rbfs |
|---|---|---|---|
| Trees searched | one | one | many (one per proc) |
| Memory | every generated node (O(b^d) worst) | O(b*d) recursion | procs * O(b*d) |
| Scheduling | none (heap order) | none (recursion order) | **pluggable** |
| Optimality | guaranteed | guaranteed | policy-dependent (suboptimal OK) |

The insight behind mp-rbfs: once you have a frontier of N promising nodes,
each one is the root of a subtree that is worth exploring *in its own right*.
Rather than forcing one global search to alternate between them (the RBFS
collapse/restore dance) or keeping all of them in one giant heap (A*), give
each subtree a "proc" and let a scheduler interleave them.

---

## 2. The two phases

mp-rbfs has a clear fork between building a frontier and exploring it.

### Phase 1 — the fork: build an initial frontier of at least `n` nodes

Expand best-first from the problem root, exactly like A*, **until the open
list has at least `n` nodes**.

One rule is mandatory: **finish generating all siblings.** If the expansion
that crosses `n` happens in the middle of a node's children, you must generate
*all* of that node's children before stopping.

> Why: "don't miss anything". If you stop mid-expansion, the frontier would
> contain a *partial* sibling set. A proc rooted at one of the generated
> children would commit to a path while its ungenerated siblings are never
> considered — a lost opportunity that can miss the solution entirely. A
> frontier is only a faithful snapshot of the search if every expanded node's
> full child set is present in it.

Phase 1 uses the **static** cost `f = g + h` (no pathmax/F back-up). The
frontier nodes are ordinary nodes with a `g` value and a `state`.

Result of Phase 1: `OPEN` contains `>= n` frontier nodes. Each of these nodes
is the head of a distinct **root-to-node path** in the search tree.

### Phase 2 — the procs: one RBFS search per path

Each Phase-1 frontier node becomes the root of one **proc**. A proc is:

> an independent, full RBFS search of the subtree rooted at its frontier node.

Key behaviors (from the design decisions):

- The proc has **its own open list** (the frontier of *its* subtree).
- When the scheduler selects the proc, the proc expands the **best node in its
  own open list** (lowest `f`).
- When children are generated, they are pushed into **that proc's open list**.
  The proc follows the best one. **It does not spawn new procs.** A proc is
  exactly one RBFS instance for its entire lifetime.
- **No backtracking / no re-spawning.** If a proc's open list is exhausted
  (dead end, or all candidates fail), the proc terminates and is removed from
  the table. Nothing revives it.

> Design decision recorded: an earlier design (`docs/multi_process_search.md`)
> treated each A* leaf as a process that ran *to completion* before the
> scheduler re-decided, and allowed process spawning. mp-rbfs differs in two
> ways: (a) scheduling is per **single node expansion** (fine-grained, the
> scheduler re-decides after every expansion), and (b) procs never spawn — the
> proc count is fixed at the number of Phase-1 frontier nodes.

---

## 3. What a proc exposes to the scheduler (requirement 3)

Every proc publishes two values that the scheduler uses to decide whom to run:

1. **`f` — the f-value of the node that will be chosen next.** This is the
   static `f = g + h` of the node currently at the top of the proc's open
   list (the node the proc will expand if scheduled). This is what makes
   scheduling meaningful: the scheduler can see, at a glance, how promising
   each proc's next move is.

2. **`priority` — a scheduler-policy score.** `priority` is *derived from `f`*
   by the scheduler's policy (e.g. best-first uses `priority = f`; a lottery
   policy converts `f` into ticket weights `1/f`; round-robin ignores `f`
   entirely). The proc itself does not compute priority; the policy lives in
   the scheduler so it can be swapped without touching the proc.

If a proc's open list is empty, it reports `f = +inf` (and a matching
priority) so the scheduler can simply never pick it and eventually drop it.

---

## 4. The scheduling loop

```
procs = build_initial_procs(root, n)        # Phase 1 + one Proc per frontier node
table = ProcTable(procs, shared_nodes_dict)
scheduler = <policy>.create()               # pluggable

while table.active_procs:
    proc = scheduler.select_next(table)     # uses proc.priority / proc.f
    if proc is None:
        break                               # no proc can make progress

    proc.expand_one()                       # one node expansion, then yield

    if proc.found_goal:
        return reconstruct(proc.goal_node)  # terminate immediately, first goal wins
    if proc.is_exhausted:
        table.remove(proc)

return FAILED                               # all procs exhausted, no solution
```

- **One expansion per schedule.** When a proc is picked it expands exactly one
  node (its best open-list node) and yields back to the scheduler. This is the
  finest practical grain and gives the closest approximation of a globally
  best-first search.
- **First goal wins.** When any proc expands a goal node, the search stops
  immediately and the solution is reconstructed. No "keep looking for a better
  one" — optimality is *not* guaranteed (the user accepted suboptimal
  solutions), and chasing a better goal would require tracking a global best,
  which we deliberately do not do.
- **Shared global tree.** All procs share one global `nodes` dict (state →
  best `_Node`). If a proc generates a state that already exists with an equal
  or better `g`, it skips it (transposition). This is the only cross-proc
  communication: state deduplication. Each proc's open list stays private.

---

## 5. Data structures

### 5.1 `Proc`

```python
@dataclass
class Proc:
    proc_id: int
    root_key: Any              # the Phase-1 frontier node this proc searches from
    open_heap: List[Tuple[float, int, Any]]   # own frontier: (f, -depth, state_key)
    nodes: Dict[Any, _Node]    # own subtree nodes (see 5.4 on sharing)
    bound: float               # initial bound for the proc's RBFS (see §6)
    status: str                # "ready" | "solved" | "exhausted"
    nodes_expanded: int = 0
    goal_node: Optional[_Node] = None

    @property
    def f(self) -> float:
        """f of the node that will be chosen next (top of open_heap), +inf if empty."""
        return self.open_heap[0][0] if self.open_heap else float("inf")
```

### 5.2 `Scheduler` (the pluggable part — requirement 2)

```python
class Scheduler(ABC):
    @abstractmethod
    def select_next(self, procs: List[Proc]) -> Optional[Proc]:
        """Pick the proc to run next, or None if none can make progress."""
```

Every policy is a subclass. The scheduler reads `proc.priority` and
`proc.f` and nothing else about the search — that is the contract that makes
policies swappable.

### 5.3 `ProcTable`

```python
class ProcTable:
    procs: List[Proc]
    shared_nodes: Dict[Any, _Node]   # transposition table across all procs
    def remove(self, proc: Proc): ...
```

### 5.4 Memory model — the shared tree vs. proc-local state

Per the design decisions:

- The **global `nodes` dict** is shared. Any state ever generated by any proc
  is recorded there (state → best `_Node`), so no state is generated twice
  across the whole run. This is the transposition table.
- Each proc keeps its **own open list** (its subtree frontier). Whether it
  also keeps its own full subtree (`proc.nodes`) or relies on the shared dict
  is an implementation choice; the simplest correct version reuses the shared
  `nodes` dict for storage and keeps only `open_heap` proc-local, with each
  proc's RBFS bounds tracked per-proc.

Worst-case memory is therefore `n * O(b*d)` (each proc's active subtree) plus
`O(total distinct states generated)` for the shared dict. If that is too much,
see **Open questions** (shared dict budget, per-proc collapse).

---

## 6. The proc's internal search (the "full RBFS of its own")

Each proc behaves like a self-contained RBFS *within its subtree*:

1. Pop the node with the lowest `f` from its own `open_heap` (ties: deeper
   first, like the ILBFS/RBFS tie-break — reuse the `(f, -depth, key)` tuple).
2. If it is a goal → `status = "solved"`, store `goal_node`, terminate the run.
3. Expand it: generate **all** children (sibling-complete), compute
   `f = g + h`, apply **pathmax** to carry forward the parent's backed-up
   value when the parent was re-expanded (`F(child) = max(F(parent), f(child))`
   when `F(parent) > f(parent)`), push into the proc's `open_heap`, and insert
   into the shared `nodes` dict (skipping states with an equal-or-better
   existing `g`).
4. Update the reported `f` (top of the heap) and yield.

**Initial bound.** Each proc starts with `bound = +inf` (or a configurable
upper threshold, e.g. a global cost cap). With `+inf` the proc is effectively
a linear-space best-first search of its own subtree that only stops when the
subtree is exhausted or a goal is found. If a bound is desired, the proc stops
pushing children whose `F > bound`; when its open heap empties it terminates.

**No backtracking.** A proc never re-routes itself back to a sibling it
passed; once its open heap is empty it is `exhausted`. (Contrast with classic
RBFS, which collapses back to a better sibling — mp-rbfs procs are
single-direction. The *scheduler* is what provides the "second chances", by
interleaving many procs at once.)

---

## 7. Scheduling policies

| Policy | `priority` used | Effect |
|---|---|---|
| **Best-first** | `priority = f` | Always runs the proc whose next node has the lowest f. Closest to a single global A*/RBFS order. |
| **Round-robin** | none (cycles) | Gives every proc equal attention; very fair, slow to deep-search any one path. |
| **Proportional** | `priority = 1/f` | Lower-f procs are picked more often; a probabilistic blend of best-first and fairness. |
| **Lottery** | tickets ∝ `1/f` | Random draw; each run is different; useful for diversity across a frontier. |
| **Priority queue (user-defined)** | external score | A static/domain-specific score per proc, set at spawn; f is informational. |

Because the proc exposes only `(priority, f)`, adding a policy means adding one
`Scheduler` subclass — nothing in the proc or the table changes. This is the
deliberate seam required by **requirement 2**.

### Optimality note

The user explicitly accepted **suboptimal solutions**. Best-first scheduling
happens to be optimal-*ish* (it reproduces global best-first expansion order
modulo the per-proc isolation), but round-robin, lottery, and proportional
policies can stop at the first goal found even if another proc would have
found a cheaper one. Do not claim optimality for the general case.

---

## 8. Termination and resource limits

- **Success**: any proc expands a goal node → terminate immediately.
- **Exhaustion**: all procs are `exhausted` (all open heaps empty) → return
  `FAILED`.
- **Node ceiling**: count across all procs with the existing `RunTracker`
  node-limit; stop the whole run if exceeded.
- **Memory ceiling**: reuse `RunTracker`'s `psutil`-sampled RSS check
  (`algorithms/_run_utils.py`). The shared `nodes` dict is the main memory
  consumer, so the memory ceiling effectively bounds the transposition table.

---

## 9. Solution reconstruction

Every `_Node` has a `parent` pointer, and Phase 1's frontier nodes are
ordinary nodes with their own parent chain back to the problem root. So the
path is simply:

```
proc.goal_node  --parent pointers-->  Phase-1 frontier node  --parent pointers-->  root
```

Walking `goal_node.parent` up to `None` yields the full root→goal action list
in one pass — no splicing needed, because the tree is shared and contiguous.

---

## 10. Implementation plan (in order)

### Milestone 1 — skeleton + best-first scheduler
1. `algorithms/base.py`: no changes needed (subclass `SearchAlgorithm`).
2. `algorithms/mp_rbfs.py`:
   - `Proc` dataclass with `open_heap`, `f` property, `expand_one()`.
   - Phase 1: best-first expansion from root until `len(OPEN) >= n`, with the
     "complete all siblings before stopping" rule.
   - `BestFirstScheduler` (a thin heap over procs keyed by `proc.f`).
   - `MPRBFS(SearchAlgorithm)` orchestrating Phase 1 + Phase 2 + shared dict.
3. Wire into `main.py` (`--scheduler`, `--num-procs n`).

### Milestone 2 — prove it finds solutions
4. Tests on the 8-puzzle (trivial instances), then 15-puzzle at
   scramble depth 10: every scheduler must solve or report a limit honestly.
5. Verify no state is generated twice across procs (shared dict works).

### Milestone 3 — policies + hardening
6. `RoundRobinScheduler`, `ProportionalScheduler`, `LotteryScheduler`.
7. Exhaustion handling, empty-frontier edge cases, duplicate-state handling.
8. Comparison tests vs. single A*/RBFS on the amit/Korf instances.

### Milestone 4 — analysis
9. Instrument `SearchResult` with per-run `num_procs`, `proc_switches`,
   per-proc expansion histograms.
10. Analyze: which scheduler finds the solution first / with fewest total
    expansions on the amit depths 21–40 dataset.

---

## 11. Open questions / design knobs

- **What is a good `n` (frontier size)?** Fixed (e.g. 50/100)? Proportional to
  branching factor? This is the main free parameter.
- **Shared-dict memory ceiling.** The shared `nodes` dict can dominate memory.
  Should there be a cap (evicting like SMA*), or is the global memory ceiling
  enough?
- **Should procs collapse internally?** Right now a proc keeps whatever it
  generates in its open heap until exhausted. An internal collapse (like
  ILBFS/RBFS) would keep each proc's memory to O(b*d) — the earlier
  `multi_process_search.md` called this the "Principal Branch Invariant". If
  this is wanted, port the collapse logic from `algorithms/rbfs.py` / the
  tie-breaking from `algorithms/ilbfs.py` (see `docs/ilbfs.md` §8) into
  `Proc.expand_one`.
- **Bound per proc.** `+inf` by default. A global cost cap would let procs
  self-terminate when their next node is worse than the cap.
- **Bounded proc count.** With no spawning the count is fixed at `n`, but
  should procs that find a goal *before* the optimal path be re-prioritized,
  or is first-goal-wins sufficient? (Per design decision: first-goal-wins.)

---

## 12. Relation to existing code and docs

- **Supersedes / refines** `docs/multi_process_search.md`. That document
  proposed OS-process RBFS runs from A* leaves with coarse scheduling. mp-rbfs
  keeps the "one search per frontier node" spirit but makes the scheduler
  pluggable, single-threaded, and per-expansion, with a shared tree and no
  proc spawning.
- **Reuses** `algorithms/base.py` (`SearchAlgorithm`, `SearchLimits`,
  `SearchResult`), `algorithms/_run_utils.py` (`RunTracker` limits),
  `algorithms/rbfs.py` (pathmax propagation, node expansion), and
  `docs/ilbfs.md` §8 (the heap tie-breaking lesson: `(f, -depth, key)` plus a
  collapse penalty — directly applicable to each proc's open heap).
- **Test domain**: 15-puzzle (Manhattan heuristic). Datasets: `korf`
  (Korf's 100, true optimal depths), `amit`
  (`instances/puzzle_amit_depths21_40.csv`, true optimal depths 21–40,
  A*-verified), `scramble` (random walks, scramble depth ≠ optimal depth).
