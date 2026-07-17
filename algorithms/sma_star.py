"""Simplified Memory-Bounded A* (SMA*).

LIMITATIONS / DOCUMENTED ASSUMPTIONS (this is a teaching-grade simplification,
not a textbook-perfect SMA*):

1. Global duplicate suppression, not a pure tree search. Each state occupies
   at most one node (keyed by `problem.state_key()`). If a successor's state
   is already present anywhere in the in-memory tree, the new edge is simply
   dropped instead of creating a second node for the same state. This avoids
   the bookkeeping complexity (and dangling-reference bugs) of reparenting
   nodes when a cheaper path to an existing state is found later, at the cost
   of occasionally keeping a slightly suboptimal parent for a state instead
   of rewiring to a newly discovered cheaper path. Classic SMA* is a tree
   search that can revisit the same state under different ancestors; this
   simplification trades that flexibility for a much simpler and bug-free
   implementation.
2. When a node's children are deleted to free memory, we back up only a
   single scalar "forgotten f-value" (the minimum f seen in the deleted
   subtree) to the parent, as in the classic algorithm. We do NOT store
   partial subtree shape, so when a node is later re-expanded its successors
   are simply regenerated from scratch via `problem.successors`. This is
   correct for deterministic domains (both bundled domains are deterministic)
   but would be unsound for stochastic/non-deterministic successors.
3. Node deletion picks the leaf with the worst (highest) backed-up f-value;
   ties are broken by preferring the most recently generated node. We never
   delete the root. If memory is exhausted down to a single node, the search
   reports `memory_limit_reached` and stops rather than looping forever.
4. f-values are kept monotonically non-decreasing along a path
   (f_child = max(g(child) + h(child), f_parent)) to keep behavior sane even
   if the heuristic were inconsistent, exactly as suggested in the standard
   SMA* writeups.
"""
from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union

from sortedcontainers import SortedList

from domains.base import SearchProblem

from ._run_utils import MemoryLimitError, NodeLimitError, RunTracker
from .base import MemoryLimit, SearchAlgorithm, SearchLimits, SearchResult

_INF = float("inf")

DEFAULT_SMA_MEMORY_LIMIT_NODES = 50_000


def normalize_memory_limits(value: Union[int, Iterable[int], MemoryLimit, Iterable[MemoryLimit]]) -> List[MemoryLimit]:
    """Coerce a single memory limit (or an iterable of them) into a list of MemoryLimit objects.

    Accepts ints (treated as fixed node counts), MemoryLimit objects directly,
    or any mix thereof.
    """
    if isinstance(value, (int, MemoryLimit)):
        return [MemoryLimit(value) if isinstance(value, int) else value]
    result: List[MemoryLimit] = []
    for v in value:
        result.append(MemoryLimit(v) if isinstance(v, int) else v)
    return result


@dataclass(slots=True)
class _Node:
    key: Any
    state: Any
    g: float
    base_f: float
    parent_key: Optional[Any]
    action: Optional[Any]
    depth: int
    order: int  # creation order, used as a recency tie-breaker
    children: Set[Any] = field(default_factory=set)
    forgotten_f: float = _INF
    dead_end: bool = False

    def selection_f(self) -> float:
        if self.dead_end:
            return _INF
        if self.forgotten_f == _INF:
            return self.base_f
        return max(self.base_f, self.forgotten_f)

    def is_leaf(self) -> bool:
        return len(self.children) == 0


def _best_score(node: _Node) -> Tuple[float, int]:
    """Lower f first; among ties prefer the most recent node (highest order)."""
    return (node.selection_f(), -node.order)


def _worst_score(node: _Node) -> Tuple[float, int]:
    """Higher f first; among ties prefer the most recent node for removal."""
    return (-node.selection_f(), -node.order)


def _heap_entry(node: _Node) -> Tuple[Tuple[float, int], int, _Node]:
    """Heap entry: (best_score, order, node).  order breaks ties deterministically."""
    return (_best_score(node), node.order, node)


