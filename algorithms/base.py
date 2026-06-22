"""Generic search algorithm interface, plus shared result/limit dataclasses."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, List, Optional

from domains.base import SearchProblem


@dataclass
class SearchLimits:
    """Resource limits applied identically to every algorithm in a benchmark run."""

    timeout_seconds: float = 10.0
    max_memory_mb: float = 512.0
    max_nodes: int = 200_000
    # Only consulted by SMA*: max number of nodes it may keep in memory at once.
    sma_star_memory_limit_nodes: int = 2_000


@dataclass
class SearchResult:
    """Outcome and metrics for a single (algorithm, problem instance) run."""

    algorithm_name: str
    domain_name: str
    instance_id: str
    success: bool = False
    solution_actions: List[Any] = field(default_factory=list)
    solution_cost: Optional[float] = None
    runtime_seconds: float = 0.0
    peak_memory_mb: float = 0.0
    nodes_expanded: int = 0
    nodes_generated: int = 0
    max_frontier_size: int = 0
    max_depth_reached: int = 0
    reexpansions: int = 0
    timeout: bool = False
    memory_limit_reached: bool = False
    error_message: Optional[str] = None

    @property
    def solution_depth(self) -> Optional[int]:
        return len(self.solution_actions) if self.success else None


class SearchAlgorithm(ABC):
    """Abstract base class every search algorithm implements."""

    name: str = "search_algorithm"

    @abstractmethod
    def search(self, problem: SearchProblem, limits: SearchLimits) -> SearchResult:
        """Run the algorithm on `problem` honoring `limits` and return a SearchResult."""
