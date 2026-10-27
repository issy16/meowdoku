"""Game session logic behind the GUI, testable without a display (R8.7).

The GUI only draws a GameSession and forwards clicks and button presses to it.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import Self

from meowdoku.assume import apply, find_break
from meowdoku.colors import name_regions, region_phrases
from meowdoku.deduce import Deduction
from meowdoku.hints import Hint, HintKind, next_hint
from meowdoku.image_import import import_screenshot
from meowdoku.parser import parse_puzzle
from meowdoku.puzzle import Cell, Puzzle
from meowdoku.rules import is_valid_solution
from meowdoku.solver import SolveResult, SolveStatus, solve
from meowdoku.state import BoardState, Mark

EXAMPLE_PUZZLE = "AABBB\nACCCB\nACDDB\nEEDDB\nEEEBB"

# At least MAX_SIZE (16) colors (R8.3). The first ten are the real game's tile
# colors (measured from tests/fixtures/screenshots/IMG_7128.jpg), so text
# puzzles look like the game; the rest are extra colors for bigger boards,
# chosen far from all the others so screenshots of the window import cleanly
# (R9.6). The comments are the names hints use for them (colors.NAMED_COLORS).
PALETTE = (
    "#9dd387",  # light green
    "#eb9fe0",  # pink
    "#f6da90",  # yellow
    "#5aa6bd",  # blue
    "#eda068",  # orange
    "#877ad4",  # purple
    "#9e704f",  # brown
    "#c77490",  # rose
    "#c7a635",  # mustard
    "#488b58",  # dark green
    "#283593",  # navy
    "#00897b",  # teal
    "#e040fb",  # magenta
    "#00bcd4",  # cyan
    "#8e2430",  # maroon
    "#aeea00",  # lime
)



class Highlight(Enum):
    HINT = "hint"
    PROBLEM = "problem"


class Paint(Enum):
    """What dragging across cells does, set by the cell where the drag began (R8.10)."""

    MARK = "mark"  # began on an empty cell: put ✕ on empty cells
    UNMARK = "unmark"  # began on a ✕: clear ✕ marks, except those a correct cat rules out


def next_mark(mark: Mark | None) -> Mark | None:
    """A click toggles a cell between empty and ✕, and clears a cat (R8.4). Cats come from double-clicks."""
    return Mark.CROSS if mark is None else None


def default_region_colors(puzzle: Puzzle) -> dict[str, str]:
    """Palette colors in order of each region's first appearance (R8.3)."""
    return {label: PALETTE[index] for index, label in enumerate(puzzle.region_labels)}


def crossed_out_by(puzzle: Puzzle, cat: Cell) -> frozenset[Cell]:
    """Cells a correct cat rules out: its row, column, color region, and touching cells (R8.9)."""
    row, col = cat
    region = puzzle.region_cells[puzzle.region_of(cat)]
    return frozenset(
        (r, c)
        for r, c in puzzle.cells()
        if (r, c) != cat and (r == row or c == col or (r, c) in region or (abs(r - row) <= 1 and abs(c - col) <= 1))
    )


def cells_between(start: Cell, end: Cell) -> list[Cell]:
    """The cells on a straight line from `start` to `end`, both included.

    A fast drag skips cells between two mouse events; this fills them in.
    """
    steps = max(abs(end[0] - start[0]), abs(end[1] - start[1]))
    if steps == 0:
        return [start]
    return [
        (
            round(start[0] + (end[0] - start[0]) * i / steps),
            round(start[1] + (end[1] - start[1]) * i / steps),
        )
        for i in range(steps + 1)
    ]


@dataclass(frozen=True)
class Frame:
    """One step of Show me (R8.14): a board to draw and the line that explains it.

    `what_if` holds the cells whose marks exist only in the assumption, which
    the window draws dashed; `ring` holds the cells to highlight.
    """

    state: BoardState
    what_if: frozenset[Cell]
    ring: frozenset[Cell]
    style: Highlight
    caption: str


