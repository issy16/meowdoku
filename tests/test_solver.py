"""Solver tests on hand-verified puzzles. Cross-checks are in test_oracles.py."""

from pathlib import Path

import pytest

import meowdoku.solver
from meowdoku.parser import parse_puzzle
from meowdoku.puzzle import Puzzle
from meowdoku.solver import Solution, SolveResult, SolveStatus, iter_solutions, solve

from helpers import column_stripes, imported_modules

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Puzzle:
    return parse_puzzle((FIXTURES / name).read_text(encoding="utf-8"))


# Solution


def test_solution_cats_pairs_rows_with_columns() -> None:
    assert Solution((1, 3, 0, 2)).cats == {(0, 1), (1, 3), (2, 0), (3, 2)}


# R2.1 Statuses on hand-verified puzzles


def test_r2_1_readme_example_is_unique() -> None:
    result = solve(load_fixture("example_5x5.txt"))
    assert result == SolveResult(SolveStatus.UNIQUE, (Solution((4, 2, 0, 3, 1)),))


def test_r2_1_single_cell_board_is_unique() -> None:
    assert solve(Puzzle.from_rows(["A"])).status is SolveStatus.UNIQUE


@pytest.mark.parametrize("size", [2, 3])
def test_r2_1_boards_of_size_2_and_3_have_no_solution(size: int) -> None:
    """Every placement of 2 or 3 cats in distinct rows and columns has a touching pair."""
    assert solve(column_stripes(size)) == SolveResult(SolveStatus.NONE, ())


def test_r2_1_two_single_cell_regions_in_one_row_have_no_solution() -> None:
    """Regions A and B are single cells in row 1, so both cats would share that row."""
    puzzle = Puzzle.from_rows(["ABCC", "DDCC", "DDCC", "DDCC"])
    assert solve(puzzle).status is SolveStatus.NONE


def test_r2_1_column_stripes_4x4_has_exactly_two_solutions() -> None:
    """Only 1-3-0-2 and its mirror 2-0-3-1 avoid touching on a 4x4 board."""
    result = solve(column_stripes(4))
    assert result == SolveResult(
        SolveStatus.MULTIPLE, (Solution((1, 3, 0, 2)), Solution((2, 0, 3, 1)))
    )


# R2.3 Stopping early and finding everything


def test_r2_3_stops_after_two_solutions_by_default() -> None:
    result = solve(column_stripes(6))
    assert result.status is SolveStatus.MULTIPLE
    assert len(result.solutions) == 2


def test_r2_3_custom_limit() -> None:
    assert len(solve(column_stripes(6), max_solutions=5).solutions) == 5


def test_r2_3_none_finds_every_solution() -> None:
    assert len(solve(column_stripes(6), max_solutions=None).solutions) == 90


@pytest.mark.parametrize("limit", [0, 1, -1])
def test_r2_3_limit_below_two_is_rejected(limit: int) -> None:
    with pytest.raises(ValueError):
        solve(column_stripes(4), max_solutions=limit)


# R2.4 Deterministic order


def test_r2_4_solutions_are_in_lexicographic_order() -> None:
    columns = [solution.columns for solution in iter_solutions(column_stripes(6))]
    assert columns == sorted(columns)
    assert len(set(columns)) == len(columns)


def test_r2_4_repeated_solves_give_identical_results() -> None:
    puzzle = column_stripes(6)
    assert solve(puzzle, max_solutions=None) == solve(puzzle, max_solutions=None)


def test_iter_solutions_is_lazy() -> None:
    """The first solution, worked out by hand: after 0-2-4-1, column 3 is a dead end."""
    solutions = iter_solutions(column_stripes(8))
    assert next(solutions) == Solution((0, 2, 4, 1, 5, 7, 3, 6))


# Independence


def test_solver_module_does_not_import_rules() -> None:
    assert not any("rules" in name for name in imported_modules(meowdoku.solver))
