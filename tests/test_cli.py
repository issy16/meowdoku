import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from meowdoku.cli import EXIT_INPUT_ERROR, EXIT_OK, main
from meowdoku.puzzle import Puzzle

from screenshot_factory import draw_screenshot, save

EXAMPLE_ROWS = ["AABBB", "ACCCB", "ACDDB", "EEDDB", "EEEBB"]


def screenshot(tmp_path: Path, rows: list[str]) -> Path:
    """A synthetic screenshot of the board."""
    return save(draw_screenshot(Puzzle.from_rows(rows)), tmp_path / "board.png")


def run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    code = main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# R6.1 Solving and output


def test_r6_1_unique_puzzle_prints_grid_status_board_and_cats(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, err = run([str(screenshot(tmp_path, EXAMPLE_ROWS))], capsys)
    assert code == EXIT_OK
    assert err == ""
    assert out == (
        "Detected puzzle:\n"
        "AABBB\nACCCB\nACDDB\nEEDDB\nEEEBB\n"
        "\n"
        "UNIQUE\n"
        "\n"
        "AABB*\n"
        "AC*CB\n"
        "*CDDB\n"
        "EED*B\n"
        "E*EBB\n"
        "5 cats: row 1, column 5; row 2, column 3; row 3, column 1; "
        "row 4, column 4; row 5, column 2\n"
    )


def test_r6_1_unsolvable_puzzle_exits_ok(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run([str(screenshot(tmp_path, ["AB", "AB"]))], capsys)
    assert code == EXIT_OK
    assert out.endswith("NONE\nThis puzzle has no solution.\n")


def test_r6_1_multiple_solutions_shows_first_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run([str(screenshot(tmp_path, ["ABCD"] * 4))], capsys)
    assert code == EXIT_OK
    assert "MULTIPLE\nShowing the first 2 solutions.\n\nSolution 1:" in out
    assert "Solution 2:" in out
    assert "Solution 3:" not in out


# R6.2 Counting every solution


def test_r6_2_count_all_reports_total(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, out, _ = run([str(screenshot(tmp_path, ["ABCDEF"] * 6)), "--count-all"], capsys)
    assert "MULTIPLE\nSolutions: 90\nShowing the first 2 solutions." in out
    assert "Solution 3:" not in out


def test_r6_2_count_all_on_unique_puzzle(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, out, _ = run([str(screenshot(tmp_path, EXAMPLE_ROWS)), "--count-all"], capsys)
    assert "UNIQUE\nSolutions: 1\n" in out


# R6.3 Input errors


def test_r6_3_text_puzzle_files_are_not_accepted(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "puzzle.txt"
    path.write_text("\n".join(EXAMPLE_ROWS), encoding="utf-8")
    code, out, err = run([str(path)], capsys)
    assert code == EXIT_INPUT_ERROR
    assert out == ""
    assert err == (
        f"meowdoku: error: {path}: puzzle.txt is not a screenshot; use a .png, .jpg, or .jpeg file\n"
    )


def test_r6_3_missing_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "missing.png"
    code, out, err = run([str(missing)], capsys)
    assert code == EXIT_INPUT_ERROR
    assert out == ""
    assert err == f"meowdoku: error: cannot read {missing}: No such file or directory\n"


def test_r6_3_screenshot_without_a_board(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "blank.png"
    Image.new("RGB", (300, 500), "white").save(path)
    code, _, err = run([str(path)], capsys)
    assert code == EXIT_INPUT_ERROR
    assert "couldn't find the board" in err


def test_r6_3_usage_error_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == EXIT_INPUT_ERROR


def test_r6_3_real_process_has_exit_code_and_no_traceback(tmp_path: Path) -> None:
    path = tmp_path / "puzzle.txt"
    path.write_text("AA\nAA", encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, "-m", "meowdoku", str(path)],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(Path(__file__).parents[1] / "src")},
    )
    assert completed.returncode == EXIT_INPUT_ERROR
    assert completed.stdout == ""
    assert "Traceback" not in completed.stderr
    assert "is not a screenshot" in completed.stderr
