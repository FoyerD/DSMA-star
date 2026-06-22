"""Generalized N-puzzle domain (default benchmark uses the 4x4 / 15-puzzle)."""
from __future__ import annotations

from typing import Iterable, Tuple

from .base import SearchProblem, Successor

# State is a flat tuple of length size*size (row-major), 0 represents the blank.
PuzzleState = Tuple[int, ...]


def goal_state(size: int) -> PuzzleState:
    return tuple(range(size * size))


class NPuzzleProblem(SearchProblem):
    """N-puzzle: slide the blank tile up/down/left/right at cost 1.

    `size=4` gives the 15-puzzle (the domain used for benchmarking); `size=3`
    gives the classic 8-puzzle. The heuristic is the sum of Manhattan
    distances of each tile from its goal position, which is admissible for
    unit-cost sliding-tile puzzles.
    """

    name = "n_puzzle"

    def __init__(self, start: PuzzleState, size: int = 4, goal: PuzzleState = None) -> None:
        self.size = size
        if goal is None:
            goal = goal_state(size)
        if sorted(start) != list(range(size * size)):
            raise ValueError(f"Invalid puzzle state for size {size}: {start}")
        self.start = start
        self.goal = goal
        self._goal_positions = {tile: divmod(i, size) for i, tile in enumerate(goal)}

    @property
    def initial_state(self) -> PuzzleState:
        return self.start

    def is_goal(self, state: PuzzleState) -> bool:
        return state == self.goal

    def successors(self, state: PuzzleState) -> Iterable[Successor]:
        size = self.size
        blank_index = state.index(0)
        row, col = divmod(blank_index, size)
        moves = (
            (-1, 0, "up"),
            (1, 0, "down"),
            (0, -1, "left"),
            (0, 1, "right"),
        )
        for drow, dcol, action in moves:
            nrow, ncol = row + drow, col + dcol
            if 0 <= nrow < size and 0 <= ncol < size:
                target_index = nrow * size + ncol
                new_state = list(state)
                new_state[blank_index], new_state[target_index] = (
                    new_state[target_index],
                    new_state[blank_index],
                )
                yield action, tuple(new_state), 1.0

    def heuristic(self, state: PuzzleState) -> float:
        size = self.size
        total = 0
        for index, tile in enumerate(state):
            if tile == 0:
                continue
            row, col = divmod(index, size)
            grow, gcol = self._goal_positions[tile]
            total += abs(row - grow) + abs(col - gcol)
        return total
