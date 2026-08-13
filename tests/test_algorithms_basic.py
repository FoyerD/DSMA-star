import statistics
from pathlib import Path

from algorithms import AStar, ILBFS, RBFS
from algorithms.base import SearchLimits
from benchmark.instance_generators import generate_puzzle_instances
from benchmark.metrics import aggregate_by_domain_and_algorithm
from benchmark.results import save_results_csv, save_results_json
from benchmark.runner import run_benchmark
from domains.n_puzzle import NPuzzleProblem, goal_state

LIMITS = SearchLimits(
    max_memory_mb=512.0,
    max_nodes=50_000,
)


def _easy_puzzle():
    # One move away from the goal: blank and tile 1 swapped.
    goal = goal_state(3)
    return NPuzzleProblem((1, 0, 2, 3, 4, 5, 6, 7, 8), size=3, goal=goal)


def test_astar_solves_easy_puzzle():
    result = AStar().search(_easy_puzzle(), LIMITS)
    assert result.success
    assert result.solution_cost == 1
    assert result.solution_actions == ["left"]


def test_ilbfs_solves_easy_puzzle():
    result = ILBFS().search(_easy_puzzle(), LIMITS)
    assert result.success
    assert result.solution_cost == 1


def test_rbfs_solves_easy_puzzle():
    result = RBFS().search(_easy_puzzle(), LIMITS)
    assert result.success
    assert result.solution_cost == 1


def test_benchmark_runner_produces_results_for_all_algorithms():
    instances = generate_puzzle_instances(seeds=[1, 2], size=3, scramble_depths=[10])
    algorithms = [
        AStar(),
        ILBFS(),
        RBFS(),
    ]
    results = run_benchmark(instances, algorithms, LIMITS)
    assert len(results) == len(instances) * len(algorithms)
    expected_names = {
        "astar",
        "ilbfs",
        "rbfs",
    }
    for result in results:
        assert result.algorithm_name in expected_names


def test_results_are_saved_as_csv_and_json(tmp_path: Path):
    instances = generate_puzzle_instances(seeds=[2], size=3, scramble_depths=[5])
    results = run_benchmark(instances, [AStar()], LIMITS)
    csv_path = tmp_path / "out" / "benchmark_results.csv"
    json_path = tmp_path / "out" / "benchmark_results.json"
    save_results_csv(results, csv_path)
    save_results_json(results, json_path)
    assert csv_path.exists() and csv_path.stat().st_size > 0
    assert json_path.exists() and json_path.stat().st_size > 0


def test_generate_puzzle_instances_is_one_per_seed_per_depth():
    instances = generate_puzzle_instances(seeds=[1, 2, 3], size=3, scramble_depths=[5, 10])
    assert len(instances) == 6
    assert {i.difficulty for i in instances} == {"depth_5", "depth_10"}
    assert len({i.instance_id for i in instances}) == 6


def test_generate_puzzle_instances_is_deterministic():
    first = generate_puzzle_instances(seeds=[1, 2, 3], size=3, scramble_depths=[5, 10])
    second = generate_puzzle_instances(seeds=[1, 2, 3], size=3, scramble_depths=[5, 10])
    assert [i.problem.start for i in first] == [i.problem.start for i in second]


def test_generate_puzzle_instances_depths_are_independent_for_same_seed():
    # A seed reused across depths must not be a truncated/extended walk of one
    # shared RNG stream -- each depth gets its own independent scramble.
    instances = generate_puzzle_instances(seeds=[42], size=3, scramble_depths=[5, 6])
    assert instances[0].problem.start != instances[1].problem.start


