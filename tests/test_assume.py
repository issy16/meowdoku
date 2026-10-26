"""D6 contradiction by assumption (R7.9).

Proofs are checked against solutions from brute force and the rule
validator, never against D6 itself.
"""

import random
import time
from itertools import permutations
from pathlib import Path

import meowdoku.assume
from meowdoku.assume import find_break, find_contradiction, follow
from meowdoku.deduce import Technique, find_deduction
from meowdoku.hints import HintKind, next_hint
from meowdoku.parser import parse_puzzle
from meowdoku.puzzle import Cell, Puzzle
from meowdoku.rules import is_valid_solution
from meowdoku.state import BoardState, Mark

from helpers import apply_deduction, column_stripes, imported_modules, random_puzzle

SEED = 20261026
IMG_7117 = parse_puzzle((Path(__file__).parent / "fixtures" / "screenshots" / "IMG_7117.txt").read_text())

# Only 1-3-0-2 and 2-0-3-1 solve this board, and D1-D5 find nothing on it.
STRIPES_4 = column_stripes(4)

# A 6x6 board with 7 solutions, all with a cat at (3, 4), where D1-D5 find nothing.
SIX = Puzzle.from_rows(["DDDDDE", "DDDDDE", "CFDDEE", "CFABBE", "CFABBB", "CCAABB"])
SIX_CROSSES = [(0, 0), (0, 1), (0, 4), (1, 0), (1, 1), (1, 4), (3, 0), (3, 2), (3, 3), (4, 3), (5, 1)]
SIX_STATE = BoardState(6, crosses=frozenset(SIX_CROSSES))
# The same board after D6 rules out (2, 2), (2, 3), and (2, 4) and D3 crosses out two more.
SIX_LATER = BoardState(6, crosses=frozenset(SIX_CROSSES + [(2, 2), (2, 3), (2, 4), (4, 5), (5, 5)]))

RULED_OUT_BY_A_CAT = "Then this cat rules out its row, column, region, and the cells around it."


def brute_force_solutions(puzzle: Puzzle, state: BoardState) -> list[frozenset[Cell]]:
    """Every solution matching the marks, from permutations and the validator (no solver)."""
    solutions = []
    for columns in permutations(range(puzzle.size)):
        cats = frozenset(enumerate(columns))
        if state.cats <= cats and not (state.crosses & cats) and is_valid_solution(puzzle, cats):
            solutions.append(cats)
    return solutions


def assert_sound(puzzle: Puzzle, state: BoardState) -> None:
    deduction = find_contradiction(puzzle, state)
    if deduction is None:
        return
    for cats in brute_force_solutions(puzzle, state):
        if deduction.place_cat is not None:
            assert deduction.place_cat in cats, deduction.reason
        assert not (deduction.cross_out & cats), deduction.reason


def stuck_state(puzzle: Puzzle, state: BoardState) -> BoardState:
    """Apply D1-D5 until they find nothing."""
    while deduction := find_deduction(puzzle, state):
        state = apply_deduction(state, deduction)
    return state


# A cat that leads to a contradiction


def test_r7_9_cat_assumption_leads_to_contradiction() -> None:
    """(1, 1) is in neither solution: a cat there leaves a row with no room.

    (0, 0) isn't either, but its proof is longer, so the shortest one wins.
    """
    state = BoardState.empty(4)
    assert find_deduction(STRIPES_4, state) is None
    deduction = find_contradiction(STRIPES_4, state)
    assert deduction is not None
    assert deduction.technique is Technique.CONTRADICTION
    assert deduction.cross_out == {(1, 1)}
    assert len(follow(STRIPES_4, state, (0, 0), Mark.CAT).trace) > 3
    assert deduction.place_cat is None
    assert deduction.reason == (
        "If this cell had a cat, this row would have no room for its cat after 3 steps, so it can't have a cat."
    )


def test_r7_9_explanation_goes_from_where_to_look_to_the_mark() -> None:
    deduction = find_contradiction(STRIPES_4, BoardState.empty(4))
    assert deduction is not None
    assert deduction.steps == (
        "Look at this cell.",
        "Suppose it has a cat.",
        RULED_OUT_BY_A_CAT,
        "Then this row has only 1 cell left.",
        RULED_OUT_BY_A_CAT,
        "That leaves this row with no room for its cat.",
        "So this cell can't have a cat.",
    )
    assert [step.technique for step in deduction.trace] == [
        Technique.CAT_NEIGHBORHOOD,
        Technique.LAST_OPEN_CELL,
        Technique.CAT_NEIGHBORHOOD,
    ]


