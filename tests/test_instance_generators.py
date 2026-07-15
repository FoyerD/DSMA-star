import csv
from pathlib import Path

import pytest

from algorithms import AStar
from algorithms.base import SearchLimits
from benchmark.instance_generators import (
    KorfPuzzleInstance,
    generate_korf_puzzle_instances,
    generate_npuzzle_instances,
    get_instance_by_optimal_depth,
    load_korf_instances,
)
from benchmark.runner import run_benchmark
from domains.n_puzzle import goal_state

GOAL_16 = tuple(range(16))
# Reached from the goal by two non-reversing moves (right, then down); its
# Manhattan-distance heuristic is exactly 2, so its true optimal depth is 2.
DEPTH_2_STATE = (1, 5, 2, 3, 4, 0, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15)


def _write_csv(path: Path, header, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)


def _state_str(state, fmt: str) -> str:
    if fmt == "space":
        return " ".join(str(x) for x in state)
    if fmt == "comma":
        return ",".join(str(x) for x in state)
    if fmt == "brackets":
        return "[" + ", ".join(str(x) for x in state) + "]"
    raise ValueError(fmt)


def test_load_korf_instances_parses_standard_csv(tmp_path: Path):
    csv_path = tmp_path / "korfs100.csv"
    _write_csv(
        csv_path,
        ["id", "state", "optimal_depth"],
        [
            [1, _state_str(GOAL_16, "space"), 0],
            [2, _state_str(DEPTH_2_STATE, "space"), 2],
        ],
    )
    instances = load_korf_instances(csv_path)
    assert len(instances) == 2
    assert instances[0] == KorfPuzzleInstance(instance_id=1, state=GOAL_16, optimal_depth=0, total_nodes=None)
    assert instances[1].state == DEPTH_2_STATE
    assert instances[1].optimal_depth == 2


def test_load_korf_instances_tolerates_column_aliases(tmp_path: Path):
    csv_path = tmp_path / "korf_aliases.csv"
    _write_csv(
        csv_path,
        ["index", "state", "solution_depth"],
        [[7, _state_str(GOAL_16, "space"), 0]],
    )
    instances = load_korf_instances(csv_path)
    assert len(instances) == 1
    assert instances[0].instance_id == 7
    assert instances[0].optimal_depth == 0


def test_load_korf_instances_tolerates_optimal_solution_length_alias(tmp_path: Path):
    csv_path = tmp_path / "korf_alias2.csv"
    _write_csv(
        csv_path,
        ["instance_id", "state", "optimal_solution_length"],
        [["a1", _state_str(GOAL_16, "space"), 0]],
    )
    instances = load_korf_instances(csv_path)
    assert instances[0].instance_id == "a1"  # non-numeric id stays a string
    assert instances[0].optimal_depth == 0


@pytest.mark.parametrize("fmt", ["space", "comma", "brackets"])
def test_load_korf_instances_parses_all_state_formats(tmp_path: Path, fmt: str):
    csv_path = tmp_path / f"korf_{fmt}.csv"
    _write_csv(csv_path, ["id", "state", "optimal_depth"], [[1, _state_str(DEPTH_2_STATE, fmt), 2]])
    instances = load_korf_instances(csv_path)
    assert instances[0].state == DEPTH_2_STATE


def test_bundled_korfs100_csv_loads_skipping_known_bad_rows(capsys):
    # The real korfs100.csv shipped in the repo -- confirms load_korf_instances
    # handles the actual bundled file. Some rows may have been fixed over time;
    # verify all valid rows load and any malformed ones are skipped gracefully.
    repo_root = Path(__file__).resolve().parent.parent
    instances = load_korf_instances(repo_root / "korfs100.csv")
    assert len(instances) >= 97  # at least 97 valid rows; 100 if all fixed
    ids = {i.instance_id for i in instances}
    # Verify we loaded a reasonable set
    assert 1 in ids
    assert 100 in ids


def test_load_korf_instances_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_korf_instances(tmp_path / "does_not_exist.csv")


def test_load_korf_instances_missing_required_column_raises(tmp_path: Path):
    csv_path = tmp_path / "korf_bad_header.csv"
    _write_csv(csv_path, ["id", "state"], [[1, _state_str(GOAL_16, "space")]])
    with pytest.raises(ValueError, match="missing required column"):
        load_korf_instances(csv_path)


def test_load_korf_instances_wrong_tile_count_is_skipped_with_warning(tmp_path: Path, capsys):
    # The bundled korfs100.csv itself has a few rows with a tile missing --
    # those must be skipped (with a clear warning), not fail the whole load.
    csv_path = tmp_path / "korf_short_state.csv"
    _write_csv(
        csv_path,
        ["id", "state", "optimal_depth"],
        [[1, "0 1 2 3", 0], [2, _state_str(GOAL_16, "space"), 5]],
    )
    instances = load_korf_instances(csv_path)
    assert len(instances) == 1
    assert instances[0].instance_id == 2
    captured = capsys.readouterr()
    assert "Skipping Korf instance 1" in captured.out
    assert "expected 16" in captured.out


def test_load_korf_instances_non_permutation_is_skipped_with_warning(tmp_path: Path, capsys):
    csv_path = tmp_path / "korf_dup_tile.csv"
    bad_state = (1,) * 16
    _write_csv(
        csv_path,
        ["id", "state", "optimal_depth"],
        [[1, _state_str(bad_state, "space"), 0], [2, _state_str(GOAL_16, "space"), 5]],
    )
    instances = load_korf_instances(csv_path)
    assert len(instances) == 1
    assert instances[0].instance_id == 2
    captured = capsys.readouterr()
    assert "Skipping Korf instance 1" in captured.out


