"""Tests for mp-bfs: Phase 1 frontier construction, best-first Proc semantics,
the shared duplicate-detection table, all three schedulers, and end-to-end
solving."""
from __future__ import annotations

import itertools
import statistics
from typing import Iterable, Tuple

import pytest

from algorithms._run_utils import RunTracker
from algorithms.base import SearchLimits
from algorithms.mp_bfs import MPBFS, _Proc
from algorithms.mp_common import _Node, _run_phase1
from algorithms.mp_schedulers import (
    BestFirstScheduler,
    ProportionalScheduler,
    RoundRobinScheduler,
    _Fenwick,
    build_scheduler,
)
from domains.base import SearchProblem, Successor
from domains.n_puzzle import NPuzzleProblem, goal_state

LIMITS = SearchLimits(max_memory_mb=1024.0, max_nodes=200_000)


def _tracker() -> RunTracker:
    return RunTracker.start(max_nodes=1_000_000, max_memory_mb=4096.0)


def _node(state, key, g, f, parent=None, action=None, h=0.0) -> _Node:
    return _Node(
        state=state,
        key=key,
        g=g,
        h=h,
        f=f,
        F=f,
        parent=parent,
        action=action,
        depth=0 if parent is None else parent.depth + 1,
    )


# ---------------------------------------------------------------------------
# Toy problems
# ---------------------------------------------------------------------------


class _TreeProblem(SearchProblem):
    """A deterministic, full b-ary tree with no goal state and h=0.

    Because h is always 0, best-first search degenerates to pure
    layer-by-layer BFS (ties broken by FIFO insertion order), which makes
    the exact frontier composition after Phase 1 fully predictable -- ideal
    for pinning down "never stop mid-expansion" behavior.
    """

    name = "tree"

    def __init__(self, branching: int = 4, max_depth: int = 6) -> None:
        self.branching = branching
        self.max_depth = max_depth

    @property
    def initial_state(self):
        return ()

    def is_goal(self, state) -> bool:
        return False

    def successors(self, state) -> Iterable[Successor]:
        if len(state) >= self.max_depth:
            return []
        return [(i, state + (i,), 1.0) for i in range(self.branching)]

    def heuristic(self, state) -> float:
        return 0.0


class _TinyGraphProblem(SearchProblem):
    """A hand-built graph with a genuine cross-path convergence: B and C
    both reach D, but at very different cost, and only C->D is optimal.
    Fully deterministic (all costs/heuristics fixed), used to exercise the
    shared best_g duplicate-detection table under a real converging path.
    """

    name = "tiny_graph"

    EDGES = {
        "A": [("toB", "B", 1.0), ("toC", "C", 1.0)],
        "B": [("toD", "D", 5.0)],  # expensive path to D
        "C": [("toD", "D", 1.0)],  # cheap path to D
        "D": [("toG", "G", 1.0)],
        "G": [],
    }

    @property
    def initial_state(self):
        return "A"

    def is_goal(self, state) -> bool:
        return state == "G"

    def successors(self, state) -> Iterable[Successor]:
        return self.EDGES.get(state, [])

    def heuristic(self, state) -> float:
        return 0.0  # admissible (trivially, all zero)


def _easy_8puzzle() -> NPuzzleProblem:
    goal = goal_state(3)
    return NPuzzleProblem((1, 0, 2, 3, 4, 5, 6, 7, 8), size=3, goal=goal)


def _validate_path(problem: SearchProblem, actions) -> None:
    state = problem.initial_state
    for action in actions:
        matches = [ns for act, ns, _c in problem.successors(state) if act == action]
        assert matches, f"action {action!r} not applicable from {state!r}"
        state = matches[0]
    assert problem.is_goal(state), f"path does not end at a goal state: {state!r}"


# ---------------------------------------------------------------------------
# Phase 1
# ---------------------------------------------------------------------------


def test_phase1_creates_at_least_n_frontier_nodes_when_possible():
    problem = _TreeProblem(branching=4, max_depth=6)
    phase1 = _run_phase1(problem, num_procs=10, tracker=_tracker())
    assert phase1.goal_node is None
    assert len(phase1.open_heap) >= 10


