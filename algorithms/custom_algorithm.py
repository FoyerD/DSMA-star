"""Placeholder slot for our own proposed search algorithm.

TODO: Replace the internals of CustomAlgorithm with our proposed algorithm.
For now it simply delegates to AStar so it satisfies the SearchAlgorithm
interface and can be benchmarked side-by-side with the others.
"""
from __future__ import annotations

from domains.base import SearchProblem

from .astar import AStar
from .base import SearchAlgorithm, SearchLimits, SearchResult


class CustomAlgorithm(SearchAlgorithm):
    """Stand-in for a future custom algorithm. Currently delegates to A*."""

    name = "custom_algorithm"

    def __init__(self) -> None:
        self._delegate = AStar()

    def search(self, problem: SearchProblem, limits: SearchLimits) -> SearchResult:
        # TODO: implement our proposed algorithm here instead of delegating.
        result = self._delegate.search(problem, limits)
        result.algorithm_name = self.name
        return result
