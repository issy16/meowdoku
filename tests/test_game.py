"""Game session logic behind the GUI, tested without a display (R8.7)."""

from pathlib import Path

import pytest

from meowdoku.game import (
    PALETTE,
    GameSession,
    Highlight,
    crossed_out_by,
    default_region_colors,
    next_mark,
    walkthrough,
)
from meowdoku.puzzle import MAX_SIZE, MeowdokuError, Puzzle
from meowdoku.state import BoardState, Mark

from helpers import apply_deduction

FIXTURES = Path(__file__).parent / "fixtures"
EXAMPLE_TEXT = "AABBB\nACCCB\nACDDB\nEEDDB\nEEEBB"
EXAMPLE_SOLUTION = [(0, 4), (1, 2), (2, 0), (3, 3), (4, 1)]


def new_session(text: str = EXAMPLE_TEXT) -> GameSession:
    return GameSession.from_text(text)


def place_cat(session: GameSession, cell: tuple[int, int]) -> None:
    """What a double-click does."""
    session.place_cat(cell)


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


def test_r8_4_click_toggles_cross_and_clears_cats() -> None:
    assert next_mark(None) is Mark.CROSS
    assert next_mark(Mark.CROSS) is None
    assert next_mark(Mark.CAT) is None


def test_r8_4_click_on_a_cross_uncrosses_it() -> None:
    session = new_session()
    session.click((0, 0))
    assert session.state.mark_at((0, 0)) is Mark.CROSS
    session.click((0, 0))
    assert session.state.is_open((0, 0))
    assert session.shake is None


def test_r8_4_place_cat_replaces_a_cross() -> None:
    session = new_session()
    session.click((1, 2))
    place_cat(session, (1, 2))
    assert session.state.mark_at((1, 2)) is Mark.CAT


def test_r8_4_a_correct_cat_is_locked() -> None:
    session = new_session()
    place_cat(session, (1, 2))
    marks = session.state
    session.click((1, 2))
    assert session.state == marks
    assert session.is_locked((1, 2))


def test_r8_4_wrong_cats_from_a_screenshot_are_not_locked() -> None:
    session = new_session()
    start_with_cats(session, (0, 0), (1, 2))
    assert not session.is_locked((0, 0))
    assert session.is_locked((1, 2))
    session.click((0, 0))
    assert session.state.is_open((0, 0))


def test_click_hides_hint_but_keeps_shown_solution() -> None:
    session = new_session()
    session.solve()
    session.hint()
    session.click((0, 0))
    assert session.highlight == frozenset()
    assert not session.hint_shown
    assert session.revealed == set(EXAMPLE_SOLUTION)


# R8.11 Applying a hint


def test_r8_11_apply_crosses_out_what_the_hint_rules_out() -> None:
    session = new_session()
    session.hint()  # D3: the pink region's cat is in column 5
    assert session.applicable is not None
    session.apply_hint()
    assert session.state.crosses == {(0, 2), (0, 3), (4, 3)}
    assert not session.hint_shown
    assert session.applicable is None


def test_r8_11_apply_places_the_cat_and_judges_it() -> None:
    """Row 1 has one cell left, so the hint places its cat; a correct cat locks and fills in ✕."""
    session = new_session()
    session.state = BoardState(5, crosses=frozenset({(0, 0), (0, 1), (0, 2), (0, 3)}))
    session.hint()
    assert session.message == "This row has only 1 cell left."
    session.apply_hint()
    assert session.state.cats == {(0, 4)}
    assert session.is_locked((0, 4))
    assert crossed_out_by(session.puzzle, (0, 4)) <= session.state.crosses


def test_r8_11_apply_works_for_a_d6_hint() -> None:
    """R7.9: on this board only D6 finds a step, a cat at (1, 1) leading nowhere."""
    session = new_session("ABCD\nABCD\nABCD\nABCD")
    session.hint()
    assert session.message.startswith("If this cell had a cat, ")
    session.apply_hint()
    assert session.state.crosses == {(1, 1)}


def test_r8_11_mistakes_have_nothing_to_apply() -> None:
    session = new_session()
    start_with_cats(session, (0, 0))
    session.hint()
    assert session.highlight_style is Highlight.PROBLEM
    assert session.applicable is None
    marks = session.state
    session.apply_hint()
    assert session.state == marks


def test_r8_11_apply_can_finish_the_puzzle() -> None:
    session = new_session()
    for cell in EXAMPLE_SOLUTION[:-1]:
        place_cat(session, cell)
    session.hint()
    session.apply_hint()
    assert session.is_solved
    assert session.just_solved


# R8.10 Dragging marks or unmarks


