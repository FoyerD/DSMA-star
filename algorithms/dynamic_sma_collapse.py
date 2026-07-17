"""Dynamic SMA*-Collapse: SMA* with an adaptively-sized RAM frontier.

This is our first proposed algorithm. It behaves exactly like the
`SMAStar` in `sma_star.py` (same simplifications and limitations documented
there: global duplicate suppression instead of a pure tree search, scalar
forgotten-f backup on collapse, no reparenting on rediscovery) except that
the memory bound `B_ram` is not fixed -- it adapts every
`limits.epoch_generated_nodes` generated nodes based on how often the
algorithm has had to collapse nodes to stay within budget:

- If more than half of recently generated nodes had to be collapsed
  (`collapse_ratio > 0.50`), memory pressure is high relative to the
  problem: double `B_ram` (capped at `dynamic_max_ram_nodes`).
- If fewer than 10% needed collapsing (`collapse_ratio < 0.10`), the search
  has more memory than it needs: halve `B_ram` (floored at
  `dynamic_min_ram_nodes`), then immediately enforce the smaller bound by
  collapsing the worst nodes if the resident set is still oversized.

`OPEN_RAM` in the spec corresponds to the full set of nodes currently
resident in memory (`nodes` below), not just leaves -- ancestors of a
resident leaf must stay resident too so f-values can be backed up and the
solution path can be reconstructed, exactly as in our `SMAStar`.

### What counts as "restored" (`SearchResult.nodes_restored`)

Collapse (`_prune_worst_leaf`) deletes a node's `_Node` record outright and
backs up only a scalar `forgotten_f` bound onto its parent -- the pruned
node's state/children are not retained anywhere (see the module docstring
of `sma_star.py` for why this scalar-backup simplification is safe here:
both domains are deterministic, so successors regenerate identically).

A node's *entire* subtree is collapsed away exactly when every one of its
children has been pruned, which makes the node a leaf again -- distinguishable
from a node that was never expanded by `forgotten_f != inf`. If that node is
later reselected as the best leaf and expanded again (`_expand`), this is a
restore: the search is regenerating a subtree it had previously forgotten,
because the backed-up bound made it look competitive again. `nodes_restored`
counts the freshly generated children produced during such a restore-expand
(0 for an ordinary first-time expansion, where `forgotten_f` is still `inf`).

This is not a perfect restore: the regenerated children are brand-new `_Node`
objects (new `order`, no memory of the exact set of grandchildren the
original subtree had before it was collapsed) -- only the scalar f-value
bound is reused for selection. It is, however, the only "does a previously
collapsed part of the tree come back?" event this simplified SMA* has.
"""
from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from sortedcontainers import SortedList

from domains.base import SearchProblem

from ._run_utils import MemoryLimitError, NodeLimitError, RunTracker
from .base import SearchAlgorithm, SearchLimits, SearchResult

_INF = float("inf")


@dataclass(slots=True)
class _Node:
    key: Any
    state: Any
    g: float
    base_f: float
    parent_key: Optional[Any]
    action: Optional[Any]
    depth: int
    order: int
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
    # Lower f first; among ties prefer larger g (deeper node).
    return (node.selection_f(), -node.g)


def _worst_score(node: _Node) -> Tuple[float, int]:
    # Larger f first; among ties prefer smaller g (shallower node) for removal.
    return (-node.selection_f(), node.g)


def _heap_entry(node: _Node) -> Tuple[Tuple[float, int], int, _Node]:
    """Heap entry: (best_score, order, node).  order breaks ties deterministically."""
    return (_best_score(node), node.order, node)


def _worst_sort_key(node: _Node) -> Tuple[float, int]:
    """Sort key for worst_leaves: (selection_f, -g). Ascending sort; worst leaf is at the end."""
    return (node.selection_f(), -node.g)


