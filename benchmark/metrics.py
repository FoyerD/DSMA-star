"""Aggregate metrics computation over a collection of SearchResult objects."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from algorithms.base import SearchResult


@dataclass
class AggregateMetrics:
    """Summary statistics for one (domain, algorithm) group of runs."""

    domain_name: str
    algorithm_name: str
    num_instances: int = 0
    success_rate: float = 0.0
    timeout_rate: float = 0.0
    memory_limit_rate: float = 0.0
    avg_runtime_seconds: float = 0.0
    avg_peak_memory_mb: float = 0.0
    avg_nodes_expanded: float = 0.0
    avg_nodes_generated: float = 0.0
    avg_max_frontier_size: float = 0.0
    avg_solution_cost: Optional[float] = None
    avg_optimality_gap: Optional[float] = None


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def compute_optimal_costs(results: List[SearchResult], optimal_algorithm_name: str = "astar") -> Dict[Tuple[str, str], float]:
    """Map (domain_name, instance_id) -> A*'s solution cost, for successful A* runs."""
    optimal_costs: Dict[Tuple[str, str], float] = {}
    for r in results:
        if r.algorithm_name == optimal_algorithm_name and r.success and r.solution_cost is not None:
            optimal_costs[(r.domain_name, r.instance_id)] = r.solution_cost
    return optimal_costs


def aggregate_by_domain_and_algorithm(
    results: List[SearchResult], optimal_algorithm_name: str = "astar"
) -> List[AggregateMetrics]:
    """Group results by (domain, algorithm) and compute summary statistics for each group."""
    optimal_costs = compute_optimal_costs(results, optimal_algorithm_name)

    groups: Dict[Tuple[str, str], List[SearchResult]] = defaultdict(list)
    for r in results:
        groups[(r.domain_name, r.algorithm_name)].append(r)

    summaries: List[AggregateMetrics] = []
    for (domain_name, algorithm_name), group in sorted(groups.items()):
        n = len(group)
        successes = [r for r in group if r.success]
        gaps = []
        for r in successes:
            opt = optimal_costs.get((r.domain_name, r.instance_id))
            if opt is not None and opt > 0 and r.solution_cost is not None:
                gaps.append((r.solution_cost - opt) / opt)

        summaries.append(
            AggregateMetrics(
                domain_name=domain_name,
                algorithm_name=algorithm_name,
                num_instances=n,
                success_rate=len(successes) / n if n else 0.0,
                timeout_rate=sum(1 for r in group if r.timeout) / n if n else 0.0,
                memory_limit_rate=sum(1 for r in group if r.memory_limit_reached) / n if n else 0.0,
                avg_runtime_seconds=_mean([r.runtime_seconds for r in group]),
                avg_peak_memory_mb=_mean([r.peak_memory_mb for r in group]),
                avg_nodes_expanded=_mean([r.nodes_expanded for r in group]),
                avg_nodes_generated=_mean([r.nodes_generated for r in group]),
                avg_max_frontier_size=_mean([r.max_frontier_size for r in group]),
                avg_solution_cost=_mean([r.solution_cost for r in successes if r.solution_cost is not None]) or None,
                avg_optimality_gap=_mean(gaps) if gaps else None,
            )
        )
    return summaries
