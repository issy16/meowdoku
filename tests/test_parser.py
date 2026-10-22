from pathlib import Path

import pytest

from meowdoku.parser import format_board, parse_puzzle
from meowdoku.puzzle import Puzzle, PuzzleFormatError, PuzzleValidationError

FIXTURES = Path(__file__).parent / "fixtures"


def format_error_for(text: str) -> PuzzleFormatError:
    with pytest.raises(PuzzleFormatError) as excinfo:
        parse_puzzle(text)
    return excinfo.value


# Valid input


def test_parses_readme_example_fixture() -> None:
    text = (FIXTURES / "example_5x5.txt").read_text(encoding="utf-8")
    puzzle = parse_puzzle(text)
    assert puzzle == Puzzle.from_rows(["AABBB", "ACCCB", "ACDDB", "EEDDB", "EEEBB"])


def test_r3_3_ignores_blank_lines_comments_and_surrounding_whitespace() -> None:
    text = "\n# a comment\n  AB  \n\n   # indented comment\n\tAB\n\n"
    assert parse_puzzle(text) == Puzzle.from_rows(["AB", "AB"])


def test_accepts_windows_line_endings() -> None:
    assert parse_puzzle("AB\r\nAB\r\n") == Puzzle.from_rows(["AB", "AB"])


def test_r3_2_any_non_whitespace_character_is_a_label() -> None:
    puzzle = parse_puzzle("1.\n1.")
    assert puzzle.region_labels == ("1", ".")


def test_hash_after_first_cell_is_a_label_not_a_comment() -> None:
    assert parse_puzzle("A#\nA#").region_labels == ("A", "#")


# R4.1 Empty input


@pytest.mark.parametrize("text", ["", "\n\n", "# only a comment\n   \n"])
def test_r4_1_input_without_rows_is_rejected(text: str) -> None:
    error = format_error_for(text)
    assert error.line is None
    assert str(error) == "no puzzle rows found; the input is empty or only comments"


# R4.2 Whitespace inside a row


def test_r4_2_whitespace_inside_row_reports_its_line() -> None:
    error = format_error_for("# comment\nAB\nA B\n")
    assert error.line == 3
    assert str(error).startswith("line 3: row contains whitespace")


def test_r4_2_tab_inside_row_is_rejected() -> None:
    assert format_error_for("A\tB\nAB").line == 1


# R4.3 Shape


def test_r4_3_unequal_row_length_reports_the_row() -> None:
    error = format_error_for("\nABC\nABC\nAB\n")
    assert error.line == 4
    assert str(error) == "line 4: row has 2 cells; expected 3 to match the first row (line 2)"


def test_r4_3_too_many_rows_reports_first_extra_row() -> None:
    error = format_error_for("AB\nAB\n# comment\nAB\n")
    assert error.line == 4
    assert str(error).startswith("line 4: too many rows")


def test_r4_3_too_few_rows_reports_last_row() -> None:
    error = format_error_for("ABC\nABC\n")
    assert error.line == 2
    assert "the board needs 3 rows but the puzzle ends after 2" in str(error)


# Structural problems pass through from Puzzle


def test_structural_problems_raise_validation_error() -> None:
    with pytest.raises(PuzzleValidationError) as excinfo:
        parse_puzzle("AA\nAA")
    assert excinfo.value.problems == ("found 1 region (A); a 2x2 board needs exactly 2",)


def test_oversized_board_raises_validation_error() -> None:
    rows = [chr(ord("A") + row) * 17 for row in range(17)]
    with pytest.raises(PuzzleValidationError):
        parse_puzzle("\n".join(rows))


# Formatting boards


def test_format_board_marks_cats_with_stars() -> None:
    puzzle = Puzzle.from_rows(["AABBB", "ACCCB", "ACDDB", "EEDDB", "EEEBB"])
    cats = {(0, 4), (1, 2), (2, 0), (3, 3), (4, 1)}
    assert format_board(puzzle, cats) == "AABB*\nAC*CB\n*CDDB\nEED*B\nE*EBB"


def test_format_board_without_cats_round_trips() -> None:
    text = "ABBB\nABCC\nDDCC\nDDDC"
    assert format_board(parse_puzzle(text), set()) == text