def walkthrough(puzzle: Puzzle, state: BoardState, deduction: Deduction) -> tuple[Frame, ...]:
    """The frames of Show me for a D6 deduction, one per line of its explanation (R8.14).

    The assumption is the opposite of the conclusion: a ✕ means a cat was
    assumed, a cat means an empty cell was. The player's `state` is never changed.
    """
    if deduction.place_cat is not None:
        cell, assumed = deduction.place_cat, Mark.CROSS
        conclusion = state.with_mark(cell, Mark.CAT)
    else:
        (cell,) = deduction.cross_out
        assumed = Mark.CAT
        conclusion = state.with_crosses({cell})
    look, suppose, *step_lines, breaks, follows = deduction.steps
    here = frozenset({cell})

    board = state.with_mark(cell, assumed)
    frames = [
        Frame(state, frozenset(), here, Highlight.HINT, look),
        Frame(board, _what_if(state, board), here, Highlight.HINT, suppose),
    ]
    for step, line in zip(deduction.trace, step_lines, strict=True):
        board = apply(board, step)
        frames.append(Frame(board, _what_if(state, board), step.basis, Highlight.HINT, line))
    broken = find_break(puzzle, board)
    assert broken is not None, "a D6 proof ends on a broken board"
    frames.append(Frame(board, _what_if(state, board), broken.cells, Highlight.PROBLEM, breaks))
    frames.append(Frame(conclusion, frozenset(), here, Highlight.HINT, follows))
    return tuple(frames)


def _what_if(before: BoardState, after: BoardState) -> frozenset[Cell]:
    """Cells whose mark in `after` isn't the player's."""
    return frozenset(cell for cell in after.cats | after.crosses if after.mark_at(cell) != before.mark_at(cell))


