"""One-time script: run A* on all 100 Korf 15-puzzle instances and add
total_nodes_a (actual A* nodes expanded) and total_nodes_a_approx (sqrt of
IDA* count) to korfs100.csv.

Usage:
    python scripts/precompute_astar_nodes.py
"""
from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from algorithms import AStar
from algorithms.base import SearchLimits
from benchmark.instance_generators import (
    DEFAULT_KORF_CSV,
    _parse_puzzle_state,
    _validate_puzzle_state,
    _coerce_instance_id,
)
from domains.n_puzzle import NPuzzleProblem


def main() -> None:
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_KORF_CSV
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}")
        sys.exit(1)

    # Read existing CSV rows.
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    # Determine column indices for the new columns.
    has_ida = "total_nodes_ida" in fieldnames
    has_a = "total_nodes_a" in fieldnames
    has_a_approx = "total_nodes_a_approx" in fieldnames

    if not has_ida:
        print("Error: korfs100.csv must have 'total_nodes_ida' column. Run this after renaming total_nodes.")
        sys.exit(1)

    # Add new columns if missing.
    if not has_a_approx:
        fieldnames.append("total_nodes_a_approx")
    if not has_a:
        fieldnames.append("total_nodes_a")

    # Also add 'estimate' if missing (needed for state reconstruction).
    has_estimate = "estimate" in fieldnames

    astar = AStar()
    limits = SearchLimits(max_nodes=50_000_000, max_memory_mb=999_999)
    total = len(rows)
    solved = 0
    failed = 0

    for i, row in enumerate(rows):
        raw_id = row.get("id", "").strip()
        if not raw_id:
            continue
        instance_id = _coerce_instance_id(raw_id)

        raw_state = row.get("state", "")
        try:
            state = _parse_puzzle_state(raw_state)
            _validate_puzzle_state(state, instance_id)
        except ValueError as exc:
            print(f"  Skipping instance {instance_id}: {exc}")
            row["total_nodes_a"] = ""
            row["total_nodes_a_approx"] = ""
            continue

        raw_depth = row.get("optimal_depth", "").strip()
        if not raw_depth:
            row["total_nodes_a"] = ""
            row["total_nodes_a_approx"] = ""
            continue

        # Compute total_nodes_a_approx from total_nodes_ida.
        raw_ida = row.get("total_nodes_ida", "").strip()
        if raw_ida:
            try:
                ida_count = int(raw_ida)
                row["total_nodes_a_approx"] = str(int(math.isqrt(ida_count)))
            except ValueError:
                row["total_nodes_a_approx"] = ""
        else:
            row["total_nodes_a_approx"] = ""

        # Run A*.
        problem = NPuzzleProblem(state, size=4)
        print(f"[{i+1}/{total}] Running A* on instance {instance_id} (optimal_depth={raw_depth})...", end=" ", flush=True)
        result = astar.search(problem, limits)

        if result.success:
            row["total_nodes_a"] = str(result.nodes_expanded)
            print(f"success — {result.nodes_expanded} nodes expanded")
            solved += 1
        else:
            reason = "node_limit" if result.node_limit_reached else ("mem_limit" if result.memory_limit_reached else "failed")
            row["total_nodes_a"] = ""
            print(f"FAILED ({reason})")
            failed += 1

    # Write updated CSV.
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"\nDone. {solved} solved, {failed} failed out of {total} instances.")
    print(f"Updated {csv_path}")


if __name__ == "__main__":
    main()