def _worst_sort_key(node: _Node) -> Tuple[float, int]:
    """Sort key for worst_leaves: (selection_f, order). Ascending sort; worst leaf is at the end."""
    return (node.selection_f(), node.order)


class SMAStar(SearchAlgorithm):
    """Simplified memory-bounded A*. See module docstring for limitations.

    Each instance is bound to a single memory limit (int or percentage-based
    ``MemoryLimit``).  To compare SMA* under several memory budgets, construct
    one ``SMAStar`` instance per budget (see ``normalize_memory_limits``)
    rather than mutating one instance's limit mid-run.  Percentage limits are
    resolved against ``limits.total_nodes`` at search time.
    """

    def __init__(
        self,
        memory_limit: Union[int, MemoryLimit] = DEFAULT_SMA_MEMORY_LIMIT_NODES,
    ) -> None:
        if isinstance(memory_limit, int):
            self.memory_limit = MemoryLimit(memory_limit)
        else:
            self.memory_limit = memory_limit
        self.name = f"SMA* (memory={self.memory_limit})"

    def search(self, problem: SearchProblem, limits: SearchLimits) -> SearchResult:
        result = SearchResult(
            algorithm_name=self.name,
            domain_name=getattr(problem, "name", "unknown"),
            instance_id="",
        )
        tracker = RunTracker.start(limits.max_nodes, limits.max_memory_mb)
        memory_limit_nodes = self.memory_limit.resolve(limits.total_nodes)
        counter = itertools.count()

        start = problem.initial_state
        start_key = problem.state_key(start)
        root = _Node(
            key=start_key,
            state=start,
            g=0.0,
            base_f=problem.heuristic(start),
            parent_key=None,
            action=None,
            depth=0,
            order=next(counter),
        )
        nodes: Dict[Any, _Node] = {start_key: root}
        tracker.nodes_generated = 1

        # --- Heap-based leaf tracking for O(log n) selection ---
        active_leaves: Set[Any] = {start_key}
        leaf_heap: list = [_heap_entry(root)]
        # --- SortedList for O(log n) worst-leaf pruning ---
        worst_leaves: SortedList[_Node] = SortedList(key=_worst_sort_key)
        worst_leaves.add(root)

        nodes_expanded = 0
        max_frontier_size = 1
        nodes_collapsed = 0

        try:
            while True:
                tracker.check_limits()

                leaf = self._select_best_leaf(active_leaves, leaf_heap)
                if leaf is None or leaf.selection_f() == _INF:
                    result.error_message = result.error_message or "search space exhausted"
                    break

                if problem.is_goal(leaf.state):
                    result.success = True
                    result.solution_cost = leaf.g
                    result.solution_actions = self._reconstruct(nodes, leaf.key)
                    break

                # Expand: remove leaf from active set (it gains children).
                # Remove BEFORE _expand because it mutates leaf.children,
                # which would break SortedList's dataclass __eq__ lookup.
                active_leaves.discard(leaf.key)
                worst_leaves.discard(leaf)

                children_before = set(leaf.children)
                goal_node = self._expand(problem, nodes, leaf, tracker, counter)
                nodes_expanded += 1

                if goal_node is not None:
                    result.success = True
                    result.solution_cost = goal_node.g
                    result.solution_actions = self._reconstruct(nodes, goal_node.key)
                    break

                new_child_keys = leaf.children - children_before
                if new_child_keys:
                    for child_key in new_child_keys:
                        child = nodes[child_key]
                        active_leaves.add(child_key)
                        worst_leaves.add(child)
                        heapq.heappush(leaf_heap, _heap_entry(child))
                else:
                    # No new children -- leaf stays as a leaf (dead_end set by _expand)
                    active_leaves.add(leaf.key)
                    worst_leaves.add(leaf)

                while len(nodes) > memory_limit_nodes:
                    pruned = self._prune_worst_leaf(nodes, root.key, active_leaves, leaf_heap, worst_leaves)
                    if pruned is None:
                        result.memory_limit_reached = True
                        break
                    nodes_collapsed += 1
                if result.memory_limit_reached:
                    break

                max_frontier_size = max(max_frontier_size, len(active_leaves))
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
        result.max_depth_reached = (
            len(result.solution_actions) if result.success else max((n.depth for n in nodes.values()), default=0)
        )
        result.reexpansions = 0  # SMA* re-expands forgotten nodes; not separately tracked in this simplification
        result.nodes_collapsed = nodes_collapsed
        result.ram_capacity_initial = memory_limit_nodes
        result.ram_capacity_final = memory_limit_nodes
        result.ram_capacity_peak = memory_limit_nodes
        result.ram_capacity_min = memory_limit_nodes
        return result

    @staticmethod
    def _select_best_leaf(active_leaves: Set[Any], leaf_heap: list) -> Optional[_Node]:
        """Pop the best valid leaf from the heap (O(log n) amortized)."""
        while leaf_heap:
            _score, _order, node = leaf_heap[0]
            if node.key in active_leaves and not node.dead_end:
                return node
            heapq.heappop(leaf_heap)  # discard stale entry
        return None

    def _expand(
        self,
        problem: SearchProblem,
        nodes: Dict[Any, _Node],
        leaf: _Node,
        tracker: RunTracker,
        counter: "itertools.count",
    ) -> Optional[_Node]:
        """Expand a leaf, generating children.  Return the goal node if found during generation."""
        new_child_added = False
        for action, next_state, cost in problem.successors(leaf.state):
            next_key = problem.state_key(next_state)
            if next_key == leaf.parent_key:
                continue  # avoid the trivial immediate-parent cycle
            if next_key in nodes:
                # State already has a node elsewhere in the tree; see module
                # docstring limitation #1 (no reparenting on rediscovery).
                continue
            new_g = leaf.g + cost
            base_f = max(new_g + problem.heuristic(next_state), leaf.base_f)
            child = _Node(
                key=next_key,
                state=next_state,
                g=new_g,
                base_f=base_f,
                parent_key=leaf.key,
                action=action,
                depth=leaf.depth + 1,
                order=next(counter),
            )
            nodes[next_key] = child
            leaf.children.add(next_key)
            tracker.nodes_generated += 1
            new_child_added = True
            if problem.is_goal(next_state):
                return child
        if not new_child_added:
            # No new node could be added (dead end, or every successor was a
            # duplicate of a node already in memory) -- never reselect this leaf.
            leaf.dead_end = True
        return None

    @staticmethod
    def _prune_worst_leaf(
        nodes: Dict[Any, _Node],
        root_key: Any,
        active_leaves: Set[Any],
        leaf_heap: list,
        worst_leaves: SortedList,
    ) -> Optional[_Node]:
        """Delete the worst leaf to free memory. Returns the pruned node, or None.

        Uses the SortedList for O(log L) worst-leaf removal instead of O(L) scan.
        Skips stale entries (nodes already removed from `nodes` dict).
        """
        while worst_leaves:
            candidate = worst_leaves[-1]
            if candidate.key == root_key:
                worst_leaves.pop()
                continue
            if candidate.key not in nodes:
                worst_leaves.pop()
                active_leaves.discard(candidate.key)
                continue
            worst = candidate
            worst_leaves.pop()
            active_leaves.discard(worst.key)
            del nodes[worst.key]
            parent = nodes.get(worst.parent_key)
            if parent is not None:
                parent.children.discard(worst.key)
                deleted_min_f = min(worst.base_f, worst.forgotten_f)
                parent.forgotten_f = min(parent.forgotten_f, deleted_min_f)
                if not parent.children:
                    parent.dead_end = False
                    active_leaves.add(parent.key)
                    worst_leaves.add(parent)
                    heapq.heappush(leaf_heap, _heap_entry(parent))
            return worst
        return None

    @staticmethod
    def _reconstruct(nodes: Dict[Any, _Node], goal_key: Any) -> List[Any]:
        actions: List[Any] = []
        key: Optional[Any] = goal_key
        while key is not None:
            node = nodes[key]
            if node.action is None:
                break
            actions.append(node.action)
            key = node.parent_key
        actions.reverse()
        return actions
