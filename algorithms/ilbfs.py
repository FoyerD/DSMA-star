"""ILBFS: Iterative Linear Best-First Search.

A non-recursive, iterative implementation based on the algorithm described
in docs/ilbfs.md.  ILBFS is functionally identical to Recursive Best-First
Search (RBFS) -- it visits the same nodes in the same order -- but replaces
recursive backtracking with an iterative framework using Collapse and
Restore macros.

Memory complexity: O(b * d) via the Principal Branch Invariant.

Heap tie-breaking: heap entries use ``(F + collapse_count, -depth, state_key)``
so that when F values are tied the deeper node is preferred (matching the
depth-first expansion pattern that makes d=24 efficient).  Nodes that have
been collapsed (children deleted) accumulate ``collapse_count``, which
breaks oscillation on hard instances like d=28 where repeated re-expansion
of the same deep node would otherwise form an infinite cycle.  This
combines the strengths of both ``-depth`` (good for d=24) and ``depth``
(good for d=28) by degrading collapsed nodes until a different branch is
explored.  See docs/ilbfs.md section 8.

Memory layout: the heap stores state_keys (not _Node references) so that
collapsed nodes can be garbage collected immediately.  When a node is popped,
its _Node is looked up from the ``nodes`` dict; stale entries (deleted from
``nodes`` or whose F value was updated by collapse) are detected and skipped.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from domains.base import SearchProblem

from ._run_utils import MemoryLimitError, NodeLimitError, RunTracker
from .base import SearchAlgorithm, SearchLimits, SearchResult


@dataclass(slots=True)
class _Node:
    state: Any
    g: float
    h: float
    f: float       # g + h (static, never changes)
    F: float       # stored/backed-up value (== f initially, updated by Collapse/Restore)
    parent: Optional[_Node]
    action: Any
    children: Dict[Any, _Node] = field(default_factory=dict)
    depth: int = 0
    collapse_count: int = 0  # incremented each time children are deleted


class ILBFS(SearchAlgorithm):
    """Iterative Linear Best-First Search.

    Functionally identical to RBFS, non-recursive with O(b*d) memory
    via Collapse/Restore macros.
    """

    name = "ilbfs"

    def search(self, problem: SearchProblem, limits: SearchLimits) -> SearchResult:
        result = SearchResult(
            algorithm_name=self.name,
            domain_name=getattr(problem, "name", "unknown"),
            instance_id="",
        )
        tracker = RunTracker.start(limits.max_nodes, limits.max_memory_mb)

        start = problem.initial_state
        start_h = problem.heuristic(start)
        state_key = problem.state_key

        root = _Node(
            state=start,
            g=0.0,
            h=start_h,
            f=start_h,
            F=start_h,
            parent=None,
            action=None,
            depth=0,
        )

        open_heap: List[Tuple[float, Any]] = []
        # Tie-breaking: (F + collapse_count, -depth, state_key) — depth-first
        # with oscillation penalty.  Store state_key (not _Node) so collapsed
        # nodes can be GC'd.
        root_key = state_key(start)
        heapq.heappush(open_heap, (root.F + root.collapse_count, -root.depth, root_key))

        nodes: Dict[Any, _Node] = {state_key(start): root}

        tracker.nodes_generated = 1
        nodes_expanded = 0
        reexpansions = 0
        collapses = 0  # nodes whose children were deleted by a Collapse (backed up)
        max_frontier_size = 1
        max_depth_reached = 0
        oldbest: Optional[_Node] = None

        try:
            while open_heap:
                tracker.check_limits()

                # Step 4: best = extract min(OPEN)
                popped_F_pen, _popped_depth, popped_key = heapq.heappop(open_heap)
                best = nodes.get(popped_key)

                # Stale entry: node was collapsed (deleted from nodes) or its
                # F value was updated by collapse (doesn't match popped F).
                if best is None or best.F + best.collapse_count != popped_F_pen:
                    continue

                max_depth_reached = max(max_depth_reached, best.depth)

                # Step 5: if goal(best) then exit
                if problem.is_goal(best.state):
                    result.success = True
                    result.solution_cost = best.g
                    result.solution_actions = self._reconstruct(best)
                    break

                # Steps 7-11: while (oldbest != best.parent) — Collapse loop
                collapsed = False
                while oldbest is not None and oldbest != best.parent:
                    collapsed = True
                    if oldbest.children:
                        oldbest.F = min(
                            child.F for child in oldbest.children.values()
                        )
                    else:
                        oldbest.F = oldbest.f
                    oldbest.collapse_count += 1
                    collapses += 1
                    heapq.heappush(
                        open_heap,
                        (oldbest.F + oldbest.collapse_count, -oldbest.depth, state_key(oldbest.state)),
                    )
                    for ck in list(oldbest.children.keys()):
                        if ck in nodes and nodes[ck] is oldbest.children[ck]:
                            del nodes[ck]
                    oldbest.children.clear()
                    oldbest = oldbest.parent

                # Line 79 of pseudocode: "Delete all children of oldbest
                # from OPEN and TREE".  The loop above deletes from TREE
                # (nodes dict).  Here we purge the corresponding stale
                # entries from OPEN by rebuilding the heap from the live
                # nodes dict.  Cost is O(|nodes|) = O(b*d) per collapse.
                if collapsed:
                    open_heap = [
                        (node.F + node.collapse_count, -node.depth, state_key(node.state))
                        for node in nodes.values()
                    ]
                    heapq.heapify(open_heap)

                if best.F > best.f:
                    reexpansions += 1

                # Steps 12-16: foreach child C of best — Expand / Restore
                nodes_expanded += 1
                for action, next_state, cost in problem.successors(best.state):
                    next_key = state_key(next_state)
                    new_g = best.g + cost

                    existing = nodes.get(next_key)
                    if existing is not None and existing.g <= new_g:
                        continue

                    tracker.nodes_generated += 1
                    next_h = problem.heuristic(next_state)
                    next_f = new_g + next_h

                    # Step 13: F(C) <- f(C)
                    next_F = next_f

                    # Steps 14-15: pathmax — Restore propagation rule
                    if best.F > best.f and best.F > next_F:
                        next_F = best.F

                    child = _Node(
                        state=next_state,
                        g=new_g,
                        h=next_h,
                        f=next_f,
                        F=next_F,
                        parent=best,
                        action=action,
                        depth=best.depth + 1,
                    )

                    # Step 16: Insert C to OPEN and TREE
                    best.children[next_key] = child
                    nodes[next_key] = child
                    heapq.heappush(
                        open_heap,
                        (child.F + child.collapse_count, -child.depth, next_key),
                    )

                # Step 17: oldbest <- best
                oldbest = best
                max_frontier_size = max(max_frontier_size, len(open_heap))

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

        result.runtime_seconds = tracker.elapsed()
        result.nodes_expanded = nodes_expanded
        result.nodes_generated = tracker.nodes_generated
        result.max_frontier_size = max_frontier_size
        result.max_depth_reached = max_depth_reached
        result.reexpansions = reexpansions
        result.total_collapses = collapses
        return result

    @staticmethod
    def _reconstruct(node: _Node) -> List[Any]:
        actions: List[Any] = []
        current = node
        while current.parent is not None:
            actions.append(current.action)
            current = current.parent
        actions.reverse()
        return actions
