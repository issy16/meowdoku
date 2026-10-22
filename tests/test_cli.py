import subprocess
import sys
from pathlib import Path

import pytest

from meowdoku.cli import EXIT_INPUT_ERROR, EXIT_OK, main

FIXTURES = Path(__file__).parent / "fixtures"
EXAMPLE = FIXTURES / "example_5x5.txt"


def write_puzzle(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "puzzle.txt"
    path.write_text(text, encoding="utf-8")
    return path


def run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    code = main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# R6.1 Solving and output


def test_r6_1_unique_puzzle_prints_status_board_and_cats(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = run([str(EXAMPLE)], capsys)
    assert code == EXIT_OK
    assert err == ""
    assert out == (
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
    code, out, _ = run([str(write_puzzle(tmp_path, "AB\nAB"))], capsys)
    assert code == EXIT_OK
    assert out == "NONE\nThis puzzle has no solution.\n"


def test_r6_1_multiple_solutions_shows_first_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run([str(write_puzzle(tmp_path, "ABCD\n" * 4))], capsys)
    assert code == EXIT_OK
    assert out.splitlines()[:4] == [
        "MULTIPLE",
        "Showing the first 2 solutions.",
        "",
        "Solution 1:",
    ]
    assert "Solution 2:" in out
    assert "Solution 3:" not in out


# R6.2 Counting every solution


def test_r6_2_count_all_reports_total(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = write_puzzle(tmp_path, "ABCDEF\n" * 6)
    _, out, _ = run([str(path), "--count-all"], capsys)
    assert out.splitlines()[:3] == ["MULTIPLE", "Solutions: 90", "Showing the first 2 solutions."]
    assert "Solution 3:" not in out


def test_r6_2_count_all_on_unique_puzzle(capsys: pytest.CaptureFixture[str]) -> None:
    _, out, _ = run([str(EXAMPLE), "--count-all"], capsys)
    assert out.splitlines()[:2] == ["UNIQUE", "Solutions: 1"]


# R6.3 Input errors


def test_r6_3_missing_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "missing.txt"
    code, out, err = run([str(missing)], capsys)
    assert code == EXIT_INPUT_ERROR
    assert out == ""
    assert err == f"meowdoku: error: cannot read {missing}: No such file or directory\n"


def test_r6_3_format_error_names_file_and_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = write_puzzle(tmp_path, "ABC\nAB\nABC")
    code, _, err = run([str(path)], capsys)
    assert code == EXIT_INPUT_ERROR
    assert err == f"meowdoku: error: {path}: line 2: row has 2 cells; expected 3 to match the first row (line 1)\n"


def test_r6_3_validation_error_lists_problems(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run([str(write_puzzle(tmp_path, "ABA\nBBB\nBBB"))], capsys)
    assert code == EXIT_INPUT_ERROR
    assert "invalid puzzle:" in err
    assert "  - found 2 regions (A, B); a 3x3 board needs exactly 3" in err
    assert "  - region 'A' is split" in err


def test_r6_3_usage_error_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == EXIT_INPUT_ERROR


def test_r6_3_real_process_has_exit_code_and_no_traceback(tmp_path: Path) -> None:
    path = write_puzzle(tmp_path, "AA\nAA")
    completed = subprocess.run(
        [sys.executable, "-m", "meowdoku", str(path)],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(Path(__file__).parents[1] / "src")},
    )
    assert completed.returncode == EXIT_INPUT_ERROR
    assert completed.stdout == ""
    assert "Traceback" not in completed.stderr
    assert "found 1 region (A)" in completed.stderr
