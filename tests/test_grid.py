from domains.grid import GridProblem


def test_successors_respect_bounds_and_obstacles():
    problem = GridProblem(width=3, height=3, start=(0, 0), goal=(2, 2), obstacles=frozenset({(1, 0)}))
    successors = list(problem.successors((0, 0)))
    next_states = {s for _action, s, _cost in successors}
    assert (1, 0) not in next_states  # blocked by obstacle
    assert (0, 1) in next_states
    assert (-1, 0) not in next_states  # out of bounds


def test_heuristic_is_manhattan_distance():
    problem = GridProblem(width=5, height=5, start=(0, 0), goal=(4, 4), obstacles=frozenset())
    assert problem.heuristic((0, 0)) == 8
    assert problem.heuristic((4, 4)) == 0


def test_is_goal():
    problem = GridProblem(width=3, height=3, start=(0, 0), goal=(2, 2), obstacles=frozenset())
    assert problem.is_goal((2, 2))
    assert not problem.is_goal((0, 0))
