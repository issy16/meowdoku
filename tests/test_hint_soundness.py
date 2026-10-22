"""Hints checked against the solver and validator, never against themselves (R7.7).

A deduction is sound if its conclusion holds in every solution that matches
the board: a placed cat is in every such solution, and no crossed-out cell
holds a cat in any of them.
"""

import random

import pytest

from meowdoku.deduce import Deduction
from meowdoku.hints import HintKind, next_hint
from meowdoku.puzzle import Cell, Puzzle
from meowdoku.rules import is_valid_solution
from meowdoku.solver import SolveStatus, iter_solutions, solve
from meowdoku.state import BoardState, Mark

from helpers import apply_deduction, random_puzzle

SEED = 20261023
EXAMPLE = Puzzle.from_rows(["AABBB", "ACCCB", "ACDDB", "EEDDB", "EEEBB"])
MAX_HINTS = 200


def puzzles_with_status(status: SolveStatus, count: int, sizes: range, seed: int) -> list[Puzzle]:
    rng = random.Random(seed)
    found: list[Puzzle] = []
    while len(found) < count:
        puzzle = random_puzzle(rng, rng.choice(sizes))
        if solve(puzzle).status is status:
            found.append(puzzle)
    return found


UNIQUE_PUZZLES = [EXAMPLE] + puzzles_with_status(SolveStatus.UNIQUE, 30, range(5, 9), SEED)
MULTIPLE_PUZZLES = puzzles_with_status(SolveStatus.MULTIPLE, 15, range(5, 7), SEED + 1)


def assert_sound(deduction: Deduction, solutions: list[frozenset[Cell]]) -> None:
    for cats in solutions:
        if deduction.place_cat is not None:
            assert deduction.place_cat in cats, deduction.reason
        assert not (deduction.cross_out & cats), deduction.reason


def matching_solutions(puzzle: Puzzle, state: BoardState) -> list[frozenset[Cell]]:
    return [
        solution.cats
        for solution in iter_solutions(puzzle)
        if state.cats <= solution.cats and not (state.crosses & solution.cats)
    ]


def follow_hints(puzzle: Puzzle, state: BoardState) -> tuple[BoardState, HintKind]:
    """Apply hints until they stop, checking each one is sound and makes progress."""
    for _ in range(MAX_HINTS):
        hint = next_hint(puzzle, state)
        if hint.kind is not HintKind.DEDUCTION:
            return state, hint.kind
        assert hint.deduction is not None
        assert_sound(hint.deduction, matching_solutions(puzzle, state))
        new_state = apply_deduction(state, hint.deduction)
        assert new_state != state, "a hint must add at least one mark"
        state = new_state
    pytest.fail("hints did not finish")


@pytest.mark.parametrize("index", range(len(UNIQUE_PUZZLES)))
def test_hints_from_empty_board_are_sound_and_finish(index: int) -> None:
    puzzle = UNIQUE_PUZZLES[index]
    state, final_kind = follow_hints(puzzle, BoardState.empty(puzzle.size))
    assert final_kind in {HintKind.SOLVED, HintKind.NO_SIMPLE_STEP}
    if final_kind is HintKind.SOLVED:
        assert is_valid_solution(puzzle, state.cats)


@pytest.mark.parametrize("index", range(len(MULTIPLE_PUZZLES)))
def test_hints_are_sound_on_puzzles_with_several_solutions(index: int) -> None:
    puzzle = MULTIPLE_PUZZLES[index]
    _, final_kind = follow_hints(puzzle, BoardState.empty(puzzle.size))
    assert final_kind in {HintKind.SOLVED, HintKind.NO_SIMPLE_STEP}


def test_hints_alone_solve_the_readme_example() -> None:
    state, final_kind = follow_hints(EXAMPLE, BoardState.empty(5))
    assert final_kind is HintKind.SOLVED
    assert state.cats == {(0, 4), (1, 2), (2, 0), (3, 3), (4, 1)}


def test_hints_fully_solve_most_unique_puzzles() -> None:
    """Records how far D1-D5 get. If this drops, a rule change made hints weaker."""
    solved = sum(
        follow_hints(puzzle, BoardState.empty(puzzle.size))[1] is HintKind.SOLVED
        for puzzle in UNIQUE_PUZZLES
    )
    assert solved >= len(UNIQUE_PUZZLES) * 0.8


def random_partial_state(rng: random.Random, puzzle: Puzzle, solution: frozenset[Cell]) -> BoardState:
    """A board in progress where every mark agrees with the solution."""
    state = BoardState.empty(puzzle.size)
    for cat in solution:
        if rng.random() < 0.3:
            state = state.with_mark(cat, Mark.CAT)
    others = [cell for cell in puzzle.cells() if cell not in solution]
    return state.with_crosses(rng.sample(others, rng.randrange(len(others))))


@pytest.mark.parametrize("index", range(len(UNIQUE_PUZZLES)))
def test_hints_are_sound_from_boards_in_progress(index: int) -> None:
    puzzle = UNIQUE_PUZZLES[index]
    solution = solve(puzzle).solutions[0].cats
    rng = random.Random(index)
    for _ in range(5):
        follow_hints(puzzle, random_partial_state(rng, puzzle, solution))


@pytest.mark.parametrize("index", range(len(UNIQUE_PUZZLES)))
def test_one_wrong_mark_is_reported_not_built_on(index: int) -> None:
    puzzle = UNIQUE_PUZZLES[index]
    solution = solve(puzzle).solutions[0].cats
    rng = random.Random(index)
    state = random_partial_state(rng, puzzle, solution)
    wrong_cell = rng.choice(sorted(solution))
    state = state.with_mark(wrong_cell, Mark.CROSS)
    hint = next_hint(puzzle, state)
    assert hint.kind is HintKind.MISTAKE
    assert hint.focus == {wrong_cell}
