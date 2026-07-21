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
- If fewer than 5% needed collapsing (`collapse_ratio < 0.05`), the search
  has more memory than it needs: shrink `B_ram` by 1/3 (floored at
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
later reselected as the best leaf and expanded again (lazy successor
generation), this is a restore: the search is regenerating a subtree it had
previously forgotten, because the backed-up bound made it look competitive
again. `nodes_restored` counts freshly generated children produced during
such a restore-expand (0 for an ordinary first-time successor generation,
where `forgotten_f` is still `inf`).

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
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

from domains.base import SearchProblem

from ._run_utils import MemoryLimitError, NodeLimitError, RunTracker
from .base import SearchAlgorithm, SearchLimits, SearchResult

_INF = float("inf")
_ORDER_ID: itertools.count = itertools.count()


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
    # Lazy successor generation: an iterator over problem.successors(state).
    successor_iter: Optional[Iterator] = None
    next_offset: int = 0
    total_successors: int = 0
    forgotten_f: float = _INF
    dead_end: bool = False
    child_keys: Set[Any] = field(default_factory=set)

    def selection_f(self) -> float:
        if self.dead_end:
            return _INF
        if self.forgotten_f == _INF:
            return self.base_f
        return max(self.base_f, self.forgotten_f)

    def all_successors_generated(self) -> bool:
        return self.successor_iter is None

    def is_leaf(self) -> bool:
        return not self.successor_iter and self.next_offset == 0

    def is_prunable_leaf(self) -> bool:
        """A node that can be pruned: no un-generated successors and no children in memory."""
        if self.successor_iter is not None:
            return False
        return len(self.child_keys) == 0


def _heap_key(node: _Node) -> Tuple[float, int, int]:
    """Primary sort: (selection_f, depth, insertion order).

    Lower f first.  Among equal f, shallower nodes first.
    Among equal f and depth, older nodes first.
    """
    return (node.selection_f(), node.depth, next(_ORDER_ID))


def _worst_prunable_leaf(heap: list) -> Optional[_Node]:
    """Scan the heap to find the shallowest leaf with the highest f-cost."""
    worst: Optional[_Node] = None
    for _key, node in heap:
        if not node.is_prunable_leaf():
            continue
        if worst is None or (node.selection_f(), -node.depth) > (worst.selection_f(), -worst.depth):
            worst = node
    return worst


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
            order=0,
            successor_iter=iter(problem.successors(start)),
        )
        root.successor_iter, count_iter = itertools.tee(root.successor_iter)
        root.total_successors = sum(1 for _ in count_iter)
        root.successor_iter, _ = itertools.tee(root.successor_iter)

        nodes: Dict[Any, _Node] = {start_key: root}
        tracker.nodes_generated = 1

        heap: list = [(_heap_key(root), root)]
        heapq.heapify(heap)

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

                if not heap:
                    result.error_message = result.error_message or "search space exhausted"
                    break

                _key, node = heapq.heappop(heap)

                if problem.is_goal(node.state):
                    result.success = True
                    result.solution_cost = node.g
                    result.solution_actions = self._reconstruct(nodes, node.key)
                    break

                # Generate the next successor (lazy generation).
                if not node.all_successors_generated():
                    is_restore = node.forgotten_f != _INF
                    try:
                        action, next_state, cost = next(node.successor_iter)
                    except StopIteration:
                        node.successor_iter = None
                    else:
                        nodes_expanded += 1
                        node.next_offset += 1

                        next_key = problem.state_key(next_state)
                        should_insert = (next_key != node.parent_key and next_key not in nodes)
                        if should_insert:
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
                                order=node.order + 1,
                            )

                            if child.depth >= b_ram and not problem.is_goal(next_state):
                                child.base_f = _INF
                                child.dead_end = True
                            else:
                                child.successor_iter = iter(problem.successors(next_state))
                                child.successor_iter, count_it = itertools.tee(child.successor_iter)
                                child.total_successors = sum(1 for _ in count_it)
                                child.successor_iter, _ = itertools.tee(child.successor_iter)

                            nodes[next_key] = child
                            tracker.nodes_generated += 1
                            generated_count_epoch += 1
                            node.child_keys.add(next_key)

                            if is_restore:
                                nodes_restored += 1

                            heapq.heappush(heap, (_heap_key(child), child))

                            if problem.is_goal(next_state):
                                result.success = True
                                result.solution_cost = child.g
                                result.solution_actions = self._reconstruct(nodes, child.key)
                                break

                        # Node has more successors — re-insert into heap.
                        heapq.heappush(heap, (_heap_key(node), node))
                        max_frontier_size = max(max_frontier_size, len(heap))
                        continue

                # No more successors for this node.
                if node.all_successors_generated():
                    if node.next_offset == 0:
                        # Dead end — never generated any successor.
                        node.dead_end = True
                        node.base_f = _INF
                        self._backup_forgotten_f(nodes, node)

                # Enforce memory limit.
                while len(nodes) > b_ram:
                    if not self._prune_worst_leaf(nodes, heap, root.key):
                        result.memory_limit_reached = True
                        break
                    nodes_collapsed += 1
                    collapsed_count_epoch += 1

                if result.memory_limit_reached:
                    break

                # Adaptation epoch.
                if generated_count_epoch >= max(1, limits.epoch_generated_nodes):
                    collapse_ratio = collapsed_count_epoch / max(generated_count_epoch, 1)
                    if collapse_ratio > 0.50:
                        b_ram = min(2 * b_ram, b_ram_max)
                        number_of_ram_increases += 1
                    elif collapse_ratio < 0.05:
                        b_ram = max(b_ram * 2 // 3, b_ram_min)
                        number_of_ram_decreases += 1
                        while len(nodes) > b_ram:
                            if not self._prune_worst_leaf(nodes, heap, root.key):
                                result.memory_limit_reached = True
                                break
                            nodes_collapsed += 1
                    collapsed_count_epoch = 0
                    generated_count_epoch = 0
                    ram_capacity_peak = max(ram_capacity_peak, b_ram)
                    ram_capacity_min = min(ram_capacity_min, b_ram)

                if result.memory_limit_reached:
                    break

                # Periodically rebuild the heap to purge stale entries.
                if len(heap) > max(1000, 3 * len(nodes)):
                    heap[:] = [(_heap_key(n), n) for n in nodes.values()
                               if not n.dead_end]
                    heapq.heapify(heap)

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
        result.nodes_restored = nodes_restored
        result.ram_capacity_initial = min(max(limits.dynamic_initial_ram_nodes, b_ram_min), b_ram_max)
        result.ram_capacity_final = b_ram
        result.ram_capacity_peak = ram_capacity_peak
        result.ram_capacity_min = ram_capacity_min
        result.number_of_ram_increases = number_of_ram_increases
        result.number_of_ram_decreases = number_of_ram_decreases
        return result

    @staticmethod
    def _backup_forgotten_f(nodes: Dict[Any, _Node], node: _Node) -> None:
        """Propagate the node's forgotten_f upward to its parent.

        Called when a leaf is pruned or a node becomes a dead end.
        """
        if node.parent_key is None:
            return
        parent = nodes.get(node.parent_key)
        if parent is None:
            return
        subtree_best = min(node.base_f, node.forgotten_f)
        if subtree_best < parent.forgotten_f:
            parent.forgotten_f = subtree_best
            if parent.is_prunable_leaf():
                DynamicSMACollapse._backup_forgotten_f(nodes, parent)

    @staticmethod
    def _prune_worst_leaf(
        nodes: Dict[Any, _Node],
        heap: list,
        root_key: Any,
    ) -> bool:
        """Find and remove the worst leaf from memory.

        Returns True if a node was pruned, False if no prunable leaf exists.
        """
        worst = _worst_prunable_leaf(heap)
        if worst is None:
            return False
        if worst.key == root_key:
            return False

        del nodes[worst.key]
        worst.dead_end = True
        worst.base_f = _INF

        parent = nodes.get(worst.parent_key)
        if parent is not None:
            parent.child_keys.discard(worst.key)
        if parent is not None:
            subtree_best = min(worst.base_f, worst.forgotten_f)
            if subtree_best < parent.forgotten_f:
                parent.forgotten_f = subtree_best
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
