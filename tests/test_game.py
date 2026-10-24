"""Game session logic behind the GUI, tested without a display (R8.7)."""

from pathlib import Path

import pytest

from meowdoku.game import (
    PALETTE,
    SOLVED_MESSAGE,
    GameSession,
    Highlight,
    crossed_out_by,
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


def start_with_cats(session: GameSession, *cats: tuple[int, int]) -> None:
    """Cats loaded as from a screenshot: not judged, so they may be wrong (R9.1a)."""
    session.state = BoardState(session.puzzle.size, frozenset(cats))


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
    session.click((1, 2))
    assert session.state.mark_at((1, 2)) is Mark.CROSS
    session.click((1, 2))
    assert session.state.mark_at((1, 2)) is Mark.CAT
    session.click((1, 2))
    assert session.state.is_open((1, 2))


def test_click_hides_hint_but_keeps_shown_solution() -> None:
    session = new_session()
    session.solve()
    session.hint()
    session.click((0, 0))
    assert session.highlight == frozenset()
    assert not session.hint_shown
    assert session.revealed == set(EXAMPLE_SOLUTION)


# R8.9 Placed cats are judged against the solution


def test_r8_9_wrong_cat_becomes_a_cross() -> None:
    session = new_session()
    place_cat(session, (0, 0))
    assert session.state.mark_at((0, 0)) is Mark.CROSS
    assert session.state.cats == frozenset()
    assert session.message == "No cat at row 1, column 1, so it's marked ✕."


def test_r8_9_a_wrong_cat_is_rejected_again() -> None:
    """The cell can't hold a cat, so the next click tries a cat and it stays ✕."""
    session = new_session()
    place_cat(session, (0, 0))
    session.click((0, 0))
    assert session.state.mark_at((0, 0)) is Mark.CROSS


def test_r8_9_correct_cat_crosses_its_row_column_region_and_neighbors() -> None:
    session = new_session()
    place_cat(session, (2, 0))
    assert session.state.cats == {(2, 0)}
    assert session.state.crosses == crossed_out_by(session.puzzle, (2, 0))


def test_r8_9_crossed_out_cells() -> None:
    """Row 3, column 1, region A (rows 1-3 of column 1, plus (0, 1)), and the cells touching (2, 0)."""
    puzzle = Puzzle.from_rows(["AABBB", "ACCCB", "ACDDB", "EEDDB", "EEEBB"])
    row = {(2, 1), (2, 2), (2, 3), (2, 4)}
    column = {(0, 0), (1, 0), (3, 0), (4, 0)}
    region = {(0, 1)}
    touching = {(1, 1), (3, 1)}
    assert crossed_out_by(puzzle, (2, 0)) == row | column | region | touching


def test_r8_9_auto_crosses_never_replace_cats() -> None:
    session = new_session()
    start_with_cats(session, (2, 2))  # wrong, but loaded from a screenshot
    place_cat(session, (2, 0))
    assert session.state.cats == {(2, 0), (2, 2)}


def test_r8_9_cats_are_judged_against_the_first_solution() -> None:
    """This board has two solutions; (0, 1) is in the first, (0, 2) only in the other."""
    session = new_session("ABCD\nABCD\nABCD\nABCD")
    assert (0, 1) in session.solve_result.solutions[0].cats
    place_cat(session, (0, 2))
    assert session.state.mark_at((0, 2)) is Mark.CROSS
    place_cat(session, (0, 1))
    assert (0, 1) in session.state.cats


def test_r8_9_no_judging_without_a_solution() -> None:
    session = new_session("AB\nAB")
    place_cat(session, (0, 0))
    assert session.state.cats == {(0, 0)}


# R8.5 Buttons


def test_r8_5_hint_highlights_and_explains_without_marking() -> None:
    session = new_session()
    session.hint()
    assert session.state == BoardState.empty(5)
    assert session.highlight_style is Highlight.HINT
    assert session.highlight == {(0, 4), (1, 4), (2, 4), (3, 4), (4, 4)}
    assert session.message.startswith("The cat must be in the pink region in this column")


def test_r8_5_hint_on_mistake_uses_problem_highlight() -> None:
    session = new_session()
    start_with_cats(session, (0, 0))
    session.hint()
    assert session.highlight_style is Highlight.PROBLEM
    assert session.highlight == {(0, 0)}


def test_r8_5_hint_again_hides_it() -> None:
    session = new_session()
    session.hint()
    session.hint()
    assert session.message == ""
    assert session.highlight == frozenset()
    assert session.highlight_style is None
    session.hint()
    assert session.message.startswith("The cat must be in the pink region")


def test_r8_5_check_with_no_problems() -> None:
    session = new_session()
    start_with_cats(session, (0, 0))
    session.check()
    assert session.message == "No rules broken so far."
    assert session.highlight_style is None


def test_r8_5_check_highlights_broken_rules() -> None:
    session = new_session()
    start_with_cats(session, (0, 0), (1, 1))
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


def test_r8_5_solve_again_hides_the_answer_and_keeps_the_marks() -> None:
    session = new_session()
    place_cat(session, (2, 0))
    marks = session.state
    session.solve()
    session.solve()
    assert session.revealed == frozenset()
    assert session.message == ""
    assert session.state == marks
    session.solve()
    assert session.revealed == set(EXAMPLE_SOLUTION)


def test_r8_5_solution_stays_while_playing() -> None:
    session = new_session()
    session.solve()
    place_cat(session, (4, 1))
    assert session.revealed == set(EXAMPLE_SOLUTION)
    assert (4, 1) in session.state.cats


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
    session.solve()
    session.hint()
    session.reset()
    assert session.state == BoardState.empty(5)
    assert session.revealed == frozenset()
    assert session.highlight == frozenset()
    assert session.message == ""


# R7.8 Regions are named by color in the GUI


def test_r7_8_hint_names_regions_by_color() -> None:
    session = new_session()
    session.hint()
    assert session.message == (
        "The cat must be in the pink region in this column, so cross out the rest of the pink region."
    )


def test_r7_8_check_names_regions_by_color() -> None:
    session = new_session()
    start_with_cats(session, (0, 1), (2, 0))
    session.check()
    assert session.message == "1 problem: the light green region has 2 cats; it needs exactly one."


# R8.6 Solved


def test_r8_6_completing_the_board_shows_solved() -> None:
    session = new_session()
    for cell in EXAMPLE_SOLUTION:
        assert not session.is_solved
        place_cat(session, cell)
    assert session.is_solved
    assert session.message == SOLVED_MESSAGE


# Opening files (R8.5): screenshots only


def test_text_puzzle_files_are_not_accepted(tmp_path: Path) -> None:
    path = tmp_path / "puzzle.txt"
    path.write_text("AB\nAB\n", encoding="utf-8")
    with pytest.raises(MeowdokuError, match="is not a screenshot"):
        GameSession.from_screenshot(path)


def test_missing_screenshot_raises_os_error(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        GameSession.from_screenshot(tmp_path / "missing.png")
