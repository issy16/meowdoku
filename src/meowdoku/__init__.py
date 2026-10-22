"""Meowdoku Solver: solve Meowdoku puzzles with backtracking search."""

from meowdoku.parser import parse_puzzle
from meowdoku.puzzle import (
    Cell,
    MeowdokuError,
    Puzzle,
    PuzzleFormatError,
    PuzzleValidationError,
)
from meowdoku.rules import Rule, RuleViolation, find_violations, is_valid_solution

__version__ = "0.1.0"

__all__ = [
    "Cell",
    "MeowdokuError",
    "Puzzle",
    "PuzzleFormatError",
    "PuzzleValidationError",
    "Rule",
    "RuleViolation",
    "find_violations",
    "is_valid_solution",
    "parse_puzzle",
]
