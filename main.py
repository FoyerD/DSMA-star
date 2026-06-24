"""CLI entry point: run the heuristic-search benchmark suite.

Usage:
    python main.py --domain all --instances 5 --seed 0

There is no wall-clock timeout: a shared stopwatch structurally favors A*
(it has no memory-management overhead per node), which defeats the point of
comparing memory-bounded algorithms. Every run goes until it solves the
problem or hits a real resource ceiling -- the actual process memory (RSS),
scaled to a fraction of this machine's total RAM via `--max-memory-fraction`
-- or, for ILBFS's recursive search, a real Python `RecursionError`.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import psutil

from algorithms import AStar, DynamicSMACollapse, ILBFS, SMAStar, TwoLevelDynamicSMA
from algorithms.base import SearchLimits
from benchmark.analyze import analyze_results
from benchmark.instance_generators import NamedInstance, generate_puzzle_instances, generate_sokoban_instances
from benchmark.metrics import aggregate_by_domain_and_algorithm
from benchmark.results import print_summary_tables, save_results_csv, save_results_json
from benchmark.runner import run_benchmark


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark A*, SMA*, ILBFS, Dynamic SMA*-Collapse, and Two-Level Dynamic SMA*."
    )
    parser.add_argument("--domain", choices=["puzzle", "sokoban", "all"], default="all")
    parser.add_argument(
        "--instances", type=int, default=5, help="Number of puzzle instances (Sokoban always uses its 3 handcrafted levels)."
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", type=str, default="results")
    parser.add_argument("--puzzle-size", type=int, default=4, help="N-puzzle board size (4 = 15-puzzle).")
    parser.add_argument("--scramble-depths", type=int, nargs="+", default=[10, 20, 30, 40, 50])
    parser.add_argument(
        "--max-nodes",
        type=int,
        default=5_000_000,
        help="Generous safety valve against a genuine infinite loop -- not meant to be the binding constraint.",
    )
    parser.add_argument(
        "--max-memory-fraction",
        type=float,
        default=0.8,
        help="Real memory ceiling as a fraction of this machine's total RAM (checked against actual process RSS).",
    )
    parser.add_argument(
        "--max-memory-mb",
        type=float,
        default=None,
        help="Override --max-memory-fraction with an absolute MB ceiling instead.",
    )
    parser.add_argument("--sma-memory", type=int, default=50_000)
    parser.add_argument("--dynamic-initial-ram", type=int, default=2_000)
    parser.add_argument("--dynamic-min-ram", type=int, default=500)
    parser.add_argument("--dynamic-max-ram", type=int, default=10_000)
    parser.add_argument("--two-level-initial-ram", type=int, default=2_000)
    parser.add_argument("--two-level-min-ram", type=int, default=500)
    parser.add_argument("--two-level-max-ram", type=int, default=10_000)
    parser.add_argument("--two-level-total-limit", type=int, default=50_000)
    parser.add_argument("--epoch-generated-nodes", type=int, default=1_000)
    parser.add_argument(
        "--keep-disk",
        action="store_true",
        help="Keep Two-Level Dynamic SMA*'s SQLite cache files instead of deleting them after each run.",
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Skip running the benchmark; just analyze the existing <output-dir>/benchmark_results.csv.",
    )
    return parser.parse_args()


def build_instances(args: argparse.Namespace) -> List[NamedInstance]:
    instances: List[NamedInstance] = []


    if args.domain in ("puzzle", "all"):
        instances.extend(
            generate_puzzle_instances(
                count=args.instances,
                size=args.puzzle_size,
                scramble_depths=args.scramble_depths,
                seed=args.seed,
            )
        )

    if args.domain in ("sokoban", "all"):
        instances.extend(generate_sokoban_instances(("easy", "medium")))

    return instances


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)

    if args.analyze_only:
        analyze_results(output_dir / "benchmark_results.csv", output_dir / "analysis")
        print(f"Wrote analysis to {output_dir / 'analysis'}")
        return

    if args.max_memory_mb is not None:
        max_memory_mb = args.max_memory_mb
    else:
        total_ram_mb = psutil.virtual_memory().total / (1024 * 1024)
        max_memory_mb = total_ram_mb * args.max_memory_fraction
    print(f"Real memory ceiling: {max_memory_mb:.0f} MB")

    limits = SearchLimits(
        max_memory_mb=max_memory_mb,
        max_nodes=args.max_nodes,
        max_ram_nodes=args.max_nodes,
        sma_memory_limit_nodes=args.sma_memory,
        dynamic_initial_ram_nodes=args.dynamic_initial_ram,
        dynamic_min_ram_nodes=args.dynamic_min_ram,
        dynamic_max_ram_nodes=args.dynamic_max_ram,
        two_level_initial_ram_nodes=args.two_level_initial_ram,
        two_level_min_ram_nodes=args.two_level_min_ram,
        two_level_max_ram_nodes=args.two_level_max_ram,
        two_level_total_node_limit=args.two_level_total_limit,
        epoch_generated_nodes=args.epoch_generated_nodes,
    )

    algorithms = [
        AStar(),
        DynamicSMACollapse(),
        SMAStar(),
        ILBFS(),
        TwoLevelDynamicSMA(keep_disk=args.keep_disk, disk_dir=output_dir / "disk_cache"),
    ]

    instances = build_instances(args)
    print(f"Running {len(algorithms)} algorithms on {len(instances)} instances...")
    results = run_benchmark(instances, algorithms, limits)

    save_results_csv(results, output_dir / "benchmark_results.csv")
    save_results_json(results, output_dir / "benchmark_results.json")
    print(f"\nSaved detailed results to {output_dir / 'benchmark_results.csv'} and {output_dir / 'benchmark_results.json'}")

    summaries = aggregate_by_domain_and_algorithm(results)
    print_summary_tables(summaries)

    analyze_results(output_dir / "benchmark_results.csv", output_dir / "analysis")
    print(f"\nWrote analysis to {output_dir / 'analysis'}")


if __name__ == "__main__":
    main()

    
