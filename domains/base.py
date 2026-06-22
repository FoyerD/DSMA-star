"""Generic search problem interface shared by all domains."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Hashable, Iterable, Tuple

# (action, next_state, cost)
Successor = Tuple[Any, Any, float]


class SearchProblem(ABC):
    """Abstract base class for a search problem instance.

    Algorithms only depend on this interface, never on a concrete domain.
    """

    name: str = "search_problem"

    @property
    @abstractmethod
    def initial_state(self) -> Any:
        """Return the starting state."""

    @abstractmethod
    def is_goal(self, state: Any) -> bool:
        """Return True if `state` is a goal state."""

    @abstractmethod
    def successors(self, state: Any) -> Iterable[Successor]:
        """Yield (action, next_state, cost) tuples reachable from `state`."""

    @abstractmethod
    def heuristic(self, state: Any) -> float:
        """Return an admissible heuristic estimate from `state` to the goal."""

    def state_key(self, state: Any) -> Hashable:
        """Return a hashable key identifying `state`. Defaults to the state itself."""
        return state
