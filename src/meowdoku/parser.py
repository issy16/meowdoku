"""Read puzzles from the text format described in docs/requirements.md (R3)."""

from dataclasses import dataclass

from meowdoku.puzzle import Puzzle, PuzzleFormatError, count_of

COMMENT_PREFIX = "#"


@dataclass(frozen=True)
class _SourceRow:
    """One board row and the 1-indexed line it came from."""

    line: int
    text: str


def parse_puzzle(text: str) -> Puzzle:
    """Parse puzzle text into a validated Puzzle.

    Raises PuzzleFormatError for malformed text (R4.1-R4.3) and
    PuzzleValidationError for structural problems (R4.4-R4.6).
    """
    rows = _read_rows(text)
    _check_square(rows)
    return Puzzle.from_rows([row.text for row in rows])


def _read_rows(text: str) -> list[_SourceRow]:
    """Collect board rows, skipping blank lines and comments (R3.3)."""
    rows = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(COMMENT_PREFIX):
            continue
        if any(char.isspace() for char in stripped):
            raise PuzzleFormatError(
                "row contains whitespace; write one region label per cell with no spaces",
                line_number,
            )
        rows.append(_SourceRow(line_number, stripped))
    if not rows:
        raise PuzzleFormatError("no puzzle rows found; the input is empty or only comments")
    return rows


def _check_square(rows: list[_SourceRow]) -> None:
    """Require equal-length rows and as many rows as cells per row (R4.3)."""
    first = rows[0]
    width = len(first.text)
    for row in rows[1:]:
        if len(row.text) != width:
            raise PuzzleFormatError(
                f"row has {count_of(len(row.text), 'cell')}; expected {width} "
                f"to match the first row (line {first.line})",
                row.line,
            )
    if len(rows) > width:
        raise PuzzleFormatError(
            f"too many rows; rows are {width} cells wide, so the board needs exactly {width} rows",
            rows[width].line,
        )
    if len(rows) < width:
        raise PuzzleFormatError(
            f"too few rows; rows are {width} cells wide, so the board needs {width} rows "
            f"but the puzzle ends after {len(rows)}",
            rows[-1].line,
        )
