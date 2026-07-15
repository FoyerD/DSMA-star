"""Random and handcrafted instance generation for the n-puzzle and Sokoban domains."""
from __future__ import annotations

import csv
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from domains.n_puzzle import NPuzzleProblem, PuzzleState, goal_state
from domains.sokoban import SokobanProblem

DEFAULT_KORF_CSV = Path("korfs100.csv")


@dataclass
class NamedInstance:
    """A problem instance paired with a stable identifier and a difficulty label."""

    instance_id: str
    problem: object
    difficulty: str = "default"
    # Where this instance came from: "scramble" (random walk), "korf100" (fixed
    # historical 15-puzzle instance), "sokoban_handcrafted", etc.
    source: str = "synthetic"
    # True optimal solution depth, when known in advance (e.g. from korfs100.csv).
    # None means "unknown" -- most generated instances don't have this.
    optimal_depth: Optional[int] = None


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
                    source="scramble",
                )
            )

    return instances


# --------------------------------------------------------------------------
# Korf's 100 historical 15-puzzle instances (fixed instances, true optimal
# solution depth known in advance -- see korfs100.csv and the README section
# "Using Korf's 100 15-puzzle instances").
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class KorfPuzzleInstance:
    """One row of korfs100.csv: a fixed 15-puzzle start state with a known
    true optimal solution depth (as opposed to a scramble depth, which is not
    the same thing -- moves can cancel out during a random walk)."""

    instance_id: Union[str, int]
    state: PuzzleState
    optimal_depth: int


# Column-name aliases tolerated in korfs100.csv, in priority order.
_ID_COLUMNS = ("id", "index", "instance_id")
_STATE_COLUMNS = ("state",)
_DEPTH_COLUMNS = ("optimal_depth", "depth", "solution_depth", "optimal_solution_length")


def _find_column(fieldnames: Sequence[str], candidates: Sequence[str]) -> Optional[str]:
    normalized = {name.strip().lower(): name for name in fieldnames}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    return None


def _coerce_instance_id(raw: str) -> Union[str, int]:
    raw = raw.strip()
    try:
        return int(raw)
    except ValueError:
        return raw


def _parse_puzzle_state(raw: str) -> Tuple[int, ...]:
    """Parse a 15-puzzle state written as space-separated ("1 2 3 ..."),
    comma-separated ("1,2,3,..."), or a Python-list-like string
    ("[1, 2, 3, ...]")."""
    text = raw.strip().strip("[]")
    if "," in text:
        parts = [p.strip() for p in text.split(",") if p.strip() != ""]
    else:
        parts = text.split()
    if not parts:
        raise ValueError(f"empty state {raw!r}")
    return tuple(int(p) for p in parts)


def _validate_puzzle_state(state: Tuple[int, ...], instance_id: Any, size: int = 4) -> None:
    expected_count = size * size
    if len(state) != expected_count:
        raise ValueError(
            f"Korf instance {instance_id!r}: state has {len(state)} numbers, expected {expected_count}"
        )
    if sorted(state) != list(range(expected_count)):
        raise ValueError(
            f"Korf instance {instance_id!r}: state must contain exactly the numbers "
            f"0..{expected_count - 1}, got {state}"
        )


