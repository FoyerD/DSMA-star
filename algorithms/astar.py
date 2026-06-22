"""Classic A* search with a binary heap open list and a closed/best-g dictionary."""
from __future__ import annotations

import heapq
import itertools
from typing import Any, Dict, List, Optional, Tuple

from domains.base import SearchProblem

from ._run_utils import NodeLimitError, RunTracker, TimeoutError_
from .base import SearchAlgorithm, SearchLimits, SearchResult


class AStar(SearchAlgorithm):
    """Standard A* using f = g + h, optimal when the heuristic is admissible."""

    name = "astar"

    def search(self, problem: SearchProblem, limits: SearchLimits) -> SearchResult:
        result = SearchResult(
            algorithm_name=self.name,
            domain_name=getattr(problem, "name", "unknown"),
            instance_id="",
        )
        tracker = RunTracker.start(limits.timeout_seconds, limits.max_nodes)

        start = problem.initial_state
        start_key = problem.state_hash(start)
        counter = itertools.count()  # tie-breaker so heap never compares states directly

        # open_heap entries: (f, tie_break, g, state)
        open_heap: List[Tuple[float, int, float, Any]] = []
        heapq.heappush(open_heap, (problem.heuristic(start), next(counter), 0.0, start))
        tracker.nodes_generated = 1

        best_g: Dict[Any, float] = {start_key: 0.0}
        came_from: Dict[Any, Tuple[Any, Any]] = {}  # key -> (action, parent_state)
        closed: set = set()

        nodes_expanded = 0
        max_frontier_size = 1
        reexpansions = 0

        try:
            while open_heap:
                tracker.check_timeout()
                tracker.check_node_limit()

                f, _, g, state = heapq.heappop(open_heap)
                key = problem.state_hash(state)

                if g > best_g.get(key, float("inf")):
                    continue  # stale entry, a better path was already found
                if key in closed:
                    reexpansions += 1
                    continue
                closed.add(key)
                nodes_expanded += 1

                if problem.is_goal(state):
                    result.success = True
                    result.solution_cost = g
                    result.solution_actions = self._reconstruct(came_from, key)
                    break

                for action, next_state, cost in problem.successors(state):
                    next_key = problem.state_hash(next_state)
                    new_g = g + cost
                    if new_g < best_g.get(next_key, float("inf")):
                        best_g[next_key] = new_g
                        came_from[next_key] = (action, state, key)
                        h = problem.heuristic(next_state)
                        heapq.heappush(open_heap, (new_g + h, next(counter), new_g, next_state))
                        tracker.nodes_generated += 1

                max_frontier_size = max(max_frontier_size, len(open_heap))
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
        result.max_depth_reached = len(result.solution_actions) if result.success else nodes_expanded
        result.reexpansions = reexpansions
        return result

    @staticmethod
    def _reconstruct(came_from: Dict[Any, Tuple[Any, Any, Any]], goal_key: Any) -> List[Any]:
        actions: List[Any] = []
        key: Optional[Any] = goal_key
        while key in came_from:
            action, _parent_state, parent_key = came_from[key]
            actions.append(action)
            key = parent_key
        actions.reverse()
        return actions
