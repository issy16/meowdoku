"""Check a placement of cats against the Meowdoku rules (R1, R5).

This module is the independent reference for what a valid solution is. It
must never import the solver (R5.3).
"""

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from enum import Enum

from meowdoku.puzzle import Cell, Puzzle, count_of, describe_cell


class Rule(Enum):
    ROW = "row"
    COLUMN = "column"
    REGION = "region"
    ADJACENT = "adjacent"
    OUT_OF_BOUNDS = "out of bounds"


@dataclass(frozen=True)
class RuleViolation:
    """One broken rule: which rule, the cells involved, and a readable message.

    For a row, column, or region with too many cats, `cells` holds those cats.
    For one with no cat, `cells` holds every cell of that row, column, or region.
    """

    rule: Rule
    cells: tuple[Cell, ...]
    message: str


def find_violations(puzzle: Puzzle, cats: Collection[Cell]) -> list[RuleViolation]:
    """Return every rule the placement breaks; an empty list means a valid solution.

    `cats` may be any collection of cells; repeated cells count once.
    Violations are ordered by rule (bounds, rows, columns, regions, adjacency),
    then by position, so the result is deterministic.
    """
    placed = frozenset(cats)
    on_board = frozenset(cat for cat in placed if puzzle.in_bounds(cat))
    return (
        check_bounds(puzzle, placed)
        + check_rows(puzzle, on_board)
        + check_columns(puzzle, on_board)
        + check_regions(puzzle, on_board)
        + check_adjacency(on_board)
    )


def is_valid_solution(puzzle: Puzzle, cats: Collection[Cell]) -> bool:
    return not find_violations(puzzle, cats)


def check_bounds(puzzle: Puzzle, cats: frozenset[Cell]) -> list[RuleViolation]:
    return [
        RuleViolation(
            Rule.OUT_OF_BOUNDS,
            (cat,),
            f"cat at {describe_cell(cat)} is outside the {puzzle.size}x{puzzle.size} board",
        )
        for cat in sorted(cats)
        if not puzzle.in_bounds(cat)
    ]


def check_rows(puzzle: Puzzle, cats: frozenset[Cell]) -> list[RuleViolation]:
    """R1.1: every row contains exactly one cat."""
    groups = (
        (f"row {row + 1}", frozenset((row, col) for col in range(puzzle.size)))
        for row in range(puzzle.size)
    )
    return _check_exactly_one(Rule.ROW, groups, cats)


def check_columns(puzzle: Puzzle, cats: frozenset[Cell]) -> list[RuleViolation]:
    """R1.2: every column contains exactly one cat."""
    groups = (
        (f"column {col + 1}", frozenset((row, col) for row in range(puzzle.size)))
        for col in range(puzzle.size)
    )
    return _check_exactly_one(Rule.COLUMN, groups, cats)


def check_regions(puzzle: Puzzle, cats: frozenset[Cell]) -> list[RuleViolation]:
    """R1.3: every region contains exactly one cat."""
    groups = ((f"region {label!r}", cells) for label, cells in puzzle.region_cells.items())
    return _check_exactly_one(Rule.REGION, groups, cats)


def check_adjacency(cats: frozenset[Cell]) -> list[RuleViolation]:
    """R1.4: no two cats share an edge or corner. Each touching pair is reported once."""
    violations = []
    for cat in sorted(cats):
        for neighbor in _later_neighbors(cat):
            if neighbor in cats:
                violations.append(
                    RuleViolation(
                        Rule.ADJACENT,
                        (cat, neighbor),
                        f"cats at {describe_cell(cat)} and {describe_cell(neighbor)} touch; "
                        "cats may not share an edge or corner",
                    )
                )
    return violations


def _later_neighbors(cell: Cell) -> list[Cell]:
    """Neighbors that come after `cell` in row-major order, so each pair is seen once."""
    row, col = cell
    return [(row, col + 1), (row + 1, col - 1), (row + 1, col), (row + 1, col + 1)]


def _check_exactly_one(
    rule: Rule, groups: Iterable[tuple[str, frozenset[Cell]]], cats: frozenset[Cell]
) -> list[RuleViolation]:
    """Report each named group of cells that doesn't contain exactly one cat."""
    violations = []
    for name, cells in groups:
        cats_here = tuple(sorted(cells & cats))
        if not cats_here:
            violations.append(
                RuleViolation(rule, tuple(sorted(cells)), f"{name} has no cat; it needs exactly one")
            )
        elif len(cats_here) > 1:
            violations.append(
                RuleViolation(
                    rule,
                    cats_here,
                    f"{name} has {count_of(len(cats_here), 'cat')}; it needs exactly one",
                )
            )
    return violations
