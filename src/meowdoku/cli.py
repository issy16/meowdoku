"""Command-line interface: `meowdoku SCREENSHOT [--count-all] [--language CODE]` (R6, R12.6)."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from meowdoku.image_import import import_screenshot
from meowdoku.messages import DEFAULT_LANGUAGE, LANGUAGES, Message, count_text, label, render
from meowdoku.parser import format_board
from meowdoku.puzzle import MeowdokuError, Puzzle, describe_cell
from meowdoku.solver import DEFAULT_MAX_SOLUTIONS, Solution, SolveResult, SolveStatus, solve

EXIT_OK = 0
EXIT_INPUT_ERROR = 2


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return the exit code (R6.3)."""
    args = _parse_args(argv)
    path: Path = args.screenshot
    language: str = args.language
    try:
        imported = import_screenshot(path)
    except OSError as error:
        reason = error.strerror or str(error)
        _print_error(render(Message("err.cannot_read", name=str(path), reason=reason), language), language)
        return EXIT_INPUT_ERROR
    except MeowdokuError as error:
        _print_error(f"{path}: {error.text(language)}", language)
        return EXIT_INPUT_ERROR

    print(f"{label('cli.detected', language)}\n{imported.text}\n")
    if imported.cats or imported.crosses:
        print(f"{label('cli.marks', language)}\n{imported.marks_text}\n")
    puzzle = imported.puzzle
    max_solutions = None if args.count_all else DEFAULT_MAX_SOLUTIONS
    result = solve(puzzle, max_solutions=max_solutions)
    print(format_result(puzzle, result, count_all=args.count_all, language=language))
    return EXIT_OK


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    # The help text is worded in the chosen language, so read --language first.
    early = argparse.ArgumentParser(add_help=False)
    early.add_argument("--language", choices=list(LANGUAGES), default=DEFAULT_LANGUAGE)
    language = early.parse_known_args(argv)[0].language

    parser = argparse.ArgumentParser(prog="meowdoku", description=label("cli.description", language))
    parser.add_argument("screenshot", type=Path, help=label("cli.screenshot_help", language))
    parser.add_argument("--count-all", action="store_true", help=label("cli.count_all_help", language))
    parser.add_argument(
        "--language", choices=list(LANGUAGES), default=DEFAULT_LANGUAGE, help=label("cli.language_help", language)
    )
    return parser.parse_args(argv)


def _print_error(message: str, language: str = DEFAULT_LANGUAGE) -> None:
    print(label("cli.error", language, message=message), file=sys.stderr)


def format_result(
    puzzle: Puzzle, result: SolveResult, count_all: bool = False, language: str = DEFAULT_LANGUAGE
) -> str:
    """The status line, an optional solution count, then the solutions shown.

    The status (UNIQUE, NONE, MULTIPLE) stays in English in every language, like a code (R6.1).
    """
    lines = [result.status.name]
    if count_all:
        lines.append(label("cli.solutions", language, n=len(result.solutions)))

    shown = result.solutions[:DEFAULT_MAX_SOLUTIONS]
    if result.status is SolveStatus.NONE:
        lines.append(label("hint.no_solution", language))
    elif result.status is SolveStatus.MULTIPLE:
        lines.append(label("cli.showing", language, n=len(shown)))

    for number, solution in enumerate(shown, start=1):
        lines.append("")
        if len(shown) > 1:
            lines.append(label("cli.solution", language, n=number))
        lines.append(format_board(puzzle, solution.cats))
        lines.append(_format_cat_positions(solution, language))
    return "\n".join(lines)


def _format_cat_positions(solution: Solution, language: str = DEFAULT_LANGUAGE) -> str:
    """List cats with 1-indexed coordinates (R6.4)."""
    cats = sorted(solution.cats)
    separator = label("cli.separator", language)
    positions = separator.join(render(describe_cell(cat), language) for cat in cats)
    return label("cli.cats", language, cats=count_text(len(cats), "cat", language), positions=positions)


if __name__ == "__main__":
    sys.exit(main())
