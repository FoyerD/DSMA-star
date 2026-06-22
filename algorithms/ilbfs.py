"""ILBFS: Iterative Lengthening (cost-bound) Best-First Search.

ASSUMPTION / DOCUMENTED INTERPRETATION:
"ILBFS" is not a single universally standardized algorithm name. Here we
implement it as **Iterative Lengthening Search over the f-cost bound**,
in the same spirit as IDA* (Iterative Deepening A*): a depth-first
recursive search that prunes any node with f = g + h > bound, and between
iterations raises `bound` to the smallest f-value that exceeded the
previous bound. The "BFS" in the name reflects that each bounded pass
explores in increasing order of f-cost layers (cost-bounded search), not
that it literally uses a FIFO breadth-first queue.

This module is intentionally isolated behind the `ILBFS` class so the
interpretation can be swapped out later (e.g. for a literal breadth-first
variant) without touching the rest of the codebase.
"""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

from domains.base import SearchProblem

from ._run_utils import NodeLimitError, RunTracker, TimeoutError_
from .base import SearchAlgorithm, SearchLimits, SearchResult

_INF = float("inf")


class ILBFS(SearchAlgorithm):
    """Iterative cost-bound (IDA*-style) search. See module docstring for the chosen semantics."""

    name = "ilbfs"

    def search(self, problem: SearchProblem, limits: SearchLimits) -> SearchResult:
        result = SearchResult(
            algorithm_name=self.name,
            domain_name=getattr(problem, "name", "unknown"),
            instance_id="",
        )
        tracker = RunTracker.start(limits.timeout_seconds, limits.max_nodes)

        start = problem.initial_state
        bound = problem.heuristic(start)
        nodes_expanded = 0
        max_frontier_size = 0  # current recursion-stack depth, the "frontier" of a DFS-style search
        max_depth_reached = 0

        try:
            while True:
                tracker.check_timeout()
                path: List[Tuple[Any, Any]] = []  # (action, state) from root, root excluded
                visited_on_path = {problem.state_hash(start)}
                counters = {"expanded": 0}
                outcome = self._bounded_dfs(
                    problem,
                    state=start,
                    g=0.0,
                    bound=bound,
                    path=path,
                    visited_on_path=visited_on_path,
                    tracker=tracker,
                    counters=counters,
                )
                nodes_expanded += counters["expanded"]
                max_frontier_size = max(max_frontier_size, outcome.max_depth_this_pass)
                max_depth_reached = max(max_depth_reached, outcome.max_depth_this_pass)

                if outcome.found:
                    result.success = True
                    result.solution_cost = outcome.solution_cost
                    result.solution_actions = [action for action, _state in path]
                    break
                if outcome.next_bound == _INF:
                    break  # search space exhausted, no solution exists
                bound = outcome.next_bound
        except TimeoutError_:
            result.timeout = True
        except NodeLimitError:
            result.memory_limit_reached = True
            result.error_message = "max_nodes exceeded"
        finally:
            result.peak_memory_mb = tracker.stop()
            if result.peak_memory_mb > limits.max_memory_mb:
                result.memory_limit_reached = True

        result.runtime_seconds = tracker.elapsed()
        result.nodes_expanded = nodes_expanded
        result.nodes_generated = tracker.nodes_generated
        result.max_frontier_size = max_frontier_size
        result.max_depth_reached = max_depth_reached
        result.reexpansions = 0  # iterative lengthening intentionally re-expands every pass; not tracked separately
        return result

    def _bounded_dfs(
        self,
        problem: SearchProblem,
        state: Any,
        g: float,
        bound: float,
        path: List[Tuple[Any, Any]],
        visited_on_path: set,
        tracker: RunTracker,
        counters: dict,
    ) -> "_PassOutcome":
        tracker.check_timeout()
        tracker.check_node_limit()

        f = g + problem.heuristic(state)
        if f > bound:
            return _PassOutcome(found=False, next_bound=f, max_depth_this_pass=len(path))

        if problem.is_goal(state):
            return _PassOutcome(found=True, next_bound=_INF, solution_cost=g, max_depth_this_pass=len(path))

        counters["expanded"] += 1
        smallest_exceeding = _INF
        deepest = len(path)

        for action, next_state, cost in problem.successors(state):
            next_key = problem.state_hash(next_state)
            if next_key in visited_on_path:
                continue  # avoid trivial cycles within the current DFS path
            tracker.nodes_generated += 1

            path.append((action, next_state))
            visited_on_path.add(next_key)

            sub_outcome = self._bounded_dfs(
                problem, next_state, g + cost, bound, path, visited_on_path, tracker, counters
            )

            if sub_outcome.found:
                return sub_outcome

            visited_on_path.discard(next_key)
            path.pop()
            smallest_exceeding = min(smallest_exceeding, sub_outcome.next_bound)
            deepest = max(deepest, sub_outcome.max_depth_this_pass)

        return _PassOutcome(found=False, next_bound=smallest_exceeding, max_depth_this_pass=deepest)


class _PassOutcome:
    __slots__ = ("found", "next_bound", "solution_cost", "max_depth_this_pass")

    def __init__(
        self,
        found: bool,
        next_bound: float,
        max_depth_this_pass: int,
        solution_cost: Optional[float] = None,
    ) -> None:
        self.found = found
        self.next_bound = next_bound
        self.solution_cost = solution_cost
        self.max_depth_this_pass = max_depth_this_pass
