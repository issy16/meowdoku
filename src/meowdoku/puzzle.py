"""Puzzle representation, structural validation, and error types."""

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from functools import cached_property
from types import MappingProxyType
from typing import Self

from meowdoku.messages import DEFAULT_LANGUAGE, Count, Message, Region, render

Cell = tuple[int, int]
"""A board position as (row, col), 0-indexed."""

MIN_SIZE = 1
MAX_SIZE = 16


class MeowdokuError(Exception):
    """Base class for all user-facing errors.

    Raised with a Message, the error can be worded in any language (R12.1).
    """

    def text(self, language: str = DEFAULT_LANGUAGE) -> str:
        return render(self.args[0], language) if self.args else ""


class PuzzleFormatError(MeowdokuError):
    """The puzzle text is malformed (R4.1-R4.3)."""

    def __init__(self, reason: str, line: int | None = None) -> None:
        self.reason = reason
        self.line = line
        message = reason if line is None else f"line {line}: {reason}"
        super().__init__(message)


class PuzzleValidationError(MeowdokuError):
    """The puzzle grid breaks one or more structural rules (R4.4-R4.6)."""

    def __init__(self, problems: Sequence[str]) -> None:
        self.problems = tuple(problems)
        super().__init__(self.text())

    def text(self, language: str = DEFAULT_LANGUAGE) -> str:
        details = "\n".join(f"  - {render(problem, language)}" for problem in self.problems)
        return f"{render(Message('err.invalid'), language)}\n{details}"


def describe_cell(cell: Cell) -> Message:
    """Describe a cell for users, 1-indexed (R6.4)."""
    row, col = cell
    return Message("cell", row=row + 1, column=col + 1)


def count_of(count: int, noun: str) -> str:
    """Format a count with a singular or plural noun, e.g. '1 cell', '2 cells'."""
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


@dataclass(frozen=True)
class Puzzle:
    """An N×N board where regions[row][col] is the region label of that cell.

    Construction validates the structure, so an invalid Puzzle cannot exist (R4.7).
    """

    size: int
    regions: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        problems = find_structure_problems(self.size, self.regions)
        if problems:
            raise PuzzleValidationError(problems)

    @classmethod
    def from_rows(cls, rows: Sequence[str]) -> Self:
        """Build a puzzle from one string per row, one character per cell."""
        return cls(size=len(rows), regions=tuple(tuple(row) for row in rows))

    def in_bounds(self, cell: Cell) -> bool:
        row, col = cell
        return 0 <= row < self.size and 0 <= col < self.size

    def cells(self) -> Iterator[Cell]:
        """Yield every cell in row-major order."""
        for row in range(self.size):
            for col in range(self.size):
                yield (row, col)

    def region_of(self, cell: Cell) -> str:
        if not self.in_bounds(cell):
            raise ValueError(f"cell {cell} is outside the {self.size}x{self.size} board")
        row, col = cell
        return self.regions[row][col]

    @cached_property
    def region_cells(self) -> Mapping[str, frozenset[Cell]]:
        """Cells of each region, keyed in order of first appearance (row-major)."""
        return MappingProxyType(group_cells_by_label(self.regions))

    @cached_property
    def region_labels(self) -> tuple[str, ...]:
        """Region labels in order of first appearance (row-major)."""
        return tuple(self.region_cells)


def group_cells_by_label(regions: Sequence[Sequence[str]]) -> dict[str, frozenset[Cell]]:
    """Group cells by region label, keyed in order of first appearance."""
    groups: dict[str, set[Cell]] = {}
    for row, labels in enumerate(regions):
        for col, label in enumerate(labels):
            groups.setdefault(label, set()).add((row, col))
    return {label: frozenset(cells) for label, cells in groups.items()}


def find_structure_problems(size: int, regions: Sequence[Sequence[str]]) -> list[str]:
    """Return every structural problem with a puzzle grid; empty means valid.

    Checks run in stages because later checks only make sense once earlier
    ones pass: size, then grid shape and labels, then regions.
    """
    size_problems = _size_problems(size)
    if size_problems:
        return size_problems
    shape_problems = _shape_problems(size, regions)
    if shape_problems:
        return shape_problems
    return _region_count_problems(size, regions) + _connectivity_problems(regions)


def _size_problems(size: int) -> list[str]:
    if not MIN_SIZE <= size <= MAX_SIZE:
        return [Message("err.board_size", size=size, min=MIN_SIZE, max=MAX_SIZE)]
    return []


def _shape_problems(size: int, regions: Sequence[Sequence[str]]) -> list[str]:
    problems = []
    if len(regions) != size:
        problems.append(f"expected {count_of(size, 'row')}, found {len(regions)}")
    for row, labels in enumerate(regions):
        if len(labels) != size:
            problems.append(f"row {row + 1} has {count_of(len(labels), 'cell')}; expected {size}")
        for col, label in enumerate(labels):
            if not _is_valid_label(label):
                problems.append(
                    f"{describe_cell((row, col))} has invalid region label {label!r}; "
                    "labels must be single non-whitespace characters"
                )
    return problems


def _is_valid_label(label: object) -> bool:
    return isinstance(label, str) and len(label) == 1 and not label.isspace()


def _region_count_problems(size: int, regions: Sequence[Sequence[str]]) -> list[str]:
    labels = list(group_cells_by_label(regions))
    if len(labels) != size:
        return [Message("err.region_count", regions=Count(len(labels), "region"), labels=", ".join(labels), size=size)]
    return []


def _connectivity_problems(regions: Sequence[Sequence[str]]) -> list[str]:
    problems = []
    for label, cells in group_cells_by_label(regions).items():
        parts = connected_parts(cells)
        if len(parts) > 1:
            problems.append(Message("err.split", region=Region(label), parts=len(parts), starts=_joined(parts)))
    return problems


def _joined(parts: Sequence[frozenset[Cell]]) -> Message:
    """Where each part starts: "row 1, column 1 and row 3, column 2"."""
    starts = [describe_cell(min(part)) for part in parts]
    joined = starts[0]
    for start in starts[1:]:
        joined = Message("err.and", first=joined, second=start)
    return joined


def connected_parts(cells: frozenset[Cell]) -> list[frozenset[Cell]]:
    """Split cells into orthogonally connected parts, ordered by their first cell."""
    remaining = set(cells)
    parts = []
    while remaining:
        part = _flood_fill(min(remaining), remaining)
        remaining -= part
        parts.append(part)
    return parts


def _flood_fill(start: Cell, allowed: set[Cell]) -> frozenset[Cell]:
    """Return all cells in `allowed` reachable from `start` by orthogonal steps."""
    seen = {start}
    stack = [start]
    while stack:
        row, col = stack.pop()
        for neighbor in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
            if neighbor in allowed and neighbor not in seen:
                seen.add(neighbor)
                stack.append(neighbor)
    return frozenset(seen)
