"""Game session logic behind the GUI, testable without a display (R8.7).

The GUI only draws a GameSession and forwards clicks and button presses to it.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import Self

from meowdoku.colors import name_regions, region_phrases
from meowdoku.hints import HintKind, next_hint
from meowdoku.image_import import import_screenshot
from meowdoku.parser import parse_puzzle
from meowdoku.puzzle import Cell, Puzzle, count_of, describe_cell
from meowdoku.rules import find_conflicts, is_valid_solution
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

SOLVED_MESSAGE = "Solved!"
IMPORTED_MESSAGE = "Read from the screenshot. Check that the board matches your game."


def imported_message(cats: int, crosses: int) -> str:
    """What the window says after opening a screenshot (R9.1a)."""
    if not cats and not crosses:
        return IMPORTED_MESSAGE
    marks = f"{count_of(cats, 'cat')} and {count_of(crosses, '✕ mark')}"
    return f"Read from the screenshot, with {marks}. Check that the board matches your game."


class Highlight(Enum):
    HINT = "hint"
    PROBLEM = "problem"


def next_mark(mark: Mark | None) -> Mark | None:
    """Clicking cycles a cell: empty → ✕ → cat → empty (R8.4). A wrong cat becomes ✕ (R8.9)."""
    if mark is None:
        return Mark.CROSS
    if mark is Mark.CROSS:
        return Mark.CAT
    return None


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
    revealed: frozenset[Cell] = field(init=False, default=frozenset())
    message: str = field(init=False, default="")

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
        session.message = imported_message(len(imported.cats), len(imported.crosses))
        return session

    @property
    def is_solved(self) -> bool:
        return is_valid_solution(self.puzzle, self.state.cats)

    @cached_property
    def solve_result(self) -> SolveResult:
        """Solved once per puzzle: Solve shows its first solution, and placed cats are judged against it."""
        return solve(self.puzzle)

    def click(self, cell: Cell) -> None:
        """Cycle the cell's mark (R8.4) and judge a newly placed cat (R8.9).

        Clicking hides a hint or Check result; a shown solution stays until
        Solve is pressed again.
        """
        self._clear_feedback()
        mark = next_mark(self.state.mark_at(cell))
        self.state = self.state.with_mark(cell, mark)
        if mark is Mark.CAT:
            self._judge_cat(cell)
        if self.is_solved:
            self.message = SOLVED_MESSAGE

    def _judge_cat(self, cat: Cell) -> None:
        """A wrong cat becomes a ✕; a correct one crosses out the cells it rules out (R8.9)."""
        if not self.solve_result.solutions:
            return  # no solution to judge against
        if cat not in self.solve_result.solutions[0].cats:
            self.state = self.state.with_mark(cat, Mark.CROSS)
            self.message = f"No cat at {describe_cell(cat)}, so it's marked ✕."
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
        hint = next_hint(self.puzzle, self.state)
        self._clear_feedback()
        self.message = name_regions(hint.message, self.region_phrases)
        self.highlight = hint.focus
        self.hint_shown = True
        if hint.kind in (HintKind.RULE_BROKEN, HintKind.MISTAKE):
            self.highlight_style = Highlight.PROBLEM
        elif hint.focus:
            self.highlight_style = Highlight.HINT

    def check(self) -> None:
        """Highlight cats that break a rule. Missing cats aren't counted on a board in progress."""
        self._clear_feedback()
        if self.is_solved:
            self.message = SOLVED_MESSAGE
            return
        conflicts = find_conflicts(self.puzzle, self.state.cats)
        if not conflicts:
            self.message = "No rules broken so far."
            return
        self.highlight = frozenset(cell for conflict in conflicts for cell in conflict.cells)
        self.highlight_style = Highlight.PROBLEM
        first = name_regions(conflicts[0].message, self.region_phrases)
        self.message = f"{count_of(len(conflicts), 'problem')}: {first}."

    def solve(self) -> None:
        """Show a solution over the player's marks, or hide it if it's showing (R8.5).

        Never changes the marks, so the player keeps playing from where they were.
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
        if result.status is SolveStatus.UNIQUE:
            self.message = "Here is the solution."
        else:
            self.message = "This puzzle has more than one solution. Here is one of them."

    def reset(self) -> None:
        self.state = BoardState.empty(self.puzzle.size)
        self.revealed = frozenset()
        self._clear_feedback()

    def _clear_feedback(self) -> None:
        """Hide a hint or Check result and its message. A shown solution stays."""
        self.highlight = frozenset()
        self.highlight_style = None
        self.hint_shown = False
        self.message = ""
