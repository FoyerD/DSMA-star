"""mp-rbfs: Multi-Path RBFS (genuine RBFS per proc).

Phase 1 builds the initial frontier exactly as in mp-bfs (`_run_phase1`), but
Phase 2 is different: each proc is a *real* Recursive Best-First Search of
its own subtree, implemented with the iterative Collapse/Restore loop that
also powers `ilbfs.py` (which is RBFS with an explicit heap + tree instead of
a recursion stack). What `expand_one()` performs is exactly one outer-loop
iteration of that loop, so the search state (open heap, live tree, `oldbest`)
persists on the proc between scheduler quanta.

RBFS semantics, per proc:

- The proc expands the lowest-F node in its own open list.
- When the popped node is no longer in the branch currently being explored
  (`oldbest != node.parent`), the Collapse loop walks up from `oldbest`,
  backing up each node's stored F to the min over its (live) children,
  incrementing its `collapse_count` oscillation penalty, deleting its
  children from the proc's TREE (heap entries store keys, so the dead
  subtrees are GC'd -- the O(b * d) per-proc memory bound), and re-pushing
  the node with its backed-up F. After any collapse the heap is rebuilt from
  the live tree to purge stale entries.
- The walk never collapses above the proc's own root (the root is the top of
  its RBFS recursion), even when the root itself is re-popped and
  re-expanded.
- Duplicate detection uses the *permanent* shared `best_g` dict: a state
  already known at a strictly better g is skipped, but a state the proc
  itself generated and later collapsed may be re-discovered at the same g --
  this re-expansion is what lets RBFS find a goal after a bound backs up.

The scheduler contract (see `mp_schedulers.py`) is unchanged from mp-bfs.
`peek_f()` now returns the proc's *backed-up* effective priority
``F + collapse_count`` of its next node, so a proc whose branch just
collapsed naturally drops in scheduling priority and other procs get the
"second chances" that single-direction procs lack. First goal found wins
(suboptimal solutions are acceptable by design).
"""
from __future__ import annotations

import heapq
import itertools
import statistics
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from domains.base import SearchProblem

from ._run_utils import MemoryLimitError, NodeLimitError, RunTracker
from .base import SearchAlgorithm, SearchLimits, SearchResult
from .mp_common import _ExpandOutcome, _Node, _Phase1Result, _live_frontier_nodes, _reconstruct, _run_phase1
from .mp_schedulers import build_scheduler

_INF = float("inf")


