"""Run ILBFS on a specific amit instance with active printing.

Usage:
    python scripts/run_ilbfs_verbose.py [target_depth]

Shows the current path being explored, depth, F values, and collapse/restore events.

Tie-breaking: depth-first (prefer deeper nodes on F-ties).
"""
from __future__ import annotations

import heapq
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from algorithms._run_utils import MemoryLimitError, NodeLimitError, RunTracker
from algorithms.base import SearchLimits, SearchResult
from benchmark.instance_generators import load_amit_instances
from domains.base import SearchProblem
from domains.n_puzzle import NPuzzleProblem


PRINT_INTERVAL = 10000  # Print status every N expansions


@dataclass(slots=True)
class _Node:
    state: Any
    g: float
    h: float
    f: float
    F: float
    parent: Optional[_Node]
    action: Any
    children: Dict[Any, _Node] = field(default_factory=dict)
    depth: int = 0


def reconstruct_path(node: _Node) -> List[Any]:
    actions: List[Any] = []
    current = node
    while current.parent is not None:
        actions.append(current.action)
        current = current.parent
    actions.reverse()
    return actions


def print_state_flat(state: Tuple[int, ...]) -> str:
    """Print state as a 4x4 grid."""
    lines = []
    for row in range(4):
        cells = []
        for col in range(4):
            val = state[row * 4 + col]
            cells.append(f"{val:2d}" if val != 0 else " .")
        lines.append(" ".join(cells))
    return "\n".join(lines)


