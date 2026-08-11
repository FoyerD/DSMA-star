"""Scheduling policies for Multi-Path RBFS (mp-rbfs).

A scheduler owns no search logic at all -- it is handed the list of `_Proc`
objects (see `mp_rbfs.py`) once at construction, and thereafter is only
asked two things, once per single-node-expansion quantum:

    proc = scheduler.select_next()   # None means every proc is exhausted
    ...caller expands `proc` by exactly one node...
    scheduler.on_expanded(proc)      # proc.peek_f() / proc.active may differ now

Keeping this contract narrow is what lets a new scheduling policy be added
without touching `MPRBFS` or `_Proc` at all.
"""
from __future__ import annotations

import heapq
import itertools
import random
from abc import ABC, abstractmethod
from collections import deque
from typing import Callable, List, Optional, Sequence, Tuple

_EPS = 1e-6


class Scheduler(ABC):
    """Common interface for every mp-rbfs scheduling policy."""

    def __init__(self, procs: Sequence) -> None:
        self.procs: List = list(procs)

    @abstractmethod
    def select_next(self):
        """Return the next proc to expand, or None if every proc is exhausted."""

    @abstractmethod
    def on_expanded(self, proc) -> None:
        """Called immediately after `proc` performed exactly one expansion."""


class BestFirstScheduler(Scheduler):
    """Always selects the active proc exposing the smallest f: p* = argmin_p f(p).

    Selection avoids an O(P) scan across every proc via a scheduler-level
    heap of ``(f, seq, proc_id)`` entries. Every time a proc's exposed f
    changes (i.e. right after it is expanded) a fresh entry is pushed
    tagged with a new globally-monotonic sequence number, and that number
    is recorded as the proc's *current* one. An old heap entry is stale
    once a newer one has been pushed for the same proc; stale entries are
    discarded lazily when popped rather than removed eagerly, so both
    selection and update are amortized O(log P). Ties (equal f) resolve to
    whichever entry was pushed first (the lower sequence number), which is
    a fully deterministic order.
    """

    def __init__(self, procs: Sequence) -> None:
        super().__init__(procs)
        self._seq_counter = itertools.count()
        self._current_seq: List[int] = [-1] * len(self.procs)
        self._heap: List[Tuple[float, int, int]] = []
        for proc in self.procs:
            self._push(proc)

    def _push(self, proc) -> None:
        seq = next(self._seq_counter)
        self._current_seq[proc.proc_id] = seq
        heapq.heappush(self._heap, (proc.peek_f(), seq, proc.proc_id))

    def select_next(self):
        heap = self._heap
        current_seq = self._current_seq
        procs = self.procs
        while heap:
            _f, seq, pid = heap[0]
            if seq != current_seq[pid]:
                heapq.heappop(heap)
                continue
            proc = procs[pid]
            if not proc.active:
                heapq.heappop(heap)
                continue
            heapq.heappop(heap)
            return proc
        return None

    def on_expanded(self, proc) -> None:
        if proc.active:
            self._push(proc)
        # Exhausted: its previous heap entry (if any) is now permanently
        # stale and will simply be discarded the next time it surfaces.


class RoundRobinScheduler(Scheduler):
    """Gives every active proc exactly one expansion per full cycle, ignoring f.

    Backed by a deque of proc ids: pop-left to select, append-right to
    requeue only if the proc is still active after its expansion. A
    proc that becomes exhausted is simply never requeued, so dead procs
    cost O(1) once and are never scanned again.
    """

    def __init__(self, procs: Sequence) -> None:
        super().__init__(procs)
        self._queue: deque = deque(proc.proc_id for proc in self.procs)

    def select_next(self):
        procs = self.procs
        queue = self._queue
        while queue:
            pid = queue.popleft()
            proc = procs[pid]
            if proc.active:
                return proc
            # Exhausted since it was queued -- drop it, never requeue.
        return None

    def on_expanded(self, proc) -> None:
        if proc.active:
            self._queue.append(proc.proc_id)


