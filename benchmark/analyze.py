"""Post-hoc analysis of a benchmark_results.csv: summaries, comparisons, and a
human-readable Markdown report.

This module is deliberately decoupled from the live `SearchResult` objects --
it reads the same CSV that `benchmark/results.py` writes, so it can be run
standalone (`python -m benchmark.analyze`) against any past run, including
ones produced on a different machine or with a hand-edited CSV. All numeric
parsing is defensive: missing/blank fields never crash the analysis, they
just become `None` (left blank in the output) or `0` for fields that are
naturally additive counts (see `_to_count`).
"""
from __future__ import annotations

import argparse
import csv
import re
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

Row = Dict[str, Any]

# Columns that are non-negative cumulative counters: a missing/blank value
# means "this algorithm doesn't produce this metric" which is equivalent to 0
# for summation/averaging purposes (e.g. A* never spills to disk).
_COUNT_FIELDS = (
    "nodes_expanded",
    "nodes_generated",
    "nodes_collapsed",
    "nodes_spilled_to_disk",
    "nodes_loaded_from_disk",
    "disk_batches_loaded",
    "disk_peak_nodes",
    "disk_read_count",
    "disk_write_count",
    "number_of_ram_increases",
    "number_of_ram_decreases",
    "number_of_total_collapses",
    "stale_disk_nodes_skipped",
    "duplicate_nodes_skipped",
    "max_frontier_size",
    "max_depth_reached",
    "reexpansions",
)

# Columns that are genuinely optional (None means "not applicable"/"unknown",
# not zero) and must never be defaulted to 0.
_OPTIONAL_FLOAT_FIELDS = (
    "solution_cost",
    "solution_depth",
    "runtime_seconds",
    "peak_memory_mb",
    "disk_io_time_seconds",
    "ram_capacity_initial",
    "ram_capacity_final",
    "ram_capacity_peak",
    "ram_capacity_min",
)

_BOOL_FIELDS = ("success", "node_limit_reached", "memory_limit_reached", "stack_exhausted")

ASTAR_NAME = "astar"
PROPOSED_ALGORITHMS = ("dynamic_sma_collapse", "two_level_dynamic_sma")
# "sma_star" is a legacy placeholder covering every fixed-memory SMA* run: a
# benchmark can contain several SMA* instances (one per --sma-memory value),
# each named "SMA* (memory=<N>)" -- see `_is_sma_star_variant`/`_sma_star_variant_names`.
BASELINE_ALGORITHMS = ("astar", "sma_star", "ilbfs")
DISPLAY_NAMES = {
    "astar": "A*",
    "sma_star": "SMA*",  # legacy label for CSVs written before per-memory SMA* names existed
    "ilbfs": "ILBFS",
    "dynamic_sma_collapse": "Dynamic SMA*-Collapse",
    "two_level_dynamic_sma": "Two-Level Dynamic SMA*",
}

# Matches names like "SMA* (memory=10000)" produced by one SMA* instance per
# --sma-memory value. "sma_star" itself is also accepted for old CSVs written
# before SMA* runs were split out by memory limit.
_SMA_STAR_VARIANT_RE = re.compile(r"^SMA\* \(memory=\d+\)$")


def _display(name: str) -> str:
    return DISPLAY_NAMES.get(name, name)


def _is_sma_star_variant(name: str) -> bool:
    return name == "sma_star" or bool(_SMA_STAR_VARIANT_RE.match(name))


def _sma_star_variant_names(names: Iterable[str]) -> List[str]:
    return sorted({name for name in names if _is_sma_star_variant(name)})


# --------------------------------------------------------------------------
# Safe parsing
# --------------------------------------------------------------------------


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    return text in ("true", "1", "yes")


def _to_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.lower() == "none":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_count(value: Any) -> int:
    """Parse a cumulative-counter field, defaulting missing/blank to 0."""
    parsed = _to_optional_float(value)
    return int(parsed) if parsed is not None else 0


def load_results(path: Path) -> List[Row]:
    """Load and type-normalize the detailed benchmark CSV into a list of dicts."""
    path = Path(path)
    rows: List[Row] = []
    if not path.exists():
        return rows
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            row: Row = {
                "algorithm_name": (raw.get("algorithm_name") or "").strip(),
                "domain_name": (raw.get("domain_name") or "").strip(),
                "instance_id": (raw.get("instance_id") or "").strip(),
                "instance_difficulty": (raw.get("instance_difficulty") or "default").strip(),
                "error_message": (raw.get("error_message") or "") or None,
            }
            for field_name in _BOOL_FIELDS:
                row[field_name] = _to_bool(raw.get(field_name))
            for field_name in _OPTIONAL_FLOAT_FIELDS:
                row[field_name] = _to_optional_float(raw.get(field_name))
            for field_name in _COUNT_FIELDS:
                row[field_name] = _to_count(raw.get(field_name))
            row["optimality_gap_vs_astar"] = None
            rows.append(row)
    return rows


