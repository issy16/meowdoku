"""D6 contradiction by assumption (R7.9, see docs/algorithm.md).

Suppose an open cell has a cat, or has none, and apply D1-D5 until they stop.
If the board breaks, no solution has that mark, so the cell gets the other
one. A branch that doesn't break proves nothing. This module must never
import the solver: hints are tested against solver output.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations

from meowdoku.deduce import Deduction, Technique, Unit, all_units, find_deduction, has_cat, open_cells
from meowdoku.messages import Count, Message
from meowdoku.puzzle import Cell, Puzzle
from meowdoku.state import BoardState, Mark


@dataclass(frozen=True)
class Break:
    """Why a board can't be finished: the cells involved and how to say it."""

    cells: frozenset[Cell]
    would: Message
    sentence: Message


@dataclass(frozen=True)
class Proof:
    """An assumption, the D1-D5 steps that followed, and the break they led to."""

    cell: Cell
    assumed: Mark
    trace: tuple[Deduction, ...]
    broken: Break


def find_contradiction(puzzle: Puzzle, state: BoardState) -> Deduction | None:
    """Return the D6 deduction with the shortest proof, or None.

    Cells are tried in row-major order, a cat before empty, and ties go to
    the first proof found, so the result is deterministic. A board that is
    already broken gets None: every assumption would "prove" something.
    """
    if find_break(puzzle, state):
        return None
    best: Proof | None = None
    for cell in puzzle.cells():
        if not state.is_open(cell):
            continue
        for assumed in (Mark.CAT, Mark.CROSS):
            if best is not None and not best.trace:
                return explain(best)  # nothing is shorter than a proof with no steps
            limit = None if best is None else len(best.trace) - 1
            best = follow(puzzle, state, cell, assumed, limit) or best
    return explain(best) if best else None


def follow(
    puzzle: Puzzle, state: BoardState, cell: Cell, assumed: Mark, limit: int | None = None
) -> Proof | None:
    """Assume `assumed` at `cell` and apply D1-D5 until the board breaks or they stop.

    Gives up after `limit` steps, when a shorter proof is already known.
    The player's `state` is never changed: each step makes a new one (R7.1).
    """
    state = state.with_mark(cell, assumed)
    trace: list[Deduction] = []
    while True:
        broken = find_break(puzzle, state)
        if broken:
            return Proof(cell, assumed, tuple(trace), broken)
        if limit is not None and len(trace) >= limit:
            return None
        deduction = find_deduction(puzzle, state)
        if deduction is None:
            return None
        trace.append(deduction)
        state = apply(state, deduction)


def apply(state: BoardState, deduction: Deduction) -> BoardState:
    """Make a D1-D5 deduction's marks on a hypothetical board."""
    if deduction.place_cat is not None:
        return state.with_mark(deduction.place_cat, Mark.CAT)
    return state.with_crosses(deduction.cross_out)


# Breaks


def find_break(puzzle: Puzzle, state: BoardState) -> Break | None:
    """A unit with no room for its cat, 2 cats in one unit, or 2 cats touching."""
    units = all_units(puzzle)
    return _empty_unit(units, state) or _crowded_unit(units, state) or _touching_cats(state)


def _empty_unit(units: Sequence[Unit], state: BoardState) -> Break | None:
    for unit in units:
        if not has_cat(unit, state) and not open_cells(unit.cells, state):
            name = _unit_phrase(unit)
            return Break(unit.cells, Message("would.empty", unit=name), Message("breaks.empty", unit=name))
    return None


def _crowded_unit(units: Sequence[Unit], state: BoardState) -> Break | None:
    for unit in units:
        cats = unit.cells & state.cats
        if len(cats) > 1:
            name = _unit_phrase(unit)
            count = Count(len(cats), "cat")
            return Break(
                frozenset(cats),
                Message("would.crowded", unit=name, cats=count),
                Message("breaks.crowded", unit=name, cats=count),
            )
    return None


def _touching_cats(state: BoardState) -> Break | None:
    for (r1, c1), (r2, c2) in combinations(sorted(state.cats), 2):
        if abs(r1 - r2) <= 1 and abs(c1 - c2) <= 1:
            return Break(frozenset({(r1, c1), (r2, c2)}), Message("would.touch"), Message("breaks.touch"))
    return None


def _unit_phrase(unit: Unit) -> Message:
    """Regions by name (the GUI turns it into a color), rows and columns as "this row" (R7.3)."""
    if unit.kind == "region":
        return Message("unit.region", region=unit.region)
    return Message(f"unit.this_{unit.kind}")


# Explanation


def explain(proof: Proof) -> Deduction:
    """Turn a proof into a hint: the opposite mark, a short reason, and the steps (R7.9)."""
    when = Message("when.now") if not proof.trace else Message("when.after", steps=Count(len(proof.trace), "step"))
    if proof.assumed is Mark.CAT:
        supposition, conclusion = Message("d6.suppose_cat"), Message("d6.so_no_cat")
        reason = Message("d6.cat", would=proof.broken.would, when=when)
        place_cat, cross_out = None, frozenset({proof.cell})
    else:
        supposition, conclusion = Message("d6.suppose_no_cat"), Message("d6.so_cat")
        reason = Message("d6.no_cat", would=proof.broken.would, when=when)
        place_cat, cross_out = proof.cell, frozenset()
    steps = (
        Message("d6.look"),
        supposition,
        *(_then(deduction.reason) for deduction in proof.trace),
        proof.broken.sentence,
        conclusion,
    )
    return Deduction(
        Technique.CONTRADICTION,
        frozenset({proof.cell}) | proof.broken.cells,
        reason,
        place_cat=place_cat,
        cross_out=cross_out,
        steps=steps,
        trace=proof.trace,
    )


def _then(reason: Message) -> Message:
    """"This row has only 1 cell left." -> "Then this row has only 1 cell left."."""
    return Message("d6.then", reason=reason)
