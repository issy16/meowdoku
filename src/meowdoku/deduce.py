"""Logical deduction rules D1-D5 used for hints (see docs/algorithm.md).

Each rule only concludes what must hold in every solution that matches the
current marks, so hints never contradict the solution (R7.7). This module
must never import the solver: hints are tested against solver output.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import Enum
from itertools import combinations

from meowdoku.puzzle import Cell, Puzzle, describe_cell
from meowdoku.state import BoardState


class Technique(Enum):
    CAT_NEIGHBORHOOD = "D1"
    LAST_OPEN_CELL = "D2"
    CONFINEMENT = "D3"
    PIGEONHOLE = "D4"
    BLOCKING = "D5"


@dataclass(frozen=True)
class Unit:
    """A row, column, or region: a group of cells that needs exactly one cat."""

    name: str
    cells: frozenset[Cell]


@dataclass(frozen=True)
class Deduction:
    """One logical step: the reasoning and what it lets the player mark.

    Exactly one of `place_cat` and `cross_out` is set.
    """

    technique: Technique
    basis: frozenset[Cell]
    reason: str
    place_cat: Cell | None = None
    cross_out: frozenset[Cell] = field(default_factory=frozenset)


# Units


def rows(puzzle: Puzzle) -> list[Unit]:
    return [
        Unit(f"row {row + 1}", frozenset((row, col) for col in range(puzzle.size)))
        for row in range(puzzle.size)
    ]


def columns(puzzle: Puzzle) -> list[Unit]:
    return [
        Unit(f"column {col + 1}", frozenset((row, col) for row in range(puzzle.size)))
        for col in range(puzzle.size)
    ]


def regions(puzzle: Puzzle) -> list[Unit]:
    return [Unit(f"region {label!r}", cells) for label, cells in puzzle.region_cells.items()]


def all_units(puzzle: Puzzle) -> list[Unit]:
    return rows(puzzle) + columns(puzzle) + regions(puzzle)


# Shared helpers


def open_cells(cells: frozenset[Cell], state: BoardState) -> frozenset[Cell]:
    return frozenset(cell for cell in cells if state.is_open(cell))


def has_cat(unit: Unit, state: BoardState) -> bool:
    return bool(unit.cells & state.cats)


def ruled_out_by(puzzle: Puzzle, cat: Cell) -> frozenset[Cell]:
    """Cells that can't hold a cat if `cat` does: same row, column, or region, or touching."""
    row, col = cat
    region = puzzle.region_cells[puzzle.region_of(cat)]
    nearby = {
        (r, c)
        for r, c in puzzle.cells()
        if r == row or c == col or (abs(r - row) <= 1 and abs(c - col) <= 1)
    }
    return frozenset((nearby | region) - {cat})


def _capitalize(text: str) -> str:
    return text[0].upper() + text[1:]


def _join(items: Sequence[str]) -> str:
    """Join as 'a', 'a and b', or 'a, b and c'."""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


# D1 Cat neighborhood


def cat_neighborhood(puzzle: Puzzle, state: BoardState) -> Deduction | None:
    """A placed cat rules out its row, column, region, and touching cells."""
    for cat in sorted(state.cats):
        targets = open_cells(ruled_out_by(puzzle, cat), state)
        if targets:
            return Deduction(
                Technique.CAT_NEIGHBORHOOD,
                frozenset({cat}),
                f"The cat at {describe_cell(cat)} rules out every other cell in its row, "
                "column, and region, and every cell touching it.",
                cross_out=targets,
            )
    return None


# D2 Last open cell


def last_open_cell(puzzle: Puzzle, state: BoardState) -> Deduction | None:
    """A row, column, or region with one open cell left must have its cat there."""
    for unit in all_units(puzzle):
        if has_cat(unit, state):
            continue
        remaining = open_cells(unit.cells, state)
        if len(remaining) == 1:
            (cell,) = remaining
            return Deduction(
                Technique.LAST_OPEN_CELL,
                unit.cells,
                f"{_capitalize(unit.name)} has only one cell left that can hold its cat, "
                f"so the cat goes at {describe_cell(cell)}.",
                place_cat=cell,
            )
    return None


# D3 Confinement


def confinement(puzzle: Puzzle, state: BoardState) -> Deduction | None:
    return region_confined_to_line(puzzle, state) or line_confined_to_region(puzzle, state)


