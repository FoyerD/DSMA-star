"""2D grid pathfinding domain with obstacles."""
from __future__ import annotations

from typing import FrozenSet, Iterable, Tuple

from .base import SearchProblem, Successor

Coordinate = Tuple[int, int]

# (dx, dy, action_name)
_MOVES = (
    (0, -1, "up"),
    (0, 1, "down"),
    (-1, 0, "left"),
    (1, 0, "right"),
)


class GridProblem(SearchProblem):
    """Grid pathfinding: move up/down/left/right at cost 1, avoiding obstacles."""

    name = "grid"

    def __init__(
        self,
        width: int,
        height: int,
        start: Coordinate,
        goal: Coordinate,
        obstacles: FrozenSet[Coordinate],
    ) -> None:
        self.width = width
        self.height = height
        self.start = start
        self.goal = goal
        self.obstacles = obstacles

    @property
    def initial_state(self) -> Coordinate:
        return self.start

    def is_goal(self, state: Coordinate) -> bool:
        return state == self.goal

    def _in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def successors(self, state: Coordinate) -> Iterable[Successor]:
        x, y = state
        for dx, dy, action in _MOVES:
            nx, ny = x + dx, y + dy
            if self._in_bounds(nx, ny) and (nx, ny) not in self.obstacles:
                yield action, (nx, ny), 1.0

    def heuristic(self, state: Coordinate) -> float:
        x, y = state
        gx, gy = self.goal
        return abs(x - gx) + abs(y - gy)
