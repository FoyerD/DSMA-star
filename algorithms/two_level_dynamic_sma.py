"""Two-Level Dynamic SMA*: RAM frontier + SQLite disk frontier + collapse.

This is our second proposed algorithm. It separates the frontier into three
tiers:

1. **RAM frontier** (`_ram`): the best `B_ram` active nodes, kept as plain
   Python objects.
2. **Disk frontier** (`_disk`, SQLite-backed): less-promising nodes spilled
   out of RAM when RAM exceeds `B_ram`. Spilling is *not* forgetting -- a
   spilled node's full (state, g, h, f) record is preserved and can be
   loaded back into RAM later if it becomes competitive.
3. **Collapsed**: nodes permanently forgotten (SMA*-style) once the total
   resident frontier (RAM + disk) exceeds `B_total`. Collapse always evicts
   the globally worst (highest-f) resident node, RAM or disk.

**Spill vs. collapse** -- the key distinction this algorithm is built
around: spilling moves a node out of RAM but keeps it fully recoverable on
disk; collapsing destroys it forever (after which the search can never
revisit it). RAM pressure triggers spills; only *total* (RAM+disk) pressure
triggers collapses. This is why the algorithm is still "SMA*-based" despite
the disk tier: collapse is deferred as long as possible, but the eviction
policy when it does happen is exactly SMA*'s "forget the worst node" rule.

LIMITATIONS / DOCUMENTED SIMPLIFICATIONS (research-grade, not textbook SMA*):

1. **No reopening / no parent revival.** Like `sma_star.py` and
   `dynamic_sma_collapse.py`, a state is only ever inserted into the
   frontier once (first-discovered path wins; tracked via the global
   `best_g` dictionary). Unlike textbook SMA*, an expanded node's parent is
   never reinstated as a re-expandable leaf after all its children are
   collapsed -- once collapsed, a subtree is gone for good. This keeps the
   disk-paging logic tractable. We still call this "SMA* backup behavior"
   in the loose sense that eviction always targets the worst available
   node; we do not implement the f-value backup-and-possible-revisit
   refinement for this two-level variant.
2. **`best_g` and the parent-pointer `node_store` are kept fully in RAM**
   (small dict of `node_id -> (parent_id, action)`), even when the
   corresponding frontier entry has been spilled to disk or collapsed. Only
   the heavier (state, g, h, f) frontier records are paged to disk. This
   matches the data layout described in the spec ("node_store ... for
   reconstructing solution paths" is listed as a RAM-resident structure
   distinct from `OPEN_RAM`/`OPEN_DISK`), and means RAM usage still grows
   slowly with total nodes generated even when the frontier itself is
   tightly bounded.
3. Because there is no reopening (#1), a disk node can never become
   "stale" in this implementation (no cheaper path is ever discovered for
   an already-seen state), so `stale_disk_nodes_skipped` is always 0 here.
   The field is kept on `SearchResult` for interface completeness and in
   case a future revision adds reopening.
4. The SQLite disk layer is experimental: one database file per run,
   created in a temp/cache directory and deleted afterward unless the
   caller asks to keep it (see `keep_disk` below).
"""
from __future__ import annotations

import itertools
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from domains.base import SearchProblem

from ._disk_store import DiskNodeRecord, DiskNodeStore
from ._run_utils import MemoryLimitError, NodeLimitError, RunTracker
from .base import SearchAlgorithm, SearchLimits, SearchResult

_INF = float("inf")


@dataclass
class _RamNode:
    node_id: int
    state: Any
    g: float
    h: float
    f: float
    depth: int


def _best_score(node: _RamNode):
    return (node.f, -node.g)


def _worst_score(node: _RamNode):
    return (-node.f, node.g)


