"""Tkinter window: a Meowdoku board with Open, Previous, Next, Hint, Step by Step, Solve, Reset (R8).

Run with `python -m meowdoku.gui [SCREENSHOT]`. This module only draws and
handles events; all game logic lives in game.py (R8.7).

The board looks like the game's (R8.2, docs/algorithm.md): rounded colored
tiles with white gaps on a white card, on a beige page. Regions are told
apart by tile color only.
"""

import argparse
import json
import locale
import os
import subprocess
import sys
import tkinter as tk
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox
from types import TracebackType

from meowdoku.game import EXAMPLE_PUZZLE, GameSession, Highlight, cells_between, error_text
from meowdoku.messages import DEFAULT_LANGUAGE, LANGUAGES, label, menu_order, normalize_language, pick_language
from meowdoku.puzzle import Cell, MeowdokuError
from meowdoku.state import BoardState

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
SOLVED_POPUP = label("ui.solved_subtitle")
POPUP_DELAY_MS = 150  # let the solving move show before the pop-up covers the board
POPUP_TAG = "popup"
POPUP_WIDTH = 280
POPUP_HEIGHT = 160
POPUP_RADIUS = 20
SOLVED_TITLE = label("ui.solved_title")
POPUP_TITLE_FONT = ("Helvetica", 22, "bold")
POPUP_BUTTON_FONT = ("Helvetica", 14, "bold")
POPUP_SUBTITLE_COLOR = "#85605c"  # dark enough for 4.5:1 contrast (R13.5)
POPUP_BUTTON_COLOR = "#b5571a"  # warm orange, dark enough for white text (R13.5)
POPUP_BORDER_COLOR = "#e4d8d2"  # a thin soft outline around the card
# English labels; the window shows them in its language (R12.6).
APPLY_TEXT = label("ui.apply")  # the link after a hint (R8.11)
STEP_LABEL = label("ui.step")  # the button that becomes Next Step while stepping (R8.12)
NEXT_LABEL = label("ui.next_step")
APPLY_TAG = "apply"
APPLY_COLOR = "#9a5c00"  # a darker shade of the Hint ring's orange
SHOW_ME_TEXT = label("ui.show_me")  # the link after a D6 hint (R8.14)
SHOW_ME_TAG = "show_me"
WALK_TAG = "walkthrough"
ICONS = {"ui.previous": "↶", "ui.next": "↷"}  # undo and redo arrows, as in the web app (R11.4)
SETTINGS_PATH = Path.home() / ".meowdoku" / "settings.json"  # the window's language, kept between runs
WALK_PADDING = 16
WALK_HEADER = 24  # height of the title line
WALK_CAPTION = 64  # room for three lines of explanation
WALK_BUTTON_HEIGHT = 32
WALK_BUTTON_WIDTH = 84
WALK_SPACING = 10
WALK_DASH = (6, 4)  # how marks that exist only in the assumption are drawn
WALK_CAPTION_TAG = "walkthrough_caption"
SHAKE_STEP_MS = 40  # time between shake steps; 6 steps in all
MESSAGE_FONT = ("Helvetica", 14)

Box = tuple[float, float, float, float]
"""A rectangle on the canvas as (left, top, right, bottom)."""


@dataclass(frozen=True)
class Grid:
    """Where a board is drawn: its top-left corner and cell size, in canvas pixels.

    The window's board and Show me's smaller copy (R8.14) are both drawn on one.
    """

    left: float
    top: float
    cell: int

    def cell_box(self, cell: Cell, inset: float = 0) -> Box:
        row, col = cell
        x0, y0 = self.left + col * self.cell, self.top + row * self.cell
        return (x0 + inset, y0 + inset, x0 + self.cell - inset, y0 + self.cell - inset)

    def tile_box(self, cell: Cell) -> Box:
        """The colored tile inside a cell, leaving half the gap on each side."""
        return self.cell_box(cell, inset=tile_gap(self.cell) / 2)


