"""Generic search algorithm interface, plus shared result/limit dataclasses."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, List, Optional

from domains.base import SearchProblem


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
    # Generic RAM-node budget some algorithms may use as a soft cap (currently advisory).
    max_ram_nodes: int = 200_000

    # SMA*: max number of nodes it may keep in memory at once.
    sma_memory_limit_nodes: int = 50_000

    # Dynamic SMA*-Collapse: dynamic RAM capacity bounds and adaptation epoch.
    dynamic_initial_ram_nodes: int = 2_000
    dynamic_min_ram_nodes: int = 500
    dynamic_max_ram_nodes: int = 10_000

    # Two-Level Dynamic SMA*: RAM bounds, total (RAM+disk) frontier bound, epoch.
    two_level_initial_ram_nodes: int = 2_000
    two_level_min_ram_nodes: int = 500
    two_level_max_ram_nodes: int = 10_000
    two_level_total_node_limit: int = 50_000

    # Shared adaptation epoch length (number of generated nodes between adjustments).
    epoch_generated_nodes: int = 1_000


@dataclass
class SearchResult:
    """Outcome and metrics for a single (algorithm, problem instance) run."""

    algorithm_name: str
    domain_name: str
    instance_id: str
    # Not in the original spec's field list, but needed to group summaries by
    # difficulty (e.g. puzzle scramble depth, Sokoban easy/medium/hard).
    instance_difficulty: str = "default"
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
    # Set when a recursive algorithm (e.g. ILBFS) hits a RecursionError --
    # the Python-safe proxy for "ran out of call stack" on a real stack overflow.
    stack_exhausted: bool = False
    error_message: Optional[str] = None

    # --- Extra metrics for memory-bounded / two-level algorithms ---
    nodes_collapsed: int = 0
    nodes_spilled_to_disk: int = 0
    nodes_loaded_from_disk: int = 0
    disk_batches_loaded: int = 0
    disk_peak_nodes: int = 0
    disk_read_count: int = 0
    disk_write_count: int = 0
    disk_io_time_seconds: float = 0.0
    ram_capacity_initial: Optional[int] = None
    ram_capacity_final: Optional[int] = None
    ram_capacity_peak: Optional[int] = None
    ram_capacity_min: Optional[int] = None
    number_of_ram_increases: int = 0
    number_of_ram_decreases: int = 0
    number_of_total_collapses: int = 0
    stale_disk_nodes_skipped: int = 0
    duplicate_nodes_skipped: int = 0

    @property
    def solution_depth(self) -> Optional[int]:
        return len(self.solution_actions) if self.success else None


class SearchAlgorithm(ABC):
    """Abstract base class every search algorithm implements."""

    name: str = "search_algorithm"

    @abstractmethod
    def search(self, problem: SearchProblem, limits: SearchLimits) -> SearchResult:
        """Run the algorithm on `problem` honoring `limits` and return a SearchResult."""
