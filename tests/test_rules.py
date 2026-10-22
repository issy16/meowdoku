"""Validator tests on hand-built placements. None of them use the solver."""

import ast
import itertools
from pathlib import Path

import pytest

import meowdoku.rules
from meowdoku.puzzle import Cell, Puzzle
from meowdoku.rules import Rule, RuleViolation, find_violations, is_valid_solution

# README example; its only solution was found by hand-checked brute force.
EXAMPLE = Puzzle.from_rows(["AABBB", "ACCCB", "ACDDB", "EEDDB", "EEEBB"])
EXAMPLE_SOLUTION = [(0, 4), (1, 2), (2, 0), (3, 3), (4, 1)]

# Each row is its own region, so the region rule repeats the row rule.
ROW_STRIPES_5 = Puzzle.from_rows(["AAAAA", "BBBBB", "CCCCC", "DDDDD", "EEEEE"])
# Each column is its own region, so the region rule repeats the column rule.
COLUMN_STRIPES_4 = Puzzle.from_rows(["ABCD"] * 4)
COLUMN_STRIPES_5 = Puzzle.from_rows(["ABCDE"] * 5)


def rules_of(violations: list[RuleViolation]) -> list[Rule]:
    return [violation.rule for violation in violations]


def cols_to_cats(columns: tuple[int, ...]) -> list[Cell]:
    return [(row, col) for row, col in enumerate(columns)]


# Valid placements


def test_readme_solution_is_valid() -> None:
    assert find_violations(EXAMPLE, EXAMPLE_SOLUTION) == []
    assert is_valid_solution(EXAMPLE, EXAMPLE_SOLUTION)


def test_accepts_any_collection_type() -> None:
    for cats in (EXAMPLE_SOLUTION, tuple(EXAMPLE_SOLUTION), set(EXAMPLE_SOLUTION)):
        assert is_valid_solution(EXAMPLE, cats)


def test_repeated_cells_count_once() -> None:
    assert is_valid_solution(EXAMPLE, EXAMPLE_SOLUTION + [(0, 4)])


def test_single_cell_board() -> None:
    assert is_valid_solution(Puzzle.from_rows(["A"]), [(0, 0)])


def test_readme_example_has_exactly_one_valid_placement() -> None:
    """Brute force over every one-cat-per-row placement confirms the README claim."""
    valid = [
        columns
        for columns in itertools.product(range(5), repeat=5)
        if is_valid_solution(EXAMPLE, cols_to_cats(columns))
    ]
    assert valid == [(4, 2, 0, 3, 1)]


# R1.1 Rows (columns and regions are all satisfied)


def test_r1_1_two_cats_in_a_row_and_an_empty_row() -> None:
    cats = [(0, 0), (2, 1), (4, 2), (0, 3), (2, 4)]
    violations = find_violations(COLUMN_STRIPES_5, cats)
    assert rules_of(violations) == [Rule.ROW] * 4
    assert violations[0] == RuleViolation(
        Rule.ROW, ((0, 0), (0, 3)), "row 1 has 2 cats; it needs exactly one"
    )
    assert violations[1] == RuleViolation(
        Rule.ROW,
        ((1, 0), (1, 1), (1, 2), (1, 3), (1, 4)),
        "row 2 has no cat; it needs exactly one",
    )


# R1.2 Columns (rows and regions are all satisfied)


def test_r1_2_two_cats_in_a_column_and_an_empty_column() -> None:
    cats = [(0, 0), (1, 2), (2, 4), (3, 0), (4, 2)]
    violations = find_violations(ROW_STRIPES_5, cats)
    assert rules_of(violations) == [Rule.COLUMN] * 4
    assert [violation.message for violation in violations] == [
        "column 1 has 2 cats; it needs exactly one",
        "column 2 has no cat; it needs exactly one",
        "column 3 has 2 cats; it needs exactly one",
        "column 4 has no cat; it needs exactly one",
    ]


# R1.3 Regions (rows, columns, and adjacency are all satisfied)