def _multi_depth_csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "korf_multi.csv"
    rows = [
        [1, _state_str(GOAL_16, "space"), 0],
        [2, _state_str(DEPTH_2_STATE, "space"), 2],
        [3, _state_str(DEPTH_2_STATE, "space"), 10],
        [4, _state_str(DEPTH_2_STATE, "space"), 10],
        [5, _state_str(DEPTH_2_STATE, "space"), 14],
    ]
    _write_csv(csv_path, ["id", "state", "optimal_depth"], rows)
    return csv_path


def test_get_instance_by_optimal_depth_exact_match_no_seed_picks_lowest_id(tmp_path: Path):
    csv_path = _multi_depth_csv(tmp_path)
    instance = get_instance_by_optimal_depth(10, seed=None, csv_path=csv_path)
    assert instance.instance_id == 3
    assert instance.optimal_depth == 10


def test_get_instance_by_optimal_depth_is_deterministic_with_seed(tmp_path: Path):
    csv_path = _multi_depth_csv(tmp_path)
    first = get_instance_by_optimal_depth(10, seed=5, csv_path=csv_path)
    second = get_instance_by_optimal_depth(10, seed=5, csv_path=csv_path)
    assert first == second


def test_get_instance_by_optimal_depth_seed_modulo_selection(tmp_path: Path):
    csv_path = _multi_depth_csv(tmp_path)
    # Two matches at depth 10 (ids 3 and 4), sorted by id -> [3, 4].
    assert get_instance_by_optimal_depth(10, seed=0, csv_path=csv_path).instance_id == 3
    assert get_instance_by_optimal_depth(10, seed=1, csv_path=csv_path).instance_id == 4
    assert get_instance_by_optimal_depth(10, seed=2, csv_path=csv_path).instance_id == 3


def test_get_instance_by_optimal_depth_falls_back_to_closest(tmp_path: Path, capsys):
    csv_path = _multi_depth_csv(tmp_path)  # depths available: 0, 2, 10, 10, 14
    instance = get_instance_by_optimal_depth(11, seed=None, csv_path=csv_path)
    assert instance.optimal_depth == 10  # closer than 14
    captured = capsys.readouterr()
    assert "No Korf instance with optimal_depth=11" in captured.out
    assert "using closest depth 10 instead" in captured.out


def test_get_instance_by_optimal_depth_closest_tie_prefers_smaller(tmp_path: Path):
    csv_path = tmp_path / "korf_tie.csv"
    rows = [[1, _state_str(GOAL_16, "space"), 8], [2, _state_str(DEPTH_2_STATE, "space"), 12]]
    _write_csv(csv_path, ["id", "state", "optimal_depth"], rows)
    # target=10 is equidistant from 8 and 12 -> must prefer the smaller depth (8).
    instance = get_instance_by_optimal_depth(10, seed=None, csv_path=csv_path)
    assert instance.optimal_depth == 8


def test_generate_korf_puzzle_instances_builds_named_instances(tmp_path: Path):
    csv_path = _multi_depth_csv(tmp_path)
    instances = generate_korf_puzzle_instances(optimal_depths=[2, 10], seed=0, csv_path=csv_path)
    assert len(instances) == 2
    depth_2 = next(i for i in instances if i.optimal_depth == 2)
    assert depth_2.source == "korf100"
    assert depth_2.difficulty == "korf_depth_2"
    assert depth_2.problem.initial_state == DEPTH_2_STATE
    assert depth_2.problem.size == 4


def test_generate_npuzzle_instances_dispatches_to_korf(tmp_path: Path):
    csv_path = _multi_depth_csv(tmp_path)
    instances = generate_npuzzle_instances(source="korf", seeds=[0], optimal_depths=[2], korf_csv=csv_path)
    assert len(instances) == 1
    assert instances[0].source == "korf100"
    assert instances[0].optimal_depth == 2


def test_generate_npuzzle_instances_dispatches_to_scramble():
    instances = generate_npuzzle_instances(source="scramble", seeds=[1], size=3, scramble_depths=[5])
    assert len(instances) == 1
    assert instances[0].source == "scramble"
    assert instances[0].optimal_depth is None


def test_generate_npuzzle_instances_rejects_unknown_source():
    with pytest.raises(ValueError):
        generate_npuzzle_instances(source="bogus")


def test_benchmark_runner_solves_korf_instance_at_known_optimal_depth(tmp_path: Path):
    csv_path = tmp_path / "korf_depth2.csv"
    _write_csv(csv_path, ["id", "state", "optimal_depth"], [[1, _state_str(DEPTH_2_STATE, "space"), 2]])
    instances = generate_npuzzle_instances(source="korf", seeds=[0], optimal_depths=[2], korf_csv=csv_path)

    results = run_benchmark(instances, [AStar()], SearchLimits())
    assert len(results) == 1
    result = results[0]
    assert result.success
    assert result.instance_source == "korf100"
    assert result.known_optimal_depth == 2
    # A* is optimal with an admissible heuristic, so it must match the known
    # true optimal depth from the CSV -- the whole point of using Korf instances.
    assert result.solution_cost == 2