def run_ilbfs_verbose(problem: SearchProblem, limits: SearchLimits) -> SearchResult:
    """ILBFS with active printing to show search progress."""
    result = SearchResult(
        algorithm_name="ilbfs_verbose",
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

    open_heap: List[Tuple[float, int, Any]] = []
    root_key = state_key(start)
    heapq.heappush(open_heap, (root.F, -root.depth, root_key))

    nodes: Dict[Any, _Node] = {state_key(start): root}

    tracker.nodes_generated = 1
    nodes_expanded = 0
    reexpansions = 0
    max_frontier_size = 1
    max_depth_reached = 0
    oldbest: Optional[_Node] = None
    last_print_time = time.time()

    print(f"Initial state (h={start_h:.0f}):")
    print(print_state_flat(start))
    print("-" * 40)

    try:
        while open_heap:
            tracker.check_limits()

            popped_F, _neg_order, popped_key = heapq.heappop(open_heap)
            best = nodes.get(popped_key)

            if best is None or best.F != popped_F:
                continue

            max_depth_reached = max(max_depth_reached, best.depth)

            if problem.is_goal(best.state):
                print(f"\n{'='*40}")
                print(f"GOAL FOUND at depth {best.depth}!")
                print(f"Solution cost: {best.g}")
                print(print_state_flat(best.state))
                result.success = True
                result.solution_cost = best.g
                result.solution_actions = reconstruct_path(best)
                break

            # Collapse loop
            collapsed = False
            collapse_depth = 0
            while oldbest is not None and oldbest != best.parent:
                collapsed = True
                collapse_depth += 1
                oldbest_path = reconstruct_path(oldbest)
                oldbest_path_str = " -> ".join(a for a in oldbest_path) if oldbest_path else "(root)"
                n_children = len(oldbest.children)
                old_F = oldbest.F
                if oldbest.children:
                    oldbest.F = min(child.F for child in oldbest.children.values())
                else:
                    oldbest.F = oldbest.f
                print(
                    f"  COLLAPSE #{collapse_depth}: depth={oldbest.depth} "
                    f"F {old_F:.0f}->{oldbest.F:.0f} children={n_children} "
                    f"| {oldbest_path_str}",
                    flush=True,
                )
                heapq.heappush(
                    open_heap,
                    (oldbest.F, -oldbest.depth, state_key(oldbest.state)),
                )
                for ck in list(oldbest.children.keys()):
                    if ck in nodes and nodes[ck] is oldbest.children[ck]:
                        del nodes[ck]
                oldbest.children.clear()
                oldbest = oldbest.parent

            if collapsed:
                open_heap = [
                    (node.F, -node.depth, state_key(node.state))
                    for node in nodes.values()
                ]
                heapq.heapify(open_heap)
                print(
                    f"  Collapsed {collapse_depth} levels, rebuilt heap: {len(open_heap)} entries, "
                    f"best.path={' -> '.join(a for a in reconstruct_path(best)) if best.depth > 0 else '(root)'}",
                    flush=True,
                )

            if best.F > best.f:
                reexpansions += 1

            nodes_expanded += 1

            # Print status periodically
            now = time.time()
            if nodes_expanded % PRINT_INTERVAL == 0 or (now - last_print_time) > 5:
                path = reconstruct_path(best)
                path_str = " -> ".join(a for a in path) if path else "(root)"
                print(
                    f"[{nodes_expanded:>8d}] depth={best.depth:>2d} "
                    f"g={best.g:.0f} h={best.h:.0f} f={best.f:.0f} F={best.F:.0f} "
                    f"frontier={len(open_heap):>6d} | {path_str}",
                    flush=True,
                )
                last_print_time = now

            # Expand children
            n_generated = 0
            n_skipped = 0
            for action, next_state, cost in problem.successors(best.state):
                next_key = state_key(next_state)
                new_g = best.g + cost

                existing = nodes.get(next_key)
                if existing is not None and existing.g <= new_g:
                    n_skipped += 1
                    continue

                tracker.nodes_generated += 1
                next_h = problem.heuristic(next_state)
                next_f = new_g + next_h

                next_F = next_f
                if best.F > best.f and best.F > next_F:
                    next_F = best.F

                child = _Node(
                    state=next_state,
                    g=new_g,
                    h=next_h,
                    f=next_f,
                    F=next_F,
                    parent=best,
                    action=action,
                    depth=best.depth + 1,
                )

                best.children[next_key] = child
                nodes[next_key] = child
                heapq.heappush(
                    open_heap,
                    (child.F, -child.depth, next_key),
                )
                n_generated += 1

            if nodes_expanded <= 5 or nodes_expanded % 50000 == 0:
                print(
                    f"  EXPANDED depth={best.depth} action={best.action} "
                    f"children_gen={n_generated} children_skip={n_skipped} "
                    f"total_nodes={len(nodes)}",
                    flush=True,
                )

            oldbest = best
            max_frontier_size = max(max_frontier_size, len(open_heap))

    except NodeLimitError:
        print(f"\nNODE LIMIT REACHED after {nodes_expanded} expansions")
        result.node_limit_reached = True
        result.error_message = "max_nodes safety valve exceeded"
    except MemoryLimitError:
        print(f"\nMEMORY LIMIT REACHED after {nodes_expanded} expansions")
        result.memory_limit_reached = True
        result.error_message = "real memory ceiling exceeded"
    finally:
        result.peak_memory_mb = tracker.stop()

    result.runtime_seconds = tracker.elapsed()
    result.nodes_expanded = nodes_expanded
    result.nodes_generated = tracker.nodes_generated
    result.max_frontier_size = max_frontier_size
    result.max_depth_reached = max_depth_reached
    result.reexpansions = reexpansions
    return result


def main() -> None:
    target_depth = int(sys.argv[1]) if len(sys.argv) > 1 else 24

    instances = load_amit_instances()
    target = [i for i in instances if i.optimal_depth == target_depth]
    if not target:
        print(f"No amit instance with optimal_depth={target_depth}")
        sys.exit(1)
    target = target[0]

    print(f"Instance: {target.instance_id}, optimal_depth={target.optimal_depth}")
    print(f"State: {target.state}")
    print()

    problem = NPuzzleProblem(target.state, size=4)
    limits = SearchLimits(max_nodes=5_000_000, max_memory_mb=8000)

    print(f"Running ILBFS with verbose output...")
    print("=" * 40)

    result = run_ilbfs_verbose(problem, limits)

    print("\n" + "=" * 40)
    print("RESULTS:")
    print(f"  Success: {result.success}")
    if result.success:
        print(f"  Solution depth: {result.solution_depth}")
        print(f"  Solution cost: {result.solution_cost}")
        print(f"  Solution actions: {result.solution_actions}")
    print(f"  Nodes expanded: {result.nodes_expanded}")
    print(f"  Nodes generated: {result.nodes_generated}")
    print(f"  Max frontier size: {result.max_frontier_size}")
    print(f"  Max depth reached: {result.max_depth_reached}")
    print(f"  Reexpansions: {result.reexpansions}")
    print(f"  Runtime: {result.runtime_seconds:.3f}s")
    print(f"  Peak memory: {result.peak_memory_mb:.1f} MB")


if __name__ == "__main__":
    main()
