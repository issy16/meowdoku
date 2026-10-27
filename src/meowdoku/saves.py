"""Saved games: a board and its marks as plain data, to keep and open again (R11.7a, R11.8).

A save holds the format version, the puzzle as a text grid (R3), each
region's color, and the cats and ✕ marks. Undo history, hints, and the
solution are not saved. Opening a save checks everything, so a damaged or
unknown save raises SaveError instead of starting a broken game.
"""

import re
from collections.abc import Iterable, Mapping
from typing import Any

from meowdoku.game import GameSession
from meowdoku.messages import DEFAULT_LANGUAGE, Message
from meowdoku.parser import parse_puzzle
from meowdoku.puzzle import Cell, MeowdokuError
from meowdoku.state import BoardState

SAVE_VERSION = 1
_COLOR = re.compile(r"#[0-9a-fA-F]{6}")


class SaveError(MeowdokuError):
    """A save that can't be opened: damaged, edited, or from an unknown version."""

    def __init__(self, reason: str) -> None:
        self.reason = reason  # for tests and debugging; players see the Message
        super().__init__(Message("err.save_unreadable"))


def to_save(session: GameSession) -> dict[str, Any]:
    """The session's puzzle and marks as JSON-ready data (R11.8)."""
    state = session.state
    return {
        "version": SAVE_VERSION,
        "grid": "\n".join("".join(row) for row in session.puzzle.regions),
        "colors": dict(session.colors),
        "cats": _cells_out(state.cats),
        "crosses": _cells_out(state.crosses),
    }


def from_save(data: object, language: str = DEFAULT_LANGUAGE) -> GameSession:
    """A new session from a save, with its marks; raises SaveError if anything is wrong (R11.8)."""
    if not isinstance(data, Mapping):
        raise SaveError("not an object")
    if data.get("version") != SAVE_VERSION:
        raise SaveError(f"unknown version {data.get('version')!r}")
    grid = data.get("grid")
    if not isinstance(grid, str):
        raise SaveError("no grid")
    try:
        puzzle = parse_puzzle(grid)
    except MeowdokuError as error:
        raise SaveError(f"bad grid: {error}") from None
    colors = data.get("colors")
    if (
        not isinstance(colors, Mapping)
        or set(colors) != set(puzzle.region_labels)
        or not all(isinstance(color, str) and _COLOR.fullmatch(color) for color in colors.values())
    ):
        raise SaveError("colors don't match the regions")
    try:
        state = BoardState(puzzle.size, _cells_in(data.get("cats")), _cells_in(data.get("crosses")))
    except ValueError as error:
        raise SaveError(f"bad marks: {error}") from None
    session = GameSession(puzzle, dict(colors), language)
    session.state = state
    return session


def _cells_out(cells: Iterable[Cell]) -> list[list[int]]:
    return [[row, col] for row, col in sorted(cells)]


def _cells_in(cells: object) -> frozenset[Cell]:
    if not isinstance(cells, list) or not all(
        isinstance(cell, list) and len(cell) == 2 and all(type(n) is int for n in cell) for cell in cells
    ):
        raise ValueError("marks must be [row, column] pairs")
    return frozenset((row, col) for row, col in cells)
