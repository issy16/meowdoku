"""Game session logic behind the GUI, tested without a display (R8.7)."""

from pathlib import Path

import pytest

from meowdoku.game import (
    PALETTE,
    SOLVED_MESSAGE,
    GameSession,
    Highlight,
    default_region_colors,
    next_mark,
)
from meowdoku.puzzle import MAX_SIZE, MeowdokuError, Puzzle
from meowdoku.state import BoardState, Mark

EXAMPLE_TEXT = "AABBB\nACCCB\nACDDB\nEEDDB\nEEEBB"
EXAMPLE_SOLUTION = [(0, 4), (1, 2), (2, 0), (3, 3), (4, 1)]


def new_session(text: str = EXAMPLE_TEXT) -> GameSession:
    return GameSession.from_text(text)


def place_cat(session: GameSession, cell: tuple[int, int]) -> None:
    """Two clicks: empty → ✕ → cat."""
    session.click(cell)
    session.click(cell)


# R8.3 Colors


def test_r8_3_palette_has_a_distinct_color_for_every_region() -> None:
    assert len(PALETTE) >= MAX_SIZE
    assert len(set(PALETTE)) == len(PALETTE)


def test_r8_3_colors_follow_first_appearance() -> None:
    puzzle = Puzzle.from_rows(["BBA", "CBA", "CCA"])
    assert default_region_colors(puzzle) == {"B": PALETTE[0], "A": PALETTE[1], "C": PALETTE[2]}


def test_custom_colors_are_kept() -> None:
    colors = {"A": "#000000", "B": "#ffffff"}
    session = GameSession(Puzzle.from_rows(["AB", "AB"]), colors)
    assert session.colors == colors


# R8.4 Clicking


def test_r8_4_click_cycles_empty_cross_cat_empty() -> None:
    assert next_mark(None) is Mark.CROSS
    assert next_mark(Mark.CROSS) is Mark.CAT
    assert next_mark(Mark.CAT) is None


def test_r8_4_click_changes_the_cell() -> None:
    session = new_session()
    session.click((1, 1))
    assert session.state.mark_at((1, 1)) is Mark.CROSS
    session.click((1, 1))
    assert session.state.mark_at((1, 1)) is Mark.CAT
    session.click((1, 1))
    assert session.state.is_open((1, 1))


def test_click_clears_hint_and_shown_solution() -> None:
    session = new_session()
    session.hint()
    session.solve()
    session.click((0, 0))
    assert session.highlight == frozenset()
    assert session.revealed == frozenset()
    assert session.message == ""


# R8.5 Buttons


def test_r8_5_hint_highlights_and_explains_without_marking() -> None:
    session = new_session()
    session.hint()
    assert session.state == BoardState.empty(5)
    assert session.highlight_style is Highlight.HINT
    assert session.highlight == {(0, 4), (1, 4), (2, 4), (3, 4), (4, 4)}
    assert session.message.startswith("Every cell left in column 5 is in region 'B'")


def test_r8_5_hint_on_mistake_uses_problem_highlight() -> None:
    session = new_session()
    place_cat(session, (0, 0))
    session.hint()
    assert session.highlight_style is Highlight.PROBLEM
    assert session.highlight == {(0, 0)}


def test_r8_5_check_with_no_problems() -> None:
    session = new_session()
    place_cat(session, (0, 0))
    session.check()
    assert session.message == "No rules broken so far."
    assert session.highlight_style is None


def test_r8_5_check_highlights_broken_rules() -> None:
    session = new_session()
    place_cat(session, (0, 0))
    place_cat(session, (1, 1))
    session.check()
    assert session.highlight_style is Highlight.PROBLEM
    assert session.highlight == {(0, 0), (1, 1)}
    assert session.message.startswith("1 problem: cats at row 1, column 1 and row 2, column 2 touch")


def test_r8_5_solve_shows_unique_solution_without_marking() -> None:
    session = new_session()
    session.click((2, 2))
    session.solve()
    assert session.revealed == set(EXAMPLE_SOLUTION)
    assert session.state.crosses == {(2, 2)}
    assert session.message == "Here is the solution."


def test_r8_5_solve_notes_several_solutions() -> None:
    session = new_session("ABCD\nABCD\nABCD\nABCD")
    session.solve()
    assert session.revealed == {(0, 1), (1, 3), (2, 0), (3, 2)}
    assert session.message == "This puzzle has more than one solution. Here is one of them."


def test_r8_5_solve_notes_no_solution() -> None:
    session = new_session("AB\nAB")
    session.solve()
    assert session.revealed == frozenset()
    assert session.message == "This puzzle has no solution."


def test_r8_5_reset_clears_everything() -> None:
    session = new_session()
    place_cat(session, (0, 0))
    session.hint()
    session.reset()
    assert session.state == BoardState.empty(5)
    assert session.highlight == frozenset()
    assert session.message == ""


# R8.6 Solved


def test_r8_6_completing_the_board_shows_solved() -> None:
    session = new_session()
    for cell in EXAMPLE_SOLUTION:
        assert not session.is_solved
        place_cat(session, cell)
    assert session.is_solved
    assert session.message == SOLVED_MESSAGE


# Opening files


def test_from_file_loads_puzzle(tmp_path: Path) -> None:
    path = tmp_path / "puzzle.txt"
    path.write_text("AB\nAB\n", encoding="utf-8")
    assert GameSession.from_file(path).puzzle == Puzzle.from_rows(["AB", "AB"])


def test_from_file_errors_are_meowdoku_or_os_errors(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        GameSession.from_file(tmp_path / "missing.txt")
    bad = tmp_path / "bad.txt"
    bad.write_text("AA\nAA", encoding="utf-8")
    with pytest.raises(MeowdokuError):
        GameSession.from_file(bad)
