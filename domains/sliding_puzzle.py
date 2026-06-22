"""8-puzzle (sliding puzzle) domain."""
from __future__ import annotations

from typing import Iterable, Tuple

from .base import SearchProblem, Successor

# State is a flat tuple of length 9 (row-major), 0 represents the blank.
PuzzleState = Tuple[int, ...]

_SIZE = 3
GOAL_STATE: PuzzleState = (0, 1, 2, 3, 4, 5, 6, 7, 8)
_GOAL = GOAL_STATE


def _index_to_rc(index: int) -> Tuple[int, int]:
    return divmod(index, _SIZE)


def _rc_to_index(row: int, col: int) -> int:
    return row * _SIZE + col


class SlidingPuzzleProblem(SearchProblem):
    """8-puzzle: slide the blank tile up/down/left/right at cost 1."""

    name = "sliding_puzzle"

    def __init__(self, start: PuzzleState, goal: PuzzleState = _GOAL) -> None:
        if sorted(start) != list(range(9)):
            raise ValueError(f"Invalid puzzle state: {start}")
        self.start = start
        self.goal = goal
        # Precompute goal tile positions for the Manhattan-distance heuristic.
        self._goal_positions = {tile: _index_to_rc(i) for i, tile in enumerate(goal)}

    @property
    def initial_state(self) -> PuzzleState:
        return self.start

    def is_goal(self, state: PuzzleState) -> bool:
        return state == self.goal

    def successors(self, state: PuzzleState) -> Iterable[Successor]:
        blank_index = state.index(0)
        row, col = _index_to_rc(blank_index)
        moves = (
            (-1, 0, "up"),
            (1, 0, "down"),
            (0, -1, "left"),
            (0, 1, "right"),
        )
        for drow, dcol, action in moves:
            nrow, ncol = row + drow, col + dcol
            if 0 <= nrow < _SIZE and 0 <= ncol < _SIZE:
                target_index = _rc_to_index(nrow, ncol)
                new_state = list(state)
                new_state[blank_index], new_state[target_index] = (
                    new_state[target_index],
                    new_state[blank_index],
                )
                yield action, tuple(new_state), 1.0

    def heuristic(self, state: PuzzleState) -> float:
        total = 0
        for index, tile in enumerate(state):
            if tile == 0:
                continue
            row, col = _index_to_rc(index)
            grow, gcol = self._goal_positions[tile]
            total += abs(row - grow) + abs(col - gcol)
        return total
