"""Each deduction rule on small hand-built boards, with expected marks worked out by hand."""

import pytest

import meowdoku.deduce
from meowdoku.deduce import (
    Deduction,
    Technique,
    Unit,
    _seen_from,
    blocking,
    cat_neighborhood,
    find_deduction,
    last_open_cell,
    line_confined_to_region,
    pigeonhole,
    region_confined_to_line,
)
from meowdoku.puzzle import Puzzle
from meowdoku.state import BoardState, Mark

from helpers import column_stripes, imported_modules

#   col 1 2 3 4 5
# row 1   A A B B B
# row 2   A C C C B
# row 3   A C D D B
# row 4   E E D D B
# row 5   E E E B B
EXAMPLE = Puzzle.from_rows(["AABBB", "ACCCB", "ACDDB", "EEDDB", "EEEBB"])


def empty(puzzle: Puzzle) -> BoardState:
    return BoardState.empty(puzzle.size)


# D1 Cat neighborhood


def test_d1_cat_rules_out_row_column_region_and_neighbors() -> None:
    state = empty(EXAMPLE).with_mark((0, 4), Mark.CAT)
    deduction = cat_neighborhood(EXAMPLE, state)
    assert deduction == Deduction(
        Technique.CAT_NEIGHBORHOOD,
        frozenset({(0, 4)}),
        "This cat rules out its row, column, region, and the cells around it.",
        cross_out=frozenset(
            {(0, 0), (0, 1), (0, 2), (0, 3)}  # row 1
            | {(1, 4), (2, 4), (3, 4), (4, 4)}  # column 5
            | {(4, 3)}  # rest of region B
            | {(1, 3)}  # touching diagonally
        ),
    )


def test_d1_only_reports_cells_still_open() -> None:
    state = empty(EXAMPLE).with_mark((0, 4), Mark.CAT)
    state = state.with_crosses(cat_neighborhood(EXAMPLE, state).cross_out)  # type: ignore[union-attr]
    assert cat_neighborhood(EXAMPLE, state) is None


def test_d1_needs_a_cat() -> None:
    assert cat_neighborhood(EXAMPLE, empty(EXAMPLE)) is None


# D2 Last open cell


def test_d2_row_with_one_open_cell() -> None:
    puzzle = column_stripes(4)
    state = empty(puzzle).with_crosses([(0, 0), (0, 1), (0, 3)])
    deduction = last_open_cell(puzzle, state)
    assert deduction is not None
    assert deduction.place_cat == (0, 2)
    assert deduction.basis == {(0, 0), (0, 1), (0, 2), (0, 3)}
    assert deduction.reason == (
        "This row has only 1 cell left."
    )


def test_d2_region_with_one_open_cell() -> None:
    state = empty(EXAMPLE).with_crosses([(2, 2), (2, 3), (3, 2)])
    deduction = last_open_cell(EXAMPLE, state)
    assert deduction is not None
    assert deduction.place_cat == (3, 3)
    assert deduction.reason == "This region has only 1 cell left."


def test_d2_skips_units_that_already_have_a_cat() -> None:
    puzzle = column_stripes(4)
    state = empty(puzzle).with_mark((0, 2), Mark.CAT).with_crosses([(0, 0), (0, 1), (0, 3)])
    deduction = last_open_cell(puzzle, state)
    assert deduction is None or deduction.place_cat != (0, 2)


# D3 Confinement


def test_d3_region_confined_to_one_row() -> None:
    """Crossing out row 3, column 2 leaves region C only in row 2."""
    state = empty(EXAMPLE).with_crosses([(2, 1)])
    deduction = region_confined_to_line(EXAMPLE, state)
    assert deduction == Deduction(
        Technique.CONFINEMENT,
        frozenset({(1, 1), (1, 2), (1, 3)}),
        "The cat must be in region 'C' in this row, so cross out the rest of this row.",
        cross_out=frozenset({(1, 0), (1, 4)}),
    )


def test_d3_column_confined_to_one_region() -> None:
    """Column 5 lies entirely in region B, so B's other cells are ruled out."""
    deduction = line_confined_to_region(EXAMPLE, empty(EXAMPLE))
    assert deduction == Deduction(
        Technique.CONFINEMENT,
        frozenset({(0, 4), (1, 4), (2, 4), (3, 4), (4, 4)}),
        "The cat must be in region 'B' in this column, so cross out the rest of region 'B'.",
        cross_out=frozenset({(0, 2), (0, 3), (4, 3)}),
    )


