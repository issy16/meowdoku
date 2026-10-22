"""Tkinter window: a colored Meowdoku board with Open, Hint, Check, Solve, Reset (R8).

Run with `python -m meowdoku.gui [SCREENSHOT]`. This module only draws and
handles events; all game logic lives in game.py (R8.7).
"""

import argparse
import tkinter as tk
from collections.abc import Callable, Sequence
from pathlib import Path
from tkinter import filedialog, messagebox
from types import TracebackType

from meowdoku.game import EXAMPLE_PUZZLE, GameSession, Highlight
from meowdoku.puzzle import Cell, MeowdokuError, Puzzle

BOARD_PIXELS = 520
MIN_CELL_PIXELS = 28
MAX_CELL_PIXELS = 72
MARGIN = 10

THIN_LINE = ("#9a9a9a", 1)
THICK_LINE = ("#2b2b2b", 3)
MARK_COLOR = "#2b2b2b"
REVEALED_COLOR = "#8a8a8a"
EYE_COLOR = "#ffffff"
HIGHLIGHT_COLORS = {Highlight.HINT: "#f5a700", Highlight.PROBLEM: "#d62828"}
SOLVED_TEXT_COLOR = "#2e7d32"
MESSAGE_FONT = ("Helvetica", 14)

GridPoint = tuple[int, int]
"""A corner of the grid as (x, y) = (column, row)."""

Segment = tuple[GridPoint, GridPoint]


# Pure layout helpers (testable without a display)


def cell_pixels(size: int) -> int:
    """Cell size in pixels so the board is about BOARD_PIXELS wide."""
    return max(MIN_CELL_PIXELS, min(MAX_CELL_PIXELS, BOARD_PIXELS // size))


def region_boundaries(puzzle: Puzzle) -> list[Segment]:
    """Edges between neighboring cells of different regions, drawn thick (R8.2)."""
    segments = []
    for row, col in puzzle.cells():
        region = puzzle.region_of((row, col))
        if col + 1 < puzzle.size and puzzle.region_of((row, col + 1)) != region:
            segments.append(((col + 1, row), (col + 1, row + 1)))
        if row + 1 < puzzle.size and puzzle.region_of((row + 1, col)) != region:
            segments.append(((col, row + 1), (col + 1, row + 1)))
    return segments


def cell_at(x: int, y: int, cell_size: int, board_size: int) -> Cell | None:
    """The cell under a canvas point, or None outside the board."""
    if x < MARGIN or y < MARGIN:
        return None
    row, col = (y - MARGIN) // cell_size, (x - MARGIN) // cell_size
    if row < board_size and col < board_size:
        return (row, col)
    return None


# The window


class MeowdokuApp:
    def __init__(self, root: tk.Tk, session: GameSession) -> None:
        self.root = root
        self.session = session
        root.title("Meowdoku")
        root.resizable(False, False)
        root.report_callback_exception = self._report_error  # type: ignore[assignment]

        toolbar = tk.Frame(root, padx=MARGIN, pady=MARGIN)
        toolbar.pack(fill="x")
        for label, command in (
            ("Open…", self.open_file),
            ("Hint", lambda: self._run(self.session.hint)),
            ("Check", lambda: self._run(self.session.check)),
            ("Solve", lambda: self._run(self.session.solve)),
            ("Reset", lambda: self._run(self.session.reset)),
        ):
            tk.Button(toolbar, text=label, command=command).pack(side="left", padx=(0, 6))

        self.canvas = tk.Canvas(root, highlightthickness=0, background="white")
        self.canvas.pack(padx=MARGIN)
        self.canvas.bind("<Button-1>", self._on_click)

        self.message = tk.Label(
            root, font=MESSAGE_FONT, justify="left", anchor="w", padx=MARGIN, pady=MARGIN
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

    def _corner(self, point: GridPoint) -> tuple[int, int]:
        x, y = point
        return (MARGIN + x * self._cell_size, MARGIN + y * self._cell_size)

    def _cell_box(self, cell: Cell, inset: float = 0) -> tuple[float, float, float, float]:
        row, col = cell
        x0, y0 = self._corner((col, row))
        size = self._cell_size
        return (x0 + inset, y0 + inset, x0 + size - inset, y0 + size - inset)

    def redraw(self) -> None:
        puzzle = self.session.puzzle
        board = puzzle.size * self._cell_size
        self.canvas.configure(width=board + 2 * MARGIN, height=board + 2 * MARGIN)
        self.canvas.delete("all")
        self._draw_cells()
        self._draw_grid_lines()
        self._draw_highlights()
        self._draw_marks()
        self.message.configure(
            text=self.session.message,
            foreground=SOLVED_TEXT_COLOR if self.session.is_solved else "black",
            wraplength=board,
        )

    def _draw_cells(self) -> None:
        for cell in self.session.puzzle.cells():
            color = self.session.colors[self.session.puzzle.region_of(cell)]
            self.canvas.create_rectangle(*self._cell_box(cell), fill=color, width=0)

    def _draw_grid_lines(self) -> None:
        n = self.session.puzzle.size
        color, width = THIN_LINE
        for i in range(1, n):
            self.canvas.create_line(*self._corner((i, 0)), *self._corner((i, n)), fill=color, width=width)
            self.canvas.create_line(*self._corner((0, i)), *self._corner((n, i)), fill=color, width=width)
        color, width = THICK_LINE
        for start, end in region_boundaries(self.session.puzzle):
            self.canvas.create_line(
                *self._corner(start), *self._corner(end), fill=color, width=width, capstyle="projecting"
            )
        self.canvas.create_rectangle(*self._corner((0, 0)), *self._corner((n, n)), outline=color, width=width)

    def _draw_highlights(self) -> None:
        style = self.session.highlight_style
        if style is None:
            return
        for cell in self.session.highlight:
            self.canvas.create_rectangle(
                *self._cell_box(cell, inset=3), outline=HIGHLIGHT_COLORS[style], width=3
            )

    def _draw_marks(self) -> None:
        state = self.session.state
        for cell in state.crosses:
            self._draw_cross(cell)
        for cell in state.cats:
            self._draw_cat(cell, MARK_COLOR)
        for cell in self.session.revealed - state.cats:
            self._draw_cat(cell, REVEALED_COLOR)

    def _draw_cross(self, cell: Cell) -> None:
        x0, y0, x1, y1 = self._cell_box(cell, inset=self._cell_size * 0.32)
        for line in ((x0, y0, x1, y1), (x0, y1, x1, y0)):
            self.canvas.create_line(*line, fill=MARK_COLOR, width=3, capstyle="round")

    def _draw_cat(self, cell: Cell, color: str) -> None:
        """A simple cat face: round head, two pointed ears, two eyes."""
        x0, y0, _, _ = self._cell_box(cell)
        s = self._cell_size

        def at(fx: float, fy: float) -> tuple[float, float]:
            return (x0 + fx * s, y0 + fy * s)

        self.canvas.create_polygon(*at(0.24, 0.50), *at(0.27, 0.16), *at(0.47, 0.34), fill=color)
        self.canvas.create_polygon(*at(0.76, 0.50), *at(0.73, 0.16), *at(0.53, 0.34), fill=color)
        self.canvas.create_oval(*at(0.22, 0.28), *at(0.78, 0.82), fill=color, width=0)
        self.canvas.create_oval(*at(0.36, 0.46), *at(0.44, 0.56), fill=EYE_COLOR, width=0)
        self.canvas.create_oval(*at(0.56, 0.46), *at(0.64, 0.56), fill=EYE_COLOR, width=0)


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
