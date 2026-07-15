"""Saving SearchResult / AggregateMetrics collections to disk and printing summaries."""
from __future__ import annotations

import csv
import dataclasses
import json
from pathlib import Path
from typing import List

from algorithms.base import SearchResult

from .metrics import AggregateMetrics

# All dataclass fields except solution_actions (handled separately, since it's
# a list and needs different CSV/JSON treatment), plus the solution_depth
# property which isn't a dataclass field but is useful in the report.
_RESULT_FIELDS = [f.name for f in dataclasses.fields(SearchResult) if f.name != "solution_actions"] + [
    "solution_depth"
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


_SUMMARY_FIELDS = [f.name for f in dataclasses.fields(AggregateMetrics)]


def save_summary_csv(summaries: List[AggregateMetrics], path: Path) -> None:
    """Write the per-(domain, difficulty, algorithm) mean/std summary to CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_SUMMARY_FIELDS)
        writer.writeheader()
        for s in summaries:
            writer.writerow(dataclasses.asdict(s))


def save_summary_json(summaries: List[AggregateMetrics], path: Path) -> None:
    """Write the per-(domain, difficulty, algorithm) mean/std summary to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [dataclasses.asdict(s) for s in summaries]
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _fmt_stat(mean: float, std: float, digits: int) -> str:
    return f"{mean:.{digits}f}(±{std:.{digits}f})"


def print_summary_tables(summaries: List[AggregateMetrics]) -> None:
    """Print one table per (domain, difficulty) group; each cell that varies per
    seed is shown as `mean(±std)`, using the sample standard deviation across the
    seeds run at that scramble depth."""
    groups = sorted({(s.domain_name, s.difficulty) for s in summaries})
    for domain, difficulty in groups:
        print(f"\n=== Domain: {domain} | Difficulty: {difficulty} ===")
        header = (
            f"{'algorithm':<22}{'n':>4}{'success%':>10}{'node-lim%':>10}{'mem-lim%':>10}{'stack-ex%':>10}"
            f"{'time(s) solved':>20}{'peak mem(MB)':>20}{'nodes expanded':>20}{'nodes generated':>20}"
            f"{'avg_gap':>9}{'collapsed':>10}{'restored':>9}{'spilled':>9}{'loaded':>8}"
        )
        print(header)
        print("-" * len(header))
        for s in summaries:
            if (s.domain_name, s.difficulty) != (domain, difficulty):
                continue
            gap_str = f"{s.avg_optimality_gap:.3f}" if s.avg_optimality_gap is not None else "n/a"
            print(
                f"{s.algorithm_name:<22}{s.num_instances:>4}"
                f"{s.success_rate * 100:>9.1f}%{s.node_limit_rate * 100:>9.1f}%{s.memory_limit_rate * 100:>9.1f}%"
                f"{s.stack_exhausted_rate * 100:>9.1f}%"
                f"{_fmt_stat(s.avg_runtime_seconds_solved, s.std_runtime_seconds_solved, 3):>20}"
                f"{_fmt_stat(s.avg_peak_memory_mb, s.std_peak_memory_mb, 2):>20}"
                f"{_fmt_stat(s.avg_nodes_expanded, s.std_nodes_expanded, 1):>20}"
                f"{_fmt_stat(s.avg_nodes_generated, s.std_nodes_generated, 1):>20}"
                f"{gap_str:>9}"
                f"{s.total_nodes_collapsed:>10}{s.total_nodes_restored:>9}"
                f"{s.total_nodes_spilled_to_disk:>9}{s.total_nodes_loaded_from_disk:>8}"
            )