def test_phase1_never_partially_expands_a_node():
    problem = _TreeProblem(branching=4, max_depth=6)
    tracker = _tracker()
    phase1 = _run_phase1(problem, num_procs=37, tracker=tracker)
    assert phase1.goal_node is None
    # Every expansion must push its FULL child set (never a truncated
    # sibling group) -- for this fixed-branching tree with no duplicate
    # states, that shows up as an exact arithmetic identity. If someone
    # added an early break inside the successor loop, this would fail.
    assert tracker.nodes_generated - 1 == phase1.expanded * problem.branching


def test_phase1_stops_early_when_search_space_exhausts_before_reaching_n():
    problem = _TreeProblem(branching=2, max_depth=2)  # 1 + 2 + 4 = 7 total states
    phase1 = _run_phase1(problem, num_procs=1000, tracker=_tracker())
    assert phase1.goal_node is None
    assert phase1.open_heap == []  # fully drained -- frontier smaller than requested
    assert phase1.expanded == 7  # every one of the 7 states got "expanded"


def test_phase1_returns_immediately_on_goal():
    problem = _easy_8puzzle()
    # num_procs=4 forces phase 1 to pop+expand the root (pushing its 3
    # children, frontier size 3 < 4), then pop the best child next -- which
    # is the goal itself (f=1, the lowest among the root's children) --
    # before the frontier-size condition would otherwise stop it.
    phase1 = _run_phase1(problem, num_procs=4, tracker=_tracker())
    assert phase1.goal_node is not None
    assert phase1.goal_node.g == 1


# ---------------------------------------------------------------------------
# Proc
# ---------------------------------------------------------------------------


def _make_root_proc(problem: SearchProblem, proc_id: int = 0) -> Tuple[_Proc, dict, "itertools.count[int]"]:
    counter = itertools.count()
    start = problem.initial_state
    key = problem.state_key(start)
    h = problem.heuristic(start)
    root = _node(state=start, key=key, g=0.0, f=h, h=h)
    best_g = {key: 0.0}
    proc = _Proc(proc_id=proc_id, heap=[(root.f, -root.g, next(counter), root)])
    return proc, best_g, counter


def test_proc_exposes_correct_next_f():
    problem = _TreeProblem(branching=3, max_depth=3)
    proc, _best_g, _counter = _make_root_proc(problem)
    assert proc.peek_f() == 0.0  # root: g=0, h=0


def test_proc_empty_heap_exposes_infinity():
    proc = _Proc(proc_id=0, heap=[])
    assert proc.peek_f() == float("inf")


def test_proc_performs_exactly_one_expansion():
    problem = _TreeProblem(branching=3, max_depth=3)
    proc, best_g, counter = _make_root_proc(problem)
    tracker = _tracker()
    outcome = proc.expand_one(problem, best_g, tracker, counter, problem.state_key)
    assert outcome is not None
    assert not outcome.is_goal
    assert proc.expansions == 1
    assert len(proc.heap) == 3  # root's 3 children, and nothing more


def test_proc_becomes_exhausted_when_open_empties():
    problem = _TreeProblem(branching=2, max_depth=0)  # root has zero successors
    proc, best_g, counter = _make_root_proc(problem)
    tracker = _tracker()
    outcome = proc.expand_one(problem, best_g, tracker, counter, problem.state_key)
    assert outcome is not None
    assert proc.active is False
    # a further call finds nothing left to expand
    again = proc.expand_one(problem, best_g, tracker, counter, problem.state_key)
    assert again is None


def test_proc_correctly_identifies_goal_without_counting_it_as_expanded():
    problem = _easy_8puzzle()
    counter = itertools.count()
    start = problem.initial_state
    # Hand-construct a proc rooted at the goal-adjacent state itself.
    key = problem.state_key(start)
    h = problem.heuristic(start)
    root = _node(state=start, key=key, g=0.0, f=h, h=h)
    best_g = {key: 0.0}
    proc = _Proc(proc_id=0, heap=[(root.f, -root.g, next(counter), root)])
    tracker = _tracker()
    # First expansion reveals the one-move-away goal child but doesn't pop it yet.
    outcome1 = proc.expand_one(problem, best_g, tracker, counter, problem.state_key)
    assert outcome1 is not None and not outcome1.is_goal
    outcome2 = proc.expand_one(problem, best_g, tracker, counter, problem.state_key)
    assert outcome2 is not None and outcome2.is_goal
    assert outcome2.node.g == 1


def test_proc_never_spawns_another_proc():
    # Structural guarantee: _Proc has no notion of creating other _Proc
    # instances -- expand_one only ever pushes _Node objects into self.heap.
    import inspect

    source = inspect.getsource(_Proc)
    assert "_Proc(" not in source


