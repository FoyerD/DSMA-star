from domains.sokoban import SokobanProblem


def _tiny_problem():
    # "#####" / "#.$@#" / "#####" -- one push solves it (box pushed left onto goal).
    walls = frozenset(
        {(x, 0) for x in range(5)} | {(x, 2) for x in range(5)} | {(0, 1), (4, 1)}
    )
    return SokobanProblem(
        width=5,
        height=3,
        walls=walls,
        goals=frozenset({(1, 1)}),
        player_start=(3, 1),
        boxes_start=frozenset({(2, 1)}),
    )


def test_successor_generation_includes_moves_and_pushes():
    problem = _tiny_problem()
    successors = list(problem.successors(problem.initial_state))
    actions = {action for action, _state, _cost in successors}
    assert "push_left" in actions
    for action, (player, boxes), cost in successors:
        assert cost == 1.0
        assert player not in problem.walls
        assert all(b not in problem.walls for b in boxes)


def test_is_goal_after_pushing_box_onto_goal():
    problem = _tiny_problem()
    push_left = next(s for s in problem.successors(problem.initial_state) if s[0] == "push_left")
    _action, next_state, _cost = push_left
    assert problem.is_goal(next_state)


def test_astar_solves_tiny_sokoban():
    from algorithms.astar import AStar
    from algorithms.base import SearchLimits

    result = AStar().search(_tiny_problem(), SearchLimits(max_nodes=10_000))
    assert result.success
    assert result.solution_cost == 1
    assert result.solution_actions == ["push_left"]
