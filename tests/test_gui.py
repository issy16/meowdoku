"""GUI layout helpers, plus a smoke test of the real window when a display is available."""

import tkinter as tk
from collections.abc import Iterator

import pytest

import meowdoku.gui
from meowdoku.game import GameSession
from meowdoku.gui import BOARD_INSET, MeowdokuApp, cell_at, cell_pixels, rounded_rect_points, tile_gap
from meowdoku.state import Mark

from helpers import imported_modules


def test_cell_size_stays_in_range() -> None:
    assert cell_pixels(1) == meowdoku.gui.MAX_CELL_PIXELS
    assert cell_pixels(16) == meowdoku.gui.BOARD_PIXELS // 16
    assert cell_pixels(100) == meowdoku.gui.MIN_CELL_PIXELS


def test_r8_2_tiles_have_a_gap_like_the_game() -> None:
    """The game's gap is about 8% of a cell; tiny cells still get a visible gap."""
    assert tile_gap(72) == 6
    assert tile_gap(28) == 2
    assert tile_gap(10) == 2


def test_r8_2_rounded_rect_stays_inside_its_box() -> None:
    points = rounded_rect_points((10, 20, 50, 80), radius=8)
    xs, ys = points[0::2], points[1::2]
    assert (min(xs), max(xs), min(ys), max(ys)) == (10, 50, 20, 80)
    assert (18, 20) in zip(xs, ys)  # the top edge starts one radius in from the corner


def test_r8_2_rounded_rect_radius_is_capped_at_half_the_shorter_side() -> None:
    points = rounded_rect_points((0, 0, 10, 40), radius=100)
    assert (5, 0) in zip(points[0::2], points[1::2])


@pytest.mark.parametrize(
    ("x", "y", "expected"),
    [
        (BOARD_INSET, BOARD_INSET, (0, 0)),
        (BOARD_INSET + 39, BOARD_INSET + 40, (1, 0)),
        (BOARD_INSET + 199, BOARD_INSET + 199, (4, 4)),
        (BOARD_INSET + 200, BOARD_INSET, None),
        (BOARD_INSET - 1, BOARD_INSET + 5, None),
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
    app._on_click(FakeClick(BOARD_INSET + size // 2, BOARD_INSET + size // 2))  # type: ignore[arg-type]
    assert app.session.state.mark_at((0, 0)) is Mark.CROSS

    app._run(app.session.hint)
    assert app.message.cget("text") == app.session.message != ""
