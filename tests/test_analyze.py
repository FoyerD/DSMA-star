import csv
from pathlib import Path

from benchmark.analyze import (
    _is_sma_star_variant,
    _sma_star_variant_names,
    add_known_optimal_gaps,
    add_optimality_gaps,
    analyze_results,
    compute_astar_reference,
    load_results,
    write_algorithm_summary,
    write_domain_algorithm_summary,
    write_instance_comparison,
    write_markdown_summary,
    write_proposed_vs_baselines,
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
    "nodes_collapsed",
    "nodes_spilled_to_disk",
    "nodes_loaded_from_disk",
    "disk_batches_loaded",
    "disk_peak_nodes",
    "disk_read_count",
    "disk_write_count",
    "disk_io_time_seconds",
    "ram_capacity_initial",
    "ram_capacity_final",
    "ram_capacity_peak",
    "ram_capacity_min",
    "number_of_ram_increases",
    "number_of_ram_decreases",
    "number_of_total_collapses",
    "stale_disk_nodes_skipped",
    "duplicate_nodes_skipped",
    "solution_depth",
    "solution_actions",
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
            "nodes_collapsed": "0",
            "nodes_spilled_to_disk": "0",
            "nodes_loaded_from_disk": "0",
            "disk_batches_loaded": "0",
            "disk_peak_nodes": "0",
            "number_of_ram_increases": "0",
            "number_of_ram_decreases": "0",
        }
    )
    base.update(overrides)
    return base


