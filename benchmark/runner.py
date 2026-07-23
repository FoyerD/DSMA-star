"""Ties together instances, algorithms, and limits to produce SearchResult lists."""
from __future__ import annotations

from typing import Dict, List, Optional

from algorithms.base import MemoryLimit, SearchAlgorithm, SearchLimits, SearchResult
from domains.base import SearchProblem

from .instance_generators import NamedInstance


def run_benchmark(
    instances: List[NamedInstance],
    algorithms: List[SearchAlgorithm],
    limits: SearchLimits,
    dynamic_overrides: Optional[Dict[str, MemoryLimit]] = None,
    memory_basis: str = "a",
) -> List[SearchResult]:
    """Run every algorithm on every instance under identical limits.

    ``dynamic_overrides`` maps SearchLimits field names to ``MemoryLimit``
    objects.  For each instance, if any override is a percentage, the
    instance's node count is resolved using ``memory_basis``:
      - ``"ida"``: ``total_nodes_ida`` (IDA* search tree size)
      - ``"a"``: ``total_nodes_a`` (actual A* nodes expanded)
      - ``"a_approx"``: ``total_nodes_a_approx`` (sqrt of IDA* count)
    """
    results: List[SearchResult] = []
    total = len(instances) * len(algorithms)
    done = 0
    for instance in instances:
        problem: SearchProblem = instance.problem

        # Select the node-count basis for percentage-based limits.
        if memory_basis == "ida":
            basis_nodes = instance.total_nodes_ida
        elif memory_basis == "a":
            basis_nodes = instance.total_nodes_a
        elif memory_basis == "a_approx":
            basis_nodes = instance.total_nodes_a_approx
        else:
            raise ValueError(f"Unknown memory_basis {memory_basis!r} (expected 'ida', 'a', or 'a_approx')")

        has_pct = any(ml.is_percent for ml in (dynamic_overrides or {}).values())
        if has_pct and basis_nodes is None:
            raise ValueError(
                f"Percentage-based memory limits require total_nodes_{memory_basis} on each instance, "
                f"but instance {instance.instance_id!r} has none. "
                f"Use --puzzle-instance-source=korf or provide flat integer limits."
            )
        resolved_limits = limits.resolve_for_instance(
            total_nodes=basis_nodes or limits.max_nodes,
            dynamic_overrides=dynamic_overrides,
        )

        for algorithm in algorithms:
            done += 1
            remaining = total - done
            print(f"[{done}/{total}] Running {algorithm.name} on {instance.instance_id} ({remaining} remaining)...")
            result = algorithm.search(problem, resolved_limits)
            status = "solved" if result.success else (
                "memory limit" if result.memory_limit_reached else (
                    "node limit" if result.node_limit_reached else (
                        "stack exhausted" if result.stack_exhausted else "failed"
                    )
                )
            )
            print(f"       → {status} ({result.runtime_seconds:.1f}s, {result.peak_memory_mb:.0f} MB, {result.nodes_expanded:,} expanded, {result.max_frontier_size:,} frontier)")
            result.instance_id = instance.instance_id
            result.instance_difficulty = instance.difficulty
            result.instance_source = instance.source
            result.known_optimal_depth = instance.optimal_depth
            result.total_nodes_ida = instance.total_nodes_ida
            result.total_nodes_a_approx = instance.total_nodes_a_approx
            result.total_nodes_a = instance.total_nodes_a
            result.total_nodes_a_predicted = instance.total_nodes_a_predicted
            result.domain_name = getattr(problem, "name", result.domain_name)
            results.append(result)
    return results
