"""Sokoban-lite domain: push boxes onto goal squares.

State = (player_position, boxes) where boxes is a sorted tuple of box
coordinates. Walls and goals are fixed properties of the problem instance,
not part of the search state.
"""
from __future__ import annotations

from typing import FrozenSet, Iterable, Tuple

from .base import SearchProblem, Successor

Coordinate = Tuple[int, int]
SokobanState = Tuple[Coordinate, Tuple[Coordinate, ...]]

_DIRECTIONS = (
    (0, -1, "up"),
    (0, 1, "down"),
    (-1, 0, "left"),
    (1, 0, "right"),
)


class SokobanProblem(SearchProblem):
    """Push-block puzzle: move the player, pushing at most one box per step."""

    name = "sokoban"

    def __init__(
        self,
        width: int,
        height: int,
        walls: FrozenSet[Coordinate],
        goals: FrozenSet[Coordinate],
        player_start: Coordinate,
        boxes_start: FrozenSet[Coordinate],
        detect_deadlock: bool = True,
    ) -> None:
        self.width = width
        self.height = height
        self.walls = walls
        self.goals = goals
        self.player_start = player_start
        self.boxes_start = tuple(sorted(boxes_start))
        self.detect_deadlock = detect_deadlock
        self._corner_deadlock_cells = self._compute_corner_cells() if detect_deadlock else frozenset()

    @property
    def initial_state(self) -> SokobanState:
        return (self.player_start, self.boxes_start)

    def is_goal(self, state: SokobanState) -> bool:
        _player, boxes = state
        return set(boxes) == self.goals

    def _in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def _is_wall(self, x: int, y: int) -> bool:
        return not self._in_bounds(x, y) or (x, y) in self.walls

    def _compute_corner_cells(self) -> FrozenSet[Coordinate]:
        """Cells that are dead for a box (non-goal corner: two perpendicular walls)."""
        corners = set()
        for x in range(self.width):
            for y in range(self.height):
                if (x, y) in self.goals or self._is_wall(x, y):
                    continue
                horiz_blocked = self._is_wall(x - 1, y) or self._is_wall(x + 1, y)
                vert_blocked = self._is_wall(x, y - 1) or self._is_wall(x, y + 1)
                if horiz_blocked and vert_blocked:
                    corners.add((x, y))
        return frozenset(corners)

    def successors(self, state: SokobanState) -> Iterable[Successor]:
        player, boxes = state
        box_set = set(boxes)
        px, py = player

        for dx, dy, action in _DIRECTIONS:
            nx, ny = px + dx, py + dy
            if self._is_wall(nx, ny):
                continue
            if (nx, ny) in box_set:
                bx, by = nx + dx, ny + dy
                if self._is_wall(bx, by) or (bx, by) in box_set:
                    continue
                new_boxes = box_set - {(nx, ny)}
                new_boxes.add((bx, by))
                if self.detect_deadlock and (bx, by) in self._corner_deadlock_cells:
                    continue  # pushing into a dead corner can never reach the goal
                yield f"push_{action}", ((nx, ny), tuple(sorted(new_boxes))), 1.0
            else:
                yield f"move_{action}", ((nx, ny), boxes), 1.0

    def heuristic(self, state: SokobanState) -> float:
        _player, boxes = state
        if self.detect_deadlock and any(box not in self.goals and box in self._corner_deadlock_cells for box in boxes):
            return float("inf")
        if not self.goals:
            return 0.0
        total = 0.0
        for box in boxes:
            total += min(abs(box[0] - gx) + abs(box[1] - gy) for gx, gy in self.goals)
        return total