@dataclass(slots=True)
class _Proc:
    """One independent RBFS search restricted to a Phase-1 frontier node's
    subtree.

    Owns a private OPEN heap (entries are ``(F + collapse_count, -depth,
    state_key)`` tuples, matching the tie-break convention of `ilbfs.py`
    -- see docs/ilbfs.md section 8 -- and storing *keys* rather than node
    references so collapsed subtrees can be garbage collected immediately)
    and a private TREE (`state_key -> _Node`, the proc's live search tree).
    `oldbest` is the most recently expanded node, used by the Collapse loop.

    The shared `best_g` dict is the only cross-proc communication: it is
    permanent (never purged), so it doubles as the transposition table, while
    the proc's own TREE is what collapse actually shrinks.
    """

    proc_id: int
    heap: List[Tuple[float, float, Any]]
    tree: Dict[Any, _Node]
    root: _Node
    oldbest: Optional[_Node] = None
    expansions: int = 0
    stale_skips: int = 0
    reexpansions: int = 0
    collapses: int = 0
    active: bool = True

    def peek_f(self) -> float:
        """The backed-up effective priority of the next node this proc will
        expand (top of the open heap), or +inf when the heap is empty. After
        a collapse this reflects the backed-up F + collapse_count, which is
        exactly what the scheduler should rank procs by."""
        return self.heap[0][0] if self.heap else _INF

    def expand_one(
        self,
        problem: SearchProblem,
        best_g: Dict[Any, float],
        tracker: RunTracker,
        counter: "itertools.count[int]",
        state_key,
    ) -> Optional[_ExpandOutcome]:
        """Perform exactly one outer-loop iteration of the iterative RBFS
        (Collapse/Restore) loop for this proc's subtree, then yield control
        back to the scheduler. Returns None if the proc's heap drains to
        empty -- the proc is exhausted."""
        heap = self.heap
        while heap:
            popped_priority, _neg_depth, key = heapq.heappop(heap)
            node = self.tree.get(key)
            if node is None or node.F + node.collapse_count != popped_priority:
                self.stale_skips += 1
                continue  # collapsed away, or its F was updated by a collapse
            if node.g > best_g.get(key, _INF):
                self.stale_skips += 1
                continue  # superseded by a better path some proc already found

            if problem.is_goal(node.state):
                self.active = bool(heap)
                return _ExpandOutcome(node=node, is_goal=True)

            # Collapse loop (ilbfs.py steps 7-11): while oldbest is not
            # node.parent, back up oldbest's F, delete its children from the
            # TREE, re-push it, and walk up toward node.parent. The walk
            # stops at the proc's own root and never touches the shared
            # Phase-1 ancestors above it.
            collapsed = False
            while self.oldbest is not None and self.oldbest != node.parent:
                collapsed = True
                ob = self.oldbest
                if ob.children:
                    ob.F = min(c.F for c in ob.children.values())
                else:
                    ob.F = ob.f
                ob.collapse_count += 1
                self.collapses += 1
                heapq.heappush(
                    heap,
                    (ob.F + ob.collapse_count, -ob.depth, state_key(ob.state)),
                )
                for ck in list(ob.children.keys()):
                    if self.tree.get(ck) is ob.children[ck]:
                        del self.tree[ck]
                ob.children.clear()
                self.oldbest = ob.parent
                if ob is self.root:
                    self.oldbest = None
                    break

            # Heap purge on collapse (docs/ilbfs.md section 8): rebuild the
            # heap from the live TREE so stale entries never accumulate.
            if collapsed:
                heap[:] = [
                    (n.F + n.collapse_count, -n.depth, state_key(n.state))
                    for n in self.tree.values()
                ]
                heapq.heapify(heap)

            if node.F > node.f:
                self.reexpansions += 1

            self.expansions += 1
            for action, next_state, cost in problem.successors(node.state):
                next_key = state_key(next_state)
                new_g = node.g + cost

                live = self.tree.get(next_key)
                if live is not None and live.g <= new_g:
                    continue  # already live in this subtree at equal/better g
                if best_g.get(next_key, _INF) < new_g:
                    continue  # a strictly better path is known globally
                # Otherwise accept: a brand-new state, a strictly better path,
                # or re-discovery at the same g of a state this proc generated
                # and later collapsed (RBFS re-expansion).

                best_g[next_key] = new_g
                tracker.nodes_generated += 1

                next_h = problem.heuristic(next_state)
                next_f = new_g + next_h

                # Pathmax / F propagation (RBFS pseudocode lines 5-7):
                # F(child) = max(F(node), f(child)) when F(node) > f(node).
                if node.F > node.f and node.F > next_f:
                    next_F = node.F
                else:
                    next_F = next_f

                child = _Node(
                    state=next_state,
                    key=next_key,
                    g=new_g,
                    h=next_h,
                    f=next_f,
                    F=next_F,
                    parent=node,
                    action=action,
                    depth=node.depth + 1,
                )
                node.children[next_key] = child
                self.tree[next_key] = child
                heapq.heappush(
                    heap,
                    (child.F + child.collapse_count, -child.depth, next_key),
                )

            self.oldbest = node
            self.active = bool(heap)
            return _ExpandOutcome(node=node, is_goal=False)

        self.active = False
        return None


def _build_procs(phase1: _Phase1Result) -> List[_Proc]:
    """Turn every live (non-stale) Phase-1 frontier node into its own proc,
    seeding each proc's TREE with its root node."""
    procs: List[_Proc] = []
    for node in _live_frontier_nodes(phase1):
        pid = len(procs)
        key = node.key
        heap = [(node.F + node.collapse_count, -node.depth, key)]
        procs.append(_Proc(proc_id=pid, heap=heap, tree={key: node}, root=node))
    return procs