def test_r8_10_paint_from_an_empty_cell_marks_empty_cells_only() -> None:
    session = new_session()
    start_with_cats(session, (2, 2))
    session.begin_paint((2, 0))
    for cell in [(2, 1), (2, 2), (2, 3)]:
        session.paint(cell)
    session.end_paint()
    assert session.state.crosses == {(2, 0), (2, 1), (2, 3)}
    assert session.state.cats == {(2, 2)}


def test_r8_10_paint_from_a_cross_clears_crosses() -> None:
    session = new_session()
    session.state = BoardState(5, crosses=frozenset({(1, 1), (1, 2), (1, 3)}))
    session.begin_paint((1, 1))
    session.paint((1, 2))
    assert session.state.crosses == {(1, 3)}


def test_r8_10_unmarking_keeps_crosses_a_correct_cat_rules_out() -> None:
    """The cat at (2, 0) is correct; its ✕ marks stay, even one the player placed before it."""
    session = new_session()
    session.click((2, 4))  # the player's own ✕, in the cat's row
    place_cat(session, (2, 0))
    session.click((1, 3))  # a ✕ the cat doesn't rule out
    session.begin_paint((1, 3))
    for cell in [(2, 4), (2, 3), (1, 1), (1, 3)]:
        session.paint(cell)
    assert session.state.crosses == crossed_out_by(session.puzzle, (2, 0))
    assert session.is_protected((2, 4))
    assert not session.is_protected((1, 3))


def test_r8_10_a_drag_from_a_cat_changes_nothing() -> None:
    session = new_session()
    place_cat(session, (2, 0))
    marks = session.state
    session.begin_paint((2, 0))
    session.paint((3, 2))
    assert session.state == marks
    assert session.painting is None


def test_r8_10_painting_hides_a_hint() -> None:
    session = new_session()
    session.hint()
    session.begin_paint((3, 0))
    assert not session.hint_shown
    assert session.message == ""


# R8.9 Placed cats are judged against the solution


def test_r8_9_wrong_cat_becomes_a_cross() -> None:
    session = new_session()
    place_cat(session, (0, 0))
    assert session.state.mark_at((0, 0)) is Mark.CROSS
    assert session.state.cats == frozenset()
    assert session.shake == (0, 0)
    assert session.message == ""


def test_r8_9_shake_ends_with_the_next_action() -> None:
    session = new_session()
    place_cat(session, (0, 0))
    session.click((4, 4))
    assert session.shake is None


def test_r8_9_a_correct_cat_does_not_shake() -> None:
    session = new_session()
    place_cat(session, (2, 0))
    assert session.shake is None


def test_r8_9_the_cross_left_by_a_wrong_cat_clears_with_a_click() -> None:
    session = new_session()
    place_cat(session, (0, 0))
    session.click((0, 0))
    assert session.state.is_open((0, 0))


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


def test_r8_5_check_is_gone() -> None:
    """Removed at the owner's request; Hint still points out broken rules in red."""
    assert not hasattr(GameSession, "check")


# R8.13 Previous and Next undo and redo the player's moves


def test_r8_13_previous_undoes_and_next_redoes_a_click() -> None:
    session = new_session()
    assert not session.can_undo
    session.click((0, 0))
    session.undo()
    assert session.state == BoardState.empty(5)
    assert session.can_redo
    session.redo()
    assert session.state.crosses == {(0, 0)}
    assert not session.can_redo


def test_r8_13_a_cat_and_its_crosses_are_one_move() -> None:
    session = new_session()
    place_cat(session, (2, 0))
    session.undo()
    assert session.state == BoardState.empty(5)
    assert not session.can_undo


def test_r8_13_a_whole_drag_is_one_move() -> None:
    session = new_session()
    session.begin_paint((3, 0))
    for cell in [(3, 1), (3, 2), (3, 3)]:
        session.paint(cell)
    session.end_paint()
    assert len(session.undo_states) == 1
    session.undo()
    assert session.state == BoardState.empty(5)


def test_r8_13_reset_can_be_undone() -> None:
    session = new_session()
    place_cat(session, (2, 0))
    marks = session.state
    session.reset()
    session.undo()
    assert session.state == marks


def test_r8_13_applying_and_stepping_are_moves() -> None:
    session = new_session()
    session.hint()
    session.apply_hint()
    session.step()
    session.step()  # Next Step makes the shown step's move
    assert len(session.undo_states) == 2
    session.undo()
    session.undo()
    assert session.state == BoardState.empty(5)


def test_r8_13_a_new_move_ends_redo() -> None:
    session = new_session()
    session.click((0, 0))
    session.undo()
    session.click((4, 4))
    assert not session.can_redo


