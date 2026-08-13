import csv
import json
from pathlib import Path

from benchmark.analyze import (
    _COMPARISON_PAIRS,
    add_known_optimal_gaps,
    add_optimality_gaps,
    analyze_results,
    compute_astar_reference,
    load_results,
    write_algorithm_summary,
    write_difficulty_summary,
    write_domain_algorithm_summary,
    write_instance_comparison,
    write_markdown_summary,
    write_proposed_vs_baselines,
    write_summary_json,
    write_winners_by_instance,
)

_HEADER = [
    "algorithm_name",
    "domain_name",
    "instance_id",
    "instance_difficulty",
    "success",
    "solution_cost",
    "runtime_seconds",
    "peak_memory_mb",
    "nodes_expanded",
    "nodes_generated",
    "max_frontier_size",
    "max_depth_reached",
    "reexpansions",
    "stack_exhausted",
    "node_limit_reached",
    "memory_limit_reached",
    "error_message",
    "solution_depth",
    "solution_actions",
    "total_collapses",
    "max_proc_tree_size",
    "proc_switches",
    "phase1_expanded",
    "phase2_expanded",
    "actual_num_procs",
    "requested_num_procs",
    "winning_proc_expansions",
]


def _row(**overrides):
    base = {field: "" for field in _HEADER}
    base.update(
        {
            "success": "False",
            "stack_exhausted": "False",
            "node_limit_reached": "False",
            "memory_limit_reached": "False",
            "nodes_expanded": "0",
            "nodes_generated": "0",
        }
    )
    base.update(overrides)
    return base