class _Fenwick:
    """Fenwick tree (Binary Indexed Tree) over dense indices [0, n).

    Supports O(log n) point updates and O(log n) weighted sampling by
    cumulative sum -- used by `ProportionalScheduler` so that after a proc's
    weight changes (normally just the one that was just expanded) both the
    update and the next weighted draw stay O(log P) instead of O(P).
    """

    __slots__ = ("n", "tree", "total")

    def __init__(self, n: int) -> None:
        self.n = max(n, 1)
        self.tree = [0.0] * (self.n + 1)
        self.total = 0.0

    def update(self, index: int, delta: float) -> None:
        if delta == 0.0:
            return
        self.total += delta
        i = index + 1
        n = self.n
        tree = self.tree
        while i <= n:
            tree[i] += delta
            i += i & (-i)

    def sample(self, target: float) -> int:
        """0-based index of the element whose cumulative-weight bucket
        contains `target` (0 <= target < self.total)."""
        idx = 0
        remaining = target
        bitmask = 1
        while bitmask * 2 <= self.n:
            bitmask *= 2
        tree = self.tree
        n = self.n
        while bitmask:
            next_idx = idx + bitmask
            if next_idx <= n and tree[next_idx] <= remaining:
                idx = next_idx
                remaining -= tree[next_idx]
            bitmask >>= 1
        return idx


class ProportionalScheduler(Scheduler):
    """Samples an active proc with probability proportional to weight_fn(f).

    weight_fn is injected (default ``1 / (f + eps)``) precisely so the
    weighting formula can be swapped later (``1/f**2``, an exponential
    softmax on ``f - f_min``, etc.) without touching this class -- see
    `build_scheduler`'s `weight_power` knob for the one built-in variation.

    Weights live in a Fenwick tree keyed by dense proc_id. After an
    expansion only the single proc whose f just changed needs its weight
    touched, so both the update and the weighted sample are O(log P).
    """

    def __init__(
        self,
        procs: Sequence,
        rng: random.Random,
        weight_fn: Optional[Callable[[float], float]] = None,
    ) -> None:
        super().__init__(procs)
        self.rng = rng
        self.weight_fn = weight_fn or (lambda f: 1.0 / (f + _EPS))
        self._fenwick = _Fenwick(len(self.procs))
        self._weights: List[float] = [0.0] * len(self.procs)
        for proc in self.procs:
            self._sync_weight(proc)

    def _weight_for(self, proc) -> float:
        if not proc.active:
            return 0.0
        f = proc.peek_f()
        if f == float("inf"):
            return 0.0
        return max(0.0, self.weight_fn(f))

    def _sync_weight(self, proc) -> None:
        new_w = self._weight_for(proc)
        old_w = self._weights[proc.proc_id]
        if new_w != old_w:
            self._fenwick.update(proc.proc_id, new_w - old_w)
            self._weights[proc.proc_id] = new_w

    def select_next(self):
        if not self.procs:
            return None
        total = self._fenwick.total
        if total <= 0.0:
            return None
        r = self.rng.uniform(0.0, total)
        if r >= total:
            r = total - _EPS if total > _EPS else 0.0
        idx = self._fenwick.sample(r)
        return self.procs[idx]

    def on_expanded(self, proc) -> None:
        self._sync_weight(proc)


def build_scheduler(
    kind: str,
    procs: Sequence,
    *,
    seed: Optional[int] = None,
    weight_power: float = 1.0,
) -> Scheduler:
    """Factory used by `MPRBFS` (and the CLI) to build a scheduler by name."""
    if kind == "best_first":
        return BestFirstScheduler(procs)
    if kind == "round_robin":
        return RoundRobinScheduler(procs)
    if kind == "proportional":
        rng = random.Random(seed)
        weight_fn = (lambda f, p=weight_power: 1.0 / ((f + _EPS) ** p))
        return ProportionalScheduler(procs, rng, weight_fn=weight_fn)
    raise ValueError(
        f"Unknown mp-rbfs scheduler: {kind!r} (expected 'best_first', 'round_robin', or 'proportional')"
    )