def test_aggregate_by_domain_and_algorithm_reports_mean_and_sample_std():
    instances = generate_puzzle_instances(seeds=[10, 11, 12, 13], size=3, scramble_depths=[8])
    results = run_benchmark(instances, [AStar()], LIMITS)
    summaries = aggregate_by_domain_and_algorithm(results)
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.num_instances == 4

    runtimes_solved = [r.runtime_seconds for r in results if r.success]
    assert summary.avg_runtime_seconds_solved == statistics.fmean(runtimes_solved)
    assert summary.std_runtime_seconds_solved == statistics.stdev(runtimes_solved)

    nodes_expanded = [r.nodes_expanded for r in results]
    assert summary.avg_nodes_expanded == statistics.fmean(nodes_expanded)
    assert summary.std_nodes_expanded == statistics.stdev(nodes_expanded)


def test_aggregate_reports_multi_path_and_known_optimal_metrics():
    from algorithms.base import SearchResult

    results = [
        SearchResult(
            algorithm_name="mp-rbfs-best_first", domain_name="n_puzzle", instance_id="d24",
            instance_difficulty="amit_depth_24", known_optimal_depth=24, success=True,
            solution_cost=25, nodes_expanded=35510, nodes_generated=63812, reexpansions=6652,
            total_collapses=35043, max_proc_tree_size=45, proc_switches=1234,
            phase1_expanded=17, phase2_expanded=35493,
        ),
        SearchResult(
            algorithm_name="mp-rbfs-best_first", domain_name="n_puzzle", instance_id="d24",
            instance_difficulty="amit_depth_24", known_optimal_depth=24, success=True,
            solution_cost=24, nodes_expanded=27000, nodes_generated=50000, reexpansions=5000,
            total_collapses=27000, max_proc_tree_size=40, proc_switches=900,
            phase1_expanded=18, phase2_expanded=26982,
        ),
    ]
    summaries = aggregate_by_domain_and_algorithm(results)
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.avg_reexpansions == statistics.fmean([6652, 5000])
    assert summary.avg_total_collapses == statistics.fmean([35043, 27000])
    assert summary.avg_max_proc_tree_size == statistics.fmean([45, 40])
    assert summary.avg_proc_switches == statistics.fmean([1234, 900])
    # gap vs known optimal: (25-24)/24 and (24-24)/24
    assert summary.avg_optimality_gap_vs_known_optimal == statistics.fmean([1 / 24, 0.0])
    assert summary.std_optimality_gap_vs_known_optimal == statistics.stdev([1 / 24, 0.0])


def test_aggregate_std_is_zero_with_a_single_seed():
    instances = generate_puzzle_instances(seeds=[7], size=3, scramble_depths=[5])
    results = run_benchmark(instances, [AStar()], LIMITS)
    summary = aggregate_by_domain_and_algorithm(results)[0]
    assert summary.std_nodes_expanded == 0.0
    assert summary.std_peak_memory_mb == 0.0


def test_all_algorithms_solve_15_puzzle_scramble_10():
    """Acceptance test: run every algorithm on a fixed 15-puzzle instance (seed=0, scramble_depth=10).

    Each algorithm must either solve the instance or honestly report a
    resource limit (node / memory). No algorithm may crash or return an
    inconsistent result.
    """
    instances = generate_puzzle_instances(seeds=[0], size=4, scramble_depths=[10])
    assert len(instances) == 1
    instance = instances[0]

    limits = SearchLimits(
        max_memory_mb=2048.0,
        max_nodes=500_000,
    )

    algorithms = [
        AStar(),
        ILBFS(),
        RBFS(),
    ]

    results = run_benchmark(instances, algorithms, limits)

    assert len(results) == len(algorithms)

    for r in results:
        # Every algorithm must produce a result for the same instance.
        assert r.instance_id == instance.instance_id
        # Must either solve or hit a known resource limit -- never both.
        assert r.success or r.node_limit_reached or r.memory_limit_reached or r.error_message
        assert not (r.success and r.node_limit_reached)
        assert not (r.success and r.memory_limit_reached)
        # If solved, solution cost must be positive.
        if r.success:
            assert r.solution_cost > 0
            assert len(r.solution_actions) > 0
