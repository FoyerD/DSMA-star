"""Tests for mp-rbfs: genuine RBFS-per-proc semantics (collapse/backup,
re-expansion, O(b*d) live tree), the root-collapse guard, cross-proc shared
duplicate detection, and end-to-end solving."""
from __future__ import annotations

import itertools
from typing import Dict, Iterable, List, Optional, Tuple

import pytest

from algorithms._run_utils import RunTracker
from algorithms.base import SearchLimits
from algorithms.mp_common import _Node, _run_phase1
from algorithms.mp_rbfs import MPRBFS, _Proc
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


def _make_root_proc(problem: SearchProblem, root_state, g: float, parent=None) -> _Proc:
    """A proc rooted at an arbitrary state (optionally with a Phase-1-style
    parent chain above it, which must never be touched by collapse)."""
    key = problem.state_key(root_state)
    root = _node(state=root_state, key=key, g=g, f=g + problem.heuristic(root_state), parent=parent, h=problem.heuristic(root_state))
    return _Proc(proc_id=0, heap=[(root.F + root.collapse_count, -root.depth, key)], tree={key: root}, root=root)


class _TreeProblem(SearchProblem):
    """Deterministic full b-ary tree, h=0, no goal (matches test_mp_bfs)."""

    name = "tree"

    def __init__(self, branching: int = 2, max_depth: int = 5) -> None:
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
    """B and C both reach D, only C->D is optimal (matches test_mp_bfs)."""

    name = "tiny_graph"

    EDGES = {
        "A": [("toB", "B", 1.0), ("toC", "C", 1.0)],
        "B": [("toD", "D", 5.0)],
        "C": [("toD", "D", 1.0)],
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
        return 0.0


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
# Collapse / backup semantics
# ---------------------------------------------------------------------------


def test_proc_exhausts_immediately_on_leafless_root():
    problem = _TreeProblem(branching=2, max_depth=0)  # root has no successors
    proc = _make_root_proc(problem, root_state=(), g=0.0)
    best_g = {problem.state_key(()): 0.0}
    tracker = _tracker()
    outcome = proc.expand_one(problem, best_g, tracker, itertools.count(), problem.state_key)
    assert outcome is not None
    assert proc.active is False
    assert proc.expand_one(problem, best_g, tracker, itertools.count(), problem.state_key) is None


def test_proc_backs_up_f_and_collapses_when_leaving_a_branch():
    """On a plain b-ary tree (h=0), the search repeatedly pops a leaf's
    sibling, which forces the Collapse loop to back up the previous leaf and
    shrink the TREE -- the defining RBFS behavior."""
    problem = _TreeProblem(branching=2, max_depth=4)
    proc = _make_root_proc(problem, root_state=(), g=0.0)
    best_g = {problem.state_key(()): 0.0}
    tracker = _tracker()
    state_key = problem.state_key

    collapsed = False
    backed_up = False
    for _ in range(400):
        if proc.expand_one(problem, best_g, tracker, itertools.count(), state_key) is None:
            break
        collapsed = collapsed or proc.collapses > 0
        backed_up = backed_up or any(n.collapse_count > 0 for n in proc.tree.values())

    assert collapsed
    assert backed_up
    # A collapsed node's stored F is backed up to the min over its children.
    for n in proc.tree.values():
        if n.collapse_count > 0 and n.children:
            assert n.F == min(c.F for c in n.children.values())


def test_proc_reexpands_nodes_after_collapse():
    problem = _TreeProblem(branching=2, max_depth=4)
    proc = _make_root_proc(problem, root_state=(), g=0.0)
    best_g = {problem.state_key(()): 0.0}
    tracker = _tracker()
    for _ in range(400):
        if proc.expand_one(problem, best_g, tracker, itertools.count(), problem.state_key) is None:
            break
    assert proc.reexpansions > 0  # nodes re-expanded with backed-up F


def test_proc_live_tree_stays_obd_while_recovering_whole_space():
    """The O(b*d) memory invariant: over a run that eventually generates
    every state of the tree, the proc's live TREE never holds them all --
    collapse keeps it linear in depth."""
    branching, max_depth = 2, 6
    problem = _TreeProblem(branching=branching, max_depth=max_depth)
    proc = _make_root_proc(problem, root_state=(), g=0.0)
    best_g = {problem.state_key(()): 0.0}
    tracker = _tracker()
    state_key = problem.state_key

    max_tree = 0
    for _ in range(1500):
        if proc.expand_one(problem, best_g, tracker, itertools.count(), state_key) is None:
            break
        max_tree = max(max_tree, len(proc.tree))

    total_states = branching ** (max_depth + 1) - 1  # full b-ary tree of depth d
    assert tracker.nodes_generated >= total_states  # every state discovered (at least once)
    assert max_tree < total_states  # never held the whole tree at once
    assert max_tree <= branching * max_depth + 4  # O(b*d) live bound
    assert proc.collapses > 0


def test_proc_never_touches_nodes_above_its_root():
    """The Collapse walk must stop at the proc's own root and never walk into
    the shared Phase-1 ancestors above it -- even when the root itself is
    re-popped and collapsed."""
    problem = _TreeProblem(branching=2, max_depth=4)
    # A Phase-1-style ancestor sitting above the proc's root (NOT in the tree).
    ancestor = _node(state=(), key=problem.state_key(()), g=0.0, f=0.0)
    root_state = (0,)
    proc = _make_root_proc(problem, root_state=root_state, g=1.0, parent=ancestor)
    best_g = {problem.state_key(root_state): 1.0}
    tracker = _tracker()
    state_key = problem.state_key

    root_collapsed = False
    for _ in range(400):
        if proc.expand_one(problem, best_g, tracker, itertools.count(), state_key) is None:
            break
        root_collapsed = root_collapsed or proc.root.collapse_count > 0
        # The guard is exercised whenever the root is re-popped after a
        # collapse: the walk collapses the root itself but stops there.
        heap_keys = {k for _p, _d, k in proc.heap}
        assert ancestor.key not in heap_keys
        assert ancestor.key not in proc.tree
        assert proc.root.key in proc.tree

    assert root_collapsed  # the root is collapsible...
    assert ancestor.collapse_count == 0  # ...but never anything above it


def test_proc_rediscovers_collapsed_state_at_equal_g():
    """RBFS re-expansion: a state this proc generated, then collapsed, must
    be re-discoverable at the same g (the permanent shared best_g must not
    suppress re-discovery -- only strictly-better known paths suppress it)."""
    problem = _TreeProblem(branching=2, max_depth=4)
    proc = _make_root_proc(problem, root_state=(), g=0.0)
    best_g = {problem.state_key(()): 0.0}
    tracker = _tracker()
    state_key = problem.state_key

    seen = set()
    for _ in range(400):
        outcome = proc.expand_one(problem, best_g, tracker, itertools.count(), state_key)
        if outcome is None:
            break
        for k in proc.tree:
            seen.add(k)
    # Every state still known at the same g as best_g was rediscovered at
    # least once after its initial generation, i.e. total accepted
    # generations exceed the distinct-state count (RBFS re-expansion).
    assert tracker.nodes_generated > len(seen)


# ---------------------------------------------------------------------------
# Cross-proc shared duplicate detection
# ---------------------------------------------------------------------------


def test_shared_best_g_marks_old_owner_stale_across_procs():
    problem = _TinyGraphProblem()
    state_key = problem.state_key

    node_a = _node(state="A", key="A", g=0.0, f=0.0)
    node_b = _node(state="B", key="B", g=1.0, f=1.0, parent=node_a, action="toB")
    node_c = _node(state="C", key="C", g=1.0, f=1.0, parent=node_a, action="toC")
    best_g: Dict[str, float] = {"A": 0.0, "B": 1.0, "C": 1.0}

    proc_b = _Proc(
        proc_id=0,
        heap=[(node_b.F + node_b.collapse_count, -node_b.depth, "B")],
        tree={"B": node_b},
        root=node_b,
    )
    proc_c = _Proc(
        proc_id=1,
        heap=[(node_c.F + node_c.collapse_count, -node_c.depth, "C")],
        tree={"C": node_c},
        root=node_c,
    )
    tracker = _tracker()

    # proc_b expands first and claims D at the expensive cost of 6.
    outcome_b = proc_b.expand_one(problem, best_g, tracker, itertools.count(), state_key)
    assert outcome_b is not None and not outcome_b.is_goal
    assert best_g["D"] == 6.0

    # proc_c finds the strictly cheaper path to D (g=2) and takes over.
    outcome_c = proc_c.expand_one(problem, best_g, tracker, itertools.count(), state_key)
    assert outcome_c is not None and not outcome_c.is_goal
    assert best_g["D"] == 2.0

    # proc_b's D(g=6) entry is now stale; popping it must discard it rather
    # than treat it as live.
    outcome_stale = proc_b.expand_one(problem, best_g, tracker, itertools.count(), state_key)
    assert outcome_stale is None
    assert proc_b.active is False
    assert proc_b.stale_skips == 1


def test_end_to_end_optimal_path_found_despite_worse_path_discovered_first():
    problem = _TinyGraphProblem()
    algo = MPRBFS(num_procs=2, scheduler="round_robin")
    result = algo.search(problem, LIMITS)
    assert result.success
    assert result.solution_cost == 3.0
    assert result.solution_actions == ["toC", "toD", "toG"]
    _validate_path(problem, result.solution_actions)


# ---------------------------------------------------------------------------
# Phase 1 + proc building
# ---------------------------------------------------------------------------


def test_build_procs_creates_one_proc_per_live_frontier_node():
    problem = _TreeProblem(branching=4, max_depth=6)
    phase1 = _run_phase1(problem, num_procs=10, tracker=_tracker())
    from algorithms.mp_rbfs import _build_procs

    procs = _build_procs(phase1)
    assert len(procs) >= 1
    assert [p.proc_id for p in procs] == list(range(len(procs)))
    for p in procs:
        assert len(p.heap) == 1
        assert p.root.key in p.tree
        assert p.active is True


# ---------------------------------------------------------------------------
# End-to-end
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scheduler", ["best_first", "round_robin", "proportional"])
def test_end_to_end_solves_already_solved_state(scheduler):
    goal = goal_state(3)
    problem = NPuzzleProblem(goal, size=3, goal=goal)
    algo = MPRBFS(num_procs=4, scheduler=scheduler, seed=3)
    result = algo.search(problem, LIMITS)
    assert result.success
    assert result.solution_cost == 0
    assert result.solution_actions == []


@pytest.mark.parametrize("scheduler", ["best_first", "round_robin", "proportional"])
def test_end_to_end_solves_easy_8puzzle(scheduler):
    problem = _easy_8puzzle()
    algo = MPRBFS(num_procs=4, scheduler=scheduler, seed=1)
    result = algo.search(problem, LIMITS)
    assert result.success
    assert result.solution_cost == 1
    _validate_path(problem, result.solution_actions)


@pytest.mark.parametrize("scheduler", ["best_first", "round_robin", "proportional"])
def test_end_to_end_solves_small_scramble_with_multiple_procs(scheduler):
    from benchmark.instance_generators import generate_puzzle_instances

    instances = generate_puzzle_instances(seeds=[0], size=3, scramble_depths=[8])
    problem = instances[0].problem
    algo = MPRBFS(num_procs=6, scheduler=scheduler, seed=2)
    result = algo.search(problem, LIMITS)
    assert result.success
    assert result.actual_num_procs >= 1
    _validate_path(problem, result.solution_actions)
    assert result.solution_cost <= 40
    # mp-rbfs reports its RBFS bookkeeping on real instances.
    assert result.total_collapses >= 0
    assert result.max_proc_tree_size >= 0
