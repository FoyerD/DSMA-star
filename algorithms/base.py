"""Generic search algorithm interface, plus shared result/limit dataclasses."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
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
    # Generic RAM-node budget some algorithms may use as a soft cap (currently advisory).
    max_ram_nodes: int = 200_000

    # SMA*'s memory limit is configured per-instance (see `SMAStar.__init__`),
    # not here, since a single benchmark run may include several SMA* instances
    # each bound to a different memory budget.

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

    # Total nodes in the optimal A* search tree for the current instance.
    # Used to resolve percentage-based MemoryLimit values at search time.
    total_nodes: int = 5_000_000

    def resolve_for_instance(
        self,
        total_nodes: int,
        dynamic_overrides: Optional[dict[str, MemoryLimit]] = None,
    ) -> SearchLimits:
        """Return a new SearchLimits with percentage-based limits resolved for an instance.

        ``dynamic_overrides`` maps field names (e.g. ``"dynamic_initial_ram_nodes"``)
        to unresolved ``MemoryLimit`` objects.  Any field present in the overrides
        is resolved via ``MemoryLimit.resolve(total_nodes)`` and set as an int;
        fields not in the overrides keep their current int values unchanged.
        """
        updates: dict[str, int] = {"total_nodes": total_nodes}
        if dynamic_overrides:
            for field_name, mem_limit in dynamic_overrides.items():
                updates[field_name] = mem_limit.resolve(total_nodes)
        return replace(self, **updates)


@dataclass
class SearchResult:
    """Outcome and metrics for a single (algorithm, problem instance) run."""

    algorithm_name: str
    domain_name: str
    instance_id: str
    # Not in the original spec's field list, but needed to group summaries by
    # difficulty (e.g. puzzle scramble depth, Sokoban easy/medium/hard).
    instance_difficulty: str = "default"
    # Where the instance came from ("scramble", "korf100", "sokoban_handcrafted",
    # ...) and its true optimal solution depth when known in advance (e.g. from
    # korfs100.csv); both are copied from NamedInstance by benchmark/runner.py.
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
    # Set when a recursive algorithm (e.g. ILBFS) hits a RecursionError --
    # the Python-safe proxy for "ran out of call stack" on a real stack overflow.
    stack_exhausted: bool = False
    error_message: Optional[str] = None

    # --- Instance metadata (copied from NamedInstance by runner) ---
    total_nodes_ida: Optional[int] = None
    total_nodes_a_approx: Optional[int] = None
    total_nodes_a: Optional[int] = None

    # --- Extra metrics for memory-bounded / two-level algorithms ---
    nodes_collapsed: int = 0
    # See dynamic_sma_collapse.py module docstring for exactly what counts as
    # "restored" -- 0 for every algorithm except Dynamic SMA*-Collapse.
    nodes_restored: int = 0
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
