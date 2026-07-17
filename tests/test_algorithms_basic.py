import statistics
from pathlib import Path

from algorithms import AStar, DynamicSMACollapse, ILBFS, MemoryLimit, SMAStar, TwoLevelDynamicSMA, normalize_memory_limits
from algorithms.base import SearchLimits
from benchmark.instance_generators import generate_puzzle_instances, generate_sokoban_instances
from benchmark.metrics import aggregate_by_domain_and_algorithm
from benchmark.results import save_results_csv, save_results_json
from benchmark.runner import run_benchmark
from domains.n_puzzle import NPuzzleProblem, goal_state

LIMITS = SearchLimits(
    max_memory_mb=512.0,
    max_nodes=50_000,
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
    result = SMAStar(memory_limit=1_000).search(_easy_puzzle(), LIMITS)
    assert result.success
    assert result.solution_cost == 1


def test_sma_star_default_memory_limit_is_50000():
    algorithm = SMAStar()
    assert algorithm.memory_limit == MemoryLimit(50_000)
    assert algorithm.name == "SMA* (memory=50000)"


def test_sma_star_name_includes_memory_limit():
    assert SMAStar(memory_limit=10_000).name == "SMA* (memory=10000)"
    assert SMAStar(memory_limit=25_000).name == "SMA* (memory=25000)"


def test_normalize_memory_limits_accepts_int_or_list():
    assert normalize_memory_limits(50_000) == [MemoryLimit(50_000)]
    assert normalize_memory_limits([10_000, 25_000, 50_000]) == [MemoryLimit(10_000), MemoryLimit(25_000), MemoryLimit(50_000)]
    assert normalize_memory_limits((10_000, 25_000)) == [MemoryLimit(10_000), MemoryLimit(25_000)]
    # Also accepts MemoryLimit objects directly
    assert normalize_memory_limits(MemoryLimit(10_000)) == [MemoryLimit(10_000)]
    assert normalize_memory_limits([MemoryLimit(10_000), 25_000]) == [MemoryLimit(10_000), MemoryLimit(25_000)]


def test_multiple_sma_star_instances_run_independently_with_distinct_names():
    instances = generate_puzzle_instances(seeds=[6], size=3, scramble_depths=[10])
    memory_limits = [500, 1_000, 2_000]
    algorithms = [SMAStar(memory_limit=m) for m in memory_limits]
    results = run_benchmark(instances, algorithms, LIMITS)

    names = [r.algorithm_name for r in results]
    assert names == ["SMA* (memory=500)", "SMA* (memory=1000)", "SMA* (memory=2000)"]
    # Each instance kept its own configured limit rather than sharing/mutating one.
    for algorithm, memory_limit in zip(algorithms, memory_limits):
        assert algorithm.memory_limit == MemoryLimit(memory_limit)


def test_ilbfs_solves_easy_puzzle():
    result = ILBFS().search(_easy_puzzle(), LIMITS)
    assert result.success
    assert result.solution_cost == 1


def test_dynamic_sma_collapse_runs_without_crashing():
    instances = generate_puzzle_instances(seeds=[3], size=3, scramble_depths=[10, 15])
    for instance in instances:
        result = DynamicSMACollapse().search(instance.problem, LIMITS)
        assert result.algorithm_name == "dynamic_sma_collapse"
        # Either it solved within budget or it honestly reported a real resource limit.
        assert result.success or result.memory_limit_reached or result.node_limit_reached


def test_dynamic_sma_collapse_nodes_restored_defaults_to_zero_without_pressure():
    # Plenty of RAM relative to the search space -> nothing should ever need
    # collapsing, so nothing can be restored either.
    result = DynamicSMACollapse().search(_easy_puzzle(), LIMITS)
    assert result.nodes_collapsed == 0
    assert result.nodes_restored == 0


def test_dynamic_sma_collapse_expand_counts_restored_only_on_reexpansion():
    # Unit-level check of the exact "restore" counting rule documented in
    # dynamic_sma_collapse.py: a leaf's re-expansion only counts as a restore
    # once its entire subtree has been collapsed away (forgotten_f != inf).
    import itertools

    from algorithms._run_utils import RunTracker
    from algorithms.dynamic_sma_collapse import DynamicSMACollapse, _Node
    from domains.n_puzzle import NPuzzleProblem, goal_state

    goal = goal_state(3)
    problem = NPuzzleProblem(goal, size=3)  # blank at index 0 -> 2 successors: "down", "right"
    algo = DynamicSMACollapse()
    tracker = RunTracker.start(max_nodes=1_000, max_memory_mb=4_096.0)
    counter = itertools.count()

    root = _Node(key=goal, state=goal, g=0.0, base_f=0.0, parent_key=None, action=None, depth=0, order=next(counter))
    nodes = {goal: root}

    # First expansion: forgotten_f is still inf -> not a restore.
    goal_first, restored_first = algo._expand(problem, nodes, root, tracker, counter)
    assert goal_first is None
    assert restored_first == 0
    assert len(root.children) == 2

    # Simulate every child having been collapsed away (as _prune_worst_leaf
    # would do): remove them and set root.forgotten_f, making root a leaf again.
    for child_key in list(root.children):
        del nodes[child_key]
    root.children.clear()
    root.forgotten_f = 5.0

    # Re-expanding root now regenerates its subtree -> this is a restore.
    goal_second, restored_second = algo._expand(problem, nodes, root, tracker, counter)
    assert goal_second is None
    assert restored_second == 2
    assert restored_second == len(root.children)


def test_dynamic_sma_collapse_restores_under_tight_memory_pressure():
    # A RAM bound tight enough to force heavy collapsing should, over enough
    # instances, eventually force at least one restore (a fully-collapsed
    # node being re-expanded because it became the best leaf again).
    tight_limits = SearchLimits(
        max_memory_mb=512.0,
        max_nodes=50_000,
        dynamic_initial_ram_nodes=3,
        dynamic_min_ram_nodes=2,
        dynamic_max_ram_nodes=4,
        epoch_generated_nodes=20,
    )
    instances = generate_puzzle_instances(seeds=list(range(10)), size=3, scramble_depths=[12])
    results = [DynamicSMACollapse().search(i.problem, tight_limits) for i in instances]
    assert any(r.nodes_collapsed > 0 for r in results)
    assert any(r.nodes_restored > 0 for r in results)


def test_two_level_dynamic_sma_runs_and_cleans_up_sqlite(tmp_path: Path):
    instance = generate_puzzle_instances(seeds=[4], size=3, scramble_depths=[15])[0]
    disk_dir = tmp_path / "disk_cache"
    algorithm = TwoLevelDynamicSMA(keep_disk=False, disk_dir=disk_dir)
    result = algorithm.search(instance.problem, LIMITS)
    assert result.algorithm_name == "two_level_dynamic_sma"
    assert result.success or result.memory_limit_reached or result.node_limit_reached
    # The temp SQLite file should have been deleted (keep_disk=False).
    leftover = list(disk_dir.glob("*.sqlite3")) if disk_dir.exists() else []
    assert leftover == []


def test_two_level_dynamic_sma_keeps_disk_file_when_requested(tmp_path: Path):
    instance = generate_puzzle_instances(seeds=[5], size=3, scramble_depths=[15])[0]
    disk_dir = tmp_path / "disk_cache_kept"
    algorithm = TwoLevelDynamicSMA(keep_disk=True, disk_dir=disk_dir)
    algorithm.search(instance.problem, LIMITS)
    assert disk_dir.exists()
    assert list(disk_dir.glob("*.sqlite3"))


def test_benchmark_runner_produces_results_for_all_algorithms():
    instances = generate_puzzle_instances(seeds=[1, 2], size=3, scramble_depths=[10])
    instances += generate_sokoban_instances(levels=["easy"])
    algorithms = [
        AStar(),
        SMAStar(memory_limit=1_000),
        SMAStar(memory_limit=2_000),
        ILBFS(),
        DynamicSMACollapse(),
        TwoLevelDynamicSMA(keep_disk=False),
    ]
    results = run_benchmark(instances, algorithms, LIMITS)
    assert len(results) == len(instances) * len(algorithms)
    expected_names = {
        "astar",
        "SMA* (memory=1000)",
        "SMA* (memory=2000)",
        "ilbfs",
        "dynamic_sma_collapse",
        "two_level_dynamic_sma",
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


def test_aggregate_std_is_zero_with_a_single_seed():
    instances = generate_puzzle_instances(seeds=[7], size=3, scramble_depths=[5])
    results = run_benchmark(instances, [AStar()], LIMITS)
    summary = aggregate_by_domain_and_algorithm(results)[0]
    assert summary.std_nodes_expanded == 0.0
    assert summary.std_peak_memory_mb == 0.0