def _write_fake_csv(path: Path) -> None:
    rows = [
        # n_puzzle / easy_1: both algorithms solve it, A* is the cost reference.
        _row(
            algorithm_name="astar", domain_name="n_puzzle", instance_id="easy_1", instance_difficulty="depth_10",
            success="True", solution_cost="10", solution_depth="10", runtime_seconds="0.01", peak_memory_mb="0.5",
            nodes_expanded="20", nodes_generated="30",
        ),
        _row(
            algorithm_name="ilbfs", domain_name="n_puzzle", instance_id="easy_1", instance_difficulty="depth_10",
            success="True", solution_cost="10", solution_depth="10", runtime_seconds="0.015", peak_memory_mb="0.1",
            nodes_expanded="22", nodes_generated="28",
        ),
        # n_puzzle / hard_1: A* fails (node limit), ILBFS solves it.
        _row(
            algorithm_name="astar", domain_name="n_puzzle", instance_id="hard_1", instance_difficulty="depth_30",
            success="False", node_limit_reached="True", runtime_seconds="5.0", peak_memory_mb="20.0",
            nodes_expanded="50000", nodes_generated="80000",
        ),
        _row(
            algorithm_name="ilbfs", domain_name="n_puzzle", instance_id="hard_1", instance_difficulty="depth_30",
            success="True", solution_cost="30", solution_depth="30", runtime_seconds="2.0", peak_memory_mb="0.01",
            nodes_expanded="40000", nodes_generated="80000",
        ),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_load_results_parses_types_safely(tmp_path: Path):
    csv_path = tmp_path / "benchmark_results.csv"
    _write_fake_csv(csv_path)
    results = load_results(csv_path)
    assert len(results) == 4
    astar_row = next(r for r in results if r["algorithm_name"] == "astar" and r["instance_id"] == "easy_1")
    assert astar_row["success"] is True
    assert astar_row["solution_cost"] == 10.0
    assert isinstance(astar_row["nodes_expanded"], int)

    astar_fail_row = next(r for r in results if r["algorithm_name"] == "astar" and r["instance_id"] == "hard_1")
    assert astar_fail_row["success"] is False
    assert astar_fail_row["solution_cost"] is None


def test_load_results_missing_file_returns_empty_list(tmp_path: Path):
    assert load_results(tmp_path / "does_not_exist.csv") == []


def test_compute_astar_reference_and_optimality_gaps(tmp_path: Path):
    csv_path = tmp_path / "benchmark_results.csv"
    _write_fake_csv(csv_path)
    results = load_results(csv_path)
    reference = compute_astar_reference(results)
    assert reference[("n_puzzle", "easy_1")] == 10.0
    assert ("n_puzzle", "hard_1") not in reference  # A* didn't solve it

    add_optimality_gaps(results, reference)
    ilbfs_easy = next(r for r in results if r["algorithm_name"] == "ilbfs" and r["instance_id"] == "easy_1")
    assert ilbfs_easy["optimality_gap_vs_astar"] == 0.0  # 10 - 10
    ilbfs_hard = next(r for r in results if r["algorithm_name"] == "ilbfs" and r["instance_id"] == "hard_1")
    assert ilbfs_hard["optimality_gap_vs_astar"] is None  # A* never solved hard_1


def test_write_algorithm_summary_has_header_even_with_no_rows(tmp_path: Path):
    out_dir = tmp_path / "analysis"
    rows = write_algorithm_summary([], out_dir)
    assert rows == []
    csv_path = out_dir / "algorithm_summary.csv"
    assert csv_path.exists()
    with csv_path.open() as f:
        header = f.readline().strip()
    assert "algorithm_name" in header


def test_write_algorithm_summary_aggregates_correctly(tmp_path: Path):
    csv_path = tmp_path / "benchmark_results.csv"
    _write_fake_csv(csv_path)
    results = load_results(csv_path)
    add_optimality_gaps(results)
    out_dir = tmp_path / "analysis"
    rows = write_algorithm_summary(results, out_dir)
    astar_summary = next(r for r in rows if r["algorithm_name"] == "astar")
    assert astar_summary["total_runs"] == 2
    assert astar_summary["solved_runs"] == 1
    assert astar_summary["failed_runs"] == 1
    assert astar_summary["success_rate"] == 0.5


def test_write_domain_algorithm_summary(tmp_path: Path):
    csv_path = tmp_path / "benchmark_results.csv"
    _write_fake_csv(csv_path)
    results = load_results(csv_path)
    add_optimality_gaps(results)
    rows = write_domain_algorithm_summary(results, tmp_path / "analysis")
    n_puzzle_astar = next(r for r in rows if r["domain_name"] == "n_puzzle" and r["algorithm_name"] == "astar")
    assert n_puzzle_astar["success_rate"] == 0.5


def test_write_instance_comparison_row_count(tmp_path: Path):
    csv_path = tmp_path / "benchmark_results.csv"
    _write_fake_csv(csv_path)
    results = load_results(csv_path)
    add_optimality_gaps(results)
    rows = write_instance_comparison(results, tmp_path / "analysis")
    assert len(rows) == 4


def test_winners_by_instance_notes_for_easy_instance(tmp_path: Path):
    csv_path = tmp_path / "benchmark_results.csv"
    _write_fake_csv(csv_path)
    results = load_results(csv_path)
    add_optimality_gaps(results)
    rows = write_winners_by_instance(results, tmp_path / "analysis")

    easy_row = next(r for r in rows if r["instance_id"] == "easy_1")
    assert easy_row["fastest_successful_algorithm"] == "astar"
    assert "A* solved fastest" in easy_row["notes"]

    hard_row = next(r for r in rows if r["instance_id"] == "hard_1")
    assert hard_row["fastest_successful_algorithm"] == "ilbfs"


def test_winners_by_instance_all_failed_note(tmp_path: Path):
    csv_path = tmp_path / "benchmark_results.csv"
    rows = [
        _row(algorithm_name="astar", domain_name="x", instance_id="impossible", success="False", node_limit_reached="True"),
        _row(algorithm_name="ilbfs", domain_name="x", instance_id="impossible", success="False", node_limit_reached="True"),
    ]
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    results = load_results(csv_path)
    add_optimality_gaps(results)
    winners = write_winners_by_instance(results, tmp_path / "analysis")
    assert winners[0]["notes"] == "All algorithms failed"
    assert winners[0]["fastest_successful_algorithm"] is None


def test_proposed_vs_baselines_groups_and_ratios(tmp_path: Path):
    csv_path = tmp_path / "benchmark_results.csv"
    _write_fake_csv(csv_path)
    results = load_results(csv_path)
    add_optimality_gaps(results)
    rows = write_proposed_vs_baselines(results, tmp_path / "analysis")
    assert any(r["proposed_algorithm"] == "mp-rbfs-best_first" and r["baseline_algorithm"] == "ilbfs" for r in rows)
    assert any(r["proposed_algorithm"] == "mp-bfs-best_first" and r["baseline_algorithm"] == "astar" for r in rows)

    # The fake CSV only contains astar/ilbfs, so the proposed side is empty data.
    rbfs_vs_ilbfs = next(
        r for r in rows if r["proposed_algorithm"] == "mp-rbfs-best_first" and r["baseline_algorithm"] == "ilbfs"
    )
    assert rbfs_vs_ilbfs["group_name"] == "all_domains"
    assert rbfs_vs_ilbfs["proposed_success_rate"] is None
    assert rbfs_vs_ilbfs["baseline_success_rate"] == 1.0  # ILBFS solves easy_1 and hard_1


def test_proposed_vs_baselines_handles_zero_denominator(tmp_path: Path):
    csv_path = tmp_path / "benchmark_results.csv"
    rows = [
        _row(
            algorithm_name="astar", domain_name="x", instance_id="i1", success="True",
            solution_cost="5", solution_depth="5", runtime_seconds="0.1",
        )
    ]
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    results = load_results(csv_path)
    add_optimality_gaps(results)
    out_rows = write_proposed_vs_baselines(results, tmp_path / "analysis")
    # Only astar is present: ratios against a missing algorithm must be None, not a crash.
    astar_pair = next(
        r for r in out_rows if r["proposed_algorithm"] == "mp-bfs-best_first" and r["baseline_algorithm"] == "astar"
    )
    assert astar_pair["proposed_success_rate"] is None
    assert astar_pair["runtime_ratio_proposed_over_baseline"] is None


def test_load_results_parses_multi_path_count_fields(tmp_path: Path):
    rows = [
        _row(
            algorithm_name="mp-rbfs-best_first", domain_name="n_puzzle", instance_id="d24",
            instance_difficulty="amit_depth_24", success="True", solution_cost="24",
            solution_depth="24", runtime_seconds="1.9", peak_memory_mb="2.0",
            nodes_expanded="35510", nodes_generated="63812", reexpansions="6652",
            total_collapses="35043", max_proc_tree_size="45", proc_switches="1234",
            phase1_expanded="17", phase2_expanded="35493", actual_num_procs="18",
            requested_num_procs="100", winning_proc_expansions="20000",
        )
    ]
    csv_path = tmp_path / "benchmark_results.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    results = load_results(csv_path)
    row = results[0]
    assert row["total_collapses"] == 35043
    assert row["max_proc_tree_size"] == 45
    assert row["proc_switches"] == 1234
    assert row["phase1_expanded"] == 17
    assert row["phase2_expanded"] == 35493
    assert row["actual_num_procs"] == 18
    assert row["requested_num_procs"] == 100
    assert row["winning_proc_expansions"] == 20000


def test_write_difficulty_summary_groups_by_difficulty(tmp_path: Path):
    csv_path = tmp_path / "benchmark_results.csv"
    _write_fake_csv(csv_path)
    results = load_results(csv_path)
    add_optimality_gaps(results)
    rows = write_difficulty_summary(results, tmp_path / "analysis")
    assert len(rows) == 4  # depth_10 x {astar, ilbfs} + depth_30 x {astar, ilbfs}
    assert rows[0]["difficulty_depth"] == 10  # sorted by depth
    d10_ilbfs = next(r for r in rows if r["difficulty_label"] == "depth_10" and r["algorithm_name"] == "ilbfs")
    assert d10_ilbfs["success_rate"] == 1.0
    assert d10_ilbfs["difficulty_depth"] == 10
    d30_astar = next(r for r in rows if r["difficulty_label"] == "depth_30" and r["algorithm_name"] == "astar")
    assert d30_astar["success_rate"] == 0.0
    assert d30_astar["node_limit_rate"] == 1.0


def test_write_summary_json_bundles_curated_views(tmp_path: Path):
    csv_path = tmp_path / "benchmark_results.csv"
    _write_fake_csv(csv_path)
    results = load_results(csv_path)
    add_optimality_gaps(results)
    path = write_summary_json(results, tmp_path / "analysis")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["input_rows"] == 4
    assert len(payload["algorithms"]) == 2
    assert len(payload["difficulties"]) == 4
    assert len(payload["comparisons"]) == len(_COMPARISON_PAIRS) * 2  # all_domains + n_puzzle


def test_analyze_results_end_to_end_produces_all_files(tmp_path: Path):
    csv_path = tmp_path / "benchmark_results.csv"
    _write_fake_csv(csv_path)
    out_dir = tmp_path / "analysis"
    analyze_results(csv_path, out_dir)

    expected_files = [
        "algorithm_summary.csv",
        "domain_algorithm_summary.csv",
        "by_difficulty_summary.csv",
        "winners_by_instance.csv",
        "proposed_algorithms_vs_baselines.csv",
        "summary.json",
        "human_readable_summary.md",
    ]
    for filename in expected_files:
        path = out_dir / filename
        assert path.exists(), f"missing {filename}"
        assert path.stat().st_size > 0

    summary_json = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert {"algorithms", "difficulties", "comparisons"} <= set(summary_json)

    markdown = (out_dir / "human_readable_summary.md").read_text(encoding="utf-8")
    assert "# Benchmark Results Summary" in markdown
    assert "Per-difficulty results" in markdown
    assert "Conclusion" in markdown
