"""Shared test helpers: random puzzles, board transforms, and import checks."""

import ast
import random
import string
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

from meowdoku.deduce import Deduction
from meowdoku.puzzle import Cell, Puzzle
from meowdoku.state import BoardState, Mark

LABELS = string.ascii_uppercase

CellTransform = Callable[[Cell, int], Cell]


def orthogonal_neighbors(cell: Cell) -> list[Cell]:
    row, col = cell
    return [(row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)]


def random_puzzle(rng: random.Random, size: int) -> Puzzle:
    """A random valid puzzle: `size` connected regions grown from random seed cells."""
    cells = [(row, col) for row in range(size) for col in range(size)]
    labels = {cell: LABELS[index] for index, cell in enumerate(rng.sample(cells, size))}
    while len(labels) < len(cells):
        frontier = [
            cell
            for cell in cells
            if cell not in labels and any(n in labels for n in orthogonal_neighbors(cell))
        ]
        cell = rng.choice(frontier)
        grown_from = rng.choice([n for n in orthogonal_neighbors(cell) if n in labels])
        labels[cell] = labels[grown_from]
    return Puzzle.from_rows(
        ["".join(labels[(row, col)] for col in range(size)) for row in range(size)]
    )


def row_stripes(size: int) -> Puzzle:
    """Each row is its own region, so the region rule adds nothing."""
    return Puzzle.from_rows([LABELS[row] * size for row in range(size)])


def column_stripes(size: int) -> Puzzle:
    """Each column is its own region, so the region rule adds nothing."""
    return Puzzle.from_rows([LABELS[:size]] * size)


# Board symmetries. Each maps a cell on an n×n board to its new position.


def rotate(cell: Cell, n: int) -> Cell:
    row, col = cell
    return (col, n - 1 - row)


def mirror(cell: Cell, n: int) -> Cell:
    row, col = cell
    return (row, n - 1 - col)


def flip(cell: Cell, n: int) -> Cell:
    row, col = cell
    return (n - 1 - row, col)


def transpose(cell: Cell, n: int) -> Cell:
    row, col = cell
    return (col, row)


def transform_puzzle(puzzle: Puzzle, transform: CellTransform) -> Puzzle:
    n = puzzle.size
    grid = [[""] * n for _ in range(n)]
    for cell in puzzle.cells():
        row, col = transform(cell, n)
        grid[row][col] = puzzle.region_of(cell)
    return Puzzle.from_rows(["".join(row) for row in grid])


def relabel_puzzle(puzzle: Puzzle, mapping: dict[str, str]) -> Puzzle:
    return Puzzle.from_rows(
        ["".join(mapping[label] for label in row) for row in puzzle.regions]
    )


def imported_modules(module: ModuleType) -> set[str]:
    """Names of all modules imported by a module's source file."""
    tree = ast.parse(Path(str(module.__file__)).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def apply_deduction(state: BoardState, deduction: Deduction) -> BoardState:
    """Make the marks a deduction allows. Only tests do this; the GUI never does (R8.5)."""
    if deduction.place_cat is not None:
        return state.with_mark(deduction.place_cat, Mark.CAT)
    return state.with_crosses(deduction.cross_out)
