"""CLI entry point: run the search-algorithm benchmark suite.

Usage:
    python main.py [--domain grid|puzzle|all] [--instances N] [--timeout SECONDS]
                    [--grid-size WIDTH HEIGHT] [--obstacle-prob P]
                    [--scramble-depths D1 D2 ...] [--seed SEED] [--output-dir DIR]
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

from algorithms import AStar, CustomAlgorithm, ILBFS, SMAStar
from algorithms.base import SearchLimits
from benchmark.instance_generators import NamedInstance, generate_grid_instances, generate_puzzle_instances
from benchmark.metrics import aggregate_by_domain_and_algorithm
from benchmark.results import print_summary_tables, save_results_csv, save_results_json
from benchmark.runner import run_benchmark


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark A*, SMA*, ILBFS, and a custom algorithm.")
    parser.add_argument("--domain", choices=["grid", "puzzle", "all"], default="all")
    parser.add_argument("--instances", type=int, default=5, help="Number of instances per domain.")
    parser.add_argument("--timeout", type=float, default=10.0, help="Per-run timeout in seconds.")
    parser.add_argument("--grid-size", type=int, nargs=2, default=[10, 10], metavar=("WIDTH", "HEIGHT"))
    parser.add_argument("--obstacle-prob", type=float, default=0.2)
    parser.add_argument("--scramble-depths", type=int, nargs="+", default=[5, 10, 15, 20])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=str, default="results")
    parser.add_argument("--max-nodes", type=int, default=200_000)
    parser.add_argument("--max-memory-mb", type=float, default=512.0)
    parser.add_argument("--sma-memory-limit-nodes", type=int, default=2000)
    return parser.parse_args()


def build_instances(args: argparse.Namespace) -> List[NamedInstance]:
    instances: List[NamedInstance] = []
    width, height = args.grid_size

    if args.domain in ("grid", "all"):
        instances.extend(
            generate_grid_instances(
                count=args.instances,
                width=width,
                height=height,
                obstacle_prob=args.obstacle_prob,
                seed=args.seed,
            )
        )

    if args.domain in ("puzzle", "all"):
        instances.extend(
            generate_puzzle_instances(
                count=args.instances,
                scramble_depths=args.scramble_depths,
                seed=args.seed,
            )
        )

    return instances


def main() -> None:
    args = parse_args()

    limits = SearchLimits(
        timeout_seconds=args.timeout,
        max_memory_mb=args.max_memory_mb,
        max_nodes=args.max_nodes,
        sma_star_memory_limit_nodes=args.sma_memory_limit_nodes,
    )
    algorithms = [AStar(), SMAStar(), ILBFS(), CustomAlgorithm()]

    instances = build_instances(args)
    print(f"Running {len(algorithms)} algorithms on {len(instances)} instances...")
    results = run_benchmark(instances, algorithms, limits)

    output_dir = Path(args.output_dir)
    save_results_csv(results, output_dir / "benchmark_results.csv")
    save_results_json(results, output_dir / "benchmark_results.json")
    print(f"\nSaved detailed results to {output_dir / 'benchmark_results.csv'} and {output_dir / 'benchmark_results.json'}")

    summaries = aggregate_by_domain_and_algorithm(results)
    print_summary_tables(summaries)


if __name__ == "__main__":
    main()
