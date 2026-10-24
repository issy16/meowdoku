"""Tkinter window: a Meowdoku board with Open, Previous, Next, Hint, Step by Step, Solve, Reset (R8).

Run with `python -m meowdoku.gui [SCREENSHOT]`. This module only draws and
handles events; all game logic lives in game.py (R8.7).

The board looks like the game's (R8.2, docs/algorithm.md): rounded colored
tiles with white gaps on a white card, on a beige page. Regions are told
apart by tile color only.
"""

import argparse
import sys
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
# Corner radius of the band around a highlighted tile, as a share of a cell, before adding
# the gap. It follows the tile's corner, which bends less than its radius (see below).
HIGHLIGHT_CORNER_SHARE = 0.09
# Tile corner radius, as a share of a cell. Tk's smoothed corners bend less
# than a true arc, so this is about twice the game's radius to look the same.
CORNER_SHARE = 0.16

# Colors sampled from the game's screenshots.
PAGE_COLOR = "#f7f2ef"
CARD_COLOR = "#ffffff"
TEXT_COLOR = "#935a5a"
CROSS_COLOR = "#ffffff"
CAT_INK = "#262626"
REVEALED_INK = "#9a9a9a"
CAT_WHITE = "#ffffff"
HIGHLIGHT_COLORS = {Highlight.HINT: "#f5a700", Highlight.PROBLEM: "#d62828"}
SOLVED_POPUP = "Well done!"
POPUP_DELAY_MS = 150  # let the solving move show before the pop-up covers the board
POPUP_TAG = "popup"
POPUP_WIDTH = 280
POPUP_HEIGHT = 160
POPUP_RADIUS = 20
SOLVED_TITLE = "Puzzle solved!"
POPUP_TITLE_FONT = ("Helvetica", 22, "bold")
POPUP_BUTTON_FONT = ("Helvetica", 14, "bold")
POPUP_SUBTITLE_COLOR = "#b08a86"
POPUP_BUTTON_COLOR = "#e8873a"  # warm orange, like the game's highlights
POPUP_BORDER_COLOR = "#e4d8d2"  # a thin soft outline around the card
APPLY_TEXT = "Apply?"  # the link after a hint (R8.11)
STEP_LABEL = "Step by Step"  # the button that becomes Next Step while stepping (R8.12)
NEXT_LABEL = "Next Step"
UNDO_LABEL = "Previous"  # undo the player's last move (R8.13)
REDO_LABEL = "Next"  # redo it
APPLY_TAG = "apply"
APPLY_COLOR = "#c77400"  # a darker shade of the Hint ring's orange
SHAKE_STEP_MS = 40  # time between shake steps; 6 steps in all
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


