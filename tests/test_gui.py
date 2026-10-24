"""GUI layout helpers, plus a smoke test of the real window when a display is available."""

import tkinter as tk
from collections.abc import Iterator

import pytest

import meowdoku.gui
from meowdoku.game import GameSession
from meowdoku.gui import (
    BOARD_INSET,
    MeowdokuApp,
    cell_at,
    cell_pixels,
    cells_between,
    rounded_rect_points,
    tile_gap,
)
from meowdoku.state import BoardState, Mark

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


def at_cell(app: MeowdokuApp, cell: tuple[int, int]) -> FakeClick:
    """A mouse event in the middle of a cell."""
    size = cell_pixels(app.session.puzzle.size)
    row, col = cell
    return FakeClick(BOARD_INSET + col * size + size // 2, BOARD_INSET + row * size + size // 2)


def click(app: MeowdokuApp, cell: tuple[int, int]) -> None:
    app._on_press(at_cell(app, cell))  # type: ignore[arg-type]
    app._on_release(at_cell(app, cell))  # type: ignore[arg-type]


def double_click(app: MeowdokuApp, cell: tuple[int, int]) -> None:
    """The events Tk sends: press, release, double-click (for the second press), release."""
    click(app, cell)
    app._on_double_click(at_cell(app, cell))  # type: ignore[arg-type]
    app._on_release(at_cell(app, cell))  # type: ignore[arg-type]


def drag(app: MeowdokuApp, *cells: tuple[int, int]) -> None:
    """Press on the first cell, move through the others, release on the last."""
    app._on_press(at_cell(app, cells[0]))  # type: ignore[arg-type]
    for cell in cells[1:]:
        app._on_drag(at_cell(app, cell))  # type: ignore[arg-type]
    app._on_release(at_cell(app, cells[-1]))  # type: ignore[arg-type]


def test_window_draws_board_and_handles_clicks(root: tk.Tk) -> None:
    session = GameSession.from_text("AABBB\nACCCB\nACDDB\nEEDDB\nEEEBB")
    app = MeowdokuApp(root, session)
    assert len(app.canvas.find_all()) > 25

    click(app, (0, 0))
    assert app.session.state.mark_at((0, 0)) is Mark.CROSS

    app._run(app.session.hint)
    assert app.message_text().startswith(app.session.message)
    assert app.session.message != ""


def test_r8_9_wrong_cat_shakes_its_cell_and_settles(root: tk.Tk) -> None:
    session = GameSession.from_text("AABBB\nACCCB\nACDDB\nEEDDB\nEEEBB")
    app = MeowdokuApp(root, session)
    double_click(app, (0, 0))  # a wrong cat
    shaking = app.canvas.find_withtag("shaking")
    assert shaking
    start = [app.canvas.coords(item) for item in shaking]
    root.after(meowdoku.gui.SHAKE_STEP_MS + 5, root.quit)
    root.mainloop()
    assert [app.canvas.coords(item) for item in shaking] != start  # moved
    root.after(meowdoku.gui.SHAKE_STEP_MS * 8, root.quit)
    root.mainloop()
    assert [app.canvas.coords(item) for item in shaking] == start  # back in place
    assert not app.canvas.find_withtag("shaking")


def test_r8_6_solving_shows_a_pop_up(root: tk.Tk) -> None:
    session = GameSession.from_text("AABBB\nACCCB\nACDDB\nEEDDB\nEEEBB")
    app = MeowdokuApp(root, session)
    for cell in [(0, 4), (1, 2), (2, 0), (3, 3), (4, 1)]:
        double_click(app, cell)
    assert not app.popup  # it waits a moment, so the last cat shows first
    wait(root, meowdoku.gui.POPUP_DELAY_MS + 100)
    assert app.popup
    items = app.canvas.find_withtag(meowdoku.gui.POPUP_TAG)
    texts = [app.canvas.itemcget(item, "text") for item in items if app.canvas.type(item) == "text"]
    assert texts == [meowdoku.gui.SOLVED_TITLE, meowdoku.gui.SOLVED_POPUP, "OK"]
    assert not any(app.canvas.type(item) == "image" for item in items)  # no icon
    assert app.message_text() == ""  # no "Solved!" line under the board


def wait(root: tk.Tk, ms: int) -> None:
    """Let Tk run its timers for a while (a full update() can hang on macOS)."""
    root.after(ms, root.quit)
    root.mainloop()


def test_r8_6_a_click_closes_the_pop_up_and_leaves_the_board(root: tk.Tk) -> None:
    app = MeowdokuApp(root, GameSession.from_text("AABBB\nACCCB\nACDDB\nEEDDB\nEEEBB"))
    app._celebrate()
    marks = app.session.state
    click(app, (4, 4))
    assert not app.popup
    assert not app.canvas.find_withtag(meowdoku.gui.POPUP_TAG)
    assert app.session.state == marks
    app._celebrate()
    app._run(app.session.reset)  # the next action closes it too
    assert not app.popup


def test_r8_8_an_error_dialog_that_cannot_open_is_printed_instead(
    root: tk.Tk, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def refuse(*args: object, **options: object) -> None:
        raise tk.TclError("NSAlert runModal cannot run inside a transaction")

    monkeypatch.setattr(meowdoku.gui.messagebox, "showerror", refuse)
    app = MeowdokuApp(root, GameSession.from_text("AABBB\nACCCB\nACDDB\nEEDDB\nEEEBB"))
    app._report_error(ValueError, ValueError("boom"), None)  # must not raise
    assert "something went wrong: ValueError: boom" in capsys.readouterr().err


# R8.10 Dragging marks or unmarks


def test_r8_10_cells_between_fills_skipped_cells() -> None:
    assert cells_between((0, 0), (0, 3)) == [(0, 0), (0, 1), (0, 2), (0, 3)]
    assert cells_between((2, 2), (0, 0)) == [(2, 2), (1, 1), (0, 0)]
    assert cells_between((1, 1), (1, 1)) == [(1, 1)]


def test_r8_10_drag_from_an_empty_cell_marks(root: tk.Tk) -> None:
    app = MeowdokuApp(root, GameSession.from_text("AABBB\nACCCB\nACDDB\nEEDDB\nEEEBB"))
    drag(app, (3, 0), (3, 3))  # one jump: the cells in between are filled in
    assert app.session.state.crosses == {(3, 0), (3, 1), (3, 2), (3, 3)}


def test_r8_10_drag_from_a_cross_unmarks(root: tk.Tk) -> None:
    app = MeowdokuApp(root, GameSession.from_text("AABBB\nACCCB\nACDDB\nEEDDB\nEEEBB"))
    drag(app, (3, 0), (3, 3))
    drag(app, (3, 3), (3, 1))
    assert app.session.state.crosses == {(3, 0)}


def test_r8_10_moving_within_one_cell_is_still_a_click(root: tk.Tk) -> None:
    app = MeowdokuApp(root, GameSession.from_text("AABBB\nACCCB\nACDDB\nEEDDB\nEEEBB"))
    drag(app, (2, 2), (2, 2))
    assert app.session.state.crosses == {(2, 2)}


def test_r8_4_click_uncrosses_and_double_click_places_a_cat(root: tk.Tk) -> None:
    app = MeowdokuApp(root, GameSession.from_text("AABBB\nACCCB\nACDDB\nEEDDB\nEEEBB"))
    click(app, (3, 4))
    click(app, (3, 4))
    assert app.session.state.is_open((3, 4))
    double_click(app, (1, 2))  # a correct cat, from an empty cell
    assert app.session.state.mark_at((1, 2)) is Mark.CAT
    assert app.session.is_locked((1, 2))


def test_r8_11_apply_link_follows_a_hint_and_applies_it(root: tk.Tk) -> None:
    app = MeowdokuApp(root, GameSession.from_text("AABBB\nACCCB\nACDDB\nEEDDB\nEEEBB"))
    app._run(app.session.hint)
    assert app.message_text() == app.session.message + " " + meowdoku.gui.APPLY_TEXT
    start, end = app.message.tag_ranges(meowdoku.gui.APPLY_TAG)
    assert app.message.get(start, end) == meowdoku.gui.APPLY_TEXT
    app.message.event_generate("<Button-1>", x=1, y=1)  # outside the link: nothing happens
    assert app.session.hint_shown
    app._run(app.session.apply_hint)  # what clicking the link does
    assert app.session.state.crosses == {(0, 2), (0, 3), (4, 3)}
    assert meowdoku.gui.APPLY_TEXT not in app.message_text()


def test_r8_11_no_link_without_an_applicable_hint(root: tk.Tk) -> None:
    """A hint about a mistake has nothing to apply."""
    session = GameSession.from_text("AABBB\nACCCB\nACDDB\nEEDDB\nEEEBB")
    session.state = BoardState(5, cats=frozenset({(0, 0)}))
    app = MeowdokuApp(root, session)
    app._run(app.session.hint)
    assert meowdoku.gui.APPLY_TEXT not in app.message_text()


def test_r8_12_step_button_reads_next_while_stepping(root: tk.Tk) -> None:
    app = MeowdokuApp(root, GameSession.from_text("AABBB\nACCCB\nACDDB\nEEDDB\nEEEBB"))
    assert app.step_button.cget("text") == meowdoku.gui.STEP_LABEL
    app._run(app.session.step)
    assert app.step_button.cget("text") == meowdoku.gui.NEXT_LABEL
    assert meowdoku.gui.APPLY_TEXT not in app.message_text()  # Next does the applying
    click(app, (4, 4))
    assert app.step_button.cget("text") == meowdoku.gui.STEP_LABEL


def test_r8_13_previous_and_next_buttons_follow_the_history(root: tk.Tk) -> None:
    app = MeowdokuApp(root, GameSession.from_text("AABBB\nACCCB\nACDDB\nEEDDB\nEEEBB"))
    assert str(app.undo_button.cget("state")) == "disabled"
    assert str(app.redo_button.cget("state")) == "disabled"
    click(app, (0, 0))
    assert str(app.undo_button.cget("state")) == "normal"
    app.undo_button.invoke()
    assert app.session.state.is_open((0, 0))
    assert str(app.undo_button.cget("state")) == "disabled"
    assert str(app.redo_button.cget("state")) == "normal"
    app.redo_button.invoke()
    assert app.session.state.mark_at((0, 0)) is Mark.CROSS
