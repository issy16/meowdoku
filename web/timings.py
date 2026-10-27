"""Prototype measurements for R11.12, run by the web worker in the browser.

Times a screenshot import, the first Solve, and every hint from an empty
board until the puzzle is solved by Apply, noting the slowest and any D6
hint. Not part of the game: the page shows the results in its Timings panel.
"""

import json
import time
from pathlib import Path

from meowdoku.game import GameSession


def measure(path: str) -> str:
    """Rows of [what, milliseconds or text], as JSON."""
    rows: list[list[object]] = []
    start = time.perf_counter()
    session = GameSession.from_screenshot(Path(path))
    rows.append(["Screenshot import", _ms(start)])
    session.state = type(session.state).empty(session.puzzle.size)

    start = time.perf_counter()
    session.solve_result
    rows.append(["Solve (first time)", _ms(start)])

    hint_times: list[int] = []
    d6_times: list[int] = []
    while not session.is_solved:
        start = time.perf_counter()
        session.hint()
        elapsed = _ms(start)
        hint_times.append(elapsed)
        if session.can_show_me:
            d6_times.append(elapsed)
        if session.applicable is None:
            break
        session.apply_hint()
    if hint_times:
        rows.append(["First hint", hint_times[0]])
        rows.append([f"Slowest of {len(hint_times)} hints", max(hint_times)])
        rows.append(["All hints to solve", sum(hint_times)])
    rows.append(["Slowest D6 hint", max(d6_times) if d6_times else "none needed"])
    rows.append(["Solved by hints alone", "yes" if session.is_solved else "no"])
    return json.dumps(rows)


def _ms(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)
