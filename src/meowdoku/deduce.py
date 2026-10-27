"""Logical deduction rules D1-D5 used for hints (see docs/algorithm.md).

D6, which builds on these rules, lives in assume.py.

Each rule only concludes what must hold in every solution that matches the
current marks, so hints never contradict the solution (R7.7). This module
must never import the solver: hints are tested against solver output.
"""

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property, lru_cache

from meowdoku.messages import Message, Region
from meowdoku.puzzle import Cell, Puzzle
from meowdoku.state import BoardState


class Technique(Enum):
    CAT_NEIGHBORHOOD = "D1"
    LAST_OPEN_CELL = "D2"
    CONFINEMENT = "D3"
    PIGEONHOLE = "D4"
    BLOCKING = "D5"
    CONTRADICTION = "D6"


@dataclass(frozen=True)
class Unit:
    """A row, column, or region: a group of cells that needs exactly one cat."""

    name: str
    cells: frozenset[Cell]
    label: str | None = None
    """The region's label; None for rows and columns."""

    @property
    def kind(self) -> str:
        """'row', 'column', or 'region', for short messages like "This row has ..."."""
        return self.name.split()[0]

    @property
    def region(self) -> Region:
        """How messages name this region; hints show it as a color (R7.8)."""
        assert self.label is not None, f"{self.name} is not a region"
        return Region(self.label)


@dataclass(frozen=True)
class Deduction:
    """One logical step: the reasoning and what it lets the player mark.

    Exactly one of `place_cat` and `cross_out` is set. Only D6 sets `steps`,
    its explanation one line at a time, and `trace`, the D1-D5 deductions
    that followed its assumption.
    """

    technique: Technique
    basis: frozenset[Cell]
    reason: Message
    place_cat: Cell | None = None
    cross_out: frozenset[Cell] = field(default_factory=frozenset)
    steps: tuple[Message, ...] = ()
    trace: tuple["Deduction", ...] = ()


# Units
#
# These depend only on the puzzle, so they're cached: D6 runs D1-D5 many
# times on the same puzzle.

PUZZLE_CACHE_SIZE = 32


@lru_cache(maxsize=PUZZLE_CACHE_SIZE)
def rows(puzzle: Puzzle) -> tuple[Unit, ...]:
    return tuple(
        Unit(f"row {row + 1}", frozenset((row, col) for col in range(puzzle.size)))
        for row in range(puzzle.size)
    )


@lru_cache(maxsize=PUZZLE_CACHE_SIZE)
def columns(puzzle: Puzzle) -> tuple[Unit, ...]:
    return tuple(
        Unit(f"column {col + 1}", frozenset((row, col) for row in range(puzzle.size)))
        for col in range(puzzle.size)
    )


@lru_cache(maxsize=PUZZLE_CACHE_SIZE)
def regions(puzzle: Puzzle) -> tuple[Unit, ...]:
    return tuple(Unit(f"region {label!r}", cells, label) for label, cells in puzzle.region_cells.items())


@lru_cache(maxsize=PUZZLE_CACHE_SIZE)
def all_units(puzzle: Puzzle) -> tuple[Unit, ...]:
    return rows(puzzle) + columns(puzzle) + regions(puzzle)


# Shared helpers


def open_cells(cells: frozenset[Cell], state: BoardState) -> frozenset[Cell]:
    return frozenset(cell for cell in cells if state.is_open(cell))


def has_cat(unit: Unit, state: BoardState) -> bool:
    return bool(unit.cells & state.cats)


@lru_cache(maxsize=PUZZLE_CACHE_SIZE * 256)
def ruled_out_by(puzzle: Puzzle, cat: Cell) -> frozenset[Cell]:
    """Cells that can't hold a cat if `cat` does: same row, column, or region, or touching."""
    row, col = cat
    region = puzzle.region_cells[puzzle.region_of(cat)]
    lines = {(row, c) for c in range(puzzle.size)} | {(r, col) for r in range(puzzle.size)}
    touching = {
        (r, c)
        for r in range(row - 1, row + 2)
        for c in range(col - 1, col + 2)
        if puzzle.in_bounds((r, c))
    }
    return frozenset((lines | touching | region) - {cat})


# D1 Cat neighborhood


def cat_neighborhood(puzzle: Puzzle, state: BoardState) -> Deduction | None:
    """A placed cat rules out its row, column, region, and touching cells."""
    for cat in sorted(state.cats):
        targets = open_cells(ruled_out_by(puzzle, cat), state)
        if targets:
            return Deduction(
                Technique.CAT_NEIGHBORHOOD,
                frozenset({cat}),
                Message("d1"),
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
                Message(f"d2.{unit.kind}"),
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
                        Message(f"d3.line.{line.kind}", region=region.region),
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
                        Message(f"d3.region.{line.kind}", region=region.region),
                        cross_out=targets,
                    )
    return None


