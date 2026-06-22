from algorithms import AStar, CustomAlgorithm, ILBFS, SMAStar
from algorithms.base import SearchLimits
from benchmark.instance_generators import generate_grid_instances, generate_puzzle_instances
from benchmark.runner import run_benchmark
from domains.grid import GridProblem
from domains.sliding_puzzle import SlidingPuzzleProblem

LIMITS = SearchLimits(timeout_seconds=10.0, max_memory_mb=512.0, max_nodes=50_000, sma_star_memory_limit_nodes=1000)


def _tiny_grid():
    return GridProblem(width=3, height=3, start=(0, 0), goal=(2, 2), obstacles=frozenset())


def _easy_puzzle():
    # One move away from the goal: blank and tile 1 swapped.
    return SlidingPuzzleProblem((1, 0, 2, 3, 4, 5, 6, 7, 8))


def test_astar_solves_tiny_grid():
    result = AStar().search(_tiny_grid(), LIMITS)
    assert result.success
    assert result.solution_cost == 4
    assert len(result.solution_actions) == 4


def test_astar_solves_easy_puzzle():
    result = AStar().search(_easy_puzzle(), LIMITS)
    assert result.success
    assert result.solution_cost == 1
    assert result.solution_actions == ["left"]


def test_sma_star_solves_tiny_grid():
    result = SMAStar().search(_tiny_grid(), LIMITS)
    assert result.success
    assert result.solution_cost == 4


def test_ilbfs_solves_tiny_grid():
    result = ILBFS().search(_tiny_grid(), LIMITS)
    assert result.success
    assert result.solution_cost == 4


def test_custom_algorithm_matches_astar_interface():
    result = CustomAlgorithm().search(_tiny_grid(), LIMITS)
    assert result.success
    assert result.algorithm_name == "custom_algorithm"
    assert result.solution_cost == 4


def test_benchmark_runner_returns_results_without_crashing():
    instances = generate_grid_instances(count=2, width=4, height=4, obstacle_prob=0.0, seed=1)
    instances += generate_puzzle_instances(count=2, scramble_depths=[5], seed=1)
    algorithms = [AStar(), SMAStar(), ILBFS(), CustomAlgorithm()]
    results = run_benchmark(instances, algorithms, LIMITS)
    assert len(results) == len(instances) * len(algorithms)
    for result in results:
        assert result.algorithm_name in {"astar", "sma_star", "ilbfs", "custom_algorithm"}
