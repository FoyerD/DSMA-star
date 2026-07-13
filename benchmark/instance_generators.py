"""Random and handcrafted instance generation for the n-puzzle and Sokoban domains."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Sequence

from domains.n_puzzle import NPuzzleProblem, goal_state
from domains.sokoban import SokobanProblem


@dataclass
class NamedInstance:
    """A problem instance paired with a stable identifier and a difficulty label."""

    instance_id: str
    problem: object
    difficulty: str = "default"


def _combined_seed(seed: int, depth: int) -> int:
    """Derive a per-(seed, depth) RNG seed so every depth gets its own independent
    scramble stream even when the same seed value is reused across depths."""
    return (seed * 1_000_003) ^ (depth * 97 + 1)


def generate_puzzle_instances(
    seeds: Sequence[int],
    size: int,
    scramble_depths: Sequence[int],
) -> List[NamedInstance]:
    """Generate one solvable n-puzzle instance per (scramble_depth, seed) pair by
    random-walking away from the goal.

    Each (depth, seed) pair gets its own `random.Random` stream (see
    `_combined_seed`), so passing the same list of `seeds` always reproduces the
    exact same set of instances regardless of instance/algorithm ordering.

    NOTE: with `size=4` (the 15-puzzle, used by default) deeper scrambles are
    genuinely hard. A* is only expected to solve the easy/moderate depths
    (e.g. 10, 20) within typical benchmark limits -- see the README.
    """
    depths = list(scramble_depths) if scramble_depths else [10]
    seed_list = list(seeds) if seeds else [0]
    goal = goal_state(size)

    instances: List[NamedInstance] = []
    for depth in depths:
        for seed in seed_list:
            rng = random.Random(_combined_seed(seed, depth))
            state = goal
            last_state = None
            for _ in range(depth):
                moves = list(NPuzzleProblem(state, size=size).successors(state))
                candidates = [m for m in moves if m[1] != last_state] or moves
                _action, next_state, _cost = rng.choice(candidates)
                last_state = state
                state = next_state
            problem = NPuzzleProblem(state, size=size)
            instances.append(
                NamedInstance(
                    instance_id=f"puzzle{size}x{size}_d{depth}_seed{seed}",
                    problem=problem,
                    difficulty=f"depth_{depth}",
                )
            )

    return instances


def _parse_sokoban_level(level: str) -> SokobanProblem:
    """Parse a Sokoban ASCII level.

    Symbols: '#' wall, '.' goal, '$' box, '*' box on goal, '@' player,
    '+' player on goal, ' ' floor.
    """
    rows = level.strip("\n").split("\n")
    height = len(rows)
    width = max(len(row) for row in rows)
    walls, goals, boxes = set(), set(), set()
    player = None
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "#":
                walls.add((x, y))
            elif ch == ".":
                goals.add((x, y))
            elif ch == "$":
                boxes.add((x, y))
            elif ch == "*":
                goals.add((x, y))
                boxes.add((x, y))
            elif ch == "@":
                player = (x, y)
            elif ch == "+":
                goals.add((x, y))
                player = (x, y)
    if player is None:
        raise ValueError("Sokoban level has no player start ('@' or '+')")
    return SokobanProblem(
        width=width,
        height=height,
        walls=frozenset(walls),
        goals=frozenset(goals),
        player_start=player,
        boxes_start=frozenset(boxes),
    )


# Handcrafted levels of increasing difficulty. "hard" is intentionally large
# (4 boxes) -- it is meant to stress memory-bounded algorithms, not to be
# guaranteed solvable within tight limits; see the README.
_SOKOBAN_LEVELS = {
    "easy": """
#####
#.$@#
#####
""",
    "medium": """
#######
#.   .#
# $ $ #
#  @  #
#######
""",
    "hard": """
#########
#.     .#
# $   $ #
#       #
# $   $ #
#.  @  .#
#########
""",
}


def generate_sokoban_instances(levels: Sequence[str] = ("easy", "medium", "hard")) -> List[NamedInstance]:
    """Build NamedInstance objects for the requested handcrafted Sokoban levels."""
    instances: List[NamedInstance] = []
    for difficulty in levels:
        level_text = _SOKOBAN_LEVELS[difficulty]
        problem = _parse_sokoban_level(level_text)
        instances.append(
            NamedInstance(instance_id=f"sokoban_{difficulty}", problem=problem, difficulty=difficulty)
        )
    return instances
