"""Shared infrastructure for the multi-path algorithms: mp-bfs and mp-rbfs.

Both algorithms share the same two-phase skeleton:

- **Phase 1 (the fork):** an ordinary best-first expansion (f = g + h) from
  the root until the open list holds at least `num_procs` nodes. One rule is
  mandatory: never stop mid-expansion -- a node's full sibling set is always
  generated before the frontier-size condition is re-checked, so the final
  frontier is a complete cut of the search tree ("don't miss anything").
- **Phase 2 (the procs):** every live Phase-1 frontier node becomes an
  independent "proc" that searches that node's subtree. A pluggable
  `Scheduler` (see `mp_schedulers.py`) decides which proc gets the next
  single-node expansion; control returns to the scheduler after every
  expansion. All procs share one permanent `best_g` dict (state -> best known
  g) for duplicate detection, so a state discovered by one proc with a better
  g invalidates (but does not need to be eagerly purged from) whichever other
  proc's heap still holds the worse entry -- stale entries are detected lazily
  at pop time.

The two algorithms differ only in what a proc does inside its subtree:

- **mp-bfs** (`mp_bfs.py`): a plain best-first search -- the proc keeps its
  whole generated subtree in its open heap until exhausted.
- **mp-rbfs** (`mp_rbfs.py`): a genuine RBFS -- the proc runs the iterative
  Collapse/Restore loop (the same one that powers `ilbfs.py`), backing up F
  values and deleting collapsed subtrees, so each proc's live memory is
  O(b * d).

Everything in this module is deliberately algorithm-agnostic.
"""
from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from domains.base import SearchProblem

_INF = float("inf")


@dataclass(slots=True)
class _Node:
    """A node in a Phase-1 or proc subtree.

    Carries everything both algorithms need: the static cost pair (g, h), the
    static f = g + h, the stored/backed-up F (only mp-rbfs's collapse loop
    ever makes F != f), a `children` dict (mp-rbfs collapse bookkeeping; left
    empty by mp-bfs), and a `collapse_count` oscillation penalty (mp-rbfs).
    """

    state: Any
    key: Any
    g: float
    h: float
    f: float  # g + h, static, never changes
    F: float  # stored/backed-up value (== f initially)
    parent: Optional["_Node"]
    action: Any
    children: Dict[Any, "_Node"] = field(default_factory=dict)
    depth: int = 0
    collapse_count: int = 0


@dataclass(slots=True)
class _ExpandOutcome:
    node: _Node
    is_goal: bool


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


def _run_phase1(problem: SearchProblem, num_procs: int, tracker) -> _Phase1Result:
    """Best-first expansion from the root until OPEN holds >= num_procs nodes.

    Never stops mid-expansion: the entire successors loop for a node always
    completes before the frontier-size condition is re-checked, so the final
    frontier may exceed num_procs but is always a complete cut.
    """
    state_key = problem.state_key
    counter: "itertools.count[int]" = itertools.count()

    start = problem.initial_state
    start_key = state_key(start)
    start_h = problem.heuristic(start)
    root = _Node(
        state=start,
        key=start_key,
        g=0.0,
        h=start_h,
        f=start_h,
        F=start_h,
        parent=None,
        action=None,
        depth=0,
    )

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


def _live_frontier_nodes(phase1: _Phase1Result) -> List[_Node]:
    """The Phase-1 frontier nodes that are still live (not superseded during
    phase 1). Each becomes the root of one proc."""
    nodes: List[_Node] = []
    for _f, _neg_g, _tie, node in phase1.open_heap:
        if node.g > phase1.best_g.get(node.key, _INF):
            continue  # superseded during phase 1, not a live frontier node
        nodes.append(node)
    return nodes


def _reconstruct(node: _Node) -> List[Any]:
    actions: List[Any] = []
    current = node
    while current.parent is not None:
        actions.append(current.action)
        current = current.parent
    actions.reverse()
    return actions
