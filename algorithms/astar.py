"""A* search with lazy successor generation (one successor per pop) and a
binary heap open list, matching SMA*'s generation pattern for fairer
comparison."""
from __future__ import annotations

import heapq
import itertools
from typing import Any, Dict, Iterator, List, Optional, Tuple

from domains.base import SearchProblem

from ._run_utils import MemoryLimitError, NodeLimitError, RunTracker
from .base import SearchAlgorithm, SearchLimits, SearchResult


class AStar(SearchAlgorithm):
    """A* with lazy successor generation — one successor per heap pop, matching
    SMA*'s pattern so both algorithms do comparable work per expansion."""

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
        counter = itertools.count()

        # open_heap entries: (f, -g, tie_break, g, state). Ties on f prefer
        # larger g (deeper / more-expanded-looking nodes).
        open_heap: List[Tuple[float, float, int, float, Any]] = []
        heapq.heappush(open_heap, (problem.heuristic(start), -0.0, next(counter), 0.0, start))
        tracker.nodes_generated = 1

        best_g: Dict[Any, float] = {start_key: 0.0}
        came_from: Dict[Any, Tuple[Any, Any, Any]] = {}  # key -> (action, parent_state, parent_key)

        # Lazy generation: one successor iterator per expanded node.
        successor_iters: Dict[Any, Iterator] = {}
        fully_expanded: set = set()

        nodes_expanded = 0
        max_frontier_size = 1
        reexpansions = 0

        try:
            while open_heap:
                tracker.check_limits()

                f, _neg_g, _tie, g, state = heapq.heappop(open_heap)
                key = problem.state_key(state)

                if g > best_g.get(key, float("inf")):
                    continue  # stale entry — a better path was already found

                if key in fully_expanded:
                    reexpansions += 1
                    continue

                if problem.is_goal(state):
                    result.success = True
                    result.solution_cost = g
                    result.solution_actions = self._reconstruct(came_from, key)
                    break

                # Lazy successor generation — create iterator on first pop.
                if key not in successor_iters:
                    successor_iters[key] = iter(problem.successors(state))
                    nodes_expanded += 1

                # Generate ONE successor.
                try:
                    action, next_state, cost = next(successor_iters[key])
                except StopIteration:
                    # All successors generated — node is fully expanded.
                    fully_expanded.add(key)
                    del successor_iters[key]
                    continue

                next_key = problem.state_key(next_state)
                new_g = g + cost
                if new_g < best_g.get(next_key, float("inf")):
                    best_g[next_key] = new_g
                    came_from[next_key] = (action, state, key)
                    h = problem.heuristic(next_state)
                    heapq.heappush(open_heap, (new_g + h, -new_g, next(counter), new_g, next_state))
                    tracker.nodes_generated += 1

                # Re-push parent so it can generate its next successor.
                if key in successor_iters:
                    heapq.heappush(open_heap, (f, _neg_g, _tie, g, state))

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
