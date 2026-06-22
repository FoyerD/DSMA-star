"""Saving SearchResult / AggregateMetrics collections to disk and printing summaries."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import List

from algorithms.base import SearchResult

from .metrics import AggregateMetrics

_RESULT_FIELDS = [
    "algorithm_name",
    "domain_name",
    "instance_id",
    "success",
    "solution_cost",
    "solution_depth",
    "runtime_seconds",
    "peak_memory_mb",
    "nodes_expanded",
    "nodes_generated",
    "max_frontier_size",
    "max_depth_reached",
    "reexpansions",
    "timeout",
    "memory_limit_reached",
    "error_message",
]


def _result_row(result: SearchResult) -> dict:
    row = {field: getattr(result, field) for field in _RESULT_FIELDS}
    row["solution_actions"] = ",".join(str(a) for a in result.solution_actions)
    return row


def save_results_csv(results: List[SearchResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = _RESULT_FIELDS + ["solution_actions"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow(_result_row(result))


def save_results_json(results: List[SearchResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = []
    for result in results:
        row = _result_row(result)
        row["solution_actions"] = result.solution_actions
        payload.append(row)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def print_summary_tables(summaries: List[AggregateMetrics]) -> None:
    domains = sorted({s.domain_name for s in summaries})
    for domain in domains:
        print(f"\n=== Domain: {domain} ===")
        header = (
            f"{'algorithm':<16}{'n':>4}{'success%':>10}{'timeout%':>10}{'mem-lim%':>10}"
            f"{'avg_t(s)':>10}{'avg_mem(MB)':>12}{'avg_exp':>10}{'avg_gen':>10}{'avg_gap':>10}"
        )
        print(header)
        print("-" * len(header))
        for s in summaries:
            if s.domain_name != domain:
                continue
            gap_str = f"{s.avg_optimality_gap:.3f}" if s.avg_optimality_gap is not None else "n/a"
            print(
                f"{s.algorithm_name:<16}{s.num_instances:>4}"
                f"{s.success_rate * 100:>9.1f}%{s.timeout_rate * 100:>9.1f}%{s.memory_limit_rate * 100:>9.1f}%"
                f"{s.avg_runtime_seconds:>10.3f}{s.avg_peak_memory_mb:>12.2f}"
                f"{s.avg_nodes_expanded:>10.1f}{s.avg_nodes_generated:>10.1f}{gap_str:>10}"
            )