def cells_between(start: Cell, end: Cell) -> list[Cell]:
    """The cells on a straight line from `start` to `end`, both included.

    A fast drag skips cells between two mouse events; this fills them in.
    """
    steps = max(abs(end[0] - start[0]), abs(end[1] - start[1]))
    if steps == 0:
        return [start]
    return [
        (
            round(start[0] + (end[0] - start[0]) * i / steps),
            round(start[1] + (end[1] - start[1]) * i / steps),
        )
        for i in range(steps + 1)
    ]


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
        self.popup = False  # whether the solved card (R8.6) is showing
        root.title("Meowdoku")
        root.resizable(False, False)
        root.configure(background=PAGE_COLOR)
        root.report_callback_exception = self._report_error  # type: ignore[assignment]

        toolbar = tk.Frame(root, padx=MARGIN, pady=MARGIN, background=PAGE_COLOR)
        toolbar.pack(fill="x")
        buttons = {}
        for label, command in (
            ("Open…", self.open_file),
            (UNDO_LABEL, lambda: self._run(self.session.undo)),
            (REDO_LABEL, lambda: self._run(self.session.redo)),
            ("Hint", lambda: self._run(self.session.hint)),
            (STEP_LABEL, lambda: self._run(self.session.step)),
            ("Solve", lambda: self._run(self.session.solve)),
            ("Reset", lambda: self._run(self.session.reset)),
        ):
            buttons[label] = tk.Button(toolbar, text=label, command=command, highlightbackground=PAGE_COLOR)
            buttons[label].pack(side="left", padx=(0, 6))
        self.step_button = buttons[STEP_LABEL]
        self.undo_button = buttons[UNDO_LABEL]
        self.redo_button = buttons[REDO_LABEL]
        self.root.update_idletasks()
        self._step_width = self.step_button.winfo_reqwidth()
        self._step_padx = int(str(self.step_button.cget("padx")))

        self.canvas = tk.Canvas(root, highlightthickness=0, background=PAGE_COLOR)
        self.canvas.pack()
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self._pressed: Cell | None = None  # where the mouse went down
        self._dragged_to: Cell | None = None  # the last cell a drag reached, once it leaves the first

        # A read-only text box rather than a label, so "Apply?" can be a link inside the sentence.
        self.message = tk.Text(
            root,
            font=MESSAGE_FONT,
            wrap="word",
            width=1,
            height=1,
            borderwidth=0,
            highlightthickness=0,
            padx=MARGIN,
            pady=MARGIN,
            background=PAGE_COLOR,
            cursor="arrow",
        )
        self.message.pack(fill="x")
        self.message.tag_configure(APPLY_TAG, foreground=APPLY_COLOR, underline=True)
        self.message.tag_bind(APPLY_TAG, "<Button-1>", lambda event: self._run(self.session.apply_hint))
        self.message.tag_bind(APPLY_TAG, "<Enter>", lambda event: self.message.configure(cursor="hand2"))
        self.message.tag_bind(APPLY_TAG, "<Leave>", lambda event: self.message.configure(cursor="arrow"))
        self.redraw()

    def _label_step_button(self, label: str) -> None:
        """Show "Step by Step" or "Next Step" (R8.12), padding the shorter one so nothing shifts.

        Padding keeps the native button look; a fixed width would not.
        """
        button = self.step_button
        if button.cget("text") == label:
            return
        button.configure(text=label, padx=self._step_padx)
        self.root.update_idletasks()
        extra = self._step_width - button.winfo_reqwidth()
        button.configure(padx=self._step_padx + max(0, extra) // 2)

    # Events

    def open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Open a screenshot",
            filetypes=[("Screenshots", "*.png *.jpg *.jpeg"), ("All files", "*")],
        )
        if not path:
            return
        self.close_popup()
        try:
            self.session = GameSession.from_screenshot(Path(path))
        except (OSError, MeowdokuError) as error:
            messagebox.showerror("Can't open puzzle", str(error))
            return
        self.redraw()

    def _run(self, action: Callable[[], None]) -> None:
        self.close_popup()
        action()
        self.redraw()
        if self.session.shake is not None:
            self._shake(self.session.shake)
        if self.session.just_solved:
            self.root.after(POPUP_DELAY_MS, self._celebrate)

    def _celebrate(self) -> None:
        """A card over the board when a move completes the puzzle (R8.6).

        Drawn on the canvas like the tiles, not as a macOS alert, which always
        shows the app's icon (Python's rocket) and can't open while the window
        is redrawing: a rounded white card with a thin soft outline, a title, a
        line of text, and a pill-shaped OK button. A click anywhere, Return,
        Escape, or the next action closes it.
        """
        self.close_popup()
        canvas = self.canvas
        width, height = int(canvas.cget("width")), int(canvas.cget("height"))
        card_w, card_h = min(width - 2 * MARGIN, POPUP_WIDTH), POPUP_HEIGHT
        left, top = (width - card_w) / 2, (height - card_h) / 2
        right, bottom = left + card_w, top + card_h
        middle = width / 2
        tags = POPUP_TAG
        self._round_box((left - 1, top - 1, right + 1, bottom + 1), POPUP_RADIUS + 1, POPUP_BORDER_COLOR, tags)
        self._round_box((left, top, right, bottom), POPUP_RADIUS, CARD_COLOR, tags)
        canvas.create_text(middle, top + 44, text=SOLVED_TITLE, font=POPUP_TITLE_FONT, fill=TEXT_COLOR, tags=tags)
        canvas.create_text(middle, top + 76, text=SOLVED_POPUP, font=MESSAGE_FONT, fill=POPUP_SUBTITLE_COLOR, tags=tags)
        button = (middle - 56, bottom - 54, middle + 56, bottom - 22)
        self._round_box(button, (button[3] - button[1]) / 2, POPUP_BUTTON_COLOR, tags)  # a pill
        canvas.create_text(middle, (button[1] + button[3]) / 2, text="OK", font=POPUP_BUTTON_FONT, fill=CARD_COLOR, tags=tags)
        self.root.bind("<Return>", lambda event: self.close_popup())
        self.root.bind("<Escape>", lambda event: self.close_popup())
        self.popup = True

    def _round_box(self, box: Box, radius: float, fill: str, tags: str) -> None:
        """A filled rounded rectangle made of circles and rectangles, whose edges macOS draws smoothly.

        Tk's smoothed polygons (rounded_rect_points) leave corners a little jagged;
        that's fine on small tiles but shows on a big card.
        """
        x0, y0, x1, y1 = box
        r = min(radius, (x1 - x0) / 2, (y1 - y0) / 2)
        plain = {"fill": fill, "width": 0, "tags": tags}
        for cx, cy in ((x0, y0), (x1 - 2 * r, y0), (x0, y1 - 2 * r), (x1 - 2 * r, y1 - 2 * r)):
            self.canvas.create_oval(cx, cy, cx + 2 * r, cy + 2 * r, **plain)
        self.canvas.create_rectangle(x0 + r, y0, x1 - r, y1, **plain)
        self.canvas.create_rectangle(x0, y0 + r, x1, y1 - r, **plain)

    def close_popup(self) -> None:
        if self.popup:
            self.canvas.delete(POPUP_TAG)
            self.popup = False
            self.root.unbind("<Return>")
            self.root.unbind("<Escape>")

    def _cell_under(self, event: "tk.Event[tk.Canvas]") -> Cell | None:
        return cell_at(event.x, event.y, self._cell_size, self.session.puzzle.size)

    def _on_press(self, event: "tk.Event[tk.Canvas]") -> None:
        self._dragged_to = None
        if self.popup:  # a click only closes the solved card; the board stays as it is
            self.close_popup()
            self._pressed = None
            return
        self._pressed = self._cell_under(event)

    def _on_drag(self, event: "tk.Event[tk.Canvas]") -> None:
        """Moving onto another cell turns the press into a drag that marks or unmarks (R8.10)."""
        cell = self._cell_under(event)
        if self._pressed is None or cell is None:
            return
        if self._dragged_to is None:
            if cell == self._pressed:
                return
            self.session.begin_paint(self._pressed)
            self._dragged_to = self._pressed
        if cell != self._dragged_to:
            for step in cells_between(self._dragged_to, cell)[1:]:
                self.session.paint(step)
            self._dragged_to = cell
            self.redraw()

    def _on_double_click(self, event: "tk.Event[tk.Canvas]") -> None:
        """A double-click places a cat (R8.4).

        Tk sends the first click as a normal click, then this instead of the
        second press; placing a cat replaces whatever that click left.
        """
        self._pressed = self._dragged_to = None  # the second release is not a click
        if self.popup:
            self.close_popup()
            return
        cell = self._cell_under(event)
        if cell is not None:
            self._run(lambda: self.session.place_cat(cell))

    def _on_release(self, event: "tk.Event[tk.Canvas]") -> None:
        """A press and release on one cell, with no drag, is a click (R8.4)."""
        pressed, dragged = self._pressed, self._dragged_to
        self._pressed = self._dragged_to = None
        if dragged is not None:
            self.session.end_paint()
        elif pressed is not None and self._cell_under(event) == pressed:
            self._run(lambda: self.session.click(pressed))

    def _report_error(
        self, exc_type: type[BaseException], error: BaseException, tb: TracebackType | None
    ) -> None:
        """Show unexpected errors in a dialog instead of a traceback (R8.8).

        If macOS won't open the dialog right now, print the error instead:
        reporting an error must never be what closes the window.
        """
        text = f"{exc_type.__name__}: {error}"
        try:
            messagebox.showerror("Something went wrong", text, parent=self.root)
        except tk.TclError:
            print(f"meowdoku: something went wrong: {text}", file=sys.stderr)

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
        self._draw_highlights()  # behind the tiles, so each shows as a band in the gap around its tile
        self._draw_tiles()
        self._draw_marks()
        self._show_message()
        self._label_step_button(NEXT_LABEL if self.session.stepping else STEP_LABEL)
        self.undo_button.configure(state="normal" if self.session.can_undo else "disabled")
        self.redo_button.configure(state="normal" if self.session.can_redo else "disabled")

    def _show_message(self) -> None:
        """The session's message, with an "Apply?" link after a hint that can be applied (R8.11)."""
        text = self.message
        text.configure(state="normal", foreground=TEXT_COLOR)
        text.delete("1.0", "end")
        text.insert("end", self.session.message)
        if self.session.applicable is not None and not self.session.stepping:  # Next applies while stepping
            text.insert("end", " ")
            text.insert("end", APPLY_TEXT, APPLY_TAG)
        text.configure(state="disabled")
        text.update_idletasks()
        lines = text.count("1.0", "end", "displaylines")
        text.configure(height=max(1, lines[0] if isinstance(lines, tuple) else lines or 1))

    def message_text(self) -> str:
        """What the message line shows, link included."""
        return self.message.get("1.0", "end-1c")

    def _shake(self, cell: Cell) -> None:
        """Wiggle a cell's tile and marks side to side for a moment: a wrong cat (R8.9)."""
        tag = "shaking"
        self.canvas.addtag_enclosed(tag, *self._cell_box(cell, inset=-1))
        step = max(3, self._cell_size // 10)
        positions = [step, -step, step, -step, step // 2, 0]
        moves = [after - before for before, after in zip([0, *positions], positions)]
        for index, dx in enumerate(moves):
            self.root.after(SHAKE_STEP_MS * (index + 1), self.canvas.move, tag, dx, 0)
        self.root.after(SHAKE_STEP_MS * (len(moves) + 1), self.canvas.dtag, tag, tag)

    def _draw_card(self, board: int) -> None:
        far = BOARD_INSET + board + CARD_PADDING
        self._rounded_rect((MARGIN, MARGIN, far, far), CARD_RADIUS, fill=CARD_COLOR)

    def _draw_tiles(self) -> None:
        radius = self._cell_size * CORNER_SHARE
        for cell in self.session.puzzle.cells():
            color = self.session.colors[self.session.puzzle.region_of(cell)]
            self._rounded_rect(self._tile_box(cell), radius, fill=color)

    def _draw_highlights(self) -> None:
        """An even colored band in the white gap around each highlighted tile.

        A smooth rounded shape a little bigger than the cell, drawn before the
        tiles: the tile covers its middle, leaving a clean band. Next to each
        other, the bands join into one outline around the group.
        """
        style = self.session.highlight_style
        if style is None:
            return
        radius = self._cell_size * HIGHLIGHT_CORNER_SHARE + tile_gap(self._cell_size) / 2
        for cell in self.session.highlight:
            self._round_box(self._cell_box(cell, inset=-1), radius, HIGHLIGHT_COLORS[style], "")

    def _draw_marks(self) -> None:
        state = self.session.state
        for cell in state.crosses:
            self._draw_cross(cell)
        for cell in state.cats:
            self._draw_cat(cell, CAT_INK)
        for cell in self.session.revealed - state.cats:
            self._draw_cat(cell, REVEALED_INK)

    def _draw_cross(self, cell: Cell) -> None:
        """A thick white X, like the game's."""
        x0, y0, x1, y1 = self._tile_box(cell)
        inset = (x1 - x0) * 0.25
        x0, y0, x1, y1 = x0 + inset, y0 + inset, x1 - inset, y1 - inset
        width = max(3, round(self._cell_size * 0.11))
        for line in ((x0, y0, x1, y1), (x0, y1, x1, y0)):
            self.canvas.create_line(*line, fill=CROSS_COLOR, width=width, capstyle="round")

    def _draw_cat(self, cell: Cell, ink: str) -> None:
        """A line-drawn lucky cat (maneki-neko) face: white with dark outlines.

        Positions are shares of the tile. The ears come first so the head
        covers their bases.
        """
        x0, y0, x1, _ = self._tile_box(cell)
        s = x1 - x0
        line = max(1.0, s * 0.045)
        thin = line * 0.8

        def at(fx: float, fy: float) -> tuple[float, float]:
            return (x0 + fx * s, y0 + fy * s)

        def shape(*points: tuple[float, float]) -> list[float]:
            return [coordinate for point in points for coordinate in at(*point)]

        def mirrored(*points: tuple[float, float]) -> list[float]:
            """The same shape reflected to the other side of the face."""
            return shape(*((1 - fx, fy) for fx, fy in points))

        canvas = self.canvas
        outlined = {"fill": CAT_WHITE, "outline": ink, "width": line}
        left_ear = ((0.10, 0.52), (0.17, 0.04), (0.46, 0.28))
        inner_ear = ((0.19, 0.30), (0.20, 0.13), (0.33, 0.24))
        for side in (shape, mirrored):
            canvas.create_polygon(side(*left_ear), **outlined)
        canvas.create_oval(*at(0.07, 0.22), *at(0.93, 0.94), **outlined)
        for side in (shape, mirrored):
            canvas.create_line(side(*inner_ear), fill=ink, width=thin)
        # Forehead stripes
        for fx in (0.44, 0.50, 0.56):
            canvas.create_line(shape((fx, 0.28), (fx, 0.38)), fill=ink, width=thin)
        # Almond eyes with round pupils
        for left in (0.21, 0.59):
            canvas.create_oval(*at(left, 0.48), *at(left + 0.20, 0.61), outline=ink, width=thin)
            canvas.create_oval(*at(left + 0.065, 0.49), *at(left + 0.135, 0.60), fill=ink, width=0)
        # Nose and mouth
        canvas.create_polygon(shape((0.46, 0.67), (0.54, 0.67), (0.50, 0.71)), fill=ink, outline=ink)
        canvas.create_line(
            shape((0.41, 0.75), (0.455, 0.78), (0.50, 0.74), (0.545, 0.78), (0.59, 0.75)),
            fill=ink,
            width=thin,
            smooth=True,
        )


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