@dataclass(frozen=True)
class WalkLayout:
    """Where Show me's card puts its parts (R8.14)."""

    card: Box
    grid: Grid
    caption: tuple[float, float, float]  # left, top, and wrap width
    buttons: dict[str, Box]


def walk_layout(width: int, height: int, board_size: int, cell: int) -> WalkLayout:
    """Lay out Show me's card over a canvas: a title, a smaller board, the caption, and three buttons.

    The board is as big as fits, but never bigger than the window's.
    """
    card = (MARGIN, MARGIN, width - MARGIN, height - MARGIN)
    left, top, right, bottom = card
    room_w = right - left - 2 * WALK_PADDING
    room_h = bottom - top - 2 * WALK_PADDING - WALK_HEADER - WALK_CAPTION - WALK_BUTTON_HEIGHT - 3 * WALK_SPACING
    small = max(1, min(cell, int(min(room_w, room_h)) // board_size))
    board = small * board_size
    board_top = top + WALK_PADDING + WALK_HEADER + WALK_SPACING
    grid = Grid((width - board) // 2, board_top, small)  # whole pixels, or the tile edges look rough
    caption_top = board_top + board + WALK_SPACING
    button_top = bottom - WALK_PADDING - WALK_BUTTON_HEIGHT
    middle = width / 2
    spots = {
        "back": left + WALK_PADDING,
        "close": middle - WALK_BUTTON_WIDTH / 2,
        "next": right - WALK_PADDING - WALK_BUTTON_WIDTH,
    }
    buttons = {
        name: (x, button_top, x + WALK_BUTTON_WIDTH, button_top + WALK_BUTTON_HEIGHT) for name, x in spots.items()
    }
    return WalkLayout(card, grid, (left + WALK_PADDING, caption_top, room_w), buttons)


def dash_pieces(line: Box, dashes: int = 3) -> list[Box]:
    """Split a line into `dashes` evenly spaced pieces with equal gaps, ends included."""
    x0, y0, x1, y1 = line
    parts = 2 * dashes - 1
    points = [(x0 + (x1 - x0) * i / parts, y0 + (y1 - y0) * i / parts) for i in range(parts + 1)]
    return [(*points[i], *points[i + 1]) for i in range(0, parts, 2)]


def box_at(x: float, y: float, boxes: dict[str, Box]) -> str | None:
    """The name of the box that holds a point, if any."""
    for name, (x0, y0, x1, y1) in boxes.items():
        if x0 <= x <= x1 and y0 <= y <= y1:
            return name
    return None


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


@dataclass(frozen=True)
class Palette:
    """Everything around the puzzle; the tiles, marks, and rings look the same in both (R13.1)."""

    page: str
    card: str
    text: str
    subtle: str
    border: str
    accent: str  # the primary button, under white text
    link: str  # Apply? and Show me


LIGHT = Palette(PAGE_COLOR, CARD_COLOR, TEXT_COLOR, POPUP_SUBTITLE_COLOR, POPUP_BORDER_COLOR, POPUP_BUTTON_COLOR, APPLY_COLOR)
NIGHT = Palette("#221c1d", "#2e2627", "#f0dcd6", "#c4aca7", "#4a3d3c", "#b5571a", "#f0a24a")  # as web/style.css
ON_ACCENT = "#ffffff"
THEMES = {"auto": "ui.theme_auto", "light": "ui.theme_light", "night": "ui.theme_night"}  # in menu order (R13.2)
FOLLOW_SYSTEM_MS = 3000  # how often Auto checks whether macOS turned dark mode on or off


def system_is_dark() -> bool:
    """Whether the computer is in dark mode; only macOS is asked, others count as light."""
    if sys.platform != "darwin":
        return False
    try:
        result = subprocess.run(
            ["defaults", "read", "-g", "AppleInterfaceStyle"], capture_output=True, text=True, timeout=2, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.stdout.strip().lower() == "dark"


# The window


def system_languages() -> list[str]:
    """The computer's preferred languages, most preferred first, like a browser's (R12.6).

    macOS keeps them in AppleLanguages; elsewhere, or if that can't be read,
    the usual environment variables and locale are used.
    """
    found: list[str] = []
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleLanguages"], capture_output=True, text=True, timeout=2, check=False
            )
            found += [item.strip().strip('",') for item in result.stdout.strip("()\n ").split(",") if item.strip()]
        except (OSError, subprocess.SubprocessError):
            pass
    for name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        found += [part.split(".")[0].replace("_", "-") for part in os.environ.get(name, "").split(":") if part]
    code = locale.getlocale()[0]
    if code:
        found.append(code.replace("_", "-"))
    return [code for code in found if code and code not in ("C", "POSIX")]


def load_settings(path: Path | None) -> dict[str, object]:
    """The settings file's contents, or nothing if there's no file or it can't be read."""
    if path is None:
        return {}
    try:
        settings = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return settings if isinstance(settings, dict) else {}


def save_setting(path: Path | None, name: str, value: str) -> None:
    """Remember one setting for next time, keeping the others; a file that can't be written is skipped."""
    if path is None:
        return
    settings = load_settings(path) | {name: value}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(settings))
    except OSError:
        pass


def load_language(path: Path | None, default: str = DEFAULT_LANGUAGE) -> str:
    """The language saved in the settings file, or `default` if there is none (R12.6)."""
    saved = load_settings(path).get("language")
    return normalize_language(saved) if isinstance(saved, str) and saved else default


def save_language(path: Path | None, language: str) -> None:
    save_setting(path, "language", language)


def load_theme(path: Path | None) -> str:
    """Auto, Light, or Night from the settings file; Auto if there is none (R13.4)."""
    saved = load_settings(path).get("theme")
    return saved if isinstance(saved, str) and saved in THEMES else "auto"


class MeowdokuApp:
    def __init__(
        self, root: tk.Tk, session: GameSession, settings: Path | None = None, preferred: Sequence[str] = ()
    ) -> None:
        """`settings` is where the chosen language is kept between runs; None keeps it for this run only.

        `preferred` holds the computer's languages: the menu lists the first one
        offered at the top, and it's the language until the player picks one (R12.2).
        """
        self.root = root
        self.session = session
        self.settings = settings
        self.preferred = list(preferred)
        self.theme = load_theme(settings)
        self.palette = LIGHT
        self.popup = False  # whether the solved card (R8.6) is showing
        root.title("Meowdoku")
        root.resizable(False, False)

        root.report_callback_exception = self._report_error  # type: ignore[assignment]

        toolbar = tk.Frame(root, padx=MARGIN, pady=MARGIN)
        self.toolbar = toolbar
        toolbar.pack(fill="x")
        self.buttons: dict[str, tk.Button] = {}  # by message key, so their labels follow the language
        for key, command in (
            ("ui.open_dialog", self.open_file),
            ("ui.previous", lambda: self._run(self.session.undo)),
            ("ui.next", lambda: self._run(self.session.redo)),
            ("ui.hint", lambda: self._run(self.session.hint)),
            ("ui.solve", lambda: self._run(self.session.solve)),
            ("ui.reset", lambda: self._run(self.session.reset)),
            ("ui.step", lambda: self._run(self.session.step)),  # last, on the right, as in the web app
        ):
            button = tk.Button(toolbar, command=command)
            button.pack(side="left", padx=(0, 6))
            self.buttons[key] = button
        self.step_button = self.buttons["ui.step"]
        self.undo_button = self.buttons["ui.previous"]
        self.redo_button = self.buttons["ui.next"]
        self._step_padx = int(str(self.step_button.cget("padx")))
        self._step_width = 0
        self.language_menu = self._build_language_menu()

        self.canvas = tk.Canvas(root, highlightthickness=0)
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
            cursor="arrow",
        )
        self.message.pack(fill="x")
        self.message.tag_configure(APPLY_TAG, underline=True)
        self.message.tag_bind(APPLY_TAG, "<Button-1>", lambda event: self._run(self.session.apply_hint))
        self.message.tag_bind(APPLY_TAG, "<Enter>", lambda event: self.message.configure(cursor="hand2"))
        self.message.tag_bind(APPLY_TAG, "<Leave>", lambda event: self.message.configure(cursor="arrow"))
        self.message.tag_configure(SHOW_ME_TAG, underline=True)
        self.message.tag_bind(SHOW_ME_TAG, "<Button-1>", lambda event: self._walk(self.session.show_me))
        self.message.tag_bind(SHOW_ME_TAG, "<Enter>", lambda event: self.message.configure(cursor="hand2"))
        self.message.tag_bind(SHOW_ME_TAG, "<Leave>", lambda event: self.message.configure(cursor="arrow"))
        self._walk_buttons: dict[str, Box] = {}  # Show me's buttons while its card is open
        root.bind("<Return>", lambda event: self._on_key("Return"))
        root.bind("<Escape>", lambda event: self._on_key("Escape"))
        root.bind("<Left>", lambda event: self._on_key("Left"))
        root.bind("<Right>", lambda event: self._on_key("Right"))
        self.set_theme(self.theme)
        default = pick_language(self.preferred) if self.preferred else self.session.language
        self.set_language(load_language(settings, default))
        self.root.after(FOLLOW_SYSTEM_MS, self._follow_system)

    # Language (R12.6)

    def _label(self, key: str, **args: object) -> str:
        return label(key, self.session.language, **args)  # type: ignore[arg-type]

    def _build_language_menu(self) -> tk.Menu:
        """A Language menu in the menu bar, each language in its own name."""
        menubar = tk.Menu(self.root)
        menu = tk.Menu(menubar, tearoff=False)
        self._language = tk.StringVar(value=self.session.language)
        for code in menu_order(self.preferred):
            menu.add_radiobutton(
                label=LANGUAGES[code], value=code, variable=self._language, command=self._choose_language
            )
        menubar.add_cascade(label=label("ui.language"), menu=menu)
        self.appearance_menu = tk.Menu(menubar, tearoff=False)
        self._theme = tk.StringVar(value="auto")
        for choice, key in THEMES.items():
            self.appearance_menu.add_radiobutton(
                label=label(key), value=choice, variable=self._theme, command=self._choose_theme
            )
        menubar.add_cascade(label=label("ui.appearance"), menu=self.appearance_menu)
        self.root.configure(menu=menubar)
        self._menubar = menubar
        return menu

    def _choose_language(self) -> None:
        self.set_language(self._language.get())
        save_language(self.settings, self.session.language)

    # Night mode (R13)

    def _choose_theme(self) -> None:
        self.set_theme(self._theme.get())
        save_setting(self.settings, "theme", self.theme)

    def set_theme(self, theme: str) -> None:
        """Auto, Light, or Night: color everything around the puzzle to match (R13.1, R13.2)."""
        self.theme = theme
        self._theme.set(theme)
        night = theme == "night" or (theme == "auto" and system_is_dark())
        self.palette = NIGHT if night else LIGHT
        page = self.palette.page
        for widget in (self.root, self.toolbar, self.canvas):
            widget.configure(background=page)
        for button in self.buttons.values():
            button.configure(highlightbackground=page)
        self.message.configure(background=page)
        self.message.tag_configure(APPLY_TAG, foreground=self.palette.link)
        self.message.tag_configure(SHOW_ME_TAG, foreground=self.palette.link)
        self.redraw()

    def _follow_system(self) -> None:
        """On Auto, switch when the computer turns dark mode on or off while the window is open."""
        if self.theme == "auto":
            wanted = NIGHT if system_is_dark() else LIGHT
            if wanted is not self.palette:
                self.set_theme("auto")
        self.root.after(FOLLOW_SYSTEM_MS, self._follow_system)

    def set_language(self, language: str) -> None:
        """Word the window in `language`: buttons, menu, messages, and hints. The board doesn't change."""
        self.session.set_language(language)
        self._language.set(language)
        self._menubar.entryconfigure(0, label=self._label("ui.language"))
        self._menubar.entryconfigure(1, label=self._label("ui.appearance"))
        for index, key in enumerate(THEMES.values()):
            self.appearance_menu.entryconfigure(index, label=self._label(key))
        for key, button in self.buttons.items():
            button.configure(text=ICONS.get(key) or self._label(key))
        self._measure_step_button()
        self.redraw()

    def _measure_step_button(self) -> None:
        """The width of the wider of Step by Step and Next Step, so switching never shifts the buttons."""
        button = self.step_button
        widths = []
        for key in ("ui.next_step", "ui.step"):
            button.configure(text=self._label(key), padx=self._step_padx)
            self.root.update_idletasks()
            widths.append(button.winfo_reqwidth())
        self._step_width = max(widths)

    def _label_step_button(self, text: str) -> None:
        """Show "Step by Step" or "Next Step" (R8.12), padding the shorter one so nothing shifts.

        Padding keeps the native button look; a fixed width would not.
        """
        button = self.step_button
        button.configure(text=text, padx=self._step_padx)
        self.root.update_idletasks()
        extra = self._step_width - button.winfo_reqwidth()
        button.configure(padx=self._step_padx + max(0, extra) // 2)

    # Events

    def open_file(self) -> None:
        path = filedialog.askopenfilename(
            title=self._label("ui.open_title"),
            filetypes=[(self._label("ui.screenshots"), "*.png *.jpg *.jpeg"), (self._label("ui.all_files"), "*")],
        )
        if not path:
            return
        self.close_popup()
        language = self.session.language
        try:
            self.session = GameSession.from_screenshot(Path(path), language)
        except (OSError, MeowdokuError) as error:
            messagebox.showerror(self._label("ui.cant_open"), error_text(error, Path(path), language))
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
        self._round_box((left - 1, top - 1, right + 1, bottom + 1), POPUP_RADIUS + 1, self.palette.border, tags)
        self._round_box((left, top, right, bottom), POPUP_RADIUS, self.palette.card, tags)
        title, subtitle = self._label("ui.solved_title"), self._label("ui.solved_subtitle")
        canvas.create_text(middle, top + 44, text=title, font=POPUP_TITLE_FONT, fill=self.palette.text, tags=tags)
        canvas.create_text(middle, top + 76, text=subtitle, font=MESSAGE_FONT, fill=self.palette.subtle, tags=tags)
        button = (middle - 56, bottom - 54, middle + 56, bottom - 22)
        self._round_box(button, (button[3] - button[1]) / 2, self.palette.accent, tags)  # a pill
        canvas.create_text(
            middle, (button[1] + button[3]) / 2, text=self._label("ui.ok"), font=POPUP_BUTTON_FONT, fill=ON_ACCENT, tags=tags
        )
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

    def _walk(self, action: Callable[[], None]) -> None:
        """Move through Show me (R8.14). Unlike _run, this never touches the marks or the hint."""
        self.close_popup()
        action()
        self.redraw()

    def _on_key(self, key: str) -> None:
        """Return and Escape close the solved card (R8.6); in Show me, the arrows move and Escape closes."""
        if self.popup:
            if key in ("Return", "Escape"):
                self.close_popup()
            return
        if not self.session.walking:
            return
        actions = {
            "Left": self.session.previous_frame,
            "Right": self.session.next_frame,
            "Return": self.session.next_frame,
            "Escape": self.session.close_show_me,
        }
        self._walk(actions[key])

    def _cell_under(self, event: "tk.Event[tk.Canvas]") -> Cell | None:
        return cell_at(event.x, event.y, self._cell_size, self.session.puzzle.size)

    def _on_press(self, event: "tk.Event[tk.Canvas]") -> None:
        self._dragged_to = None
        self._pressed = None
        if self.popup:  # a click only closes the solved card; the board stays as it is
            self.close_popup()
            return
        if self.session.walking:  # Show me covers the board; only its buttons respond
            self._press_walk_button(event.x, event.y)
            return
        self._pressed = self._cell_under(event)

    def _press_walk_button(self, x: float, y: float) -> None:
        actions = {
            "back": self.session.previous_frame,
            "close": self.session.close_show_me,
            "next": self.session.next_frame,
        }
        name = box_at(x, y, self._walk_buttons)
        if name is not None:
            self._walk(actions[name])

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
        if self.session.walking:  # the second press of a quick double-click on a button
            self._press_walk_button(event.x, event.y)
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
            messagebox.showerror(self._label("ui.went_wrong"), text, parent=self.root)
        except tk.TclError:
            print(f"meowdoku: something went wrong: {text}", file=sys.stderr)

    # Drawing

    @property
    def _cell_size(self) -> int:
        return cell_pixels(self.session.puzzle.size)

    @property
    def _grid(self) -> Grid:
        return Grid(BOARD_INSET, BOARD_INSET, self._cell_size)

    def _rounded_rect(self, box: Box, radius: float, **options: object) -> None:
        self.canvas.create_polygon(rounded_rect_points(box, radius), smooth=True, **options)

    def redraw(self) -> None:
        board = self.session.puzzle.size * self._cell_size
        self.canvas.configure(width=board + 2 * BOARD_INSET, height=board + 2 * BOARD_INSET)
        self.canvas.delete("all")
        self._draw_card(board)
        grid = self._grid
        # Highlights go behind the tiles, so each shows as a band in the gap around its tile.
        self._draw_highlights(grid, self.session.highlight, self.session.highlight_style)
        self._draw_tiles(grid)
        self._draw_marks(grid)
        self._walk_buttons = {}
        if self.session.walking:
            self._draw_walkthrough()
        self._show_message()
        self._label_step_button(self._label("ui.next_step" if self.session.stepping else "ui.step"))
        self.undo_button.configure(state="normal" if self.session.can_undo else "disabled")
        self.redo_button.configure(state="normal" if self.session.can_redo else "disabled")

    def _show_message(self) -> None:
        """The session's message, with an "Apply?" link after a hint that can be applied (R8.11)."""
        text = self.message
        text.configure(state="normal", foreground=self.palette.text)
        text.delete("1.0", "end")
        text.insert("end", self.session.message)
        if self.session.can_show_me:
            text.insert("end", " ")
            text.insert("end", self._label("ui.show_me"), SHOW_ME_TAG)
        if self.session.applicable is not None and not self.session.stepping:  # Next applies while stepping
            text.insert("end", " ")
            text.insert("end", self._label("ui.apply"), APPLY_TAG)
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
        self.canvas.addtag_enclosed(tag, *self._grid.cell_box(cell, inset=-1))
        step = max(3, self._cell_size // 10)
        positions = [step, -step, step, -step, step // 2, 0]
        moves = [after - before for before, after in zip([0, *positions], positions)]
        for index, dx in enumerate(moves):
            self.root.after(SHAKE_STEP_MS * (index + 1), self.canvas.move, tag, dx, 0)
        self.root.after(SHAKE_STEP_MS * (len(moves) + 1), self.canvas.dtag, tag, tag)

    def _draw_card(self, board: int) -> None:
        far = BOARD_INSET + board + CARD_PADDING
        self._rounded_rect((MARGIN, MARGIN, far, far), CARD_RADIUS, fill=self.palette.card)

    def _draw_tiles(self, grid: Grid, tags: str = "") -> None:
        """Rounded tiles. Show me's smaller ones are drawn like the pop-up cards, since
        smoothed polygons get rough edges at that size; true arcs need half the radius.
        """
        radius = grid.cell * CORNER_SHARE
        for cell in self.session.puzzle.cells():
            color = self.session.colors[self.session.puzzle.region_of(cell)]
            if tags:
                self._round_box(grid.tile_box(cell), radius / 2, color, tags)
            else:
                self._rounded_rect(grid.tile_box(cell), radius, fill=color)

    def _draw_highlights(
        self, grid: Grid, cells: frozenset[Cell], style: Highlight | None, tags: str = ""
    ) -> None:
        """An even colored band in the white gap around each highlighted tile.

        A smooth rounded shape a little bigger than the cell, drawn before the
        tiles: the tile covers its middle, leaving a clean band. Next to each
        other, the bands join into one outline around the group.
        """
        if style is None:
            return
        radius = grid.cell * HIGHLIGHT_CORNER_SHARE + tile_gap(grid.cell) / 2
        for cell in cells:
            self._round_box(grid.cell_box(cell, inset=-1), radius, HIGHLIGHT_COLORS[style], tags)

    def _draw_marks(self, grid: Grid) -> None:
        state = self.session.state
        self._draw_board_marks(grid, state)
        for cell in self.session.revealed - state.cats:
            self._draw_cat(grid, cell, REVEALED_INK)

    def _draw_board_marks(
        self, grid: Grid, state: BoardState, what_if: frozenset[Cell] = frozenset(), tags: str = ""
    ) -> None:
        """Cats and ✕ marks; those in `what_if` exist only in an assumption and are dashed (R8.14)."""
        for cell in state.crosses:
            self._draw_cross(grid, cell, dashed=cell in what_if, tags=tags)
        for cell in state.cats:
            self._draw_cat(grid, cell, CAT_INK, dashed=cell in what_if, tags=tags)

    def _draw_cross(self, grid: Grid, cell: Cell, dashed: bool = False, tags: str = "") -> None:
        """A thick white X, like the game's."""
        x0, y0, x1, y1 = grid.tile_box(cell)
        inset = (x1 - x0) * 0.25
        x0, y0, x1, y1 = x0 + inset, y0 + inset, x1 - inset, y1 - inset
        width = max(3, round(grid.cell * 0.11))
        for line in ((x0, y0, x1, y1), (x0, y1, x1, y0)):
            # Tk's own dashes come out blotchy on thick, short lines, so a dashed arm is drawn as pieces.
            pieces = dash_pieces(line) if dashed else [line]
            for piece in pieces:
                self.canvas.create_line(*piece, fill=CROSS_COLOR, width=width * 0.8 if dashed else width, capstyle="round", tags=tags)

    def _draw_cat(self, grid: Grid, cell: Cell, ink: str, dashed: bool = False, tags: str = "") -> None:
        """A line-drawn lucky cat (maneki-neko) face: white with dark outlines.

        Positions are shares of the tile. The ears come first so the head
        covers their bases. A dashed cat has dashed outlines on its ears and head.
        """
        x0, y0, x1, _ = grid.tile_box(cell)
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
        outlined: dict[str, object] = {"fill": CAT_WHITE, "outline": ink, "width": line, "tags": tags}
        if dashed:
            outlined["dash"] = WALK_DASH
        left_ear = ((0.10, 0.52), (0.17, 0.04), (0.46, 0.28))
        inner_ear = ((0.19, 0.30), (0.20, 0.13), (0.33, 0.24))
        for side in (shape, mirrored):
            canvas.create_polygon(side(*left_ear), **outlined)
        canvas.create_oval(*at(0.07, 0.22), *at(0.93, 0.94), **outlined)
        for side in (shape, mirrored):
            canvas.create_line(side(*inner_ear), fill=ink, width=thin, tags=tags)
        # Forehead stripes
        for fx in (0.44, 0.50, 0.56):
            canvas.create_line(shape((fx, 0.28), (fx, 0.38)), fill=ink, width=thin, tags=tags)
        # Almond eyes with round pupils
        for left in (0.21, 0.59):
            canvas.create_oval(*at(left, 0.48), *at(left + 0.20, 0.61), outline=ink, width=thin, tags=tags)
            canvas.create_oval(*at(left + 0.065, 0.49), *at(left + 0.135, 0.60), fill=ink, width=0, tags=tags)
        # Nose and mouth
        canvas.create_polygon(shape((0.46, 0.67), (0.54, 0.67), (0.50, 0.71)), fill=ink, outline=ink, tags=tags)
        canvas.create_line(
            shape((0.41, 0.75), (0.455, 0.78), (0.50, 0.74), (0.545, 0.78), (0.59, 0.75)),
            fill=ink,
            width=thin,
            smooth=True,
            tags=tags,
        )

    def _draw_walkthrough(self) -> None:
        """Show me's card over the board (R8.14): a frame of the proof on a smaller copy of the board."""
        frame = self.session.frame
        assert frame is not None
        width, height = int(self.canvas.cget("width")), int(self.canvas.cget("height"))
        layout = walk_layout(width, height, self.session.puzzle.size, self._cell_size)
        tags = WALK_TAG
        x0, y0, x1, y1 = layout.card
        left, top, right = x0, y0, x1
        self._round_box((x0 - 1, y0 - 1, x1 + 1, y1 + 1), POPUP_RADIUS + 1, self.palette.border, tags)
        self._round_box(layout.card, POPUP_RADIUS, self.palette.card, tags)
        header_y = top + WALK_PADDING + WALK_HEADER / 2
        self.canvas.create_text(
            left + WALK_PADDING,
            header_y,
            text=self._label("ui.walk_title"),
            anchor="w",
            font=POPUP_BUTTON_FONT,
            fill=self.palette.text,
            tags=tags,
        )
        count = self._label("ui.walk_count", number=self.session.frame_number + 1, total=len(self.session.frames))
        self.canvas.create_text(
            right - WALK_PADDING, header_y, text=count, anchor="e", font=MESSAGE_FONT, fill=self.palette.subtle, tags=tags
        )
        grid = layout.grid
        self._draw_highlights(grid, frame.ring, frame.style, tags)
        self._draw_tiles(grid, tags)
        self._draw_board_marks(grid, frame.state, frame.what_if, tags)
        caption_x, caption_y, wrap = layout.caption
        self.canvas.create_text(
            caption_x,
            caption_y,
            text=self.session.caption,
            anchor="nw",
            width=wrap,
            font=MESSAGE_FONT,
            fill=self.palette.text,
            tags=(tags, WALK_CAPTION_TAG),
        )
        last = self.session.frame_number + 1 == len(self.session.frames)
        labels = {
            "back": self._label("ui.back"),
            "close": self._label("ui.close"),
            "next": self._label("ui.done" if last else "ui.walk_next"),
        }
        if self.session.frame_number == 0:
            del labels["back"]
        for name, label in labels.items():
            box = layout.buttons[name]
            self._walk_buttons[name] = box
            primary = name == "next"
            self._round_box(box, (box[3] - box[1]) / 2, self.palette.accent if primary else self.palette.border, tags)
            self.canvas.create_text(
                (box[0] + box[2]) / 2,
                (box[1] + box[3]) / 2,
                text=label,
                font=POPUP_BUTTON_FONT,
                fill=ON_ACCENT if primary else self.palette.text,
                tags=tags,
            )

    def walk_caption(self) -> str:
        """The caption Show me's card shows, or "" when it's closed."""
        items = self.canvas.find_withtag(WALK_CAPTION_TAG)
        return self.canvas.itemcget(items[0], "text") if items else ""


# Entry point


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m meowdoku.gui", description="Play Meowdoku.")
    parser.add_argument("screenshot", nargs="?", type=Path, help="a .png or .jpg screenshot (optional)")
    args = parser.parse_args(argv)

    root = tk.Tk()
    preferred = system_languages()
    language = load_language(SETTINGS_PATH, pick_language(preferred))
    session = GameSession.from_text(EXAMPLE_PUZZLE)
    if args.screenshot is not None:
        try:
            session = GameSession.from_screenshot(args.screenshot, language)
        except (OSError, MeowdokuError) as error:
            reason = error_text(error, args.screenshot, language)
            messagebox.showerror(label("ui.cant_open", language), f"{reason}\n\n{label('ui.example_instead', language)}")
    MeowdokuApp(root, session, SETTINGS_PATH, preferred)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