def test_r8_13_moves_that_change_nothing_are_not_recorded() -> None:
    session = new_session()
    place_cat(session, (2, 0))
    session.click((2, 0))  # a locked cat: nothing happens
    session.begin_paint((2, 0))  # a drag from a cat paints nothing
    session.paint((4, 4))
    session.end_paint()
    assert len(session.undo_states) == 1


def test_r8_13_undo_hides_a_hint_and_ends_stepping() -> None:
    session = new_session()
    session.click((0, 0))
    session.step()
    session.undo()
    assert not session.stepping
    assert not session.hint_shown


def test_r8_13_redoing_the_solving_move_shows_no_pop_up() -> None:
    session = new_session()
    for cell in EXAMPLE_SOLUTION:
        place_cat(session, cell)
    session.undo()
    assert not session.is_solved
    session.redo()
    assert session.message == ""  # the pop-up is the only notice (R8.6)
    assert not session.just_solved


# R8.12 Step by Step


def test_r8_12_first_press_shows_step_one_without_marking() -> None:
    session = new_session()
    session.step()
    assert session.stepping
    assert session.message.startswith("Step 1: The cat must be in the pink region")
    assert session.highlight_style is Highlight.HINT
    assert session.state == BoardState.empty(5)


def test_r8_12_next_applies_the_step_and_shows_the_next() -> None:
    session = new_session()
    session.step()
    session.step()
    assert session.state.crosses == {(0, 2), (0, 3), (4, 3)}
    assert session.stepping
    assert session.message.startswith("Step 2: ")


def test_r8_12_stepping_to_the_end_solves_the_puzzle() -> None:
    session = new_session()
    presses = 0
    session.step()
    while session.stepping:
        session.step()
        presses += 1
        assert presses < 50
    assert session.is_solved
    assert session.just_solved
    assert session.message == ""  # the pop-up is the only notice (R8.6)


def test_r8_12_stops_when_no_step_is_left() -> None:
    session = new_session("\n".join(["ABCDEF"] * 6))  # 90 solutions, no step even D6 can prove
    session.step()
    assert not session.stepping
    assert session.message == "No simple step found; try Solve."


def test_r8_12_stops_at_a_mistake() -> None:
    session = new_session()
    start_with_cats(session, (0, 0))
    session.step()
    assert not session.stepping
    assert session.highlight_style is Highlight.PROBLEM


def test_r8_12_clicking_a_cell_ends_stepping() -> None:
    session = new_session()
    session.step()
    session.click((4, 4))
    assert not session.stepping
    session.step()
    assert session.message.startswith("Step 1: ")


def test_r8_5_solve_shows_unique_solution_without_marking() -> None:
    session = new_session()
    session.click((2, 2))
    session.solve()
    assert session.revealed == set(EXAMPLE_SOLUTION)
    assert session.state.crosses == {(2, 2)}
    assert session.message == ""


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


def test_r8_5_solve_shows_one_of_several_solutions_quietly() -> None:
    session = new_session("ABCD\nABCD\nABCD\nABCD")
    session.solve()
    assert session.revealed == {(0, 1), (1, 3), (2, 0), (3, 2)}
    assert session.message == ""


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


# R8.6 Solved


def test_r8_6_completing_the_board_shows_solved() -> None:
    session = new_session()
    for cell in EXAMPLE_SOLUTION:
        assert not session.is_solved
        place_cat(session, cell)
    assert session.is_solved
    assert session.message == ""  # the pop-up is the only notice (R8.6)
    assert session.just_solved


def test_r8_6_pop_up_only_on_the_click_that_solves() -> None:
    session = new_session()
    for cell in EXAMPLE_SOLUTION[:-1]:
        place_cat(session, cell)
        assert not session.just_solved
    place_cat(session, EXAMPLE_SOLUTION[-1])
    assert session.just_solved
    session.hint()
    assert not session.just_solved


# Opening files (R8.5): screenshots only


def test_text_puzzle_files_are_not_accepted(tmp_path: Path) -> None:
    path = tmp_path / "puzzle.txt"
    path.write_text("AB\nAB\n", encoding="utf-8")
    with pytest.raises(MeowdokuError, match="is not a screenshot"):
        GameSession.from_screenshot(path)


