"""Simplified Memory-Bounded A* (SMA*).

This implementation follows the classic SMA* pseudocode from Russell (1992)
and the Wikipedia article closely:

- All nodes live in a single priority queue ordered by f-cost.
- Successors are generated one at a time (lazy generation).
- A node stays in the queue while it still has un-generated successors.
- When memory is full, the shallowest leaf with the highest f-cost is pruned.
- Pruned nodes back up a scalar ``forgotten_f`` to their parent.
- Duplicate detection is global (graph search), not pure tree search.
- No reparenting on rediscovery (simplification).
"""
from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Iterator, List, Optional, Set, Tuple, Union

from domains.base import SearchProblem

from ._run_utils import MemoryLimitError, NodeLimitError, RunTracker
from .base import MemoryLimit, SearchAlgorithm, SearchLimits, SearchResult

_INF = float("inf")

DEFAULT_SMA_MEMORY_LIMIT_NODES = 50_000


def normalize_memory_limits(value: Union[int, Iterable[int], MemoryLimit, Iterable[MemoryLimit]]) -> List[MemoryLimit]:
    """Coerce a single memory limit (or an iterable of them) into a list of MemoryLimit objects."""
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
    base_f: float  # g(s) + h(s), used as the actual f-value for leaf nodes
    parent_key: Optional[Any]
    action: Optional[Any]
    depth: int
    order: int
    # Lazy successor generation: an iterator over problem.successors(state).
    # Set to None once exhausted.
    successor_iter: Optional[Iterator] = None
    # Number of successors already generated (for tracking remaining count).
    next_offset: int = 0
    # Total number of successors (cached from first iteration pass or known a priori).
    total_successors: int = 0
    # The minimum f-value among all pruned descendants.
    forgotten_f: float = _INF
    dead_end: bool = False
    child_keys: Set[Any] = field(default_factory=set)

    def selection_f(self) -> float:
        """The f-value used for ordering in the queue.

        If the node's entire subtree has been collapsed, the best f-value
        among the deleted descendants is used instead of the node's own f.
        """
        if self.dead_end:
            return _INF
        if self.forgotten_f == _INF:
            return self.base_f
        return max(self.base_f, self.forgotten_f)

    def all_successors_generated(self) -> bool:
        """True if the successor iterator is fully consumed."""
        return self.successor_iter is None

    def is_leaf(self) -> bool:
        """A node is a leaf if it has never been expanded (no iterator) or
        has generated all its successors and generated none (dead end)."""
        return not self.successor_iter and self.next_offset == 0

    def is_prunable_leaf(self) -> bool:
        """A node that can be pruned: no un-generated successors and no children in memory."""
        if self.successor_iter is not None:
            return False
        return len(self.child_keys) == 0


_HEAP_ENTRY_ORDER_ID = itertools.count()


def _heap_key(node: _Node) -> Tuple[float, int, int]:
    """Primary sort: (selection_f, depth, insertion order).

    Lower f first.  Among equal f, shallower nodes first.
    Among equal f and depth, older nodes first.
    """
    return (node.selection_f(), node.depth, next(_HEAP_ENTRY_ORDER_ID))


def _prune_key(node: _Node) -> Tuple[float, int, int]:
    """Key for pruning: highest f first; among ties, shallower first.

    Returns a tuple that sorts ascending so that the *worst* candidate
    (highest f, shallowest depth) appears at the end.
    """
    return (node.selection_f(), -node.depth, node.order)


def _worst_prunable_leaf(heap: list) -> Optional[_Node]:
    """Scan the heap to find the shallowest leaf with the highest f-cost.

    According to the classic SMA* algorithm, we prune the worst leaf.
    "Worst" = highest f-cost; "leaf" = a node with no descendants in memory.
    If multiple nodes have the same f-cost, the shallowest one is chosen.
    """
    worst: Optional[_Node] = None
    for _key, node in heap:
        if not node.is_prunable_leaf():
            continue
        if worst is None or (node.selection_f(), -node.depth) > (worst.selection_f(), -worst.depth):
            worst = node
    return worst


