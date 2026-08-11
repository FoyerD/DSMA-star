"""mp-rbfs: Multi-Path RBFS.

Phase 1 runs an ordinary best-first search (f = g + h) from the root until
OPEN holds at least `num_procs` nodes, always finishing every child of a
node it starts expanding (the frontier stays a complete cut of the search
tree, never a partially-expanded node -- see `_run_phase1`). Phase 2 turns
every surviving Phase-1 frontier node into an independent "proc": a private
best-first search restricted to that node's subtree. A pluggable
`Scheduler` (see `mp_rbfs_schedulers.py`) decides which proc receives the
next single-node expansion; control returns to the scheduler after every
expansion. All procs share one global `best_g` dict for duplicate
detection, so a state discovered by one proc with a better g invalidates
(but does not need to be eagerly purged from) whichever other proc's heap
is still holding the worse entry -- stale entries are detected lazily at
pop time. The first proc to pop a goal state wins and the whole run stops,
so mp-rbfs is intentionally allowed to return a suboptimal solution;
Best-First scheduling tends closest to plain best-first search, Round-Robin
and Proportional trade optimality for fairness/robustness against
starvation. See docs/mp_rbfs.md for the full design.
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
from .mp_rbfs_schedulers import build_scheduler

_INF = float("inf")


@dataclass(slots=True)
class _Node:
    """Minimal node record.

    No `children` dict (unlike ILBFS, a proc never revisits a node's
    children after generating them once -- there is no collapse to undo).
    No separate `h` field (only needed transiently while computing `f`). No
    `depth` field (`g` already doubles as depth for this domain's unit
    action costs, so a separate counter would be redundant).
    """

    state: Any
    key: Any
    g: float
    f: float  # g + h, pathmax-adjusted: max(parent.f, g + h)
    parent: Optional["_Node"]
    action: Any


@dataclass(slots=True)
class _ExpandOutcome:
    node: _Node
    is_goal: bool


@dataclass(slots=True)
class _Proc:
    """One independent best-first search restricted to a Phase-1 frontier
    node's subtree.

    Owns a private OPEN heap (entries are ``(f, -g, counter, node)`` tuples,
    matching the tie-break convention used elsewhere in this project:
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
        # May reflect a stale (superseded) entry -- see module docstring.
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
        """Pop-and-validate until a live node is found (discarding any
        stale entries along the way), then perform exactly one real
        expansion. Returns None if the proc's heap drains to empty without
        ever finding a live node -- the proc is exhausted."""
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
                    child = _Node(state=next_state, key=next_key, g=new_g, f=f_child, parent=node, action=action)
                    heapq.heappush(heap, (child.f, -child.g, next(counter), child))
                    tracker.nodes_generated += 1

            self.active = bool(heap)
            return _ExpandOutcome(node=node, is_goal=False)

        self.active = False
        return None


@dataclass(slots=True)
class _Phase1Result:
    goal_node: Optional[_Node]
    open_heap: List[Tuple[float, float, int, _Node]]
    best_g: Dict[Any, float]
    counter: "itertools.count[int]"
    expanded: int
    stale: int
    max_frontier_size: int
    max_depth_reached: int


def _run_phase1(problem: SearchProblem, num_procs: int, tracker: RunTracker) -> _Phase1Result:
    """Ordinary best-first search from the root until OPEN has >= num_procs
    nodes. Never stops mid-expansion: the entire successors loop for a node
    always completes before the frontier-size condition is re-checked, so
    the final frontier may exceed num_procs but is always a complete cut."""
    state_key = problem.state_key
    counter: "itertools.count[int]" = itertools.count()

    start = problem.initial_state
    start_key = state_key(start)
    root = _Node(state=start, key=start_key, g=0.0, f=problem.heuristic(start), parent=None, action=None)

    best_g: Dict[Any, float] = {start_key: 0.0}
    tracker.nodes_generated = 1
    open_heap: List[Tuple[float, float, int, _Node]] = [(root.f, -root.g, next(counter), root)]

    goal_node: Optional[_Node] = None
    expanded = 0
    stale = 0
    max_frontier_size = 1
    max_depth_reached = 0

    while open_heap and len(open_heap) < num_procs:
        tracker.check_limits()
        _f, _neg_g, _tie, node = heapq.heappop(open_heap)
        if node.g > best_g.get(node.key, _INF):
            stale += 1
            continue  # stale: a better path to this state was already found

        max_depth_reached = max(max_depth_reached, int(node.g))
        if problem.is_goal(node.state):
            goal_node = node
            break

        expanded += 1
        for action, next_state, cost in problem.successors(node.state):
            next_key = state_key(next_state)
            new_g = node.g + cost
            if new_g < best_g.get(next_key, _INF):
                best_g[next_key] = new_g
                h = problem.heuristic(next_state)
                f_child = new_g + h
                if node.f > f_child:
                    f_child = node.f  # pathmax
                child = _Node(state=next_state, key=next_key, g=new_g, f=f_child, parent=node, action=action)
                heapq.heappush(open_heap, (child.f, -child.g, next(counter), child))
                tracker.nodes_generated += 1

        max_frontier_size = max(max_frontier_size, len(open_heap))

    return _Phase1Result(
        goal_node=goal_node,
        open_heap=open_heap,
        best_g=best_g,
        counter=counter,
        expanded=expanded,
        stale=stale,
        max_frontier_size=max_frontier_size,
        max_depth_reached=max_depth_reached,
    )


def _build_procs(phase1: _Phase1Result) -> List[_Proc]:
    """Turn every live (non-stale) Phase-1 frontier node into its own proc."""
    procs: List[_Proc] = []
    for _f, _neg_g, _tie, node in phase1.open_heap:
        if node.g > phase1.best_g.get(node.key, _INF):
            continue  # superseded during phase 1, not a live frontier node
        pid = len(procs)
        procs.append(_Proc(proc_id=pid, heap=[(node.f, -node.g, next(phase1.counter), node)]))
    return procs


def _reconstruct(node: _Node) -> List[Any]:
    actions: List[Any] = []
    current = node
    while current.parent is not None:
        actions.append(current.action)
        current = current.parent
    actions.reverse()
    return actions


class MPRBFS(SearchAlgorithm):
    """Multi-Path RBFS: a Phase-1 best-first frontier build followed by
    `num_procs` independent best-first procs multiplexed by a pluggable
    scheduler. Single-threaded; "proc" is a logical search process, not an
    OS thread/process."""

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
