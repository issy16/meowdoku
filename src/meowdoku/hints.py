"""The next available hint for a board in progress (R7).

This is the only module where deduction, rule checking, and solving meet.
Hints never change the board and never reveal the solution.
"""

from dataclasses import dataclass, field
from enum import Enum

from meowdoku.assume import find_contradiction
from meowdoku.deduce import Deduction, find_deduction
from meowdoku.messages import Message
from meowdoku.puzzle import Cell, Puzzle
from meowdoku.rules import Rule, RuleViolation, find_conflicts, is_valid_solution
from meowdoku.solver import Solution, SolveResult, SolveStatus, iter_solutions, solve
from meowdoku.state import BoardState

NO_SOLUTION_MESSAGE = Message("hint.no_solution")
SOLVED_MESSAGE = Message("hint.solved")
NO_SIMPLE_STEP_MESSAGE = Message("hint.no_step")


class HintKind(Enum):
    NO_SOLUTION = "no solution"
    SOLVED = "solved"
    RULE_BROKEN = "rule broken"
    MISTAKE = "mistake"
    DEDUCTION = "deduction"
    NO_SIMPLE_STEP = "no simple step"


@dataclass(frozen=True)
class Hint:
    """What to tell the player, and which cells to highlight.

    `focus` holds the cells the hint is about: the reasoning for a deduction,
    or the problem cells for a broken rule or mistake.
    """

    kind: HintKind
    message: Message
    focus: frozenset[Cell] = field(default_factory=frozenset)
    deduction: Deduction | None = None


def next_hint(puzzle: Puzzle, state: BoardState) -> Hint:
    """Return the next available hint, checking in the order of docs/algorithm.md."""
    if state.size != puzzle.size:
        raise ValueError(f"board state is {state.size}x{state.size} but the puzzle is {puzzle.size}x{puzzle.size}")

    result = solve(puzzle)
    if result.status is SolveStatus.NONE:
        return Hint(HintKind.NO_SOLUTION, NO_SOLUTION_MESSAGE)
    if is_valid_solution(puzzle, state.cats):
        return Hint(HintKind.SOLVED, SOLVED_MESSAGE)

    problem = _find_broken_rule(puzzle, state) or _find_mistake(puzzle, state, result)
    if problem:
        return problem

    # D6 is tried only when D1-D5 find nothing (R7.9).
    deduction = find_deduction(puzzle, state) or find_contradiction(puzzle, state)
    if deduction:
        return Hint(HintKind.DEDUCTION, deduction.reason, deduction.basis, deduction)
    return Hint(HintKind.NO_SIMPLE_STEP, NO_SIMPLE_STEP_MESSAGE)


def _find_broken_rule(puzzle: Puzzle, state: BoardState) -> Hint | None:
    """R7.5: point at cats that already break a rule."""
    conflicts = find_conflicts(puzzle, state.cats)
    if not conflicts:
        return None
    first = conflicts[0]
    return Hint(HintKind.RULE_BROKEN, _broken_rule_message(first), frozenset(first.cells))


def _broken_rule_message(violation: RuleViolation) -> Message:
    """Short, since the hint highlights the cats: "These cats touch." or "This row has 2 cats."."""
    if violation.rule is Rule.ADJACENT:
        return Message("hint.touch")
    if violation.rule is Rule.OUT_OF_BOUNDS:
        return Message("hint.off_board")
    return Message(f"hint.crowded.{violation.rule.value}", n=len(violation.cells))


def _find_mistake(puzzle: Puzzle, state: BoardState, result: SolveResult) -> Hint | None:
    """R7.5: report marks that no solution agrees with."""
    if result.status is SolveStatus.UNIQUE:
        solution = result.solutions[0].cats
        wrong = sorted((state.cats - solution) | (state.crosses & solution))
        if not wrong:
            return None
        return Hint(
            HintKind.MISTAKE,
            Message("hint.wrong_mark"),
            frozenset({wrong[0]}),
        )
    if any(_matches(solution, state) for solution in iter_solutions(puzzle)):
        return None
    return Hint(HintKind.MISTAKE, Message("hint.some_wrong"))


def _matches(solution: Solution, state: BoardState) -> bool:
    cats = solution.cats
    return state.cats <= cats and not (state.crosses & cats)