class SMAStar(SearchAlgorithm):
    """Simplified memory-bounded A*. See module docstring for limitations."""

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
        max_depth = memory_limit_nodes  # depth beyond which we cannot fit more nodes

        # In classic SMA* the queue contains ALL generated nodes, not just
        # leaves.  Internal nodes stay in the queue as long as they have
        # un-generated successors.
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
            order=next(_HEAP_ENTRY_ORDER_ID),
            successor_iter=iter(problem.successors(start)),
        )
        # Determine total successor count by materializing the iterator.
        root.successor_iter, count_iter = itertools.tee(root.successor_iter)
        root.total_successors = sum(1 for _ in count_iter)
        root.successor_iter, _ = itertools.tee(root.successor_iter)

        nodes: Dict[Any, _Node] = {start_key: root}
        tracker.nodes_generated = 1

        # The queue: list of (heap_key, node) tuples.
        heap: list = [(_heap_key(root), root)]
        heapq.heapify(heap)

        nodes_expanded = 0
        nodes_collapsed = 0
        max_frontier_size = 1

        try:
            while True:
                tracker.check_limits()

                if not heap:
                    result.error_message = result.error_message or "search space exhausted"
                    break

                # Pop the best node from the queue.
                _key, node = heapq.heappop(heap)

                if problem.is_goal(node.state):
                    result.success = True
                    result.solution_cost = node.g
                    result.solution_actions = self._reconstruct(nodes, node.key)
                    break

                # Generate the next successor (lazy generation).
                if not node.all_successors_generated():
                    try:
                        action, next_state, cost = next(node.successor_iter)
                    except StopIteration:
                        node.successor_iter = None
                        # Fall through to re-insert the node with no more successors.
                    else:
                        nodes_expanded += 1

                        next_key = problem.state_key(next_state)
                        if next_key == node.parent_key:
                            pass  # skip trivial parent cycle
                        elif next_key in nodes:
                            pass  # global duplicate suppression
                        else:
                            new_g = node.g + cost
                            new_h = problem.heuristic(next_state)
                            base_f = max(new_g + new_h, node.base_f)
                            child = _Node(
                                key=next_key,
                                state=next_state,
                                g=new_g,
                                base_f=base_f,
                                parent_key=node.key,
                                action=action,
                                depth=node.depth + 1,
                                order=next(_HEAP_ENTRY_ORDER_ID),
                            )
                            # Check depth limit: beyond max_depth, the path is
                            # useless (cannot fit more nodes in memory).
                            if child.depth >= max_depth and not problem.is_goal(next_state):
                                child.base_f = _INF
                                child.dead_end = True
                            else:
                                child.successor_iter = iter(problem.successors(next_state))
                                child.successor_iter, count_it = itertools.tee(child.successor_iter)
                                child.total_successors = sum(1 for _ in count_it)
                                child.successor_iter, _ = itertools.tee(child.successor_iter)

                            nodes[next_key] = child
                            tracker.nodes_generated += 1
                            node.child_keys.add(next_key)

                            # Insert child into heap.
                            heapq.heappush(heap, (_heap_key(child), child))

                            if problem.is_goal(next_state):
                                result.success = True
                                result.solution_cost = child.g
                                result.solution_actions = self._reconstruct(nodes, child.key)
                                break

                        # Node has more successors — re-insert into heap.
                        heapq.heappush(heap, (_heap_key(node), node))
                        # If this is the first time we encountered this node,
                        # increment expanded count only once.  We already did
                        # above, so skip further processing.
                        # We must skip the rest of the loop body for this
                        # iteration.
                        # Actually, we need to handle the "no more successors"
                        # case below, so we use conditional logic.
                        # Continue to next iteration.
                        max_frontier_size = max(max_frontier_size, len(heap))
                        continue

                # If we get here, either the node has no more successors
                # (generator exhausted) or it was never expanded.
                if node.all_successors_generated():
                    if node.next_offset == 0:
                        # Leaf that was never successfully expanded → dead end.
                        node.dead_end = True
                        node.base_f = _INF
                        self._backup_forgotten_f(nodes, node)
                    elif self._all_children_pruned(nodes, node):
                        # Leaf again — all children have been pruned.
                        self._backup_forgotten_f(nodes, node)
                        if node.selection_f() < _INF:
                            heapq.heappush(heap, (_heap_key(node), node))
                    # Internal node with children still in memory — not re-inserted.
                    # It will be re-inserted by _prune_worst_leaf when a child
                    # is pruned and the parent becomes a leaf again.
                # Enforce memory limit.
                while len(nodes) > memory_limit_nodes:
                    if not self._prune_worst_leaf(nodes, heap, root.key):
                        result.memory_limit_reached = True
                        break
                    nodes_collapsed += 1

                if result.memory_limit_reached:
                    break

                max_frontier_size = max(max_frontier_size, len(heap))

        except NodeLimitError:
            result.node_limit_reached = True
            result.error_message = "max_nodes safety valve exceeded"
        except MemoryLimitError:
            result.memory_limit_reached = True
            result.error_message = "real memory ceiling exceeded"
        except RecursionError:
            result.stack_exhausted = True
            result.error_message = "recursion depth exceeded"
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
        result.reexpansions = 0
        result.nodes_collapsed = nodes_collapsed
        result.ram_capacity_initial = memory_limit_nodes
        result.ram_capacity_final = memory_limit_nodes
        result.ram_capacity_peak = memory_limit_nodes
        result.ram_capacity_min = memory_limit_nodes
        return result

    @staticmethod
    def _backup_forgotten_f(nodes: Dict[Any, _Node], node: _Node) -> None:
        """Propagate the node's selection_f upward as forgotten_f to its
        parent, then recurse upward if the parent becomes a prunable leaf."""
        if node.parent_key is None:
            return
        parent = nodes.get(node.parent_key)
        if parent is None:
            return
        # The best f-value in the deleted subtree is min(base_f, forgotten_f).
        subtree_best = min(node.base_f, node.forgotten_f)
        if subtree_best < parent.forgotten_f:
            parent.forgotten_f = subtree_best
            # If parent is now a prunable leaf, propagate upward.
            if parent.is_prunable_leaf():
                SMAStar._backup_forgotten_f(nodes, parent)

    @staticmethod
    def _all_children_pruned(nodes: Dict[Any, _Node], node: _Node) -> bool:
        """Check whether every child of this node has been removed from
        the nodes dict (i.e., pruned).  Assumes children explicitly
        tracked by the node's `children` set would be empty if all
        pruned, but we don't explicitly track children — instead we rely
        on the fact that if a node has generated successors and none
        remain in `nodes`, it's a leaf again."""
        # We don't track children explicitly in this rewrite.  Instead,
        # we know: if the node has a successor index > 0 (it generated
        # some children) but those children have all been deleted, then
        # the node's forgotten_f will have been updated.  We detect this
        # by checking if the node's selection_f differs from its base_f
        # (indicating some forgotten_f was backed up), or more directly
        # by checking if the node is now a prunable leaf.
        return node.is_prunable_leaf()

    @staticmethod
    def _prune_worst_leaf(
        nodes: Dict[Any, _Node],
        heap: list,
        root_key: Any,
    ) -> bool:
        """Find and remove the worst leaf from memory.

        Returns True if a node was pruned, False if no prunable leaf
        exists (memory exhaustion at a single node).
        """
        worst = _worst_prunable_leaf(heap)
        if worst is None:
            return False
        if worst.key == root_key:
            return False

        # Remove from nodes dict.
        del nodes[worst.key]
        # Remove from heap (lazy — just mark as dead; the heap entry
        # will be skipped when popped).  Reset selection_f to INF.
        worst.dead_end = True
        worst.base_f = _INF

        # Update parent.
        parent = nodes.get(worst.parent_key)
        if parent is not None:
            parent.child_keys.discard(worst.key)
        if parent is not None:
            # Back up the subtree's best f.
            subtree_best = min(worst.base_f, worst.forgotten_f)
            if subtree_best < parent.forgotten_f:
                parent.forgotten_f = subtree_best
            # If parent is now a prunable leaf, it may need to be
            # re-inserted into the heap.
            if parent.is_prunable_leaf() and parent.selection_f() < _INF:
                heapq.heappush(heap, (_heap_key(parent), parent))

        return True

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