def region_confined_to_line(puzzle: Puzzle, state: BoardState) -> Deduction | None:
    """If a region's open cells all lie in one row or column, that line's other cells are ✕."""
    lines = rows(puzzle) + columns(puzzle)
    for region in regions(puzzle):
        remaining = open_cells(region.cells, state)
        if has_cat(region, state) or not remaining:
            continue
        for line in lines:
            if remaining <= line.cells:
                targets = open_cells(line.cells - region.cells, state)
                if targets:
                    return Deduction(
                        Technique.CONFINEMENT,
                        remaining,
                        f"Every cell left in {region.name} is in {line.name}, so the cat of "
                        f"{line.name} must be in {region.name}. The other cells in "
                        f"{line.name} can't have a cat.",
                        cross_out=targets,
                    )
    return None


def line_confined_to_region(puzzle: Puzzle, state: BoardState) -> Deduction | None:
    """If a row's or column's open cells all lie in one region, that region's other cells are ✕."""
    for line in rows(puzzle) + columns(puzzle):
        remaining = open_cells(line.cells, state)
        if has_cat(line, state) or not remaining:
            continue
        for region in regions(puzzle):
            if remaining <= region.cells:
                targets = open_cells(region.cells - line.cells, state)
                if targets:
                    return Deduction(
                        Technique.CONFINEMENT,
                        remaining,
                        f"Every cell left in {line.name} is in {region.name}, so the cat of "
                        f"{region.name} must be in {line.name}. The other cells in "
                        f"{region.name} can't have a cat.",
                        cross_out=targets,
                    )
    return None


# D4 Pigeonhole


def pigeonhole(puzzle: Puzzle, state: BoardState) -> Deduction | None:
    """If k regions fit inside k rows (or columns), those lines' other cells are ✕.

    Groups of 2 up to N/2 regions are tried; one region is D3.
    """
    candidates = [
        (region, open_cells(region.cells, state))
        for region in regions(puzzle)
        if not has_cat(region, state) and open_cells(region.cells, state)
    ]
    for group_size in range(2, puzzle.size // 2 + 1):
        for axis, line_word in ((0, "rows"), (1, "columns")):
            for group in combinations(candidates, group_size):
                deduction = _pigeonhole_for_group(puzzle, state, group, axis, line_word)
                if deduction:
                    return deduction
    return None


def _pigeonhole_for_group(
    puzzle: Puzzle,
    state: BoardState,
    group: Sequence[tuple[Unit, frozenset[Cell]]],
    axis: int,
    line_word: str,
) -> Deduction | None:
    remaining = frozenset().union(*(cells for _, cells in group))
    lines = sorted({cell[axis] for cell in remaining})
    if len(lines) != len(group):
        return None
    group_cells = frozenset().union(*(region.cells for region, _ in group))
    targets = frozenset(
        cell
        for cell in puzzle.cells()
        if cell[axis] in lines and state.is_open(cell) and cell not in group_cells
    )
    if not targets:
        return None
    region_names = _join([region.name for region, _ in group])
    line_names = f"{line_word} " + _join([str(line + 1) for line in lines])
    return Deduction(
        Technique.PIGEONHOLE,
        remaining,
        f"Every cell left in {region_names} is in {line_names}. These {len(group)} regions "
        f"need {len(group)} cats, which fill {line_names}, so the other cells in "
        f"{line_names} can't have a cat.",
        cross_out=targets,
    )


# D5 Blocking


def blocking(puzzle: Puzzle, state: BoardState) -> Deduction | None:
    """An open cell is ✕ if a cat there would leave some other unit with no open cell."""
    units = [unit for unit in all_units(puzzle) if not has_cat(unit, state)]
    for cell in puzzle.cells():
        if not state.is_open(cell):
            continue
        ruled_out = ruled_out_by(puzzle, cell)
        for unit in units:
            remaining = open_cells(unit.cells, state)
            if cell in unit.cells or not remaining:
                continue
            if remaining <= ruled_out:
                return Deduction(
                    Technique.BLOCKING,
                    remaining,
                    f"A cat at {describe_cell(cell)} would rule out every cell left in "
                    f"{unit.name}, so {describe_cell(cell)} can't have a cat.",
                    cross_out=frozenset({cell}),
                )
    return None


# All rules, simplest first (R7.4)

RULES: tuple[Callable[[Puzzle, BoardState], Deduction | None], ...] = (
    cat_neighborhood,
    last_open_cell,
    confinement,
    pigeonhole,
    blocking,
)


def find_deduction(puzzle: Puzzle, state: BoardState) -> Deduction | None:
    """Return the first deduction from D1-D5 that adds new marks, or None."""
    for rule in RULES:
        deduction = rule(puzzle, state)
        if deduction:
            return deduction
    return None