# D4 Pigeonhole


def pigeonhole(puzzle: Puzzle, state: BoardState) -> Deduction | None:
    """If k regions fit inside k rows (or columns), those lines' other cells are ✕.

    Groups of 2 up to N/2 regions are tried; one region is D3.
    """
    candidates = [
        _Candidate(region, open_cells(region.cells, state))
        for region in regions(puzzle)
        if not has_cat(region, state) and open_cells(region.cells, state)
    ]
    open_by_line = (
        [open_cells(line.cells, state) for line in rows(puzzle)],
        [open_cells(line.cells, state) for line in columns(puzzle)],
    )
    for group_size in range(2, puzzle.size // 2 + 1):
        for axis, line_word in ((0, "rows"), (1, "columns")):
            for group in _fitting_groups(candidates, group_size, axis):
                deduction = _pigeonhole_for_group(group, open_by_line[axis], axis, line_word)
                if deduction:
                    return deduction
    return None


@dataclass(frozen=True)
class _Candidate:
    """A region without a cat, its open cells, and the rows and columns they lie in.

    The lines are worked out once per call, since D6 runs D4 many times.
    """

    region: Unit
    remaining: frozenset[Cell]

    @cached_property
    def lines(self) -> tuple[frozenset[int], frozenset[int]]:
        return (
            frozenset(row for row, _ in self.remaining),
            frozenset(col for _, col in self.remaining),
        )


def _fitting_groups(
    candidates: Sequence[_Candidate], group_size: int, axis: int
) -> Iterator[tuple[_Candidate, ...]]:
    """Groups of `group_size` candidates whose open cells lie in at most that many lines.

    The same groups, in the same order, as itertools.combinations, without the
    ones that can't fit: adding a region never takes away a line, so a group
    that is already too wide is skipped with everything that would extend it.
    """

    def extend(
        start: int, group: tuple[_Candidate, ...], lines: frozenset[int]
    ) -> Iterator[tuple[_Candidate, ...]]:
        if len(group) == group_size:
            yield group
            return
        for index in range(start, len(candidates)):
            wider = lines | candidates[index].lines[axis]
            if len(wider) <= group_size:
                yield from extend(index + 1, group + (candidates[index],), wider)

    yield from extend(0, (), frozenset())


def _pigeonhole_for_group(
    group: Sequence[_Candidate],
    open_by_line: Sequence[frozenset[Cell]],
    axis: int,
    line_word: str,
) -> Deduction | None:
    """`open_by_line[i]` holds the open cells of row i (or column i, for columns)."""
    lines = frozenset().union(*(candidate.lines[axis] for candidate in group))
    if len(lines) != len(group):
        return None
    # The group's open cells all lie in these lines, so any other open cell there is a target.
    open_in_group = sum(len(candidate.remaining) for candidate in group)
    if sum(len(open_by_line[line]) for line in lines) == open_in_group:
        return None
    remaining = frozenset().union(*(candidate.remaining for candidate in group))
    targets = frozenset().union(*(open_by_line[line] for line in lines)) - remaining
    return Deduction(
        Technique.PIGEONHOLE,
        remaining,
        Message(f"d4.{line_word}"),
        cross_out=targets,
    )


# D5 Blocking


def blocking(puzzle: Puzzle, state: BoardState) -> Deduction | None:
    """An open cell is ✕ if a cat there would leave some other unit with no open cell.

    The basis is the cell itself, which the hint calls "here".
    """
    units = [
        (unit, open_cells(unit.cells, state))
        for unit in all_units(puzzle)
        if not has_cat(unit, state) and open_cells(unit.cells, state)
    ]
    for cell in puzzle.cells():
        if not state.is_open(cell):
            continue
        ruled_out = ruled_out_by(puzzle, cell)
        for unit, remaining in units:
            if cell in unit.cells:
                continue
            if remaining <= ruled_out:
                return Deduction(
                    Technique.BLOCKING,
                    frozenset({cell}),
                    Message("d5", unit=_seen_from(cell, unit)),
                    cross_out=frozenset({cell}),
                )
    return None


def _seen_from(cell: Cell, unit: Unit) -> Message:
    """Name a unit without numbers, from where `cell` is: "the row above", "region 'B'".

    The blocked unit is never the cell's own row or column, so a row is above
    or below it and a column is to its left or right.
    """
    if unit.kind == "region":
        return Message("unit.region", region=unit.region)
    axis = 0 if unit.kind == "row" else 1
    distance = next(iter(unit.cells))[axis] - cell[axis]
    if unit.kind == "row":
        side = ("above" if distance < 0 else "below") if abs(distance) == 1 else ("up" if distance < 0 else "down")
        return Message(f"unit.row_{side}")
    side = "left" if distance < 0 else "right"
    return Message(f"unit.column_{side}" if abs(distance) == 1 else f"unit.column_further_{side}")


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
