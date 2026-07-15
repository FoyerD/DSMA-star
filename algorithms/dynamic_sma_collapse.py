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

import itertools
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from domains.base import SearchProblem

from ._run_utils import MemoryLimitError, NodeLimitError, RunTracker
from .base import SearchAlgorithm, SearchLimits, SearchResult

_INF = float("inf")


@dataclass
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


def _best_score(node: _Node):
    # Lower f first; among ties prefer larger g (deeper node).
    return (node.selection_f(), -node.g)


def _worst_score(node: _Node):
    # Larger f first; among ties prefer smaller g (shallower node) for removal.
    return (-node.selection_f(), node.g)


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

                leaf = self._select_best_leaf(nodes)
                if leaf is None or leaf.selection_f() == _INF:
                    result.error_message = result.error_message or "search space exhausted"
                    break

                if problem.is_goal(leaf.state):
                    result.success = True
                    result.solution_cost = leaf.g
                    result.solution_actions = self._reconstruct(nodes, leaf.key)
                    break

                generated_before = tracker.nodes_generated
                nodes_restored += self._expand(problem, nodes, leaf, tracker, counter)
                nodes_expanded += 1
                generated_count_epoch += tracker.nodes_generated - generated_before

                while len(nodes) > b_ram:
                    if self._prune_worst_leaf(nodes, root.key):
                        nodes_collapsed += 1
                        collapsed_count_epoch += 1
                    else:
                        result.memory_limit_reached = True
                        break
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
                            if self._prune_worst_leaf(nodes, root.key):
                                nodes_collapsed += 1
                            else:
                                result.memory_limit_reached = True
                                break
                    collapsed_count_epoch = 0
                    generated_count_epoch = 0
                    ram_capacity_peak = max(ram_capacity_peak, b_ram)
                    ram_capacity_min = min(ram_capacity_min, b_ram)

                if result.memory_limit_reached:
                    break

                leaf_count = sum(1 for n in nodes.values() if n.is_leaf())
                max_frontier_size = max(max_frontier_size, leaf_count)
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
    def _select_best_leaf(nodes: Dict[Any, _Node]) -> Optional[_Node]:
        leaves = [n for n in nodes.values() if n.is_leaf() and not n.dead_end]
        if not leaves:
            return None
        return min(leaves, key=_best_score)

    def _expand(
        self,
        problem: SearchProblem,
        nodes: Dict[Any, _Node],
        leaf: _Node,
        tracker: RunTracker,
        counter: "itertools.count",
    ) -> int:
        """Expand `leaf`, returning how many of its new children count as
        "restored" (see module docstring): nonzero only when `leaf` was
        previously expanded and its entire subtree was since collapsed away
        (`leaf.forgotten_f != inf`), i.e. this expansion is regenerating a
        subtree the search had forgotten."""
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
        if not new_child_added:
            leaf.dead_end = True
        return restored

    @staticmethod
    def _prune_worst_leaf(nodes: Dict[Any, _Node], root_key: Any) -> bool:
        leaves = [n for n in nodes.values() if n.key != root_key and n.is_leaf()]
        if not leaves:
            return False
        worst = min(leaves, key=_worst_score)
        del nodes[worst.key]
        parent = nodes.get(worst.parent_key)
        if parent is not None:
            parent.children.discard(worst.key)
            parent.forgotten_f = min(parent.forgotten_f, worst.selection_f())
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
