"""Shared helpers for timing, real-memory tracking, and resource-limit checks
across algorithms.

There is deliberately no wall-clock timeout here. Comparing algorithms by
"who finished before an arbitrary stopwatch" structurally favors A* (it has
no memory-management overhead per node), which defeats the point of
benchmarking memory-bounded algorithms. Instead, a run only stops when it
either solves the problem or hits a *real* resource ceiling:

- `NodeLimitError` — a generous safety valve (`limits.max_nodes`) against a
  genuine infinite loop, not meant to be the binding constraint in practice.
- `MemoryLimitError` — the actual process RSS (via `psutil`, sampled
  periodically rather than every node to keep overhead low) crossed
  `limits.max_memory_mb`. This is the realistic "ran out of memory" signal.
- Python's own `RecursionError` (handled by callers, e.g. `ilbfs.py`) is the
  realistic "ran out of call stack" signal for recursive algorithms.
"""
from __future__ import annotations

import time
import tracemalloc
from dataclasses import dataclass, field
from typing import Optional

import psutil

# Querying process RSS is a syscall; only do it every N node-limit checks so
# it doesn't dominate runtime on algorithms that check limits every node.
_MEMORY_CHECK_INTERVAL = 256


class NodeLimitError(Exception):
    """Raised internally when an algorithm exceeds the max-nodes safety valve."""


class MemoryLimitError(Exception):
    """Raised internally when the process's real (RSS) memory exceeds the configured ceiling."""


@dataclass
class RunTracker:
    """Tracks elapsed time, real memory usage, and the node-count safety valve."""

    start_time: float
    max_nodes: int
    max_memory_mb: float
    nodes_generated: int = 0
    peak_rss_mb: float = 0.0
    _process: Optional[psutil.Process] = field(default=None, repr=False)
    _check_count: int = 0

    @classmethod
    def start(cls, max_nodes: int, max_memory_mb: float) -> "RunTracker":
        tracemalloc.start()
        process = psutil.Process()
        tracker = cls(
            start_time=time.perf_counter(),
            max_nodes=max_nodes,
            max_memory_mb=max_memory_mb,
            _process=process,
        )
        tracker.peak_rss_mb = process.memory_info().rss / (1024 * 1024)
        return tracker

    def elapsed(self) -> float:
        return time.perf_counter() - self.start_time

    def check_node_limit(self) -> None:
        if self.nodes_generated > self.max_nodes:
            raise NodeLimitError()

    def check_memory_limit(self) -> None:
        self._check_count += 1
        if self._check_count % _MEMORY_CHECK_INTERVAL != 0:
            return
        rss_mb = self._process.memory_info().rss / (1024 * 1024)
        if rss_mb > self.peak_rss_mb:
            self.peak_rss_mb = rss_mb
        if rss_mb > self.max_memory_mb:
            raise MemoryLimitError()

    def check_limits(self) -> None:
        """Call once per loop iteration: cheap node-count check + sampled real-memory check."""
        self.check_node_limit()
        self.check_memory_limit()

    def peak_memory_mb(self) -> float:
        _, tracemalloc_peak = tracemalloc.get_traced_memory()
        tracemalloc_mb = tracemalloc_peak / (1024 * 1024)
        # Report whichever signal is larger: tracemalloc only sees Python-object
        # allocations, while peak_rss_mb is sampled real process memory and may
        # miss a spike between samples -- taking the max is a safe estimate.
        return max(tracemalloc_mb, self.peak_rss_mb)

    def stop(self) -> float:
        peak_mb = self.peak_memory_mb()
        tracemalloc.stop()
        return peak_mb
