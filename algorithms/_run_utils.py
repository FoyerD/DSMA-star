"""Shared helpers for timing, memory tracking, and timeout checks across algorithms."""
from __future__ import annotations

import time
import tracemalloc
from dataclasses import dataclass


class TimeoutError_(Exception):
    """Raised internally when an algorithm exceeds its wall-clock budget."""


class NodeLimitError(Exception):
    """Raised internally when an algorithm exceeds the max-nodes budget."""


@dataclass
class RunTracker:
    """Tracks elapsed time, peak memory, and node-count budgets during a search."""

    start_time: float
    timeout_seconds: float
    max_nodes: int
    nodes_generated: int = 0

    @classmethod
    def start(cls, timeout_seconds: float, max_nodes: int) -> "RunTracker":
        tracemalloc.start()
        return cls(start_time=time.perf_counter(), timeout_seconds=timeout_seconds, max_nodes=max_nodes)

    def elapsed(self) -> float:
        return time.perf_counter() - self.start_time

    def check_timeout(self) -> None:
        if self.elapsed() > self.timeout_seconds:
            raise TimeoutError_()

    def check_node_limit(self) -> None:
        if self.nodes_generated > self.max_nodes:
            raise NodeLimitError()

    def peak_memory_mb(self) -> float:
        _, peak = tracemalloc.get_traced_memory()
        return peak / (1024 * 1024)

    def stop(self) -> float:
        peak_mb = self.peak_memory_mb()
        tracemalloc.stop()
        return peak_mb
