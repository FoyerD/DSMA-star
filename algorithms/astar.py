"""Classic A* search with a binary heap open list and a closed/best-g dictionary."""
from __future__ import annotations

import heapq
import itertools
from typing import Any, Dict, List, Optional, Tuple

from domains.base import SearchProblem

from ._run_utils import MemoryLimitError, NodeLimitError, RunTracker
from .base import SearchAlgorithm, SearchLimits, SearchResult


class AStar(SearchAlgorithm):
    """Standard graph-search A* using f = g + h, optimal when h is admissible."""

    name = "astar"

    def search(self, problem: SearchProblem, limits: SearchLimits) -> SearchResult:
        result = SearchResult(
            algorithm_name=self.name,
            domain_name=getattr(problem, "name", "unknown"),
            instance_id="",
        )
        tracker = RunTracker.start(limits.max_nodes, limits.max_memory_mb)

        start = problem.initial_state
        start_key = problem.state_key(start)
        counter = itertools.count()  # tie-breaker so heap never compares states directly

        # open_heap entries: (f, -g, tie_break, g, state). Ties on f prefer
        # larger g (deeper / more-expanded-looking nodes), as specified.
        open_heap: List[Tuple[float, float, int, float, Any]] = []
        heapq.heappush(open_heap, (problem.heuristic(start), -0.0, next(counter), 0.0, start))
        tracker.nodes_generated = 1

        best_g: Dict[Any, float] = {start_key: 0.0}
        came_from: Dict[Any, Tuple[Any, Any, Any]] = {}  # key -> (action, parent_state, parent_key)
        closed: set = set()

        nodes_expanded = 0
        max_frontier_size = 1
        reexpansions = 0

        try:
            while open_heap:
                tracker.check_limits()

                # Periodically rebuild the heap to purge stale entries.
                live_count = len(best_g) - len(closed)
                if len(open_heap) > max(1000, 3 * live_count):
                    seen = set()
                    fresh = []
                    for entry in open_heap:
                        f, neg_g, tie, g, state = entry
                        key = problem.state_key(state)
                        if key not in seen and key not in closed and g == best_g.get(key):
                            seen.add(key)
                            fresh.append(entry)
                    open_heap[:] = fresh
                    heapq.heapify(open_heap)

                f, _neg_g, _tie, g, state = heapq.heappop(open_heap)
                key = problem.state_key(state)

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
                    next_key = problem.state_key(next_state)
                    new_g = g + cost
                    if new_g < best_g.get(next_key, float("inf")):
                        best_g[next_key] = new_g
                        came_from[next_key] = (action, state, key)
                        h = problem.heuristic(next_state)
                        heapq.heappush(open_heap, (new_g + h, -new_g, next(counter), new_g, next_state))
                        tracker.nodes_generated += 1

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
