"""Ties together instances, algorithms, and limits to produce SearchResult lists."""
from __future__ import annotations

from typing import List

from algorithms.base import SearchAlgorithm, SearchLimits, SearchResult
from domains.base import SearchProblem

from .instance_generators import NamedInstance


def run_benchmark(
    instances: List[NamedInstance],
    algorithms: List[SearchAlgorithm],
    limits: SearchLimits,
) -> List[SearchResult]:
    """Run every algorithm on every instance under identical limits."""
    results: List[SearchResult] = []
    total = len(instances) * len(algorithms)
    done = 0
    for instance in instances:
        problem: SearchProblem = instance.problem
        for algorithm in algorithms:
            done += 1
            remaining = total - done
            print(f"[{done}/{total}] Running {algorithm.name} on {instance.instance_id} ({remaining} remaining)...")
            result = algorithm.search(problem, limits)
            status = "solved" if result.success else (
                "memory limit" if result.memory_limit_reached else (
                    "node limit" if result.node_limit_reached else (
                        "stack exhausted" if result.stack_exhausted else "failed"
                    )
                )
            )
            print(f"       → {status} ({result.runtime_seconds:.1f}s, {result.peak_memory_mb:.0f} MB)")
            result.instance_id = instance.instance_id
            result.instance_difficulty = instance.difficulty
            result.instance_source = instance.source
            result.known_optimal_depth = instance.optimal_depth
            result.domain_name = getattr(problem, "name", result.domain_name)
            results.append(result)
    return results
