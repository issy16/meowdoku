"""Game session logic behind the GUI, testable without a display (R8.7).

The GUI only draws a GameSession and forwards clicks and button presses to it.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Self

from meowdoku.colors import name_regions, region_phrases
from meowdoku.hints import HintKind, next_hint
from meowdoku.image_import import import_screenshot
from meowdoku.parser import parse_puzzle
from meowdoku.puzzle import Cell, Puzzle, count_of
from meowdoku.rules import find_conflicts, is_valid_solution
from meowdoku.solver import SolveStatus, solve
from meowdoku.state import BoardState, Mark

EXAMPLE_PUZZLE = "AABBB\nACCCB\nACDDB\nEEDDB\nEEEBB"

# At least MAX_SIZE (16) colors (R8.3). The first ten are the real game's tile
# colors (measured from tests/fixtures/screenshots/IMG_7128.jpg), so text
# puzzles look like the game; the rest are extra colors for bigger boards.
# The comments are the names hints use for them (colors.NAMED_COLORS).
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
    "#9fdcdc",  # teal
    "#e0e48f",  # lime
    "#bfc9d9",  # gray
    "#8fc1e3",  # sky blue
    "#e8a0a0",  # coral
    "#d9b99b",  # tan
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
    """Clicking cycles a cell: empty → ✕ → cat → empty (R8.4)."""
    if mark is None:
        return Mark.CROSS
    if mark is Mark.CROSS:
        return Mark.CAT
    return None


def default_region_colors(puzzle: Puzzle) -> dict[str, str]:
    """Palette colors in order of each region's first appearance (R8.3)."""
    return {label: PALETTE[index] for index, label in enumerate(puzzle.region_labels)}


@dataclass
class GameSession:
    """One puzzle being played: the marks, what to highlight, and a message."""

    puzzle: Puzzle
    colors: Mapping[str, str] = field(default_factory=dict)
    region_phrases: dict[str, str] = field(init=False, default_factory=dict)
    state: BoardState = field(init=False)
    highlight: frozenset[Cell] = field(init=False, default=frozenset())
    highlight_style: Highlight | None = field(init=False, default=None)
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

    def click(self, cell: Cell) -> None:
        """Cycle the cell's mark, then clear hints and any shown solution."""
        self.state = self.state.with_mark(cell, next_mark(self.state.mark_at(cell)))
        self._clear()
        if self.is_solved:
            self.message = SOLVED_MESSAGE

    def hint(self) -> None:
        """Highlight the next hint and explain it. Never changes the marks (R8.5)."""
        hint = next_hint(self.puzzle, self.state)
        self._clear()
        self.message = name_regions(hint.message, self.region_phrases)
        self.highlight = hint.focus
        if hint.kind in (HintKind.RULE_BROKEN, HintKind.MISTAKE):
            self.highlight_style = Highlight.PROBLEM
        elif hint.focus:
            self.highlight_style = Highlight.HINT

    def check(self) -> None:
        """Highlight cats that break a rule. Missing cats aren't counted on a board in progress."""
        self._clear()
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
        """Show a solution on top of the board without changing the player's marks."""
        result = solve(self.puzzle)
        self._clear()
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
        self._clear()

    def _clear(self) -> None:
        self.highlight = frozenset()
        self.highlight_style = None
        self.revealed = frozenset()
        self.message = ""
