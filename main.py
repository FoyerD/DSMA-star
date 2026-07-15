"""CLI entry point: run the heuristic-search benchmark suite.

Usage:
    python main.py --domain all --seeds 0 1 2 3 4

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

from algorithms import AStar, DynamicSMACollapse, ILBFS, MemoryLimit, SMAStar, TwoLevelDynamicSMA, normalize_memory_limits
from algorithms.base import SearchAlgorithm, SearchLimits
from benchmark.analyze import analyze_results
from benchmark.instance_generators import (
    DEFAULT_KORF_CSV,
    NamedInstance,
    generate_npuzzle_instances,
    generate_sokoban_instances,
)
from benchmark.metrics import aggregate_by_domain_and_algorithm
from benchmark.results import (
    print_summary_tables,
    save_results_csv,
    save_results_json,
    save_summary_csv,
    save_summary_json,
)
from benchmark.runner import run_benchmark


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark A*, SMA*, ILBFS, Dynamic SMA*-Collapse, and Two-Level Dynamic SMA*."
    )
    parser.add_argument("--domain", choices=["puzzle", "sokoban", "all"], default="all")
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=[0],
        help=(
            "RNG seeds for reproducible instance generation. One puzzle instance is generated "
            "per (scramble depth, seed) pair, so results are aggregated as mean/std across seeds "
            "for each (algorithm, scramble depth) combination."
        ),
    )
    parser.add_argument("--output-dir", type=str, default="results")
    parser.add_argument("--puzzle-size", type=int, default=4, help="N-puzzle board size (4 = 15-puzzle).")
    parser.add_argument(
        "--puzzle-instance-source",
        choices=["korf", "scramble"],
        default="korf" if DEFAULT_KORF_CSV.exists() else "scramble",
        help=(
            "How to generate 15-puzzle instances: 'korf' selects Korf's 100 fixed historical "
            "instances by true optimal solution depth (--optimal-depths, --korf-csv); "
            "'scramble' generates instances by random-walking from the goal (--scramble-depths). "
            "Defaults to 'korf' when korfs100.csv exists in the working directory, else 'scramble'."
        ),
    )
    parser.add_argument(
        "--korf-csv",
        type=str,
        default=str(DEFAULT_KORF_CSV),
        help="Path to the Korf 100 instances CSV, used when --puzzle-instance-source=korf.",
    )
    parser.add_argument(
        "--optimal-depths",
        type=int,
        nargs="+",
        default=[40, 45, 50, 55, 60],
        help="True optimal solution depths to select via Korf instances, used when --puzzle-instance-source=korf.",
    )
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
    parser.add_argument(
        "--sma-memory",
        type=MemoryLimit.parse,
        nargs="+",
        default=[MemoryLimit.parse('20%')],
        help=(
            "Memory limit(s) for SMA*. Accepts flat node counts (e.g. 10000) "
            "or percentages of the instance's total_nodes (e.g. 10%%). Provide "
            "multiple values to run SMA* once per limit, each as its own "
            "independent algorithm instance."
        ),
    )
    parser.add_argument(
        "--dynamic-initial-ram",
        type=MemoryLimit.parse,
        default=MemoryLimit.parse('5%'),
        help="Dynamic SMA*-Collapse initial RAM node budget (int or percentage, e.g. 10%%).",
    )
    parser.add_argument(
        "--dynamic-min-ram",
        type=MemoryLimit.parse,
        default=MemoryLimit.parse('2%'),
        help="Dynamic SMA*-Collapse minimum RAM node budget (int or percentage).",
    )
    parser.add_argument(
        "--dynamic-max-ram",
        type=MemoryLimit.parse,
        default=MemoryLimit.parse('20%'),
        help="Dynamic SMA*-Collapse maximum RAM node budget (int or percentage).",
    )
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
            generate_npuzzle_instances(
                source=args.puzzle_instance_source,
                seeds=args.seeds,
                size=args.puzzle_size,
                scramble_depths=args.scramble_depths,
                optimal_depths=args.optimal_depths,
                korf_csv=Path(args.korf_csv),
            )
        )

    if args.domain in ("sokoban", "all"):
        instances.extend(generate_sokoban_instances(("easy", "medium")))

    return instances


def build_algorithms(args: argparse.Namespace) -> List[SearchAlgorithm]:
    sma_memory_limits = normalize_memory_limits(args.sma_memory)
    return [
        AStar(),
        DynamicSMACollapse(),
        *[SMAStar(memory_limit=ml) for ml in sma_memory_limits],
        ILBFS(),
        # TwoLevelDynamicSMA(keep_disk=args.keep_disk, disk_dir=output_dir / "disk_cache"),
    ]


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
        two_level_initial_ram_nodes=args.two_level_initial_ram,
        two_level_min_ram_nodes=args.two_level_min_ram,
        two_level_max_ram_nodes=args.two_level_max_ram,
        two_level_total_node_limit=args.two_level_total_limit,
        epoch_generated_nodes=args.epoch_generated_nodes,
    )

    dynamic_overrides = {
        "dynamic_initial_ram_nodes": args.dynamic_initial_ram,
        "dynamic_min_ram_nodes": args.dynamic_min_ram,
        "dynamic_max_ram_nodes": args.dynamic_max_ram,
    }

    algorithms = build_algorithms(args)

    instances = build_instances(args)
    print(f"Running {len(algorithms)} algorithms on {len(instances)} instances...")
    results = run_benchmark(instances, algorithms, limits, dynamic_overrides=dynamic_overrides)

    save_results_csv(results, output_dir / "benchmark_results.csv")
    save_results_json(results, output_dir / "benchmark_results.json")
    print(f"\nSaved detailed results to {output_dir / 'benchmark_results.csv'} and {output_dir / 'benchmark_results.json'}")

    summaries = aggregate_by_domain_and_algorithm(results)
    print_summary_tables(summaries)
    save_summary_csv(summaries, output_dir / "benchmark_summary.csv")
    save_summary_json(summaries, output_dir / "benchmark_summary.json")
    print(f"Saved mean/std summary to {output_dir / 'benchmark_summary.csv'} and {output_dir / 'benchmark_summary.json'}")

    analyze_results(output_dir / "benchmark_results.csv", output_dir / "analysis")
    print(f"\nWrote analysis to {output_dir / 'analysis'}")


if __name__ == "__main__":
    main()

    