# Empty cells that lead to a contradiction


def test_r7_9_empty_cell_assumption_leads_to_contradiction() -> None:
    proof = follow(SIX, SIX_STATE, (3, 4), Mark.CROSS)
    assert proof is not None
    assert proof.broken.sentence == "That leaves this column with no room for its cat."
    assert [step.technique for step in proof.trace] == [
        Technique.PIGEONHOLE,
        Technique.LAST_OPEN_CELL,
        Technique.CAT_NEIGHBORHOOD,
    ]
    assert all((3, 4) in cats for cats in brute_force_solutions(SIX, SIX_STATE))


def test_r7_9_ties_go_to_the_first_cell_in_row_major_order() -> None:
    """(2, 2) as a cat and (3, 4) as empty both break in 3 steps; (2, 2) comes first."""
    deduction = find_contradiction(SIX, SIX_STATE)
    assert deduction is not None
    assert deduction.cross_out == {(2, 2)}
    assert len(deduction.trace) == 3


def test_r7_9_hint_places_a_cat_when_no_cat_is_impossible() -> None:
    assert find_deduction(SIX, SIX_LATER) is None
    hint = next_hint(SIX, SIX_LATER)
    assert hint.kind is HintKind.DEDUCTION
    deduction = hint.deduction
    assert deduction is not None
    assert deduction.technique is Technique.CONTRADICTION
    assert deduction.place_cat == (3, 4)
    assert deduction.cross_out == frozenset()
    assert deduction.steps[1] == "Suppose it has no cat."
    assert deduction.steps[-1] == "So the cat goes here."
    assert deduction.reason.startswith("If this cell had no cat, ")
    assert hint.message == deduction.reason
    assert hint.focus == deduction.basis


# Nothing to prove


def test_r7_9_neither_branch_proves_anything_for_a_cell_in_one_solution() -> None:
    """(0, 1) has a cat in one solution and not the other, so both branches must stay open."""
    state = BoardState.empty(4)
    assert follow(STRIPES_4, state, (0, 1), Mark.CAT) is None
    assert follow(STRIPES_4, state, (0, 1), Mark.CROSS) is None


def test_r7_9_finds_nothing_when_every_cell_is_undecided() -> None:
    """Every cell of this board is in some of its 90 solutions and not in others."""
    assert find_contradiction(column_stripes(6), BoardState.empty(6)) is None


def test_r7_9_branch_that_finishes_the_board_proves_nothing() -> None:
    """A cat at (0, 1) leads D1-D5 to a valid board, but the other solution exists too."""
    state = BoardState.empty(4)
    finished = stuck_state(STRIPES_4, state.with_mark((0, 1), Mark.CAT))
    assert is_valid_solution(STRIPES_4, finished.cats)
    assert follow(STRIPES_4, state, (0, 1), Mark.CAT) is None
    assert find_contradiction(STRIPES_4, state).cross_out != {(0, 1)}


def test_r7_9_already_broken_board_gets_nothing() -> None:
    state = BoardState(4, cats=frozenset({(0, 0), (0, 1)}))
    assert find_contradiction(STRIPES_4, state) is None


# Several steps and accurate traces


def test_r7_9_contradiction_after_several_steps() -> None:
    puzzle = Puzzle.from_rows(["ABBBB", "AABBD", "AACBD", "AACCC", "EECCC"])
    crosses = [(0, 0), (0, 1), (0, 4), (1, 2), (1, 3), (2, 2), (2, 3), (3, 0), (3, 1), (3, 4), (4, 2), (4, 3), (4, 4)]
    state = BoardState(5, crosses=frozenset(crosses))
    assert find_deduction(puzzle, state) is None
    deduction = find_contradiction(puzzle, state)
    assert deduction is not None
    assert deduction.cross_out == {(1, 0)}
    assert len(deduction.trace) == 5
    assert len(deduction.steps) == len(deduction.trace) + 4
    assert_sound(puzzle, state)


def test_r7_9_trace_replays_to_the_break() -> None:
    """Each traced step is what D1-D5 give at that point, and the last one breaks the board."""
    puzzle, state = SIX, SIX_LATER
    deduction = find_contradiction(puzzle, state)
    assert deduction is not None and deduction.place_cat is not None
    replay = state.with_mark(deduction.place_cat, Mark.CROSS)
    for step in deduction.trace:
        assert find_break(puzzle, replay) is None
        assert find_deduction(puzzle, replay) == step
        replay = apply_deduction(replay, step)
    broken = find_break(puzzle, replay)
    assert broken is not None
    assert deduction.steps[-2] == broken.sentence
    assert deduction.basis == {deduction.place_cat} | broken.cells