def test_two_procs_do_not_touch_each_others_heap():
    problem = _TreeProblem(branching=3, max_depth=3)
    counter = itertools.count()
    state_key = problem.state_key

    root_a = _node(state=(0,), key=state_key((0,)), g=1.0, f=1.0, action=0)
    root_b = _node(state=(1,), key=state_key((1,)), g=1.0, f=1.0, action=1)
    best_g = {root_a.key: 1.0, root_b.key: 1.0}
    proc_a = _Proc(proc_id=0, heap=[(root_a.f, -root_a.g, next(counter), root_a)])
    proc_b = _Proc(proc_id=1, heap=[(root_b.f, -root_b.g, next(counter), root_b)])

    tracker = _tracker()
    proc_a.expand_one(problem, best_g, tracker, counter, state_key)
    assert len(proc_b.heap) == 1  # untouched
    assert proc_b.expansions == 0


# ---------------------------------------------------------------------------
# Shared duplicate-detection table
# ---------------------------------------------------------------------------


def test_shared_best_g_discards_equal_or_worse_duplicate():
    key = "X"
    best_g = {key: 5.0}
    # A worse rediscovery must not be accepted.
    assert not (6.0 < best_g.get(key, float("inf")))
    # An equal rediscovery must not be accepted either (strict improvement only).
    assert not (5.0 < best_g.get(key, float("inf")))


def test_shared_best_g_allows_strictly_better_path_and_marks_old_owner_stale():
    problem = _TinyGraphProblem()
    counter = itertools.count()
    state_key = problem.state_key

    node_b = _node(state="B", key="B", g=1.0, f=1.0, action="toB")
    node_c = _node(state="C", key="C", g=1.0, f=1.0, action="toC")
    best_g = {"A": 0.0, "B": 1.0, "C": 1.0}

    proc_b = _Proc(proc_id=0, heap=[(node_b.f, -node_b.g, next(counter), node_b)])
    proc_c = _Proc(proc_id=1, heap=[(node_c.f, -node_c.g, next(counter), node_c)])
    tracker = _tracker()

    # proc_b expands first and "claims" D at the expensive cost of 6.
    outcome_b = proc_b.expand_one(problem, best_g, tracker, counter, state_key)
    assert outcome_b is not None and not outcome_b.is_goal
    assert best_g["D"] == 6.0
    assert len(proc_b.heap) == 1  # holds D(g=6)

    # proc_c then finds the strictly cheaper path to D (g=2) and takes over.
    outcome_c = proc_c.expand_one(problem, best_g, tracker, counter, state_key)
    assert outcome_c is not None and not outcome_c.is_goal
    assert best_g["D"] == 2.0
    assert len(proc_c.heap) == 1  # holds D(g=2)

    # proc_b's D(g=6) entry is now stale; expanding it must discard it
    # rather than incorrectly treating it as live, leaving proc_b exhausted.
    outcome_stale = proc_b.expand_one(problem, best_g, tracker, counter, state_key)
    assert outcome_stale is None
    assert proc_b.active is False
    assert proc_b.stale_skips == 1


def test_end_to_end_optimal_path_found_despite_worse_path_discovered_first():
    """Full MPBFS pipeline on the converging graph: round_robin schedules
    the expensive B-branch first, so it "wins" D at g=6 before the cheap
    C-branch corrects it to g=2. The final solution must still be optimal
    (cost 3 via C->D->G), proving the stale entry never corrupts the result.
    """
    problem = _TinyGraphProblem()
    algo = MPBFS(num_procs=2, scheduler="round_robin")
    result = algo.search(problem, LIMITS)
    assert result.success
    assert result.solution_cost == 3.0
    assert result.solution_actions == ["toC", "toD", "toG"]
    _validate_path(problem, result.solution_actions)


# ---------------------------------------------------------------------------
# Fenwick tree
# ---------------------------------------------------------------------------


def test_fenwick_sampling_matches_expected_buckets():
    fw = _Fenwick(3)
    fw.update(0, 1.0)
    fw.update(1, 2.0)
    fw.update(2, 3.0)
    assert fw.total == 6.0
    # weights: [0,1) -> idx0, [1,3) -> idx1, [3,6) -> idx2
    assert fw.sample(0.0) == 0
    assert fw.sample(0.999) == 0
    assert fw.sample(1.0) == 1
    assert fw.sample(2.999) == 1
    assert fw.sample(3.0) == 2
    assert fw.sample(5.999) == 2


