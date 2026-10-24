"""Remake the screenshots of this program's own window in tests/fixtures/screenshots/ (R9.6).

Run on a Mac, from the project folder:

    python tests/capture_window_screenshots.py

Each screenshot is taken with macOS's `screencapture -l`, like pressing
Shift-Command-4 then Space: the whole window with its title bar and its
transparent shadow (JPEG copies are laid over white). It works even when
other windows cover this one. Each gets a .txt file (the regions) and a
.marks file (the player's marks) beside it for test_image_import.py. Remake
them whenever the window's look changes. Needs permission to record the
screen.
"""

import ctypes
import os
import random
import subprocess
import sys
import tempfile
import tkinter as tk
from collections.abc import Callable
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from helpers import random_puzzle  # noqa: E402

from meowdoku.game import EXAMPLE_PUZZLE, GameSession  # noqa: E402
from meowdoku.gui import MeowdokuApp  # noqa: E402
from meowdoku.puzzle import Cell  # noqa: E402
from meowdoku.state import BoardState  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "screenshots"
GAME_SCREENSHOT = FIXTURES / "IMG_7117.PNG"

Setup = Callable[[GameSession], None]


def capture(name: str, session: GameSession, setup: Setup = lambda session: None, quality: int = 0) -> None:
    """Show the window, take its screenshot, and write the expected regions and marks."""
    root = tk.Tk()
    setup(session)
    app = MeowdokuApp(root, session)

    failure: list[BaseException] = []

    def grab() -> None:
        try:
            save()
        except BaseException as error:  # Tk would swallow it and keep the window open
            failure.append(error)
        root.destroy()

    def save() -> None:
        path = FIXTURES / name
        with tempfile.TemporaryDirectory() as folder:
            shot = Path(folder) / "window.png"
            _capture_window(shot)
            image = Image.open(shot)
            if quality:
                white = Image.new("RGBA", image.size, "white")
                Image.alpha_composite(white, image.convert("RGBA")).convert("RGB").save(path, quality=quality)
            else:
                image.save(path, optimize=True)
        path.with_suffix(".txt").write_text("\n".join("".join(row) for row in app.session.puzzle.regions) + "\n")
        path.with_suffix(".marks").write_text(_expected_marks(app.session))
        print(f"wrote {path.name}")

    root.after(1000, grab)
    root.mainloop()
    if failure:
        raise failure[0]


def _capture_window(shot: Path) -> None:
    """Screenshot this process's window. An earlier, closed window may still be listed; it can't be captured."""
    windows = _window_ids()
    for window in windows:
        if subprocess.run(["screencapture", "-x", "-l", str(window), str(shot)]).returncode == 0:
            return
    raise SystemExit(f"couldn't capture any of this program's windows: {windows}")


def _window_ids() -> list[int]:
    """This process's window numbers, from the macOS window list (CoreGraphics, through ctypes)."""
    cg = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
    cf = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    pointer = ctypes.c_void_p
    cg.CGWindowListCopyWindowInfo.restype = pointer
    cg.CGWindowListCopyWindowInfo.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    cf.CFArrayGetCount.restype = ctypes.c_long
    cf.CFArrayGetCount.argtypes = [pointer]
    cf.CFArrayGetValueAtIndex.restype = pointer
    cf.CFArrayGetValueAtIndex.argtypes = [pointer, ctypes.c_long]
    cf.CFDictionaryGetValue.restype = pointer
    cf.CFDictionaryGetValue.argtypes = [pointer, pointer]
    cf.CFStringCreateWithCString.restype = pointer
    cf.CFStringCreateWithCString.argtypes = [pointer, ctypes.c_char_p, ctypes.c_uint32]
    cf.CFNumberGetValue.restype = ctypes.c_bool
    cf.CFNumberGetValue.argtypes = [pointer, ctypes.c_int, pointer]
    utf8, int64, on_screen_only = 0x08000100, 4, 1

    def number(info: int, key: str) -> int | None:
        value = ctypes.c_int64()
        ref = cf.CFDictionaryGetValue(info, cf.CFStringCreateWithCString(None, key.encode(), utf8))
        return value.value if ref and cf.CFNumberGetValue(ref, int64, ctypes.byref(value)) else None

    windows = cg.CGWindowListCopyWindowInfo(on_screen_only, 0)
    found = []
    for index in range(cf.CFArrayGetCount(windows)):
        info = cf.CFArrayGetValueAtIndex(windows, index)
        if number(info, "kCGWindowOwnerPID") == os.getpid() and number(info, "kCGWindowLayer") == 0:
            window = number(info, "kCGWindowNumber")
            if window is not None:
                found.append(window)
    if not found:
        raise SystemExit("couldn't find the Meowdoku window on screen")
    return found


