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
    """Rows of [label key, its details, milliseconds or a label key], as JSON (R12.1).

    The page words each row in the chosen language from labels.json.
    """
    rows: list[list[object]] = []
    start = time.perf_counter()
    session = GameSession.from_screenshot(Path(path))
    rows.append(["timing.import", {}, _ms(start)])
    session.state = type(session.state).empty(session.puzzle.size)

    start = time.perf_counter()
    session.solve_result
    rows.append(["timing.solve", {}, _ms(start)])

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
        rows.append(["timing.first_hint", {}, hint_times[0]])
        rows.append(["timing.slowest", {"n": len(hint_times)}, max(hint_times)])
        rows.append(["timing.all_hints", {}, sum(hint_times)])
    rows.append(["timing.slowest_d6", {}, max(d6_times) if d6_times else "timing.none_needed"])
    rows.append(["timing.solved_by_hints", {}, "timing.yes" if session.is_solved else "timing.no"])
    return json.dumps(rows)


def _ms(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)