# --------------------------------------------------------------------------
# Optimality gap
# --------------------------------------------------------------------------


def compute_astar_reference(results: List[Row]) -> Dict[Tuple[str, str], float]:
    """Map (domain_name, instance_id) -> A*'s solution cost, for successful A* runs."""
    reference: Dict[Tuple[str, str], float] = {}
    for row in results:
        if row["algorithm_name"] == ASTAR_NAME and row["success"] and row["solution_cost"] is not None:
            reference[(row["domain_name"], row["instance_id"])] = row["solution_cost"]
    return reference


def add_optimality_gaps(results: List[Row], astar_reference: Optional[Dict[Tuple[str, str], float]] = None) -> List[Row]:
    """Annotate each row with `optimality_gap_vs_astar` (None if A* didn't solve that instance)."""
    if astar_reference is None:
        astar_reference = compute_astar_reference(results)
    for row in results:
        gap = None
        if row["success"] and row["solution_cost"] is not None:
            astar_cost = astar_reference.get((row["domain_name"], row["instance_id"]))
            if astar_cost is not None:
                gap = row["solution_cost"] - astar_cost
        row["optimality_gap_vs_astar"] = gap
    return results


# --------------------------------------------------------------------------
# Shared aggregation
# --------------------------------------------------------------------------


def _mean(values: List[float]) -> Optional[float]:
    return statistics.fmean(values) if values else None


def _median(values: List[float]) -> Optional[float]:
    return statistics.median(values) if values else None


