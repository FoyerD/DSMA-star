from domains.n_puzzle import NPuzzleProblem, goal_state


def test_successors_are_legal_moves():
    goal = goal_state(3)  # 8-puzzle for a small, fast check
    problem = NPuzzleProblem(goal, size=3)
    successors = list(problem.successors(goal))
    # Blank is at index 0 (top-left of a 3x3); only "down" and "right" are legal.
    actions = {action for action, _state, _cost in successors}
    assert actions == {"down", "right"}
    for _action, next_state, cost in successors:
        assert sorted(next_state) == list(range(9))
        assert cost == 1.0


def test_heuristic_zero_at_goal():
    goal = goal_state(4)
    problem = NPuzzleProblem(goal, size=4)
    assert problem.heuristic(goal) == 0


def test_heuristic_positive_when_scrambled():
    goal = goal_state(3)
    scrambled = (1, 0, 2, 3, 4, 5, 6, 7, 8)
    problem = NPuzzleProblem(scrambled, size=3)
    assert problem.heuristic(scrambled) > 0


def test_invalid_state_rejected():
    import pytest

    with pytest.raises(ValueError):
        NPuzzleProblem((1, 1, 2, 3, 4, 5, 6, 7, 8), size=3)