def test_r1_3_two_cats_in_a_region_and_an_empty_region() -> None:
    puzzle = Puzzle.from_rows(["AABB", "ACCB", "ACDD", "ADDD"])
    cats = [(0, 1), (1, 3), (2, 0), (3, 2)]
    assert find_violations(puzzle, cats) == [
        RuleViolation(Rule.REGION, ((0, 1), (2, 0)), "region 'A' has 2 cats; it needs exactly one"),
        RuleViolation(
            Rule.REGION, ((1, 1), (1, 2), (2, 1)), "region 'C' has no cat; it needs exactly one"
        ),
    ]


# R1.4 Adjacency (rows, columns, and regions are all satisfied)


def test_r1_4_diagonal_neighbors_are_reported_pair_by_pair() -> None:
    violations = find_violations(COLUMN_STRIPES_4, cols_to_cats((0, 1, 2, 3)))
    assert rules_of(violations) == [Rule.ADJACENT] * 3
    assert [violation.cells for violation in violations] == [
        ((0, 0), (1, 1)),
        ((1, 1), (2, 2)),
        ((2, 2), (3, 3)),
    ]
    assert violations[0].message == (
        "cats at row 1, column 1 and row 2, column 2 touch; cats may not share an edge or corner"
    )


def test_r1_4_anti_diagonal_neighbors_are_reported() -> None:
    violations = find_violations(COLUMN_STRIPES_4, cols_to_cats((3, 2, 1, 0)))
    assert [violation.cells for violation in violations] == [
        ((0, 3), (1, 2)),
        ((1, 2), (2, 1)),
        ((2, 1), (3, 0)),
    ]


@pytest.mark.parametrize(
    ("first", "second"),
    [((1, 1), (1, 2)), ((1, 1), (2, 1)), ((1, 1), (2, 2)), ((1, 2), (2, 1))],
)
def test_r1_4_every_kind_of_touch_is_reported_once(first: Cell, second: Cell) -> None:
    adjacent = [v for v in find_violations(ROW_STRIPES_5, [second, first]) if v.rule is Rule.ADJACENT]
    assert [violation.cells for violation in adjacent] == [(first, second)]


def test_r1_4_cats_two_apart_do_not_touch() -> None:
    cats = frozenset({(0, 0), (0, 2), (2, 0), (2, 2)})
    assert meowdoku.rules.check_adjacency(cats) == []


# Out of bounds


def test_cats_outside_board_are_reported_and_otherwise_ignored() -> None:
    cats = EXAMPLE_SOLUTION + [(5, 0), (-1, 2)]
    assert find_violations(EXAMPLE, cats) == [
        RuleViolation(Rule.OUT_OF_BOUNDS, ((-1, 2),), "cat at row 0, column 3 is outside the 5x5 board"),
        RuleViolation(Rule.OUT_OF_BOUNDS, ((5, 0),), "cat at row 6, column 1 is outside the 5x5 board"),
    ]


# Several rules at once


def test_empty_placement_reports_every_missing_cat() -> None:
    violations = find_violations(COLUMN_STRIPES_4, [])
    assert rules_of(violations) == [Rule.ROW] * 4 + [Rule.COLUMN] * 4 + [Rule.REGION] * 4


def test_violations_are_ordered_by_rule() -> None:
    cats = [(0, 0), (0, 1), (9, 9)]
    order = [Rule.OUT_OF_BOUNDS, Rule.ROW, Rule.COLUMN, Rule.REGION, Rule.ADJACENT]
    found = rules_of(find_violations(COLUMN_STRIPES_4, cats))
    assert found == sorted(found, key=order.index)
    assert set(found) == set(order)


def test_result_does_not_depend_on_input_order() -> None:
    cats = [(3, 3), (0, 0), (1, 1), (0, 2)]
    assert find_violations(COLUMN_STRIPES_4, cats) == find_violations(COLUMN_STRIPES_4, cats[::-1])


# R5.3 Independence


def test_r5_3_rules_module_does_not_import_solver() -> None:
    tree = ast.parse(Path(meowdoku.rules.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not any("solver" in name for name in imported)