class TwoLevelDynamicSMA(SearchAlgorithm):
    """RAM + disk two-tier frontier with dynamic RAM sizing. See module docstring."""

    name = "two_level_dynamic_sma"

    def __init__(self, keep_disk: bool = False, disk_dir: Optional[Path] = None) -> None:
        self.keep_disk = keep_disk
        self.disk_dir = disk_dir

    def search(self, problem: SearchProblem, limits: SearchLimits) -> SearchResult:
        result = SearchResult(
            algorithm_name=self.name,
            domain_name=getattr(problem, "name", "unknown"),
            instance_id="",
        )
        tracker = RunTracker.start(limits.max_nodes, limits.max_memory_mb)
        counter = itertools.count()

        b_ram_min = max(2, limits.two_level_min_ram_nodes)
        b_ram_max = max(b_ram_min, limits.two_level_max_ram_nodes)
        b_ram = min(max(limits.two_level_initial_ram_nodes, b_ram_min), b_ram_max)
        b_total = max(b_ram, limits.two_level_total_node_limit)

        if self.disk_dir is not None:
            self.disk_dir.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(prefix="two_level_sma_", suffix=".sqlite3", dir=str(self.disk_dir))
        else:
            fd, tmp_path = tempfile.mkstemp(prefix="two_level_sma_", suffix=".sqlite3")
        os.close(fd)
        disk = DiskNodeStore(Path(tmp_path))

        node_store: Dict[int, Tuple[Optional[int], Any]] = {}
        best_g: Dict[Any, float] = {}

        start = problem.initial_state
        start_key = problem.state_key(start)
        root = _RamNode(node_id=next(counter), state=start, g=0.0, h=problem.heuristic(start), f=problem.heuristic(start), depth=0)
        node_store[root.node_id] = (None, None)
        best_g[start_key] = 0.0
        ram: List[_RamNode] = [root]
        tracker.nodes_generated = 1

        nodes_expanded = 0
        nodes_collapsed = 0
        nodes_spilled_to_disk = 0
        nodes_loaded_from_disk = 0
        disk_batches_loaded = 0
        number_of_total_collapses = 0
        number_of_ram_increases = 0
        number_of_ram_decreases = 0
        duplicate_nodes_skipped = 0
        max_frontier_size = 1
        ram_capacity_initial = b_ram
        ram_capacity_peak = b_ram
        ram_capacity_min = b_ram

        spilled_epoch = 0
        loaded_epoch = 0
        generated_epoch = 0

        def spill_overflow() -> None:
            nonlocal nodes_spilled_to_disk, spilled_epoch
            while len(ram) > b_ram:
                worst = max(ram, key=_worst_score)
                ram.remove(worst)
                parent_id, action = node_store[worst.node_id]
                disk.insert_nodes(
                    [DiskNodeRecord(worst.node_id, parent_id, worst.state, action, worst.g, worst.h, worst.f, worst.depth)]
                )
                nodes_spilled_to_disk += 1
                spilled_epoch += 1

        def collapse_to_total_bound() -> bool:
            nonlocal nodes_collapsed, number_of_total_collapses
            while len(ram) + disk.count() > b_total:
                if disk.count() > 0:
                    victims = disk.pop_worst_batch(1)
                elif ram:
                    worst = max(ram, key=_worst_score)
                    ram.remove(worst)
                    victims = [worst]
                else:
                    return False
                if not victims:
                    return False
                nodes_collapsed += 1
                number_of_total_collapses += 1
            return True

        try:
            while True:
                tracker.check_limits()

                best_ram = min(ram, key=_best_score) if ram else None
                best_disk_meta = disk.peek_best()

                if best_disk_meta is not None and (best_ram is None or best_disk_meta.f <= best_ram.f):
                    batch_size = max(1, b_ram // 4)
                    loaded = disk.pop_best_batch(batch_size)
                    for rec in loaded:
                        ram.append(_RamNode(rec.node_id, rec.state, rec.g, rec.h, rec.f, rec.depth))
                    if loaded:
                        nodes_loaded_from_disk += len(loaded)
                        disk_batches_loaded += 1
                        loaded_epoch += len(loaded)
                    spill_overflow()
                    best_ram = min(ram, key=_best_score) if ram else None

                if best_ram is None:
                    result.error_message = result.error_message or "search space exhausted"
                    break

                leaf = best_ram
                if problem.is_goal(leaf.state):
                    result.success = True
                    result.solution_cost = leaf.g
                    result.solution_actions = self._reconstruct(node_store, leaf.node_id)
                    break

                ram.remove(leaf)
                nodes_expanded += 1
                for action, next_state, cost in problem.successors(leaf.state):
                    next_key = problem.state_key(next_state)
                    if next_key in best_g:
                        duplicate_nodes_skipped += 1
                        continue
                    new_g = leaf.g + cost
                    h = problem.heuristic(next_state)
                    if h == _INF:
                        continue  # pruned (e.g. detected Sokoban deadlock)
                    best_g[next_key] = new_g
                    node_id = next(counter)
                    node_store[node_id] = (leaf.node_id, action)
                    ram.append(_RamNode(node_id, next_state, new_g, h, new_g + h, leaf.depth + 1))
                    tracker.nodes_generated += 1
                    generated_epoch += 1

                spill_overflow()
                if not collapse_to_total_bound():
                    result.memory_limit_reached = True
                    break

                if generated_epoch >= max(1, limits.epoch_generated_nodes):
                    if spilled_epoch > 0.50 * b_ram or loaded_epoch > 0.25 * b_ram:
                        b_ram = min(2 * b_ram, b_ram_max)
                        number_of_ram_increases += 1
                    elif spilled_epoch < 0.10 * b_ram and loaded_epoch == 0:
                        b_ram = max(b_ram // 2, b_ram_min)
                        number_of_ram_decreases += 1
                        spill_overflow()
                    spilled_epoch = 0
                    loaded_epoch = 0
                    generated_epoch = 0
                    ram_capacity_peak = max(ram_capacity_peak, b_ram)
                    ram_capacity_min = min(ram_capacity_min, b_ram)

                max_frontier_size = max(max_frontier_size, len(ram) + disk.count())
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
            result.disk_peak_nodes = disk.peak_nodes
            result.disk_read_count = disk.read_count
            result.disk_write_count = disk.write_count
            result.disk_io_time_seconds = disk.io_time_seconds
            disk.close(delete_file=not self.keep_disk)

        result.runtime_seconds = tracker.elapsed()
        result.nodes_expanded = nodes_expanded
        result.nodes_generated = tracker.nodes_generated
        result.max_frontier_size = max_frontier_size
        result.max_depth_reached = (
            len(result.solution_actions) if result.success else max((n.depth for n in ram), default=0)
        )
        result.reexpansions = 0
        result.nodes_collapsed = nodes_collapsed
        result.nodes_spilled_to_disk = nodes_spilled_to_disk
        result.nodes_loaded_from_disk = nodes_loaded_from_disk
        result.disk_batches_loaded = disk_batches_loaded
        result.ram_capacity_initial = ram_capacity_initial
        result.ram_capacity_final = b_ram
        result.ram_capacity_peak = ram_capacity_peak
        result.ram_capacity_min = ram_capacity_min
        result.number_of_ram_increases = number_of_ram_increases
        result.number_of_ram_decreases = number_of_ram_decreases
        result.number_of_total_collapses = number_of_total_collapses
        result.stale_disk_nodes_skipped = 0  # see limitation #3 in module docstring
        result.duplicate_nodes_skipped = duplicate_nodes_skipped
        return result

    @staticmethod
    def _reconstruct(node_store: Dict[int, Tuple[Optional[int], Any]], leaf_node_id: int) -> List[Any]:
        actions: List[Any] = []
        node_id: Optional[int] = leaf_node_id
        while node_id is not None:
            parent_id, action = node_store[node_id]
            if parent_id is None:
                break
            actions.append(action)
            node_id = parent_id
        actions.reverse()
        return actions
