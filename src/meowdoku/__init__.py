"""Meowdoku Solver: solve Meowdoku puzzles with backtracking search."""

from meowdoku.hints import Hint, HintKind, next_hint
from meowdoku.parser import parse_puzzle
from meowdoku.puzzle import (
    Cell,
    MeowdokuError,
    Puzzle,
    PuzzleFormatError,
    PuzzleValidationError,
)
from meowdoku.rules import Rule, RuleViolation, find_violations, is_valid_solution
from meowdoku.solver import Solution, SolveResult, SolveStatus, iter_solutions, solve
from meowdoku.state import BoardState, Mark

__version__ = "0.1.0"

__all__ = [
    "BoardState",
    "Cell",
    "Hint",
    "HintKind",
    "Mark",
    "MeowdokuError",
    "Puzzle",
    "PuzzleFormatError",
    "PuzzleValidationError",
    "Rule",
    "RuleViolation",
    "Solution",
    "SolveResult",
    "SolveStatus",
    "find_violations",
    "is_valid_solution",
    "iter_solutions",
    "next_hint",
    "parse_puzzle",
    "solve",
]
