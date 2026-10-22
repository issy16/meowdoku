"""GUI layout helpers, plus a smoke test of the real window when a display is available."""

import tkinter as tk
from collections.abc import Iterator

import pytest

import meowdoku.gui
from meowdoku.game import GameSession
from meowdoku.gui import MARGIN, MeowdokuApp, cell_at, cell_pixels, region_boundaries
from meowdoku.puzzle import Puzzle
from meowdoku.state import Mark

from helpers import imported_modules


def test_cell_size_stays_in_range() -> None:
    assert cell_pixels(1) == meowdoku.gui.MAX_CELL_PIXELS
    assert cell_pixels(16) == meowdoku.gui.BOARD_PIXELS // 16
    assert cell_pixels(100) == meowdoku.gui.MIN_CELL_PIXELS


def test_r8_2_boundaries_only_between_different_regions() -> None:
    puzzle = Puzzle.from_rows(["AB", "AB"])
    assert region_boundaries(puzzle) == [((1, 0), (1, 1)), ((1, 1), (1, 2))]


def test_r8_2_no_inner_boundaries_inside_one_region() -> None:
    assert region_boundaries(Puzzle.from_rows(["A"])) == []


def test_r8_2_boundary_count_on_example() -> None:
    puzzle = Puzzle.from_rows(["AABBB", "ACCCB", "ACDDB", "EEDDB", "EEEBB"])
    edges = region_boundaries(puzzle)
    assert len(edges) == len(set(edges))
    # Each segment separates two cells of different regions, so count those pairs by hand.
    different_neighbors = sum(
        1
        for row, col in puzzle.cells()
        for other in ((row, col + 1), (row + 1, col))
        if puzzle.in_bounds(other) and puzzle.region_of(other) != puzzle.region_of((row, col))
    )
    assert len(edges) == different_neighbors


@pytest.mark.parametrize(
    ("x", "y", "expected"),
    [
        (MARGIN, MARGIN, (0, 0)),
        (MARGIN + 39, MARGIN + 40, (1, 0)),
        (MARGIN + 199, MARGIN + 199, (4, 4)),
        (MARGIN + 200, MARGIN, None),
        (MARGIN - 1, MARGIN + 5, None),
    ],
)
def test_cell_at_maps_pixels_to_cells(x: int, y: int, expected: tuple[int, int] | None) -> None:
    assert cell_at(x, y, cell_size=40, board_size=5) == expected


def test_r8_7_gui_holds_no_game_logic() -> None:
    """The GUI talks to GameSession, not to the solver, rules, or hints directly."""
    imported = imported_modules(meowdoku.gui)
    assert not imported & {"meowdoku.solver", "meowdoku.rules", "meowdoku.hints", "meowdoku.deduce"}


# Smoke test with a real (hidden) window


@pytest.fixture
def root() -> Iterator[tk.Tk]:
    try:
        window = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available")
    window.withdraw()
    yield window
    window.destroy()


class FakeClick:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


def test_window_draws_board_and_handles_clicks(root: tk.Tk) -> None:
    session = GameSession.from_text("AABBB\nACCCB\nACDDB\nEEDDB\nEEEBB")
    app = MeowdokuApp(root, session)
    assert len(app.canvas.find_all()) > 25

    size = cell_pixels(5)
    app._on_click(FakeClick(MARGIN + size // 2, MARGIN + size // 2))  # type: ignore[arg-type]
    assert app.session.state.mark_at((0, 0)) is Mark.CROSS

    app._run(app.session.hint)
    assert app.message.cget("text") == app.session.message != ""
