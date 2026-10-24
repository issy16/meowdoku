"""Tkinter window: a Meowdoku board with Open, Hint, Check, Solve, Reset (R8).

Run with `python -m meowdoku.gui [SCREENSHOT]`. This module only draws and
handles events; all game logic lives in game.py (R8.7).

The board looks like the game's (R8.2, docs/algorithm.md): rounded colored
tiles with white gaps on a white card, on a beige page. Regions are told
apart by tile color only.
"""

import argparse
import tkinter as tk
from collections.abc import Callable, Sequence
from pathlib import Path
from tkinter import filedialog, messagebox
from types import TracebackType

from meowdoku.game import EXAMPLE_PUZZLE, GameSession, Highlight
from meowdoku.puzzle import Cell, MeowdokuError

BOARD_PIXELS = 520
MIN_CELL_PIXELS = 28
MAX_CELL_PIXELS = 72
MARGIN = 10  # page space around the card
CARD_PADDING = 12  # white card space around the tiles
BOARD_INSET = MARGIN + CARD_PADDING  # canvas offset of the first tile
CARD_RADIUS = 16

# Proportions measured on the game (105 px tiles, 9 px gaps, 8 px corners).
GAP_SHARE = 0.08  # white gap between tiles, as a share of a cell
# Tile corner radius, as a share of a cell. Tk's smoothed corners bend less
# than a true arc, so this is about twice the game's radius to look the same.
CORNER_SHARE = 0.16

# Colors sampled from the game's screenshots.
PAGE_COLOR = "#f7f2ef"
CARD_COLOR = "#ffffff"
TEXT_COLOR = "#935a5a"
CROSS_COLOR = "#ffffff"
CAT_FUR = "#262626"
REVEALED_FUR = "#9a9a9a"
CAT_FACE = "#ffffff"
CAT_NOSE = "#f4a3b4"
HIGHLIGHT_COLORS = {Highlight.HINT: "#f5a700", Highlight.PROBLEM: "#d62828"}
SOLVED_TEXT_COLOR = "#2e7d32"
MESSAGE_FONT = ("Helvetica", 14)

Box = tuple[float, float, float, float]
"""A rectangle on the canvas as (left, top, right, bottom)."""


# Pure layout helpers (testable without a display)


