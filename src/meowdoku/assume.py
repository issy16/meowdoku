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
from meowdoku.puzzle import Cell, Puzzle, count_of
from meowdoku.state import BoardState, Mark


@dataclass(frozen=True)
class Break:
    """Why a board can't be finished: the cells involved and how to say it."""

    cells: frozenset[Cell]
    would: str
    sentence: str


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
            return Break(
                unit.cells,
                f"{name} would have no room for its cat",
                f"That leaves {name} with no room for its cat.",
            )
    return None


def _crowded_unit(units: Sequence[Unit], state: BoardState) -> Break | None:
    for unit in units:
        cats = unit.cells & state.cats
        if len(cats) > 1:
            name = _unit_phrase(unit)
            return Break(
                frozenset(cats),
                f"{name} would have {count_of(len(cats), 'cat')}",
                f"That puts {count_of(len(cats), 'cat')} in {name}.",
            )
    return None


def _touching_cats(state: BoardState) -> Break | None:
    for (r1, c1), (r2, c2) in combinations(sorted(state.cats), 2):
        if abs(r1 - r2) <= 1 and abs(c1 - c2) <= 1:
            return Break(frozenset({(r1, c1), (r2, c2)}), "2 cats would touch", "That makes 2 cats touch.")
    return None


def _unit_phrase(unit: Unit) -> str:
    """Regions by name (the GUI turns it into a color), rows and columns as "this row" (R7.3)."""
    return unit.name if unit.kind == "region" else f"this {unit.kind}"


# Explanation


def explain(proof: Proof) -> Deduction:
    """Turn a proof into a hint: the opposite mark, a short reason, and the steps (R7.9)."""
    when = "right away" if not proof.trace else f"after {count_of(len(proof.trace), 'step')}"
    if proof.assumed is Mark.CAT:
        supposition, conclusion = "Suppose it has a cat.", "So this cell can't have a cat."
        reason = f"If this cell had a cat, {proof.broken.would} {when}, so it can't have a cat."
        place_cat, cross_out = None, frozenset({proof.cell})
    else:
        supposition, conclusion = "Suppose it has no cat.", "So the cat goes here."
        reason = f"If this cell had no cat, {proof.broken.would} {when}, so the cat goes here."
        place_cat, cross_out = proof.cell, frozenset()
    steps = (
        "Look at this cell.",
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


def _then(reason: str) -> str:
    """"This row has only 1 cell left." -> "Then this row has only 1 cell left."."""
    return f"Then {reason[0].lower()}{reason[1:]}"
