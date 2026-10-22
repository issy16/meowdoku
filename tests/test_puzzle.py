from dataclasses import FrozenInstanceError

import pytest

from meowdoku.puzzle import (
    MAX_SIZE,
    MeowdokuError,
    Puzzle,
    PuzzleFormatError,
    PuzzleValidationError,
    connected_parts,
    describe_cell,
)

EXAMPLE_ROWS = ["AABBB", "ACCCB", "ACDDB", "EEDDB", "EEEBB"]


def problems_for(rows: list[str]) -> tuple[str, ...]:
    with pytest.raises(PuzzleValidationError) as excinfo:
        Puzzle.from_rows(rows)
    return excinfo.value.problems


def stripes(size: int) -> list[str]:
    """A size×size board where each row is its own region."""
    labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return [labels[row] * size for row in range(size)]


# Valid puzzles


def test_from_rows_builds_size_and_regions() -> None:
    puzzle = Puzzle.from_rows(EXAMPLE_ROWS)
    assert puzzle.size == 5
    assert puzzle.regions[1] == ("A", "C", "C", "C", "B")


def test_region_of_uses_row_then_column() -> None:
    puzzle = Puzzle.from_rows(EXAMPLE_ROWS)
    assert puzzle.region_of((0, 0)) == "A"
    assert puzzle.region_of((2, 3)) == "D"
    assert puzzle.region_of((4, 2)) == "E"


@pytest.mark.parametrize("cell", [(-1, 0), (0, -1), (5, 0), (0, 5)])
def test_region_of_rejects_cells_outside_board(cell: tuple[int, int]) -> None:
    puzzle = Puzzle.from_rows(EXAMPLE_ROWS)
    with pytest.raises(ValueError):
        puzzle.region_of(cell)


def test_region_cells_groups_every_cell() -> None:
    puzzle = Puzzle.from_rows(EXAMPLE_ROWS)
    assert puzzle.region_cells["D"] == {(2, 2), (2, 3), (3, 2), (3, 3)}
    assert sum(len(cells) for cells in puzzle.region_cells.values()) == 25


def test_region_labels_in_order_of_first_appearance() -> None:
    puzzle = Puzzle.from_rows(["BBA", "CBA", "CCA"])
    assert puzzle.region_labels == ("B", "A", "C")


def test_cells_are_row_major() -> None:
    puzzle = Puzzle.from_rows(["AB", "AB"])
    assert list(puzzle.cells()) == [(0, 0), (0, 1), (1, 0), (1, 1)]


def test_smallest_board_is_valid() -> None:
    assert Puzzle.from_rows(["A"]).size == 1


def test_largest_board_is_valid() -> None:
    assert Puzzle.from_rows(stripes(MAX_SIZE)).size == MAX_SIZE


def test_puzzle_is_immutable() -> None:
    puzzle = Puzzle.from_rows(["A"])
    with pytest.raises(FrozenInstanceError):
        puzzle.size = 2  # type: ignore[misc]


def test_equal_puzzles_compare_and_hash_equal() -> None:
    assert Puzzle.from_rows(EXAMPLE_ROWS) == Puzzle.from_rows(EXAMPLE_ROWS)
    assert len({Puzzle.from_rows(EXAMPLE_ROWS), Puzzle.from_rows(EXAMPLE_ROWS)}) == 1


def test_unsolvable_but_well_formed_puzzle_is_valid() -> None:
    """R2.5: a 2x2 board has no solution, but it is not an input error."""
    assert Puzzle.from_rows(["AB", "AB"]).size == 2


# R4.4 Size


def test_r4_4_empty_board_is_rejected() -> None:
    problems = problems_for([])
    assert problems == ("board size 0 is not supported; it must be between 1 and 16",)


def test_r4_4_board_larger_than_limit_is_rejected() -> None:
    problems = problems_for(stripes(MAX_SIZE + 1))
    assert len(problems) == 1
    assert "board size 17" in problems[0]


# R4.5 Region count


def test_r4_5_too_few_regions() -> None:
    problems = problems_for(["AAA", "BBB", "BBB"])
    assert problems == ("found 2 regions (A, B); a 3x3 board needs exactly 3",)


def test_r4_5_too_many_regions() -> None:
    problems = problems_for(["AB", "CD"])
    assert problems == ("found 4 regions (A, B, C, D); a 2x2 board needs exactly 2",)


# R4.6 Connectivity


def test_r4_6_split_region_is_rejected() -> None:
    problems = problems_for(["ABA", "BBB", "CCC"])
    assert problems == (
        "region 'A' is split into 2 separate parts "
        "(starting at row 1, column 1 and row 1, column 3); "
        "every region must be one connected area",
    )


def test_r4_6_diagonal_contact_does_not_connect() -> None:
    problems = problems_for(["AB", "BA"])
    assert len(problems) == 2
    assert "region 'A' is split" in problems[0]
    assert "region 'B' is split" in problems[1]


def test_all_region_problems_are_collected() -> None:
    """Structural validation reports every problem, not just the first."""
    problems = problems_for(["ABA", "BBB", "BBB"])
    assert len(problems) == 2
    assert problems[0].startswith("found 2 regions")
    assert problems[1].startswith("region 'A' is split")


# R4.7 Direct construction is validated too


def test_r4_7_wrong_row_count_is_rejected() -> None:
    with pytest.raises(PuzzleValidationError) as excinfo:
        Puzzle(size=2, regions=(("A", "B"),))
    assert excinfo.value.problems == ("expected 2 rows, found 1",)


def test_counts_use_singular_for_one() -> None:
    with pytest.raises(PuzzleValidationError) as excinfo:
        Puzzle(size=2, regions=(("A", "B"), ("A",)))
    assert excinfo.value.problems == ("row 2 has 1 cell; expected 2",)


def test_r4_7_wrong_row_length_is_rejected() -> None:
    with pytest.raises(PuzzleValidationError) as excinfo:
        Puzzle(size=3, regions=(("A", "B", "C"),) * 2 + (("A",),))
    assert "row 3 has 1 cell; expected 3" in excinfo.value.problems


@pytest.mark.parametrize("label", ["", "AB", " ", 7])
def test_r4_7_invalid_labels_are_rejected(label: object) -> None:
    with pytest.raises(PuzzleValidationError) as excinfo:
        Puzzle(size=1, regions=((label,),))  # type: ignore[arg-type]
    assert "row 1, column 1 has invalid region label" in excinfo.value.problems[0]


# Errors and helpers


def test_error_types_share_a_base_class() -> None:
    assert issubclass(PuzzleFormatError, MeowdokuError)
    assert issubclass(PuzzleValidationError, MeowdokuError)


def test_validation_error_message_lists_every_problem() -> None:
    error = PuzzleValidationError(["first", "second"])
    assert str(error) == "invalid puzzle:\n  - first\n  - second"


def test_describe_cell_is_one_indexed() -> None:
    assert describe_cell((0, 4)) == "row 1, column 5"


def test_connected_parts_orders_parts_by_first_cell() -> None:
    parts = connected_parts(frozenset({(2, 2), (0, 0), (0, 1)}))
    assert parts == [frozenset({(0, 0), (0, 1)}), frozenset({(2, 2)})]