def cell_pixels(size: int) -> int:
    """Cell size in pixels so the board is about BOARD_PIXELS wide."""
    return max(MIN_CELL_PIXELS, min(MAX_CELL_PIXELS, BOARD_PIXELS // size))


def tile_gap(cell_size: int) -> int:
    """White space between neighboring tiles, at least 2 pixels."""
    return max(2, round(cell_size * GAP_SHARE))


def cell_at(x: int, y: int, cell_size: int, board_size: int) -> Cell | None:
    """The cell under a canvas point, or None outside the board."""
    if x < BOARD_INSET or y < BOARD_INSET:
        return None
    row, col = (y - BOARD_INSET) // cell_size, (x - BOARD_INSET) // cell_size
    if row < board_size and col < board_size:
        return (row, col)
    return None


def rounded_rect_points(box: Box, radius: float) -> list[float]:
    """Polygon points that tkinter's smooth=True draws as a rounded rectangle.

    The points where each straight edge starts and ends are doubled, so the
    spline runs straight along the edges and bends only around the corner
    points. The radius is capped at half the shorter side.
    """
    x0, y0, x1, y1 = box
    r = max(0.0, min(radius, (x1 - x0) / 2, (y1 - y0) / 2))
    return [
        x0 + r, y0, x0 + r, y0, x1 - r, y0, x1 - r, y0, x1, y0,
        x1, y0 + r, x1, y0 + r, x1, y1 - r, x1, y1 - r, x1, y1,
        x1 - r, y1, x1 - r, y1, x0 + r, y1, x0 + r, y1, x0, y1,
        x0, y1 - r, x0, y1 - r, x0, y0 + r, x0, y0 + r, x0, y0,
    ]  # fmt: skip


# The window


class MeowdokuApp:
    def __init__(self, root: tk.Tk, session: GameSession) -> None:
        self.root = root
        self.session = session
        root.title("Meowdoku")
        root.resizable(False, False)
        root.configure(background=PAGE_COLOR)
        root.report_callback_exception = self._report_error  # type: ignore[assignment]

        toolbar = tk.Frame(root, padx=MARGIN, pady=MARGIN, background=PAGE_COLOR)
        toolbar.pack(fill="x")
        for label, command in (
            ("Open…", self.open_file),
            ("Hint", lambda: self._run(self.session.hint)),
            ("Check", lambda: self._run(self.session.check)),
            ("Solve", lambda: self._run(self.session.solve)),
            ("Reset", lambda: self._run(self.session.reset)),
        ):
            tk.Button(
                toolbar, text=label, command=command, highlightbackground=PAGE_COLOR
            ).pack(side="left", padx=(0, 6))

        self.canvas = tk.Canvas(root, highlightthickness=0, background=PAGE_COLOR)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self._on_click)

        self.message = tk.Label(
            root,
            font=MESSAGE_FONT,
            justify="left",
            anchor="w",
            padx=MARGIN,
            pady=MARGIN,
            background=PAGE_COLOR,
        )
        self.message.pack(fill="x")
        self.redraw()

    # Events

    def open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Open a screenshot",
            filetypes=[("Screenshots", "*.png *.jpg *.jpeg"), ("All files", "*")],
        )
        if not path:
            return
        try:
            self.session = GameSession.from_screenshot(Path(path))
        except (OSError, MeowdokuError) as error:
            messagebox.showerror("Can't open puzzle", str(error))
            return
        self.redraw()

    def _run(self, action: Callable[[], None]) -> None:
        action()
        self.redraw()

    def _on_click(self, event: "tk.Event[tk.Canvas]") -> None:
        cell = cell_at(event.x, event.y, self._cell_size, self.session.puzzle.size)
        if cell is not None:
            self._run(lambda: self.session.click(cell))

    def _report_error(
        self, exc_type: type[BaseException], error: BaseException, tb: TracebackType | None
    ) -> None:
        """Show unexpected errors in a dialog instead of a traceback (R8.8)."""
        messagebox.showerror("Something went wrong", f"{exc_type.__name__}: {error}")

    # Drawing

    @property
    def _cell_size(self) -> int:
        return cell_pixels(self.session.puzzle.size)

    def _cell_box(self, cell: Cell, inset: float = 0) -> Box:
        row, col = cell
        size = self._cell_size
        x0, y0 = BOARD_INSET + col * size, BOARD_INSET + row * size
        return (x0 + inset, y0 + inset, x0 + size - inset, y0 + size - inset)

    def _tile_box(self, cell: Cell) -> Box:
        """The colored tile inside a cell, leaving half the gap on each side."""
        return self._cell_box(cell, inset=tile_gap(self._cell_size) / 2)

    def _rounded_rect(self, box: Box, radius: float, **options: object) -> None:
        self.canvas.create_polygon(rounded_rect_points(box, radius), smooth=True, **options)

    def redraw(self) -> None:
        board = self.session.puzzle.size * self._cell_size
        self.canvas.configure(width=board + 2 * BOARD_INSET, height=board + 2 * BOARD_INSET)
        self.canvas.delete("all")
        self._draw_card(board)
        self._draw_tiles()
        self._draw_highlights()
        self._draw_marks()
        self.message.configure(
            text=self.session.message,
            foreground=SOLVED_TEXT_COLOR if self.session.is_solved else TEXT_COLOR,
            wraplength=board + 2 * CARD_PADDING,
        )

    def _draw_card(self, board: int) -> None:
        far = BOARD_INSET + board + CARD_PADDING
        self._rounded_rect((MARGIN, MARGIN, far, far), CARD_RADIUS, fill=CARD_COLOR)

    def _draw_tiles(self) -> None:
        radius = self._cell_size * CORNER_SHARE
        for cell in self.session.puzzle.cells():
            color = self.session.colors[self.session.puzzle.region_of(cell)]
            self._rounded_rect(self._tile_box(cell), radius, fill=color)

    def _draw_highlights(self) -> None:
        """A colored ring in the white gap around each highlighted tile."""
        style = self.session.highlight_style
        if style is None:
            return
        radius = self._cell_size * CORNER_SHARE + tile_gap(self._cell_size) / 2
        for cell in self.session.highlight:
            self._rounded_rect(
                self._cell_box(cell, inset=1.5), radius, fill="", outline=HIGHLIGHT_COLORS[style], width=3
            )

    def _draw_marks(self) -> None:
        state = self.session.state
        for cell in state.crosses:
            self._draw_cross(cell)
        for cell in state.cats:
            self._draw_cat(cell, CAT_FUR)
        for cell in self.session.revealed - state.cats:
            self._draw_cat(cell, REVEALED_FUR)

    def _draw_cross(self, cell: Cell) -> None:
        """A thick white X, like the game's."""
        x0, y0, x1, y1 = self._tile_box(cell)
        inset = (x1 - x0) * 0.25
        x0, y0, x1, y1 = x0 + inset, y0 + inset, x1 - inset, y1 - inset
        width = max(3, round(self._cell_size * 0.11))
        for line in ((x0, y0, x1, y1), (x0, y1, x1, y0)):
            self.canvas.create_line(*line, fill=CROSS_COLOR, width=width, capstyle="round")

    def _draw_cat(self, cell: Cell, fur: str) -> None:
        """A black and white cat face like the game's: dark head and ears, white muzzle, round eyes."""
        x0, y0, x1, _ = self._tile_box(cell)
        s = x1 - x0

        def at(fx: float, fy: float) -> tuple[float, float]:
            return (x0 + fx * s, y0 + fy * s)

        def ear(side: int, fx: float, fy: float) -> tuple[float, float]:
            """A point of the right ear (side 1), or its mirror image on the left (side -1)."""
            return at(0.5 + side * (fx - 0.5), fy)

        canvas = self.canvas
        for side in (1, -1):
            canvas.create_polygon(*ear(side, 0.88, 0.52), *ear(side, 0.82, 0.06), *ear(side, 0.52, 0.28), fill=fur)
            canvas.create_polygon(
                *ear(side, 0.80, 0.34), *ear(side, 0.79, 0.16), *ear(side, 0.65, 0.27), fill=CAT_NOSE
            )
        canvas.create_oval(*at(0.12, 0.20), *at(0.88, 0.90), fill=fur, width=0)
        canvas.create_oval(*at(0.27, 0.54), *at(0.73, 0.90), fill=CAT_FACE, width=0)
        for cx in (0.35, 0.65):
            canvas.create_oval(*at(cx - 0.075, 0.44), *at(cx + 0.075, 0.59), fill=CAT_FACE, width=0)
            canvas.create_oval(*at(cx - 0.04, 0.48), *at(cx + 0.04, 0.56), fill=fur, width=0)
        canvas.create_oval(*at(0.465, 0.62), *at(0.535, 0.67), fill=CAT_NOSE, width=0)


# Entry point


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m meowdoku.gui", description="Play Meowdoku.")
    parser.add_argument("screenshot", nargs="?", type=Path, help="a .png or .jpg screenshot (optional)")
    args = parser.parse_args(argv)

    root = tk.Tk()
    session = GameSession.from_text(EXAMPLE_PUZZLE)
    if args.screenshot is not None:
        try:
            session = GameSession.from_screenshot(args.screenshot)
        except (OSError, MeowdokuError) as error:
            messagebox.showerror("Can't open puzzle", f"{error}\n\nShowing the example puzzle instead.")
    MeowdokuApp(root, session)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
