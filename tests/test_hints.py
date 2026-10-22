import pytest

from meowdoku.deduce import Technique
from meowdoku.hints import (
    NO_SIMPLE_STEP_MESSAGE,
    NO_SOLUTION_MESSAGE,
    SOLVED_MESSAGE,
    Hint,
    HintKind,
    next_hint,
)
from meowdoku.puzzle import Puzzle
from meowdoku.state import BoardState, Mark

from helpers import column_stripes

EXAMPLE = Puzzle.from_rows(["AABBB", "ACCCB", "ACDDB", "EEDDB", "EEEBB"])
EXAMPLE_SOLUTION = {(0, 4), (1, 2), (2, 0), (3, 3), (4, 1)}


def with_cats(puzzle: Puzzle, cats: set[tuple[int, int]]) -> BoardState:
    state = BoardState.empty(puzzle.size)
    for cat in cats:
        state = state.with_mark(cat, Mark.CAT)
    return state


def test_r7_6_puzzle_without_solution() -> None:
    puzzle = column_stripes(3)
    assert next_hint(puzzle, BoardState.empty(3)) == Hint(HintKind.NO_SOLUTION, NO_SOLUTION_MESSAGE)


def test_solved_board() -> None:
    assert next_hint(EXAMPLE, with_cats(EXAMPLE, EXAMPLE_SOLUTION)) == Hint(
        HintKind.SOLVED, SOLVED_MESSAGE
    )


def test_r7_5_broken_rule_points_at_conflicting_cats() -> None:
    hint = next_hint(EXAMPLE, with_cats(EXAMPLE, {(0, 0), (1, 1)}))
    assert hint.kind is HintKind.RULE_BROKEN
    assert hint.focus == {(0, 0), (1, 1)}
    assert hint.message == (
        "A rule is broken: cats at row 1, column 1 and row 2, column 2 touch; "
        "cats may not share an edge or corner."
    )


def test_r7_5_mistake_points_at_first_wrong_mark() -> None:
    """(1, 2) holds a solution cat, so crossing it out is a mistake."""
    state = BoardState.empty(5).with_crosses([(4, 1), (1, 2), (0, 0)])
    hint = next_hint(EXAMPLE, state)
    assert hint.kind is HintKind.MISTAKE
    assert hint.focus == {(1, 2)}
    assert hint.message == (
        "There's a mistake: the mark at row 2, column 3 doesn't fit the solution."
    )


def test_r7_5_wrong_cat_is_a_mistake() -> None:
    hint = next_hint(EXAMPLE, with_cats(EXAMPLE, {(0, 0)}))
    assert hint.kind is HintKind.MISTAKE
    assert hint.focus == {(0, 0)}


def test_r7_5_mistake_on_puzzle_with_several_solutions() -> None:
    """Only 1-3-0-2 and 2-0-3-1 solve this board; a cat at (0, 0) fits neither."""
    puzzle = column_stripes(4)
    hint = next_hint(puzzle, with_cats(puzzle, {(0, 0)}))
    assert hint == Hint(HintKind.MISTAKE, "There's a mistake: your marks don't fit any solution.")


def test_r7_2_deduction_hint_on_empty_board() -> None:
    hint = next_hint(EXAMPLE, BoardState.empty(5))
    assert hint.kind is HintKind.DEDUCTION
    assert hint.deduction is not None
    assert hint.deduction.technique is Technique.CONFINEMENT
    assert hint.message == hint.deduction.reason
    assert hint.focus == hint.deduction.basis


def test_r7_6_no_simple_step() -> None:
    puzzle = column_stripes(6)
    assert next_hint(puzzle, BoardState.empty(6)) == Hint(
        HintKind.NO_SIMPLE_STEP, NO_SIMPLE_STEP_MESSAGE
    )


def test_r7_4_same_state_gives_same_hint() -> None:
    state = BoardState.empty(5).with_crosses([(2, 1)])
    assert next_hint(EXAMPLE, state) == next_hint(EXAMPLE, state)


def test_size_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError):
        next_hint(EXAMPLE, BoardState.empty(4))
