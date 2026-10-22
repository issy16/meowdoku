"""Find solutions with row-by-row backtracking (see docs/algorithm.md).

This module must never import the rule validator (R5.3); tests use the
validator as an independent check on what the solver returns.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum
from itertools import islice

from meowdoku.puzzle import Cell, Puzzle

DEFAULT_MAX_SOLUTIONS = 2


@dataclass(frozen=True)
class Solution:
    """A solution as one column per row: columns[row] is that row's cat."""

    columns: tuple[int, ...]

    @property
    def cats(self) -> frozenset[Cell]:
        return frozenset(enumerate(self.columns))


class SolveStatus(Enum):
    NONE = "none"
    UNIQUE = "unique"
    MULTIPLE = "multiple"


@dataclass(frozen=True)
class SolveResult:
    status: SolveStatus
    solutions: tuple[Solution, ...]


def solve(puzzle: Puzzle, max_solutions: int | None = DEFAULT_MAX_SOLUTIONS) -> SolveResult:
    """Search for solutions and classify the puzzle as NONE, UNIQUE, or MULTIPLE.

    Stops after `max_solutions` (default 2, enough to tell UNIQUE from
    MULTIPLE; R2.3). Pass None to find every solution.
    """
    if max_solutions is not None and max_solutions < 2:
        raise ValueError("max_solutions must be at least 2 to tell UNIQUE from MULTIPLE, or None")
    solutions = tuple(islice(iter_solutions(puzzle), max_solutions))
    return SolveResult(_classify(len(solutions)), solutions)


def _classify(count: int) -> SolveStatus:
    if count == 0:
        return SolveStatus.NONE
    if count == 1:
        return SolveStatus.UNIQUE
    return SolveStatus.MULTIPLE


def iter_solutions(puzzle: Puzzle) -> Iterator[Solution]:
    """Yield every solution lazily, in lexicographic order of columns (R2.4)."""
    yield from _search(puzzle, _Placement())


@dataclass
class _Placement:
    """The cats placed so far during the search, one per row from the top."""

    columns: list[int] = field(default_factory=list)
    used_columns: set[int] = field(default_factory=set)
    used_regions: set[str] = field(default_factory=set)

    def can_place(self, col: int, region: str) -> bool:
        if col in self.used_columns or region in self.used_regions:
            return False
        # One cat per row means only the previous row's cat can touch this one.
        return not self.columns or abs(col - self.columns[-1]) > 1

    def place(self, col: int, region: str) -> None:
        self.columns.append(col)
        self.used_columns.add(col)
        self.used_regions.add(region)

    def remove(self, col: int, region: str) -> None:
        self.columns.pop()
        self.used_columns.remove(col)
        self.used_regions.remove(region)

    def is_still_open(self, cell: Cell) -> bool:
        """Could a later row still put a cat in this cell?"""
        row, col = cell
        next_row = len(self.columns)
        if row < next_row or col in self.used_columns:
            return False
        return row > next_row or abs(col - self.columns[-1]) > 1


def _search(puzzle: Puzzle, placement: _Placement) -> Iterator[Solution]:
    row = len(placement.columns)
    if row == puzzle.size:
        yield Solution(tuple(placement.columns))
        return
    for col in range(puzzle.size):
        region = puzzle.region_of((row, col))
        if placement.can_place(col, region):
            placement.place(col, region)
            if _every_region_can_still_fit(puzzle, placement):
                yield from _search(puzzle, placement)
            placement.remove(col, region)


def _every_region_can_still_fit(puzzle: Puzzle, placement: _Placement) -> bool:
    """Pruning: give up early if a region without a cat has no open cell left."""
    return all(
        any(placement.is_still_open(cell) for cell in cells)
        for label, cells in puzzle.region_cells.items()
        if label not in placement.used_regions
    )