def test_missing_screenshot_raises_os_error(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        GameSession.from_screenshot(tmp_path / "missing.png")


# R8.14 Show me

STRIPES_TEXT = "ABCD\nABCD\nABCD\nABCD"  # only D6 finds a step: a cat at (1, 1) leads nowhere
SIX_TEXT = "DDDDDE\nDDDDDE\nCFDDEE\nCFABBE\nCFABBB\nCCAABB"
# On this board D6's hint places a cat at (3, 4): with no cat there, a column ends up empty.
SIX_CROSSES = [(0, 0), (0, 1), (0, 4), (1, 0), (1, 1), (1, 4), (2, 2), (2, 3), (2, 4), (3, 0), (3, 2), (3, 3)]
SIX_CROSSES += [(4, 3), (4, 5), (5, 1), (5, 5)]


def d6_session(text: str = STRIPES_TEXT, crosses: list[tuple[int, int]] | None = None) -> GameSession:
    session = new_session(text)
    if crosses:
        session.state = BoardState(session.puzzle.size, crosses=frozenset(crosses))
    session.hint()
    assert session.can_show_me
    return session


def test_r8_14_walkthrough_has_one_frame_per_line_of_the_explanation() -> None:
    session = d6_session()
    assert session.applicable is not None and session.applicable.deduction is not None
    deduction = session.applicable.deduction
    frames = walkthrough(session.puzzle, session.state, deduction)
    assert [frame.caption for frame in frames] == list(deduction.steps)


def test_r8_14_walkthrough_replays_the_assumption_and_its_steps() -> None:
    session = d6_session()
    deduction = session.applicable.deduction  # type: ignore[union-attr]
    player = session.state
    look, suppose, *steps, breaks, follows = walkthrough(session.puzzle, player, deduction)

    assert look.state == player and not look.what_if and look.ring == {(1, 1)}
    assert suppose.state == player.with_mark((1, 1), Mark.CAT)
    assert suppose.what_if == {(1, 1)}

    board = suppose.state
    for frame, step in zip(steps, deduction.trace, strict=True):
        board = apply_deduction(board, step)
        assert frame.state == board
        assert frame.ring == step.basis
        assert frame.style is Highlight.HINT
        assert frame.what_if == board.cats | board.crosses  # the player's board was empty

    assert breaks.state == board
    assert breaks.style is Highlight.PROBLEM
    assert breaks.ring == {(2, 0), (2, 1), (2, 2), (2, 3)}  # the row left with no room

    assert follows.state == player.with_crosses({(1, 1)})
    assert not follows.what_if  # the conclusion is real, so it's drawn solid
    assert session.state == player


def test_r8_14_empty_cell_assumption_ends_with_the_cat() -> None:
    session = d6_session(SIX_TEXT, SIX_CROSSES)
    session.show_me()
    assert session.frames[1].caption == "Suppose it has no cat."
    assert session.frames[1].state.mark_at((3, 4)) is Mark.CROSS
    assert session.frames[1].what_if == {(3, 4)}
    assert session.frames[-1].state.mark_at((3, 4)) is Mark.CAT
    assert session.frames[-1].caption == "So the cat goes here."


def test_r8_14_only_d6_hints_can_be_shown() -> None:
    session = new_session()
    session.hint()  # D3
    assert session.applicable is not None
    assert not session.can_show_me
    session.show_me()
    assert not session.walking


def test_r8_14_next_and_back_stay_in_bounds_and_done_closes() -> None:
    session = d6_session()
    session.show_me()
    assert session.walking and session.frame_number == 0
    session.previous_frame()
    assert session.frame_number == 0
    for number in range(1, len(session.frames)):
        session.next_frame()
        assert session.frame_number == number
    session.next_frame()  # Done
    assert not session.walking


def test_r8_14_closing_keeps_the_hint_and_the_marks() -> None:
    session = d6_session()
    hint, marks = session.applicable, session.state
    session.show_me()
    session.next_frame()
    session.close_show_me()
    assert not session.walking
    assert session.hint_shown and session.applicable == hint
    assert session.state == marks
    session.apply_hint()  # Apply? still works afterwards
    assert session.state.crosses == {(1, 1)}


def test_r8_14_any_other_action_closes_it() -> None:
    session = d6_session()
    session.show_me()
    session.click((3, 3))
    assert not session.walking


def test_r8_14_show_me_while_stepping() -> None:
    session = new_session(STRIPES_TEXT)
    session.step()
    assert session.stepping and session.can_show_me
    session.show_me()
    assert session.walking
    session.close_show_me()
    assert session.stepping


def test_r8_14_captions_name_regions_by_color() -> None:
    """R7.8: no region letters, like the hint's own message.

    Plays the real IMG_7117 board until a D6 proof that ends on an empty region.
    """
    session = new_session((FIXTURES / "screenshots" / "IMG_7117.txt").read_text())
    for _ in range(100):
        session.hint()
        assert session.applicable is not None and session.applicable.deduction is not None
        if session.can_show_me and "region '" in session.applicable.deduction.steps[-2]:
            break
        session.apply_hint()
    else:
        pytest.fail("no D6 hint about a region")
    session.show_me()
    captions = [session.text(frame.caption) for frame in session.frames]
    assert captions[-2].startswith("That leaves the ") and captions[-2].endswith(" region with no room for its cat.")
    assert all("region '" not in caption for caption in captions)