# D4 Pigeonhole

#   col 1 2 3 4 5
# row 1   A A B B C
# row 2   A A B B C
# row 3   C C C C C
# row 4   D D D E E
# row 5   D D D E E
PIGEONHOLE = Puzzle.from_rows(["AABBC", "AABBC", "CCCCC", "DDDEE", "DDDEE"])


def test_d4_two_regions_in_two_rows() -> None:
    deduction = pigeonhole(PIGEONHOLE, empty(PIGEONHOLE))
    assert deduction is not None
    assert deduction.technique is Technique.PIGEONHOLE
    assert deduction.cross_out == {(0, 4), (1, 4)}
    assert deduction.reason == (
        "These regions only fit in these rows, so cross out the rest of those rows."
    )


def test_d4_regions_with_cats_are_ignored() -> None:
    state = empty(PIGEONHOLE).with_mark((0, 0), Mark.CAT)
    deduction = pigeonhole(PIGEONHOLE, state)
    assert deduction is None or not deduction.basis & PIGEONHOLE.region_cells["A"]


# D5 Blocking

#   col 1 2 3 4 5
# row 1   A A A B B
# row 2   A A C C C
# row 3   D D D C C
# row 4   D D E E E
# row 5   D E E E E
BLOCKING = Puzzle.from_rows(["AAABB", "AACCC", "DDDCC", "DDEEE", "DEEEE"])


def test_d5_cat_that_would_empty_another_region() -> None:
    deduction = blocking(BLOCKING, empty(BLOCKING))
    assert deduction == Deduction(
        Technique.BLOCKING,
        frozenset({(0, 0)}),  # the cell itself: the hint calls it "here"
        "A cat here would leave region 'B' with no room for its cat, so it can't have a cat.",
        cross_out=frozenset({(0, 0)}),
    )


# Order and determinism (R7.4)


def test_r7_4_rules_are_tried_simplest_first() -> None:
    state = empty(EXAMPLE).with_mark((0, 4), Mark.CAT).with_crosses([(2, 1)])
    deduction = find_deduction(EXAMPLE, state)
    assert deduction is not None
    assert deduction.technique is Technique.CAT_NEIGHBORHOOD


def test_r7_4_first_hint_on_empty_example() -> None:
    deduction = find_deduction(EXAMPLE, empty(EXAMPLE))
    assert deduction == line_confined_to_region(EXAMPLE, empty(EXAMPLE))


def test_no_deduction_on_open_board_without_structure() -> None:
    """Every column is its own region and nothing is marked: no rule applies."""
    puzzle = column_stripes(6)
    assert find_deduction(puzzle, empty(puzzle)) is None


# Independence


def test_deduce_module_does_not_import_solver() -> None:
    assert not any("solver" in name for name in imported_modules(meowdoku.deduce))


@pytest.mark.parametrize(
    ("cell", "cells", "phrase"),
    [
        ((2, 8), {(1, 8), (1, 9)}, "the row above"),
        ((2, 8), {(3, 0)}, "the row below"),
        ((2, 8), {(0, 3)}, "a row further up"),
        ((2, 8), {(9, 8)}, "a row further down"),
    ],
)
def test_d5_names_a_blocked_row_by_where_it_is(
    cell: tuple[int, int], cells: set[tuple[int, int]], phrase: str
) -> None:
    """The owner's case: a cat at row 3, column 9 touches both open cells of row 2."""
    row = next(iter(cells))[0]
    assert _seen_from(cell, Unit(f"row {row + 1}", frozenset(cells))) == phrase


@pytest.mark.parametrize(
    ("column", "phrase"),
    [(7, "the column to the left"), (9, "the column to the right"), (2, "a column further left")],
)
def test_d5_names_a_blocked_column_by_where_it_is(column: int, phrase: str) -> None:
    cells = frozenset({(0, column), (5, column)})
    assert _seen_from((2, 8), Unit(f"column {column + 1}", cells)) == phrase