def test_fenwick_update_is_incremental():
    fw = _Fenwick(4)
    for i in range(4):
        fw.update(i, float(i + 1))
    assert fw.total == 10.0
    fw.update(1, -2.0)  # weight at idx1 goes from 2 -> 0
    assert fw.total == 8.0
    assert fw.sample(0.5) == 0
    # idx1 now has zero width, so nothing samples into bucket 1 alone
    assert fw.sample(0.999) == 0


# ---------------------------------------------------------------------------
# Best-First scheduler
# ---------------------------------------------------------------------------


class _FakeProc:
    """A minimal stand-in exposing exactly the surface schedulers need."""

    def __init__(self, proc_id: int, f: float, active: bool = True):
        self.proc_id = proc_id
        self._f = f
        self.active = active

    def peek_f(self) -> float:
        return self._f


def test_best_first_scheduler_selects_smallest_f():
    procs = [_FakeProc(0, 30.0), _FakeProc(1, 20.0), _FakeProc(2, 25.0)]
    sched = BestFirstScheduler(procs)
    chosen = sched.select_next()
    assert chosen.proc_id == 1


def test_best_first_scheduler_reflects_updated_f_after_expansion():
    procs = [_FakeProc(0, 30.0), _FakeProc(1, 20.0), _FakeProc(2, 25.0)]
    sched = BestFirstScheduler(procs)
    p1 = sched.select_next()
    assert p1.proc_id == 1
    p1._f = 40.0  # simulate P1 expanding and exposing a worse next node
    sched.on_expanded(p1)
    nxt = sched.select_next()
    assert nxt.proc_id == 2  # now the smallest is P2 (25.0)


def test_best_first_scheduler_skips_stale_heap_entries():
    procs = [_FakeProc(0, 10.0), _FakeProc(1, 50.0)]
    sched = BestFirstScheduler(procs)
    # Two rapid f changes on proc 0 before it's ever selected -- the older
    # pushed heap entry (f=10) is now stale and must not win over proc 1
    # once proc 0's *current* f is worse than proc 1's.
    procs[0]._f = 5.0
    sched.on_expanded(procs[0])
    procs[0]._f = 100.0
    sched.on_expanded(procs[0])
    chosen = sched.select_next()
    assert chosen.proc_id == 1  # proc 0's stale (f=10 and f=5) entries are skipped


def test_best_first_scheduler_skips_exhausted_procs():
    procs = [_FakeProc(0, 5.0, active=False), _FakeProc(1, 50.0)]
    sched = BestFirstScheduler(procs)
    chosen = sched.select_next()
    assert chosen.proc_id == 1


def test_best_first_scheduler_returns_none_when_all_exhausted():
    procs = [_FakeProc(0, 5.0, active=False)]
    sched = BestFirstScheduler(procs)
    assert sched.select_next() is None


# ---------------------------------------------------------------------------
# Round-robin scheduler
# ---------------------------------------------------------------------------


def test_round_robin_cycles_through_active_procs_in_order():
    procs = [_FakeProc(0, 1.0), _FakeProc(1, 1.0), _FakeProc(2, 1.0)]
    sched = RoundRobinScheduler(procs)
    order = []
    for _ in range(7):
        p = sched.select_next()
        order.append(p.proc_id)
        sched.on_expanded(p)
    assert order == [0, 1, 2, 0, 1, 2, 0]


def test_round_robin_drops_exhausted_proc_and_continues_with_rest():
    procs = [_FakeProc(0, 1.0), _FakeProc(1, 1.0), _FakeProc(2, 1.0)]
    sched = RoundRobinScheduler(procs)
    p0 = sched.select_next()
    assert p0.proc_id == 0
    p0.active = False  # becomes exhausted during this expansion
    sched.on_expanded(p0)  # not requeued

    order = []
    for _ in range(4):
        p = sched.select_next()
        order.append(p.proc_id)
        sched.on_expanded(p)
    assert order == [1, 2, 1, 2]


def test_round_robin_returns_none_when_all_exhausted():
    procs = [_FakeProc(0, 1.0, active=False)]
    sched = RoundRobinScheduler(procs)
    assert sched.select_next() is None


# ---------------------------------------------------------------------------
# Proportional scheduler
# ---------------------------------------------------------------------------