class DynamicSMACollapse(SearchAlgorithm):
    """SMA* with a dynamically resized RAM bound. See module docstring."""

    name = "dynamic_sma_collapse"

    def search(self, problem: SearchProblem, limits: SearchLimits) -> SearchResult:
        result = SearchResult(
            algorithm_name=self.name,
            domain_name=getattr(problem, "name", "unknown"),
            instance_id="",
        )
        tracker = RunTracker.start(limits.max_nodes, limits.max_memory_mb)
        counter = itertools.count()

        b_ram = max(2, limits.dynamic_initial_ram_nodes)
        b_ram_min = max(2, limits.dynamic_min_ram_nodes)
        b_ram_max = max(b_ram_min, limits.dynamic_max_ram_nodes)
        b_ram = min(max(b_ram, b_ram_min), b_ram_max)

        collapsed_count_epoch = 0
        generated_count_epoch = 0

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
        nodes_collapsed = 0
        nodes_restored = 0
        max_frontier_size = 1
        ram_capacity_peak = b_ram
        ram_capacity_min = b_ram
        number_of_ram_increases = 0
        number_of_ram_decreases = 0

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
                generated_before = tracker.nodes_generated
                goal_node, restored = self._expand(problem, nodes, leaf, tracker, counter)
                nodes_restored += restored
                nodes_expanded += 1
                generated_count_epoch += tracker.nodes_generated - generated_before

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

                while len(nodes) > b_ram:
                    pruned = self._prune_worst_leaf(nodes, root.key, active_leaves, leaf_heap, worst_leaves)
                    if pruned is None:
                        result.memory_limit_reached = True
                        break
                    nodes_collapsed += 1
                    collapsed_count_epoch += 1
                    # If parent became a leaf, it's already in active_leaves / heap
                if result.memory_limit_reached:
                    break

                if generated_count_epoch >= max(1, limits.epoch_generated_nodes):
                    collapse_ratio = collapsed_count_epoch / max(generated_count_epoch, 1)
                    if collapse_ratio > 0.50:
                        b_ram = min(2 * b_ram, b_ram_max)
                        number_of_ram_increases += 1
                    elif collapse_ratio < 0.10:
                        b_ram = max(b_ram // 2, b_ram_min)
                        number_of_ram_decreases += 1
                        while len(nodes) > b_ram:
                            pruned = self._prune_worst_leaf(nodes, root.key, active_leaves, leaf_heap, worst_leaves)
                            if pruned is None:
                                result.memory_limit_reached = True
                                break
                            nodes_collapsed += 1
                    collapsed_count_epoch = 0
                    generated_count_epoch = 0
                    ram_capacity_peak = max(ram_capacity_peak, b_ram)
                    ram_capacity_min = min(ram_capacity_min, b_ram)

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
        result.reexpansions = 0
        result.nodes_collapsed = nodes_collapsed
        result.nodes_restored = nodes_restored
        result.ram_capacity_initial = min(max(limits.dynamic_initial_ram_nodes, b_ram_min), b_ram_max)
        result.ram_capacity_final = b_ram
        result.ram_capacity_peak = ram_capacity_peak
        result.ram_capacity_min = ram_capacity_min
        result.number_of_ram_increases = number_of_ram_increases
        result.number_of_ram_decreases = number_of_ram_decreases
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
    ) -> Tuple[Optional[_Node], int]:
        """Expand `leaf`, returning (goal_node_or_None, restored_count).

        The restored count is nonzero only when `leaf` was previously expanded
        and its entire subtree was since collapsed away (`leaf.forgotten_f != inf`)."""
        is_restore = leaf.forgotten_f != _INF
        new_child_added = False
        restored = 0
        for action, next_state, cost in problem.successors(leaf.state):
            next_key = problem.state_key(next_state)
            if next_key == leaf.parent_key:
                continue
            if next_key in nodes:
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
            if is_restore:
                restored += 1
            if problem.is_goal(next_state):
                return child, restored
        if not new_child_added:
            leaf.dead_end = True
        return None, restored

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
                # Stale entry — node was removed from `nodes` but stale
                # SortedList reference survived (dataclass __eq__ drift).
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
