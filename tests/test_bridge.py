"""The web bridge: JSON actions in, a plain board description out (R11.2)."""

import json
from pathlib import Path
from typing import Any

from meowdoku.bridge import Bridge
from meowdoku.game import EXAMPLE_PUZZLE, GameSession

FIXTURES = Path(__file__).parent / "fixtures"
EXAMPLE_SOLUTION = [[0, 4], [1, 2], [2, 0], [3, 3], [4, 1]]


def act(bridge: Bridge, action: str, *args: Any) -> dict[str, Any]:
    return json.loads(bridge.handle(json.dumps({"action": action, "args": list(args)})))


def test_r11_2_view_describes_the_example_board() -> None:
    view = act(Bridge(), "view")
    assert view["size"] == 5
    assert view["regions"] == EXAMPLE_PUZZLE.split("\n")
    assert set(view["colors"]) == set("ABCDE")
    assert view["cats"] == view["crosses"] == view["highlight"] == []
    assert view["error"] is None
    assert not view["can_undo"] and not view["can_apply"]


def test_r11_2_view_is_plain_json_data() -> None:
    """Only dicts, lists, strings, numbers, booleans, and None cross to JavaScript."""

    def plain(value: Any) -> bool:
        if isinstance(value, dict):
            return all(isinstance(key, str) and plain(item) for key, item in value.items())
        if isinstance(value, list):
            return all(plain(item) for item in value)
        return value is None or isinstance(value, (str, int, float, bool))

    bridge = Bridge()
    act(bridge, "double", 0, 4)
    act(bridge, "hint")
    assert plain(bridge.view())


def test_r11_2_press_and_release_on_one_cell_is_a_click() -> None:
    bridge = Bridge()
    act(bridge, "press", 1, 1)
    view = act(bridge, "release", 1, 1)
    assert view["crosses"] == [[1, 1]]
    assert view["can_undo"]


def test_r11_2_release_on_another_cell_without_a_drag_does_nothing() -> None:
    bridge = Bridge()
    act(bridge, "press", 1, 1)
    assert act(bridge, "release", 2, 2)["crosses"] == []


def test_r11_2_drag_marks_skipped_cells_as_one_move() -> None:
    """R8.10: a fast drag fills in the cells between; R8.13: the drag is one move."""
    bridge = Bridge()
    act(bridge, "press", 0, 0)
    act(bridge, "move", 0, 0)
    act(bridge, "move", 0, 3)
    view = act(bridge, "release", 0, 3)
    assert view["crosses"] == [[0, 0], [0, 1], [0, 2], [0, 3]]
    assert act(bridge, "previous")["crosses"] == []


def test_r11_2_double_places_a_judged_cat() -> None:
    """R8.9: a correct cat locks and crosses out its row, column, region, and neighbors."""
    bridge = Bridge()
    act(bridge, "press", 0, 4)
    act(bridge, "release", 0, 4)  # a double tap's first tap is a click
    view = act(bridge, "double", 0, 4)
    assert view["cats"] == view["locked"] == [[0, 4]]
    assert [0, 0] in view["crosses"]


def test_r11_2_wrong_cat_shakes() -> None:
    view = act(Bridge(), "double", 0, 0)
    assert view["shake"] == [0, 0]
    assert view["cats"] == []
    assert view["crosses"] == [[0, 0]]


def test_r11_2_hint_and_apply_match_the_session() -> None:
    """R8.11: Apply makes the shown hint's move, the same as GameSession does."""
    bridge = Bridge()
    session = GameSession.from_text(EXAMPLE_PUZZLE)
    view = act(bridge, "hint")
    session.hint()
    assert view["message"] == session.message
    assert view["highlight"] == sorted([list(cell) for cell in session.highlight])
    assert view["highlight_style"] == "hint"
    assert view["can_apply"]
    view = act(bridge, "apply")
    session.apply_hint()
    assert view["crosses"] == sorted([list(cell) for cell in session.state.crosses])
    assert view["cats"] == sorted([list(cell) for cell in session.state.cats])
    assert view["message"] == ""


def test_r11_2_solve_shows_the_first_solution_without_changing_marks() -> None:
    view = act(Bridge(), "solve")
    assert view["solution"] == EXAMPLE_SOLUTION
    assert view["cats"] == []


def test_r11_2_solving_move_reports_just_solved() -> None:
    bridge = Bridge()
    for row, col in EXAMPLE_SOLUTION:
        view = act(bridge, "double", row, col)
    assert view["just_solved"]
    assert not act(bridge, "hint")["just_solved"]


def test_r11_2_previous_and_next_undo_and_redo() -> None:
    bridge = Bridge()
    act(bridge, "press", 2, 2)
    act(bridge, "release", 2, 2)
    view = act(bridge, "previous")
    assert view["crosses"] == [] and view["can_redo"]
    assert act(bridge, "next")["crosses"] == [[2, 2]]


def test_r11_2_reset_clears_the_board() -> None:
    bridge = Bridge()
    act(bridge, "double", 0, 4)
    view = act(bridge, "reset")
    assert view["cats"] == view["crosses"] == []


def test_r11_5_open_reads_a_screenshot() -> None:
    path = FIXTURES / "screenshots" / "IMG_7117.PNG"
    view = act(Bridge(), "open", str(path))
    session = GameSession.from_screenshot(path)
    assert view["error"] is None
    assert view["regions"] == ["".join(row) for row in session.puzzle.regions]
    assert view["colors"] == dict(session.colors)
    assert view["crosses"] == sorted([list(cell) for cell in session.state.crosses])


def test_r8_8_unreadable_file_is_an_error_and_keeps_the_game() -> None:
    bridge = Bridge()
    act(bridge, "double", 0, 4)
    view = act(bridge, "open", str(FIXTURES / "screenshots" / "IMG_7117.txt"))
    assert view["error"]
    assert view["cats"] == [[0, 4]]


def test_r11_2_bad_requests_are_errors_not_crashes() -> None:
    bridge = Bridge()
    assert "bad request" in json.loads(bridge.handle(json.dumps({"action": "fly"})))["error"]
    assert "bad request" in json.loads(bridge.handle("not json"))["error"]
    assert "bad request" in act(bridge, "press", 1)["error"]
