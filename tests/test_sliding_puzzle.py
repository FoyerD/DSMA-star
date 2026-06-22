from domains.sliding_puzzle import GOAL_STATE, SlidingPuzzleProblem


def test_successors_move_blank_correctly():
    problem = SlidingPuzzleProblem(GOAL_STATE)
    successors = list(problem.successors(GOAL_STATE))
    next_states = {s for _action, s, _cost in successors}
    # Blank starts at index 0 (top-left); only "down" and "right" moves are legal.
    assert len(successors) == 2
    assert (1, 0, 2, 3, 4, 5, 6, 7, 8) in next_states  # swap with index 1 (right)
    assert (3, 1, 2, 0, 4, 5, 6, 7, 8) in next_states  # swap with index 3 (down)


def test_is_goal():
    problem = SlidingPuzzleProblem(GOAL_STATE)
    assert problem.is_goal(GOAL_STATE)
    assert not problem.is_goal((1, 0, 2, 3, 4, 5, 6, 7, 8))


def test_heuristic_zero_at_goal():
    problem = SlidingPuzzleProblem(GOAL_STATE)
    assert problem.heuristic(GOAL_STATE) == 0


def test_invalid_state_rejected():
    import pytest

    with pytest.raises(ValueError):
        SlidingPuzzleProblem((1, 1, 2, 3, 4, 5, 6, 7, 8))
