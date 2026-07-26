"""Generate 15-puzzle instances with known true optimal depths (21-40).

For each target depth d, escalates scramble depth until A* confirms an
instance whose optimal solution depth is exactly d.

Usage:
    python scripts/generate_depths21_40.py
"""
from __future__ import annotations

import csv
import random
import sys
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from algorithms import AStar
from algorithms.base import SearchLimits
from benchmark.instance_generators import (
    _combined_seed,
    generate_puzzle_instances,
)
from domains.n_puzzle import NPuzzleProblem, PuzzleState, goal_state


TARGET_DEPTHS = list(range(21, 41))
TRIES_PER_SCRAMBLE_DEPTH = 10
MAX_SCRAMBLE_DEPTH = 80
OUTPUT_DIR = Path("instances")
OUTPUT_FILE = OUTPUT_DIR / "puzzle_amit_depths21_40.csv"


def find_instance_with_optimal_depth(
    target_depth: int,
    astar: AStar,
    limits: SearchLimits,
) -> Optional[Tuple[PuzzleState, int]]:
    """Find one puzzle instance whose true optimal depth equals target_depth.

    Starts at scramble_depth = target_depth and escalates if needed.
    Returns (state, optimal_depth) or None if nothing found within limits.
    """
    for scramble_depth in range(target_depth, MAX_SCRAMBLE_DEPTH + 1):
        for seed_offset in range(TRIES_PER_SCRAMBLE_DEPTH):
            seed = seed_offset
            rng = random.Random(_combined_seed(seed, scramble_depth))
            state = goal_state(4)
            last_state = None
            for _ in range(scramble_depth):
                moves = list(NPuzzleProblem(state, size=4).successors(state))
                candidates = [m for m in moves if m[1] != last_state] or moves
                _action, next_state, _cost = rng.choice(candidates)
                last_state = state
                state = next_state

            problem = NPuzzleProblem(state, size=4)
            result = astar.search(problem, limits)
            if result.success:
                optimal_depth = int(result.solution_cost)
                if optimal_depth == target_depth:
                    print(
                        f"  Found optimal_depth={target_depth} at scramble_depth={scramble_depth} "
                        f"(seed={seed}, nodes={result.nodes_expanded})"
                    )
                    return state, optimal_depth

    print(f"  FAILED to find instance with optimal_depth={target_depth}")
    return None


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    astar = AStar()
    limits = SearchLimits(max_nodes=50_000_000, max_memory_mb=999_999)

    rows: List[dict] = []
    for target in TARGET_DEPTHS:
        print(f"Finding instance with optimal_depth={target}...")
        result = find_instance_with_optimal_depth(target, astar, limits)
        if result is None:
            print(f"  Skipping depth {target}")
            continue
        state, optimal_depth = result
        state_str = " ".join(str(x) for x in state)
        rows.append({
            "id": len(rows) + 1,
            "state": state_str,
            "optimal_depth": optimal_depth,
            "total_nodes_a": "",
        })

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "state", "optimal_depth", "total_nodes_a"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote {len(rows)} instances to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
