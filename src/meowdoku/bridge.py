"""The web app's way into the game: actions in, a plain board description out (R11.2).

The web page runs this module in Pyodide, in a web worker (R11.3). Each
request is JSON naming one player action, and each reply is JSON describing
the whole board, so the page only draws what it's told and holds no game
logic, like the desktop window (R8.7). Presses, drags, and releases follow the
same rules as gui.py: a press and release on one cell is a click, moving onto
another cell turns it into a drag (R8.4, R8.10).
"""

import json
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from meowdoku.game import EXAMPLE_PUZZLE, GameSession, cells_between
from meowdoku.puzzle import Cell, MeowdokuError

View = dict[str, Any]


def _cells(cells: Iterable[Cell]) -> list[list[int]]:
    """Cells as sorted [row, col] pairs, 0-indexed, so the reply is deterministic (NFR4)."""
    return [[row, col] for row, col in sorted(cells)]


class Bridge:
    """One player's game in the browser, driven by `handle`."""

    def __init__(self) -> None:
        self.session = GameSession.from_text(EXAMPLE_PUZZLE)
        self._pressed: Cell | None = None
        self._dragged_to: Cell | None = None
        self._actions: dict[str, Callable[..., None]] = {
            "open": self.open,
            "press": self.press,
            "move": self.move,
            "release": self.release,
            "double": self.double,
            "hint": self.session_action("hint"),
            "apply": self.session_action("apply_hint"),
            "step": self.session_action("step"),
            "solve": self.session_action("solve"),
            "reset": self.session_action("reset"),
            "previous": self.session_action("undo"),
            "next": self.session_action("redo"),
            "view": lambda: None,
        }

    def session_action(self, name: str) -> Callable[[], None]:
        """A button press, forwarded to the current session (which `open` may replace)."""
        return lambda: getattr(self.session, name)()

    def handle(self, request: str) -> str:
        """Run one action, e.g. {"action": "press", "args": [2, 3]}, and return the board as JSON.

        A file that can't be opened, or an unknown action, leaves the game as
        it was and puts the reason in the reply's "error" (as R8.8).
        """
        error = None
        try:
            message = json.loads(request)
            action = self._actions[message["action"]]
            action(*message.get("args", []))
        except (MeowdokuError, OSError) as exc:
            error = str(exc)
        except (KeyError, TypeError, ValueError) as exc:
            error = f"bad request: {exc!r}"
        return json.dumps(self.view(error))

    def open(self, path: str) -> None:
        """Open a screenshot the worker saved in Pyodide's file system (R11.5)."""
        self.session = GameSession.from_screenshot(Path(path))
        self._pressed = self._dragged_to = None

    def press(self, row: int, col: int) -> None:
        self._pressed, self._dragged_to = (row, col), None

    def move(self, row: int, col: int) -> None:
        """Moving onto another cell turns the press into a drag; skipped cells are filled in (R8.10)."""
        cell = (row, col)
        if self._pressed is None:
            return
        if self._dragged_to is None:
            if cell == self._pressed:
                return
            self.session.begin_paint(self._pressed)
            self._dragged_to = self._pressed
        for step in cells_between(self._dragged_to, cell)[1:]:
            self.session.paint(step)
        self._dragged_to = cell

    def release(self, row: int, col: int) -> None:
        """A press and release on one cell, with no drag, is a click (R8.4)."""
        pressed, dragged = self._pressed, self._dragged_to
        self._pressed = self._dragged_to = None
        if dragged is not None:
            self.session.end_paint()
        elif pressed == (row, col):
            self.session.click(pressed)

    def double(self, row: int, col: int) -> None:
        """A double-click or double tap places a cat (R8.4); its second release is not a click."""
        self._pressed = self._dragged_to = None
        self.session.place_cat((row, col))

    def view(self, error: str | None = None) -> View:
        """Everything the page draws, as plain JSON-ready data (R11.2)."""
        session = self.session
        state = session.state
        style = session.highlight_style
        return {
            "size": session.puzzle.size,
            "regions": ["".join(row) for row in session.puzzle.regions],
            "colors": dict(session.colors),
            "cats": _cells(state.cats),
            "crosses": _cells(state.crosses),
            "locked": _cells(cell for cell in state.cats if session.is_locked(cell)),
            "solution": _cells(session.revealed),
            "highlight": _cells(session.highlight),
            "highlight_style": None if style is None else style.value,
            "message": session.message,
            "can_apply": session.applicable is not None and not session.stepping,
            "stepping": session.stepping,
            "can_undo": session.can_undo,
            "can_redo": session.can_redo,
            "shake": None if session.shake is None else list(session.shake),
            "just_solved": session.just_solved,
            "error": error,
        }
