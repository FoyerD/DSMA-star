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
    for instance in instances:
        problem: SearchProblem = instance.problem
        for algorithm in algorithms:
            result = algorithm.search(problem, limits)
            result.instance_id = instance.instance_id
            result.instance_difficulty = instance.difficulty
            result.domain_name = getattr(problem, "name", result.domain_name)
            results.append(result)
    return results