def _expected_marks(session: GameSession) -> str:
    """The player's marks, as import should read them.

    Solve's gray cats aren't the player's marks, and a ✕ under one is hidden,
    so both are expected to read as empty.
    """
    state = session.state
    hidden = sorted(cell for cell in session.revealed if cell in state.crosses)

    def symbol(cell: Cell) -> str:
        if cell in state.cats:
            return "*"
        if cell in state.crosses and cell not in hidden:
            return "x"
        return "."

    size = state.size
    lines = ["".join(symbol((row, col)) for col in range(size)) for row in range(size)]
    notes = []
    if session.revealed:
        notes.append("# Gray cats are Solve's answer, not the player's marks, so they read as empty.")
    if hidden:
        cells = ", ".join(f"row {row + 1} col {col + 1}" for row, col in hidden)
        notes.append(f"# A ✕ under a gray cat is hidden, so it reads as empty too: {cells}.")
    return "\n".join(notes + lines) + "\n"


def random_marks(seed: int) -> Setup:
    """About 15% cats and 40% ✕ marks, set directly (not judged); not a real game."""

    def setup(session: GameSession) -> None:
        rng = random.Random(seed)
        cats, crosses = set(), set()
        for cell in session.puzzle.cells():
            roll = rng.random()
            if roll < 0.15:
                cats.add(cell)
            elif roll < 0.55:
                crosses.add(cell)
        session.state = BoardState(session.puzzle.size, frozenset(cats), frozenset(crosses))

    return setup


def crosses_then_solve(seed: int) -> Setup:
    """✕ on a quarter of the tiles, some under the answer's cats, then Solve."""

    def setup(session: GameSession) -> None:
        session.reset()
        cells = list(session.puzzle.cells())
        for cell in random.Random(seed).sample(cells, len(cells) // 4):
            session.click(cell)  # one click makes a ✕
        session.solve()

    return setup


def click_cats(*cells: Cell) -> Setup:
    """Place cats as a double-click does, so they're judged: wrong ones become ✕, right ones add ✕ around them."""

    def setup(session: GameSession) -> None:
        for cell in cells:
            session.place_cat(cell)

    return setup


def one_cat_one_cross_then_solve(session: GameSession) -> None:
    click_cats((0, 4))(session)
    session.click((1, 0))  # ✕
    session.solve()


def marks_then_hint(session: GameSession) -> None:
    """Random marks break a rule, so the hint shows a red problem ring."""
    random_marks(5)(session)
    session.hint()


def main() -> None:
    capture("gui-IMG_7117.png", GameSession.from_screenshot(GAME_SCREENSHOT))
    capture("gui-IMG_7117-hint.png", GameSession.from_screenshot(GAME_SCREENSHOT), lambda session: session.hint())
    capture("gui-IMG_7117-solve.jpg", GameSession.from_screenshot(GAME_SCREENSHOT), crosses_then_solve(1), quality=80)
    capture("gui-16x16.jpg", GameSession(random_puzzle(random.Random(16), 16)), random_marks(16), quality=85)
    capture("gui-16x16-solve.jpg", GameSession(random_puzzle(random.Random(0), 16)), crosses_then_solve(1), quality=85)
    capture("gui-5x5-problem.png", GameSession.from_text(EXAMPLE_PUZZLE), marks_then_hint)
    capture("gui-5x5-solve.png", GameSession.from_text(EXAMPLE_PUZZLE), one_cat_one_cross_then_solve)
    capture("gui-5x5-play.png", GameSession.from_text(EXAMPLE_PUZZLE), click_cats((0, 0), (2, 0), (1, 3)))


if __name__ == "__main__":
    main()
