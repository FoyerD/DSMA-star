from pathlib import Path

from algorithms import AStar, DynamicSMACollapse, ILBFS, SMAStar, TwoLevelDynamicSMA
from algorithms.base import SearchLimits
from benchmark.instance_generators import generate_puzzle_instances, generate_sokoban_instances
from benchmark.results import save_results_csv, save_results_json
from benchmark.runner import run_benchmark
from domains.n_puzzle import NPuzzleProblem, goal_state

LIMITS = SearchLimits(
    max_memory_mb=512.0,
    max_nodes=50_000,
    sma_memory_limit_nodes=1_000,
    dynamic_initial_ram_nodes=500,
    dynamic_min_ram_nodes=100,
    dynamic_max_ram_nodes=2_000,
    two_level_initial_ram_nodes=500,
    two_level_min_ram_nodes=100,
    two_level_max_ram_nodes=2_000,
    two_level_total_node_limit=5_000,
    epoch_generated_nodes=200,
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


def test_sma_star_solves_easy_puzzle():
    result = SMAStar().search(_easy_puzzle(), LIMITS)
    assert result.success
    assert result.solution_cost == 1


def test_ilbfs_solves_easy_puzzle():
    result = ILBFS().search(_easy_puzzle(), LIMITS)
    assert result.success
    assert result.solution_cost == 1


def test_dynamic_sma_collapse_runs_without_crashing():
    instances = generate_puzzle_instances(count=2, size=3, scramble_depths=[10, 15], seed=3)
    for instance in instances:
        result = DynamicSMACollapse().search(instance.problem, LIMITS)
        assert result.algorithm_name == "dynamic_sma_collapse"
        # Either it solved within budget or it honestly reported a real resource limit.
        assert result.success or result.memory_limit_reached or result.node_limit_reached


def test_two_level_dynamic_sma_runs_and_cleans_up_sqlite(tmp_path: Path):
    instance = generate_puzzle_instances(count=1, size=3, scramble_depths=[15], seed=4)[0]
    disk_dir = tmp_path / "disk_cache"
    algorithm = TwoLevelDynamicSMA(keep_disk=False, disk_dir=disk_dir)
    result = algorithm.search(instance.problem, LIMITS)
    assert result.algorithm_name == "two_level_dynamic_sma"
    assert result.success or result.memory_limit_reached or result.node_limit_reached
    # The temp SQLite file should have been deleted (keep_disk=False).
    leftover = list(disk_dir.glob("*.sqlite3")) if disk_dir.exists() else []
    assert leftover == []


def test_two_level_dynamic_sma_keeps_disk_file_when_requested(tmp_path: Path):
    instance = generate_puzzle_instances(count=1, size=3, scramble_depths=[15], seed=5)[0]
    disk_dir = tmp_path / "disk_cache_kept"
    algorithm = TwoLevelDynamicSMA(keep_disk=True, disk_dir=disk_dir)
    algorithm.search(instance.problem, LIMITS)
    assert disk_dir.exists()
    assert list(disk_dir.glob("*.sqlite3"))


def test_benchmark_runner_produces_results_for_all_algorithms():
    instances = generate_puzzle_instances(count=2, size=3, scramble_depths=[10], seed=1)
    instances += generate_sokoban_instances(levels=["easy"])
    algorithms = [AStar(), SMAStar(), ILBFS(), DynamicSMACollapse(), TwoLevelDynamicSMA(keep_disk=False)]
    results = run_benchmark(instances, algorithms, LIMITS)
    assert len(results) == len(instances) * len(algorithms)
    expected_names = {"astar", "sma_star", "ilbfs", "dynamic_sma_collapse", "two_level_dynamic_sma"}
    for result in results:
        assert result.algorithm_name in expected_names


def test_results_are_saved_as_csv_and_json(tmp_path: Path):
    instances = generate_puzzle_instances(count=1, size=3, scramble_depths=[5], seed=2)
    results = run_benchmark(instances, [AStar()], LIMITS)
    csv_path = tmp_path / "out" / "benchmark_results.csv"
    json_path = tmp_path / "out" / "benchmark_results.json"
    save_results_csv(results, csv_path)
    save_results_json(results, json_path)
    assert csv_path.exists() and csv_path.stat().st_size > 0
    assert json_path.exists() and json_path.stat().st_size > 0
