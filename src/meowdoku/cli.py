"""Command-line interface: `meowdoku PUZZLE_FILE [--count-all]` (R6).

PUZZLE_FILE may be a text puzzle or a PNG/JPEG screenshot (R6.5)."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from meowdoku.image_import import import_screenshot, is_image_path
from meowdoku.parser import format_board, read_puzzle_file
from meowdoku.puzzle import MeowdokuError, Puzzle, count_of, describe_cell
from meowdoku.solver import DEFAULT_MAX_SOLUTIONS, Solution, SolveResult, SolveStatus, solve

EXIT_OK = 0
EXIT_INPUT_ERROR = 2


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return the exit code (R6.3)."""
    args = _parse_args(argv)
    path: Path = args.puzzle_file
    try:
        if is_image_path(path):
            imported = import_screenshot(path)
            print(f"Detected puzzle:\n{imported.text}\n")
            puzzle = imported.puzzle
        else:
            puzzle = read_puzzle_file(path)
    except OSError as error:
        _print_error(f"cannot read {path}: {error.strerror or error}")
        return EXIT_INPUT_ERROR
    except MeowdokuError as error:
        _print_error(f"{path}: {error}")
        return EXIT_INPUT_ERROR

    max_solutions = None if args.count_all else DEFAULT_MAX_SOLUTIONS
    result = solve(puzzle, max_solutions=max_solutions)
    print(format_result(puzzle, result, count_all=args.count_all))
    return EXIT_OK


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="meowdoku",
        description="Solve a Meowdoku puzzle and report whether it has none, one, or several solutions.",
    )
    parser.add_argument(
        "puzzle_file", type=Path, help="puzzle text file, or a .png/.jpg screenshot (see README.md)"
    )
    parser.add_argument(
        "--count-all",
        action="store_true",
        help="count every solution instead of stopping at two (may be slow)",
    )
    return parser.parse_args(argv)


def _print_error(message: str) -> None:
    print(f"meowdoku: error: {message}", file=sys.stderr)


def format_result(puzzle: Puzzle, result: SolveResult, count_all: bool = False) -> str:
    """The status line, an optional solution count, then the solutions shown."""
    lines = [result.status.name]
    if count_all:
        lines.append(f"Solutions: {len(result.solutions)}")

    shown = result.solutions[:DEFAULT_MAX_SOLUTIONS]
    if result.status is SolveStatus.NONE:
        lines.append("This puzzle has no solution.")
    elif result.status is SolveStatus.MULTIPLE:
        lines.append(f"Showing the first {len(shown)} solutions.")

    for number, solution in enumerate(shown, start=1):
        lines.append("")
        if len(shown) > 1:
            lines.append(f"Solution {number}:")
        lines.append(format_board(puzzle, solution.cats))
        lines.append(_format_cat_positions(solution))
    return "\n".join(lines)


def _format_cat_positions(solution: Solution) -> str:
    """List cats with 1-indexed coordinates (R6.4)."""
    cats = sorted(solution.cats)
    return f"{count_of(len(cats), 'cat')}: " + "; ".join(describe_cell(cat) for cat in cats)


if __name__ == "__main__":
    sys.exit(main())