def _write_fake_csv(path: Path) -> None:
    rows = [
        # n_puzzle / easy_1: everyone solves it, A* is the cost reference.
        _row(
            algorithm_name="astar", domain_name="n_puzzle", instance_id="easy_1", instance_difficulty="depth_10",
            success="True", solution_cost="10", solution_depth="10", runtime_seconds="0.01", peak_memory_mb="0.5",
            nodes_expanded="20", nodes_generated="30",
        ),
        _row(
            algorithm_name="sma_star", domain_name="n_puzzle", instance_id="easy_1", instance_difficulty="depth_10",
            success="True", solution_cost="12", solution_depth="12", runtime_seconds="0.02", peak_memory_mb="0.3",
            nodes_expanded="25", nodes_generated="35", nodes_collapsed="2",
        ),
        _row(
            algorithm_name="ilbfs", domain_name="n_puzzle", instance_id="easy_1", instance_difficulty="depth_10",
            success="True", solution_cost="10", solution_depth="10", runtime_seconds="0.015", peak_memory_mb="0.1",
            nodes_expanded="22", nodes_generated="28",
        ),
        _row(
            algorithm_name="dynamic_sma_collapse", domain_name="n_puzzle", instance_id="easy_1",
            instance_difficulty="depth_10", success="True", solution_cost="10", solution_depth="10",
            runtime_seconds="0.03", peak_memory_mb="0.4", nodes_expanded="40", nodes_generated="100",
            nodes_collapsed="40",  # heavy collapsing -> should trigger the "many collapses" note
        ),
        _row(
            algorithm_name="two_level_dynamic_sma", domain_name="n_puzzle", instance_id="easy_1",
            instance_difficulty="depth_10", success="True", solution_cost="10", solution_depth="10",
            runtime_seconds="0.05", peak_memory_mb="0.2", nodes_expanded="20", nodes_generated="30",
            nodes_spilled_to_disk="5", nodes_loaded_from_disk="3", disk_io_time_seconds="0.001",
        ),
        # sokoban / hard_1: A* fails (node limit), only Two-Level solves it.
        _row(
            algorithm_name="astar", domain_name="sokoban", instance_id="hard_1", instance_difficulty="hard",
            success="False", node_limit_reached="True", runtime_seconds="5.0", peak_memory_mb="20.0",
            nodes_expanded="50000", nodes_generated="80000",
        ),
        _row(
            algorithm_name="sma_star", domain_name="sokoban", instance_id="hard_1", instance_difficulty="hard",
            success="False", memory_limit_reached="True", runtime_seconds="5.0", peak_memory_mb="3.0",
            nodes_expanded="10000", nodes_generated="9000",
        ),
        _row(
            algorithm_name="ilbfs", domain_name="sokoban", instance_id="hard_1", instance_difficulty="hard",
            success="False", node_limit_reached="True", runtime_seconds="5.0", peak_memory_mb="0.01",
            nodes_expanded="40000", nodes_generated="80000",
        ),
        _row(
            algorithm_name="dynamic_sma_collapse", domain_name="sokoban", instance_id="hard_1",
            instance_difficulty="hard", success="False", memory_limit_reached="True", runtime_seconds="5.0",
            peak_memory_mb="1.5", nodes_expanded="17000", nodes_generated="25000", nodes_collapsed="24000",
        ),
        _row(
            algorithm_name="two_level_dynamic_sma", domain_name="sokoban", instance_id="hard_1",
            instance_difficulty="hard", success="True", solution_cost="40", solution_depth="40",
            runtime_seconds="4.0", peak_memory_mb="1.0", nodes_expanded="1200", nodes_generated="2000",
            nodes_spilled_to_disk="500", nodes_loaded_from_disk="450", disk_io_time_seconds="0.05",
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
    assert len(results) == 10
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
    assert ("sokoban", "hard_1") not in reference  # A* didn't solve it

    add_optimality_gaps(results, reference)
    sma = next(r for r in results if r["algorithm_name"] == "sma_star" and r["instance_id"] == "easy_1")
    assert sma["optimality_gap_vs_astar"] == 2.0  # 12 - 10
    two_level_hard = next(
        r for r in results if r["algorithm_name"] == "two_level_dynamic_sma" and r["instance_id"] == "hard_1"
    )
    assert two_level_hard["optimality_gap_vs_astar"] is None  # A* never solved hard_1


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
    sokoban_astar = next(r for r in rows if r["domain_name"] == "sokoban" and r["algorithm_name"] == "astar")
    assert sokoban_astar["success_rate"] == 0.0


def test_write_instance_comparison_row_count(tmp_path: Path):
    csv_path = tmp_path / "benchmark_results.csv"
    _write_fake_csv(csv_path)
    results = load_results(csv_path)
    add_optimality_gaps(results)
    rows = write_instance_comparison(results, tmp_path / "analysis")
    assert len(rows) == 10


def test_winners_by_instance_notes_for_hard_instance(tmp_path: Path):
    csv_path = tmp_path / "benchmark_results.csv"
    _write_fake_csv(csv_path)
    results = load_results(csv_path)
    add_optimality_gaps(results)
    rows = write_winners_by_instance(results, tmp_path / "analysis")
    hard_row = next(r for r in rows if r["instance_id"] == "hard_1")
    assert hard_row["astar_solved"] is False
    assert hard_row["two_level_dynamic_sma_solved"] is True
    assert "A* failed" in hard_row["notes"]
    assert "Two-Level used disk" in hard_row["notes"]
    assert "Dynamic collapse had many collapses" in hard_row["notes"]

    easy_row = next(r for r in rows if r["instance_id"] == "easy_1")
    assert easy_row["fastest_successful_algorithm"] == "astar"
    assert "A* solved fastest" in easy_row["notes"]


def test_winners_by_instance_all_failed_note(tmp_path: Path):
    # An instance where literally everyone fails.
    csv_path = tmp_path / "benchmark_results.csv"
    rows = [
        _row(algorithm_name="astar", domain_name="x", instance_id="impossible", success="False", node_limit_reached="True"),
        _row(algorithm_name="sma_star", domain_name="x", instance_id="impossible", success="False", memory_limit_reached="True"),
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
    group_names = {r["group_name"] for r in rows}
    assert "all_domains" in group_names
    assert "n_puzzle" in group_names
    assert "sokoban" in group_names

    pair_names = {(r["proposed_algorithm"], r["baseline_algorithm"]) for r in rows}
    assert ("two_level_dynamic_sma", "dynamic_sma_collapse") in pair_names
    assert ("dynamic_sma_collapse", "astar") in pair_names

    two_level_vs_astar_sokoban = next(
        r
        for r in rows
        if r["group_name"] == "sokoban" and r["proposed_algorithm"] == "two_level_dynamic_sma" and r["baseline_algorithm"] == "astar"
    )
    # Two-Level solved hard_1, A* did not -> proposed success rate should exceed baseline's.
    assert two_level_vs_astar_sokoban["success_rate_delta"] > 0
    assert two_level_vs_astar_sokoban["interpretation"]  # non-empty sentence


def test_proposed_vs_baselines_handles_zero_denominator(tmp_path: Path):
    # baseline never appears at all in this dataset -> ratios must be None, not crash.
    csv_path = tmp_path / "benchmark_results.csv"
    rows = [
        _row(
            algorithm_name="dynamic_sma_collapse", domain_name="x", instance_id="i1", success="True",
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
    comparison = next(
        r for r in out_rows if r["group_name"] == "all_domains" and r["proposed_algorithm"] == "dynamic_sma_collapse" and r["baseline_algorithm"] == "astar"
    )
    assert comparison["baseline_success_rate"] is None
    assert comparison["runtime_ratio_proposed_over_baseline"] is None


def test_is_sma_star_variant_matches_memory_named_and_legacy_labels():
    assert _is_sma_star_variant("sma_star")  # legacy, pre-multi-memory label
    assert _is_sma_star_variant("SMA* (memory=10000)")
    assert _is_sma_star_variant("SMA* (memory=50000)")
    assert not _is_sma_star_variant("dynamic_sma_collapse")
    assert not _is_sma_star_variant("SMA*")  # missing the "(memory=N)" suffix


def test_sma_star_variant_names_dedupes_and_sorts():
    names = ["astar", "SMA* (memory=50000)", "SMA* (memory=10000)", "ilbfs", "SMA* (memory=10000)"]
    assert _sma_star_variant_names(names) == ["SMA* (memory=10000)", "SMA* (memory=50000)"]


def _write_multi_memory_sma_csv(path: Path) -> None:
    rows = [
        _row(
            algorithm_name="astar", domain_name="n_puzzle", instance_id="easy_1", instance_difficulty="depth_10",
            success="True", solution_cost="10", solution_depth="10", runtime_seconds="0.01", peak_memory_mb="0.5",
            nodes_expanded="20", nodes_generated="30",
        ),
        _row(
            algorithm_name="SMA* (memory=10000)", domain_name="n_puzzle", instance_id="easy_1",
            instance_difficulty="depth_10", success="True", solution_cost="12", solution_depth="12",
            runtime_seconds="0.02", peak_memory_mb="0.3", nodes_expanded="25", nodes_generated="35",
        ),
        _row(
            algorithm_name="SMA* (memory=50000)", domain_name="n_puzzle", instance_id="easy_1",
            instance_difficulty="depth_10", success="True", solution_cost="10", solution_depth="10",
            runtime_seconds="0.04", peak_memory_mb="0.6", nodes_expanded="18", nodes_generated="27",
        ),
        _row(
            algorithm_name="dynamic_sma_collapse", domain_name="n_puzzle", instance_id="easy_1",
            instance_difficulty="depth_10", success="True", solution_cost="10", solution_depth="10",
            runtime_seconds="0.03", peak_memory_mb="0.4", nodes_expanded="40", nodes_generated="100",
        ),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_multi_memory_sma_star_runs_are_grouped_as_distinct_algorithms(tmp_path: Path):
    csv_path = tmp_path / "benchmark_results.csv"
    _write_multi_memory_sma_csv(csv_path)
    results = load_results(csv_path)
    add_optimality_gaps(results)

    summary_rows = write_algorithm_summary(results, tmp_path / "analysis")
    summary_names = {r["algorithm_name"] for r in summary_rows}
    assert "SMA* (memory=10000)" in summary_names
    assert "SMA* (memory=50000)" in summary_names

    sma_10k = next(r for r in summary_rows if r["algorithm_name"] == "SMA* (memory=10000)")
    sma_50k = next(r for r in summary_rows if r["algorithm_name"] == "SMA* (memory=50000)")
    assert sma_10k["total_runs"] == 1
    assert sma_50k["total_runs"] == 1
    assert sma_10k["avg_peak_memory_mb"] != sma_50k["avg_peak_memory_mb"]


def test_proposed_vs_baselines_expands_sma_star_placeholder_per_memory_variant(tmp_path: Path):
    csv_path = tmp_path / "benchmark_results.csv"
    _write_multi_memory_sma_csv(csv_path)
    results = load_results(csv_path)
    add_optimality_gaps(results)

    rows = write_proposed_vs_baselines(results, tmp_path / "analysis")
    pair_names = {(r["proposed_algorithm"], r["baseline_algorithm"]) for r in rows}
    # Both SMA* memory variants get their own baseline comparison row, instead
    # of a single opaque "sma_star" row that wouldn't match either variant.
    assert ("dynamic_sma_collapse", "SMA* (memory=10000)") in pair_names
    assert ("dynamic_sma_collapse", "SMA* (memory=50000)") in pair_names
    assert ("dynamic_sma_collapse", "sma_star") not in pair_names


def test_markdown_summary_lists_each_sma_star_memory_variant(tmp_path: Path):
    csv_path = tmp_path / "benchmark_results.csv"
    _write_multi_memory_sma_csv(csv_path)
    results = load_results(csv_path)
    add_optimality_gaps(results)

    out_dir = tmp_path / "analysis"
    write_markdown_summary(results, out_dir)
    markdown = (out_dir / "human_readable_summary.md").read_text(encoding="utf-8")
    assert "SMA* (memory=10000)" in markdown
    assert "SMA* (memory=50000)" in markdown


def test_analyze_results_end_to_end_produces_all_files(tmp_path: Path):
    csv_path = tmp_path / "benchmark_results.csv"
    _write_fake_csv(csv_path)
    out_dir = tmp_path / "analysis"
    analyze_results(csv_path, out_dir)

    expected_files = [
        "algorithm_summary.csv",
        "domain_algorithm_summary.csv",
        "instance_comparison.csv",
        "winners_by_instance.csv",
        "proposed_algorithms_vs_baselines.csv",
        "human_readable_summary.md",
    ]
    for filename in expected_files:
        path = out_dir / filename
        assert path.exists(), f"missing {filename}"
        assert path.stat().st_size > 0

    markdown = (out_dir / "human_readable_summary.md").read_text(encoding="utf-8")
    assert "# Benchmark Results Summary" in markdown
    assert "Conclusion" in markdown


# --------------------------------------------------------------------------
# nodes_restored: old CSVs (written before this field existed) must not crash
# and must default the missing column to 0; new CSVs must aggregate it correctly.
# --------------------------------------------------------------------------


def test_load_results_missing_nodes_restored_defaults_to_zero(tmp_path: Path):
    # _HEADER (above) intentionally has no "nodes_restored" column, simulating
    # a benchmark_results.csv written before this field was added.
    csv_path = tmp_path / "benchmark_results.csv"
    _write_fake_csv(csv_path)
    results = load_results(csv_path)
    assert results  # sanity: old-format file still loads rows
    for row in results:
        assert row["nodes_restored"] == 0
        assert isinstance(row["nodes_restored"], int)


def test_algorithm_summary_has_total_nodes_restored_column_even_for_old_csv(tmp_path: Path):
    csv_path = tmp_path / "benchmark_results.csv"
    _write_fake_csv(csv_path)
    results = load_results(csv_path)
    add_optimality_gaps(results)
    add_known_optimal_gaps(results)
    rows = write_algorithm_summary(results, tmp_path / "analysis")
    for row in rows:
        assert row["total_nodes_restored"] == 0


def test_domain_algorithm_summary_has_total_nodes_restored_column(tmp_path: Path):
    csv_path = tmp_path / "benchmark_results.csv"
    _write_fake_csv(csv_path)
    results = load_results(csv_path)
    add_optimality_gaps(results)
    add_known_optimal_gaps(results)
    rows = write_domain_algorithm_summary(results, tmp_path / "analysis")
    for row in rows:
        assert row["total_nodes_restored"] == 0


def test_proposed_vs_baselines_has_proposed_total_restored_column(tmp_path: Path):
    csv_path = tmp_path / "benchmark_results.csv"
    _write_fake_csv(csv_path)
    results = load_results(csv_path)
    add_optimality_gaps(results)
    add_known_optimal_gaps(results)
    rows = write_proposed_vs_baselines(results, tmp_path / "analysis")
    for row in rows:
        assert row["proposed_total_restored"] == 0


_NEW_HEADER = _HEADER + ["instance_source", "known_optimal_depth", "nodes_restored"]


def _write_csv_with_restores(path: Path) -> None:
    rows = [
        _row(
            algorithm_name="dynamic_sma_collapse", domain_name="n_puzzle", instance_id="korf1_d52",
            instance_difficulty="korf_depth_52", success="True", solution_cost="52", solution_depth="52",
            runtime_seconds="1.0", peak_memory_mb="10.0", nodes_expanded="500", nodes_generated="900",
            nodes_collapsed="300", instance_source="korf100", known_optimal_depth="52", nodes_restored="3",
        ),
        _row(
            algorithm_name="dynamic_sma_collapse", domain_name="n_puzzle", instance_id="korf2_d55",
            instance_difficulty="korf_depth_55", success="True", solution_cost="55", solution_depth="55",
            runtime_seconds="2.0", peak_memory_mb="12.0", nodes_expanded="700", nodes_generated="1300",
            nodes_collapsed="400", instance_source="korf100", known_optimal_depth="55", nodes_restored="7",
        ),
        _row(
            algorithm_name="astar", domain_name="n_puzzle", instance_id="korf1_d52",
            instance_difficulty="korf_depth_52", success="True", solution_cost="52", solution_depth="52",
            runtime_seconds="0.5", peak_memory_mb="8.0", nodes_expanded="400", nodes_generated="600",
            instance_source="korf100", known_optimal_depth="52",
        ),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_NEW_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_nodes_restored_aggregated_correctly_from_new_format_csv(tmp_path: Path):
    csv_path = tmp_path / "benchmark_results.csv"
    _write_csv_with_restores(csv_path)
    results = load_results(csv_path)
    add_optimality_gaps(results)
    add_known_optimal_gaps(results)

    rows = write_algorithm_summary(results, tmp_path / "analysis")
    dyn_row = next(r for r in rows if r["algorithm_name"] == "dynamic_sma_collapse")
    assert dyn_row["total_nodes_collapsed"] == 700
    assert dyn_row["total_nodes_restored"] == 10

    astar_row = next(r for r in rows if r["algorithm_name"] == "astar")
    assert astar_row["total_nodes_restored"] == 0


def test_instance_comparison_includes_known_optimal_depth_and_gap(tmp_path: Path):
    csv_path = tmp_path / "benchmark_results.csv"
    _write_csv_with_restores(csv_path)
    results = load_results(csv_path)
    add_optimality_gaps(results)
    add_known_optimal_gaps(results)
    rows = write_instance_comparison(results, tmp_path / "analysis")
    dyn_row = next(r for r in rows if r["algorithm_name"] == "dynamic_sma_collapse" and r["instance_id"] == "korf1_d52")
    assert dyn_row["known_optimal_depth"] == 52.0
    assert dyn_row["optimality_gap_vs_known_optimal"] == 0.0  # solved exactly at the true optimal depth
    assert dyn_row["nodes_restored"] == 3
    assert dyn_row["instance_source"] == "korf100"


def test_proposed_vs_baselines_reports_total_restored_from_new_format_csv(tmp_path: Path):
    csv_path = tmp_path / "benchmark_results.csv"
    _write_csv_with_restores(csv_path)
    results = load_results(csv_path)
    add_optimality_gaps(results)
    add_known_optimal_gaps(results)
    rows = write_proposed_vs_baselines(results, tmp_path / "analysis")
    comparison = next(
        r for r in rows if r["group_name"] == "all_domains"
        and r["proposed_algorithm"] == "dynamic_sma_collapse" and r["baseline_algorithm"] == "astar"
    )
    assert comparison["proposed_total_restored"] == 10


def test_analyze_results_end_to_end_still_works_with_new_format_csv(tmp_path: Path):
    csv_path = tmp_path / "benchmark_results.csv"
    _write_csv_with_restores(csv_path)
    out_dir = tmp_path / "analysis"
    analyze_results(csv_path, out_dir)
    for filename in [
        "algorithm_summary.csv",
        "domain_algorithm_summary.csv",
        "instance_comparison.csv",
        "winners_by_instance.csv",
        "proposed_algorithms_vs_baselines.csv",
        "human_readable_summary.md",
    ]:
        path = out_dir / filename
        assert path.exists() and path.stat().st_size > 0

    markdown = (out_dir / "human_readable_summary.md").read_text(encoding="utf-8")
    assert "Collapse and restore behavior" in markdown
    assert "restored" in markdown