def load_korf_instances(csv_path: Path = DEFAULT_KORF_CSV) -> List[KorfPuzzleInstance]:
    """Parse korfs100.csv (or an equivalent CSV) into KorfPuzzleInstance rows.

    Tolerates a few column-name variants (see `_ID_COLUMNS`/`_STATE_COLUMNS`/
    `_DEPTH_COLUMNS`) and three `state` formats (space-separated,
    comma-separated, or a bracketed Python-list-like string).

    A malformed CSV *shape* (missing file, no header row, missing a required
    column) raises immediately -- that means the file isn't usable at all. A
    malformed individual *row*, however, is skipped with a printed warning
    rather than raising: the bundled korfs100.csv itself has a handful of
    rows with a tile missing (apparently lost in whatever process produced
    the file), and failing the entire load over a few bad rows would throw
    away the other ~97 perfectly good ones.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Korf instances CSV not found: {csv_path}")

    instances: List[KorfPuzzleInstance] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"Korf instances CSV has no header row: {csv_path}")

        id_col = _find_column(reader.fieldnames, _ID_COLUMNS)
        state_col = _find_column(reader.fieldnames, _STATE_COLUMNS)
        depth_col = _find_column(reader.fieldnames, _DEPTH_COLUMNS)
        missing = [
            label for label, col in (("id", id_col), ("state", state_col), ("optimal_depth", depth_col)) if col is None
        ]
        if missing:
            raise ValueError(
                f"Korf instances CSV {csv_path} is missing required column(s): {', '.join(missing)} "
                f"(accepted names: id={_ID_COLUMNS}, state={_STATE_COLUMNS}, optimal_depth={_DEPTH_COLUMNS})"
            )

        for line_number, raw_row in enumerate(reader, start=2):
            raw_id = (raw_row.get(id_col) or "").strip()
            if not raw_id:
                print(f"Skipping {csv_path}:{line_number}: missing {id_col!r} value")
                continue
            instance_id = _coerce_instance_id(raw_id)

            raw_state = raw_row.get(state_col) or ""
            try:
                state = _parse_puzzle_state(raw_state)
                _validate_puzzle_state(state, instance_id)
            except ValueError as exc:
                print(
                    f"Skipping Korf instance {instance_id!r} ({csv_path}:{line_number}): "
                    f"invalid state {raw_state!r}: {exc}"
                )
                continue

            raw_depth = (raw_row.get(depth_col) or "").strip()
            try:
                optimal_depth = int(raw_depth)
            except ValueError:
                print(
                    f"Skipping Korf instance {instance_id!r} ({csv_path}:{line_number}): "
                    f"optimal_depth {raw_depth!r} is not an integer"
                )
                continue

            instances.append(KorfPuzzleInstance(instance_id=instance_id, state=state, optimal_depth=optimal_depth))

    return instances


def _instance_id_sort_key(instance: KorfPuzzleInstance) -> Tuple[int, Any]:
    # Numeric ids sort numerically (1, 2, ..., 100), not lexicographically
    # ("10" before "2"); non-numeric ids fall back to string order after them.
    if isinstance(instance.instance_id, int):
        return (0, instance.instance_id)
    return (1, str(instance.instance_id))


def get_instance_by_optimal_depth(
    target_depth: int,
    seed: Optional[int] = None,
    csv_path: Path = DEFAULT_KORF_CSV,
) -> KorfPuzzleInstance:
    """Deterministically select one Korf instance with the given true optimal
    solution depth.

    - Loads every instance from `csv_path` and groups by `optimal_depth`.
    - If `target_depth` has matches: `seed is None` picks the first match
      sorted by `instance_id`; otherwise picks `matches[seed % len(matches)]`
      (matches sorted by `instance_id` first, so the choice is reproducible).
    - If `target_depth` has no matches: falls back to the closest available
      depth (ties broken toward the smaller depth), prints a warning, and
      applies the same seed-selection logic within that depth's matches.
    """
    instances = load_korf_instances(csv_path)
    if not instances:
        raise ValueError(f"No Korf instances loaded from {csv_path}")

    by_depth: Dict[int, List[KorfPuzzleInstance]] = defaultdict(list)
    for instance in instances:
        by_depth[instance.optimal_depth].append(instance)

    matches = by_depth.get(target_depth)
    if not matches:
        closest_depth = min(by_depth, key=lambda d: (abs(d - target_depth), d))
        print(f"No Korf instance with optimal_depth={target_depth}; using closest depth {closest_depth} instead.")
        matches = by_depth[closest_depth]

    matches = sorted(matches, key=_instance_id_sort_key)
    if seed is None:
        return matches[0]
    return matches[seed % len(matches)]


def generate_korf_puzzle_instances(
    optimal_depths: Sequence[int],
    seed: Optional[int] = None,
    csv_path: Path = DEFAULT_KORF_CSV,
) -> List[NamedInstance]:
    """Build one NamedInstance per requested true optimal depth, sourced from
    Korf's 100 historical 15-puzzle instances instead of a random scramble."""
    instances: List[NamedInstance] = []
    for depth in optimal_depths:
        korf_instance = get_instance_by_optimal_depth(depth, seed=seed, csv_path=csv_path)
        problem = NPuzzleProblem(korf_instance.state, size=4)
        instances.append(
            NamedInstance(
                instance_id=f"korf{korf_instance.instance_id}_d{korf_instance.optimal_depth}",
                problem=problem,
                difficulty=f"korf_depth_{korf_instance.optimal_depth}",
                source="korf100",
                optimal_depth=korf_instance.optimal_depth,
            )
        )
    return instances


def generate_npuzzle_instances(
    source: str = "scramble",
    *,
    seeds: Sequence[int] = (0,),
    size: int = 4,
    scramble_depths: Sequence[int] = (10, 20, 30, 40, 50),
    optimal_depths: Sequence[int] = (),
    korf_csv: Path = DEFAULT_KORF_CSV,
) -> List[NamedInstance]:
    """Single entry point for 15-puzzle instance generation, selecting between
    a random scramble (`source="scramble"`) and Korf's 100 fixed historical
    instances selected by true optimal depth (`source="korf"`).

    Korf mode is 15-puzzle only (`size` is ignored -- korfs100.csv states are
    always 4x4) and picks one instance per depth in `optimal_depths`, using
    `seeds[0]` (if any) as the deterministic tie-break seed for
    `get_instance_by_optimal_depth`.
    """
    if source == "korf":
        seed = seeds[0] if seeds else None
        return generate_korf_puzzle_instances(optimal_depths=optimal_depths, seed=seed, csv_path=korf_csv)
    if source == "scramble":
        return generate_puzzle_instances(seeds=seeds, size=size, scramble_depths=scramble_depths)
    raise ValueError(f"Unknown puzzle instance source: {source!r} (expected 'korf' or 'scramble')")


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
            NamedInstance(
                instance_id=f"sokoban_{difficulty}",
                problem=problem,
                difficulty=difficulty,
                source="sokoban_handcrafted",
            )
        )
    return instances
