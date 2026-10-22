"""The player's progress: which cells hold a cat or a ✕ mark (R7.1)."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from typing import Self

from meowdoku.puzzle import Cell


class Mark(Enum):
    CAT = "cat"
    CROSS = "cross"


@dataclass(frozen=True)
class BoardState:
    """Marks on an N×N board. Unmarked cells are open. Changes return a new state."""

    size: int
    cats: frozenset[Cell] = field(default_factory=frozenset)
    crosses: frozenset[Cell] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        outside = sorted(cell for cell in self.cats | self.crosses if not self._in_bounds(cell))
        if outside:
            raise ValueError(f"cells {outside} are outside the {self.size}x{self.size} board")
        both = sorted(self.cats & self.crosses)
        if both:
            raise ValueError(f"cells {both} are marked as both cat and cross")

    @classmethod
    def empty(cls, size: int) -> Self:
        return cls(size)

    def _in_bounds(self, cell: Cell) -> bool:
        row, col = cell
        return 0 <= row < self.size and 0 <= col < self.size

    def mark_at(self, cell: Cell) -> Mark | None:
        if cell in self.cats:
            return Mark.CAT
        if cell in self.crosses:
            return Mark.CROSS
        return None

    def is_open(self, cell: Cell) -> bool:
        return cell not in self.cats and cell not in self.crosses

    def with_mark(self, cell: Cell, mark: Mark | None) -> Self:
        """Return a new state with `cell` set to `mark`; None clears it."""
        cats = self.cats - {cell}
        crosses = self.crosses - {cell}
        if mark is Mark.CAT:
            cats |= {cell}
        elif mark is Mark.CROSS:
            crosses |= {cell}
        return type(self)(self.size, cats, crosses)

    def with_crosses(self, cells: Iterable[Cell]) -> Self:
        """Return a new state with every given cell marked ✕."""
        cells = frozenset(cells)
        return type(self)(self.size, self.cats - cells, self.crosses | cells)
