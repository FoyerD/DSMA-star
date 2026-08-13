"""Generic search algorithm interface, plus shared result/limit dataclasses."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, List, Optional, Union

from domains.base import SearchProblem


@dataclass(frozen=True)
class MemoryLimit:
    """A node-count memory limit, either a fixed integer or a percentage of total_nodes.

    Percentages are stored as fractions (0.0-1.0); use the ``parse`` classmethod
    to accept CLI strings like ``"10%"`` or ``"5000"``.
    """

    value: Union[int, float]
    is_percent: bool = False

    def resolve(self, total_nodes: int) -> int:
        """Return the concrete node count for this limit."""
        if self.is_percent:
            return max(2, int(self.value * total_nodes))
        return max(2, int(self.value))

    @classmethod
    def parse(cls, raw: str) -> MemoryLimit:
        """Parse ``'5000'`` or ``'10%'`` into a MemoryLimit."""
        s = raw.strip()
        if s.endswith("%"):
            return cls(value=float(s[:-1]) / 100.0, is_percent=True)
        return cls(value=int(s), is_percent=False)

    def __repr__(self) -> str:
        if self.is_percent:
            pct = self.value * 100
            return f"{pct:.4g}%"
        return str(self.value)


@dataclass
class SearchLimits:
    """Resource limits applied identically to every algorithm in a benchmark run.

    There is intentionally no wall-clock timeout: a shared stopwatch
    structurally favors A* (it has no memory-management overhead per node),
    which defeats the point of comparing memory-bounded algorithms. A run
    only stops when it solves the problem or hits a real resource ceiling --
    `max_memory_mb` is enforced against actual process RSS (see
    `algorithms/_run_utils.py`), and `max_nodes` is a generous safety valve
    against a genuine infinite loop, not meant to be the binding constraint.
    """

    max_memory_mb: float = 4_096.0
    max_nodes: int = 5_000_000


@dataclass
class SearchResult:
    """Outcome and metrics for a single (algorithm, problem instance) run."""

    algorithm_name: str
    domain_name: str
    instance_id: str
    instance_difficulty: str = "default"
    instance_source: str = "unknown"
    known_optimal_depth: Optional[int] = None
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
    node_limit_reached: bool = False
    memory_limit_reached: bool = False
    stack_exhausted: bool = False
    error_message: Optional[str] = None

    # --- Instance metadata (copied from NamedInstance by runner) ---
    total_nodes_ida: Optional[int] = None
    total_nodes_a_approx: Optional[int] = None
    total_nodes_a: Optional[int] = None
    total_nodes_a_predicted: bool = False

    # --- multi-path specific (mp-bfs / mp-rbfs; None/0 for every other algorithm) ---
    requested_num_procs: Optional[int] = None
    actual_num_procs: Optional[int] = None
    scheduler_name: Optional[str] = None
    proc_switches: int = 0
    phase1_expanded: int = 0
    phase2_expanded: int = 0
    total_collapses: int = 0  # mp-rbfs only: collapse/backup events across all procs
    max_proc_tree_size: int = 0  # mp-rbfs only: largest live proc TREE observed (O(b*d) check)
    active_procs_at_solution: Optional[int] = None
    procs_used: Optional[int] = None
    min_proc_expansions: Optional[int] = None
    max_proc_expansions: Optional[int] = None
    mean_proc_expansions: Optional[float] = None
    median_proc_expansions: Optional[float] = None
    std_proc_expansions: Optional[float] = None
    winning_proc_id: Optional[int] = None
    winning_proc_expansions: Optional[int] = None
    # Compact "count,count,count,..." string, one entry per proc, in proc_id
    # order -- an optional escape hatch for offline analysis without adding a
    # column per proc to the normal CSV.
    proc_expansions_histogram: Optional[str] = None

    @property
    def solution_depth(self) -> Optional[int]:
        return len(self.solution_actions) if self.success else None


class SearchAlgorithm(ABC):
    """Abstract base class every search algorithm implements."""

    name: str = "search_algorithm"

    @abstractmethod
    def search(self, problem: SearchProblem, limits: SearchLimits) -> SearchResult:
        """Run the algorithm on `problem` honoring `limits` and return a SearchResult."""
