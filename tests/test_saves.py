"""Saved games: the format, and refusing saves that can't be trusted (R11.7a, R11.8)."""

import json
from pathlib import Path
from typing import Any

import pytest

from meowdoku.game import GameSession
from meowdoku.saves import SAVE_VERSION, SaveError, from_save, to_save
from meowdoku.state import BoardState

FIXTURES = Path(__file__).parent / "fixtures"
EXAMPLE = "AABBB\nACCCB\nACDDB\nEEDDB\nEEEBB"


def played() -> GameSession:
    session = GameSession.from_text(EXAMPLE)
    session.state = BoardState(5, frozenset({(0, 4)}), frozenset({(0, 0), (2, 2)}))
    return session


def test_r11_8_save_holds_the_puzzle_colors_and_marks() -> None:
    session = played()
    data = to_save(session)
    assert data == {
        "version": SAVE_VERSION,
        "grid": EXAMPLE,
        "colors": dict(session.colors),
        "cats": [[0, 4]],
        "crosses": [[0, 0], [2, 2]],
    }
    assert json.loads(json.dumps(data)) == data  # plain JSON


def test_r11_8_opening_a_save_gives_back_the_same_game() -> None:
    session = played()
    again = from_save(to_save(session), "ja")
    assert again.puzzle == session.puzzle
    assert again.colors == session.colors
    assert again.state == session.state
    assert again.language == "ja"
    assert not again.can_undo  # undo history isn't saved


def test_r11_8_a_screenshot_game_keeps_its_colors() -> None:
    session = GameSession.from_screenshot(FIXTURES / "screenshots" / "IMG_7117.PNG")
    again = from_save(json.loads(json.dumps(to_save(session))))
    assert again.colors == session.colors
    assert again.state == session.state


def broken(**changes: Any) -> dict[str, Any]:
    data = to_save(played())
    data.update(changes)
    return {key: value for key, value in data.items() if value is not None}


@pytest.mark.parametrize(
    "data",
    [
        "not a save",
        broken(version=2),
        broken(version=None),
        broken(grid="AAB\nABB"),  # not square
        broken(grid="AAAAA\nAAAAA\nAAAAA\nAAAAA\nAAAAA"),  # one region
        broken(colors={"A": "#ffffff"}),
        broken(colors={label: "pink" for label in "ABCDE"}),
        broken(cats=[[0, 9]]),  # off the board
        broken(cats=[[0, 0]], crosses=[[0, 0]]),  # both a cat and a cross
        broken(cats=[["0", "4"]]),
        broken(crosses=None),
    ],
)
def test_r11_8_a_bad_save_is_refused(data: object) -> None:
    with pytest.raises(SaveError):
        from_save(data)


def test_r12_1_a_bad_save_is_reported_in_the_players_language() -> None:
    with pytest.raises(SaveError) as error:
        from_save(broken(version=99))
    assert error.value.text("zh-TW") == "無法開啟你儲存的遊戲，所以開始了新的一局。"
    assert "version" in error.value.reason