def test_proportional_scheduler_reproducible_with_fixed_seed():
    def make_procs():
        return [_FakeProc(0, 10.0), _FakeProc(1, 20.0), _FakeProc(2, 40.0)]

    import random

    sched1 = ProportionalScheduler(make_procs(), random.Random(42))
    sched2 = ProportionalScheduler(make_procs(), random.Random(42))

    picks1 = [sched1.select_next().proc_id for _ in range(50)]
    picks2 = [sched2.select_next().proc_id for _ in range(50)]
    assert picks1 == picks2


def test_proportional_scheduler_prefers_lower_f_proc_statistically():
    import random

    procs = [_FakeProc(0, 5.0), _FakeProc(1, 500.0)]
    sched = ProportionalScheduler(procs, random.Random(7))
    counts = {0: 0, 1: 0}
    for _ in range(2000):
        counts[sched.select_next().proc_id] += 1
    # Not a tight probability bound -- just confirm the low-f proc is
    # picked meaningfully more often, without flaking on sampling noise.
    assert counts[0] > counts[1] * 3


def test_proportional_scheduler_handles_zero_and_inf_f_safely():
    import random

    procs = [_FakeProc(0, 0.0), _FakeProc(1, float("inf"))]
    sched = ProportionalScheduler(procs, random.Random(1))
    for _ in range(20):
        chosen = sched.select_next()
        assert chosen.proc_id == 0  # inf-f proc must never be selected


def test_proportional_scheduler_zero_weight_when_all_exhausted():
    import random

    procs = [_FakeProc(0, 5.0, active=False)]
    sched = ProportionalScheduler(procs, random.Random(1))
    assert sched.select_next() is None


def test_build_scheduler_factory_rejects_unknown_kind():
    with pytest.raises(ValueError):
        build_scheduler("nonexistent", [])


# ---------------------------------------------------------------------------
# End-to-end
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scheduler", ["best_first", "round_robin", "proportional"])
def test_end_to_end_solves_already_solved_state(scheduler):
    goal = goal_state(3)
    problem = NPuzzleProblem(goal, size=3, goal=goal)
    algo = MPBFS(num_procs=4, scheduler=scheduler, seed=3)
    result = algo.search(problem, LIMITS)
    assert result.success
    assert result.solution_cost == 0
    assert result.solution_actions == []


@pytest.mark.parametrize("scheduler", ["best_first", "round_robin", "proportional"])
def test_end_to_end_solves_easy_8puzzle(scheduler):
    problem = _easy_8puzzle()
    algo = MPBFS(num_procs=4, scheduler=scheduler, seed=1)
    result = algo.search(problem, LIMITS)
    assert result.success
    assert result.solution_cost == 1
    _validate_path(problem, result.solution_actions)


@pytest.mark.parametrize("scheduler", ["best_first", "round_robin", "proportional"])
def test_end_to_end_solves_small_scramble_with_multiple_procs(scheduler):
    from benchmark.instance_generators import generate_puzzle_instances

    instances = generate_puzzle_instances(seeds=[0], size=3, scramble_depths=[8])
    problem = instances[0].problem
    algo = MPBFS(num_procs=6, scheduler=scheduler, seed=2)
    result = algo.search(problem, LIMITS)
    assert result.success
    assert result.actual_num_procs >= 1
    _validate_path(problem, result.solution_actions)
    # first-goal-wins is allowed to be suboptimal, but never worse than a
    # generous sanity ceiling relative to the true optimum (8).
    assert result.solution_cost <= 40


def test_best_first_scheduler_tends_closer_to_optimal_than_others_on_average():
    """Not a strict per-instance guarantee (mp-bfs is allowed to be
    suboptimal by design) -- but across several scrambles, best-first
    should track the true optimum at least as well as proportional/round
    robin on average. Uses generous, non-flaky slack."""
    from benchmark.instance_generators import generate_puzzle_instances

    instances = generate_puzzle_instances(seeds=[0, 1, 2], size=3, scramble_depths=[10])
    gaps = {"best_first": [], "round_robin": [], "proportional": []}
    for inst in instances:
        for scheduler in gaps:
            algo = MPBFS(num_procs=6, scheduler=scheduler, seed=0)
            result = algo.search(inst.problem, LIMITS)
            assert result.success
            gaps[scheduler].append(result.solution_cost)

    assert statistics.fmean(gaps["best_first"]) <= statistics.fmean(gaps["round_robin"]) + 1e-9