def _safe_ratio(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _safe_delta(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return a - b


def _aggregate(rows: List[Row]) -> Dict[str, Any]:
    """Compute every statistic needed by algorithm_summary / domain_algorithm_summary."""
    total = len(rows)
    solved = [r for r in rows if r["success"]]
    n_solved = len(solved)
    n_failed = total - n_solved

    runtimes_solved = [r["runtime_seconds"] for r in solved if r["runtime_seconds"] is not None]
    costs_solved = [r["solution_cost"] for r in solved if r["solution_cost"] is not None]
    depths_solved = [r["solution_depth"] for r in solved if r["solution_depth"] is not None]
    gaps = [r["optimality_gap_vs_astar"] for r in rows if r["optimality_gap_vs_astar"] is not None]
    peak_mem = [r["peak_memory_mb"] for r in rows if r["peak_memory_mb"] is not None]
    ram_final = [r["ram_capacity_final"] for r in rows if r["ram_capacity_final"] is not None]
    disk_io = [r["disk_io_time_seconds"] for r in rows if r["disk_io_time_seconds"] is not None]
    disk_peak = [r["disk_peak_nodes"] for r in rows]

    return {
        "total_runs": total,
        "solved_runs": n_solved,
        "failed_runs": n_failed,
        "success_rate": (n_solved / total) if total else None,
        "memory_limit_rate": (sum(1 for r in rows if r["memory_limit_reached"]) / total) if total else None,
        "node_limit_rate": (sum(1 for r in rows if r["node_limit_reached"]) / total) if total else None,
        "stack_exhausted_rate": (sum(1 for r in rows if r["stack_exhausted"]) / total) if total else None,
        "avg_runtime_s_solved": _mean(runtimes_solved),
        "median_runtime_s_solved": _median(runtimes_solved),
        "avg_peak_memory_mb": _mean(peak_mem),
        "avg_nodes_expanded": _mean([r["nodes_expanded"] for r in rows]),
        "avg_nodes_generated": _mean([r["nodes_generated"] for r in rows]),
        "avg_solution_cost_solved": _mean(costs_solved),
        "avg_solution_depth_solved": _mean(depths_solved),
        "avg_optimality_gap_vs_astar": _mean(gaps),
        "total_nodes_collapsed": sum(r["nodes_collapsed"] for r in rows),
        "total_nodes_spilled_to_disk": sum(r["nodes_spilled_to_disk"] for r in rows),
        "total_nodes_loaded_from_disk": sum(r["nodes_loaded_from_disk"] for r in rows),
        "total_disk_batches_loaded": sum(r["disk_batches_loaded"] for r in rows),
        "avg_disk_io_time_seconds": _mean(disk_io),
        "max_disk_peak_nodes": max(disk_peak) if disk_peak else 0,
        "avg_ram_capacity_final": _mean(ram_final),
        "total_ram_increases": sum(r["number_of_ram_increases"] for r in rows),
        "total_ram_decreases": sum(r["number_of_ram_decreases"] for r in rows),
    }


def _write_csv(path: Path, fieldnames: List[str], rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in fieldnames})


# --------------------------------------------------------------------------
# 1. algorithm_summary.csv
# --------------------------------------------------------------------------

_ALGORITHM_SUMMARY_FIELDS = [
    "algorithm_name",
    "total_runs",
    "solved_runs",
    "failed_runs",
    "success_rate",
    "memory_limit_rate",
    "node_limit_rate",
    "stack_exhausted_rate",
    "avg_runtime_s_solved",
    "median_runtime_s_solved",
    "avg_peak_memory_mb",
    "avg_nodes_expanded",
    "avg_nodes_generated",
    "avg_solution_cost_solved",
    "avg_solution_depth_solved",
    "avg_optimality_gap_vs_astar",
    "total_nodes_collapsed",
    "total_nodes_spilled_to_disk",
    "total_nodes_loaded_from_disk",
    "total_disk_batches_loaded",
    "avg_disk_io_time_seconds",
    "max_disk_peak_nodes",
    "avg_ram_capacity_final",
    "total_ram_increases",
    "total_ram_decreases",
]


def write_algorithm_summary(results: List[Row], out_dir: Path) -> List[Dict[str, Any]]:
    by_algo: Dict[str, List[Row]] = defaultdict(list)
    for row in results:
        by_algo[row["algorithm_name"]].append(row)

    out_rows = []
    for algorithm_name in sorted(by_algo):
        stats = _aggregate(by_algo[algorithm_name])
        out_rows.append({"algorithm_name": algorithm_name, **stats})

    _write_csv(out_dir / "algorithm_summary.csv", _ALGORITHM_SUMMARY_FIELDS, out_rows)
    return out_rows


# --------------------------------------------------------------------------
# 2. domain_algorithm_summary.csv
# --------------------------------------------------------------------------

_DOMAIN_ALGORITHM_SUMMARY_FIELDS = [
    "domain_name",
    "algorithm_name",
    "total_runs",
    "solved_runs",
    "success_rate",
    "memory_limit_rate",
    "node_limit_rate",
    "stack_exhausted_rate",
    "avg_runtime_s_solved",
    "median_runtime_s_solved",
    "avg_peak_memory_mb",
    "avg_nodes_expanded",
    "avg_nodes_generated",
    "avg_solution_cost_solved",
    "avg_solution_depth_solved",
    "avg_optimality_gap_vs_astar",
    "total_nodes_collapsed",
    "total_nodes_spilled_to_disk",
    "total_nodes_loaded_from_disk",
    "avg_disk_io_time_seconds",
    "max_disk_peak_nodes",
]


def write_domain_algorithm_summary(results: List[Row], out_dir: Path) -> List[Dict[str, Any]]:
    by_group: Dict[Tuple[str, str], List[Row]] = defaultdict(list)
    for row in results:
        by_group[(row["domain_name"], row["algorithm_name"])].append(row)

    out_rows = []
    for (domain_name, algorithm_name) in sorted(by_group):
        stats = _aggregate(by_group[(domain_name, algorithm_name)])
        out_rows.append({"domain_name": domain_name, "algorithm_name": algorithm_name, **stats})

    _write_csv(out_dir / "domain_algorithm_summary.csv", _DOMAIN_ALGORITHM_SUMMARY_FIELDS, out_rows)
    return out_rows


# --------------------------------------------------------------------------
# 3. instance_comparison.csv
# --------------------------------------------------------------------------

_INSTANCE_COMPARISON_FIELDS = [
    "domain_name",
    "instance_id",
    "difficulty_label",
    "algorithm_name",
    "success",
    "memory_limit_reached",
    "node_limit_reached",
    "stack_exhausted",
    "runtime_seconds",
    "peak_memory_mb",
    "nodes_expanded",
    "nodes_generated",
    "solution_cost",
    "solution_depth",
    "optimality_gap_vs_astar",
    "nodes_collapsed",
    "nodes_spilled_to_disk",
    "nodes_loaded_from_disk",
    "disk_io_time_seconds",
    "disk_peak_nodes",
    "ram_capacity_initial",
    "ram_capacity_final",
    "number_of_ram_increases",
    "number_of_ram_decreases",
]


def write_instance_comparison(results: List[Row], out_dir: Path) -> List[Dict[str, Any]]:
    out_rows = []
    for row in results:
        out_rows.append(
            {
                "domain_name": row["domain_name"],
                "instance_id": row["instance_id"],
                "difficulty_label": row["instance_difficulty"],
                "algorithm_name": row["algorithm_name"],
                "success": row["success"],
                "memory_limit_reached": row["memory_limit_reached"],
                "node_limit_reached": row["node_limit_reached"],
                "stack_exhausted": row["stack_exhausted"],
                "runtime_seconds": row["runtime_seconds"],
                "peak_memory_mb": row["peak_memory_mb"],
                "nodes_expanded": row["nodes_expanded"],
                "nodes_generated": row["nodes_generated"],
                "solution_cost": row["solution_cost"],
                "solution_depth": row["solution_depth"],
                "optimality_gap_vs_astar": row["optimality_gap_vs_astar"],
                "nodes_collapsed": row["nodes_collapsed"],
                "nodes_spilled_to_disk": row["nodes_spilled_to_disk"],
                "nodes_loaded_from_disk": row["nodes_loaded_from_disk"],
                "disk_io_time_seconds": row["disk_io_time_seconds"],
                "disk_peak_nodes": row["disk_peak_nodes"],
                "ram_capacity_initial": row["ram_capacity_initial"],
                "ram_capacity_final": row["ram_capacity_final"],
                "number_of_ram_increases": row["number_of_ram_increases"],
                "number_of_ram_decreases": row["number_of_ram_decreases"],
            }
        )
    _write_csv(out_dir / "instance_comparison.csv", _INSTANCE_COMPARISON_FIELDS, out_rows)
    return out_rows


# --------------------------------------------------------------------------
# 4. winners_by_instance.csv
# --------------------------------------------------------------------------

_WINNERS_FIELDS = [
    "domain_name",
    "instance_id",
    "fastest_successful_algorithm",
    "lowest_memory_successful_algorithm",
    "fewest_expansions_successful_algorithm",
    "best_solution_cost_algorithm",
    "astar_solved",
    "dynamic_sma_collapse_solved",
    "two_level_dynamic_sma_solved",
    "notes",
]

# Heuristic threshold for "many collapses": collapsing more than this fraction
# of generated nodes is considered heavy memory pressure for the note.
_HEAVY_COLLAPSE_RATIO = 0.30


def _best_by(rows: List[Row], key: str) -> Optional[str]:
    candidates = [r for r in rows if r["success"] and r[key] is not None]
    if not candidates:
        return None
    return min(candidates, key=lambda r: r[key])["algorithm_name"]


def _build_notes(rows: List[Row], fastest: Optional[str]) -> str:
    notes: List[str] = []
    by_algo = {r["algorithm_name"]: r for r in rows}
    solvers = [r["algorithm_name"] for r in rows if r["success"]]

    astar_row = by_algo.get(ASTAR_NAME)
    astar_solved = bool(astar_row and astar_row["success"])

    if not solvers:
        notes.append("All algorithms failed")
    elif not astar_solved:
        others = ", ".join(_display(name) for name in solvers if name != ASTAR_NAME)
        if others:
            notes.append(f"A* failed; {others} solved")
    elif fastest == ASTAR_NAME:
        notes.append("A* solved fastest")

    two_level_row = by_algo.get("two_level_dynamic_sma")
    if two_level_row and (two_level_row["nodes_spilled_to_disk"] > 0 or two_level_row["nodes_loaded_from_disk"] > 0):
        notes.append("Two-Level used disk")

    dynamic_row = by_algo.get("dynamic_sma_collapse")
    if dynamic_row and dynamic_row["nodes_generated"] > 0:
        ratio = dynamic_row["nodes_collapsed"] / dynamic_row["nodes_generated"]
        if ratio > _HEAVY_COLLAPSE_RATIO:
            notes.append("Dynamic collapse had many collapses")

    stack_exhausted_algos = [name for name, row in by_algo.items() if row["stack_exhausted"]]
    if stack_exhausted_algos:
        notes.append(f"{', '.join(_display(n) for n in stack_exhausted_algos)} exhausted the call stack")

    return "; ".join(notes)


def write_winners_by_instance(results: List[Row], out_dir: Path) -> List[Dict[str, Any]]:
    by_instance: Dict[Tuple[str, str], List[Row]] = defaultdict(list)
    for row in results:
        by_instance[(row["domain_name"], row["instance_id"])].append(row)

    out_rows = []
    for (domain_name, instance_id) in sorted(by_instance):
        rows = by_instance[(domain_name, instance_id)]
        by_algo = {r["algorithm_name"]: r for r in rows}

        fastest = _best_by(rows, "runtime_seconds")
        out_rows.append(
            {
                "domain_name": domain_name,
                "instance_id": instance_id,
                "fastest_successful_algorithm": fastest,
                "lowest_memory_successful_algorithm": _best_by(rows, "peak_memory_mb"),
                "fewest_expansions_successful_algorithm": _best_by(rows, "nodes_expanded"),
                "best_solution_cost_algorithm": _best_by(rows, "solution_cost"),
                "astar_solved": by_algo.get(ASTAR_NAME, {}).get("success", False),
                "dynamic_sma_collapse_solved": by_algo.get("dynamic_sma_collapse", {}).get("success", False),
                "two_level_dynamic_sma_solved": by_algo.get("two_level_dynamic_sma", {}).get("success", False),
                "notes": _build_notes(rows, fastest),
            }
        )

    _write_csv(out_dir / "winners_by_instance.csv", _WINNERS_FIELDS, out_rows)
    return out_rows


# --------------------------------------------------------------------------
# 5. proposed_algorithms_vs_baselines.csv
# --------------------------------------------------------------------------

_PROPOSED_VS_BASELINES_FIELDS = [
    "group_name",
    "proposed_algorithm",
    "baseline_algorithm",
    "proposed_success_rate",
    "baseline_success_rate",
    "success_rate_delta",
    "proposed_avg_runtime_s_solved",
    "baseline_avg_runtime_s_solved",
    "runtime_ratio_proposed_over_baseline",
    "proposed_avg_peak_memory_mb",
    "baseline_avg_peak_memory_mb",
    "memory_ratio_proposed_over_baseline",
    "proposed_avg_nodes_expanded",
    "baseline_avg_nodes_expanded",
    "expanded_ratio_proposed_over_baseline",
    "proposed_avg_solution_cost",
    "baseline_avg_solution_cost",
    "solution_cost_delta",
    "proposed_total_collapsed",
    "proposed_total_spilled_to_disk",
    "proposed_total_loaded_from_disk",
    "interpretation",
]

_COMPARISON_PAIRS = [
    ("dynamic_sma_collapse", "astar"),
    ("dynamic_sma_collapse", "sma_star"),
    ("dynamic_sma_collapse", "ilbfs"),
    ("two_level_dynamic_sma", "astar"),
    ("two_level_dynamic_sma", "sma_star"),
    ("two_level_dynamic_sma", "ilbfs"),
    ("two_level_dynamic_sma", "dynamic_sma_collapse"),
]


def _expand_comparison_pairs(
    pairs: List[Tuple[str, str]], available_algorithm_names: Iterable[str]
) -> List[Tuple[str, str]]:
    """Expand the "sma_star" placeholder baseline into one pair per SMA* variant
    actually present (e.g. "SMA* (memory=10000)", "SMA* (memory=50000)")."""
    sma_variants = _sma_star_variant_names(available_algorithm_names)
    expanded: List[Tuple[str, str]] = []
    for proposed, baseline in pairs:
        if baseline == "sma_star":
            expanded.extend((proposed, variant) for variant in sma_variants)
        else:
            expanded.append((proposed, baseline))
    return expanded


_EPSILON = 1e-9


def _interpret(proposed: str, stats_p: Dict[str, Any], stats_b: Dict[str, Any]) -> str:
    sr_delta = _safe_delta(stats_p["success_rate"], stats_b["success_rate"])
    runtime_p, runtime_b = stats_p["avg_runtime_s_solved"], stats_b["avg_runtime_s_solved"]
    mem_p, mem_b = stats_p["avg_peak_memory_mb"], stats_b["avg_peak_memory_mb"]
    exp_p, exp_b = stats_p["avg_nodes_expanded"], stats_b["avg_nodes_expanded"]

    if proposed == "two_level_dynamic_sma" and stats_p["total_nodes_spilled_to_disk"] > 0:
        if runtime_p is not None and runtime_b is not None and runtime_p > runtime_b * 1.5:
            return "Two-Level used disk heavily; check disk I/O overhead."

    if sr_delta is not None and sr_delta > _EPSILON:
        if runtime_p is None or runtime_b is None or runtime_p >= runtime_b:
            return "Proposed solved more instances but was slower on solved cases."
        return "Proposed solved more instances and was also faster on solved cases."

    if sr_delta is not None and sr_delta < -_EPSILON:
        return "Baseline solved more instances than proposed."

    # Tie (or unknown) on success rate.
    if runtime_p is not None and runtime_b is not None:
        if runtime_b < runtime_p:
            return "Both solved the same number of instances; baseline was faster."
        if runtime_p < runtime_b:
            return "Both solved the same number of instances; proposed was faster."

    if mem_p is not None and mem_b is not None and exp_p is not None and exp_b is not None:
        if mem_p < mem_b and exp_p > exp_b:
            return "Proposed used less RAM but expanded more nodes."
        if mem_p < mem_b:
            return "Proposed used less RAM with comparable node expansion."

    return "Both solved the same number of instances with comparable performance."


def write_proposed_vs_baselines(results: List[Row], out_dir: Path) -> List[Dict[str, Any]]:
    domains = sorted({row["domain_name"] for row in results})
    groups: List[Tuple[str, List[Row]]] = [("all_domains", results)]
    for domain in domains:
        groups.append((domain, [r for r in results if r["domain_name"] == domain]))

    out_rows = []
    for group_name, group_rows in groups:
        by_algo: Dict[str, List[Row]] = defaultdict(list)
        for row in group_rows:
            by_algo[row["algorithm_name"]].append(row)

        for proposed, baseline in _expand_comparison_pairs(_COMPARISON_PAIRS, by_algo.keys()):
            stats_p = _aggregate(by_algo.get(proposed, []))
            stats_b = _aggregate(by_algo.get(baseline, []))

            out_rows.append(
                {
                    "group_name": group_name,
                    "proposed_algorithm": proposed,
                    "baseline_algorithm": baseline,
                    "proposed_success_rate": stats_p["success_rate"],
                    "baseline_success_rate": stats_b["success_rate"],
                    "success_rate_delta": _safe_delta(stats_p["success_rate"], stats_b["success_rate"]),
                    "proposed_avg_runtime_s_solved": stats_p["avg_runtime_s_solved"],
                    "baseline_avg_runtime_s_solved": stats_b["avg_runtime_s_solved"],
                    "runtime_ratio_proposed_over_baseline": _safe_ratio(
                        stats_p["avg_runtime_s_solved"], stats_b["avg_runtime_s_solved"]
                    ),
                    "proposed_avg_peak_memory_mb": stats_p["avg_peak_memory_mb"],
                    "baseline_avg_peak_memory_mb": stats_b["avg_peak_memory_mb"],
                    "memory_ratio_proposed_over_baseline": _safe_ratio(
                        stats_p["avg_peak_memory_mb"], stats_b["avg_peak_memory_mb"]
                    ),
                    "proposed_avg_nodes_expanded": stats_p["avg_nodes_expanded"],
                    "baseline_avg_nodes_expanded": stats_b["avg_nodes_expanded"],
                    "expanded_ratio_proposed_over_baseline": _safe_ratio(
                        stats_p["avg_nodes_expanded"], stats_b["avg_nodes_expanded"]
                    ),
                    "proposed_avg_solution_cost": stats_p["avg_solution_cost_solved"],
                    "baseline_avg_solution_cost": stats_b["avg_solution_cost_solved"],
                    "solution_cost_delta": _safe_delta(
                        stats_p["avg_solution_cost_solved"], stats_b["avg_solution_cost_solved"]
                    ),
                    "proposed_total_collapsed": stats_p["total_nodes_collapsed"],
                    "proposed_total_spilled_to_disk": stats_p["total_nodes_spilled_to_disk"],
                    "proposed_total_loaded_from_disk": stats_p["total_nodes_loaded_from_disk"],
                    "interpretation": _interpret(proposed, stats_p, stats_b),
                }
            )

    _write_csv(out_dir / "proposed_algorithms_vs_baselines.csv", _PROPOSED_VS_BASELINES_FIELDS, out_rows)
    return out_rows


# --------------------------------------------------------------------------
# 6. human_readable_summary.md
# --------------------------------------------------------------------------


def _fmt(value: Optional[float], digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


def _rank_table(algo_summary: List[Dict[str, Any]], key: str, ascending: bool, label: str) -> List[str]:
    ranked = [r for r in algo_summary if r.get(key) is not None]
    ranked.sort(key=lambda r: r[key], reverse=not ascending)
    lines = [f"### Ranking by {label}", ""]
    if not ranked:
        lines.append("_No data available._")
    else:
        for i, r in enumerate(ranked, start=1):
            lines.append(f"{i}. **{_display(r['algorithm_name'])}** — {_fmt(r[key])}")
    lines.append("")
    return lines


def write_markdown_summary(
    results: List[Row],
    out_dir: Path,
    algorithm_summary: Optional[List[Dict[str, Any]]] = None,
    domain_algorithm_summary: Optional[List[Dict[str, Any]]] = None,
    proposed_vs_baselines: Optional[List[Dict[str, Any]]] = None,
) -> Path:
    if algorithm_summary is None:
        algorithm_summary = write_algorithm_summary(results, out_dir)
    if domain_algorithm_summary is None:
        domain_algorithm_summary = write_domain_algorithm_summary(results, out_dir)
    if proposed_vs_baselines is None:
        proposed_vs_baselines = write_proposed_vs_baselines(results, out_dir)

    lines: List[str] = ["# Benchmark Results Summary", ""]

    lines += _rank_table(algorithm_summary, "success_rate", ascending=False, label="success rate")
    lines += _rank_table(
        algorithm_summary, "avg_runtime_s_solved", ascending=True, label="average runtime (solved instances)"
    )
    lines += _rank_table(algorithm_summary, "avg_peak_memory_mb", ascending=True, label="average peak memory")

    lines.append("## Per-domain observations")
    lines.append("")
    domains = sorted({r["domain_name"] for r in domain_algorithm_summary})
    for domain in domains:
        lines.append(f"### {domain}")
        lines.append("")
        for r in sorted(domain_algorithm_summary, key=lambda x: x["algorithm_name"]):
            if r["domain_name"] != domain:
                continue
            lines.append(
                f"- **{_display(r['algorithm_name'])}**: success {_fmt_pct(r['success_rate'])}, "
                f"avg runtime (solved) {_fmt(r['avg_runtime_s_solved'])}s, "
                f"avg peak memory {_fmt(r['avg_peak_memory_mb'])} MB"
            )
        lines.append("")

    # A* on hard Sokoban
    sokoban_hard = [r for r in results if r["domain_name"] == "sokoban" and r["instance_difficulty"] == "hard"]
    astar_hard = [r for r in sokoban_hard if r["algorithm_name"] == ASTAR_NAME]
    lines.append("## Did A* fail on hard Sokoban instances?")
    lines.append("")
    if not astar_hard:
        lines.append("_No hard Sokoban A* runs found in this dataset._")
    else:
        failed = sum(1 for r in astar_hard if not r["success"])
        lines.append(f"A* failed on {failed}/{len(astar_hard)} hard Sokoban instance run(s) in this dataset.")
    lines.append("")

    def _stats_for(name: str, rows: List[Row]) -> Dict[str, Any]:
        return _aggregate([r for r in rows if r["algorithm_name"] == name])

    dyn_stats = _stats_for("dynamic_sma_collapse", results)
    sma_variant_names = _sma_star_variant_names(r["algorithm_name"] for r in results)
    lines.append("## Did Dynamic SMA*-Collapse improve over fixed SMA*?")
    lines.append("")
    lines.append(
        f"Dynamic SMA*-Collapse: success {_fmt_pct(dyn_stats['success_rate'])}, "
        f"avg runtime (solved) {_fmt(dyn_stats['avg_runtime_s_solved'])}s, "
        f"avg peak memory {_fmt(dyn_stats['avg_peak_memory_mb'])} MB."
    )
    if not sma_variant_names:
        lines.append("_No fixed SMA* runs found in this dataset._")
    else:
        for variant in sma_variant_names:
            variant_stats = _stats_for(variant, results)
            lines.append(
                f"Fixed {_display(variant)}: success {_fmt_pct(variant_stats['success_rate'])}, "
                f"avg runtime (solved) {_fmt(variant_stats['avg_runtime_s_solved'])}s, "
                f"avg peak memory {_fmt(variant_stats['avg_peak_memory_mb'])} MB.  "
            )
    lines.append("")

    two_level_stats = _stats_for("two_level_dynamic_sma", results)
    lines.append("## Did Two-Level Dynamic SMA* improve over Dynamic SMA*-Collapse?")
    lines.append("")
    lines.append(
        f"Two-Level Dynamic SMA*: success {_fmt_pct(two_level_stats['success_rate'])}, "
        f"avg runtime (solved) {_fmt(two_level_stats['avg_runtime_s_solved'])}s, "
        f"avg peak memory {_fmt(two_level_stats['avg_peak_memory_mb'])} MB, "
        f"nodes spilled to disk: {two_level_stats['total_nodes_spilled_to_disk']}, "
        f"nodes loaded from disk: {two_level_stats['total_nodes_loaded_from_disk']}.  \n"
        f"Dynamic SMA*-Collapse: success {_fmt_pct(dyn_stats['success_rate'])}, "
        f"avg runtime (solved) {_fmt(dyn_stats['avg_runtime_s_solved'])}s, "
        f"avg peak memory {_fmt(dyn_stats['avg_peak_memory_mb'])} MB."
    )
    lines.append("")

    lines.append("## Tradeoff discussion")
    lines.append("")
    lines.append(f"- **Runtime**: see runtime ranking above; Two-Level Dynamic SMA* pays extra overhead for SQLite I/O "
                  f"(avg disk I/O time across all algorithms: {_fmt(_mean([r['disk_io_time_seconds'] for r in results if r['disk_io_time_seconds'] is not None]))}s).")
    lines.append("- **RAM usage**: see peak-memory ranking above; fixed and dynamic SMA* variants cap resident nodes, "
                 "trading memory for potential extra runtime/collapses.")
    lines.append(f"- **Disk usage**: total nodes spilled to disk across all runs: "
                 f"{sum(r['nodes_spilled_to_disk'] for r in results)}; "
                 f"total nodes loaded back: {sum(r['nodes_loaded_from_disk'] for r in results)}.")
    lines.append(f"- **Collapses**: total nodes collapsed across all runs: {sum(r['nodes_collapsed'] for r in results)}.")
    lines.append(f"- **Solution quality**: average optimality gap vs. A* (where A* solved the same instance): "
                 f"{_fmt(_mean([r['optimality_gap_vs_astar'] for r in results if r['optimality_gap_vs_astar'] is not None]))}.")
    lines.append("")

    lines.append("## Conclusion")
    lines.append("")
    by_success = sorted([r for r in algorithm_summary if r["success_rate"] is not None], key=lambda r: -r["success_rate"])
    strongest_overall = _display(by_success[0]["algorithm_name"]) if by_success else "n/a"
    by_memory = sorted([r for r in algorithm_summary if r["avg_peak_memory_mb"] is not None], key=lambda r: r["avg_peak_memory_mb"])
    strongest_under_pressure = _display(by_memory[0]["algorithm_name"]) if by_memory else "n/a"
    disk_helped = two_level_stats["total_nodes_loaded_from_disk"] > 0
    ram_adapted = (dyn_stats["total_ram_increases"] + dyn_stats["total_ram_decreases"]
                   + two_level_stats["total_ram_increases"] + two_level_stats["total_ram_decreases"]) > 0

    lines.append(f"- **Strongest overall (by success rate)**: {strongest_overall}.")
    lines.append(f"- **Strongest under memory pressure (by avg peak memory)**: {strongest_under_pressure}.")
    lines.append(
        f"- **Did disk spilling help?** "
        f"{'Yes — nodes were loaded back from disk and contributed to search.' if disk_helped else 'No evidence of disk loads contributing in this run.'}"
    )
    lines.append(
        f"- **Did adaptive RAM sizing help?** "
        f"{'RAM capacity was adjusted at least once across the dynamic algorithms.' if ram_adapted else 'No RAM adjustments were triggered in this run (try a longer/harder benchmark to see adaptation).'}"
    )
    lines.append("")

    path = out_dir / "human_readable_summary.md"
    out_dir.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------


def analyze_results(input_csv: Path, output_dir: Path) -> None:
    results = load_results(Path(input_csv))
    add_optimality_gaps(results)

    output_dir = Path(output_dir)
    algorithm_summary = write_algorithm_summary(results, output_dir)
    domain_algorithm_summary = write_domain_algorithm_summary(results, output_dir)
    write_instance_comparison(results, output_dir)
    write_winners_by_instance(results, output_dir)
    proposed_vs_baselines = write_proposed_vs_baselines(results, output_dir)
    write_markdown_summary(
        results,
        output_dir,
        algorithm_summary=algorithm_summary,
        domain_algorithm_summary=domain_algorithm_summary,
        proposed_vs_baselines=proposed_vs_baselines,
    )


def _parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze a benchmark_results.csv and write summary CSVs/Markdown.")
    parser.add_argument("--input", type=str, default="results/benchmark_results.csv")
    parser.add_argument("--output-dir", type=str, default="results/analysis")
    return parser.parse_args()


def main() -> None:
    args = _parse_cli_args()
    analyze_results(Path(args.input), Path(args.output_dir))
    print(f"Wrote analysis to {args.output_dir}")


if __name__ == "__main__":
    main()
