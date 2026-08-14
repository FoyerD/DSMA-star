"""RBFS: Recursive Best-First Search.

A recursive implementation of the standard RBFS algorithm (Korf, 1993).
Functionally identical to ILBFS — visits the same nodes in the same order —
but uses the recursion stack instead of iterative Collapse/Restore macros.

Memory complexity: O(b * d) via the recursion stack.

Reference pseudocode (from user-provided source):

    RBFS(n, B)
    1. if n is a goal
    2.   solution <- n; exit()
    3. C <- expand(n)
    4. if C is empty, return infinity
    5. for each child ni in C
    6.   if f(n) < F(n) then F(ni) <- max(F(n), f(ni))
    7.   else F(ni) <- f(ni)
    8. (n1, n2) <- bestF(C)
    9. while (F(n1) <= B and F(n1) < infinity)
    10.  F(n1) <- RBFS(n1, min(B, F(n2)))
    11.  (n1, n2) <- bestF(C)
    12. return F(n1)
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from domains.base import SearchProblem

from ._run_utils import MemoryLimitError, NodeLimitError, RunTracker
from .base import SearchAlgorithm, SearchLimits, SearchResult

_INF = float("inf")


@dataclass(slots=True)
class _Node:
    state: Any
    g: float
    h: float
    f: float       # g + h (static, never changes)
    F: float       # stored/backed-up value (== f initially, updated by RBFS)
    parent: Optional[_Node]
    action: Any
    children: Dict[Any, _Node] = field(default_factory=dict)
    depth: int = 0


class RBFS(SearchAlgorithm):
    """Recursive Best-First Search.

    Functionally identical to ILBFS, uses the recursion stack for O(b*d)
    memory instead of iterative Collapse/Restore macros.
    """

    name = "rbfs"

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

        nodes_expanded = 0
        nodes_generated = 1
        max_depth_reached = 0
        max_frontier_size = 0
        goal_found = False
        # Backed-up subtrees: every non-goal return from a child _rbfs() call
        # means that child's subtree was explored, its F backed up, and the
        # parent abandoned it for another child. Recursive RBFS never *deletes*
        # children (no literal Collapse), so this is the closest analog to
        # ILBFS's collapse count -- both count subtree-abandonment events.
        collapses = 0
        nodes: Dict[Any, _Node] = {state_key(start): root}

        # Raise the recursion limit so depth-60+ instances don't hit
        # Python's default 1000 ceiling.  Restored in the finally block.
        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(max(old_limit, 10_000))

        def _rbfs(node: _Node, bound: float) -> float:
            nonlocal nodes_expanded, nodes_generated, max_depth_reached
            nonlocal max_frontier_size, goal_found, collapses

            tracker.check_limits()
            if goal_found:
                return _INF

            max_depth_reached = max(max_depth_reached, node.depth)

            # Lines 1-2: goal check
            if problem.is_goal(node.state):
                result.success = True
                result.solution_cost = node.g
                result.solution_actions = self._reconstruct(node)
                goal_found = True
                return 0.0

            # Line 3: expand(n) -- generate children (only once per node)
            if not node.children:
                nodes_expanded += 1
                for action, next_state, cost in problem.successors(node.state):
                    next_key = state_key(next_state)
                    new_g = node.g + cost

                    existing = nodes.get(next_key)
                    if existing is not None and existing.g <= new_g:
                        continue

                    tracker.nodes_generated += 1
                    nodes_generated += 1

                    next_h = problem.heuristic(next_state)
                    next_f = new_g + next_h

                    # Lines 5-7: F-value propagation (conditional, per standard RBFS pseudocode)
                    if node.F > node.f and node.F > next_f:
                        next_F = node.F
                    else:
                        next_F = next_f

                    child = _Node(
                        state=next_state,
                        g=new_g,
                        h=next_h,
                        f=next_f,
                        F=next_F,
                        parent=node,
                        action=action,
                        depth=node.depth + 1,
                    )
                    node.children[next_key] = child
                    nodes[next_key] = child

            children_list = list(node.children.values())

            # Line 4: if C is empty, return infinity
            if not children_list:
                return _INF

            max_frontier_size = max(max_frontier_size, len(children_list))

            # Line 8: (n1, n2) <- bestF(C)
            children_list.sort(key=lambda c: c.F)
            best = children_list[0]
            second = children_list[1] if len(children_list) > 1 else _sentinel_node

            # Lines 9-11: while loop
            while best.F <= bound and best.F < _INF:
                tracker.check_limits()
                if goal_found:
                    return _INF

                # Line 10: recursive call
                best.F = _rbfs(best, min(bound, second.F))
                if not goal_found:
                    collapses += 1  # child's subtree explored and backed up

                if goal_found:
                    return 0.0

                # Line 11: re-find best and second-best
                children_list.sort(key=lambda c: c.F)
                best = children_list[0]
                second = (
                    children_list[1] if len(children_list) > 1 else _sentinel_node
                )

            # Line 12: return F(n1)
            return best.F

        try:
            root.F = _rbfs(root, _INF)
        except RecursionError:
            result.stack_exhausted = True
            result.error_message = "recursion limit exceeded"
        except NodeLimitError:
            result.node_limit_reached = True
            result.error_message = "max_nodes safety valve exceeded"
        except MemoryLimitError:
            result.memory_limit_reached = True
            result.error_message = "real memory ceiling exceeded"
        finally:
            sys.setrecursionlimit(old_limit)
            result.peak_memory_mb = tracker.stop()
            if result.peak_memory_mb > limits.max_memory_mb:
                result.memory_limit_reached = True

        result.runtime_seconds = tracker.elapsed()
        result.nodes_expanded = nodes_expanded
        result.nodes_generated = tracker.nodes_generated
        result.max_frontier_size = max_frontier_size
        result.max_depth_reached = max_depth_reached
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


# Sentinel used when a node has only one child (second-best F = infinity).
_sentinel_node = _Node(
    state=None, g=_INF, h=_INF, f=_INF, F=_INF,
    parent=None, action=None, depth=0,
)
