"""mp-bfs: Multi-Path Best-First Search.

The "honest" name for what used to be called mp-rbfs: each proc is a *plain*
best-first search of its Phase-1 frontier node's subtree. There is no
collapse, no F back-up, no bound -- a proc keeps its entire generated subtree
in its open heap until the subtree is exhausted, so per-proc memory is
O(subtree), not O(b * d). This is the fast, high-success-rate variant; see
`mp_rbfs.py` for the memory-bounded sibling that runs a genuine RBFS per
proc.

Phase 1 (the fork) and the pluggable schedulers are shared with mp-rbfs and
live in `mp_common.py` / `mp_schedulers.py`. The first proc to pop a goal
state wins, so mp-bfs is intentionally allowed to return a suboptimal
solution; Best-First scheduling tends closest to a single global best-first
search, while Round-Robin and Proportional trade optimality for fairness and
robustness against starvation.
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
    """One independent best-first search restricted to a Phase-1 frontier
    node's subtree.

    Owns a private OPEN heap (entries are ``(f, -g, counter, node)`` tuples:
    depth/`g` prefers deeper nodes on an `f` tie, and the monotonic counter
    guarantees heapq never has to compare two `_Node` objects directly).
    Duplicate detection against every other proc happens purely through the
    *shared* `best_g` dict passed into `expand_one` -- procs never read or
    write each other's heaps.
    """

    proc_id: int
    heap: List[Tuple[float, float, int, _Node]]
    expansions: int = 0
    stale_skips: int = 0
    active: bool = True

    def peek_f(self) -> float:
        # May reflect a stale (superseded) entry -- see the module docstring.
        # Cheap (O(1)) and self-correcting: resolved lazily the next time
        # this proc is actually selected and its heap is drained below.
        return self.heap[0][0] if self.heap else _INF

    def expand_one(
        self,
        problem: SearchProblem,
        best_g: Dict[Any, float],
        tracker: RunTracker,
        counter: "itertools.count[int]",
        state_key,
    ) -> Optional[_ExpandOutcome]:
        """Pop-and-validate until a live node is found (discarding any stale
        entries along the way), then perform exactly one real expansion.
        Returns None if the proc's heap drains to empty without ever finding
        a live node -- the proc is exhausted."""
        heap = self.heap
        while heap:
            _f, _neg_g, _tie, node = heapq.heappop(heap)
            if node.g > best_g.get(node.key, _INF):
                self.stale_skips += 1
                continue  # superseded by a better path some proc already found

            if problem.is_goal(node.state):
                self.active = bool(heap)
                return _ExpandOutcome(node=node, is_goal=True)

            self.expansions += 1
            for action, next_state, cost in problem.successors(node.state):
                next_key = state_key(next_state)
                new_g = node.g + cost
                if new_g < best_g.get(next_key, _INF):
                    best_g[next_key] = new_g
                    h = problem.heuristic(next_state)
                    f_child = new_g + h
                    if node.f > f_child:
                        f_child = node.f  # pathmax
                    child = _Node(
                        state=next_state,
                        key=next_key,
                        g=new_g,
                        h=h,
                        f=f_child,
                        F=f_child,
                        parent=node,
                        action=action,
                        depth=node.depth + 1,
                    )
                    heapq.heappush(heap, (child.f, -child.g, next(counter), child))
                    tracker.nodes_generated += 1

            self.active = bool(heap)
            return _ExpandOutcome(node=node, is_goal=False)

        self.active = False
        return None


def _build_procs(phase1: _Phase1Result) -> List[_Proc]:
    """Turn every live (non-stale) Phase-1 frontier node into its own proc."""
    procs: List[_Proc] = []
    for node in _live_frontier_nodes_sorted(phase1):
        pid = len(procs)
        procs.append(_Proc(proc_id=pid, heap=[(node.f, -node.g, next(phase1.counter), node)]))
    return procs


def _live_frontier_nodes_sorted(phase1: _Phase1Result) -> List[_Node]:
    """Live Phase-1 frontier nodes in a deterministic order (by state key) so
    two procs never share a root state and proc ids are reproducible."""
    nodes = sorted(
        (n for n in _live_frontier_nodes(phase1)),
        key=lambda n: n.key,
    )
    # Two frontier nodes with the same state (different paths, equal g) would
    # become duplicate procs; keep the first and drop the rest.
    seen: set = set()
    unique: List[_Node] = []
    for n in nodes:
        if n.key in seen:
            continue
        seen.add(n.key)
        unique.append(n)
    return unique


class MPBFS(SearchAlgorithm):
    """Multi-Path Best-First Search: a Phase-1 best-first frontier build
    followed by `num_procs` independent best-first procs multiplexed by a
    pluggable scheduler. Single-threaded; "proc" is a logical search process,
    not an OS thread/process."""

    name = "mp-bfs"

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
        self.name = f"mp-bfs-{scheduler}"

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
        result.reexpansions = phase1_stale + sum(p.stale_skips for p in procs)

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
