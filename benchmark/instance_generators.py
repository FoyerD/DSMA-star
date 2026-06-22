"""Random instance generation for the grid and sliding-puzzle domains."""
from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass
from typing import List, Sequence, Tuple

from domains.grid import GridProblem
from domains.sliding_puzzle import GOAL_STATE, SlidingPuzzleProblem


@dataclass
class NamedInstance:
    """A problem instance paired with a stable identifier for reporting."""

    instance_id: str
    problem: object


def _grid_is_solvable(problem: GridProblem) -> bool:
    """Quick BFS reachability check used to reject unsolvable random grids."""
    frontier = deque([problem.start])
    seen = {problem.start}
    while frontier:
        state = frontier.popleft()
        if state == problem.goal:
            return True
        for _action, next_state, _cost in problem.successors(state):
            if next_state not in seen:
                seen.add(next_state)
                frontier.append(next_state)
    return False


def generate_grid_instances(
    count: int,
    width: int,
    height: int,
    obstacle_prob: float,
    seed: int,
    reject_unsolvable: bool = True,
    max_attempts_per_instance: int = 200,
) -> List[NamedInstance]:
    """Generate `count` random grid instances with start/goal guaranteed unblocked."""
    rng = random.Random(seed)
    instances: List[NamedInstance] = []

    for i in range(count):
        problem = None
        for _attempt in range(max_attempts_per_instance):
            start = (0, 0)
            goal = (width - 1, height - 1)
            obstacles = {
                (x, y)
                for x in range(width)
                for y in range(height)
                if rng.random() < obstacle_prob and (x, y) not in (start, goal)
            }
            candidate = GridProblem(width, height, start, goal, frozenset(obstacles))
            if not reject_unsolvable or _grid_is_solvable(candidate):
                problem = candidate
                break
        if problem is None:
            # Fall back to an obstacle-free grid so we always return `count` instances.
            problem = GridProblem(width, height, (0, 0), (width - 1, height - 1), frozenset())
        instances.append(NamedInstance(instance_id=f"grid_{i:03d}", problem=problem))

    return instances


def generate_puzzle_instances(
    count: int,
    scramble_depths: Sequence[int],
    seed: int,
) -> List[NamedInstance]:
    """Generate solvable 8-puzzle instances by random-walking away from the goal."""
    rng = random.Random(seed)
    instances: List[NamedInstance] = []

    depths = list(scramble_depths) if scramble_depths else [10]
    for i in range(count):
        depth = depths[i % len(depths)]
        state = GOAL_STATE
        last_blank_from = None
        helper = SlidingPuzzleProblem(GOAL_STATE)
        for _ in range(depth):
            moves = list(helper.successors(state))
            if last_blank_from is not None:
                moves = [m for m in moves if m[1] != last_blank_from] or moves
            action, next_state, _cost = rng.choice(moves)
            last_blank_from = state
            state = next_state
        problem = SlidingPuzzleProblem(state)
        instances.append(NamedInstance(instance_id=f"puzzle_d{depth}_{i:03d}", problem=problem))

    return instances