# Breaks


def test_find_break_reports_a_unit_with_no_room() -> None:
    state = BoardState(4, crosses=frozenset({(0, 0), (0, 1), (0, 2), (0, 3)}))
    broken = find_break(STRIPES_4, state)
    assert broken is not None
    assert broken.sentence == "That leaves this row with no room for its cat."


def test_find_break_reports_two_cats_in_a_region() -> None:
    puzzle = Puzzle.from_rows(["AABBB", "ACCCB", "ACDDB", "EEDDB", "EEEBB"])
    broken = find_break(puzzle, BoardState(5, cats=frozenset({(0, 2), (2, 4)})))
    assert broken is not None
    assert broken.cells == {(0, 2), (2, 4)}
    assert broken.sentence == "That puts 2 cats in region 'B'."


def test_find_break_reports_touching_cats() -> None:
    broken = find_break(STRIPES_4, BoardState(4, cats=frozenset({(0, 1), (1, 2)})))
    assert broken is not None
    assert broken.sentence == "That makes 2 cats touch."


def test_find_break_accepts_a_board_that_can_still_be_finished() -> None:
    assert find_break(STRIPES_4, BoardState(4, cats=frozenset({(0, 1)}))) is None


# The player's board and determinism


def test_r7_1_board_is_never_changed() -> None:
    state = SIX_LATER
    before = (state.cats, state.crosses)
    find_contradiction(SIX, state)
    follow(SIX, state, (3, 4), Mark.CROSS)
    next_hint(SIX, state)
    assert (state.cats, state.crosses) == before


def test_r7_4_same_board_gives_same_d6_hint() -> None:
    assert find_contradiction(SIX, SIX_STATE) == find_contradiction(SIX, SIX_STATE)


# D1-D5 come first


def test_r7_9_d1_to_d5_come_before_d6() -> None:
    """On the real IMG_7117 board, D6 only appears when D1-D5 find nothing."""
    state = BoardState.empty(10)
    techniques = []
    for _ in range(200):
        hint = next_hint(IMG_7117, state)
        if hint.kind is not HintKind.DEDUCTION:
            break
        assert hint.deduction is not None
        simple = find_deduction(IMG_7117, state)
        if simple is not None:
            assert hint.deduction == simple
        else:
            assert hint.deduction.technique is Technique.CONTRADICTION
        techniques.append(hint.deduction.technique)
        state = apply_deduction(state, hint.deduction)
    assert hint.kind is HintKind.SOLVED
    assert Technique.CONTRADICTION in techniques


def test_d1_to_d5_alone_get_stuck_on_the_real_board() -> None:
    """Why D6 exists: the hints test above needs it to finish this board."""
    assert len(stuck_state(IMG_7117, BoardState.empty(10)).cats) < 10


def test_d6_hint_is_fast_on_a_real_board() -> None:
    state = stuck_state(IMG_7117, BoardState.empty(10))
    start = time.perf_counter()
    assert find_contradiction(IMG_7117, state) is not None
    assert time.perf_counter() - start < 1.0


# Soundness against brute force


def test_r7_7_d6_is_sound_on_random_small_boards() -> None:
    """Seeded random 4x4-6x6 boards, from empty and in progress, against brute force."""
    rng = random.Random(SEED)
    checked = 0
    while checked < 40:
        puzzle = random_puzzle(rng, rng.choice([4, 5, 6]))
        solutions = brute_force_solutions(puzzle, BoardState.empty(puzzle.size))
        if not solutions:
            continue
        solution = rng.choice(solutions)
        state = BoardState.empty(puzzle.size)
        others = [cell for cell in puzzle.cells() if cell not in solution]
        state = state.with_crosses(rng.sample(others, rng.randrange(len(others) // 2 + 1)))
        state = stuck_state(puzzle, state)
        while (deduction := find_contradiction(puzzle, state)) is not None:
            assert_sound(puzzle, state)
            state = stuck_state(puzzle, apply_deduction(state, deduction))
        checked += 1


# Module boundaries


def test_assume_never_imports_the_solver_or_validator() -> None:
    imported = imported_modules(meowdoku.assume)
    assert not any("solver" in name or "rules" in name for name in imported)