@dataclass
class GameSession:
    """One puzzle being played: the marks, what to highlight, and a message."""

    puzzle: Puzzle
    colors: Mapping[str, str] = field(default_factory=dict)
    region_phrases: dict[str, str] = field(init=False, default_factory=dict)
    state: BoardState = field(init=False)
    highlight: frozenset[Cell] = field(init=False, default=frozenset())
    highlight_style: Highlight | None = field(init=False, default=None)
    hint_shown: bool = field(init=False, default=False)
    applicable: Hint | None = field(init=False, default=None)
    """The shown hint, when it's a logical step that Apply can make for the player (R8.11)."""
    stepping: bool = field(init=False, default=False)
    """True during Step by Step while a step is shown; the window's button then reads Next (R8.12)."""
    step_number: int = field(init=False, default=0)
    undo_states: list[BoardState] = field(init=False, default_factory=list)
    """The marks before each of the player's moves, latest last; Previous goes back to them (R8.13)."""
    redo_states: list[BoardState] = field(init=False, default_factory=list)
    """Marks that Previous undid, latest last; Next brings them back (R8.13)."""
    _paint_start: BoardState | None = field(init=False, default=None)
    revealed: frozenset[Cell] = field(init=False, default=frozenset())
    message: str = field(init=False, default="")
    shake: Cell | None = field(init=False, default=None)
    """The cell where the last click put a wrong cat; the window shakes it (R8.9)."""
    just_solved: bool = field(init=False, default=False)
    """True right after a click completes the puzzle; the window shows a pop-up (R8.6)."""
    painting: Paint | None = field(init=False, default=None)
    """What the current drag does, or None when not dragging or when it began on a cat (R8.10)."""
    frames: tuple[Frame, ...] = field(init=False, default=())
    """Show me's frames while its card is open, else empty (R8.14)."""
    frame_number: int = field(init=False, default=0)
    """The shown frame, counting from 0."""

    def __post_init__(self) -> None:
        if not self.colors:
            self.colors = default_region_colors(self.puzzle)
        self.region_phrases = region_phrases(self.colors)
        self.state = BoardState.empty(self.puzzle.size)

    @classmethod
    def from_text(cls, text: str) -> Self:
        """For the built-in example puzzle and tests; players open screenshots."""
        return cls(parse_puzzle(text))

    @classmethod
    def from_screenshot(cls, path: Path) -> Self:
        """Open a screenshot, starting from its cats and ✕ marks (R8.5, R9.1a).

        Raises OSError or MeowdokuError for files that can't be used.
        """
        imported = import_screenshot(path)
        session = cls(imported.puzzle, imported.colors)
        session.state = BoardState(imported.puzzle.size, imported.cats, imported.crosses)
        return session

    @property
    def is_solved(self) -> bool:
        return is_valid_solution(self.puzzle, self.state.cats)

    @cached_property
    def solve_result(self) -> SolveResult:
        """Solved once per puzzle: Solve shows its first solution, and placed cats are judged against it."""
        return solve(self.puzzle)

    def is_locked(self, cell: Cell) -> bool:
        """A correct cat stays put: clicking it does nothing (R8.4)."""
        solutions = self.solve_result.solutions
        return cell in self.state.cats and bool(solutions) and cell in solutions[0].cats

    def is_protected(self, cell: Cell) -> bool:
        """A ✕ that a correct cat on the board rules out; dragging never clears it (R8.10)."""
        return any(cell in crossed_out_by(self.puzzle, cat) for cat in self.state.cats if self.is_locked(cat))

    def begin_paint(self, cell: Cell) -> None:
        """Start a drag at `cell` and paint it: ✕ from an empty cell, clearing from a ✕ (R8.10).

        A drag that begins on a cat paints nothing.
        """
        self._clear_feedback()
        self._paint_start = self.state
        start = self.state.mark_at(cell)
        self.painting = Paint.MARK if start is None else Paint.UNMARK if start is Mark.CROSS else None
        self.paint(cell)

    def paint(self, cell: Cell) -> None:
        """Apply the current drag to one more cell. Cats are never changed."""
        mark = self.state.mark_at(cell)
        if self.painting is Paint.MARK and mark is None:
            self.state = self.state.with_mark(cell, Mark.CROSS)
        elif self.painting is Paint.UNMARK and mark is Mark.CROSS and not self.is_protected(cell):
            self.state = self.state.with_mark(cell, None)

    def end_paint(self) -> None:
        """Finish a drag; the whole drag is one move for Previous (R8.13)."""
        self.painting = None
        if self._paint_start is not None:
            self._remember(self._paint_start)
            self._paint_start = None

    def click(self, cell: Cell) -> None:
        """Toggle the cell between empty and ✕ (R8.4).

        Clicking a correct cat does nothing. Otherwise clicking hides a hint
        and ends Step by Step; a shown solution stays until Solve is pressed again.
        """
        if self.is_locked(cell):
            return
        before, was_solved = self.state, self.is_solved
        self._clear_feedback()
        self.state = self.state.with_mark(cell, next_mark(self.state.mark_at(cell)))
        self._note_solved(was_solved)
        self._remember(before)

    def place_cat(self, cell: Cell) -> None:
        """Put a cat on the cell, whatever it held, and judge it (R8.4, R8.9). A double-click does this."""
        if self.is_locked(cell):
            return
        before, was_solved = self.state, self.is_solved
        self._clear_feedback()
        self.state = self.state.with_mark(cell, Mark.CAT)
        self._judge_cat(cell)
        self._note_solved(was_solved)
        self._remember(before)

    def _note_solved(self, was_solved: bool) -> None:
        """Flag the pop-up if this move completed the puzzle (R8.6); the pop-up is the only notice."""
        self.just_solved = self.is_solved and not was_solved

    def _judge_cat(self, cat: Cell) -> None:
        """A wrong cat becomes a ✕ and shakes; a correct one crosses out the cells it rules out (R8.9)."""
        if not self.solve_result.solutions:
            return  # no solution to judge against
        if cat not in self.solve_result.solutions[0].cats:
            self.state = self.state.with_mark(cat, Mark.CROSS)
            self.shake = cat
            return
        self.state = self.state.with_crosses(
            cell for cell in crossed_out_by(self.puzzle, cat) if self.state.is_open(cell)
        )

    def hint(self) -> None:
        """Highlight the next hint and explain it, or hide it if it's showing (R8.5).

        Never changes the marks.
        """
        if self.hint_shown:
            self._clear_feedback()
            return
        self._clear_feedback()
        self._show_hint()

    def _show_hint(self) -> None:
        hint = next_hint(self.puzzle, self.state)
        self.message = name_regions(hint.message, self.region_phrases)
        self.highlight = hint.focus
        self.hint_shown = True
        if hint.kind is HintKind.DEDUCTION and hint.deduction is not None:
            self.applicable = hint
        if hint.kind in (HintKind.RULE_BROKEN, HintKind.MISTAKE):
            self.highlight_style = Highlight.PROBLEM
        elif hint.focus:
            self.highlight_style = Highlight.HINT

    def apply_hint(self) -> None:
        """Make the shown hint's move for the player, then hide the hint (R8.11).

        A cat goes through the same check as a clicked one (R8.9); ✕ marks go
        on the cells the hint rules out.
        """
        if self.applicable is None or self.applicable.deduction is None:
            return
        deduction = self.applicable.deduction
        before, was_solved = self.state, self.is_solved
        self._clear_feedback()
        if deduction.place_cat is not None:
            self.state = self.state.with_mark(deduction.place_cat, Mark.CAT)
            self._judge_cat(deduction.place_cat)
        else:
            self.state = self.state.with_crosses(cell for cell in deduction.cross_out if self.state.is_open(cell))
        self._note_solved(was_solved)
        self._remember(before)

    @property
    def can_show_me(self) -> bool:
        """Whether the shown hint is a D6 step, the only kind with an explanation to walk through (R8.14)."""
        return self.applicable is not None and self.applicable.deduction is not None and bool(
            self.applicable.deduction.steps
        )

    @property
    def walking(self) -> bool:
        return bool(self.frames)

    @property
    def frame(self) -> Frame | None:
        return self.frames[self.frame_number] if self.frames else None

    def show_me(self) -> None:
        """Open Show me at its first frame (R8.14). The hint stays, and the marks never change."""
        if not self.can_show_me:
            return
        assert self.applicable is not None and self.applicable.deduction is not None
        frames = walkthrough(self.puzzle, self.state, self.applicable.deduction)
        self.frames = tuple(replace(f, caption=name_regions(f.caption, self.region_phrases)) for f in frames)
        self.frame_number = 0

    def next_frame(self) -> None:
        """Next, or Done on the last frame, which closes Show me."""
        if self.frame_number + 1 < len(self.frames):
            self.frame_number += 1
        else:
            self.close_show_me()

    def previous_frame(self) -> None:
        self.frame_number = max(0, self.frame_number - 1)

    def close_show_me(self) -> None:
        """Close the card. The hint it came from stays showing."""
        self.frames = ()
        self.frame_number = 0

    def step(self) -> None:
        """Step by Step, then Next (R8.12): like pressing Hint and Apply over and over.

        The first press shows step 1. Each Next makes the shown step's move and
        shows the following step. Stepping ends when the puzzle is solved (the
        pop-up follows, R8.6) or no step is left: then the message is that last
        hint's, such as "No simple step found; try Solve.".
        """
        if self.stepping and self.applicable is not None:
            number = self.step_number
            self.apply_hint()
            if self.is_solved:
                return
            self.step_number = number + 1
        else:
            self._clear_feedback()
            self.step_number = 1
        self._show_hint()
        if self.applicable is not None:
            self.stepping = True
            self.message = f"Step {self.step_number}: {self.message}"

    def solve(self) -> None:
        """Show a solution over the player's marks, or hide it if it's showing (R8.5).

        Never changes the marks, so the player keeps playing from where they
        were. The board shows the answer, so there's no message, except when
        there is no solution to show.
        """
        self._clear_feedback()
        if self.revealed:
            self.revealed = frozenset()
            return
        result = self.solve_result
        if result.status is SolveStatus.NONE:
            self.message = "This puzzle has no solution."
            return
        self.revealed = result.solutions[0].cats

    def reset(self) -> None:
        """Clear the board. Previous can bring the marks back (R8.13)."""
        before = self.state
        self.state = BoardState.empty(self.puzzle.size)
        self.revealed = frozenset()
        self._clear_feedback()
        self._remember(before)

    def _remember(self, before: BoardState) -> None:
        """Record a move for Previous, if the marks changed. A new move ends what Next could redo."""
        if self.state != before:
            self.undo_states.append(before)
            self.redo_states.clear()

    @property
    def can_undo(self) -> bool:
        return bool(self.undo_states)

    @property
    def can_redo(self) -> bool:
        return bool(self.redo_states)

    def undo(self) -> None:
        """Previous: go back to the marks before the last move (R8.13)."""
        if self.undo_states:
            self._clear_feedback()
            self.redo_states.append(self.state)
            self.state = self.undo_states.pop()
            self._note_solved(was_solved=True)  # no pop-up when undoing

    def redo(self) -> None:
        """Next: make the move that Previous undid (R8.13)."""
        if self.redo_states:
            self._clear_feedback()
            self.undo_states.append(self.state)
            self.state = self.redo_states.pop()
            self._note_solved(was_solved=True)

    def _clear_feedback(self) -> None:
        """Hide a hint and its message, end Step by Step and Show me, and end a shake or pop-up. A shown solution stays."""
        self.highlight = frozenset()
        self.highlight_style = None
        self.hint_shown = False
        self.applicable = None
        self.stepping = False
        self.message = ""
        self.shake = None
        self.just_solved = False
        self.close_show_me()