class MPRBFS(SearchAlgorithm):
    """Multi-Path RBFS: a Phase-1 best-first frontier build followed by
    `num_procs` independent RBFS procs (collapse/backup, O(b * d) live memory
    each) multiplexed by a pluggable scheduler. Single-threaded; "proc" is a
    logical search process, not an OS thread/process."""

    name = "mp-rbfs"

    def __init__(
        self,
        num_procs: int = 100,
        scheduler: str = "best_first",
        seed: Optional[int] = None,
        weight_power: float = 1.0,
    ) -> None:
        self.num_procs = max(1, num_procs)
        self.scheduler_kind = scheduler
        self.seed = seed
        self.weight_power = weight_power
        # Overrides the class attribute so each (scheduler) variant shows up
        # as its own algorithm in benchmark output without extra plumbing.
        self.name = f"mp-rbfs-{scheduler}"

    def search(self, problem: SearchProblem, limits: SearchLimits) -> SearchResult:
        result = SearchResult(
            algorithm_name=self.name,
            domain_name=getattr(problem, "name", "unknown"),
            instance_id="",
        )
        tracker = RunTracker.start(limits.max_nodes, limits.max_memory_mb)

        phase1: Optional[_Phase1Result] = None
        goal_node: Optional[_Node] = None
        procs: List[_Proc] = []
        winning_proc_id: Optional[int] = None
        phase2_expanded = 0
        proc_switches = 0
        max_depth_reached = 0
        max_proc_tree_size = 0

        try:
            phase1 = _run_phase1(problem, self.num_procs, tracker)
            goal_node = phase1.goal_node
            max_depth_reached = phase1.max_depth_reached

            if goal_node is None:
                procs = _build_procs(phase1)
                scheduler = build_scheduler(
                    self.scheduler_kind, procs, seed=self.seed, weight_power=self.weight_power
                )
                state_key = problem.state_key
                last_proc_id: Optional[int] = None

                while True:
                    tracker.check_limits()
                    proc = scheduler.select_next()
                    if proc is None:
                        break  # every proc exhausted -- search space depleted

                    if proc.proc_id != last_proc_id:
                        proc_switches += 1
                        last_proc_id = proc.proc_id

                    outcome = proc.expand_one(problem, phase1.best_g, tracker, phase1.counter, state_key)
                    if outcome is not None:
                        max_depth_reached = max(max_depth_reached, int(outcome.node.g))
                        if outcome.is_goal:
                            goal_node = outcome.node
                            winning_proc_id = proc.proc_id
                            break
                        phase2_expanded += 1
                        max_proc_tree_size = max(max_proc_tree_size, len(proc.tree))

                    scheduler.on_expanded(proc)

        except NodeLimitError:
            result.node_limit_reached = True
            result.error_message = "max_nodes safety valve exceeded"
        except MemoryLimitError:
            result.memory_limit_reached = True
            result.error_message = "real memory ceiling exceeded"
        finally:
            result.peak_memory_mb = tracker.stop()
            if result.peak_memory_mb > limits.max_memory_mb:
                result.memory_limit_reached = True

        if goal_node is not None:
            result.success = True
            result.solution_cost = goal_node.g
            result.solution_actions = _reconstruct(goal_node)

        phase1_expanded = phase1.expanded if phase1 is not None else 0
        phase1_stale = phase1.stale if phase1 is not None else 0

        result.runtime_seconds = tracker.elapsed()
        result.nodes_expanded = phase1_expanded + phase2_expanded
        result.nodes_generated = tracker.nodes_generated
        result.max_depth_reached = max_depth_reached
        result.reexpansions = phase1_stale + sum(p.stale_skips for p in procs) + sum(p.reexpansions for p in procs)
        result.total_collapses = sum(p.collapses for p in procs)
        result.max_proc_tree_size = max_proc_tree_size

        phase1_frontier = phase1.max_frontier_size if phase1 is not None else 0
        proc_frontier = sum(len(p.heap) for p in procs)
        result.max_frontier_size = max(phase1_frontier, proc_frontier)

        result.requested_num_procs = self.num_procs
        result.actual_num_procs = len(procs)
        result.scheduler_name = self.scheduler_kind
        result.phase1_expanded = phase1_expanded
        result.phase2_expanded = phase2_expanded
        result.proc_switches = proc_switches

        if procs:
            exp_counts = [p.expansions for p in procs]
            result.active_procs_at_solution = sum(1 for p in procs if p.active)
            result.min_proc_expansions = min(exp_counts)
            result.max_proc_expansions = max(exp_counts)
            result.mean_proc_expansions = statistics.fmean(exp_counts)
            result.median_proc_expansions = statistics.median(exp_counts)
            result.std_proc_expansions = statistics.stdev(exp_counts) if len(exp_counts) >= 2 else 0.0
            result.procs_used = sum(1 for c in exp_counts if c > 0)
            result.proc_expansions_histogram = ",".join(str(c) for c in exp_counts)
            if winning_proc_id is not None:
                result.winning_proc_id = winning_proc_id
                result.winning_proc_expansions = procs[winning_proc_id].expansions

        return result
